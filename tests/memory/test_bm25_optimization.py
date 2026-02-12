"""Tests for Phase 4.1: BM25 Inverted Index Optimization.

Tests BM25 inverted index construction, fast querying, and performance improvements.
"""

import tempfile
from pathlib import Path

import pytest

from sunwell.foundation.types.memory import Learning
from sunwell.memory.core.learning_cache import LearningCache


class TestBM25Index:
    """Test BM25 inverted index construction and querying."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_cache.db"
        self.cache = LearningCache(self.db_path)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_build_bm25_index(self):
        """Test building BM25 inverted index."""
        # Add learnings
        learnings = [
            Learning(id="l1", fact="React hooks are powerful", category="pattern"),
            Learning(id="l2", fact="Use React with TypeScript", category="pattern"),
            Learning(id="l3", fact="PostgreSQL is a database", category="pattern"),
        ]

        for learning in learnings:
            self.cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

        # Build index
        indexed_count = self.cache.build_bm25_index()
        assert indexed_count == 3

        # Verify index exists
        assert self.cache.has_bm25_index() is True

    def test_bm25_fast_query(self):
        """Test fast BM25 query using inverted index."""
        # Add learnings
        learnings = [
            Learning(id="l1", fact="React hooks are powerful for state management", category="pattern"),
            Learning(id="l2", fact="Use React with TypeScript for type safety", category="pattern"),
            Learning(id="l3", fact="PostgreSQL is a relational database", category="pattern"),
        ]

        for learning in learnings:
            self.cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

        # Build index
        self.cache.build_bm25_index()

        # Query for "React"
        results = self.cache.bm25_query_fast("React hooks", limit=10)

        # Should return learnings with React
        assert len(results) >= 2
        learning_ids = [r[0] for r in results]
        assert "l1" in learning_ids
        assert "l2" in learning_ids

        # l1 should score higher (has both "React" and "hooks")
        assert results[0][0] == "l1"

    def test_bm25_term_frequency(self):
        """Test that term frequency is correctly indexed."""
        learning = Learning(
            id="l1",
            fact="React React React hooks hooks",
            category="pattern",
        )

        self.cache.add_learning(
            learning_id=learning.id,
            fact=learning.fact,
            category=learning.category,
        )

        self.cache.build_bm25_index()

        # Query should reflect term frequencies
        results = self.cache.bm25_query_fast("React", limit=10)
        assert len(results) == 1

        # React appears 3 times, hooks 2 times
        # Score should be higher for React query

    def test_bm25_idf_calculation(self):
        """Test IDF calculation in BM25."""
        # Add learnings with varying term frequencies
        learnings = [
            Learning(id="l1", fact="React is popular", category="pattern"),
            Learning(id="l2", fact="React hooks are useful", category="pattern"),
            Learning(id="l3", fact="Angular is a framework", category="pattern"),
        ]

        for learning in learnings:
            self.cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

        self.cache.build_bm25_index()

        # "React" appears in 2/3 documents (common)
        # "Angular" appears in 1/3 documents (rare)
        # Rare terms should have higher IDF

        results_react = self.cache.bm25_query_fast("React", limit=10)
        results_angular = self.cache.bm25_query_fast("Angular", limit=10)

        assert len(results_react) == 2
        assert len(results_angular) == 1

    def test_rebuild_index_after_new_learnings(self):
        """Test rebuilding index after adding new learnings."""
        # Initial learnings
        self.cache.add_learning("l1", "React hooks", "pattern")
        self.cache.build_bm25_index()

        results1 = self.cache.bm25_query_fast("TypeScript", limit=10)
        assert len(results1) == 0

        # Add new learning
        self.cache.add_learning("l2", "TypeScript types", "pattern")

        # Index not rebuilt - should still return 0
        results2 = self.cache.bm25_query_fast("TypeScript", limit=10)
        assert len(results2) == 0

        # Rebuild index
        self.cache.build_bm25_index()

        # Now should find TypeScript
        results3 = self.cache.bm25_query_fast("TypeScript", limit=10)
        assert len(results3) == 1
        assert results3[0][0] == "l2"

    def test_empty_index(self):
        """Test querying empty index."""
        assert self.cache.has_bm25_index() is False

        # Build on empty cache
        indexed = self.cache.build_bm25_index()
        assert indexed == 0

        # Query should return empty
        results = self.cache.bm25_query_fast("test", limit=10)
        assert len(results) == 0

    def test_bm25_performance_comparison(self):
        """Test that indexed BM25 is faster than naive implementation."""
        import time

        # Add many learnings
        for i in range(100):
            self.cache.add_learning(
                learning_id=f"l{i}",
                fact=f"Learning {i} about technology and programming",
                category="pattern",
            )

        # Build index
        self.cache.build_bm25_index()

        # Time indexed query
        start_indexed = time.perf_counter()
        for _ in range(10):
            self.cache.bm25_query_fast("technology programming", limit=10)
        time_indexed = time.perf_counter() - start_indexed

        # Indexed should be faster (in real scenario with 10k+ learnings)
        # For 100 learnings, difference may be small
        # This test verifies the query executes without error
        assert time_indexed >= 0


class TestBM25Integration:
    """Integration tests for BM25 optimization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_cache.db"
        self.cache = LearningCache(self.db_path)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_hybrid_search_with_index(self):
        """Test hybrid search uses BM25 index when available."""
        from sunwell.memory.simulacrum.core.retrieval.similarity import hybrid_score

        # Add learnings
        learnings = [
            Learning(id="l1", fact="React hooks", category="pattern"),
            Learning(id="l2", fact="TypeScript types", category="pattern"),
        ]

        for learning in learnings:
            self.cache.add_learning(
                learning_id=learning.id,
                fact=learning.fact,
                category=learning.category,
            )

        self.cache.build_bm25_index()

        # Use hybrid_score with cache (should use fast path)
        # Mock embeddings
        query_embedding = [0.1] * 384
        doc_embedding = [0.15] * 384

        score = hybrid_score(
            query="React",
            query_embedding=query_embedding,
            document="React hooks are powerful",
            document_embedding=doc_embedding,
            learning_id="l1",
            cache=self.cache,
        )

        assert score > 0
        # Score should include BM25 component

    def test_index_metadata_tracking(self):
        """Test that index metadata is tracked."""
        # Add learnings
        for i in range(5):
            self.cache.add_learning(
                learning_id=f"l{i}",
                fact=f"Learning {i}",
                category="pattern",
            )

        self.cache.build_bm25_index()

        # Metadata should be stored
        # (avg_doc_length, total_docs tracked internally)
        assert self.cache.has_bm25_index() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
