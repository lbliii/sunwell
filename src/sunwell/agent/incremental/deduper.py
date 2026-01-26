"""Work deduplication for parallel execution (RFC-074).

Prevents redundant LLM calls when multiple threads request the same work.
If multiple requests arrive for the same artifact (identified by hash),
only one executes; others wait and receive the same result.

Inspired by Pachyderm's WorkDeduper:
https://github.com/pachyderm/pachyderm/blob/master/src/internal/miscutil/work_deduper.go

Example:
    >>> deduper = WorkDeduper[str]()
    >>>
    >>> # Thread 1 and Thread 2 call simultaneously with same key
    >>> result = deduper.do("hash_abc123", lambda: expensive_llm_call())
    >>>
    >>> # Only one LLM call happens, both threads get same result
"""

import asyncio
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class WorkDeduper[T]:
    """Deduplicate concurrent identical synchronous work.

    If multiple threads request the same work (identified by key),
    only one actually executes; others wait and receive the same result.

    Thread-safe via threading.Lock.

    Example:
        >>> deduper = WorkDeduper[str]()
        >>>
        >>> def expensive_work() -> str:
        ...     return "result"
        >>>
        >>> # First call executes
        >>> result1 = deduper.do("key1", expensive_work)
        >>>
        >>> # Concurrent call with same key waits and gets same result
        >>> result2 = deduper.do("key1", expensive_work)
        >>>
        >>> assert result1 is result2  # Same object
    """

    _in_progress: dict[str, threading.Event] = field(default_factory=dict)
    """Keys currently being computed."""

    _results: dict[str, T] = field(default_factory=dict)
    """Cached results by key."""

    _errors: dict[str, Exception] = field(default_factory=dict)
    """Cached errors by key."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for thread-safe access."""

    def do(self, key: str, work: Callable[[], T]) -> T:
        """Execute work, deduplicating concurrent identical requests.

        Args:
            key: Unique identifier for this work (e.g., artifact hash).
            work: Function to execute if this is the first request.

        Returns:
            Result of work (may be from cache if concurrent request).

        Raises:
            Exception: If work raises, propagated to all waiters.
        """
        with self._lock:
            # Check if result already cached
            if key in self._results:
                return self._results[key]
            if key in self._errors:
                raise self._errors[key]

            # Check if work is already in progress
            if key in self._in_progress:
                event = self._in_progress[key]
                # Release lock while waiting
                self._lock.release()
                try:
                    event.wait()
                finally:
                    self._lock.acquire()

                # Return result or raise error
                if key in self._errors:
                    raise self._errors[key]
                return self._results[key]

            # We're the first — start the work
            event = threading.Event()
            self._in_progress[key] = event

        # Execute work outside the lock
        try:
            result = work()
            with self._lock:
                self._results[key] = result
                del self._in_progress[key]
            event.set()
            return result
        except Exception as e:
            with self._lock:
                self._errors[key] = e
                del self._in_progress[key]
            event.set()
            raise

    def clear(self, key: str | None = None) -> None:
        """Clear cached results.

        Args:
            key: Specific key to clear, or None to clear all.
        """
        with self._lock:
            if key is None:
                self._results.clear()
                self._errors.clear()
            else:
                self._results.pop(key, None)
                self._errors.pop(key, None)

    def is_cached(self, key: str) -> bool:
        """Check if a result is cached.

        Args:
            key: The key to check.

        Returns:
            True if result (or error) is cached.
        """
        with self._lock:
            return key in self._results or key in self._errors

    def get_cached(self, key: str) -> T | None:
        """Get cached result without executing.

        Args:
            key: The key to look up.

        Returns:
            Cached result, or None if not cached.

        Raises:
            Exception: If cached error exists.
        """
        with self._lock:
            if key in self._errors:
                raise self._errors[key]
            return self._results.get(key)

    @property
    def cache_size(self) -> int:
        """Number of cached results."""
        with self._lock:
            return len(self._results)

    @property
    def pending_count(self) -> int:
        """Number of in-progress work items."""
        with self._lock:
            return len(self._in_progress)


@dataclass(slots=True)
class AsyncWorkDeduper[T]:
    """Deduplicate concurrent identical async work.

    Async version of WorkDeduper for use with asyncio.

    Example:
        >>> deduper = AsyncWorkDeduper[str]()
        >>>
        >>> async def expensive_work() -> str:
        ...     await asyncio.sleep(1)
        ...     return "result"
        >>>
        >>> # Multiple concurrent calls with same key
        >>> results = await asyncio.gather(
        ...     deduper.do("key1", expensive_work),
        ...     deduper.do("key1", expensive_work),
        ... )
        >>>
        >>> # Only one execution, both get same result
        >>> assert results[0] == results[1]
    """

    _in_progress: dict[str, asyncio.Event] = field(default_factory=dict)
    """Keys currently being computed."""

    _results: dict[str, T] = field(default_factory=dict)
    """Cached results by key."""

    _errors: dict[str, Exception] = field(default_factory=dict)
    """Cached errors by key."""

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    """Lock for async-safe access."""

    async def do(
        self,
        key: str,
        work: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Execute async work, deduplicating concurrent identical requests.

        Args:
            key: Unique identifier for this work (e.g., artifact hash).
            work: Async function to execute if this is the first request.

        Returns:
            Result of work (may be from cache if concurrent request).

        Raises:
            Exception: If work raises, propagated to all waiters.
        """
        while True:
            async with self._lock:
                # Check if result already cached
                if key in self._results:
                    return self._results[key]
                if key in self._errors:
                    raise self._errors[key]

                # Check if work is already in progress
                if key in self._in_progress:
                    event_to_wait = self._in_progress[key]
                else:
                    # We're the first — register and start the work
                    event = asyncio.Event()
                    self._in_progress[key] = event
                    break  # Exit lock to execute work

            # Wait for in-progress work (outside the lock)
            await event_to_wait.wait()
            # Loop back to check result under lock

        # Execute work outside the lock
        try:
            result = await work()
            async with self._lock:
                self._results[key] = result
                del self._in_progress[key]
            event.set()
            return result
        except Exception as e:
            async with self._lock:
                self._errors[key] = e
                del self._in_progress[key]
            event.set()
            raise

    async def clear(self, key: str | None = None) -> None:
        """Clear cached results.

        Args:
            key: Specific key to clear, or None to clear all.
        """
        async with self._lock:
            if key is None:
                self._results.clear()
                self._errors.clear()
            else:
                self._results.pop(key, None)
                self._errors.pop(key, None)

    async def is_cached(self, key: str) -> bool:
        """Check if a result is cached.

        Args:
            key: The key to check.

        Returns:
            True if result (or error) is cached.
        """
        async with self._lock:
            return key in self._results or key in self._errors

    @property
    def cache_size(self) -> int:
        """Number of cached results (approximate, not async-safe)."""
        return len(self._results)

    @property
    def pending_count(self) -> int:
        """Number of in-progress work items (approximate, not async-safe)."""
        return len(self._in_progress)

    async def get_cache_size(self) -> int:
        """Get number of cached results (async-safe)."""
        async with self._lock:
            return len(self._results)

    async def get_pending_count(self) -> int:
        """Get number of in-progress work items (async-safe)."""
        async with self._lock:
            return len(self._in_progress)
