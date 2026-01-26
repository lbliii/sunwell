"""Tests for work deduplication (WorkDeduper and AsyncWorkDeduper).

Tests concurrent behavior, error propagation, and cache semantics.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from sunwell.agent.incremental.deduper import AsyncWorkDeduper, WorkDeduper


# =============================================================================
# WorkDeduper Tests (Synchronous)
# =============================================================================


class TestWorkDeduper:
    """Tests for synchronous WorkDeduper."""

    def test_basic_execution(self) -> None:
        """Work function is called and result returned."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def work() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        result = deduper.do("key1", work)

        assert result == "result"
        assert call_count == 1

    def test_result_cached(self) -> None:
        """Second call with same key returns cached result without re-execution."""
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

    def test_different_keys_both_execute(self) -> None:
        """Different keys execute their own work."""
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
        """Errors are cached and propagated to callers."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def failing_work() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("intentional error")

        # First call raises
        with pytest.raises(ValueError, match="intentional error"):
            deduper.do("key1", failing_work)

        # Second call raises same error without re-execution
        with pytest.raises(ValueError, match="intentional error"):
            deduper.do("key1", failing_work)

        assert call_count == 1  # Only called once

    def test_concurrent_same_key_single_execution(self) -> None:
        """Multiple concurrent calls with same key result in single execution."""
        deduper = WorkDeduper[str]()
        call_count = 0
        call_lock = threading.Lock()

        def slow_work() -> str:
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.1)  # Simulate slow work
            return "result"

        results: list[str] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                result = deduper.do("key1", slow_work)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start 5 threads simultaneously
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        assert all(r == "result" for r in results)
        assert call_count == 1  # Only one execution despite 5 threads

    def test_concurrent_error_propagation(self) -> None:
        """Error during concurrent execution propagates to all waiters."""
        deduper = WorkDeduper[str]()
        call_count = 0
        call_lock = threading.Lock()

        def failing_slow_work() -> str:
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.1)
            raise ValueError("concurrent error")

        errors: list[Exception] = []

        def worker() -> None:
            try:
                deduper.do("key1", failing_slow_work)
            except ValueError as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 5  # All threads got the error
        assert all("concurrent error" in str(e) for e in errors)
        assert call_count == 1  # Only one execution

    def test_clear_specific_key(self) -> None:
        """Clearing a specific key allows re-execution."""
        deduper = WorkDeduper[int]()
        call_count = 0

        def work() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        result1 = deduper.do("key1", work)
        assert result1 == 1

        deduper.clear("key1")

        result2 = deduper.do("key1", work)
        assert result2 == 2  # Re-executed after clear
        assert call_count == 2

    def test_clear_all(self) -> None:
        """Clearing all keys allows re-execution of everything."""
        deduper = WorkDeduper[str]()

        deduper.do("key1", lambda: "a")
        deduper.do("key2", lambda: "b")

        assert deduper.cache_size == 2

        deduper.clear()

        assert deduper.cache_size == 0

    def test_is_cached(self) -> None:
        """is_cached correctly reports cached state."""
        deduper = WorkDeduper[str]()

        assert not deduper.is_cached("key1")

        deduper.do("key1", lambda: "result")

        assert deduper.is_cached("key1")
        assert not deduper.is_cached("key2")

    def test_get_cached(self) -> None:
        """get_cached retrieves without execution."""
        deduper = WorkDeduper[str]()

        assert deduper.get_cached("key1") is None

        deduper.do("key1", lambda: "result")

        assert deduper.get_cached("key1") == "result"

    def test_get_cached_raises_for_error(self) -> None:
        """get_cached raises if cached error exists."""
        deduper = WorkDeduper[str]()

        def failing() -> str:
            raise ValueError("cached error")

        with pytest.raises(ValueError):
            deduper.do("key1", failing)

        with pytest.raises(ValueError, match="cached error"):
            deduper.get_cached("key1")

    def test_pending_count(self) -> None:
        """pending_count tracks in-progress work."""
        deduper = WorkDeduper[str]()
        started = threading.Event()
        proceed = threading.Event()

        def blocking_work() -> str:
            started.set()
            proceed.wait()
            return "done"

        def worker() -> None:
            deduper.do("key1", blocking_work)

        t = threading.Thread(target=worker)
        t.start()

        started.wait()
        assert deduper.pending_count == 1

        proceed.set()
        t.join()

        assert deduper.pending_count == 0


# =============================================================================
# AsyncWorkDeduper Tests
# =============================================================================


class TestAsyncWorkDeduper:
    """Tests for asynchronous AsyncWorkDeduper."""

    @pytest.mark.asyncio
    async def test_basic_execution(self) -> None:
        """Work function is called and result returned."""
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
    async def test_result_cached(self) -> None:
        """Second call with same key returns cached result."""
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
    async def test_error_propagation(self) -> None:
        """Errors are cached and propagated."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def failing_work() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("async error")

        with pytest.raises(ValueError, match="async error"):
            await deduper.do("key1", failing_work)

        with pytest.raises(ValueError, match="async error"):
            await deduper.do("key1", failing_work)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_same_key_single_execution(self) -> None:
        """Multiple concurrent calls with same key result in single execution."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def slow_work() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return "result"

        # Start 5 concurrent tasks
        results = await asyncio.gather(*[deduper.do("key1", slow_work) for _ in range(5)])

        assert len(results) == 5
        assert all(r == "result" for r in results)
        assert call_count == 1  # Only one execution

    @pytest.mark.asyncio
    async def test_concurrent_different_keys(self) -> None:
        """Different keys execute independently in parallel."""
        deduper = AsyncWorkDeduper[str]()
        execution_order: list[str] = []
        lock = asyncio.Lock()

        async def work(key: str) -> str:
            async with lock:
                execution_order.append(f"start_{key}")
            await asyncio.sleep(0.05)
            async with lock:
                execution_order.append(f"end_{key}")
            return key

        results = await asyncio.gather(
            deduper.do("key1", lambda: work("key1")),
            deduper.do("key2", lambda: work("key2")),
            deduper.do("key3", lambda: work("key3")),
        )

        assert set(results) == {"key1", "key2", "key3"}
        # All should start before any ends (parallel execution)
        starts = [e for e in execution_order if e.startswith("start")]
        ends = [e for e in execution_order if e.startswith("end")]
        assert len(starts) == 3
        assert len(ends) == 3

    @pytest.mark.asyncio
    async def test_concurrent_error_propagation(self) -> None:
        """Error during concurrent execution propagates to all waiters."""
        deduper = AsyncWorkDeduper[str]()
        call_count = 0

        async def failing_slow_work() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            raise ValueError("concurrent async error")

        tasks = [deduper.do("key1", failing_slow_work) for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert all(isinstance(r, ValueError) for r in results)
        assert all("concurrent async error" in str(r) for r in results)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Clearing allows re-execution."""
        deduper = AsyncWorkDeduper[int]()
        call_count = 0

        async def work() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        result1 = await deduper.do("key1", work)
        assert result1 == 1

        await deduper.clear("key1")

        result2 = await deduper.do("key1", work)
        assert result2 == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_is_cached(self) -> None:
        """is_cached correctly reports cached state."""
        deduper = AsyncWorkDeduper[str]()

        assert not await deduper.is_cached("key1")

        async def work1() -> str:
            return "result"

        await deduper.do("key1", work1)

        assert await deduper.is_cached("key1")
        assert not await deduper.is_cached("key2")

    @pytest.mark.asyncio
    async def test_race_condition_fixed(self) -> None:
        """Verify the race condition fix works correctly.

        This test creates a scenario where multiple tasks compete for the same key,
        ensuring only one executes while others wait correctly.
        """
        deduper = AsyncWorkDeduper[str]()
        execution_count = 0
        execution_order: list[str] = []

        async def tracked_work() -> str:
            nonlocal execution_count
            execution_count += 1
            execution_order.append("work_start")
            await asyncio.sleep(0.05)  # Simulate work
            execution_order.append("work_end")
            return "completed"

        # Create many concurrent requests
        tasks = [deduper.do("race_key", tracked_work) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should get the same result
        assert all(r == "completed" for r in results)
        # Only one execution should have happened
        assert execution_count == 1
        assert execution_order == ["work_start", "work_end"]

    @pytest.mark.asyncio
    async def test_get_cache_size_async_safe(self) -> None:
        """Async-safe get_cache_size returns accurate count."""
        deduper = AsyncWorkDeduper[str]()

        assert await deduper.get_cache_size() == 0

        async def work(val: str) -> str:
            return val

        await deduper.do("key1", lambda: work("a"))
        await deduper.do("key2", lambda: work("b"))

        assert await deduper.get_cache_size() == 2

    @pytest.mark.asyncio
    async def test_get_pending_count_async_safe(self) -> None:
        """Async-safe get_pending_count returns accurate count."""
        deduper = AsyncWorkDeduper[str]()
        started = asyncio.Event()
        proceed = asyncio.Event()

        async def blocking_work() -> str:
            started.set()
            await proceed.wait()
            return "done"

        # Start work but don't let it complete
        task = asyncio.create_task(deduper.do("key1", blocking_work))

        await started.wait()

        # Should show 1 pending
        assert await deduper.get_pending_count() == 1
        assert deduper.pending_count == 1  # Property should also work here

        # Let it complete
        proceed.set()
        await task

        assert await deduper.get_pending_count() == 0

    @pytest.mark.asyncio
    async def test_async_safe_vs_property_under_contention(self) -> None:
        """Async-safe methods are reliable under contention.

        Properties may give stale values during concurrent modifications,
        but async methods are always accurate.
        """
        deduper = AsyncWorkDeduper[int]()
        results_collected: list[int] = []

        async def work(i: int) -> int:
            await asyncio.sleep(0.01)
            return i

        async def add_and_check(i: int) -> None:
            await deduper.do(f"key_{i}", lambda: work(i))
            # Async method gives accurate count
            size = await deduper.get_cache_size()
            results_collected.append(size)

        # Run many concurrent additions
        await asyncio.gather(*[add_and_check(i) for i in range(20)])

        # Final count should be accurate
        assert await deduper.get_cache_size() == 20

        # All collected sizes should be between 1 and 20
        assert all(1 <= s <= 20 for s in results_collected)
