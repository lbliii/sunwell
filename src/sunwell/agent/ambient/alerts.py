"""Ambient alert types and structures.

Defines the types of alerts that can be detected and surfaced
proactively by the ambient intelligence system.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class AmbientAlertType(Enum):
    """Types of ambient alerts that can be detected."""

    SECURITY_CONCERN = "security"
    """Potential security issue (hardcoded secrets, unsafe patterns)."""

    OPTIMIZATION = "optimization"
    """Performance improvement opportunity."""

    DRIFT_DETECTED = "drift"
    """Behavior change without corresponding test change."""

    DEPENDENCY_ISSUE = "dependency"
    """Outdated or vulnerable dependency."""

    STYLE_VIOLATION = "style"
    """Code style or linting violation introduced."""

    COMPLEXITY = "complexity"
    """Code complexity issue (too long, too nested)."""

    DOCUMENTATION = "documentation"
    """Missing or outdated documentation."""

    TYPE_ERROR = "type_error"
    """Potential type error or type safety issue."""


class AlertSeverity(Enum):
    """Severity levels for ambient alerts."""

    INFO = "info"
    """Informational - no action required."""

    WARNING = "warning"
    """Warning - should be addressed."""

    ERROR = "error"
    """Error - must be addressed."""


@dataclass(frozen=True, slots=True)
class AmbientAlert:
    """An ambient alert detected during execution.

    Attributes:
        alert_type: Type of alert
        severity: Severity level
        message: Human-readable description
        file_path: Path to affected file (if applicable)
        line_number: Line number where issue found (if applicable)
        suggested_fix: Suggested fix or action
        context: Additional context data
        detected_at: When alert was detected
    """

    alert_type: AmbientAlertType
    severity: AlertSeverity
    message: str
    file_path: str | None = None
    line_number: int | None = None
    suggested_fix: str | None = None
    context: dict | None = None
    detected_at: datetime | None = None

    def __post_init__(self) -> None:
        # Set detection time if not provided
        if self.detected_at is None:
            object.__setattr__(self, "detected_at", datetime.now(timezone.utc))

    @property
    def location(self) -> str | None:
        """Get location string if file path is set."""
        if self.file_path is None:
            return None
        if self.line_number is not None:
            return f"{self.file_path}:{self.line_number}"
        return self.file_path

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "suggested_fix": self.suggested_fix,
            "context": self.context,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AmbientAlert":
        """Deserialize from dictionary."""
        detected_at = None
        if data.get("detected_at"):
            detected_at = datetime.fromisoformat(data["detected_at"])

        return cls(
            alert_type=AmbientAlertType(data["alert_type"]),
            severity=AlertSeverity(data["severity"]),
            message=data["message"],
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            suggested_fix=data.get("suggested_fix"),
            context=data.get("context"),
            detected_at=detected_at,
        )
