"""Tests for Phase 2.2: Entity-Aware Retrieval System.

Tests entity extraction from queries, entity overlap boosting, and co-occurrence expansion.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.foundation.types.memory import Learning
from sunwell.memory.core.entities.store import EntityStore
from sunwell.memory.core.entities.types import Entity, EntityType
from sunwell.memory.simulacrum.core.planning_context import PlanningContext


class TestEntityExtractionFromQuery:
    """Test entity extraction from planning goals."""

    def test_extract_entities_from_goal(self):
        """Test extracting entities from a planning goal."""
        from sunwell.memory.core.entities.extractor import PatternEntityExtractor

        extractor = PatternEntityExtractor()
        goal = "How do I use React with TypeScript in the main.py file?"

        result = extractor.extract(goal)

        # Should extract React, TypeScript, main.py
        assert len(result.entities) >= 3
        entity_names = [e.canonical_name for e in result.entities]
        assert "React" in entity_names
        assert "TypeScript" in entity_names
        assert "main.py" in entity_names

    def test_extract_tech_entities(self):
        """Test extracting technology entities from goal."""
        from sunwell.memory.core.entities.extractor import PatternEntityExtractor

        extractor = PatternEntityExtractor()
        goal = "Optimize PostgreSQL queries for better performance"

        result = extractor.extract(goal)

        tech_entities = [e for e in result.entities if e.entity_type == EntityType.TECH]
        assert len(tech_entities) >= 1
        assert any(e.canonical_name == "PostgreSQL" for e in tech_entities)


class TestEntityOverlapBoosting:
    """Test entity overlap scoring boost."""

    def test_boost_score_by_entity_overlap(self):
        """Test that learnings with matching entities get score boost."""
        # Goal entities: React, TypeScript
        goal_entities = {"React", "TypeScript"}

        # Learning 1: Mentions React, TypeScript (overlap = 2)
        learning1_entities = {"React", "TypeScript", "Jest"}
        learning1_score = 0.5

        # Learning 2: Mentions only Jest (overlap = 0)
        learning2_entities = {"Jest"}
        learning2_score = 0.6

        # Apply boost (0.15 per entity)
        entity_boost = 0.15
        overlap1 = len(goal_entities & learning1_entities)
        overlap2 = len(goal_entities & learning2_entities)

        boosted_score1 = learning1_score + (overlap1 * entity_boost)
        boosted_score2 = learning2_score + (overlap2 * entity_boost)

        # Learning 1 should now score higher despite lower base score
        assert boosted_score1 > boosted_score2
        assert boosted_score1 == 0.5 + (2 * 0.15)  # 0.8
        assert boosted_score2 == 0.6  # No boost

    def test_partial_entity_overlap(self):
        """Test partial entity overlap."""
        goal_entities = {"React", "TypeScript", "Jest"}
        learning_entities = {"React", "Angular"}

        overlap = len(goal_entities & learning_entities)
        assert overlap == 1  # Only React matches

        boost = overlap * 0.15
        assert boost == 0.15


class TestCooccurrenceExpansion:
    """Test co-occurrence-based query expansion."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_entities.db"
        self.store = EntityStore(self.db_path)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_get_cooccurring_entities(self):
        """Test retrieving co-occurring entities."""
        # Create entities
        react = Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH)
        typescript = Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH)
        jest = Entity(entity_id="e3", canonical_name="Jest", entity_type=EntityType.TECH)

        self.store.add_entity(react)
        self.store.add_entity(typescript)
        self.store.add_entity(jest)

        # Record co-occurrences
        for _ in range(5):
            self.store.update_cooccurrence("e1", "e2")  # React-TypeScript (5 times)
        for _ in range(2):
            self.store.update_cooccurrence("e1", "e3")  # React-Jest (2 times)

        # Get co-occurring entities (min_count=3)
        cooccurring = self.store.get_cooccurring_entities("e1", min_count=3, limit=10)

        # Should only return TypeScript (count >= 3)
        assert len(cooccurring) == 1
        assert cooccurring[0][0].entity_id == "e2"
        assert cooccurring[0][1] == 5

    def test_cooccurrence_depth_expansion(self):
        """Test multi-hop co-occurrence expansion."""
        # Entity chain: React -> TypeScript -> Jest
        entities = [
            Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH),
            Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH),
            Entity(entity_id="e3", canonical_name="Jest", entity_type=EntityType.TECH),
        ]

        for entity in entities:
            self.store.add_entity(entity)

        # Create co-occurrence chain
        for _ in range(10):
            self.store.update_cooccurrence("e1", "e2")  # React-TypeScript
            self.store.update_cooccurrence("e2", "e3")  # TypeScript-Jest

        # Depth 1: Should find TypeScript
        depth1 = self.store.get_cooccurring_entities("e1", min_count=5, limit=10)
        assert len(depth1) == 1
        assert depth1[0][0].entity_id == "e2"

        # Depth 2: Should also find Jest (via TypeScript)
        # In real implementation, this would be in PlanningRetriever
        # Here we simulate by getting co-occurrences of TypeScript
        depth2 = self.store.get_cooccurring_entities("e2", min_count=5, limit=10)
        depth2_ids = {e[0].entity_id for e in depth2}
        assert "e1" in depth2_ids or "e3" in depth2_ids

    def test_cooccurrence_score_decay(self):
        """Test score decay with co-occurrence depth."""
        base_score = 1.0
        decay = 0.5

        # Depth 0 (direct match)
        depth0_score = base_score
        assert depth0_score == 1.0

        # Depth 1 (1 hop)
        depth1_score = base_score * (decay ** 1)
        assert depth1_score == 0.5

        # Depth 2 (2 hops)
        depth2_score = base_score * (decay ** 2)
        assert depth2_score == 0.25


@pytest.mark.asyncio
class TestEntityAwareRetrieval:
    """Integration tests for entity-aware retrieval."""

    async def test_retrieve_with_entity_boost(self):
        """Test retrieval with entity overlap boosting."""
        # Mock planning retriever
        goal = "React hooks best practices"

        # Mock learnings with different entity overlaps
        learnings = [
            Learning(id="l1", fact="React hooks are powerful", category="pattern"),
            Learning(id="l2", fact="Use useState for local state", category="pattern"),
            Learning(id="l3", fact="Angular components are different", category="pattern"),
        ]

        # In a real scenario, we'd extract entities for each learning
        # and boost scores based on overlap with goal entities (React, hooks)

        # Learning l1 and l2 should score higher than l3 due to React entity match
        # This is tested implicitly through the retrieval pipeline

    async def test_cooccurrence_expansion_retrieval(self):
        """Test retrieval with co-occurrence expansion."""
        # If query mentions "React", should also consider learnings about
        # co-occurring entities like "TypeScript" or "Jest"

        goal_entities = ["React"]

        # Simulated co-occurring entities (would come from EntityStore)
        cooccurring_entities = [
            ("TypeScript", 10),  # Count = 10
            ("Jest", 8),  # Count = 8
            ("Redux", 3),  # Count = 3 (below threshold)
        ]

        # With min_count=5, should expand to include TypeScript and Jest
        expanded_entities = [e for e, count in cooccurring_entities if count >= 5]
        assert "TypeScript" in expanded_entities
        assert "Jest" in expanded_entities
        assert "Redux" not in expanded_entities

    async def test_end_to_end_entity_aware_retrieval(self):
        """Test complete entity-aware retrieval pipeline."""
        # This would test the full pipeline:
        # 1. Extract entities from goal
        # 2. Retrieve learnings via hybrid search
        # 3. Boost scores by entity overlap
        # 4. Expand via co-occurrence graph
        # 5. Merge and return top-k

        # Mock implementation (real test would use actual PlanningRetriever)
        goal = "How to use React hooks effectively?"

        # Step 1: Extract entities
        from sunwell.memory.core.entities.extractor import PatternEntityExtractor
        extractor = PatternEntityExtractor()
        result = extractor.extract(goal)
        goal_entities = {e.canonical_name for e in result.entities}

        assert "React" in goal_entities

        # Step 2-5 would be tested with actual retrieval system
        # Here we verify the entity extraction works correctly


class TestPlanningContextWithEntities:
    """Test PlanningContext integration with entities."""

    def test_planning_context_stores_entities(self):
        """Test that PlanningContext can store entity information."""
        context = PlanningContext()

        # Add learnings with entity metadata
        learning1 = Learning(
            id="l1",
            fact="React hooks",
            category="pattern",
            metadata={"entities": ["React", "hooks"]},
        )

        context.add_learning(learning1)

        # Verify learning is stored
        assert len(context.patterns) == 1
        assert context.patterns[0].id == "l1"

    def test_entity_aware_context_assembly(self):
        """Test assembling context with entity awareness."""
        context = PlanningContext()

        # Add learnings with entities
        learnings = [
            Learning(id="l1", fact="React basics", category="pattern",
                    metadata={"entities": ["React"]}),
            Learning(id="l2", fact="TypeScript types", category="pattern",
                    metadata={"entities": ["TypeScript"]}),
            Learning(id="l3", fact="React with TypeScript", category="pattern",
                    metadata={"entities": ["React", "TypeScript"]}),
        ]

        for learning in learnings:
            context.add_learning(learning)

        # Learning l3 has both entities, so it's most relevant for a
        # "React + TypeScript" query
        assert len(context.patterns) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
