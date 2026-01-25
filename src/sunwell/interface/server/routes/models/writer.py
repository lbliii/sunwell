"""Writer and Diataxis response models (RFC-086)."""

from typing import Literal

from sunwell.interface.server.routes.models.base import CamelModel

ValidationSeverity = Literal["warning", "error", "info"]


class ValidationWarning(CamelModel):
    """A validation warning for a document."""

    line: int
    column: int | None = None
    message: str
    rule: str
    severity: ValidationSeverity
    suggestion: str | None = None


class ValidationResponse(CamelModel):
    """Result of document validation."""

    warnings: list[ValidationWarning]


class FixAllResponse(CamelModel):
    """Result of fixing all issues."""

    content: str
    fixed: int


class DiataxisScores(CamelModel):
    """Diataxis content type scores."""

    tutorial: float = 0.0
    how_to: float = 0.0
    explanation: float = 0.0
    reference: float = 0.0


class DiataxisDetection(CamelModel):
    """Diataxis detection result."""

    detected_type: str | None
    confidence: float
    signals: list[str]
    scores: DiataxisScores


class DiataxisResponse(CamelModel):
    """Response for Diataxis content type detection."""

    detection: DiataxisDetection
    warnings: list[str]


class SkillExecuteResponse(CamelModel):
    """Response for skill execution."""

    message: str
