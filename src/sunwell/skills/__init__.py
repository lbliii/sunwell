"""Skills module - Agent Skills integration for Sunwell Lenses.

This module implements RFC-011: Arming Sunwell Lenses with Agent Skills.
RFC-087: Skill-Lens DAG extends this with dependency tracking and caching.

Skills provide action capabilities (instructions, scripts, templates)
while lenses provide judgment (heuristics, validators, personas).
Together they create "Capable Lenses" that can both execute tasks AND
evaluate their own output.
"""

from sunwell.skills.cache import SkillCache, SkillCacheEntry, SkillCacheKey
from sunwell.skills.executor import (
    ExecutionContext,
    IncrementalSkillExecutor,
    SkillExecutionError,
    SkillExecutionPlan,
    SkillExecutor,
    WaveExecutionError,
)
from sunwell.skills.graph import (
    CircularDependencyError,
    MissingDependencyError,
    SkillGraph,
    SkillGraphError,
    UnsatisfiedRequiresError,
)
from sunwell.skills.interop import (
    SkillExporter,
    SkillImporter,
    SkillValidationResult,
    SkillValidator,
)
from sunwell.skills.sandbox import ScriptResult, ScriptSandbox
from sunwell.skills.types import (
    Artifact,
    Resource,
    Script,
    Skill,
    SkillDependency,
    SkillError,
    SkillOutput,
    SkillOutputMetadata,
    SkillResult,
    SkillRetryPolicy,
    SkillType,
    SkillValidation,
    Template,
    TrustLevel,
)

__all__ = [
    # Types
    "Skill",
    "SkillDependency",
    "SkillType",
    "TrustLevel",
    "Script",
    "Template",
    "Resource",
    "SkillValidation",
    "SkillRetryPolicy",
    "SkillOutput",
    "SkillOutputMetadata",
    "Artifact",
    "SkillResult",
    "SkillError",
    # RFC-087: Skill Graph
    "SkillGraph",
    "SkillGraphError",
    "CircularDependencyError",
    "MissingDependencyError",
    "UnsatisfiedRequiresError",
    # RFC-087: Skill Cache
    "SkillCache",
    "SkillCacheKey",
    "SkillCacheEntry",
    # Execution
    "SkillExecutor",
    "IncrementalSkillExecutor",
    "ExecutionContext",
    "SkillExecutionPlan",
    "SkillExecutionError",
    "WaveExecutionError",
    "ScriptSandbox",
    "ScriptResult",
    # Interop (Phase 4)
    "SkillExporter",
    "SkillImporter",
    "SkillValidator",
    "SkillValidationResult",
]
