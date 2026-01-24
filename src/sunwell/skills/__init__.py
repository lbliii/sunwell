"""Skills module - Agent Skills integration for Sunwell Lenses.

This module implements RFC-011: Arming Sunwell Lenses with Agent Skills.
RFC-087: Skill-Lens DAG extends this with dependency tracking and caching.
RFC-110: Skill execution moved to Agent. This module provides skill definitions.
RFC-111: Skill DAG Activation — SkillCompiler bridges skills to tasks.
RFC-111 Phase 5: SkillLearner and SkillLibrary for self-learning skills.

Skills provide action capabilities (instructions, scripts, templates)
while lenses provide judgment (heuristics, validators, personas).
Together they create "Capable Lenses" that can both execute tasks AND
evaluate their own output.
"""

from sunwell.skills.cache import SkillCache, SkillCacheEntry, SkillCacheKey
from sunwell.skills.compiler import (
    CompiledTaskGraph,
    SkillCompilationCache,
    SkillCompilationError,
    SkillCompiler,
    has_dag_metadata,
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
from sunwell.skills.learner import (
    ExecutionPattern,
    LearnedSkillMetadata,
    SkillLearner,
    SkillLearningResult,
)
from sunwell.skills.library import SkillLibrary, SkillProvenance
from sunwell.skills.sandbox import ScriptResult, ScriptSandbox
from sunwell.skills.types import (
    Artifact,
    Resource,
    Script,
    Skill,
    SkillDependency,
    SkillError,
    SkillMetadata,
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
    "SkillMetadata",
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
    # RFC-111: Skill Compiler
    "SkillCompiler",
    "SkillCompilationCache",
    "SkillCompilationError",
    "CompiledTaskGraph",
    "has_dag_metadata",
    # RFC-111 Phase 5: Self-Learning
    "SkillLearner",
    "SkillLearningResult",
    "ExecutionPattern",
    "LearnedSkillMetadata",
    "SkillLibrary",
    "SkillProvenance",
    # Sandbox
    "ScriptSandbox",
    "ScriptResult",
    # Interop (Phase 4)
    "SkillExporter",
    "SkillImporter",
    "SkillValidator",
    "SkillValidationResult",
]
