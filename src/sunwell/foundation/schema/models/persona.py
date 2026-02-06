"""Persona data models for stakeholder simulation."""


from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Persona:
    """A stakeholder persona for testing outputs.

    Personas simulate different audience perspectives, stress-testing
    content from multiple viewpoints. Each persona brings unique
    goals, frustrations, and critique angles.
    """

    name: str
    description: str | None = None
    background: str | None = None  # What they know
    goals: tuple[str, ...] = ()  # What they want
    friction_points: tuple[str, ...] = ()  # What frustrates them
    attack_vectors: tuple[str, ...] = ()  # How they critique
    evaluation_prompt: str | None = None  # Custom eval prompt
    output_format: str | None = None  # How to report findings

    def to_evaluation_prompt(self, content: str) -> str:
        """Generate the persona evaluation prompt."""
        if self.evaluation_prompt:
            return self.evaluation_prompt.format(content=content)

        background = self.description or self.background or "Unknown background"
        goals = ", ".join(self.goals) if self.goals else "Not specified"
        friction = ", ".join(self.friction_points) if self.friction_points else "Not specified"

        questions = "\n".join(f"- {q}" for q in self.attack_vectors) if self.attack_vectors else ""

        return f"""You are a {self.name}: {background}

Your goals: {goals}
What frustrates you: {friction}

Review this content and identify problems from your perspective:

---
{content}
---

Questions to consider:
{questions}

Provide specific, actionable feedback. Focus on what would actually block or frustrate you."""

    def embedding_parts(self) -> tuple[str | None, ...]:
        """Return parts for embedding text (Embeddable protocol)."""
        return (self.name, self.description, self.background, *self.goals, *self.attack_vectors)

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        from sunwell.foundation.schema.models.embeddable import to_embedding_text

        return to_embedding_text(self)


@dataclass(frozen=True, slots=True)
class PersonaResult:
    """Result from persona evaluation."""

    persona_name: str
    approved: bool
    feedback: str
    issues: tuple[str, ...] = ()
    severity: str = "info"  # info, warning, error
