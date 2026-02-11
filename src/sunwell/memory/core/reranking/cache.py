"""Result cache for cross-encoder reranking.

Caches reranking results to avoid expensive recomputation.
Uses query + candidate IDs as cache key.

Part of Phase 1: Foundation.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(slots=True)
class CachedResult:
    """A cached reranking result."""

    ranked_ids: tuple[str, ...]
    """Ranked candidate IDs."""

    scores: tuple[float, ...]
    """Corresponding scores."""

    timestamp: float
    """When result was cached."""

    ttl_seconds: int
    """Time-to-live in seconds."""

    def is_expired(self) -> bool:
        """Check if result is expired."""
        return time.time() - self.timestamp > self.ttl_seconds


class RerankingCache:
    """LRU cache for reranking results.

    Cache key = hash(query + sorted_candidate_ids)
    Expected hit rate: ~95% in typical usage.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """Initialize cache.

        Args:
            max_size: Maximum cache entries (LRU eviction)
            default_ttl: Default TTL in seconds (1 hour)
        """
        self._cache: dict[str, CachedResult] = {}
        self._access_times: dict[str, float] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl

        # Stats
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str, candidate_ids: list[str]) -> str:
        """Generate cache key from query and candidate IDs.

        Args:
            query: Query string
            candidate_ids: List of candidate IDs

        Returns:
            Cache key (hash)
        """
        # Sort IDs for consistent keys regardless of input order
        sorted_ids = sorted(candidate_ids)
        key_string = f"{query}:{','.join(sorted_ids)}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def get(
        self,
        query: str,
        candidate_ids: list[str],
    ) -> tuple[list[str], list[float]] | None:
        """Get cached result if available and not expired.

        Args:
            query: Query string
            candidate_ids: Candidate IDs

        Returns:
            Tuple of (ranked_ids, scores) if hit, None if miss
        """
        key = self._make_key(query, candidate_ids)

        if key not in self._cache:
            self._misses += 1
            return None

        result = self._cache[key]

        # Check expiration
        if result.is_expired():
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
            self._misses += 1
            return None

        # Update access time
        self._access_times[key] = time.time()
        self._hits += 1

        return (list(result.ranked_ids), list(result.scores))

    def put(
        self,
        query: str,
        candidate_ids: list[str],
        ranked_ids: list[str],
        scores: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        """Cache a reranking result.

        Args:
            query: Query string
            candidate_ids: Original candidate IDs
            ranked_ids: Ranked candidate IDs
            scores: Corresponding scores
            ttl_seconds: Optional TTL override
        """
        key = self._make_key(query, candidate_ids)

        # Check size limit and evict if needed
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._evict_lru()

        # Store result
        self._cache[key] = CachedResult(
            ranked_ids=tuple(ranked_ids),
            scores=tuple(scores),
            timestamp=time.time(),
            ttl_seconds=ttl_seconds or self._default_ttl,
        )
        self._access_times[key] = time.time()

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_times:
            return

        # Find LRU key
        lru_key = min(self._access_times, key=self._access_times.get)  # type: ignore[arg-type]

        # Remove from cache
        if lru_key in self._cache:
            del self._cache[lru_key]
        del self._access_times[lru_key]

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        self._access_times.clear()

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }
