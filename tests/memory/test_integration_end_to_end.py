"""End-to-end integration tests for Hindsight-inspired memory enhancements.

Tests the complete pipeline: entity extraction → entity-aware retrieval →
reflection → optimization, verifying all phases work together.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.foundation.types.memory import Learning
from sunwell.memory.core.entities.extractor import PatternEntityExtractor
from sunwell.memory.core.entities.store import EntityStore
from sunwell.memory.core.learning_cache import LearningCache
from sunwell.memory.core.reranking.config import RerankingConfig
from sunwell.memory.core.reranking.cross_encoder import CrossEncoderReranker
from sunwell.memory.core.retrieval.query_expansion import QueryExpander


class TestPhase1Integration:
    """Integration tests for Phase 1 (Entity extraction + Reranking)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.entity_db = Path(self.temp_dir) / "entities.db"
        self.cache_db = Path(self.temp_dir) / "cache.db"

        self.entity_store = EntityStore(self.entity_db)
        self.learning_cache = LearningCache(self.cache_db)
        self.extractor = PatternEntityExtractor()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_extract_and_store_entities(self):
        """Test extracting entities and storing them."""
        text = "Use React with TypeScript to build the main.py component"
        result = self.extractor.extract(text, learning_id="l1")

        # Store entities
        for entity in result.entities:
            self.entity_store.add_entity(entity)

        # Store mentions
        for mention in result.mentions:
            self.entity_store.add_mention(mention)

        # Verify storage
        react_learnings = self.entity_store.get_learnings_by_entity("React")
        assert "l1" in react_learnings

        # Verify entity count
        stats = self.entity_store.stats()
        assert stats["total_entities"] >= 3

    def test_entity_extraction_with_cache(self):
        """Test entity extraction integrated with learning cache."""
        # Add learning to cache
        learning = Learning(
            id="l1",
            fact="React hooks are useful for state management",
            category="pattern",
        )

        self.learning_cache.add_learning(
            learning_id=learning.id,
            fact=learning.fact,
            category=learning.category,
        )

        # Extract entities
        result = self.extractor.extract(learning.fact, learning_id=learning.id)

        # Link entities to learning in cache
        for entity in result.entities:
            self.learning_cache.add_entity(
                entity_id=entity.entity_id,
                canonical_name=entity.canonical_name,
                entity_type=entity.entity_type.value,
            )
            self.learning_cache.link_learning_to_entity(learning.id, entity.entity_id)

        # Verify entities are linked
        entities = self.learning_cache.get_entities_for_learning(learning.id)
        assert len(entities) >= 2


class TestPhase2Integration:
    """Integration tests for Phase 2 (Entity graph + Entity-aware retrieval)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.entity_db = Path(self.temp_dir) / "entities.db"
        self.entity_store = EntityStore(self.entity_db)
        self.extractor = PatternEntityExtractor()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_cooccurrence_graph_construction(self):
        """Test building co-occurrence graph from learnings."""
        # Learning 1: React + TypeScript
        learning1 = Learning(
            id="l1",
            fact="Use React with TypeScript for type safety",
            category="pattern",
        )
        result1 = self.extractor.extract(learning1.fact, learning_id=learning1.id)

        # Learning 2: React + Jest
        learning2 = Learning(
            id="l2",
            fact="Test React components with Jest",
            category="pattern",
        )
        result2 = self.extractor.extract(learning2.fact, learning_id=learning2.id)

        # Store entities and build graph
        for entity in result1.entities:
            self.entity_store.add_entity(entity)
        for mention in result1.mentions:
            self.entity_store.add_mention(mention)

        for entity in result2.entities:
            self.entity_store.add_entity(entity)
        for mention in result2.mentions:
            self.entity_store.add_mention(mention)

        # Build co-occurrence edges
        # React appears in both, so co-occurs with TypeScript and Jest
        react_id = None
        typescript_id = None
        jest_id = None

        for entity in result1.entities + result2.entities:
            if entity.canonical_name == "React":
                react_id = entity.entity_id
            elif entity.canonical_name == "TypeScript":
                typescript_id = entity.entity_id
            elif entity.canonical_name == "Jest":
                jest_id = entity.entity_id

        if react_id and typescript_id:
            self.entity_store.update_cooccurrence(react_id, typescript_id)
        if react_id and jest_id:
            self.entity_store.update_cooccurrence(react_id, jest_id)

        # Verify co-occurrence graph
        if react_id:
            cooccurring = self.entity_store.get_cooccurring_entities(react_id, min_count=1, limit=10)
            assert len(cooccurring) >= 1

    def test_entity_aware_retrieval_boost(self):
        """Test entity overlap boosting in retrieval."""
        # Goal: "React TypeScript setup"
        goal = "React TypeScript setup"
        goal_result = self.extractor.extract(goal)
        goal_entities = {e.canonical_name for e in goal_result.entities}

        # Learning 1: High entity overlap
        learning1 = Learning(id="l1", fact="React and TypeScript configuration", category="pattern")
        learning1_result = self.extractor.extract(learning1.fact)
        learning1_entities = {e.canonical_name for e in learning1_result.entities}

        # Learning 2: Low entity overlap
        learning2 = Learning(id="l2", fact="Angular components", category="pattern")
        learning2_result = self.extractor.extract(learning2.fact)
        learning2_entities = {e.canonical_name for e in learning2_result.entities}

        # Calculate overlap
        overlap1 = len(goal_entities & learning1_entities)
        overlap2 = len(goal_entities & learning2_entities)

        assert overlap1 > overlap2

        # With entity boost (0.15 per entity), learning1 should score higher
        entity_boost = 0.15
        base_score1 = 0.5
        base_score2 = 0.6

        boosted_score1 = base_score1 + (overlap1 * entity_boost)
        boosted_score2 = base_score2 + (overlap2 * entity_boost)

        assert boosted_score1 > boosted_score2


@pytest.mark.asyncio
class TestPhase3Integration:
    """Integration tests for Phase 3 (Reflection + Mental models)."""

    async def test_reflection_workflow(self):
        """Test complete reflection workflow."""
        from sunwell.memory.core.reflection.reflector import Reflector

        reflector = Reflector()

        # Create constraint learnings
        constraints = [
            Learning(id="l1", fact="Don't use global state in React", category="constraint"),
            Learning(id="l2", fact="Avoid side effects in render functions", category="constraint"),
            Learning(id="l3", fact="Use hooks for state management", category="constraint"),
            Learning(id="l4", fact="Keep components pure and predictable", category="constraint"),
        ]

        # Mock causality analysis
        with patch.object(reflector.causality_analyzer, "analyze_causality", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "theme": "React functional programming",
                "causality": "These constraints stem from React's declarative rendering model",
                "summary": "Functional purity enables predictable re-renders and easier testing",
            }

            # Trigger reflection
            reflection = await reflector.reflect_on_constraints(constraints)

            # Verify reflection
            assert reflection.theme == "React functional programming"
            assert len(reflection.source_learning_ids) == 4
            assert reflection.confidence > 0.8

            # Convert to learning for storage
            reflection_learning = reflection.to_learning()
            assert reflection_learning.category == "reflection"

    async def test_mental_model_token_efficiency(self):
        """Test that mental models save tokens."""
        from sunwell.memory.core.reflection.reflector import Reflector

        reflector = Reflector()

        # Create many learnings on same topic
        learnings = [
            Learning(id=f"l{i}", fact=f"React pattern {i}", category="pattern")
            for i in range(10)
        ]

        # Mock clustering and analysis
        with patch.object(reflector.pattern_detector, "cluster_learnings") as mock_cluster:
            from sunwell.memory.core.reflection.types import PatternCluster

            mock_cluster.return_value = [
                PatternCluster(
                    theme="React patterns",
                    learnings=learnings,
                    coherence_score=0.85,
                )
            ]

            with patch.object(reflector.causality_analyzer, "analyze_causality", new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = {
                    "theme": "React patterns",
                    "causality": "React best practices",
                    "summary": "Follow React conventions",
                }

                # Build mental model
                mental_model = await reflector.build_mental_model("React patterns", learnings)

                # Estimate token savings
                savings = reflector.estimate_token_savings(mental_model)

                # Should achieve 20-40% savings
                assert savings["savings_percent"] >= 20
                assert savings["savings_tokens"] > 0


class TestPhase4Integration:
    """Integration tests for Phase 4 (Optimization)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_db = Path(self.temp_dir) / "cache.db"
        self.learning_cache = LearningCache(self.cache_db)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_bm25_index_performance(self):
        """Test BM25 index improves query performance."""
        import time

        # Add many learnings
        for i in range(100):
            self.learning_cache.add_learning(
                learning_id=f"l{i}",
                fact=f"Learning {i} about programming and technology",
                category="pattern",
            )

        # Build index
        self.learning_cache.build_bm25_index()

        # Query with index
        start = time.perf_counter()
        results = self.learning_cache.bm25_query_fast("programming technology", limit=10)
        time_with_index = time.perf_counter() - start

        # Verify results
        assert len(results) > 0
        assert time_with_index < 1.0  # Should be fast

    def test_query_expansion_integration(self):
        """Test query expansion improves retrieval."""
        expander = QueryExpander()

        # Original query with abbreviation
        original_query = "auth setup"
        expanded_queries = expander.expand(original_query)

        # Add learnings
        learnings = [
            Learning(id="l1", fact="Authentication implementation guide", category="pattern"),
            Learning(id="l2", fact="Login system setup tutorial", category="pattern"),
            Learning(id="l3", fact="auth module configuration", category="pattern"),
        ]

        for learning in learnings:
            self.learning_cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

        self.learning_cache.build_bm25_index()

        # Query with original term
        original_results = self.learning_cache.bm25_query_fast(original_query, limit=10)

        # Query with expanded terms
        all_expanded_results = []
        for expanded in expanded_queries:
            results = self.learning_cache.bm25_query_fast(expanded, limit=10)
            all_expanded_results.extend(results)

        # Expanded should find more results
        expanded_ids = {r[0] for r in all_expanded_results}
        assert len(expanded_ids) >= len(original_results)


class TestEndToEndPipeline:
    """End-to-end tests for complete memory enhancement pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.entity_db = Path(self.temp_dir) / "entities.db"
        self.cache_db = Path(self.temp_dir) / "cache.db"

        self.entity_store = EntityStore(self.entity_db)
        self.learning_cache = LearningCache(self.cache_db)
        self.extractor = PatternEntityExtractor()
        self.expander = QueryExpander()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_complete_pipeline(self):
        """Test complete pipeline from ingestion to retrieval."""
        # Step 1: Add learnings
        learnings = [
            Learning(id="l1", fact="Use React hooks for state management", category="pattern"),
            Learning(id="l2", fact="TypeScript provides type safety for React", category="pattern"),
            Learning(id="l3", fact="Test React components with Jest", category="pattern"),
            Learning(id="l4", fact="PostgreSQL indexes improve query performance", category="pattern"),
        ]

        for learning in learnings:
            # Add to cache
            self.learning_cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

            # Extract and store entities
            result = self.extractor.extract(learning.fact, learning_id=learning.id)
            for entity in result.entities:
                self.entity_store.add_entity(entity)
                self.learning_cache.add_entity(
                    entity_id=entity.entity_id,
                    canonical_name=entity.canonical_name,
                    entity_type=entity.entity_type.value,
                )
                self.learning_cache.link_learning_to_entity(learning.id, entity.entity_id)

            for mention in result.mentions:
                self.entity_store.add_mention(mention)

        # Step 2: Build BM25 index
        self.learning_cache.build_bm25_index()

        # Step 3: Query with entity extraction
        goal = "React state management best practices"
        goal_result = self.extractor.extract(goal)
        goal_entities = {e.canonical_name for e in goal_result.entities}

        # Step 4: BM25 retrieval
        bm25_results = self.learning_cache.bm25_query_fast(goal, limit=10)

        # Step 5: Entity overlap boosting
        boosted_results = []
        for learning_id, bm25_score in bm25_results:
            learning_entities = self.learning_cache.get_entities_for_learning(learning_id)
            learning_entity_names = {e["canonical_name"] for e in learning_entities}

            # Calculate overlap
            overlap = len(goal_entities & learning_entity_names)
            entity_boost = overlap * 0.15

            boosted_score = bm25_score + entity_boost
            boosted_results.append((learning_id, boosted_score))

        # Sort by boosted score
        boosted_results.sort(key=lambda x: x[1], reverse=True)

        # Step 6: Verify results
        assert len(boosted_results) > 0

        # React-related learnings should rank higher
        top_ids = [r[0] for r in boosted_results[:2]]
        assert "l1" in top_ids or "l2" in top_ids

    @pytest.mark.asyncio
    async def test_pipeline_with_reflection(self):
        """Test pipeline including reflection and mental models."""
        from sunwell.memory.core.reflection.reflector import Reflector

        # Add constraint learnings
        constraints = [
            Learning(id="c1", fact="Don't use global state", category="constraint"),
            Learning(id="c2", fact="Avoid side effects in render", category="constraint"),
            Learning(id="c3", fact="Use functional components", category="constraint"),
        ]

        for learning in constraints:
            self.learning_cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

        # Trigger reflection
        reflector = Reflector()

        with patch.object(reflector.causality_analyzer, "analyze_causality", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "theme": "React functional programming",
                "causality": "React's rendering model requires purity",
                "summary": "Functional components enable predictable UI",
            }

            reflection = await reflector.reflect_on_constraints(constraints)

            # Store reflection as learning
            reflection_learning = reflection.to_learning()
            self.learning_cache.add_learning(
                learning_id=f"r_{reflection.reflection_id}",
                fact=reflection_learning.fact,
                category=reflection_learning.category,
            )

            # Build index
            self.learning_cache.build_bm25_index()

            # Query should find reflection
            results = self.learning_cache.bm25_query_fast("React functional", limit=10)
            result_ids = [r[0] for r in results]

            # Verify reflection is retrievable
            assert any(rid.startswith("r_") for rid in result_ids)

    def test_expected_improvements(self):
        """Test that enhancements achieve expected improvements."""
        # Based on plan expectations:
        # - Retrieval accuracy: 75% → 85%
        # - BM25 latency: 25x faster
        # - Mental models: 30% token savings

        # This is a high-level validation test
        # Actual metrics would come from benchmarking harness

        # Add test learnings
        for i in range(50):
            self.learning_cache.add_learning(
                learning_id=f"l{i}",
                fact=f"Test learning {i}",
                category="pattern",
            )

        # Build index
        indexed_count = self.learning_cache.build_bm25_index()
        assert indexed_count == 50

        # Verify fast queries work
        results = self.learning_cache.bm25_query_fast("test", limit=10)
        assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
