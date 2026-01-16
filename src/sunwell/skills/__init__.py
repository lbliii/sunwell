"""Skills module - Agent Skills integration for Sunwell Lenses.

This module implements RFC-011: Arming Sunwell Lenses with Agent Skills.

Skills provide action capabilities (instructions, scripts, templates)
while lenses provide judgment (heuristics, validators, personas).
Together they create "Capable Lenses" that can both execute tasks AND
evaluate their own output.
"""

from sunwell.skills.types import (
    Skill,
    SkillType,
    TrustLevel,
    Script,
    Template,
    Resource,
    SkillValidation,
    SkillRetryPolicy,
    SkillOutput,
    SkillOutputMetadata,
    Artifact,
    SkillResult,
    SkillError,
)
from sunwell.skills.executor import SkillExecutor
from sunwell.skills.sandbox import ScriptSandbox, ScriptResult
from sunwell.skills.interop import (
    SkillExporter,
    SkillImporter,
    SkillValidator,
    SkillValidationResult,
)

__all__ = [
    # Types
    "Skill",
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
    # Execution
    "SkillExecutor",
    "ScriptSandbox",
    "ScriptResult",
    # Interop (Phase 4)
    "SkillExporter",
    "SkillImporter",
    "SkillValidator",
    "SkillValidationResult",
]
