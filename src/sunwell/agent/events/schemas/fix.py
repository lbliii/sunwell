"""Fix event schemas."""

from typing import TypedDict


class FixStartData(TypedDict, total=False):
    """Data for fix_start event."""
    error_count: int
    artifact_id: str | None


class FixProgressData(TypedDict, total=False):
    """Data for fix_progress event."""
    stage: str  # Required
    progress: float  # Required: 0.0-1.0
    detail: str


class FixAttemptData(TypedDict, total=False):
    """Data for fix_attempt event."""
    attempt: int  # Required
    fix_type: str
    error_id: str | None


class FixCompleteData(TypedDict, total=False):
    """Data for fix_complete event."""
    fixes_applied: int
    errors_remaining: int


class FixFailedData(TypedDict, total=False):
    """Data for fix_failed event."""
    attempt: int  # Required
    reason: str
    error_id: str | None
