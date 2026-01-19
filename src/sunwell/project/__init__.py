"""Project schema module for domain-agnostic project support (RFC-035).

This module provides the infrastructure for defining domain-specific project
schemas that allow Sunwell to work with any domain (fiction, architecture,
research, etc.) using the same underlying dependency resolution and parallel
execution infrastructure from RFC-034.

Key components:
- ProjectSchema: Domain-agnostic project definition
- ArtifactType: User-defined artifact types
- ConstraintValidator: DSL-based validation
- Schema → Task resolver: RFC-034 integration
"""

from sunwell.project.compatibility import is_lens_compatible
from sunwell.project.dsl import ConstraintDSL, ParsedRule
from sunwell.project.resolver import SchemaResolver
from sunwell.project.schema import (
    ArtifactField,
    ArtifactType,
    ConditionalRequirement,
    PlanningConfig,
    PlanningPhase,
    ProjectSchema,
    ValidatorConfig,
)
from sunwell.project.validators import ConstraintValidator, ConstraintViolation

__all__ = [
    # Schema
    "ProjectSchema",
    "ArtifactType",
    "ArtifactField",
    "PlanningConfig",
    "PlanningPhase",
    "ValidatorConfig",
    "ConditionalRequirement",
    # DSL
    "ConstraintDSL",
    "ParsedRule",
    # Validators
    "ConstraintValidator",
    "ConstraintViolation",
    # Resolver
    "SchemaResolver",
    # Compatibility
    "is_lens_compatible",
]
