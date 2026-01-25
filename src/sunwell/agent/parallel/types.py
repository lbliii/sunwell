"""Type definitions for multi-instance coordination (RFC-051)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class WorkerState(Enum):
    """Worker lifecycle states."""

    STARTING = "starting"
    IDLE = "idle"
    CLAIMING = "claiming"
    EXECUTING = "executing"
    COMMITTING = "committing"
    MERGING = "merging"
    STOPPED = "stopped"
    FAILED = "failed"


# Module-level constant for worker progress calculation
_STATE_PROGRESS: dict[WorkerState, float] = {
    WorkerState.CLAIMING: 0.1,
    WorkerState.EXECUTING: 0.5,
    WorkerState.COMMITTING: 0.8,
    WorkerState.MERGING: 0.9,
}


@dataclass(slots=True)
class WorkerStatus:
    """Current status of a worker process."""

    worker_id: int
    """Unique identifier for this worker."""

    pid: int
    """Process ID of the worker."""

    state: WorkerState
    """Current lifecycle state."""

    branch: str
    """Git branch this worker commits to."""

    current_goal_id: str | None = None
    """ID of the goal currently being executed."""

    goals_completed: int = 0
    """Number of goals successfully completed."""

    goals_failed: int = 0
    """Number of goals that failed."""

    started_at: datetime = field(default_factory=datetime.now)
    """When the worker started."""

    last_heartbeat: datetime = field(default_factory=datetime.now)
    """Last time the worker reported status."""

    error_message: str | None = None
    """Error message if worker is in FAILED state."""


@dataclass(frozen=True, slots=True)
class WorkerResult:
    """Result of a worker process execution."""

    worker_id: int
    """Which worker produced this result."""

    goals_completed: int
    """Number of goals successfully completed."""

    goals_failed: int
    """Number of goals that failed."""

    branch: str
    """Git branch with the worker's commits."""

    duration_seconds: float = 0.0
    """Total execution time."""

    commit_shas: tuple[str, ...] = ()
    """Tuple of commit SHAs created by this worker."""


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Result of merging worker branches."""

    merged: tuple[str, ...] = ()
    """Branches that were successfully merged."""

    conflicts: tuple[str, ...] = ()
    """Branches with merge conflicts (need human review)."""


# RFC-100: UI-focused types for ATC view
@dataclass(frozen=True, slots=True)
class FileConflict:
    """A file conflict between workers for UI display."""

    path: str
    """Path to the conflicting file."""

    worker_a: int
    """ID of first worker involved in conflict."""

    worker_b: int
    """ID of second worker involved in conflict."""

    conflict_type: str = "concurrent_modification"
    """Type of conflict: 'concurrent_modification', 'lock_contention'."""

    resolution: str | None = None
    """Resolution if available: 'auto_merged', 'manual_required', 'paused'."""

    detected_at: datetime = field(default_factory=datetime.now)
    """When the conflict was detected."""


@dataclass(frozen=True, slots=True)
class CoordinatorUIState:
    """State snapshot for UI consumption (RFC-100 Phase 4).

    This is the data structure passed to the Studio frontend
    for the ATC (Air Traffic Control) view.
    """

    workers: tuple[WorkerStatus, ...] = ()
    """Current status of all workers."""

    conflicts: tuple[FileConflict, ...] = ()
    """Active file conflicts requiring attention."""

    total_progress: float = 0.0
    """Overall progress (0.0-1.0) across all workers."""

    merged_branches: tuple[str, ...] = ()
    """Branches that have been successfully merged."""

    pending_merges: tuple[str, ...] = ()
    """Branches waiting to be merged."""

    is_running: bool = False
    """Whether the coordinator is currently running."""

    started_at: datetime | None = None
    """When the coordinator started."""

    last_update: datetime = field(default_factory=datetime.now)
    """When this state was last updated."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON/Tauri."""
        return {
            "workers": [
                {
                    "id": w.worker_id,
                    "goal": w.current_goal_id or "",
                    "status": w.state.value,
                    "progress": self._calculate_worker_progress(w),
                    "current_file": None,  # Could be added to WorkerStatus
                    "branch": w.branch,
                    "goals_completed": w.goals_completed,
                    "goals_failed": w.goals_failed,
                    "last_heartbeat": w.last_heartbeat.isoformat(),
                }
                for w in self.workers
            ],
            "conflicts": [
                {
                    "path": c.path,
                    "worker_a": c.worker_a,
                    "worker_b": c.worker_b,
                    "conflict_type": c.conflict_type,
                    "resolution": c.resolution,
                    "detected_at": c.detected_at.isoformat(),
                }
                for c in self.conflicts
            ],
            "total_progress": self.total_progress,
            "merged_branches": self.merged_branches,
            "pending_merges": self.pending_merges,
            "is_running": self.is_running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_update": self.last_update.isoformat(),
        }

    def _calculate_worker_progress(self, worker: WorkerStatus) -> float:
        """Calculate progress percentage for a worker."""
        if worker.state == WorkerState.STOPPED:
            return 1.0
        if worker.state in (WorkerState.FAILED, WorkerState.STARTING, WorkerState.IDLE):
            return 0.0
        return _STATE_PROGRESS.get(worker.state, 0.5)
