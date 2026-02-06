"""Validator data models.

Canonical definitions moved to sunwell.foundation.schema.models.validator;
re-exported here for backward compatibility.

RFC-035 adds SchemaValidator for lens-provided schema artifact validation.
"""

from sunwell.foundation.schema.models.validator import (
    DeterministicValidator,
    HeuristicValidator,
    SchemaValidationMethod,
    SchemaValidator,
    ValidationResult,
)

__all__ = [
    "DeterministicValidator",
    "HeuristicValidator",
    "SchemaValidationMethod",
    "SchemaValidator",
    "ValidationResult",
]
