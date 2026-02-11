"""Cross-encoder reranking for two-stage retrieval (Phase 1: Foundation).

Provides cross-encoder models for reranking initial retrieval candidates.
Significantly improves accuracy at the cost of additional inference.

Part of Hindsight-inspired memory enhancements.
"""

from sunwell.memory.core.reranking.cache import RerankingCache
from sunwell.memory.core.reranking.config import (
    RERANKING_ACCURATE,
    RERANKING_BALANCED,
    RERANKING_DISABLED,
    RERANKING_FAST,
    RerankingConfig,
)
from sunwell.memory.core.reranking.cross_encoder import (
    CrossEncoderReranker,
    create_reranker,
)

__all__ = [
    # Config
    "RerankingConfig",
    "RERANKING_DISABLED",
    "RERANKING_FAST",
    "RERANKING_BALANCED",
    "RERANKING_ACCURATE",
    # Reranker
    "CrossEncoderReranker",
    "create_reranker",
    # Cache
    "RerankingCache",
]
