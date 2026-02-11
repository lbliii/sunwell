"""Skill data models - types for Agent Skills integration.

Canonical definitions moved to sunwell.foundation.schema.models.skill;
re-exported here for backward compatibility.

Implements the skill schema from RFC-011 Appendix A.
RFC-087: Skill-Lens DAG extends this with dependency tracking.
RFC-111: Adds SkillMetadata for progressive disclosure.
"""

from typing import TYPE_CHECKING

from sunwell.foundation.schema.models.skill import (
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
    SKILL_NAME_PATTERN,
    Template,
    TrustLevel,
    validate_skill_name,
)

if TYPE_CHECKING:
    from sunwell.models import Tool

__all__ = [
    # Enums
    "SkillType",
    "TrustLevel",
    # Dependencies (RFC-087)
    "SkillDependency",
    # Metadata (RFC-111)
    "SkillMetadata",
    # Data types
    "Script",
    "Template",
    "Resource",
    "SkillValidation",
    "SkillRetryPolicy",
    "Skill",
    # Outputs
    "Artifact",
    "SkillOutputMetadata",
    "SkillOutput",
    "SkillResult",
    "SkillError",
    # Helpers
    "SKILL_NAME_PATTERN",
    "validate_skill_name",
]
