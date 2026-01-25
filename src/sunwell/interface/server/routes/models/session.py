"""Session and plan versioning response models (RFC-120)."""

from sunwell.interface.server.routes.models.base import CamelModel


class SessionSummaryResponse(CamelModel):
    """Session activity summary."""

    session_id: str
    started_at: str
    goals_completed: int
    goals_started: int
    files_modified: int
    files_created: int
    total_duration_seconds: float
    error: str | None = None


class SessionHistoryItem(CamelModel):
    """A session in the history list."""

    session_id: str
    started_at: str
    goals_completed: int
    goals_started: int
    files_modified: int
    total_duration_seconds: float


class SessionHistoryResponse(CamelModel):
    """List of recent sessions."""

    sessions: list[SessionHistoryItem]
    count: int


class PlanVersionsResponse(CamelModel):
    """Plan version history."""

    plan_id: str
    versions: list[dict[str, str | int | float]]
    count: int


class RecentPlanItem(CamelModel):
    """A plan in the recent plans list."""

    plan_id: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    version_count: int
    progress_percent: float


class RecentPlansResponse(CamelModel):
    """List of recent plans."""

    plans: list[RecentPlanItem]
    count: int
