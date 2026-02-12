"""Reflection types for Phase 3: Reflection System.

Reflections are higher-order insights about patterns, constraints,
and mental models derived from learnings.

Part of Hindsight-inspired memory enhancements.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Reflection:
    """A reflection on a set of learnings.

    Reflections synthesize higher-order insights about WHY
    patterns and constraints exist, enabling deeper understanding.

    Example:
        Input learnings:
        - "Don't use global state in components"
        - "Avoid side effects in render"
        - "Use hooks for state management"

        Output reflection:
        - theme: "React functional programming"
        - causality: "These stem from React's declarative rendering model"
        - mental_model: "Functional purity enables predictable re-renders"
    """

    id: str
    """Unique identifier for this reflection."""

    theme: str
    """Common theme connecting the learnings."""

    causality: str
    """Why these patterns/constraints exist (root cause)."""

    summary: str
    """Concise summary (2-3 sentences)."""

    source_learning_ids: tuple[str, ...] = field(default_factory=tuple)
    """Learning IDs this reflection is based on."""

    confidence: float = 0.8
    """Confidence in this reflection (0-1)."""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this reflection was created."""

    category: str = "reflection"
    """Learning category for storage."""

    def to_learning_dict(self) -> dict:
        """Convert to Learning-compatible dict for storage.

        Reflections are stored as special learnings with category="reflection".
        """
        fact = f"Reflection on {self.theme}: {self.summary}\n\nCausality: {self.causality}"
        return {
            "id": self.id,
            "fact": fact,
            "category": self.category,
            "confidence": self.confidence,
            "source_turns": self.source_learning_ids,
            "metadata": {
                "type": "reflection",
                "theme": self.theme,
                "causality": self.causality,
                "summary": self.summary,
            },
        }

    def to_dict(self) -> dict:
        """Serialize reflection."""
        return {
            "id": self.id,
            "theme": self.theme,
            "causality": self.causality,
            "summary": self.summary,
            "source_learning_ids": list(self.source_learning_ids),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Reflection":
        """Deserialize reflection."""
        return cls(
            id=data["id"],
            theme=data["theme"],
            causality=data["causality"],
            summary=data["summary"],
            source_learning_ids=tuple(data.get("source_learning_ids", [])),
            confidence=data.get("confidence", 0.8),
            created_at=data.get("created_at", datetime.now().isoformat()),
            category=data.get("category", "reflection"),
        )


@dataclass(slots=True)
class MentalModel:
    """A coherent mental model about a topic.

    Mental models are synthesized from reflections and learnings,
    providing a single coherent view that's more token-efficient
    than injecting individual learnings.

    Example:
        Topic: "React state management"
        Core principles:
        - "Components are pure functions of props and state"
        - "State updates trigger re-renders"
        - "Hooks provide functional state management"

        Key patterns:
        - "useState for local state"
        - "useContext for shared state"
        - "useReducer for complex state"

        Anti-patterns:
        - "Mutating state directly"
        - "Using global variables"
        - "Side effects in render"
    """

    id: str
    """Unique identifier."""

    topic: str
    """Topic this model covers (e.g., "React state management")."""

    core_principles: tuple[str, ...] = field(default_factory=tuple)
    """Fundamental principles underlying this topic."""

    key_patterns: tuple[str, ...] = field(default_factory=tuple)
    """Recommended patterns and approaches."""

    anti_patterns: tuple[str, ...] = field(default_factory=tuple)
    """What to avoid (from dead_ends)."""

    confidence: float = 0.8
    """Confidence in this model (0-1)."""

    source_learning_count: int = 0
    """Number of learnings this model synthesizes."""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this model was created."""

    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this model was last updated."""

    def to_prompt(self) -> str:
        """Convert to prompt-friendly format for injection.

        This is the key benefit of mental models: they provide
        a single coherent context instead of multiple learnings.
        """
        parts = [
            f"# Mental Model: {self.topic}",
            "",
            "## Core Principles",
        ]
        for principle in self.core_principles:
            parts.append(f"- {principle}")

        if self.key_patterns:
            parts.extend(["", "## Key Patterns"])
            for pattern in self.key_patterns:
                parts.append(f"- {pattern}")

        if self.anti_patterns:
            parts.extend(["", "## Anti-Patterns (Avoid)"])
            for anti in self.anti_patterns:
                parts.append(f"- {anti}")

        parts.append("")
        parts.append(f"(Confidence: {self.confidence:.1%}, based on {self.source_learning_count} learnings)")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Serialize mental model."""
        return {
            "id": self.id,
            "topic": self.topic,
            "core_principles": list(self.core_principles),
            "key_patterns": list(self.key_patterns),
            "anti_patterns": list(self.anti_patterns),
            "confidence": self.confidence,
            "source_learning_count": self.source_learning_count,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MentalModel":
        """Deserialize mental model."""
        return cls(
            id=data["id"],
            topic=data["topic"],
            core_principles=tuple(data.get("core_principles", [])),
            key_patterns=tuple(data.get("key_patterns", [])),
            anti_patterns=tuple(data.get("anti_patterns", [])),
            confidence=data.get("confidence", 0.8),
            source_learning_count=data.get("source_learning_count", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
        )

    def estimate_token_count(self) -> int:
        """Estimate token count for this mental model.

        Rough estimate: ~0.75 tokens per character for English text.
        """
        prompt = self.to_prompt()
        return int(len(prompt) * 0.75)


@dataclass(slots=True)
class PatternCluster:
    """A cluster of related patterns/constraints.

    Used internally by the reflector to group learnings
    before generating reflections.
    """

    theme: str
    """Common theme in this cluster."""

    learning_ids: list[str] = field(default_factory=list)
    """Learning IDs in this cluster."""

    coherence_score: float = 0.0
    """How coherent this cluster is (0-1)."""

    def add_learning(self, learning_id: str) -> None:
        """Add a learning to this cluster."""
        if learning_id not in self.learning_ids:
            self.learning_ids.append(learning_id)

    def __len__(self) -> int:
        """Number of learnings in cluster."""
        return len(self.learning_ids)
