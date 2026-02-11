"""Skill data models - types for Agent Skills integration.

Implements the skill schema from RFC-011 Appendix A.
RFC-087: Skill-Lens DAG extends this with dependency tracking.
RFC-111: Adds SkillMetadata for progressive disclosure.

Moved from sunwell.planning.skills.types to foundation since these
are pure data types (stdlib-only) used by the lens schema loader.

Note: Skill.to_tool() was removed during extraction. Use
sunwell.models.core.protocol.tool_from_skill() instead.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class SkillType(Enum):
    """How a skill is defined."""

    INLINE = "inline"  # Defined directly in lens file
    REFERENCE = "reference"  # External fount reference
    LOCAL = "local"  # Local folder with SKILL.md


# =============================================================================
# RFC-087: Skill Dependencies
# =============================================================================


@dataclass(frozen=True, slots=True)
class SkillDependency:
    """A dependency on another skill (RFC-087).

    Uses the same source format as SkillType.REFERENCE for consistency.

    Examples:
        - "read-file" -> local skill in same lens
        - "sunwell/common:read-file" -> skill from library
        - "fount://audit-skills@^1.0:validate-code" -> versioned fount reference
    """

    source: str
    """Skill reference in format: [library:]skill_name or fount://..."""

    @property
    def is_local(self) -> bool:
        """True if this references a skill in the same lens."""
        return ":" not in self.source and "/" not in self.source

    @property
    def skill_name(self) -> str:
        """Extract skill name from reference."""
        if ":" in self.source:
            return self.source.split(":")[-1]
        return self.source

    @property
    def library(self) -> str | None:
        """Extract library name if external reference."""
        if ":" in self.source:
            return self.source.rsplit(":", 1)[0]
        return None

    def __str__(self) -> str:
        return self.source


# =============================================================================
# RFC-111: Skill Metadata for Progressive Disclosure
# =============================================================================


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Lightweight skill info for routing and DAG construction (RFC-111).

    This is the ONLY thing loaded initially for progressive disclosure.
    Full instructions are loaded lazily when the skill executes.

    The metadata contains enough information to:
    1. Build the dependency graph (depends_on, produces, requires)
    2. Match skills to user intent (name, description, triggers)
    3. Determine execution order

    Full skill content (instructions, scripts, templates) is loaded
    only when needed — often never, if results are cached.
    """

    name: str
    """Unique skill name."""

    description: str
    """Human-readable purpose for discovery."""

    skill_type: SkillType
    """How the skill is defined (inline, reference, local)."""

    # DAG fields (needed for graph construction)
    depends_on: tuple[SkillDependency, ...] = ()
    """Skills that must execute before this one."""

    produces: tuple[str, ...] = ()
    """Context keys this skill produces."""

    requires: tuple[str, ...] = ()
    """Context keys this skill requires from upstream."""

    triggers: tuple[str, ...] = ()
    """Keywords/patterns that suggest this skill."""

    # Reference to full skill (lazy loaded)
    source_path: Path | None = None
    """Path to load full skill content from."""

    def matches_intent(self, query: str) -> float:
        """Score how well this skill matches a user intent.

        Returns a score from 0.0 to 1.0 based on:
        - Name match (0.5)
        - Trigger match (0.3 per trigger)
        - Description keyword overlap (0.1 per word)
        """
        query_lower = query.lower()
        score = 0.0

        # Name match
        if self.name in query_lower:
            score += 0.5

        # Trigger match
        for trigger in self.triggers:
            if trigger.lower() in query_lower:
                score += 0.3

        # Description keyword match
        desc_words = set(self.description.lower().split())
        query_words = set(query_lower.split())
        overlap = len(desc_words & query_words)
        score += overlap * 0.1

        return min(score, 1.0)

    @classmethod
    def from_skill(cls, skill: Skill) -> SkillMetadata:
        """Create metadata from a full Skill object.

        Args:
            skill: The skill to extract metadata from

        Returns:
            SkillMetadata with DAG and routing fields
        """
        return cls(
            name=skill.name,
            description=skill.description,
            skill_type=skill.skill_type,
            depends_on=skill.depends_on,
            produces=skill.produces,
            requires=skill.requires,
            triggers=skill.triggers,
            source_path=Path(skill.path) if skill.path else None,
        )


class TrustLevel(Enum):
    """Trust level controls sandbox restrictions.

    Maps directly to sandbox configuration per RFC-011.
    """

    FULL = "full"  # No sandbox. Use ONLY for your own scripts.
    SANDBOXED = "sandboxed"  # Default. Restricted execution.
    NONE = "none"  # Instructions only. Scripts are IGNORED.


# Skill name validation pattern (per Agent Skills spec)
SKILL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_skill_name(name: str) -> None:
    """Validate skill name matches Agent Skills spec.

    Rules:
    - Lowercase letters, numbers, hyphens only
    - Must start with a letter
    - Max 64 characters
    - Cannot start/end with hyphen
    - No consecutive hyphens
    """
    if len(name) > 64:
        raise ValueError(f"Skill name too long (max 64): {name}")

    if name.startswith("-") or name.endswith("-"):
        raise ValueError(f"Skill name cannot start/end with hyphen: {name}")

    if "--" in name:
        raise ValueError(f"Skill name cannot have consecutive hyphens: {name}")

    if not SKILL_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid skill name '{name}'. "
            "Must be lowercase letters, numbers, and hyphens, starting with a letter."
        )


@dataclass(frozen=True, slots=True)
class Script:
    """A script that can be executed by a skill."""

    name: str  # Filename, e.g., "extract.py"
    content: str  # Script source code
    language: Literal["python", "node", "bash"] = "python"
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Template:
    """A file template with variable expansion."""

    name: str  # Template filename, e.g., "component.tsx"
    content: str  # Template content with ${vars}


@dataclass(frozen=True, slots=True)
class Resource:
    """A reference resource for a skill."""

    name: str  # Resource label
    url: str | None = None  # External URL (mutually exclusive with path)
    path: str | None = None  # Local path (mutually exclusive with url)

    def __post_init__(self) -> None:
        if self.url and self.path:
            raise ValueError("Resource cannot have both url and path")
        if not self.url and not self.path:
            raise ValueError("Resource must have either url or path")


@dataclass(frozen=True, slots=True)
class SkillValidation:
    """Validation binding for a skill."""

    validators: tuple[str, ...] = ()  # Validator names from this lens
    personas: tuple[str, ...] = ()  # Persona names for testing
    min_confidence: float = 0.7  # 0.0-1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(
                f"min_confidence must be between 0.0 and 1.0, got {self.min_confidence}"
            )


@dataclass(frozen=True, slots=True)
class SkillRetryPolicy:
    """Retry policy for skill execution."""

    max_attempts: int = 3
    backoff_ms: tuple[int, ...] = (100, 500, 2000)
    retry_on: tuple[str, ...] = ("timeout", "validation_failure")
    abort_on: tuple[str, ...] = ("security_violation", "script_crash")

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError(
                f"max_attempts must be between 1 and 10, got {self.max_attempts}"
            )


@dataclass(frozen=True, slots=True)
class Skill:
    """An agent skill that provides action capabilities.

    Skills define HOW to do something (instructions, scripts, templates)
    while lenses define HOW to judge the output (heuristics, validators).

    RFC-087: Skills can now declare dependencies on other skills via depends_on,
    forming a DAG for ordered execution with incremental caching.

    RFC-089: Skills can declare permissions for security-first execution.
    RFC-092: Skills can inherit permissions from presets via preset field.
    """

    # Required fields
    name: str  # Unique identifier within lens
    description: str  # Human-readable purpose for discovery
    skill_type: SkillType  # How skill is defined

    # RFC-092: Permission preset inheritance
    preset: str | None = None
    """Name of permission preset to inherit."""

    # RFC-087: Skill dependencies for DAG ordering
    depends_on: tuple[SkillDependency, ...] = ()
    """Skills that must execute before this one."""

    # RFC-087: Artifact flow for incremental execution
    produces: tuple[str, ...] = ()
    """Context keys this skill produces."""

    requires: tuple[str, ...] = ()
    """Context keys this skill requires from upstream skills."""

    # RFC-070: Trigger patterns for automatic discovery
    triggers: tuple[str, ...] = ()
    """Keywords/patterns that suggest this skill."""

    # RFC-089: Security permissions for declarative permission graphs
    permissions: dict | None = None
    """Security permissions declaration (RFC-089)."""

    # RFC-089: Security metadata
    security: dict | None = None
    """Security metadata for the skill (RFC-089)."""

    # Agent Skills spec alignment
    compatibility: str | None = None  # Environment requirements
    allowed_tools: tuple[str, ...] = ()  # Pre-approved tools

    # RFC-012: Tool calling integration
    parameters_schema: dict | None = None  # JSON Schema for tool parameters

    # For type: inline
    instructions: str | None = None  # Markdown instructions
    scripts: tuple[Script, ...] = ()
    templates: tuple[Template, ...] = ()
    resources: tuple[Resource, ...] = ()

    # For type: reference
    source: str | None = None  # e.g., "fount://name@^1.0"

    # For type: local
    path: str | None = None  # e.g., "./skills/my-skill/"

    # Execution settings (all types)
    trust: TrustLevel = TrustLevel.SANDBOXED
    timeout: int = 30  # Seconds, range 1-300
    override: bool = False  # If true, overrides same-name skill from parent

    # Validation binding (all types)
    validate_with: SkillValidation = field(default_factory=SkillValidation)

    def __post_init__(self) -> None:
        validate_skill_name(self.name)

        if not 1 <= self.timeout <= 300:
            raise ValueError(f"timeout must be between 1 and 300, got {self.timeout}")

        # Validate type-specific requirements
        if self.skill_type == SkillType.INLINE and not self.instructions:
            raise ValueError(f"Inline skill '{self.name}' requires instructions field")

        if self.skill_type == SkillType.REFERENCE and not self.source:
            raise ValueError(f"Reference skill '{self.name}' requires source field")

        if self.skill_type == SkillType.LOCAL and not self.path:
            raise ValueError(f"Local skill '{self.name}' requires path field")

    def to_prompt_fragment(self) -> str:
        """Convert skill to prompt injection format."""
        parts = [f"### Skill: {self.name}"]

        if self.description:
            parts.append(f"\n{self.description}")

        if self.instructions:
            parts.append(f"\n#### Instructions\n\n{self.instructions}")

        if self.templates:
            parts.append("\n#### Templates")
            for t in self.templates:
                parts.append(f"\n**{t.name}**:\n```\n{t.content}\n```")

        if self.resources:
            parts.append("\n#### Resources")
            for r in self.resources:
                if r.url:
                    parts.append(f"- [{r.name}]({r.url})")
                elif r.path:
                    parts.append(f"- {r.name}: `{r.path}`")

        return "\n".join(parts)


# Output types


@dataclass(frozen=True, slots=True)
class Artifact:
    """A file artifact produced by skill execution."""

    path: Path
    operation: Literal["created", "modified", "deleted"]
    content_hash: str  # SHA-256 for change detection


@dataclass(frozen=True, slots=True)
class SkillOutputMetadata:
    """Metadata passed from skill to validators."""

    skill_name: str
    execution_time_ms: int
    scripts_run: tuple[str, ...] = ()

    # Hints for validators
    expected_format: str | None = None  # e.g., "markdown with code blocks"
    source_files: tuple[str, ...] = ()  # Files the skill read
    target_files: tuple[str, ...] = ()  # Files the skill wrote


@dataclass(frozen=True, slots=True)
class SkillOutput:
    """Output from skill execution, input to validation."""

    # Primary output (what the skill produced)
    content: str
    content_type: Literal["text", "code", "markdown", "json"] = "text"

    # Artifacts (files created/modified)
    artifacts: tuple[Artifact, ...] = ()

    # Metadata for validation
    metadata: SkillOutputMetadata | None = None

    # RFC-087: Context values this skill produces (keyed by skill.produces)
    context: dict[str, Any] = field(default_factory=dict)
    """Values produced by this skill, available to downstream skills."""


@dataclass(frozen=True, slots=True)
class SkillResult:
    """Complete result from skill execution with validation."""

    content: str
    skill_name: str
    lens_name: str

    # Validation results
    validation_passed: bool = True
    confidence: float = 1.0

    # Artifacts produced
    artifacts: tuple[Artifact, ...] = ()

    # Execution info
    execution_time_ms: int = 0
    scripts_run: tuple[str, ...] = ()
    refinement_count: int = 0


@dataclass(frozen=True, slots=True)
class SkillError:
    """Structured error from skill execution."""

    phase: Literal["parse", "execute", "validate", "refine"]
    skill_name: str
    message: str
    recoverable: bool

    # Optional context for debugging
    details: dict[str, Any] = field(default_factory=dict)
    script_name: str | None = None
    exit_code: int | None = None
    stderr: str | None = None
