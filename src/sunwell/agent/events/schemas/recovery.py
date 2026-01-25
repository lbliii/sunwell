"""Recovery event schemas (RFC-125)."""

from typing import TypedDict


class RecoverySavedData(TypedDict, total=False):
    """Data for recovery_saved event."""
    recovery_id: str  # Required
    artifact_ids: list[str]  # Required - artifacts in recovery
    reason: str  # Why recovery was triggered


class RecoveryLoadedData(TypedDict, total=False):
    """Data for recovery_loaded event."""
    recovery_id: str  # Required
    artifact_ids: list[str]  # Required


class RecoveryResolvedData(TypedDict, total=False):
    """Data for recovery_resolved event."""
    recovery_id: str  # Required
    artifacts_passed: int  # Required


class RecoveryAbortedData(TypedDict, total=False):
    """Data for recovery_aborted event."""
    recovery_id: str  # Required
    reason: str  # Required
