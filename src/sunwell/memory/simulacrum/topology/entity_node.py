"""Entity nodes for the multi-topology memory system.

Entity nodes represent extractable concepts (files, technologies, concepts, etc.)
and enable entity-aware retrieval and co-occurrence analysis.

Part of Phase 2: Graph Enhancement.
"""

from dataclasses import dataclass, field

from sunwell.memory.core.entities.types import EntityType
from sunwell.memory.simulacrum.topology.memory_node import MemoryNode


@dataclass(slots=True)
class EntityNode(MemoryNode):
    """Entity node extending MemoryNode with entity-specific fields.

    Represents an entity (file, tech, concept, person, symbol) in the
    multi-topology memory system. Enables entity-aware retrieval and
    co-occurrence analysis.

    Entity nodes are connected to:
    - Learnings via MENTIONS edges (learning → entity)
    - Other entities via CO_OCCURS edges (entity ↔ entity)
    - Canonical entities via ALIAS_OF edges (alias → canonical)
    """

    entity_type: EntityType = EntityType.CONCEPT
    """Type of entity (file, tech, concept, person, symbol)."""

    canonical_name: str = ""
    """Canonical/normalized name for this entity."""

    aliases: tuple[str, ...] = field(default_factory=tuple)
    """Alternative names for this entity."""

    mention_count: int = 0
    """Number of times this entity has been mentioned."""

    related_learnings: tuple[str, ...] = field(default_factory=tuple)
    """Learning IDs that mention this entity."""

    def summary(self) -> str:
        """Generate human-readable summary of entity node."""
        parts = [
            f"[Entity: {self.entity_type.value}]",
            self.canonical_name,
        ]

        if self.aliases:
            parts.append(f"(aliases: {', '.join(self.aliases[:3])})")

        if self.mention_count:
            parts.append(f"({self.mention_count} mentions)")

        return " ".join(parts)

    def to_dict(self) -> dict:
        """Serialize entity node for storage."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "node_type": "entity",  # Discriminator for deserialization
                "entity_type": self.entity_type.value,
                "canonical_name": self.canonical_name,
                "aliases": list(self.aliases),
                "mention_count": self.mention_count,
                "related_learnings": list(self.related_learnings),
            }
        )
        return base_dict

    @classmethod
    def from_dict(cls, data: dict) -> EntityNode:
        """Deserialize entity node from storage."""
        # Get base MemoryNode fields
        base_node = super().from_dict(data)

        return cls(
            id=base_node.id,
            content=base_node.content,
            chunk=base_node.chunk,
            spatial=base_node.spatial,
            section=base_node.section,
            facets=base_node.facets,
            outgoing_edges=base_node.outgoing_edges,
            incoming_edges=base_node.incoming_edges,
            created_at=base_node.created_at,
            updated_at=base_node.updated_at,
            embedding=base_node.embedding,
            # Entity-specific fields
            entity_type=EntityType(data["entity_type"]),
            canonical_name=data.get("canonical_name", ""),
            aliases=tuple(data.get("aliases", [])),
            mention_count=data.get("mention_count", 0),
            related_learnings=tuple(data.get("related_learnings", [])),
        )

    def with_mention(self, learning_id: str) -> EntityNode:
        """Return a new EntityNode with incremented mention count and added learning."""
        return EntityNode(
            id=self.id,
            content=self.content,
            chunk=self.chunk,
            spatial=self.spatial,
            section=self.section,
            facets=self.facets,
            outgoing_edges=self.outgoing_edges,
            incoming_edges=self.incoming_edges,
            created_at=self.created_at,
            updated_at=self.updated_at,
            embedding=self.embedding,
            entity_type=self.entity_type,
            canonical_name=self.canonical_name,
            aliases=self.aliases,
            mention_count=self.mention_count + 1,
            related_learnings=(
                *self.related_learnings,
                learning_id,
            ) if learning_id not in self.related_learnings else self.related_learnings,
        )
