"""Core domain models for Sunwell."""

from sunwell.core.context import AppContext
from sunwell.core.framework import Framework, FrameworkCategory
from sunwell.core.freethreading import (
    WorkloadType,
    is_free_threaded,
    optimal_workers,
    run_cpu_bound,
    run_parallel,
    run_parallel_async,
    runtime_info,
)
from sunwell.core.heuristic import AntiHeuristic, CommunicationStyle, Heuristic
from sunwell.core.identity import (
    ResourceIdentity,
    SunwellURI,
    URIParseError,
    slugify,
    validate_slug,
)
from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.persona import Persona
from sunwell.core.spell import (
    Grimoire,
    Reagent,
    ReagentMode,
    ReagentType,
    Spell,
    SpellExample,
    SpellResult,
    SpellValidation,
    ValidationMode,
    parse_spell,
    validate_spell_output,
)
from sunwell.core.types import (
    Confidence,
    IntentCategory,
    LensReference,
    SemanticVersion,
    Severity,
    Tier,
    ValidationMethod,
)
from sunwell.core.validator import (
    DeterministicValidator,
    HeuristicValidator,
    ValidationResult,
)
from sunwell.core.workflow import Refiner, Workflow, WorkflowStep

__all__ = [
    "Lens",
    "LensMetadata",
    "Heuristic",
    "AntiHeuristic",
    "CommunicationStyle",
    "Persona",
    "DeterministicValidator",
    "HeuristicValidator",
    "ValidationResult",
    "Framework",
    "FrameworkCategory",
    "Workflow",
    "WorkflowStep",
    "Refiner",
    "Severity",
    "Tier",
    "ValidationMethod",
    "IntentCategory",
    "SemanticVersion",
    "LensReference",
    "Confidence",
    # Free-threading utilities
    "is_free_threaded",
    "optimal_workers",
    "WorkloadType",
    "run_parallel",
    "run_parallel_async",
    "run_cpu_bound",
    "runtime_info",
    # Spells (RFC-021)
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
    # Context (RFC-025)
    "AppContext",
    # Identity (RFC-101)
    "SunwellURI",
    "ResourceIdentity",
    "URIParseError",
    "slugify",
    "validate_slug",
]
