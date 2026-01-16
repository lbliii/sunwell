"""Core domain models for Sunwell."""

from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.heuristic import Heuristic, AntiHeuristic, CommunicationStyle
from sunwell.core.persona import Persona
from sunwell.core.validator import (
    DeterministicValidator,
    HeuristicValidator,
    ValidationResult,
)
from sunwell.core.framework import Framework, FrameworkCategory
from sunwell.core.workflow import Workflow, WorkflowStep, Refiner
from sunwell.core.types import (
    Severity,
    Tier,
    ValidationMethod,
    IntentCategory,
    SemanticVersion,
    LensReference,
    Confidence,
)
from sunwell.core.freethreading import (
    is_free_threaded,
    optimal_workers,
    WorkloadType,
    run_parallel,
    run_parallel_async,
    run_cpu_bound,
    runtime_info,
)
from sunwell.core.spell import (
    Spell,
    SpellValidation,
    SpellExample,
    Reagent,
    ReagentType,
    ReagentMode,
    ValidationMode,
    Grimoire,
    SpellResult,
    parse_spell,
    validate_spell_output,
)
from sunwell.core.context import AppContext

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
]
