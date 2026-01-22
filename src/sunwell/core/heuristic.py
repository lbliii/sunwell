"""Heuristic data models."""


from dataclasses import dataclass, field


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

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        parts = [self.name, self.rule]
        if self.always:
            parts.extend(self.always)
        if self.never:
            parts.extend(self.never)
        return " ".join(parts)


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
    """Communication/tone configuration."""

    tone: tuple[str, ...] = ()  # e.g., ("professional", "concise")
    structure: str | None = None  # Output structure pattern

    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format."""
        lines = []
        if self.tone:
            lines.append(f"**Tone**: {', '.join(self.tone)}")
        if self.structure:
            lines.append(f"**Structure**: {self.structure}")
        return "\n".join(lines)
