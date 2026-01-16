"""Framework/methodology data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameworkCategory:
    """A category within a framework (e.g., TUTORIAL in Diataxis).

    Categories define different types of content within a framework,
    each with its own purpose, structure, and boundaries.
    """

    name: str
    purpose: str
    structure: tuple[str, ...] = ()  # Expected sections
    includes: tuple[str, ...] = ()  # What belongs here
    excludes: tuple[str, ...] = ()  # What doesn't belong
    triggers: tuple[str, ...] = ()  # Keywords that indicate this category

    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format."""
        lines = [
            f"### {self.name}",
            f"**Purpose**: {self.purpose}",
        ]

        if self.structure:
            lines.append(f"**Structure**: {', '.join(self.structure)}")

        if self.includes:
            lines.append(f"**Include**: {', '.join(self.includes)}")

        if self.excludes:
            lines.append(f"**Exclude**: {', '.join(self.excludes)}")

        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Framework:
    """A professional methodology (Diataxis, IRAC, AIDA, etc.).

    Frameworks provide structured approaches to categorizing and
    creating content within a domain.
    """

    name: str
    description: str | None = None
    decision_tree: str | None = None  # How to categorize work
    categories: tuple[FrameworkCategory, ...] = ()

    def classify(self, content: str) -> FrameworkCategory | None:
        """Classify content into a category based on triggers."""
        content_lower = content.lower()
        for category in self.categories:
            if any(trigger.lower() in content_lower for trigger in category.triggers):
                return category
        return None

    def get_category(self, name: str) -> FrameworkCategory | None:
        """Get a category by name."""
        for category in self.categories:
            if category.name.lower() == name.lower():
                return category
        return None

    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format."""
        lines = [f"## Framework: {self.name}"]

        if self.description:
            lines.append(self.description)

        if self.decision_tree:
            lines.append(f"\n**Decision Tree**: {self.decision_tree}")

        if self.categories:
            lines.append("\n### Categories")
            for category in self.categories:
                lines.append(category.to_prompt_fragment())
                lines.append("")

        return "\n".join(lines)
