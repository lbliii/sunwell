"""Parallel execution utilities for Python 3.14 free-threading.

This module leverages Python 3.14's free-threading (PEP 703/779) to achieve
true parallelism for API calls. In tier 2 execution, this can reduce 10
sequential API calls to effectively 1 round-trip time.

Key features:
- ThreadPoolExecutor for GIL-free parallel execution
- ContextVar for thread-safe state propagation
- Batch execution with configurable concurrency
- Adaptive worker counts based on GIL state (see core.freethreading)

Thread Safety:
    All shared mutable state (ChunkCache) uses threading.Lock for
    safe access in free-threaded Python (3.14t).
"""


import asyncio
import hashlib
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, TypeVar

from sunwell.core.freethreading import (
    WorkloadType,
    optimal_workers,
)

T = TypeVar("T")
R = TypeVar("R")


# Thread-safe context variables
execution_context: ContextVar[dict] = ContextVar("execution_context", default={})
current_tier: ContextVar[int] = ContextVar("current_tier", default=1)


@dataclass(frozen=True, slots=True)
class ParallelResult[T]:
    """Result from parallel execution."""

    results: tuple[T, ...]
    """Results in order of submission."""

    elapsed_ms: float
    """Total wall-clock time in milliseconds."""

    concurrency: int
    """Number of parallel workers used."""

    @property
    def speedup(self) -> float:
        """Estimated speedup vs sequential execution."""
        if len(self.results) == 0:
            return 1.0
        # Assume each call takes ~elapsed_ms/concurrency if parallel
        sequential_estimate = self.elapsed_ms * len(self.results) / max(self.concurrency, 1)
        return sequential_estimate / max(self.elapsed_ms, 1)


@dataclass(slots=True)
class ParallelExecutor:
    """Execute tasks in parallel using Python 3.14 free-threading.

    This executor uses ThreadPoolExecutor which, in Python 3.14 with
    free-threading enabled, can achieve true parallelism without GIL.

    For async tasks, it wraps them to run in the thread pool while
    preserving context variables.

    Worker count adapts based on GIL state:
    - Free-threaded: Higher workers for true parallelism
    - Standard Python: Conservative workers (threads serialize at GIL)
    """

    max_workers: int | None = None
    """Maximum workers. None = auto-detect based on GIL state."""

    workload_type: WorkloadType = WorkloadType.IO_BOUND
    """Type of work for optimal worker selection."""

    @property
    def effective_workers(self) -> int:
        """Get effective worker count."""
        if self.max_workers is not None:
            return self.max_workers
        return optimal_workers(self.workload_type)

    _pool: ThreadPoolExecutor | None = field(default=None, init=False)

    def __enter__(self) -> ParallelExecutor:
        self._pool = ThreadPoolExecutor(max_workers=self.max_workers)
        return self

    def __exit__(self, *args) -> None:
        if self._pool:
            self._pool.shutdown(wait=True)
            self._pool = None

    async def execute_batch(
        self,
        tasks: Sequence[Callable[[], T]],
    ) -> ParallelResult[T]:
        """Execute a batch of callables in parallel.

        Args:
            tasks: Sequence of zero-argument callables.

        Returns:
            ParallelResult with all results in submission order.

        Note:
            Worker count is adaptive based on GIL state. On free-threaded
            Python, more workers = more parallelism. On standard Python,
            extra workers just add context-switch overhead.
        """
        if not tasks:
            return ParallelResult(results=(), elapsed_ms=0, concurrency=0)

        start = time.perf_counter()
        workers = self.effective_workers

        # Capture current context for propagation
        ctx = copy_context()

        # Submit all tasks
        pool = self._pool or ThreadPoolExecutor(max_workers=workers)
        own_pool = self._pool is None

        try:
            futures = {
                pool.submit(ctx.run, task): i
                for i, task in enumerate(tasks)
            }

            # Collect results maintaining order
            results: list[T | None] = [None] * len(tasks)
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

            elapsed = (time.perf_counter() - start) * 1000

            return ParallelResult(
                results=tuple(results),  # type: ignore
                elapsed_ms=elapsed,
                concurrency=min(len(tasks), workers),
            )
        finally:
            if own_pool:
                pool.shutdown(wait=False)

    async def execute_async_batch(
        self,
        coroutines: Sequence[asyncio.coroutine],
    ) -> ParallelResult:
        """Execute async coroutines concurrently.

        Uses asyncio.gather for concurrent execution of coroutines.
        This is optimal for I/O-bound tasks like API calls.
        """
        if not coroutines:
            return ParallelResult(results=(), elapsed_ms=0, concurrency=0)

        start = time.perf_counter()

        # asyncio.gather runs coroutines concurrently
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        elapsed = (time.perf_counter() - start) * 1000

        # Check for exceptions
        for r in results:
            if isinstance(r, Exception):
                raise r

        return ParallelResult(
            results=tuple(results),
            elapsed_ms=elapsed,
            concurrency=len(coroutines),
        )


def content_hash(content: str) -> str:
    """Create content-addressable hash for deduplication.

    Uses xxhash-style fast hashing for O(1) deduplication checks.
    Falls back to MD5 for availability.

    Args:
        content: String content to hash.

    Returns:
        Hex digest of content hash.
    """
    # Use blake2b - fast and built into Python
    return hashlib.blake2b(content.encode(), digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class HashedChunk:
    """Content-addressable chunk for O(1) deduplication."""

    content_hash: str
    """Blake2b hash of content."""

    content: str
    """Original content."""

    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """Additional metadata (immutable)."""

    @classmethod
    def create(cls, content: str, **metadata: Any) -> HashedChunk:
        """Create a hashed chunk from content."""
        return cls(
            content_hash=content_hash(content),
            content=content,
            metadata=MappingProxyType(metadata),
        )

    def __hash__(self) -> int:
        return hash(self.content_hash)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, HashedChunk):
            return self.content_hash == other.content_hash
        return False


class ChunkCache:
    """O(1) content-addressable chunk cache.

    Uses hashing for instant deduplication - if we've seen
    this exact content before, skip re-processing.

    Thread Safety:
        Uses threading.Lock for thread-safe access in free-threaded Python (3.14t).
    """

    def __init__(self) -> None:
        self._cache: dict[str, HashedChunk] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def get_or_create(self, content: str, **metadata) -> tuple[HashedChunk, bool]:
        """Get existing chunk or create new one.

        Returns:
            Tuple of (chunk, is_new).
        """
        h = content_hash(content)

        # Fast path: check cache without lock
        if h in self._cache:
            return self._cache[h], False

        # Slow path: acquire lock, double-check, create
        with self._lock:
            if h in self._cache:
                return self._cache[h], False

            chunk = HashedChunk.create(content, **metadata)
            self._cache[h] = chunk
            return chunk, True

    def get_embedding(self, chunk: HashedChunk) -> list[float] | None:
        """Get cached embedding for chunk."""
        return self._embeddings.get(chunk.content_hash)

    def set_embedding(self, chunk: HashedChunk, embedding: list[float]) -> None:
        """Cache embedding for chunk."""
        with self._lock:
            self._embeddings[chunk.content_hash] = embedding

    @property
    def stats(self) -> dict:
        """Cache statistics."""
        with self._lock:
            return {
                "chunks": len(self._cache),
                "embeddings": len(self._embeddings),
                "hit_rate": len(self._embeddings) / max(len(self._cache), 1),
            }
