"""Lens data model - the core expertise container."""


from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.core.framework import Framework
from sunwell.core.heuristic import AntiHeuristic, CommunicationStyle, Heuristic
from sunwell.core.persona import Persona
from sunwell.core.types import LensReference, SemanticVersion, Tier
from sunwell.core.validator import DeterministicValidator, HeuristicValidator, SchemaValidator
from sunwell.core.workflow import Refiner, Workflow

if TYPE_CHECKING:
    from sunwell.core.spell import Spell
    from sunwell.skills.types import Skill, SkillRetryPolicy


# =============================================================================
# RFC-072: Surface Affordances
# =============================================================================


@dataclass(frozen=True, slots=True)
class PrimitiveAffordance:
    """A primitive that a lens can surface (RFC-072).

    Affordances define which UI primitives are relevant for a lens's domain
    and under what conditions they should be activated.
    """

    primitive: str
    """Primitive ID (e.g., "CodeEditor", "Terminal")."""

    default_size: str = "panel"
    """Default size: "full", "split", "panel", "sidebar", "widget", "floating"."""

    weight: float = 0.5
    """Base relevance weight (0.0-1.0). Higher = more likely to be selected."""

    trigger: str | None = None
    """Pipe-separated keywords that activate this primitive (e.g., "test|verify|coverage")."""

    mode_hint: str | None = None
    """Hint to switch lens when this primitive is activated (e.g., "coder")."""


@dataclass(frozen=True, slots=True)
class Affordances:
    """Surface affordances for a lens (RFC-072).

    Defines which UI primitives should be shown when this lens is active.
    Primitives are categorized by importance:
    - primary: Always shown, core to the domain
    - secondary: Shown when triggered or space permits
    - contextual: Floating/widget elements shown on demand
    """

    primary: tuple[PrimitiveAffordance, ...] = ()
    """Always-visible primitives (max 2)."""

    secondary: tuple[PrimitiveAffordance, ...] = ()
    """Conditionally-visible primitives (max 3)."""

    contextual: tuple[PrimitiveAffordance, ...] = ()
    """Floating/widget primitives (max 2)."""


@dataclass(frozen=True, slots=True)
class LensMetadata:
    """Lens metadata.

    RFC-035 adds compatible_schemas for domain-specific lenses.
    RFC-070 adds library metadata (use_cases, tags, icon).
    """

    name: str
    domain: str | None = None
    version: SemanticVersion = field(default_factory=lambda: SemanticVersion(0, 1, 0))
    description: str | None = None
    author: str | None = None
    license: str | None = None

    # RFC-035: Schema compatibility
    compatible_schemas: tuple[str, ...] = ()
    """Schema types this lens is designed for.

    Empty tuple means universal (works with any schema or no schema).
    Example: ("fiction", "screenplay", "memoir")

    When a lens with compatible_schemas is applied to a project:
    1. Schema match check: Lens only activates if project.schema.type in compatible_schemas
    2. Validator merging: schema_validators are added to the project's validator list
    3. Inheritance preserved: extends/compose work normally; child lenses inherit parent's schemas
    """

    # RFC-070: Library metadata for browsing/filtering
    use_cases: tuple[str, ...] = ()
    """When to use this lens (e.g., "API documentation", "Code review")."""

    tags: tuple[str, ...] = ()
    """Searchable tags (e.g., "python", "documentation", "testing")."""

    icon: str | None = None
    """Optional icon identifier for UI display."""


@dataclass(frozen=True, slots=True)
class Provenance:
    """Evidence/citation configuration."""

    format: str = "file:line"  # Citation format
    types: tuple[str, ...] = ()  # Evidence categories
    required_contexts: tuple[str, ...] = ()  # When citations are required


@dataclass(frozen=True, slots=True)
class RouterTier:
    """A routing tier configuration."""

    level: Tier
    name: str
    triggers: tuple[str, ...] = ()  # Keywords that trigger this tier
    retrieval: bool = True
    validation: bool = True
    personas: tuple[str, ...] = ()  # Persona names to run
    require_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class Router:
    """Intent routing configuration."""

    tiers: tuple[RouterTier, ...] = ()
    intent_categories: tuple[str, ...] = ()
    signals: dict[str, str] = field(default_factory=dict)  # keyword → intent

    # RFC-070: Command shortcuts for skill invocation
    shortcuts: dict[str, str] = field(default_factory=dict)
    """Maps shortcut commands to skill names.

    Example: {"::a": "audit-documentation", "::p": "polish-documentation"}
    """

    # RFC-070: Skill routing configuration
    skill_triggers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Maps skill names to trigger keywords for automatic discovery.

    This is derived from skills' trigger fields during lens loading
    for efficient runtime lookup.
    """


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    """Quality gate requirements."""

    min_confidence: float = 0.7
    required_validators: tuple[str, ...] = ()  # Must-pass validators
    persona_agreement: float = 0.5  # Min % of personas that must approve
    retry_limit: int = 3  # Max refinement loops


@dataclass(slots=True)
class Lens:
    """The core expertise container.

    A Lens represents a professional perspective that can be applied
    to LLM interactions. It contains heuristics (how to think),
    frameworks (methodology), personas (testing), validators
    (quality gates), and skills (action capabilities).

    RFC-011 introduces skills: Agent Skills integration that combines
    judgment (lenses) with action (skills) to create "Capable Lenses".
    """

    metadata: LensMetadata

    # Inheritance/composition
    extends: LensReference | None = None
    compose: tuple[LensReference, ...] = ()

    # Core heuristics
    heuristics: tuple[Heuristic, ...] = ()
    anti_heuristics: tuple[AntiHeuristic, ...] = ()
    communication: CommunicationStyle | None = None

    # Methodology
    framework: Framework | None = None

    # Testing
    personas: tuple[Persona, ...] = ()

    # Quality gates
    deterministic_validators: tuple[DeterministicValidator, ...] = ()
    heuristic_validators: tuple[HeuristicValidator, ...] = ()

    # Workflows
    workflows: tuple[Workflow, ...] = ()
    refiners: tuple[Refiner, ...] = ()

    # Evidence
    provenance: Provenance | None = None

    # Routing
    router: Router | None = None

    # Quality policy
    quality_policy: QualityPolicy = field(default_factory=QualityPolicy)

    # Skills (RFC-011: Agent Skills integration)
    skills: tuple[Skill, ...] = ()
    skill_retry: SkillRetryPolicy | None = None

    # RFC-087: Skill library sources for resolving REFERENCE skills
    skill_sources: tuple[str, ...] = ()
    """Skill libraries to search when resolving SkillType.REFERENCE skills.

    Examples:
        - "sunwell/common" → built-in skill library
        - "./skills" → local project skills directory
        - "fount://my-skills@^1.0" → versioned fount package

    Resolution order: local skills first, then skill_sources in order.
    """

    # Spellbook (RFC-021: Portable Workflow Incantations)
    spellbook: tuple[Spell, ...] = ()

    # RFC-035: Schema-specific validators
    schema_validators: tuple[SchemaValidator, ...] = ()
    """Validators that only apply when a compatible schema is active.

    These extend the project schema's validators with lens-specific checks.
    Unlike heuristic_validators (general content), schema_validators target
    specific artifact types defined in the schema.

    Example:
        A developmental-editor lens for fiction might add:
        SchemaValidator(
            name="character_arc_complete",
            check="Every major character must change by the end",
            applies_to="character",
            condition="character.role == 'major'",
        )
    """

    # RFC-072: Surface affordances
    affordances: Affordances | None = None
    """UI primitives this lens surfaces. None = use domain defaults."""

    # RFC-130: Agent Constellation — Specialist spawning
    can_spawn: bool = False
    """Whether agent using this lens can spawn specialist sub-agents.

    When True, the agent can delegate complex subtasks to specialists
    instead of struggling alone. Specialists run with focused context
    and limited token budget.

    Example:
        A 'senior-engineer' lens might enable spawning for:
        - code_reviewer: Security review of auth changes
        - architect: Design review for new modules
        - debugger: Deep investigation of tricky bugs
    """

    max_children: int = 3
    """Maximum specialist spawns allowed per execution.

    Prevents runaway spawning. After max_children specialists are spawned,
    the agent must complete work directly or request user guidance.
    """

    spawn_budget_tokens: int = 10_000
    """Token budget allocated to spawned specialists (total, not per-spawn).

    Budget is split across spawned specialists. Parent keeps 80% of its
    budget, specialists share the remaining 20%.
    """

    # Source tracking
    source_path: Path | None = None

    @property
    def all_validators(self) -> tuple[DeterministicValidator | HeuristicValidator, ...]:
        """All validators (deterministic + heuristic)."""
        return self.deterministic_validators + self.heuristic_validators

    def get_persona(self, name: str) -> Persona | None:
        """Get a persona by name."""
        for p in self.personas:
            if p.name.lower() == name.lower():
                return p
        return None

    def get_heuristic(self, name: str) -> Heuristic | None:
        """Get a heuristic by name."""
        for h in self.heuristics:
            if h.name.lower() == name.lower():
                return h
        return None

    def get_workflow(self, name: str) -> Workflow | None:
        """Get a workflow by name."""
        for w in self.workflows:
            if w.name.lower() == name.lower():
                return w
        return None

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        for s in self.skills:
            # Skills use hyphens per Agent Skills spec
            if s.name.lower() == name.lower() or s.name.replace("-", "_") == name.replace("-", "_"):
                return s
        return None

    def get_spell(self, incantation: str) -> Spell | None:
        """Get a spell by incantation or alias."""
        incantation_lower = incantation.lower()
        for spell in self.spellbook:
            if spell.incantation.lower() == incantation_lower:
                return spell
            if incantation_lower in (a.lower() for a in spell.aliases):
                return spell
        return None

    def to_context(self, components: list[str] | None = None) -> str:
        """Convert lens to context injection format.

        If components is None, includes all components.
        Otherwise, only includes specified component names.
        """
        sections = []

        # Header
        sections.append(f"# Expertise: {self.metadata.name}")
        if self.metadata.description:
            sections.append(self.metadata.description)

        # Filter heuristics
        heuristics = self.heuristics
        if components:
            heuristics = tuple(h for h in heuristics if h.name in components)

        if heuristics:
            sections.append("\n## Heuristics")
            for h in heuristics:
                sections.append(h.to_prompt_fragment())

        # Anti-heuristics
        if self.anti_heuristics:
            sections.append("\n## Anti-Patterns to Avoid")
            for ah in self.anti_heuristics:
                sections.append(ah.to_prompt_fragment())

        # Communication style
        if self.communication:
            sections.append("\n## Communication Style")
            sections.append(self.communication.to_prompt_fragment())

        # Framework
        if self.framework:
            sections.append("\n" + self.framework.to_prompt_fragment())

        return "\n".join(sections)

    def summary(self) -> str:
        """Get a brief summary of the lens."""
        parts = [f"Lens: {self.metadata.name} v{self.metadata.version}"]
        if self.metadata.domain:
            parts.append(f"Domain: {self.metadata.domain}")
        parts.append(f"Heuristics: {len(self.heuristics)}")
        parts.append(f"Validators: {len(self.all_validators)}")
        parts.append(f"Personas: {len(self.personas)}")
        if self.skills:
            parts.append(f"Skills: {len(self.skills)}")
        return " | ".join(parts)


# =============================================================================
# RFC-XXX: Ephemeral Lenses for Smart-to-Dumb Model Delegation
# =============================================================================


@dataclass(frozen=True, slots=True)
class EphemeralLens:
    """Virtual lens generated on-the-fly for model delegation.

    A smart model (Opus, o1) creates an EphemeralLens encoding its understanding
    of how to complete a task, then delegates the actual generation to a cheaper
    model (Haiku, 4o-mini) that follows the encoded expertise.

    Use cases:
    - Cost optimization: Think once with Opus, generate 10 files with Haiku
    - Parallel execution: Same lens across many Haiku instances
    - Quality preservation: Expertise survives model downgrade

    Example:
        >>> # Smart model creates lens
        >>> lens = await create_ephemeral_lens(
        ...     model=opus,
        ...     task="Build REST API with FastAPI",
        ...     context=codebase_summary,
        ... )
        >>>
        >>> # Cheap model uses lens for generation
        >>> loop = AgentLoop(model=haiku, ...)
        >>> async for event in loop.run(task, lens=lens):
        ...     ...

    The lens implements the same `to_context()` interface as Lens,
    so it can be used interchangeably in prompts.
    """

    # Core expertise (what to do)
    heuristics: tuple[str, ...] = ()
    """Domain-specific guidelines. e.g., "Use Pydantic for validation"."""

    patterns: tuple[str, ...] = ()
    """Code patterns to follow. e.g., "snake_case functions", "type hints required"."""

    anti_patterns: tuple[str, ...] = ()
    """Things to avoid. e.g., "No global state", "No print() debugging"."""

    constraints: tuple[str, ...] = ()
    """Hard requirements. e.g., "Must use existing db.py module"."""

    # Examples (show, don't tell)
    examples: tuple[str, ...] = ()
    """Code snippets demonstrating the desired style."""

    # Task scoping
    task_scope: str = ""
    """Description of what tasks this lens is valid for."""

    target_files: tuple[str, ...] = ()
    """Files this lens is designed to generate/modify."""

    # Provenance
    generated_by: str = ""
    """Model that created this lens."""

    generation_prompt: str = ""
    """The prompt used to generate this lens (for debugging/replay)."""

    def to_context(self) -> str:
        """Format for prompt injection (same interface as Lens).

        This allows EphemeralLens to be used anywhere a Lens can be used.
        """
        sections = []

        # Header
        if self.task_scope:
            sections.append(f"# Task Expertise: {self.task_scope}")
        else:
            sections.append("# Generated Expertise")

        # Heuristics
        if self.heuristics:
            sections.append("\n## Guidelines")
            for h in self.heuristics:
                sections.append(f"- {h}")

        # Patterns
        if self.patterns:
            sections.append("\n## Patterns to Follow")
            for p in self.patterns:
                sections.append(f"- {p}")

        # Anti-patterns
        if self.anti_patterns:
            sections.append("\n## Things to Avoid")
            for ap in self.anti_patterns:
                sections.append(f"- ❌ {ap}")

        # Constraints
        if self.constraints:
            sections.append("\n## Hard Constraints")
            for c in self.constraints:
                sections.append(f"- ⚠️ {c}")

        # Examples
        if self.examples:
            sections.append("\n## Style Examples")
            for i, ex in enumerate(self.examples, 1):
                sections.append(f"\n### Example {i}")
                sections.append(f"```\n{ex}\n```")

        return "\n".join(sections)

    def summary(self) -> str:
        """Brief summary for logging."""
        parts = [f"EphemeralLens({self.task_scope or 'unnamed'})"]
        parts.append(f"heuristics={len(self.heuristics)}")
        parts.append(f"patterns={len(self.patterns)}")
        if self.generated_by:
            parts.append(f"by={self.generated_by}")
        return " ".join(parts)


# Type alias for functions that accept either lens type
LensLike = Lens | EphemeralLens
