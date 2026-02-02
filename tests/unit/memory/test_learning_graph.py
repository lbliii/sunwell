"""Tests for learning relationship graph functionality.

Tests the LearningGraph class and its integration with ConversationDAG
for MIRA-inspired importance scoring.
"""

import pytest

from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.memory.simulacrum.core.retrieval.learning_graph import (
    LearningEdge,
    LearningGraph,
    RelationType,
    detect_relationships,
)
from sunwell.memory.simulacrum.core.turn import Learning


class TestLearningGraph:
    """Tests for the LearningGraph class."""

    def test_add_edge(self) -> None:
        """Test adding edges to the graph."""
        graph = LearningGraph()

        edge = LearningEdge(
            source_id="learning_a",
            target_id="learning_b",
            relation_type=RelationType.SUPPORTS,
            weight=0.8,
        )
        graph.add_edge(edge)

        assert graph.inbound_count("learning_b") == 1
        assert graph.outbound_count("learning_a") == 1

    def test_no_duplicate_edges(self) -> None:
        """Test that duplicate edges are not added."""
        graph = LearningGraph()

        edge = LearningEdge(
            source_id="a",
            target_id="b",
            relation_type=RelationType.SUPPORTS,
        )
        graph.add_edge(edge)
        graph.add_edge(edge)  # Duplicate

        assert graph.inbound_count("b") == 1

    def test_inbound_count(self) -> None:
        """Test inbound link counting for hub scoring."""
        graph = LearningGraph()

        # learning_hub is referenced by multiple others
        for i in range(5):
            graph.add_edge(LearningEdge(
                source_id=f"learning_{i}",
                target_id="learning_hub",
                relation_type=RelationType.SUPPORTS,
            ))

        assert graph.inbound_count("learning_hub") == 5
        assert graph.inbound_count("learning_0") == 0  # No inbound

    def test_weighted_count(self) -> None:
        """Test weighted inbound counting."""
        graph = LearningGraph()

        graph.add_edge(LearningEdge("a", "hub", RelationType.SUPPORTS, weight=1.0))
        graph.add_edge(LearningEdge("b", "hub", RelationType.RELATED, weight=0.5))

        assert graph.inbound_weighted_count("hub") == 1.5

    def test_remove_learning(self) -> None:
        """Test removing a learning and its edges."""
        graph = LearningGraph()

        graph.add_edge(LearningEdge("a", "b", RelationType.SUPPORTS))
        graph.add_edge(LearningEdge("b", "c", RelationType.DERIVES_FROM))

        graph.remove_learning("b")

        assert graph.inbound_count("b") == 0
        assert graph.outbound_count("b") == 0
        assert graph.outbound_count("a") == 0  # Edge to b was removed

    def test_get_related(self) -> None:
        """Test getting all related learnings."""
        graph = LearningGraph()

        graph.add_edge(LearningEdge("a", "center", RelationType.SUPPORTS))
        graph.add_edge(LearningEdge("center", "b", RelationType.ELABORATES))

        related = graph.get_related("center")
        assert related == {"a", "b"}

    def test_persistence(self, tmp_path) -> None:
        """Test save and load."""
        graph = LearningGraph()
        graph.add_edge(LearningEdge("a", "b", RelationType.SUPPORTS, weight=0.9))
        graph.add_edge(LearningEdge("b", "c", RelationType.CONTRADICTS))

        path = tmp_path / "graph.json"
        graph.save(path)

        loaded = LearningGraph.load(path)
        assert loaded.inbound_count("b") == 1
        assert loaded.inbound_count("c") == 1

        # Check weight preserved
        edges = loaded.get_inbound("b")
        assert len(edges) == 1
        assert edges[0].weight == 0.9


class TestDetectRelationships:
    """Tests for automatic relationship detection."""

    def test_derives_from_source_overlap(self) -> None:
        """Test that source turn overlap creates DERIVES_FROM edge."""
        existing = Learning(
            fact="The API uses REST conventions",
            source_turns=("turn_1", "turn_2"),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )

        new = Learning(
            fact="REST endpoints follow standard naming",
            source_turns=("turn_2", "turn_3"),  # Overlaps with turn_2
            confidence=0.85,
            category="fact",
            activity_day_created=2,
            activity_day_accessed=2,
        )

        edges = detect_relationships(new, [existing])
        assert len(edges) == 1
        assert edges[0].relation_type == RelationType.DERIVES_FROM

    def test_related_keyword_overlap(self) -> None:
        """Test that keyword overlap creates RELATED edge."""
        existing = Learning(
            fact="Database connection pooling uses PostgreSQL driver configuration",
            source_turns=("turn_1",),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )

        new = Learning(
            fact="PostgreSQL database connection pooling improves performance significantly",
            source_turns=("turn_5",),  # No source overlap
            confidence=0.85,
            category="preference",  # Different category
            activity_day_created=2,
            activity_day_accessed=2,
        )

        edges = detect_relationships(new, [existing])
        # Should have RELATED edge due to keyword overlap (database, connection, pooling, PostgreSQL)
        assert len(edges) >= 1
        relation_types = {e.relation_type for e in edges}
        assert RelationType.RELATED in relation_types or RelationType.SUPPORTS in relation_types

    def test_no_self_relationship(self) -> None:
        """Test that a learning doesn't relate to itself."""
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )

        edges = detect_relationships(learning, [learning])
        assert len(edges) == 0


class TestDAGLearningGraphIntegration:
    """Tests for ConversationDAG integration with LearningGraph."""

    def test_hub_learning_ranks_higher(self) -> None:
        """Test that learnings with more inbound links get higher importance scores."""
        from sunwell.memory.simulacrum.core.retrieval.importance import compute_importance

        dag = ConversationDAG()

        # Create a "hub" learning that will be referenced by others
        hub = Learning(
            fact="FastAPI is the web framework used in this project",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )
        dag.add_learning(hub, auto_detect_relationships=False)

        # Create an isolated learning with same relevance
        isolated = Learning(
            fact="Flask is an alternative web framework option",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )
        dag.add_learning(isolated, auto_detect_relationships=False)

        # Add multiple learnings that reference the hub
        for i in range(5):
            dag.learning_graph.add_edge(LearningEdge(
                source_id=f"referrer_{i}",
                target_id=hub.id,
                relation_type=RelationType.SUPPORTS,
            ))

        # Same semantic similarity for both
        hub_score = compute_importance(
            hub,
            query_similarity=0.8,
            activity_days=10,
            inbound_link_count=dag.get_inbound_link_count(hub.id),
        )
        isolated_score = compute_importance(
            isolated,
            query_similarity=0.8,
            activity_days=10,
            inbound_link_count=dag.get_inbound_link_count(isolated.id),
        )

        # Hub should rank higher due to inbound links
        assert hub_score > isolated_score
        # Verify the hub actually has more links
        assert dag.get_inbound_link_count(hub.id) == 5
        assert dag.get_inbound_link_count(isolated.id) == 0

    def test_add_learning_creates_relationships(self) -> None:
        """Test that adding learnings auto-detects relationships."""
        dag = ConversationDAG()

        # Add first learning
        learning1 = Learning(
            fact="The codebase uses Python 3.14",
            source_turns=("turn_1",),
            confidence=0.95,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )
        dag.add_learning(learning1)

        # Add second learning with overlapping source
        learning2 = Learning(
            fact="Python 3.14 enables free-threading",
            source_turns=("turn_1", "turn_2"),  # Overlaps
            confidence=0.9,
            category="fact",
            activity_day_created=2,
            activity_day_accessed=2,
        )
        dag.add_learning(learning2)

        # Check relationship was created
        assert dag.learning_graph.inbound_count(learning1.id) >= 1

    def test_get_inbound_link_count(self) -> None:
        """Test the convenience method for getting inbound links."""
        dag = ConversationDAG()

        # Create a hub learning referenced by others
        hub = Learning(
            fact="Core API design principle",
            source_turns=(),
            confidence=0.95,
            category="pattern",
            activity_day_created=1,
            activity_day_accessed=1,
        )
        dag.add_learning(hub, auto_detect_relationships=False)

        # Manually add references to hub
        dag.learning_graph.add_edge(LearningEdge(
            source_id="other_1",
            target_id=hub.id,
            relation_type=RelationType.SUPPORTS,
        ))
        dag.learning_graph.add_edge(LearningEdge(
            source_id="other_2",
            target_id=hub.id,
            relation_type=RelationType.DERIVES_FROM,
        ))

        assert dag.get_inbound_link_count(hub.id) == 2

    def test_stats_includes_learning_graph(self) -> None:
        """Test that DAG stats include learning graph info."""
        dag = ConversationDAG()

        learning = Learning(
            fact="Test",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )
        dag.add_learning(learning)

        stats = dag.stats
        assert "learning_graph" in stats
        assert "total_nodes" in stats["learning_graph"]

    def test_dag_persistence_preserves_graph(self, tmp_path) -> None:
        """Test that saving/loading DAG preserves learning graph."""
        dag = ConversationDAG()

        # Add learnings with relationships
        learning1 = Learning(
            fact="Fact one about testing",
            source_turns=("t1",),
            confidence=0.9,
            category="fact",
            activity_day_created=1,
            activity_day_accessed=1,
        )
        learning2 = Learning(
            fact="Fact two derives from testing fact",
            source_turns=("t1",),  # Same source creates relationship
            confidence=0.85,
            category="fact",
            activity_day_created=2,
            activity_day_accessed=2,
        )

        dag.add_learning(learning1)
        dag.add_learning(learning2)

        # Save and reload
        path = tmp_path / "dag.json"
        dag.save(path)
        loaded_dag = ConversationDAG.load(path)

        # Check learnings preserved
        assert len(loaded_dag.learnings) == 2

        # Check learning graph preserved
        original_edges = dag.learning_graph.stats["total_edges"]
        loaded_edges = loaded_dag.learning_graph.stats["total_edges"]
        assert loaded_edges == original_edges
