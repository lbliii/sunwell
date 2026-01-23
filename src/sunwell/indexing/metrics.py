"""Index health metrics for observability (RFC-108)."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IndexMetrics:
    """Telemetry for index health monitoring."""

    build_time_ms: int = 0
    """Total time to build index in milliseconds."""

    chunk_count: int = 0
    """Number of chunks in the index."""

    file_count: int = 0
    """Number of files indexed."""

    embedding_time_ms: int = 0
    """Time spent on embeddings in milliseconds."""

    cache_hits: int = 0
    """Number of cache hits."""

    cache_misses: int = 0
    """Number of cache misses."""

    query_latencies: deque[int] = field(default_factory=lambda: deque(maxlen=100))
    """Recent query latencies in milliseconds."""

    last_build: datetime | None = None
    """Timestamp of last index build."""

    last_query: datetime | None = None
    """Timestamp of last query."""

    errors: deque[str] = field(default_factory=lambda: deque(maxlen=10))
    """Recent error messages."""

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate (0.0-1.0)."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def avg_query_latency_ms(self) -> float:
        """Average query latency in milliseconds."""
        if not self.query_latencies:
            return 0.0
        return sum(self.query_latencies) / len(self.query_latencies)

    @property
    def last_query_latency_ms(self) -> int:
        """Last query latency in milliseconds."""
        if not self.query_latencies:
            return 0
        return self.query_latencies[-1]

    def record_query(self, latency_ms: int) -> None:
        """Record a query latency."""
        self.query_latencies.append(latency_ms)
        self.last_query = datetime.now()

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1

    def record_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(f"{datetime.now().isoformat()}: {error}")

    def is_healthy(self) -> bool:
        """Check if index is healthy.

        Returns:
            True if index is in good health.
        """
        # Queries should be <500ms on average
        if self.avg_query_latency_ms > 500:
            return False
        # Should have indexed something
        if self.chunk_count == 0:
            return False
        return True

    def to_json(self) -> dict:
        """Export metrics as JSON-serializable dict."""
        return {
            "build_time_ms": self.build_time_ms,
            "chunk_count": self.chunk_count,
            "file_count": self.file_count,
            "embedding_time_ms": self.embedding_time_ms,
            "cache_hit_rate": self.cache_hit_rate,
            "avg_query_latency_ms": self.avg_query_latency_ms,
            "last_query_latency_ms": self.last_query_latency_ms,
            "last_build": self.last_build.isoformat() if self.last_build else None,
            "last_query": self.last_query.isoformat() if self.last_query else None,
            "is_healthy": self.is_healthy(),
            "recent_errors": list(self.errors),
        }
