"""Tests for RFC-074 WorkDeduper."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from sunwell.agent.incremental.deduper import AsyncWorkDeduper, WorkDeduper


class TestWorkDeduper:
    """Tests for synchronous WorkDeduper."""

    def test_execute_work(self) -> None:
        """Basic work execution."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def work() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        result = deduper.do("key1", work)

        assert result == "result"
        assert call_count == 1

    def test_cache_result(self) -> None:
        """Second call returns cached result."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def work() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        result1 = deduper.do("key1", work)
        result2 = deduper.do("key1", work)

        assert result1 == result2
        assert call_count == 1  # Only called once

    def test_different_keys(self) -> None:
        """Different keys execute independently."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def work() -> str:
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        result1 = deduper.do("key1", work)
        result2 = deduper.do("key2", work)

        assert result1 == "result_1"
        assert result2 == "result_2"
        assert call_count == 2

    def test_error_propagation(self) -> None:
        """Errors are cached and re-raised."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def work() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            deduper.do("key1", work)

        # Second call should raise same error
        with pytest.raises(ValueError, match="test error"):
            deduper.do("key1", work)

        assert call_count == 1  # Only called once

    def test_clear(self) -> None:
        """Can clear cached results."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def work() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        deduper.do("key1", work)
        deduper.clear("key1")
        deduper.do("key1", work)

        assert call_count == 2  # Called twice after clear

    def test_clear_all(self) -> None:
        """Can clear all cached results."""
        deduper = WorkDeduper[str]()

        deduper.do("key1", lambda: "result1")
        deduper.do("key2", lambda: "result2")

        assert deduper.cache_size == 2

        deduper.clear()

        assert deduper.cache_size == 0

    def test_is_cached(self) -> None:
        """Can check if key is cached."""
        deduper = WorkDeduper[str]()

        assert not deduper.is_cached("key1")

        deduper.do("key1", lambda: "result")

        assert deduper.is_cached("key1")

    def test_concurrent_same_key(self) -> None:
        """Concurrent calls with same key only execute once."""
        deduper = WorkDeduper[str]()
        call_count = 0
        call_lock = threading.Lock()

        def work() -> str:
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.1)  # Simulate slow work
            return "result"

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(deduper.do, "key1", work) for _ in range(5)]
            results = [f.result() for f in futures]

        assert all(r == "result" for r in results)
        assert call_count == 1  # Only executed once


class TestAsyncWorkDeduper:
    """Tests for async AsyncWorkDeduper."""

    @pytest.mark.asyncio
    async def test_execute_work(self) -> None:
        """Basic async work execution."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def work() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        result = await deduper.do("key1", work)

        assert result == "result"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cache_result(self) -> None:
        """Second call returns cached result."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def work() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        result1 = await deduper.do("key1", work)
        result2 = await deduper.do("key1", work)

        assert result1 == result2
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_same_key(self) -> None:
        """Concurrent async calls with same key only execute once."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def work() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate slow work
            return "result"

        results = await asyncio.gather(
            deduper.do("key1", work),
            deduper.do("key1", work),
            deduper.do("key1", work),
        )

        assert all(r == "result" for r in results)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_error_propagation(self) -> None:
        """Errors are cached and re-raised in async."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def work() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("async error")

        with pytest.raises(ValueError, match="async error"):
            await deduper.do("key1", work)

        with pytest.raises(ValueError, match="async error"):
            await deduper.do("key1", work)

        assert call_count == 1
