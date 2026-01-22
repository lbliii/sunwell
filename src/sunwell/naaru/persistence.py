"""Plan persistence and incremental execution for RFC-040.

This module enables saving artifact graphs and execution state to disk for:
- Resume: Pick up interrupted builds mid-wave
- Audit: See what was planned vs executed
- Incremental: Skip unchanged artifacts, re-run only what's affected
- Preview: Show the plan before committing tokens/time

Storage structure:
    .sunwell/
    ├── plans/
    │   ├── <goal_hash>.json          # Saved plan + execution state
    │   └── <goal_hash>.trace.jsonl   # Execution events (append-only)
    └── hashes/
        └── <goal_hash>.json          # Content hashes for incremental

Example:
    >>> store = PlanStore()
    >>> execution = SavedExecution(goal="Build API", graph=graph)
    >>> store.save(execution)
    >>>
    >>> # Later, resume:
    >>> loaded = store.find_by_goal("Build API")
    >>> remaining = loaded.get_remaining_artifacts()
"""


import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sunwell.naaru.artifacts import ArtifactGraph
from sunwell.naaru.executor import ArtifactResult, ExecutionResult

# =============================================================================
# Constants
# =============================================================================

PERSISTENCE_VERSION = "1.0"
DEFAULT_PLANS_DIR = Path(".sunwell/plans")
DEFAULT_HASHES_DIR = Path(".sunwell/hashes")


# =============================================================================
# Execution Status
# =============================================================================


class ExecutionStatus(Enum):
    """Status of a saved execution."""

    PLANNED = "planned"  # Graph created, not started
    IN_PROGRESS = "in_progress"  # Executing waves
    PAUSED = "paused"  # Interrupted, can resume
    COMPLETED = "completed"  # All artifacts done
    FAILED = "failed"  # Execution failed


# =============================================================================
# Content Hashing
# =============================================================================


def hash_goal(goal: str) -> str:
    """Hash a goal string for deterministic lookup.

    Args:
        goal: The goal text

    Returns:
        16-character hex hash
    """
    return hashlib.sha256(goal.encode()).hexdigest()[:16]


def hash_content(content: str | bytes) -> str:
    """Hash content for change detection.

    Args:
        content: String or bytes to hash

    Returns:
        16-character hex hash
    """
    if isinstance(content, str):
        content = content.encode()
    return hashlib.sha256(content).hexdigest()[:16]


def hash_file(path: Path) -> str | None:
    """Hash a file's contents for change detection.

    Args:
        path: Path to file

    Returns:
        16-character hex hash, or None if file doesn't exist
    """
    if not path.exists():
        return None
    return hash_content(path.read_bytes())


# =============================================================================
# Artifact Completion Record
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArtifactCompletion:
    """Record of a completed artifact.

    Attributes:
        artifact_id: The artifact that was created
        content_hash: SHA-256 hash of output (truncated to 16 chars)
        model_tier: Model tier used (small/medium/large)
        duration_ms: Creation time in milliseconds
        verified: Whether the artifact passed verification
        completed_at: When the artifact was completed
    """

    artifact_id: str
    content_hash: str
    model_tier: str = "medium"
    duration_ms: int = 0
    verified: bool = False
    completed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "content_hash": self.content_hash,
            "model_tier": self.model_tier,
            "duration_ms": self.duration_ms,
            "verified": self.verified,
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactCompletion:
        """Create from dict."""
        return cls(
            artifact_id=data["artifact_id"],
            content_hash=data["content_hash"],
            model_tier=data.get("model_tier", "medium"),
            duration_ms=data.get("duration_ms", 0),
            verified=data.get("verified", False),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if "completed_at" in data
            else datetime.now(),
        )

    @classmethod
    def from_result(cls, result: ArtifactResult) -> ArtifactCompletion:
        """Create from an ArtifactResult."""
        content_hash = hash_content(result.content) if result.content else ""
        return cls(
            artifact_id=result.artifact_id,
            content_hash=content_hash,
            model_tier=result.model_tier,
            duration_ms=result.duration_ms,
            verified=result.verified,
        )


# =============================================================================
# SavedExecution
# =============================================================================


@dataclass
class SavedExecution:
    """Complete state for a goal's execution.

    Combines plan (ArtifactGraph), checkpoint (progress), and trace (events).

    Attributes:
        goal: Original goal text
        goal_hash: Deterministic hash for lookup
        graph: The artifact graph (plan)
        status: Current execution status
        completed: Completed artifacts with metadata
        failed: Failed artifacts with error messages
        content_hashes: Content hashes for incremental rebuild
        current_wave: Wave currently being executed (for resume)
        created_at: When the plan was created
        updated_at: When the execution was last updated
        model_distribution: Count of each model tier used
    """

    goal: str
    graph: ArtifactGraph
    goal_hash: str = ""
    status: ExecutionStatus = ExecutionStatus.PLANNED
    completed: dict[str, ArtifactCompletion] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    content_hashes: dict[str, str] = field(default_factory=dict)
    current_wave: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    model_distribution: dict[str, int] = field(
        default_factory=lambda: {"small": 0, "medium": 0, "large": 0}
    )

    def __post_init__(self) -> None:
        """Initialize goal_hash if not provided."""
        if not self.goal_hash:
            self.goal_hash = hash_goal(self.goal)

    @property
    def completed_ids(self) -> set[str]:
        """Get set of completed artifact IDs."""
        return set(self.completed.keys())

    @property
    def failed_ids(self) -> set[str]:
        """Get set of failed artifact IDs."""
        return set(self.failed.keys())

    @property
    def pending_ids(self) -> set[str]:
        """Get set of pending artifact IDs."""
        all_ids = set(self.graph)
        return all_ids - self.completed_ids - self.failed_ids

    @property
    def is_complete(self) -> bool:
        """Check if all artifacts are completed or failed."""
        return len(self.pending_ids) == 0

    @property
    def progress_percent(self) -> float:
        """Get completion percentage."""
        total = len(self.graph)
        if total == 0:
            return 100.0
        return (len(self.completed) / total) * 100

    def get_remaining_artifacts(self) -> list[str]:
        """Get artifact IDs that haven't been completed or failed."""
        return list(self.pending_ids)

    def get_resume_wave(self) -> int:
        """Find which wave to resume from.

        Returns:
            Index of first incomplete wave
        """
        waves = self.graph.execution_waves()
        for i, wave in enumerate(waves):
            if not all(aid in self.completed for aid in wave):
                return i
        return len(waves)  # All complete

    def mark_completed(self, result: ArtifactResult) -> None:
        """Mark an artifact as completed.

        Args:
            result: The artifact result
        """
        completion = ArtifactCompletion.from_result(result)
        self.completed[result.artifact_id] = completion
        if result.content:
            self.content_hashes[result.artifact_id] = completion.content_hash
        self.model_distribution[result.model_tier] += 1
        self.updated_at = datetime.now()

    def mark_failed(self, artifact_id: str, error: str) -> None:
        """Mark an artifact as failed.

        Args:
            artifact_id: The artifact that failed
            error: Error message
        """
        self.failed[artifact_id] = error
        self.updated_at = datetime.now()

    def update_from_result(self, result: ExecutionResult) -> None:
        """Update from an ExecutionResult.

        Args:
            result: The execution result to merge
        """
        for artifact_id, artifact_result in result.completed.items():
            self.mark_completed(artifact_result)
        for artifact_id, error in result.failed.items():
            self.mark_failed(artifact_id, error)

        # Update status
        if self.is_complete:
            self.status = (
                ExecutionStatus.COMPLETED if not self.failed else ExecutionStatus.FAILED
            )
        else:
            self.status = ExecutionStatus.IN_PROGRESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": PERSISTENCE_VERSION,
            "goal": self.goal,
            "goal_hash": self.goal_hash,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "graph": self.graph.to_dict(),
            "execution": {
                "current_wave": self.current_wave,
                "completed": {
                    aid: comp.to_dict() for aid, comp in self.completed.items()
                },
                "failed": self.failed,
            },
            "content_hashes": self.content_hashes,
            "metrics": {
                "total_artifacts": len(self.graph),
                "completed_count": len(self.completed),
                "failed_count": len(self.failed),
                "progress_percent": self.progress_percent,
                "model_distribution": self.model_distribution,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SavedExecution:
        """Create from dict."""
        graph = ArtifactGraph.from_dict(data["graph"])
        execution = data.get("execution", {})

        completed = {
            aid: ArtifactCompletion.from_dict(comp)
            for aid, comp in execution.get("completed", {}).items()
        }

        model_dist = data.get("metrics", {}).get(
            "model_distribution", {"small": 0, "medium": 0, "large": 0}
        )

        return cls(
            goal=data["goal"],
            goal_hash=data.get("goal_hash", hash_goal(data["goal"])),
            graph=graph,
            status=ExecutionStatus(data.get("status", "planned")),
            completed=completed,
            failed=execution.get("failed", {}),
            content_hashes=data.get("content_hashes", {}),
            current_wave=execution.get("current_wave", 0),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(),
            model_distribution=model_dist,
        )


# =============================================================================
# PlanStore
# =============================================================================


@dataclass
class PlanStore:
    """Manages plan persistence with file locking.

    Thread-safe storage for SavedExecution objects.

    Attributes:
        base_path: Directory for plan files
        _lock: Thread lock for concurrent access

    Example:
        >>> store = PlanStore()
        >>> execution = SavedExecution(goal="Build API", graph=graph)
        >>> path = store.save(execution)
        >>>
        >>> # Load by goal hash
        >>> loaded = store.load(execution.goal_hash)
        >>>
        >>> # Or find by goal text
        >>> found = store.find_by_goal("Build API")
    """

    base_path: Path = field(default_factory=lambda: DEFAULT_PLANS_DIR)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        """Ensure storage directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, execution: SavedExecution) -> Path:
        """Save execution state to disk (thread-safe).

        Args:
            execution: The execution state to save

        Returns:
            Path to saved file
        """
        path = self.base_path / f"{execution.goal_hash}.json"

        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file, then atomic rename
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(execution.to_dict(), f, indent=2)
            temp_path.rename(path)

        return path

    def load(self, goal_hash: str) -> SavedExecution | None:
        """Load execution state from disk.

        Args:
            goal_hash: The goal hash to load

        Returns:
            SavedExecution if found, None otherwise
        """
        path = self.base_path / f"{goal_hash}.json"
        if not path.exists():
            return None

        with open(path) as f:
            return SavedExecution.from_dict(json.load(f))

    def find_by_goal(self, goal: str) -> SavedExecution | None:
        """Find execution by goal text (computes hash).

        Args:
            goal: The goal text

        Returns:
            SavedExecution if found, None otherwise
        """
        goal_hash = hash_goal(goal)
        return self.load(goal_hash)

    def exists(self, goal_hash: str) -> bool:
        """Check if a plan exists.

        Args:
            goal_hash: The goal hash to check

        Returns:
            True if plan exists
        """
        path = self.base_path / f"{goal_hash}.json"
        return path.exists()

    def delete(self, goal_hash: str) -> bool:
        """Delete a saved plan.

        Args:
            goal_hash: The goal hash to delete

        Returns:
            True if deleted, False if not found
        """
        path = self.base_path / f"{goal_hash}.json"
        trace_path = path.with_suffix(".trace.jsonl")

        deleted = False
        with self._lock:
            if path.exists():
                path.unlink()
                deleted = True
            if trace_path.exists():
                trace_path.unlink()

        return deleted

    def list_recent(self, limit: int = 10) -> list[SavedExecution]:
        """List recent executions.

        Args:
            limit: Maximum number to return

        Returns:
            List of SavedExecution objects, most recent first
        """
        if not self.base_path.exists():
            return []

        plans = sorted(
            self.base_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        results = []
        for p in plans[:limit]:
            if p.suffix == ".json" and not p.name.endswith(".trace.jsonl"):
                execution = self.load(p.stem)
                if execution:
                    results.append(execution)

        return results

    def list_all(self) -> list[tuple[str, Path]]:
        """List all saved plans.

        Returns:
            List of (goal_hash, path) tuples
        """
        if not self.base_path.exists():
            return []

        return [
            (p.stem, p)
            for p in self.base_path.glob("*.json")
            if not p.name.endswith(".trace.jsonl")
        ]

    def get_plan_age_hours(self, goal_hash: str) -> float | None:
        """Get age of a plan in hours.

        Args:
            goal_hash: The goal hash

        Returns:
            Age in hours, or None if not found
        """
        path = self.base_path / f"{goal_hash}.json"
        if not path.exists():
            return None

        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return (datetime.now() - mtime).total_seconds() / 3600

    def clean_old(self, max_age_hours: float = 168.0) -> int:
        """Clean plans older than max_age_hours.

        Args:
            max_age_hours: Maximum age (default: 1 week)

        Returns:
            Number of plans deleted
        """
        deleted = 0
        for goal_hash, _path in self.list_all():
            age = self.get_plan_age_hours(goal_hash)
            if age and age > max_age_hours and self.delete(goal_hash):
                deleted += 1
        return deleted


# =============================================================================
# Trace Logging
# =============================================================================


@dataclass
class TraceLogger:
    """Append-only event logging for execution trace.

    Writes JSONL format for easy streaming and analysis.

    Example:
        >>> logger = TraceLogger(goal_hash="abc123")
        >>> logger.log_event("plan_created", artifact_count=5)
        >>> logger.log_event("wave_start", wave=0, artifacts=["A", "B"])
    """

    goal_hash: str
    base_path: Path = field(default_factory=lambda: DEFAULT_PLANS_DIR)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def trace_path(self) -> Path:
        """Get path to trace file."""
        return self.base_path / f"{self.goal_hash}.trace.jsonl"

    def log_event(self, event: str, **kwargs: Any) -> None:
        """Log an event to the trace file.

        Args:
            event: Event type (plan_created, wave_start, artifact_complete, etc.)
            **kwargs: Additional event data
        """
        record = {
            "ts": datetime.now().isoformat(),
            "event": event,
            **kwargs,
        }

        with self._lock:
            self.base_path.mkdir(parents=True, exist_ok=True)
            with open(self.trace_path, "a") as f:
                f.write(json.dumps(record) + "\n")

    def read_events(self) -> list[dict[str, Any]]:
        """Read all events from trace file.

        Returns:
            List of event records
        """
        if not self.trace_path.exists():
            return []

        events = []
        with open(self.trace_path) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def clear(self) -> None:
        """Clear the trace file."""
        with self._lock:
            if self.trace_path.exists():
                self.trace_path.unlink()


# =============================================================================
# Resume Support
# =============================================================================


async def resume_execution(
    execution: SavedExecution,
    create_fn,  # CreateArtifactFn
    on_progress=None,
) -> ExecutionResult:
    """Resume a paused or incomplete execution.

    Args:
        execution: The saved execution to resume
        create_fn: Function to create artifacts
        on_progress: Optional progress callback

    Returns:
        ExecutionResult with completed/failed artifacts
    """
    import asyncio

    from sunwell.naaru.executor import ArtifactResult

    # Find completed wave
    completed_ids = execution.completed_ids
    waves = execution.graph.execution_waves()

    resume_from_wave = execution.get_resume_wave()

    if on_progress:
        on_progress(f"Resuming from wave {resume_from_wave + 1}/{len(waves)}")

    # Execute remaining waves
    result = ExecutionResult(
        completed={
            aid: ArtifactResult(
                artifact_id=aid,
                content=None,  # Content not preserved
                verified=comp.verified,
                model_tier=comp.model_tier,
                duration_ms=comp.duration_ms,
            )
            for aid, comp in execution.completed.items()
        },
        failed=dict(execution.failed),
    )

    for wave_num in range(resume_from_wave, len(waves)):
        wave = waves[wave_num]

        # Filter to incomplete artifacts in this wave
        to_execute = [aid for aid in wave if aid not in completed_ids]

        if not to_execute:
            continue

        if on_progress:
            on_progress(f"Wave {wave_num + 1}: {', '.join(to_execute)}")

        # Execute wave
        wave_results = await asyncio.gather(
            *[create_fn(execution.graph[aid]) for aid in to_execute],
            return_exceptions=True,
        )

        # Process results
        for artifact_id, wave_result in zip(to_execute, wave_results, strict=True):
            if isinstance(wave_result, Exception):
                result.failed[artifact_id] = str(wave_result)
            elif isinstance(wave_result, str):
                # create_fn returns string content
                artifact_result = ArtifactResult(
                    artifact_id=artifact_id,
                    content=wave_result,
                    verified=False,
                )
                result.completed[artifact_id] = artifact_result
            else:
                result.completed[artifact_id] = wave_result

    return result


# =============================================================================
# Utility Functions
# =============================================================================


def get_latest_execution(goal: str | None = None) -> SavedExecution | None:
    """Get the most recent execution, optionally for a specific goal.

    Args:
        goal: Optional goal text to match

    Returns:
        Most recent SavedExecution, or None
    """
    store = PlanStore()

    if goal:
        return store.find_by_goal(goal)

    recent = store.list_recent(limit=1)
    return recent[0] if recent else None


def save_execution(execution: SavedExecution) -> Path:
    """Save an execution to the default store.

    Args:
        execution: The execution to save

    Returns:
        Path to saved file
    """
    store = PlanStore()
    return store.save(execution)
