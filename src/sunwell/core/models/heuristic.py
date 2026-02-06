"""Heuristic data models."""


from dataclasses import dataclass, field

# =============================================================================
# RFC-131: Lens Composition — Identity dataclass
# =============================================================================


@dataclass(frozen=True, slots=True)
class Identity:
    """Agent identity/persona configuration (RFC-131).

    Defines how the agent presents itself. Identity is NOT merged during
    lens composition — if a child lens specifies identity, it fully replaces
    the parent's identity.

    Example in YAML:
        communication:
          identity:
            name: "M'uru"
            nature: "A Naaru — a being of light and wisdom"
            style: "Helpful, warm, genuinely interested in assisting"
            prohibitions:
              - "Do NOT start responses with 'My name is M'uru' unless asked"
    """

    name: str
    """Name the agent uses (e.g., "M'uru", "Jarvis")."""

    nature: str | None = None
    """What the agent is (e.g., "A Naaru — a being of light")."""

    style: str | None = None
    """Communication style (e.g., "Helpful, warm, genuinely interested")."""

    prohibitions: tuple[str, ...] = ()
    """Things the agent should NOT do/claim."""

    def to_prompt_fragment(self) -> str:
        """Convert to system prompt section."""
        lines = [f"You are {self.name}."]

        if self.nature:
            lines.append(f"Nature: {self.nature}")

        if self.style:
            lines.append(f"Style: {self.style}")

        if self.prohibitions:
            lines.append("\nIMPORTANT:")
            for prohibition in self.prohibitions:
                lines.append(f"- {prohibition}")

        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Example:
    """Good/bad example for a heuristic."""

    good: tuple[str, ...] = ()
    bad: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Heuristic:
    """A professional heuristic (thinking pattern).

    Heuristics encode how professionals think about problems—not just
    what to do, but how to approach decisions, trade-offs, and edge cases.
    """

    name: str
    rule: str  # Core principle
    test: str | None = None  # How to check compliance
    always: tuple[str, ...] = ()  # Always do these
    never: tuple[str, ...] = ()  # Never do these
    examples: Example = field(default_factory=Example)
    priority: int = 1  # 1-10, higher = more important

    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format."""
        lines = [f"### {self.name}", f"**Rule**: {self.rule}"]

        if self.test:
            lines.append(f"**Test**: {self.test}")

        if self.always:
            always_text = ", ".join(self.always)
            lines.append(f"**Always**: {always_text}")

        if self.never:
            never_text = ", ".join(self.never)
            lines.append(f"**Never**: {never_text}")

        if self.examples.good:
            lines.append("**Good examples**:")
            for ex in self.examples.good:
                lines.append(f"  - {ex}")

        if self.examples.bad:
            lines.append("**Bad examples**:")
            for ex in self.examples.bad:
                lines.append(f"  - {ex}")

        return "\n".join(lines)

    def embedding_parts(self) -> tuple[str | None, ...]:
        """Return parts for embedding text (Embeddable protocol)."""
        return (self.name, self.rule, *self.always, *self.never)

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        from sunwell.core.types.embeddable import to_embedding_text

        return to_embedding_text(self)


@dataclass(frozen=True, slots=True)
class AntiHeuristic:
    """A pattern to avoid (anti-pattern).

    Anti-heuristics help detect when output is going wrong—common
    failure modes that should trigger correction.
    """

    name: str
    description: str
    triggers: tuple[str, ...]  # Phrases that indicate this anti-pattern
    correction: str  # How to fix

    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format."""
        lines = [
            f"### ⚠️ Avoid: {self.name}",
            f"**Description**: {self.description}",
            f"**Triggers**: {', '.join(self.triggers)}",
            f"**Correction**: {self.correction}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class CommunicationStyle:
    """Communication/tone configuration.

    RFC-131: Added identity field for agent persona configuration.
    """

    tone: tuple[str, ...] = ()  # e.g., ("professional", "concise")
    structure: str | None = None  # Output structure pattern
    identity: Identity | None = None  # RFC-131: Agent identity/persona

    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format."""
        lines = []
        if self.tone:
            lines.append(f"**Tone**: {', '.join(self.tone)}")
        if self.structure:
            lines.append(f"**Structure**: {self.structure}")
        if self.identity:
            lines.append("\n## Your Identity\n")
            lines.append(self.identity.to_prompt_fragment())
        return "\n".join(lines)
