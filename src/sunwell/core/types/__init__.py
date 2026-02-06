"""Shared type definitions across Sunwell.

Lens schema types moved to sunwell.foundation.schema.models.types;
re-exported here via core.types.types for backward compatibility.
"""

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
