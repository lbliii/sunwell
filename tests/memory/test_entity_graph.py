"""Tests for Phase 2.1: Entity Graph System.

Tests entity graph construction, co-occurrence tracking, and graph operations.
"""

import pytest

from sunwell.foundation.types.memory import Learning
from sunwell.memory.core.entities.types import Entity, EntityMention, EntityType
from sunwell.memory.simulacrum.topology.entity_graph_builder import EntityGraphBuilder
from sunwell.memory.simulacrum.topology.entity_node import EntityNode
from sunwell.memory.simulacrum.topology.topology_base import RelationType


class TestEntityNode:
    """Test entity node creation and properties."""

    def test_create_entity_node(self):
        """Test creating an entity node."""
        node = EntityNode(
            node_id="e1",
            entity_type="TECH",
            canonical_name="React",
            aliases=("ReactJS", "react.js"),
            mention_count=5,
            related_learnings=("l1", "l2"),
        )

        assert node.node_id == "e1"
        assert node.entity_type == "TECH"
        assert node.canonical_name == "React"
        assert "ReactJS" in node.aliases
        assert node.mention_count == 5
        assert len(node.related_learnings) == 2

    def test_entity_node_metadata(self):
        """Test entity node metadata."""
        node = EntityNode(
            node_id="e1",
            entity_type="FILE",
            canonical_name="main.py",
            aliases=(),
            mention_count=3,
            related_learnings=(),
        )

        metadata = node.to_dict()
        assert metadata["entity_type"] == "FILE"
        assert metadata["canonical_name"] == "main.py"
        assert metadata["mention_count"] == 3


class TestEntityGraphBuilder:
    """Test entity graph construction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = EntityGraphBuilder()

    def test_add_entity_to_graph(self):
        """Test adding an entity to the graph."""
        entity = Entity(
            entity_id="e1",
            canonical_name="React",
            entity_type=EntityType.TECH,
            aliases=("ReactJS",),
            mention_count=5,
        )

        node = self.builder.add_entity_to_graph(entity, related_learnings=["l1", "l2"])

        assert node.node_id == "e1"
        assert node.canonical_name == "React"
        assert node.entity_type == "TECH"
        assert len(node.related_learnings) == 2

    def test_add_mention_edge(self):
        """Test adding mention edge between learning and entity."""
        entity = Entity(
            entity_id="e1",
            canonical_name="React",
            entity_type=EntityType.TECH,
        )

        learning_id = "l1"

        # Add entity and learning
        entity_node = self.builder.add_entity_to_graph(entity, related_learnings=[learning_id])

        # Add mention edge
        self.builder.add_mention_edge(learning_id, "e1", confidence=0.9)

        # Verify edge exists
        edges = self.builder.get_edges_from_node(learning_id)
        mention_edges = [e for e in edges if e["type"] == RelationType.MENTIONS]
        assert len(mention_edges) == 1
        assert mention_edges[0]["target"] == "e1"
        assert mention_edges[0]["weight"] == 0.9

    def test_add_cooccurrence_edge(self):
        """Test adding co-occurrence edge between entities."""
        entity1 = Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH)
        entity2 = Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH)

        self.builder.add_entity_to_graph(entity1, related_learnings=[])
        self.builder.add_entity_to_graph(entity2, related_learnings=[])

        # Add co-occurrence edge
        self.builder.add_cooccurrence_edge("e1", "e2", count=3)

        # Verify bidirectional edges
        edges_from_e1 = self.builder.get_edges_from_node("e1")
        edges_from_e2 = self.builder.get_edges_from_node("e2")

        cooccur_from_e1 = [e for e in edges_from_e1 if e["type"] == RelationType.CO_OCCURS]
        cooccur_from_e2 = [e for e in edges_from_e2 if e["type"] == RelationType.CO_OCCURS]

        assert len(cooccur_from_e1) == 1
        assert cooccur_from_e1[0]["target"] == "e2"
        assert cooccur_from_e1[0]["weight"] == 3

        assert len(cooccur_from_e2) == 1
        assert cooccur_from_e2[0]["target"] == "e1"
        assert cooccur_from_e2[0]["weight"] == 3

    def test_process_learning_integration(self):
        """Test processing a learning to extract entities and build graph."""
        learning = Learning(
            id="l1",
            fact="Use React with TypeScript for the main.py component",
            category="pattern",
        )

        entities = [
            Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH),
            Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH),
            Entity(entity_id="e3", canonical_name="main.py", entity_type=EntityType.FILE),
        ]

        mentions = [
            EntityMention(learning_id="l1", entity_id="e1", mention_text="React", confidence=0.9),
            EntityMention(learning_id="l1", entity_id="e2", mention_text="TypeScript", confidence=0.9),
            EntityMention(learning_id="l1", entity_id="e3", mention_text="main.py", confidence=0.95),
        ]

        # Process learning
        self.builder.process_learning(learning, entities, mentions)

        # Verify entities added
        for entity in entities:
            node = self.builder.get_node(entity.entity_id)
            assert node is not None
            assert node.canonical_name == entity.canonical_name

        # Verify mention edges
        edges_from_learning = self.builder.get_edges_from_node("l1")
        mention_edges = [e for e in edges_from_learning if e["type"] == RelationType.MENTIONS]
        assert len(mention_edges) == 3

        # Verify co-occurrence edges (should exist between e1-e2, e1-e3, e2-e3)
        edges_from_e1 = self.builder.get_edges_from_node("e1")
        cooccur_edges = [e for e in edges_from_e1 if e["type"] == RelationType.CO_OCCURS]
        assert len(cooccur_edges) == 2  # e1 co-occurs with e2 and e3

    def test_update_cooccurrence_count(self):
        """Test updating co-occurrence count for existing edge."""
        entity1 = Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH)
        entity2 = Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH)

        self.builder.add_entity_to_graph(entity1, related_learnings=[])
        self.builder.add_entity_to_graph(entity2, related_learnings=[])

        # Add co-occurrence edge (count=1)
        self.builder.add_cooccurrence_edge("e1", "e2", count=1)

        # Update co-occurrence (count=2)
        self.builder.add_cooccurrence_edge("e1", "e2", count=2)

        # Verify updated count
        edges = self.builder.get_edges_from_node("e1")
        cooccur = [e for e in edges if e["type"] == RelationType.CO_OCCURS and e["target"] == "e2"]
        assert len(cooccur) == 1
        assert cooccur[0]["weight"] == 2

    def test_get_cooccurring_entities(self):
        """Test retrieving co-occurring entities."""
        # Create entity graph
        entities = [
            Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH),
            Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH),
            Entity(entity_id="e3", canonical_name="Jest", entity_type=EntityType.TECH),
        ]

        for entity in entities:
            self.builder.add_entity_to_graph(entity, related_learnings=[])

        # Add co-occurrences: e1-e2 (count=5), e1-e3 (count=2)
        self.builder.add_cooccurrence_edge("e1", "e2", count=5)
        self.builder.add_cooccurrence_edge("e1", "e3", count=2)

        # Get co-occurring entities for e1
        cooccurring = self.builder.get_cooccurring_entities("e1", min_count=3)

        # Should only return e2 (count >= 3)
        assert len(cooccurring) == 1
        assert cooccurring[0][0].node_id == "e2"
        assert cooccurring[0][1] == 5  # Count

    def test_graph_traversal(self):
        """Test graph traversal from entity to learnings."""
        # Create entity
        entity = Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH)
        self.builder.add_entity_to_graph(entity, related_learnings=["l1", "l2", "l3"])

        # Add mention edges
        self.builder.add_mention_edge("l1", "e1", confidence=0.9)
        self.builder.add_mention_edge("l2", "e1", confidence=0.8)
        self.builder.add_mention_edge("l3", "e1", confidence=0.95)

        # Get entity node
        node = self.builder.get_node("e1")
        assert len(node.related_learnings) == 3

        # Verify we can traverse back to learnings
        edges = self.builder.get_edges_to_node("e1")
        mention_edges = [e for e in edges if e["type"] == RelationType.MENTIONS]
        assert len(mention_edges) == 3


class TestEntityGraphIntegration:
    """Integration tests for entity graph system."""

    def test_end_to_end_graph_construction(self):
        """Test complete graph construction from learnings."""
        builder = EntityGraphBuilder()

        # Learning 1: React + TypeScript
        learning1 = Learning(id="l1", fact="Use React with TypeScript", category="pattern")
        entities1 = [
            Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH),
            Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH),
        ]
        mentions1 = [
            EntityMention(learning_id="l1", entity_id="e1", mention_text="React", confidence=0.9),
            EntityMention(learning_id="l1", entity_id="e2", mention_text="TypeScript", confidence=0.9),
        ]

        # Learning 2: React + Jest
        learning2 = Learning(id="l2", fact="Test React with Jest", category="pattern")
        entities2 = [
            Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH),
            Entity(entity_id="e3", canonical_name="Jest", entity_type=EntityType.TECH),
        ]
        mentions2 = [
            EntityMention(learning_id="l2", entity_id="e1", mention_text="React", confidence=0.9),
            EntityMention(learning_id="l2", entity_id="e3", mention_text="Jest", confidence=0.9),
        ]

        # Process learnings
        builder.process_learning(learning1, entities1, mentions1)
        builder.process_learning(learning2, entities2, mentions2)

        # Verify graph structure
        react_node = builder.get_node("e1")
        assert react_node.mention_count == 2  # Mentioned in both learnings

        # Verify co-occurrences
        cooccurring = builder.get_cooccurring_entities("e1", min_count=1)
        assert len(cooccurring) == 2  # TypeScript and Jest

        # Verify we can find learnings via entities
        assert "l1" in react_node.related_learnings
        assert "l2" in react_node.related_learnings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
