"""Persistent run storage for Observatory (RFC-112 Observatory Maturation).

Persists runs and their events to disk so they can be viewed later in
the Observatory. Each run is stored as a JSON file with all its events.

Storage structure:
    ~/.sunwell/runs/
        {run_id}.json  - Run metadata + events

Features:
- Automatic persistence when runs complete
- Load historical runs on demand
- Compute Observatory visualization data from events
- Thread-safe file operations
"""

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default storage location
DEFAULT_RUNS_DIR = Path.home() / ".sunwell" / "runs"


@dataclass(frozen=True, slots=True)
class StoredRun:
    """A persisted run with metadata and events."""

    run_id: str
    goal: str
    status: str
    source: str
    started_at: str  # ISO format
    completed_at: str | None
    workspace: str | None
    project_id: str | None
    lens: str | None
    model: str | None
    events: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "status": self.status,
            "source": self.source,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "workspace": self.workspace,
            "project_id": self.project_id,
            "lens": self.lens,
            "model": self.model,
            "events": list(self.events),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredRun":
        """Deserialize from dict."""
        return cls(
            run_id=data["run_id"],
            goal=data["goal"],
            status=data["status"],
            source=data.get("source", "unknown"),
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            workspace=data.get("workspace"),
            project_id=data.get("project_id"),
            lens=data.get("lens"),
            model=data.get("model"),
            events=tuple(data.get("events", [])),
        )


@dataclass(frozen=True, slots=True)
class ObservatorySnapshot:
    """Pre-computed Observatory visualization data for a run.

    Contains the extracted state for each visualization:
    - ResonanceWave: refinement iterations
    - PrismFracture: candidate generation/scoring
    - ExecutionCinema: task execution
    - MemoryLattice: learnings and concepts
    - ConvergenceProgress: convergence loop iterations
    """

    run_id: str
    resonance_iterations: tuple[dict[str, Any], ...]
    prism_candidates: tuple[dict[str, Any], ...]
    selected_candidate: dict[str, Any] | None
    tasks: tuple[dict[str, Any], ...]
    learnings: tuple[str, ...]
    convergence_iterations: tuple[dict[str, Any], ...]
    convergence_status: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        return {
            "run_id": self.run_id,
            "resonance_iterations": list(self.resonance_iterations),
            "prism_candidates": list(self.prism_candidates),
            "selected_candidate": self.selected_candidate,
            "tasks": list(self.tasks),
            "learnings": list(self.learnings),
            "convergence_iterations": list(self.convergence_iterations),
            "convergence_status": self.convergence_status,
        }


def _extract_observatory_snapshot(run: StoredRun) -> ObservatorySnapshot:
    """Extract Observatory visualization data from run events.

    Processes the event stream to build the state each visualization needs.
    """
    resonance_iterations: list[dict[str, Any]] = []
    prism_candidates: dict[str, dict[str, Any]] = {}  # id -> candidate
    selected_candidate: dict[str, Any] | None = None
    tasks: dict[str, dict[str, Any]] = {}  # id -> task
    learnings: list[str] = []
    convergence_iterations: list[dict[str, Any]] = []
    convergence_status: str | None = None

    for event in run.events:
        event_type = event.get("type", "")
        data = event.get("data", {})

        # ResonanceWave: Refinement events
        if event_type == "plan_refine_start":
            resonance_iterations.append({
                "round": data.get("round", 0),
                "current_score": data.get("current_score", 0),
                "improvements_identified": data.get("improvements_identified", ""),
                "improved": False,
            })
        elif event_type == "plan_refine_complete":
            round_num = data.get("round", 0)
            for it in resonance_iterations:
                if it["round"] == round_num:
                    it["improved"] = data.get("improved", False)
                    it["old_score"] = data.get("old_score")
                    it["new_score"] = data.get("new_score")
                    it["improvement"] = data.get("improvement")
                    it["reason"] = data.get("reason")
                    break

        # PrismFracture: Candidate generation events
        elif event_type == "plan_candidate_generated":
            candidate_id = data.get("candidate_id", "")
            if candidate_id:
                prism_candidates[candidate_id] = {
                    "id": candidate_id,
                    "artifact_count": data.get("artifact_count", 0),
                    "variance_config": data.get("variance_config"),
                }
        elif event_type == "plan_candidate_scored":
            candidate_id = data.get("candidate_id", "")
            if candidate_id in prism_candidates:
                prism_candidates[candidate_id]["score"] = data.get("score")
                prism_candidates[candidate_id]["metrics"] = data.get("metrics")
        elif event_type == "plan_winner":
            selected_id = data.get("selected_candidate_id", "")
            if selected_id in prism_candidates:
                selected_candidate = prism_candidates[selected_id].copy()
                selected_candidate["selection_reason"] = data.get("selection_reason", "")
            else:
                selected_candidate = {
                    "id": selected_id,
                    "artifact_count": data.get("artifact_count", 0),
                    "score": data.get("score"),
                    "selection_reason": data.get("selection_reason", ""),
                }

        # ExecutionCinema: Task events
        elif event_type == "task_start":
            task_id = data.get("task_id", "")
            if task_id:
                tasks[task_id] = {
                    "id": task_id,
                    "description": data.get("description", ""),
                    "status": "running",
                    "progress": 0,
                }
        elif event_type == "task_progress":
            task_id = data.get("task_id", "")
            if task_id in tasks:
                tasks[task_id]["progress"] = data.get("progress", 0)
        elif event_type == "task_complete":
            task_id = data.get("task_id", "")
            if task_id in tasks:
                tasks[task_id]["status"] = "complete"
                tasks[task_id]["progress"] = 100
        elif event_type == "task_failed":
            task_id = data.get("task_id", "")
            if task_id in tasks:
                tasks[task_id]["status"] = "failed"

        # MemoryLattice: Learning events
        elif event_type == "memory_learning":
            fact = data.get("fact", "")
            if fact:
                learnings.append(fact)

        # ConvergenceProgress: Convergence events
        elif event_type == "convergence_start":
            convergence_status = "running"
        elif event_type == "convergence_iteration_complete":
            convergence_iterations.append({
                "iteration": data.get("iteration", 0),
                "all_passed": data.get("all_passed", False),
                "total_errors": data.get("total_errors", 0),
                "gate_results": data.get("gate_results", []),
            })
        elif event_type == "convergence_stable":
            convergence_status = "stable"
        elif event_type == "convergence_timeout":
            convergence_status = "timeout"
        elif event_type == "convergence_stuck":
            convergence_status = "stuck"
        elif event_type == "convergence_max_iterations":
            convergence_status = "escalated"

    return ObservatorySnapshot(
        run_id=run.run_id,
        resonance_iterations=tuple(resonance_iterations),
        prism_candidates=tuple(prism_candidates.values()),
        selected_candidate=selected_candidate,
        tasks=tuple(tasks.values()),
        learnings=tuple(learnings),
        convergence_iterations=tuple(convergence_iterations),
        convergence_status=convergence_status,
    )


class RunStore:
    """Persistent storage for runs and their events.

    Thread-safe file-based storage that:
    - Saves completed runs automatically
    - Loads historical runs on demand
    - Computes Observatory visualization snapshots

    Example:
        >>> store = RunStore()
        >>> store.save_run(run_state)  # After run completes
        >>> runs = store.list_runs(limit=20)
        >>> snapshot = store.get_observatory_snapshot("run-123")
    """

    def __init__(self, runs_dir: Path | None = None) -> None:
        """Initialize run store.

        Args:
            runs_dir: Directory for run storage. Defaults to ~/.sunwell/runs/
        """
        self._runs_dir = runs_dir or DEFAULT_RUNS_DIR
        self._lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create storage directory if it doesn't exist."""
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: str) -> Path:
        """Get path for a run's JSON file."""
        return self._runs_dir / f"{run_id}.json"

    def save_run(self, run: Any) -> None:
        """Save a run to disk.

        Args:
            run: RunState object from RunManager
        """
        try:
            # Convert RunState to StoredRun format
            stored = StoredRun(
                run_id=run.run_id,
                goal=run.goal,
                status=run.status,
                source=run.source,
                started_at=run.started_at.isoformat() if run.started_at else "",
                completed_at=run.completed_at.isoformat() if run.completed_at else None,
                workspace=run.workspace,
                project_id=run.project_id,
                lens=run.lens,
                model=run.model,
                events=tuple(run.events),
            )

            with self._lock:
                path = self._run_path(run.run_id)
                path.write_text(json.dumps(stored.to_dict(), indent=2))
                logger.debug(f"Saved run {run.run_id} to {path}")

        except Exception as e:
            logger.error(f"Failed to save run {run.run_id}: {e}")

    def load_run(self, run_id: str) -> StoredRun | None:
        """Load a run from disk.

        Args:
            run_id: The run ID to load.

        Returns:
            StoredRun or None if not found.
        """
        try:
            path = self._run_path(run_id)
            if not path.exists():
                return None

            with self._lock:
                data = json.loads(path.read_text())
                return StoredRun.from_dict(data)

        except Exception as e:
            logger.error(f"Failed to load run {run_id}: {e}")
            return None

    def list_runs(
        self,
        limit: int = 50,
        project_id: str | None = None,
    ) -> list[StoredRun]:
        """List stored runs, most recent first.

        Args:
            limit: Maximum number of runs to return.
            project_id: Optional filter by project.

        Returns:
            List of StoredRun objects.
        """
        runs: list[StoredRun] = []

        try:
            with self._lock:
                # Get all run files sorted by modification time (newest first)
                files = sorted(
                    self._runs_dir.glob("*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )

                for path in files[:limit * 2]:  # Read extra in case of filtering
                    try:
                        data = json.loads(path.read_text())
                        run = StoredRun.from_dict(data)

                        # Apply project filter
                        if project_id and run.project_id != project_id:
                            continue

                        runs.append(run)
                        if len(runs) >= limit:
                            break

                    except Exception as e:
                        logger.warning(f"Failed to load run from {path}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to list runs: {e}")

        return runs

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        """Get all events for a run.

        Args:
            run_id: The run ID.

        Returns:
            List of event dicts.
        """
        run = self.load_run(run_id)
        if run is None:
            return []
        return list(run.events)

    def get_observatory_snapshot(self, run_id: str) -> ObservatorySnapshot | None:
        """Get pre-computed Observatory visualization data for a run.

        Args:
            run_id: The run ID.

        Returns:
            ObservatorySnapshot or None if run not found.
        """
        run = self.load_run(run_id)
        if run is None:
            return None
        return _extract_observatory_snapshot(run)

    def delete_run(self, run_id: str) -> bool:
        """Delete a stored run.

        Args:
            run_id: The run ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        try:
            path = self._run_path(run_id)
            if path.exists():
                with self._lock:
                    path.unlink()
                    logger.debug(f"Deleted run {run_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete run {run_id}: {e}")
            return False

    def cleanup_old_runs(self, max_age_days: int = 30, max_runs: int = 500) -> int:
        """Clean up old runs to prevent unbounded growth.

        Args:
            max_age_days: Delete runs older than this.
            max_runs: Keep at most this many runs.

        Returns:
            Number of runs deleted.
        """
        deleted = 0
        cutoff = datetime.now(UTC).timestamp() - (max_age_days * 86400)

        try:
            with self._lock:
                files = sorted(
                    self._runs_dir.glob("*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )

                for i, path in enumerate(files):
                    # Delete if over max_runs limit
                    if i >= max_runs:
                        path.unlink()
                        deleted += 1
                        continue

                    # Delete if too old
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        deleted += 1

        except Exception as e:
            logger.error(f"Failed to cleanup runs: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old runs")

        return deleted


# Global instance
_run_store: RunStore | None = None


def get_run_store() -> RunStore:
    """Get the global run store instance."""
    global _run_store
    if _run_store is None:
        _run_store = RunStore()
    return _run_store
