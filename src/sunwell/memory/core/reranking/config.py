"""Configuration for cross-encoder reranking.

Part of Phase 1: Foundation - Two-stage retrieval.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class RerankingConfig:
    """Configuration for cross-encoder reranking.

    Two-stage retrieval:
    1. Fast retrieval: Hybrid search (vector + BM25) gets ~3x candidates
    2. Reranking: Cross-encoder scores candidate relevance

    This is more expensive but significantly improves accuracy,
    especially for complex queries where semantic similarity alone
    isn't enough.
    """

    enabled: bool = False
    """Whether reranking is enabled (opt-in, expensive)."""

    model: str = "ms-marco-MiniLM-L-6-v2"
    """Cross-encoder model to use.

    Recommended models (by size/speed):
    - ms-marco-TinyBERT-L-2-v2: 17MB, fastest
    - ms-marco-MiniLM-L-6-v2: 80MB, balanced (default)
    - ms-marco-MiniLM-L-12-v2: 134MB, most accurate
    """

    batch_size: int = 8
    """Batch size for cross-encoder inference."""

    cache_ttl_seconds: int = 3600
    """Cache TTL for reranking results (1 hour default)."""

    overretrieve_multiplier: int = 3
    """How many candidates to retrieve before reranking.

    E.g., if limit=10 and multiplier=3, retrieve 30 candidates,
    then rerank and return top 10.
    """

    endpoint: str | None = None
    """Optional custom endpoint for cross-encoder inference.

    If None, uses local model loading. Can be set to an API
    endpoint for offloading inference.
    """

    fallback_on_error: bool = True
    """If True, fall back to original ranking on reranking errors."""

    min_candidates_for_reranking: int = 5
    """Minimum candidates needed to trigger reranking.

    If fewer candidates, skip reranking (not worth the overhead).
    """


# Default config instances for common scenarios
RERANKING_DISABLED = RerankingConfig(enabled=False)

RERANKING_FAST = RerankingConfig(
    enabled=True,
    model="ms-marco-TinyBERT-L-2-v2",
    batch_size=16,
)

RERANKING_BALANCED = RerankingConfig(
    enabled=True,
    model="ms-marco-MiniLM-L-6-v2",
    batch_size=8,
)

RERANKING_ACCURATE = RerankingConfig(
    enabled=True,
    model="ms-marco-MiniLM-L-12-v2",
    batch_size=4,
)
