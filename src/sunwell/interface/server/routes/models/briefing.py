"""Briefing response models (RFC-071)."""

from typing import Literal

from sunwell.interface.server.routes.models.base import CamelModel

BriefingStatus = Literal["not_started", "in_progress", "blocked", "complete"]


class BriefingResponse(CamelModel):
    """Briefing state for a project."""

    mission: str
    status: BriefingStatus
    progress: str
    last_action: str
    next_action: str | None = None
    hazards: list[str]
    blockers: list[str]
    hot_files: list[str]
    goal_hash: str | None = None
    related_learnings: list[str]

    # Dispatch hints (optional)
    predicted_skills: list[str] | None = None
    suggested_lens: str | None = None
    complexity_estimate: str | None = None
    estimated_files_touched: int | None = None

    # Metadata
    updated_at: str
    session_id: str


class BriefingExistsResponse(CamelModel):
    """Whether briefing exists."""

    exists: bool


class BriefingClearResponse(CamelModel):
    """Result of clearing briefing."""

    success: bool
    message: str | None = None
