"""Project schema module for domain-agnostic project support (RFC-035).

This module provides the infrastructure for defining domain-specific project
schemas that allow Sunwell to work with any domain (fiction, architecture,
research, etc.) using the same underlying dependency resolution and parallel
execution infrastructure from RFC-034.

Extended in RFC-079 with universal project analysis capabilities:
- ProjectAnalysis: Universal project understanding
- analyze_project: Main analysis entry point
- Signal gathering, goal inference, and workspace selection

Key components:
- ProjectSchema: Domain-agnostic project definition (RFC-035)
- ArtifactType: User-defined artifact types (RFC-035)
- ConstraintValidator: DSL-based validation (RFC-035)
- ProjectAnalysis: Universal project understanding (RFC-079)
- analyze_project: Project intent analysis (RFC-079)
"""

# RFC-079: Project Intent Analyzer
from sunwell.project.cache import (
    invalidate_cache,
    load_cached_analysis,
    save_analysis_cache,
)
from sunwell.project.compatibility import is_lens_compatible
from sunwell.project.dsl import ConstraintDSL, ParsedRule
from sunwell.project.intent_analyzer import (
    analyze_monorepo,
    analyze_project,
    load_or_analyze,
)
from sunwell.project.intent_types import (
    WORKSPACE_PRIMARIES,
    DevCommand,
    InferredGoal,
    PipelineStep,
    Prerequisite,
    ProjectAnalysis,
    ProjectType,
    SuggestedAction,
)
from sunwell.project.monorepo import SubProject, detect_sub_projects, is_monorepo
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
from sunwell.project.signals import (
    GitStatus,
    ProjectSignals,
    gather_project_signals,
)
from sunwell.project.validators import ConstraintValidator, ConstraintViolation

__all__ = [
    # Schema (RFC-035)
    "ProjectSchema",
    "ArtifactType",
    "ArtifactField",
    "PlanningConfig",
    "PlanningPhase",
    "ValidatorConfig",
    "ConditionalRequirement",
    # DSL (RFC-035)
    "ConstraintDSL",
    "ParsedRule",
    # Validators (RFC-035)
    "ConstraintValidator",
    "ConstraintViolation",
    # Resolver (RFC-035)
    "SchemaResolver",
    # Compatibility (RFC-035)
    "is_lens_compatible",
    # Project Intent Types (RFC-079)
    "ProjectType",
    "ProjectAnalysis",
    "SuggestedAction",
    "DevCommand",
    "Prerequisite",
    "PipelineStep",
    "InferredGoal",
    "WORKSPACE_PRIMARIES",
    # Signals (RFC-079)
    "ProjectSignals",
    "GitStatus",
    "gather_project_signals",
    # Cache (RFC-079)
    "load_cached_analysis",
    "save_analysis_cache",
    "invalidate_cache",
    # Monorepo (RFC-079)
    "SubProject",
    "detect_sub_projects",
    "is_monorepo",
    # Analyzer (RFC-079)
    "analyze_project",
    "analyze_monorepo",
    "load_or_analyze",
]
