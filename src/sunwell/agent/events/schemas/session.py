"""Session and goal lifecycle event schemas (RFC-131)."""

from typing import TypedDict


# =============================================================================
# Session Lifecycle Events
# =============================================================================


class SessionStartData(TypedDict, total=False):
    """Data for session_start event."""

    session_id: str | None


class SessionReadyData(TypedDict, total=False):
    """Data for session_ready event."""

    session_id: str | None


class SessionEndData(TypedDict, total=False):
    """Data for session_end event."""

    session_id: str | None
    duration_s: float | None


class SessionCrashData(TypedDict, total=False):
    """Data for session_crash event."""

    session_id: str | None
    error: str | None


# =============================================================================
# Goal Lifecycle Events
# =============================================================================


class GoalReceivedData(TypedDict, total=False):
    """Data for goal_received event."""

    goal: str


class GoalAnalyzingData(TypedDict, total=False):
    """Data for goal_analyzing event."""

    goal: str | None


class GoalReadyData(TypedDict, total=False):
    """Data for goal_ready event."""

    goal: str | None
    tasks: int | None


class GoalCompleteData(TypedDict, total=False):
    """Data for goal_complete event."""

    goal: str | None
    tasks_completed: int | None
    duration_s: float | None


class GoalFailedData(TypedDict, total=False):
    """Data for goal_failed event."""

    goal: str | None
    error: str | None


class GoalPausedData(TypedDict, total=False):
    """Data for goal_paused event."""

    goal: str | None
    checkpoint: str | None
