"""Schema model types for lens definitions.

These types were originally in core.models.* and core.types.* but belong
in foundation since they are pure data types (stdlib-only dependencies)
used by the lens schema loader and Lens model.

Moved here as part of the layer-exemption burn-down epic to eliminate
foundation -> core (L1 -> L3) layer violations.
"""

from sunwell.foundation.schema.models.framework import Framework, FrameworkCategory
from sunwell.foundation.schema.models.heuristic import (
    AntiHeuristic,
    CommunicationStyle,
    Example,
    Heuristic,
    Identity,
)
from sunwell.foundation.schema.models.persona import Persona, PersonaResult
from sunwell.foundation.schema.models.types import (
    LensReference,
    SemanticVersion,
    Severity,
    Tier,
    ValidationMethod,
)
from sunwell.foundation.schema.models.validator import (
    DeterministicValidator,
    HeuristicValidator,
    SchemaValidationMethod,
    SchemaValidator,
    ValidationResult,
)
from sunwell.foundation.schema.models.skill import (
    Resource,
    Script,
    Skill,
    SkillRetryPolicy,
    SkillType,
    SkillValidation,
    Template,
    TrustLevel,
)
from sunwell.foundation.schema.models.workflow import Refiner, Workflow, WorkflowStep

__all__ = [
    # Framework
    "Framework",
    "FrameworkCategory",
    # Heuristic
    "Heuristic",
    "AntiHeuristic",
    "CommunicationStyle",
    "Identity",
    "Example",
    # Persona
    "Persona",
    "PersonaResult",
    # Validator
    "DeterministicValidator",
    "HeuristicValidator",
    "ValidationResult",
    "SchemaValidator",
    "SchemaValidationMethod",
    # Workflow
    "Workflow",
    "WorkflowStep",
    "Refiner",
    # Types
    "Severity",
    "Tier",
    "ValidationMethod",
    "SemanticVersion",
    "LensReference",
    # Skill
    "Skill",
    "SkillType",
    "SkillRetryPolicy",
    "SkillValidation",
    "TrustLevel",
    "Script",
    "Template",
    "Resource",
]
