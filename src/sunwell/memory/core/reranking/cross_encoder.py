"""Cross-encoder reranking for two-stage retrieval.

Uses cross-encoder models to rerank initial retrieval candidates.
More expensive than first-stage retrieval but significantly more accurate.

Part of Phase 1: Foundation.
"""

import logging
from typing import TYPE_CHECKING, TypeVar

from sunwell.memory.core.reranking.cache import RerankingCache
from sunwell.memory.core.reranking.config import RerankingConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CrossEncoderReranker:
    """Cross-encoder reranker for improving retrieval accuracy.

    Two-stage retrieval pipeline:
    1. Fast retrieval (hybrid search) gets ~3x candidates
    2. Cross-encoder scores query-candidate pairs for accurate ranking

    This is opt-in (expensive) but can improve accuracy from ~75% to ~85%+.
    """

    def __init__(self, config: RerankingConfig):
        """Initialize cross-encoder reranker.

        Args:
            config: Reranking configuration
        """
        self.config = config
        self._cache = RerankingCache(
            max_size=1000,
            default_ttl=config.cache_ttl_seconds,
        )
        self._model = None
        self._model_loaded = False
        self._load_failed = False

    def _load_model(self) -> bool:
        """Load the cross-encoder model.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._model_loaded or self._load_failed:
            return self._model_loaded

        try:
            # Try to import sentence-transformers
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.config.model)
            self._model_loaded = True
            logger.info(f"Loaded cross-encoder model: {self.config.model}")
            return True
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            self._load_failed = True
            return False
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder model: {e}")
            self._load_failed = True
            return False

    async def rerank(
        self,
        query: str,
        candidates: list[tuple[T, float]],
        limit: int,
    ) -> list[tuple[T, float]]:
        """Rerank candidates using cross-encoder.

        Args:
            query: Query string
            candidates: List of (item, score) tuples from first-stage retrieval
            limit: Number of results to return after reranking

        Returns:
            Reranked list of (item, score) tuples
        """
        if not self.config.enabled:
            return candidates[:limit]

        if len(candidates) < self.config.min_candidates_for_reranking:
            return candidates[:limit]

        # Extract candidate IDs for caching
        # For now, use str representation of items
        candidate_ids = [str(hash(str(item))) for item, _ in candidates]

        # Check cache
        cached = self._cache.get(query, candidate_ids)
        if cached:
            ranked_ids, scores = cached
            # Rebuild results from cached order
            id_to_item = {
                candidate_ids[i]: candidates[i] for i in range(len(candidates))
            }
            return [
                (id_to_item[rid][0], score)
                for rid, score in zip(ranked_ids, scores, strict=True)
                if rid in id_to_item
            ][:limit]

        # Load model if needed
        if not self._load_model():
            if self.config.fallback_on_error:
                logger.debug("Falling back to original ranking (model not available)")
                return candidates[:limit]
            return candidates[:limit]

        try:
            # Prepare query-candidate pairs
            pairs = [(query, self._get_text(item)) for item, _ in candidates]

            # Score with cross-encoder
            scores = self._model.predict(
                pairs,
                batch_size=self.config.batch_size,
                show_progress_bar=False,
            )

            # Combine items with new scores
            reranked = [
                (candidates[i][0], float(scores[i]))
                for i in range(len(candidates))
            ]

            # Sort by cross-encoder score
            reranked.sort(key=lambda x: x[1], reverse=True)

            # Cache the result
            ranked_ids = [candidate_ids[candidates.index(item)] for item, _ in reranked]
            self._cache.put(
                query,
                candidate_ids,
                ranked_ids[:limit],
                [score for _, score in reranked[:limit]],
            )

            return reranked[:limit]

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            if self.config.fallback_on_error:
                logger.debug("Falling back to original ranking")
                return candidates[:limit]
            raise

    def _get_text(self, item: T) -> str:
        """Extract text from an item for reranking.

        Args:
            item: Item to extract text from

        Returns:
            Text representation
        """
        # Handle common types
        if hasattr(item, "fact"):
            return item.fact  # Learning
        if hasattr(item, "content"):
            return item.content  # Turn/Chunk
        if hasattr(item, "summary"):
            return item.summary  # Episode
        if isinstance(item, str):
            return item
        return str(item)

    def stats(self) -> dict:
        """Get reranker statistics.

        Returns:
            Dict with reranker stats
        """
        return {
            "enabled": self.config.enabled,
            "model": self.config.model,
            "model_loaded": self._model_loaded,
            "cache_stats": self._cache.stats(),
        }


# Factory function
def create_reranker(
    enabled: bool = False,
    model: str = "ms-marco-MiniLM-L-6-v2",
    cache_ttl: int = 3600,
) -> CrossEncoderReranker:
    """Create a cross-encoder reranker.

    Args:
        enabled: Whether reranking is enabled
        model: Cross-encoder model name
        cache_ttl: Cache TTL in seconds

    Returns:
        CrossEncoderReranker instance
    """
    config = RerankingConfig(
        enabled=enabled,
        model=model,
        cache_ttl_seconds=cache_ttl,
    )
    return CrossEncoderReranker(config)
