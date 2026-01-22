"""Skill data models - types for Agent Skills integration.

Implements the skill schema from RFC-011 Appendix A.
RFC-087: Skill-Lens DAG extends this with dependency tracking.
"""


import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sunwell.models.protocol import Tool


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
        - "read-file" → local skill in same lens
        - "sunwell/common:read-file" → skill from library
        - "fount://audit-skills@^1.0:validate-code" → versioned fount reference
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
    """Name of permission preset to inherit.

    Presets are defined in skills/permission-presets.yaml.
    When set, the skill inherits all permissions and security
    metadata from the preset.

    The skill can override specific fields:

        preset: read-only
        permissions:
          shell:
            allow: ["git diff"]  # Override just shell

    Overrides are merged, not replaced.
    """

    # RFC-087: Skill dependencies for DAG ordering
    depends_on: tuple[SkillDependency, ...] = ()
    """Skills that must execute before this one.

    Dependencies form a DAG. Circular dependencies are detected at resolution time.
    """

    # RFC-087: Artifact flow for incremental execution
    produces: tuple[str, ...] = ()
    """Context keys this skill produces.

    These are keys in the execution context dict, NOT file paths.
    Example: ("code_analysis", "lint_results")

    Used for:
    1. Cache key computation (if produces change, invalidate)
    2. Dependency validation (requires must be subset of upstream produces)
    """

    requires: tuple[str, ...] = ()
    """Context keys this skill requires from upstream skills.

    Example: ("file_content",) means this skill needs the output
    from a skill that produces "file_content".

    Validated at resolution time: all requires must be satisfied
    by produces of skills in depends_on (transitively).
    """

    # RFC-070: Trigger patterns for automatic discovery
    triggers: tuple[str, ...] = ()
    """Keywords/patterns that suggest this skill.

    When router analyzes intent, it matches against skill triggers
    to suggest relevant skills alongside lens selection.

    Example: triggers: ("audit", "validate", "check", "verify")
    """

    # RFC-089: Security permissions for declarative permission graphs
    permissions: dict | None = None
    """Security permissions declaration (RFC-089).

    Defines what resources this skill can access:
    - filesystem: {read: [...], write: [...]} - glob patterns
    - network: {allow: [...], deny: [...]} - host:port patterns
    - shell: {allow: [...], deny: [...]} - command prefixes
    - environment: {read: [...], write: [...]} - env var names

    Example:
        permissions:
          filesystem:
            read: ["/app/src/*", "/app/config/*.yaml"]
            write: ["/tmp/build-*"]
          network:
            allow: ["registry.internal:5000"]
            deny: ["*"]
          shell:
            allow: ["docker build", "docker push"]
            deny: ["docker run"]

    If None, skill inherits ambient permissions (legacy behavior).
    """

    # RFC-089: Security metadata
    security: dict | None = None
    """Security metadata for the skill (RFC-089).

    Optional metadata for security policies:
    - data_classification: "public" | "internal" | "confidential" | "secret"
    - requires_approval: bool - always require human approval
    - audit_level: "minimal" | "standard" | "verbose"

    Example:
        security:
          data_classification: internal
          requires_approval: false
          audit_level: standard
    """

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

    def to_tool(self) -> "Tool":
        """Convert this skill to a callable tool (RFC-012).

        Returns:
            A Tool object suitable for LLM function calling.
        """
        from sunwell.models.protocol import Tool

        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema or {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What to accomplish with this skill",
                    },
                },
                "required": ["task"],
            },
        )


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
    """Values produced by this skill, available to downstream skills.

    Keys should match the skill's produces declaration.
    Example: {"code_analysis": {...}, "complexity_score": 7.5}
    """


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
