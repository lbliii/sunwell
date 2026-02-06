"""Shared type definitions across Sunwell.

Lens schema types (Severity, Tier, ValidationMethod, SemanticVersion,
LensReference) moved to sunwell.foundation.schema.models.types;
re-exported here for backward compatibility.
"""


from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from sunwell.foundation.errors import ErrorCode, SunwellError

# Re-export types that moved to foundation
from sunwell.foundation.schema.models.types import (
    LensReference,
    SemanticVersion,
    Severity,
    Tier,
    ValidationMethod,
)


class IntentCategory(Enum):
    """High-level intent categories for routing."""

    TRIVIAL = auto()  # Typos, formatting
    STANDARD = auto()  # General content creation
    COMPLEX = auto()  # Architecture, audits, high-stakes
    AMBIGUOUS = auto()  # Needs clarification


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence score with explanation."""

    score: float  # 0.0 - 1.0
    explanation: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Confidence score must be between 0 and 1, got {self.score}")

    @property
    def level(self) -> str:
        """Get confidence level indicator."""
        if self.score >= 0.9:
            return "🟢 High"
        elif self.score >= 0.7:
            return "🟡 Moderate"
        elif self.score >= 0.5:
            return "🟠 Low"
        else:
            return "🔴 Uncertain"




@dataclass(frozen=True, slots=True)
class ValidationExecutionError:
    """Error during validator execution."""

    validator_name: str
    error_type: Literal["script_failed", "timeout", "invalid_output", "sandbox_violation"]
    message: str
    exit_code: int | None = None
    stderr: str | None = None
    recoverable: bool = True


@dataclass(frozen=True, slots=True)
class ModelError:
    """Error from LLM provider."""

    provider: str
    error_type: Literal["rate_limit", "auth_failed", "context_exceeded", "timeout", "api_error"]
    message: str
    retry_after: float | None = None
    recoverable: bool = True


class LensResolutionError(SunwellError):
    """Error resolving lens inheritance/composition."""

    def __init__(
        self,
        lens_name: str,
        error_type: Literal["not_found", "circular_dependency", "version_conflict", "merge_conflict"],
        message: str,
        conflicting_lenses: tuple[str, ...] = (),
    ):
        self.lens_name = lens_name
        self.error_type = error_type
        self.conflicting_lenses = conflicting_lenses

        # Map error_type to ErrorCode
        error_code_map = {
            "not_found": ErrorCode.LENS_NOT_FOUND,
            "circular_dependency": ErrorCode.LENS_CIRCULAR_DEPENDENCY,
            "version_conflict": ErrorCode.LENS_VERSION_CONFLICT,
            "merge_conflict": ErrorCode.LENS_MERGE_CONFLICT,
        }

        super().__init__(
            code=error_code_map.get(error_type, ErrorCode.LENS_NOT_FOUND),
            context={
                "lens": lens_name,
                "detail": message,
                "conflicting_lenses": conflicting_lenses,
            },
        )

    @classmethod
    def create(
        cls,
        lens_name: str,
        error_type: Literal["not_found", "circular_dependency", "version_conflict", "merge_conflict"],
        message: str,
        conflicting_lenses: tuple[str, ...] = (),
    ) -> LensResolutionError:
        return cls(
            lens_name=lens_name,
            error_type=error_type,
            message=message,
            conflicting_lenses=conflicting_lenses,
        )
