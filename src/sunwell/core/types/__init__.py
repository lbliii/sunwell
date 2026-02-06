"""Shared type definitions across Sunwell."""

from sunwell.core.types.embeddable import Embeddable, to_embedding_text
from sunwell.core.types.types import (
    Confidence,
    IntentCategory,
    LensReference,
    LensResolutionError,
    ModelError,
    SemanticVersion,
    Severity,
    Tier,
    ValidationExecutionError,
    ValidationMethod,
)

__all__ = [
    # Protocols
    "Embeddable",
    "to_embedding_text",
    # Enums
    "Severity",
    "Tier",
    "ValidationMethod",
    "IntentCategory",
    # Data types
    "SemanticVersion",
    "LensReference",
    "Confidence",
    # Errors
    "ValidationExecutionError",
    "ModelError",
    "LensResolutionError",
]
