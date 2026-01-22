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
