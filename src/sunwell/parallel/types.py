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


@dataclass
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


@dataclass
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

    commit_shas: list[str] = field(default_factory=list)
    """List of commit SHAs created by this worker."""


@dataclass
class MergeResult:
    """Result of merging worker branches."""

    merged: list[str] = field(default_factory=list)
    """Branches that were successfully merged."""

    conflicts: list[str] = field(default_factory=list)
    """Branches with merge conflicts (need human review)."""
