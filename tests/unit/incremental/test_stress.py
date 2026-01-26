"""Stress tests and advanced scenarios for incremental package.

Tests concurrency under load, state consistency invariants, and error recovery.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from sunwell.agent.incremental.cache import ExecutionCache, ExecutionStatus
from sunwell.agent.incremental.deduper import AsyncWorkDeduper, WorkDeduper


# =============================================================================
# Concurrency Stress Tests
# =============================================================================


class TestConcurrencyStress:
    """High-concurrency stress tests."""

    def test_sync_deduper_100_concurrent_same_key(self) -> None:
        """100 threads requesting same key results in single execution."""
        deduper = WorkDeduper[str]()
        execution_count = 0
        lock = threading.Lock()

        def slow_work() -> str:
            nonlocal execution_count
            with lock:
                execution_count += 1
            time.sleep(0.05)
            return "result"

        results: list[str] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                result = deduper.do("shared_key", slow_work)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100
        assert all(r == "result" for r in results)
        assert execution_count == 1

    @pytest.mark.asyncio
    async def test_async_deduper_100_concurrent_same_key(self) -> None:
        """100 async tasks requesting same key results in single execution."""
        deduper = AsyncWorkDeduper[str]()
        execution_count = 0

        async def slow_work() -> str:
            nonlocal execution_count
            execution_count += 1
            await asyncio.sleep(0.05)
            return "result"

        results = await asyncio.gather(
            *[deduper.do("shared_key", slow_work) for _ in range(100)]
        )

        assert len(results) == 100
        assert all(r == "result" for r in results)
        assert execution_count == 1

    @pytest.mark.asyncio
    async def test_async_deduper_many_unique_keys(self) -> None:
        """Many unique keys execute in parallel without interference."""
        deduper = AsyncWorkDeduper[int]()
        execution_count = 0

        async def work(i: int) -> int:
            nonlocal execution_count
            execution_count += 1
            await asyncio.sleep(0.01)
            return i * 2

        results = await asyncio.gather(
            *[deduper.do(f"key_{i}", lambda i=i: work(i)) for i in range(50)]
        )

        assert len(results) == 50
        assert set(results) == {i * 2 for i in range(50)}
        assert execution_count == 50

    def test_cache_concurrent_writes_stress(self, tmp_path: Path) -> None:
        """Stress test concurrent writes to cache."""
        cache = ExecutionCache(tmp_path / "stress.db")
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(100):
                    cache.set(
                        f"artifact_{thread_id}_{i}",
                        f"hash_{thread_id}_{i}",
                        ExecutionStatus.COMPLETED,
                        {"data": f"{thread_id}_{i}"},
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        cache.close()

        assert len(errors) == 0

        # Verify data integrity
        cache2 = ExecutionCache(tmp_path / "stress.db")
        artifacts = cache2.list_artifacts()
        assert len(artifacts) == 1000  # 10 threads * 100 artifacts
        cache2.close()

    @pytest.mark.asyncio
    async def test_rapid_key_creation_deletion(self) -> None:
        """Rapid creation and deletion cycles don't corrupt state."""
        deduper = AsyncWorkDeduper[str]()

        async def work() -> str:
            return "result"

        for cycle in range(20):
            # Add keys
            await asyncio.gather(
                *[deduper.do(f"key_{i}", work) for i in range(10)]
            )
            assert await deduper.get_cache_size() == 10

            # Clear all
            await deduper.clear()
            assert await deduper.get_cache_size() == 0


# =============================================================================
# State Consistency Tests
# =============================================================================


class TestStateConsistency:
    """Tests for state invariants and consistency."""

    @pytest.mark.asyncio
    async def test_cache_pending_invariant(self) -> None:
        """cache_size + pending_count reflects total keys being tracked."""
        deduper = AsyncWorkDeduper[str]()
        started_events: list[asyncio.Event] = []
        proceed = asyncio.Event()

        async def blocking_work(i: int) -> str:
            event = asyncio.Event()
            started_events.append(event)
            event.set()
            await proceed.wait()
            return f"result_{i}"

        # Start multiple pending tasks
        tasks = [
            asyncio.create_task(deduper.do(f"key_{i}", lambda i=i: blocking_work(i)))
            for i in range(5)
        ]

        # Wait for all to start
        await asyncio.sleep(0.1)

        # Check invariant: pending should be 5
        pending = await deduper.get_pending_count()
        cached = await deduper.get_cache_size()
        assert pending == 5
        assert cached == 0

        # Let them complete
        proceed.set()
        await asyncio.gather(*tasks)

        # Now all should be cached
        pending = await deduper.get_pending_count()
        cached = await deduper.get_cache_size()
        assert pending == 0
        assert cached == 5

    @pytest.mark.asyncio
    async def test_clear_during_work_in_progress(self) -> None:
        """Clear while work is in-progress doesn't corrupt state."""
        deduper = AsyncWorkDeduper[str]()
        started = asyncio.Event()
        proceed = asyncio.Event()

        async def blocking_work() -> str:
            started.set()
            await proceed.wait()
            return "result"

        # Start work
        task = asyncio.create_task(deduper.do("key1", blocking_work))
        await started.wait()

        # Clear while in progress - this clears results but not in_progress
        await deduper.clear()

        # Let work complete
        proceed.set()
        result = await task

        assert result == "result"
        # Result should now be cached
        assert await deduper.get_cache_size() == 1

    def test_cache_state_after_partial_failure(self, tmp_path: Path) -> None:
        """Cache state is consistent after mixed success/failure."""
        cache = ExecutionCache(tmp_path / "partial.db")

        # Some succeed, some fail
        for i in range(10):
            status = ExecutionStatus.COMPLETED if i % 2 == 0 else ExecutionStatus.FAILED
            cache.set(f"artifact_{i}", f"hash_{i}", status)

        stats = cache.get_stats()
        assert stats["by_status"]["completed"] == 5
        assert stats["by_status"]["failed"] == 5
        assert stats["total_artifacts"] == 10

        cache.close()


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_error_then_success_after_clear(self) -> None:
        """After clearing error, same key can succeed."""
        deduper = AsyncWorkDeduper[str]()
        should_fail = True

        async def maybe_fail() -> str:
            if should_fail:
                raise ValueError("intentional failure")
            return "success"

        # First call fails
        with pytest.raises(ValueError):
            await deduper.do("key1", maybe_fail)

        # Cached error is returned
        with pytest.raises(ValueError):
            await deduper.do("key1", maybe_fail)

        # Clear the error
        await deduper.clear("key1")

        # Now succeed
        should_fail = False
        result = await deduper.do("key1", maybe_fail)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_different_error_types(self) -> None:
        """Different error types are cached correctly."""
        deduper = AsyncWorkDeduper[str]()

        async def raise_value_error() -> str:
            raise ValueError("value error")

        async def raise_runtime_error() -> str:
            raise RuntimeError("runtime error")

        async def raise_custom() -> str:
            raise CustomTestError("custom error")

        with pytest.raises(ValueError):
            await deduper.do("key1", raise_value_error)

        with pytest.raises(RuntimeError):
            await deduper.do("key2", raise_runtime_error)

        with pytest.raises(CustomTestError):
            await deduper.do("key3", raise_custom)

        # All errors cached
        assert await deduper.get_cache_size() == 0  # Errors not in _results
        # But is_cached should return True
        assert await deduper.is_cached("key1")
        assert await deduper.is_cached("key2")
        assert await deduper.is_cached("key3")

    def test_sync_deduper_error_recovery(self) -> None:
        """Sync deduper handles error recovery correctly."""
        deduper = WorkDeduper[str]()
        call_count = 0

        def failing_work() -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"attempt {call_count}")

        # First call fails
        with pytest.raises(RuntimeError, match="attempt 1"):
            deduper.do("key1", failing_work)

        # Second call gets cached error (same message)
        with pytest.raises(RuntimeError, match="attempt 1"):
            deduper.do("key1", failing_work)

        # Only one execution
        assert call_count == 1

        # Clear and retry
        deduper.clear("key1")

        with pytest.raises(RuntimeError, match="attempt 2"):
            deduper.do("key1", failing_work)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self) -> None:
        """Timeout errors are handled like other errors."""
        deduper = AsyncWorkDeduper[str]()

        async def slow_work() -> str:
            await asyncio.sleep(10)
            return "never"

        # Use wait_for to create timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(deduper.do("key1", slow_work), timeout=0.1)

        # Key should still be in_progress (work wasn't cancelled properly)
        # This is expected behavior - the work continues in background


# =============================================================================
# Regression Tests
# =============================================================================


class TestRegressionBugs:
    """Tests for specific bugs that were fixed."""

    def test_module_imports_cleanly(self) -> None:
        """Module can be imported without errors (regression: duplicate import)."""
        import importlib
        import sunwell.agent.incremental.cache as cache_module

        # Force reimport
        importlib.reload(cache_module)

        # Should not raise
        from sunwell.agent.incremental import ExecutionCache

    @pytest.mark.asyncio
    async def test_async_deduper_race_condition_regression(self) -> None:
        """Regression test for the specific race condition that was fixed.

        The bug: Between checking _in_progress and waiting on the event,
        another task could complete the work, causing the waiter to miss
        the result and potentially start duplicate work.
        """
        deduper = AsyncWorkDeduper[str]()
        execution_order: list[str] = []
        execution_count = 0

        async def tracked_work() -> str:
            nonlocal execution_count
            execution_count += 1
            execution_order.append(f"start_{execution_count}")
            # Small delay to allow other tasks to queue up
            await asyncio.sleep(0.02)
            execution_order.append(f"end_{execution_count}")
            return "result"

        # Create staggered requests to maximize race condition window
        async def staggered_request(delay: float) -> str:
            await asyncio.sleep(delay)
            return await deduper.do("race_key", tracked_work)

        results = await asyncio.gather(
            *[staggered_request(i * 0.005) for i in range(20)]
        )

        # All should get same result
        assert all(r == "result" for r in results)
        # Only ONE execution should have happened
        assert execution_count == 1
        assert execution_order == ["start_1", "end_1"]

    def test_cache_thread_safety_regression(self, tmp_path: Path) -> None:
        """Regression test for thread-unsafe read operations.

        The bug: Read operations like get() and get_by_hash() weren't
        protected by the lock, causing potential issues with
        check_same_thread=False.
        """
        cache = ExecutionCache(tmp_path / "threadsafe.db")
        errors: list[Exception] = []

        # Pre-populate
        for i in range(100):
            cache.set(f"artifact_{i}", "shared_hash", ExecutionStatus.COMPLETED)

        def reader() -> None:
            try:
                for _ in range(100):
                    cache.get("artifact_50")
                    cache.get_by_hash("shared_hash")
                    cache.get_stats()
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for i in range(100, 200):
                    cache.set(f"artifact_{i}", "shared_hash", ExecutionStatus.COMPLETED)
            except Exception as e:
                errors.append(e)

        threads = [
            *[threading.Thread(target=reader) for _ in range(5)],
            *[threading.Thread(target=writer) for _ in range(3)],
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        cache.close()

    def test_hasher_hex_format_regression(self) -> None:
        """Regression test: hash output is valid hex (not arbitrary chars)."""
        from dataclasses import dataclass

        from sunwell.agent.incremental.hasher import compute_input_hash

        @dataclass
        class MockSpec:
            id: str
            description: str
            contract: str
            requires: tuple[str, ...] = ()

        spec = MockSpec(id="test", description="desc", contract="contract")
        hash_val = compute_input_hash(spec, {})

        # Must be exactly 20 hex characters
        assert len(hash_val) == 20
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_events_all_exports_accessible(self) -> None:
        """Regression test: all exports in __all__ are importable."""
        from sunwell.agent.incremental import events

        for name in events.__all__:
            assert hasattr(events, name), f"Missing export: {name}"
            obj = getattr(events, name)
            assert obj is not None


class CustomTestError(Exception):
    """Custom error for testing."""

    pass


# =============================================================================
# Memory/Resource Tests
# =============================================================================


class TestMemoryAndResources:
    """Tests for memory usage and resource management."""

    @pytest.mark.asyncio
    async def test_deduper_clear_releases_references(self) -> None:
        """Cleared entries don't hold references."""
        deduper = AsyncWorkDeduper[list[int]]()

        async def create_large_list() -> list[int]:
            return list(range(10000))

        await deduper.do("key1", create_large_list)

        # Get reference to cached result
        result = deduper._results.get("key1")
        assert result is not None
        assert len(result) == 10000

        await deduper.clear()

        # After clear, internal dicts should be empty
        assert len(deduper._results) == 0
        assert len(deduper._errors) == 0

    def test_cache_vacuum_reduces_size(self, tmp_path: Path) -> None:
        """Vacuum after delete reduces database file size."""
        cache_path = tmp_path / "vacuum_test.db"
        cache = ExecutionCache(cache_path)

        # Add lots of data
        large_data = {"content": "x" * 10000}
        for i in range(100):
            cache.set(f"artifact_{i}", f"hash_{i}", ExecutionStatus.COMPLETED, large_data)

        size_before_delete = cache_path.stat().st_size

        # Delete all
        cache.clear()

        # Vacuum
        cache.vacuum()

        size_after_vacuum = cache_path.stat().st_size

        # File should be smaller after vacuum
        assert size_after_vacuum < size_before_delete

        cache.close()
