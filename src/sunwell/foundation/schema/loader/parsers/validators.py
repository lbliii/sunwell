"""Validators parsing."""

from sunwell.core.models.validator import (
    DeterministicValidator,
    HeuristicValidator,
    SchemaValidationMethod,
    SchemaValidator,
)
from sunwell.core.types.types import Severity, ValidationMethod


def parse_deterministic_validators(
    data: list[dict],
) -> tuple[DeterministicValidator, ...]:
    """Parse deterministic validators."""
    return tuple(
        DeterministicValidator(
            name=v["name"],
            script=v["script"],
            severity=Severity(v.get("severity", "error")),
            description=v.get("description"),
            timeout_seconds=v.get("timeout_seconds", 30.0),
        )
        for v in data
    )


def parse_heuristic_validators(
    data: list[dict],
) -> tuple[HeuristicValidator, ...]:
    """Parse heuristic validators."""
    return tuple(
        HeuristicValidator(
            name=v["name"],
            check=v["check"],
            method=ValidationMethod(v.get("method", "pattern_match")),
            confidence_threshold=v.get("confidence_threshold", 0.8),
            severity=Severity(v.get("severity", "warning")),
            description=v.get("description"),
        )
        for v in data
    )


def parse_schema_validators(
    data: list[dict],
) -> tuple[SchemaValidator, ...]:
    """Parse schema validators (RFC-035).

    Schema validators validate outputs against JSON schemas.
    """
    return tuple(
        SchemaValidator(
            name=v["name"],
            schema=v["schema"],
            method=SchemaValidationMethod(v.get("method", "json_schema")),
            severity=Severity(v.get("severity", "error")),
            description=v.get("description"),
            path=v.get("path"),  # JSONPath for partial validation
        )
        for v in data
    )
