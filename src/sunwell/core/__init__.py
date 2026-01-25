"""Core domain models for Sunwell - Lens data model and supporting types.

This package contains the lens data model and related types:
- Heuristic, Persona, Framework: Lens components
- Spell, Grimoire: Workflow incantations (RFC-021)
- Validators: Quality gates
- AppContext: Application runtime context

For Lens itself, import from sunwell.foundation:
    from sunwell.foundation import Lens, LensMetadata

For infrastructure (config, errors, threading), use sunwell.foundation.
"""

# Context
from sunwell.core.context.context import AppContext

# Domain models
from sunwell.core.models import (
    AntiHeuristic,
    CommunicationStyle,
    DeterministicValidator,
    Example,
    Framework,
    FrameworkCategory,
    Grimoire,
    Heuristic,
    HeuristicValidator,
    Identity,
    Persona,
    PersonaResult,
    Reagent,
    ReagentMode,
    ReagentType,
    Refiner,
    SchemaValidationMethod,
    SchemaValidator,
    Spell,
    SpellExample,
    SpellResult,
    SpellValidation,
    ValidationMode,
    ValidationResult,
    Workflow,
    WorkflowStep,
    parse_spell,
    validate_spell_output,
)

# Core types
from sunwell.core.types import (
    Confidence,
    IntentCategory,
    LensReference,
    SemanticVersion,
    Severity,
    Tier,
    ValidationMethod,
)

# Identity utilities (re-exported for convenience)
from sunwell.foundation.identity import (
    ResourceIdentity,
    SunwellURI,
    URIParseError,
    validate_slug,
)
from sunwell.foundation.utils import slugify

__all__ = [
    # === Heuristics ===
    "Heuristic",
    "AntiHeuristic",
    "CommunicationStyle",
    "Identity",
    "Example",
    # === Personas ===
    "Persona",
    "PersonaResult",
    # === Framework ===
    "Framework",
    "FrameworkCategory",
    # === Validators ===
    "DeterministicValidator",
    "HeuristicValidator",
    "SchemaValidator",
    "SchemaValidationMethod",
    "ValidationResult",
    # === Workflows ===
    "Workflow",
    "WorkflowStep",
    "Refiner",
    # === Spells (RFC-021) ===
    "Spell",
    "SpellValidation",
    "SpellExample",
    "Reagent",
    "ReagentType",
    "ReagentMode",
    "ValidationMode",
    "Grimoire",
    "SpellResult",
    "parse_spell",
    "validate_spell_output",
    # === Types ===
    "Severity",
    "Tier",
    "ValidationMethod",
    "IntentCategory",
    "SemanticVersion",
    "LensReference",
    "Confidence",
    # === Context ===
    "AppContext",
    # === Identity (RFC-101) ===
    "ResourceIdentity",
    "SunwellURI",
    "URIParseError",
    "slugify",
    "validate_slug",
]
