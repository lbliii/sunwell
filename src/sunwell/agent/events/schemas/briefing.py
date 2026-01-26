"""Briefing event schemas."""

from typing import TypedDict


class BriefingLoadedData(TypedDict, total=False):
    """Data for briefing_loaded event.

    Note: Factory provides mission/status/has_hazards/has_dispatch_hints.
    """

    mission: str
    status: str
    has_hazards: bool
    has_dispatch_hints: bool
    # Legacy field for backward compatibility
    path: str | None


class BriefingSavedData(TypedDict, total=False):
    """Data for briefing_saved event.

    Note: Factory provides status/next_action/tasks_completed.
    """

    status: str
    next_action: str | None
    tasks_completed: int
    # Legacy field for backward compatibility
    path: str | None
