"""Validation event schemas."""

from typing import TypedDict


class ValidateStartData(TypedDict, total=False):
    """Data for validate_start event."""
    artifact_id: str | None
    validation_levels: list[str]


class ValidateLevelData(TypedDict, total=False):
    """Data for validate_level event."""
    level: str  # Required: "syntax" | "import" | "runtime"
    artifact_id: str | None
    passed: bool


class ValidateErrorData(TypedDict, total=False):
    """Data for validate_error event."""
    error_type: str  # Required
    message: str  # Required
    file: str | None
    line: int | None


class ValidatePassData(TypedDict, total=False):
    """Data for validate_pass event."""
    level: str  # Required
    artifact_id: str | None
