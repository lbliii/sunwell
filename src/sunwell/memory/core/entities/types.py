"""Entity types and schemas for Phase 1: Entity Extraction.

Entities represent extractable concepts from learnings:
- FILE: File paths, directories
- TECH: Technologies, frameworks, libraries
- CONCEPT: Domain concepts, abstractions
- PERSON: Names, roles
- SYMBOL: Code symbols (classes, functions)

Part of Hindsight-inspired memory enhancements (RFC-XXX).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class EntityType(Enum):
    """Types of entities that can be extracted."""

    FILE = "file"  # File paths, directories
    TECH = "tech"  # Technologies, frameworks, libraries
    CONCEPT = "concept"  # Domain concepts, abstractions
    PERSON = "person"  # Names, roles, user identifiers
    SYMBOL = "symbol"  # Code symbols (classes, functions, variables)


@dataclass(slots=True, frozen=True)
class Entity:
    """An entity extracted from learnings.

    Entities are normalized and deduplicated across learnings.
    They enable entity-aware retrieval and co-occurrence graphs.

    Attributes:
        entity_id: Unique identifier (hash of canonical_name + type)
        canonical_name: Normalized name (e.g., "ReactJS" for "React")
        entity_type: Type of entity
        aliases: Alternative names for this entity
        first_seen: When first extracted
        mention_count: Number of times mentioned across learnings
        confidence: Extraction confidence (0-1)
    """

    entity_id: str
    canonical_name: str
    entity_type: EntityType
    aliases: tuple[str, ...] = field(default_factory=tuple)
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    mention_count: int = 0
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type.value,
            "aliases": list(self.aliases),
            "first_seen": self.first_seen,
            "mention_count": self.mention_count,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Entity:
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            canonical_name=data["canonical_name"],
            entity_type=EntityType(data["entity_type"]),
            aliases=tuple(data.get("aliases", [])),
            first_seen=data.get("first_seen", datetime.now().isoformat()),
            mention_count=data.get("mention_count", 0),
            confidence=data.get("confidence", 1.0),
        )

    def with_mention(self) -> Entity:
        """Return a new entity with incremented mention count."""
        return Entity(
            entity_id=self.entity_id,
            canonical_name=self.canonical_name,
            entity_type=self.entity_type,
            aliases=self.aliases,
            first_seen=self.first_seen,
            mention_count=self.mention_count + 1,
            confidence=self.confidence,
        )

    def with_alias(self, alias: str) -> Entity:
        """Return a new entity with an additional alias."""
        if alias in self.aliases or alias == self.canonical_name:
            return self
        return Entity(
            entity_id=self.entity_id,
            canonical_name=self.canonical_name,
            entity_type=self.entity_type,
            aliases=(*self.aliases, alias),
            first_seen=self.first_seen,
            mention_count=self.mention_count,
            confidence=self.confidence,
        )


@dataclass(slots=True)
class EntityMention:
    """A mention of an entity in a learning.

    Tracks which entities appear in which learnings for
    entity-aware retrieval and co-occurrence analysis.
    """

    learning_id: str
    entity_id: str
    mention_text: str  # Original text that matched
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "learning_id": self.learning_id,
            "entity_id": self.entity_id,
            "mention_text": self.mention_text,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class ExtractionResult:
    """Result of entity extraction from text.

    Contains extracted entities and their metadata.
    Used by both pattern-based and LLM-based extractors.
    """

    entities: list[Entity]
    mentions: list[EntityMention]
    extraction_mode: str  # "pattern" or "llm"
    confidence: float = 1.0

    def __bool__(self) -> bool:
        """Check if extraction found any entities."""
        return len(self.entities) > 0
