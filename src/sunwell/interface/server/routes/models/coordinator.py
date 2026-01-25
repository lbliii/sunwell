"""Coordinator response models (RFC-100)."""

from sunwell.interface.server.routes.models.base import CamelModel


class CoordinatorWorker(CamelModel):
    """A worker in the coordinator."""

    id: int
    goal: str
    status: str
    progress: float
    current_file: str | None
    branch: str | None
    goals_completed: int
    goals_failed: int
    last_heartbeat: str


class CoordinatorConflict(CamelModel):
    """A conflict detected by the coordinator."""

    path: str
    worker_a: int
    worker_b: int
    conflict_type: str
    resolution: str | None
    detected_at: str | None


class CoordinatorStateResponse(CamelModel):
    """Coordinator state for UI."""

    workers: list[CoordinatorWorker]
    conflicts: list[CoordinatorConflict]
    total_progress: float
    merged_branches: list[str]
    pending_merges: list[str]
    is_running: bool
    started_at: str | None
    last_update: str
    error: str | None = None


class WorkerStartResponse(CamelModel):
    """Result of starting workers."""

    status: str
    num_workers: int | None = None
    error: str | None = None


class WorkerActionResponse(CamelModel):
    """Result of a worker action (pause/resume)."""

    status: str
    worker_id: int
    error: str | None = None


class StateDagResponse(CamelModel):
    """State DAG for brownfield scanning."""

    root: str | None
    scanned_at: str | None
    lens_name: str | None
    overall_health: float
    node_count: int
    edge_count: int
    unhealthy_count: int
    critical_count: int
    nodes: list[dict[str, str | int | float | bool | None]]
    edges: list[dict[str, str]]
    metadata: dict[str, str | int | float]
    error: str | None = None
