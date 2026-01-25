"""Checkpointing for RFC-032 Agent Mode.

Enables long-running agent tasks to checkpoint progress for recovery.
"""


import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sunwell.naaru.types import Task


class FailurePolicy(Enum):
    """How to handle task failures (RFC-032)."""

    CONTINUE = "continue"     # Default: skip failed, continue others
    RETRY = "retry"           # Retry with exponential backoff
    ABORT = "abort"           # Stop entire run
    REPLAN = "replan"         # Re-plan remaining tasks


class CheckpointPhase(Enum):
    """Semantic phases for workflow checkpoints (RFC-130).

    Phases represent meaningful workflow stages that enable intelligent resume.
    Instead of just tracking task IDs, we track semantic progress.

    Example:
        >>> cp = AgentCheckpoint.find_latest_for_goal(workspace, "Add OAuth")
        >>> if cp and cp.phase == CheckpointPhase.DESIGN_APPROVED:
        ...     # Skip planning, user already approved approach
        ...     resume_from_implementation(cp)
    """

    ORIENT_COMPLETE = "orient_complete"
    """Memory loaded, constraints identified. Ready for exploration."""

    EXPLORATION_COMPLETE = "exploration_complete"
    """Codebase analyzed, signals extracted. Ready for planning."""

    PLAN_COMPLETE = "plan_complete"
    """Plan generated. Awaiting user approval or auto-proceeding."""

    DESIGN_APPROVED = "design_approved"
    """User approved approach. Ready for implementation."""

    IMPLEMENTATION_COMPLETE = "implementation_complete"
    """Code written. Ready for validation."""

    REVIEW_COMPLETE = "review_complete"
    """Quality checked. Ready for completion."""

    USER_CHECKPOINT = "user_checkpoint"
    """Manual checkpoint by user request."""

    TASK_COMPLETE = "task_complete"
    """Individual task completed (backward compatible)."""


@dataclass(frozen=True, slots=True)
class TaskExecutionConfig:
    """Configuration for task execution (RFC-032)."""

    failure_policy: FailurePolicy = FailurePolicy.CONTINUE
    max_retries_per_task: int = 2
    retry_backoff_seconds: float = 1.0
    abort_on_critical: bool = True  # Abort if CRITICAL risk task fails
    checkpoint_interval_seconds: float = 60.0  # Save checkpoint every 60s

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "failure_policy": self.failure_policy.value,
            "max_retries_per_task": self.max_retries_per_task,
            "retry_backoff_seconds": self.retry_backoff_seconds,
            "abort_on_critical": self.abort_on_critical,
            "checkpoint_interval_seconds": self.checkpoint_interval_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskExecutionConfig:
        """Create from dict."""
        return cls(
            failure_policy=FailurePolicy(data.get("failure_policy", "continue")),
            max_retries_per_task=data.get("max_retries_per_task", 2),
            retry_backoff_seconds=data.get("retry_backoff_seconds", 1.0),
            abort_on_critical=data.get("abort_on_critical", True),
            checkpoint_interval_seconds=data.get("checkpoint_interval_seconds", 60.0),
        )


@dataclass(frozen=True, slots=True)
class ParallelConfig:
    """Configuration for parallel task execution (RFC-032)."""

    enabled: bool = True
    max_parallel_tasks: int = 8      # Matches NaaruConfig default
    max_parallel_writes: int = 2     # Limit concurrent file writes
    parallel_research: bool = True   # Research tasks are always safe

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "enabled": self.enabled,
            "max_parallel_tasks": self.max_parallel_tasks,
            "max_parallel_writes": self.max_parallel_writes,
            "parallel_research": self.parallel_research,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParallelConfig:
        """Create from dict."""
        return cls(
            enabled=data.get("enabled", True),
            max_parallel_tasks=data.get("max_parallel_tasks", 8),
            max_parallel_writes=data.get("max_parallel_writes", 2),
            parallel_research=data.get("parallel_research", True),
        )


@dataclass(slots=True)
class AgentCheckpoint:
    """Saved state for resuming agent execution (RFC-032, RFC-130).

    Long-running tasks (>60 seconds) checkpoint progress to enable recovery.
    Checkpoints are saved:
    - Every 60 seconds during execution
    - After each task completes
    - On timeout or graceful shutdown
    - On unrecoverable error
    - RFC-130: At semantic phase boundaries

    Example:
        >>> checkpoint = AgentCheckpoint(
        ...     goal="Build a React app",
        ...     tasks=tasks,
        ... )
        >>> checkpoint.save(Path(".sunwell/checkpoints/agent-123.json"))
        >>>
        >>> # Later, resume:
        >>> cp = AgentCheckpoint.load(checkpoint_path)
        >>> remaining = cp.get_remaining_tasks()
        >>>
        >>> # RFC-130: Resume by goal
        >>> cp = AgentCheckpoint.find_latest_for_goal(workspace, "Build a React app")
        >>> if cp:
        ...     print(f"Resume from {cp.phase.value}: {cp.phase_summary}")
    """

    goal: str
    started_at: datetime = field(default_factory=datetime.now)
    checkpoint_at: datetime = field(default_factory=datetime.now)
    tasks: list[Task] = field(default_factory=list)
    completed_ids: set[str] = field(default_factory=set)
    artifacts: list[Path] = field(default_factory=list)

    # Execution context
    working_directory: str = "."
    context: dict[str, Any] = field(default_factory=dict)

    # Configuration
    execution_config: TaskExecutionConfig = field(default_factory=TaskExecutionConfig)
    parallel_config: ParallelConfig = field(default_factory=ParallelConfig)

    # RFC-130: Semantic phase tracking
    phase: CheckpointPhase = CheckpointPhase.TASK_COMPLETE
    """Current semantic phase (enables phase-based resume)."""

    phase_summary: str = ""
    """Human-readable summary of what was accomplished at this phase."""

    user_decisions: tuple[str, ...] = ()
    """User decisions recorded during execution (e.g., 'Approved approach: minimal')."""

    spawned_specialists: tuple[str, ...] = ()
    """IDs of specialists spawned (for constellation tracking)."""

    memory_snapshot_path: str | None = None
    """Path to memory snapshot (for memory-informed resume)."""

    def save(self, path: Path) -> None:
        """Save checkpoint to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> AgentCheckpoint:
        """Load checkpoint from disk."""
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "goal": self.goal,
            "started_at": self.started_at.isoformat(),
            "checkpoint_at": self.checkpoint_at.isoformat(),
            "tasks": [t.to_dict() for t in self.tasks],
            "completed_ids": list(self.completed_ids),
            "artifacts": [str(p) for p in self.artifacts],
            "working_directory": self.working_directory,
            "context": self.context,
            "execution_config": self.execution_config.to_dict(),
            "parallel_config": self.parallel_config.to_dict(),
            # RFC-130: Semantic phase fields
            "phase": self.phase.value,
            "phase_summary": self.phase_summary,
            "user_decisions": list(self.user_decisions),
            "spawned_specialists": list(self.spawned_specialists),
            "memory_snapshot_path": self.memory_snapshot_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCheckpoint:
        """Create from dict."""
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]

        # RFC-130: Parse phase with backwards compatibility
        phase_value = data.get("phase", "task_complete")
        try:
            phase = CheckpointPhase(phase_value)
        except ValueError:
            phase = CheckpointPhase.TASK_COMPLETE

        return cls(
            goal=data["goal"],
            started_at=datetime.fromisoformat(data["started_at"]),
            checkpoint_at=datetime.fromisoformat(data["checkpoint_at"]),
            tasks=tasks,
            completed_ids=set(data.get("completed_ids", [])),
            artifacts=[Path(p) for p in data.get("artifacts", [])],
            working_directory=data.get("working_directory", "."),
            context=data.get("context", {}),
            execution_config=TaskExecutionConfig.from_dict(
                data.get("execution_config", {})
            ),
            parallel_config=ParallelConfig.from_dict(
                data.get("parallel_config", {})
            ),
            # RFC-130: Semantic phase fields
            phase=phase,
            phase_summary=data.get("phase_summary", ""),
            user_decisions=tuple(data.get("user_decisions", [])),
            spawned_specialists=tuple(data.get("spawned_specialists", [])),
            memory_snapshot_path=data.get("memory_snapshot_path"),
        )

    def get_remaining_tasks(self) -> list[Task]:
        """Get tasks that haven't been completed."""
        from sunwell.naaru.types import TaskStatus

        return [
            t for t in self.tasks
            if t.id not in self.completed_ids
            and t.status not in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        ]

    def get_progress_summary(self) -> dict[str, Any]:
        """Get a summary of execution progress."""
        from sunwell.naaru.types import TaskStatus

        completed = len(self.completed_ids)
        total = len(self.tasks)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)

        return {
            "goal": self.goal,
            "total_tasks": total,
            "completed": completed,
            "remaining": total - completed,
            "failed": failed,
            "artifacts": len(self.artifacts),
            "started_at": self.started_at.isoformat(),
            "checkpoint_at": self.checkpoint_at.isoformat(),
            "duration_seconds": (self.checkpoint_at - self.started_at).total_seconds(),
            # RFC-130: Include phase info
            "phase": self.phase.value,
            "phase_summary": self.phase_summary,
        }

    def get_resume_phase(self) -> CheckpointPhase:
        """Get the phase to resume from.

        RFC-130: Returns the current phase for intelligent resume.
        """
        return self.phase

    @classmethod
    def find_latest_for_goal(
        cls,
        workspace: Path,
        goal: str,
    ) -> "AgentCheckpoint | None":
        """Find the most recent checkpoint for a specific goal.

        RFC-130: Enables goal-based resume for autonomous recovery.

        Args:
            workspace: Project workspace directory
            goal: The goal to find checkpoints for

        Returns:
            The most recent checkpoint for this goal, or None if not found
        """
        checkpoint_dir = workspace / ".sunwell" / "checkpoints"
        if not checkpoint_dir.exists():
            return None

        matching: list[AgentCheckpoint] = []
        for path in checkpoint_dir.glob("*.json"):
            try:
                cp = cls.load(path)
                # Match by exact goal or goal prefix (for slightly rephrased goals)
                if cp.goal == goal or cp.goal.startswith(goal[:50]):
                    matching.append(cp)
            except Exception:
                continue  # Skip corrupted checkpoints

        if not matching:
            return None

        # Return most recent by checkpoint_at
        return max(matching, key=lambda c: c.checkpoint_at)

    @classmethod
    def find_all_for_goal(
        cls,
        workspace: Path,
        goal: str,
    ) -> list["AgentCheckpoint"]:
        """Find all checkpoints for a specific goal, sorted by time.

        Args:
            workspace: Project workspace directory
            goal: The goal to find checkpoints for

        Returns:
            List of checkpoints, most recent first
        """
        checkpoint_dir = workspace / ".sunwell" / "checkpoints"
        if not checkpoint_dir.exists():
            return []

        matching: list[AgentCheckpoint] = []
        for path in checkpoint_dir.glob("*.json"):
            try:
                cp = cls.load(path)
                if cp.goal == goal or cp.goal.startswith(goal[:50]):
                    matching.append(cp)
            except Exception:
                continue

        return sorted(matching, key=lambda c: c.checkpoint_at, reverse=True)


def find_latest_checkpoint(
    checkpoint_dir: Path | None = None,
) -> AgentCheckpoint | None:
    """Find the most recent checkpoint file.

    Args:
        checkpoint_dir: Directory to search (default: .sunwell/checkpoints/)

    Returns:
        The most recent AgentCheckpoint, or None if none found
    """
    if checkpoint_dir is None:
        checkpoint_dir = Path.cwd() / ".sunwell" / "checkpoints"

    if not checkpoint_dir.exists():
        return None

    # Find all checkpoint files
    checkpoint_files = list(checkpoint_dir.glob("agent-*.json"))

    if not checkpoint_files:
        return None

    # Sort by modification time (most recent first)
    checkpoint_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Load the most recent
    try:
        return AgentCheckpoint.load(checkpoint_files[0])
    except (json.JSONDecodeError, KeyError):
        return None


def get_checkpoint_path(base_dir: Path | None = None) -> Path:
    """Get a new checkpoint file path with timestamp.

    Args:
        base_dir: Base directory (default: .sunwell/checkpoints/)

    Returns:
        Path for new checkpoint file
    """
    if base_dir is None:
        base_dir = Path.cwd() / ".sunwell" / "checkpoints"

    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return base_dir / f"agent-{timestamp}.json"


# Error messages for user-facing output
ERROR_MESSAGES = {
    "planning_failed": "Could not create a plan for this goal. Try being more specific.",
    "trust_violation": "Task requires {tool} but trust level is {level}. Use --trust shell to allow.",
    "timeout": "Ran out of time. {completed}/{total} tasks completed. Run again to continue.",
    "deadlock": "Some tasks are blocked. Failed tasks: {failed}. Run with --verbose for details.",
}
