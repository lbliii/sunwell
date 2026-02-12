"""Tests for Phase 1.2: Cross-Encoder Reranking System.

Tests two-stage retrieval with cross-encoder reranking for improved relevance.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sunwell.memory.core.reranking.cache import RerankingCache
from sunwell.memory.core.reranking.config import RerankingConfig
from sunwell.memory.core.reranking.cross_encoder import CrossEncoderReranker
from sunwell.foundation.types.memory import Learning


class TestRerankingConfig:
    """Test reranking configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RerankingConfig()

        assert config.model == "ms-marco-MiniLM-L-6-v2"
        assert config.cache_ttl_seconds == 3600
        assert config.batch_size == 8
        assert config.overretrieve_multiplier == 3
        assert config.min_candidates_for_reranking == 5

    def test_custom_config(self):
        """Test custom configuration."""
        config = RerankingConfig(
            model="ms-marco-TinyBERT-L-2-v2",
            cache_ttl_seconds=1800,
            batch_size=16,
        )

        assert config.model == "ms-marco-TinyBERT-L-2-v2"
        assert config.cache_ttl_seconds == 1800
        assert config.batch_size == 16


class TestRerankingCache:
    """Test reranking cache with TTL."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = RerankingCache(ttl_seconds=3600)

    def test_cache_miss(self):
        """Test cache miss."""
        result = self.cache.get("query", ["id1", "id2"])
        assert result is None

    def test_cache_hit(self):
        """Test cache hit."""
        query = "test query"
        candidate_ids = ["id1", "id2", "id3"]
        scores = [0.9, 0.7, 0.5]

        # Store in cache
        self.cache.put(query, candidate_ids, scores)

        # Retrieve from cache
        cached_scores = self.cache.get(query, candidate_ids)
        assert cached_scores == scores

    def test_cache_key_order_independence(self):
        """Test that candidate order doesn't affect cache key."""
        query = "test query"
        candidate_ids_1 = ["id1", "id2", "id3"]
        candidate_ids_2 = ["id3", "id1", "id2"]
        scores = [0.9, 0.7, 0.5]

        # Store with first order
        self.cache.put(query, candidate_ids_1, scores)

        # Should hit with second order (sorted internally)
        cached_scores = self.cache.get(query, candidate_ids_2)
        assert cached_scores is not None

    def test_cache_different_queries(self):
        """Test that different queries have separate cache entries."""
        candidate_ids = ["id1", "id2"]

        self.cache.put("query1", candidate_ids, [0.9, 0.7])
        self.cache.put("query2", candidate_ids, [0.8, 0.6])

        scores1 = self.cache.get("query1", candidate_ids)
        scores2 = self.cache.get("query2", candidate_ids)

        assert scores1 == [0.9, 0.7]
        assert scores2 == [0.8, 0.6]

    def test_cache_stats(self):
        """Test cache statistics."""
        query = "test"
        ids = ["id1"]

        # Miss
        self.cache.get(query, ids)

        # Put
        self.cache.put(query, ids, [0.9])

        # Hit
        self.cache.get(query, ids)

        stats = self.cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1


class TestCrossEncoderReranker:
    """Test cross-encoder reranking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = RerankingConfig(
            model="ms-marco-MiniLM-L-6-v2",
            batch_size=8,
        )
        self.reranker = CrossEncoderReranker(self.config)

    def test_model_unavailable_fallback(self):
        """Test graceful fallback when model unavailable."""
        # Force model to be None
        self.reranker.model = None

        learnings = [
            Learning(id="l1", fact="React hooks are useful", category="pattern"),
            Learning(id="l2", fact="Use TypeScript for types", category="pattern"),
        ]

        # Should return learnings unchanged
        reranked = self.reranker.rerank("React", learnings, limit=2)
        assert len(reranked) == 2
        assert reranked[0].id == "l1"
        assert reranked[1].id == "l2"

    @patch("sunwell.memory.core.reranking.cross_encoder.CrossEncoder")
    def test_reranking_with_mock_model(self, mock_cross_encoder):
        """Test reranking with mocked model."""
        # Mock the model
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.3, 0.7]  # Scores for 3 candidates
        mock_cross_encoder.return_value = mock_model

        # Create reranker with mocked model
        reranker = CrossEncoderReranker(self.config)
        reranker.model = mock_model

        learnings = [
            Learning(id="l1", fact="React hooks", category="pattern"),
            Learning(id="l2", fact="Angular components", category="pattern"),
            Learning(id="l3", fact="React context", category="pattern"),
        ]

        reranked = reranker.rerank("React best practices", learnings, limit=2)

        # Should be sorted by score: l1 (0.9), l3 (0.7)
        assert len(reranked) == 2
        assert reranked[0].id == "l1"
        assert reranked[1].id == "l3"

    @patch("sunwell.memory.core.reranking.cross_encoder.CrossEncoder")
    def test_cache_usage(self, mock_cross_encoder):
        """Test that cache is used for repeated queries."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.7]
        mock_cross_encoder.return_value = mock_model

        reranker = CrossEncoderReranker(self.config)
        reranker.model = mock_model

        learnings = [
            Learning(id="l1", fact="React", category="pattern"),
            Learning(id="l2", fact="Angular", category="pattern"),
        ]

        # First call - should hit model
        reranker.rerank("test query", learnings, limit=2)
        assert mock_model.predict.call_count == 1

        # Second call with same query/learnings - should use cache
        reranker.rerank("test query", learnings, limit=2)
        assert mock_model.predict.call_count == 1  # Still 1 (cached)

    def test_min_candidates_threshold(self):
        """Test that reranking skips if too few candidates."""
        learnings = [
            Learning(id="l1", fact="React", category="pattern"),
            Learning(id="l2", fact="Angular", category="pattern"),
        ]

        # With min_candidates=5, should skip reranking
        config = RerankingConfig(min_candidates_for_reranking=5)
        reranker = CrossEncoderReranker(config)

        reranked = reranker.rerank("test", learnings, limit=2)

        # Should return unchanged (too few candidates)
        assert reranked == learnings

    @patch("sunwell.memory.core.reranking.cross_encoder.CrossEncoder")
    def test_batch_processing(self, mock_cross_encoder):
        """Test batch processing of candidates."""
        mock_model = MagicMock()
        # Return scores for 10 candidates
        mock_model.predict.return_value = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
        mock_cross_encoder.return_value = mock_model

        config = RerankingConfig(batch_size=4)
        reranker = CrossEncoderReranker(config)
        reranker.model = mock_model

        # Create 10 learnings
        learnings = [
            Learning(id=f"l{i}", fact=f"fact {i}", category="pattern")
            for i in range(10)
        ]

        reranked = reranker.rerank("test query", learnings, limit=5)

        # Should return top 5 by score
        assert len(reranked) == 5
        assert reranked[0].id == "l0"  # Highest score (0.9)
        assert reranked[1].id == "l1"  # Second (0.8)


class TestTwoStageRetrieval:
    """Integration tests for two-stage retrieval pipeline."""

    @patch("sunwell.memory.core.reranking.cross_encoder.CrossEncoder")
    def test_overretrieve_and_rerank(self, mock_cross_encoder):
        """Test overretrieve then rerank pattern."""
        mock_model = MagicMock()
        # 15 candidates, but only top 5 should be returned
        mock_model.predict.return_value = list(range(15, 0, -1))  # Scores 15, 14, ..., 1
        mock_cross_encoder.return_value = mock_model

        config = RerankingConfig(
            overretrieve_multiplier=3,
            min_candidates_for_reranking=5,
        )
        reranker = CrossEncoderReranker(config)
        reranker.model = mock_model

        # Simulate overretrieved candidates (limit=5, retrieved=15)
        candidates = [
            Learning(id=f"l{i}", fact=f"fact {i}", category="pattern")
            for i in range(15)
        ]

        # Rerank to top 5
        reranked = reranker.rerank("query", candidates, limit=5)

        assert len(reranked) == 5
        # Should be sorted by score descending
        assert reranked[0].id == "l0"  # Score 15
        assert reranked[4].id == "l4"  # Score 11

    def test_integration_with_disabled_reranking(self):
        """Test that system works when reranking disabled."""
        config = RerankingConfig()
        reranker = CrossEncoderReranker(config)

        # Force model unavailable
        reranker.model = None

        learnings = [
            Learning(id="l1", fact="First", category="pattern"),
            Learning(id="l2", fact="Second", category="pattern"),
        ]

        # Should pass through unchanged
        result = reranker.rerank("query", learnings, limit=2)
        assert result == learnings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
