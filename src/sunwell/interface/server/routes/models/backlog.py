"""Backlog response models (RFC-114)."""

from sunwell.interface.server.routes.models.base import CamelModel


class BacklogGoalItem(CamelModel):
    """A goal in the backlog."""

    id: str
    title: str
    description: str | None
    priority: float
    category: str
    status: str
    estimated_complexity: str
    auto_approvable: bool
    requires: list[str]
    claimed_by: str | None
    created_at: str | None


class BacklogResponse(CamelModel):
    """Backlog goals list."""

    goals: list[BacklogGoalItem]
    total: int
    error: str | None = None


class GoalAddResponse(CamelModel):
    """Result of adding/updating/deleting a goal."""

    status: str
    goal_id: str | None = None
    error: str | None = None


class BacklogRefreshResponse(CamelModel):
    """Result of refreshing the backlog."""

    status: str
    goal_count: int
    error: str | None = None
