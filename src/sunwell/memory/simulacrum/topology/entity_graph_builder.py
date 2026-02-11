"""Entity graph builder for Phase 2: Graph Enhancement.

Constructs entity graphs from learnings:
- Creates EntityNode instances for extracted entities
- Creates MENTIONS edges from learnings to entities
- Creates CO_OCCURS edges between co-occurring entities
- Creates ALIAS_OF edges for entity aliases

Integrates with UnifiedMemoryStore and EntityIntegration.
"""

import hashlib
import logging
from typing import TYPE_CHECKING

from sunwell.memory.simulacrum.topology.entity_node import EntityNode
from sunwell.memory.simulacrum.topology.topology_base import ConceptEdge, RelationType

if TYPE_CHECKING:
    from datetime import datetime

    from sunwell.memory.core.entities import Entity
    from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore

logger = logging.getLogger(__name__)


class EntityGraphBuilder:
    """Builds entity graphs from learnings.

    Listens to learning events and constructs an entity graph
    in the UnifiedMemoryStore, creating:
    - EntityNode instances for entities
    - MENTIONS edges (learning → entity)
    - CO_OCCURS edges (entity ↔ entity)
    - ALIAS_OF edges (alias → canonical)
    """

    def __init__(self, unified_store: UnifiedMemoryStore):
        """Initialize entity graph builder.

        Args:
            unified_store: UnifiedMemoryStore to add entity nodes to
        """
        self.unified_store = unified_store
        self._entity_cache: dict[str, EntityNode] = {}

    def add_entity_to_graph(
        self,
        entity: Entity,
        learning_id: str,
    ) -> EntityNode:
        """Add an entity to the graph or update existing.

        Args:
            entity: Entity to add
            learning_id: Learning that mentions this entity

        Returns:
            EntityNode (new or updated)
        """
        # Check if entity already exists
        existing = self.unified_store.get_node(entity.entity_id)

        if existing and isinstance(existing, EntityNode):
            # Update existing entity
            entity_node = existing.with_mention(learning_id)
        else:
            # Create new entity node
            entity_node = EntityNode(
                id=entity.entity_id,
                content=f"Entity: {entity.canonical_name}",
                entity_type=entity.entity_type,
                canonical_name=entity.canonical_name,
                aliases=entity.aliases,
                mention_count=1,
                related_learnings=(learning_id,),
            )

        # Add/update in unified store
        self.unified_store.add_node(entity_node)

        # Cache for co-occurrence tracking
        self._entity_cache[entity.entity_id] = entity_node

        return entity_node

    def add_mention_edge(
        self,
        learning_id: str,
        entity_id: str,
        mention_text: str = "",
        confidence: float = 1.0,
    ) -> ConceptEdge:
        """Create MENTIONS edge from learning to entity.

        Args:
            learning_id: Learning ID
            entity_id: Entity ID
            mention_text: Text where entity was mentioned
            confidence: Confidence of the mention

        Returns:
            Created ConceptEdge
        """
        from datetime import datetime

        edge = ConceptEdge(
            source_id=learning_id,
            target_id=entity_id,
            relation=RelationType.MENTIONS,
            confidence=confidence,
            evidence=f"Mentioned as: {mention_text}" if mention_text else "",
            auto_extracted=True,
            timestamp=datetime.now().isoformat(),
        )

        # Add to graph
        self.unified_store._concept_graph.add_edge(edge)

        return edge

    def add_cooccurrence_edge(
        self,
        entity_id1: str,
        entity_id2: str,
        weight: int = 1,
    ) -> ConceptEdge:
        """Create or update CO_OCCURS edge between entities.

        Args:
            entity_id1: First entity ID
            entity_id2: Second entity ID
            weight: Co-occurrence count

        Returns:
            Created ConceptEdge
        """
        from datetime import datetime

        # Ensure consistent ordering
        if entity_id1 > entity_id2:
            entity_id1, entity_id2 = entity_id2, entity_id1

        # Check if edge already exists
        existing_edges = self.unified_store._concept_graph.get_outgoing(
            entity_id1,
            RelationType.CO_OCCURS,
        )
        existing = next(
            (e for e in existing_edges if e.target_id == entity_id2),
            None,
        )

        if existing:
            # Update weight (encoded in confidence)
            new_confidence = min(1.0, existing.confidence + 0.1)
            edge = ConceptEdge(
                source_id=entity_id1,
                target_id=entity_id2,
                relation=RelationType.CO_OCCURS,
                confidence=new_confidence,
                evidence=f"Co-occurred {int(new_confidence * 10)} times",
                auto_extracted=True,
                timestamp=datetime.now().isoformat(),
            )
        else:
            # Create new edge
            edge = ConceptEdge(
                source_id=entity_id1,
                target_id=entity_id2,
                relation=RelationType.CO_OCCURS,
                confidence=0.1 * weight,  # Weight encoded in confidence
                evidence=f"Co-occurred {weight} times",
                auto_extracted=True,
                timestamp=datetime.now().isoformat(),
            )

        # Add to graph (will handle bidirectional automatically)
        self.unified_store._concept_graph.add_edge(edge)

        return edge

    def add_alias_edge(
        self,
        alias_entity_id: str,
        canonical_entity_id: str,
    ) -> ConceptEdge:
        """Create ALIAS_OF edge from alias to canonical entity.

        Args:
            alias_entity_id: Alias entity ID
            canonical_entity_id: Canonical entity ID

        Returns:
            Created ConceptEdge
        """
        from datetime import datetime

        edge = ConceptEdge(
            source_id=alias_entity_id,
            target_id=canonical_entity_id,
            relation=RelationType.ALIAS_OF,
            confidence=1.0,
            evidence="Resolved to canonical form",
            auto_extracted=True,
            timestamp=datetime.now().isoformat(),
        )

        # Add to graph
        self.unified_store._concept_graph.add_edge(edge)

        return edge

    def process_learning(
        self,
        learning_id: str,
        entities: list[Entity],
    ) -> None:
        """Process a learning and its entities to build the graph.

        Args:
            learning_id: Learning ID
            entities: List of entities extracted from the learning
        """
        # Add entities to graph
        entity_nodes = []
        for entity in entities:
            entity_node = self.add_entity_to_graph(entity, learning_id)
            entity_nodes.append(entity_node)

            # Create MENTIONS edge
            self.add_mention_edge(learning_id, entity.entity_id, confidence=entity.confidence)

        # Create CO_OCCURS edges for entity pairs
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                self.add_cooccurrence_edge(
                    entities[i].entity_id,
                    entities[j].entity_id,
                )

    def get_cooccurring_entities(
        self,
        entity_id: str,
        min_weight: int = 2,
        limit: int = 10,
    ) -> list[tuple[EntityNode, int]]:
        """Get entities that co-occur with the given entity.

        Args:
            entity_id: Entity ID to find co-occurrences for
            min_weight: Minimum co-occurrence weight (confidence * 10)
            limit: Maximum results

        Returns:
            List of (EntityNode, weight) tuples sorted by weight
        """
        # Get CO_OCCURS edges
        edges = self.unified_store._concept_graph.get_outgoing(
            entity_id,
            RelationType.CO_OCCURS,
        )

        # Filter by weight and get entity nodes
        results = []
        for edge in edges:
            weight = int(edge.confidence * 10)
            if weight >= min_weight:
                entity_node = self.unified_store.get_node(edge.target_id)
                if entity_node and isinstance(entity_node, EntityNode):
                    results.append((entity_node, weight))

        # Sort by weight and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_entities_by_learning(self, learning_id: str) -> list[EntityNode]:
        """Get all entities mentioned in a learning.

        Args:
            learning_id: Learning ID

        Returns:
            List of EntityNode instances
        """
        # Get MENTIONS edges from learning
        edges = self.unified_store._concept_graph.get_outgoing(
            learning_id,
            RelationType.MENTIONS,
        )

        # Get entity nodes
        entities = []
        for edge in edges:
            entity_node = self.unified_store.get_node(edge.target_id)
            if entity_node and isinstance(entity_node, EntityNode):
                entities.append(entity_node)

        return entities

    def stats(self) -> dict:
        """Get entity graph statistics.

        Returns:
            Dict with entity graph stats
        """
        # Count entity nodes
        entity_nodes = [
            node
            for node in self.unified_store._nodes.values()
            if isinstance(node, EntityNode)
        ]

        # Count edges by type
        mentions_count = 0
        cooccurs_count = 0
        alias_of_count = 0

        for edges in self.unified_store._concept_graph._edges.values():
            for edge in edges:
                if edge.relation == RelationType.MENTIONS:
                    mentions_count += 1
                elif edge.relation == RelationType.CO_OCCURS:
                    cooccurs_count += 1
                elif edge.relation == RelationType.ALIAS_OF:
                    alias_of_count += 1

        # Count by entity type
        type_counts = {}
        for node in entity_nodes:
            entity_type = node.entity_type.value
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

        return {
            "total_entities": len(entity_nodes),
            "mentions_edges": mentions_count,
            "cooccurs_edges": cooccurs_count // 2,  # Bidirectional
            "alias_of_edges": alias_of_count,
            "by_type": type_counts,
        }
