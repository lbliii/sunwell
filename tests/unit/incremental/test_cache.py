"""Tests for ExecutionCache thread-safety and functionality.

Tests concurrent access, provenance queries, and cache operations.
"""

import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from sunwell.agent.incremental.cache import (
    CachedExecution,
    ExecutionCache,
    ExecutionStatus,
)


# =============================================================================
# Basic Cache Operations
# =============================================================================


class TestExecutionCacheBasic:
    """Basic cache functionality tests."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_set_and_get(self, cache: ExecutionCache) -> None:
        """Basic set and get operations work."""
        cache.set("artifact_1", "hash_123", ExecutionStatus.COMPLETED, {"output": "test"})

        result = cache.get("artifact_1")

        assert result is not None
        assert result.artifact_id == "artifact_1"
        assert result.input_hash == "hash_123"
        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {"output": "test"}

    def test_get_missing_returns_none(self, cache: ExecutionCache) -> None:
        """Getting non-existent artifact returns None."""
        result = cache.get("nonexistent")
        assert result is None

    def test_get_by_hash(self, cache: ExecutionCache) -> None:
        """Get artifacts by input hash."""
        cache.set("artifact_1", "shared_hash", ExecutionStatus.COMPLETED)
        cache.set("artifact_2", "shared_hash", ExecutionStatus.COMPLETED)
        cache.set("artifact_3", "different_hash", ExecutionStatus.COMPLETED)

        results = cache.get_by_hash("shared_hash")

        assert len(results) == 2
        ids = {r.artifact_id for r in results}
        assert ids == {"artifact_1", "artifact_2"}

    def test_upsert_updates_existing(self, cache: ExecutionCache) -> None:
        """Setting same artifact_id updates the record."""
        cache.set("artifact_1", "hash_v1", ExecutionStatus.PENDING)
        cache.set("artifact_1", "hash_v2", ExecutionStatus.COMPLETED, {"new": "result"})

        result = cache.get("artifact_1")

        assert result is not None
        assert result.input_hash == "hash_v2"
        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {"new": "result"}

    def test_delete(self, cache: ExecutionCache) -> None:
        """Delete removes artifact."""
        cache.set("artifact_1", "hash", ExecutionStatus.COMPLETED)

        deleted = cache.delete("artifact_1")
        assert deleted is True

        result = cache.get("artifact_1")
        assert result is None

        # Deleting again returns False
        deleted_again = cache.delete("artifact_1")
        assert deleted_again is False

    def test_record_skip_increments_count(self, cache: ExecutionCache) -> None:
        """record_skip increments skip_count."""
        cache.set("artifact_1", "hash", ExecutionStatus.COMPLETED)

        cache.record_skip("artifact_1")
        cache.record_skip("artifact_1")
        cache.record_skip("artifact_1")

        result = cache.get("artifact_1")
        assert result is not None
        assert result.skip_count == 3

    def test_all_statuses(self, cache: ExecutionCache) -> None:
        """All ExecutionStatus values work correctly."""
        for status in ExecutionStatus:
            cache.set(f"artifact_{status.value}", "hash", status)
            result = cache.get(f"artifact_{status.value}")
            assert result is not None
            assert result.status == status


# =============================================================================
# Provenance Tracking
# =============================================================================


class TestProvenanceTracking:
    """Tests for provenance (dependency) tracking."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_add_and_get_dependencies(self, cache: ExecutionCache) -> None:
        """Add provenance and query direct dependencies."""
        # B depends on A
        cache.add_provenance("B", "A", "requires")

        deps = cache.get_direct_dependencies("B")
        assert deps == ["A"]

    def test_get_direct_dependents(self, cache: ExecutionCache) -> None:
        """Query which artifacts depend on a given artifact."""
        # B and C both depend on A
        cache.add_provenance("B", "A", "requires")
        cache.add_provenance("C", "A", "requires")

        dependents = cache.get_direct_dependents("A")
        assert set(dependents) == {"B", "C"}

    def test_get_upstream_transitive(self, cache: ExecutionCache) -> None:
        """Upstream query finds transitive dependencies."""
        # C -> B -> A
        cache.add_provenance("C", "B", "requires")
        cache.add_provenance("B", "A", "requires")

        upstream = cache.get_upstream("C")
        assert upstream == ["B", "A"]  # Ordered by depth

    def test_get_downstream_transitive(self, cache: ExecutionCache) -> None:
        """Downstream query finds transitive dependents."""
        # C -> B -> A (A is upstream of C)
        cache.add_provenance("C", "B", "requires")
        cache.add_provenance("B", "A", "requires")

        downstream = cache.get_downstream("A")
        assert downstream == ["B", "C"]  # Ordered by depth

    def test_diamond_dependency(self, cache: ExecutionCache) -> None:
        """Diamond dependency pattern is handled correctly."""
        #     D
        #    / \
        #   B   C
        #    \ /
        #     A
        cache.add_provenance("B", "A", "requires")
        cache.add_provenance("C", "A", "requires")
        cache.add_provenance("D", "B", "requires")
        cache.add_provenance("D", "C", "requires")

        upstream_d = cache.get_upstream("D")
        assert set(upstream_d) == {"A", "B", "C"}

        downstream_a = cache.get_downstream("A")
        assert set(downstream_a) == {"B", "C", "D"}

    def test_invalidate_downstream(self, cache: ExecutionCache) -> None:
        """invalidate_downstream sets status to pending."""
        # Set up artifacts
        cache.set("A", "hash_a", ExecutionStatus.COMPLETED)
        cache.set("B", "hash_b", ExecutionStatus.COMPLETED)
        cache.set("C", "hash_c", ExecutionStatus.COMPLETED)

        # B and C depend on A
        cache.add_provenance("B", "A", "requires")
        cache.add_provenance("C", "A", "requires")

        # Invalidate downstream of A
        invalidated = cache.invalidate_downstream("A")

        assert set(invalidated) == {"B", "C"}

        # Check statuses changed
        b = cache.get("B")
        c = cache.get("C")
        a = cache.get("A")

        assert b is not None and b.status == ExecutionStatus.PENDING
        assert c is not None and c.status == ExecutionStatus.PENDING
        assert a is not None and a.status == ExecutionStatus.COMPLETED  # Source unchanged

    def test_delete_removes_provenance(self, cache: ExecutionCache) -> None:
        """Deleting an artifact removes its provenance entries."""
        cache.add_provenance("B", "A", "requires")
        cache.add_provenance("C", "B", "requires")

        cache.delete("B")

        # B's dependencies and dependents should be gone
        assert cache.get_direct_dependencies("B") == []
        assert cache.get_direct_dependents("B") == []


# =============================================================================
# Thread Safety
# =============================================================================


class TestThreadSafety:
    """Tests for concurrent access to the cache."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_concurrent_writes(self, cache: ExecutionCache) -> None:
        """Multiple threads can write concurrently without corruption."""
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(50):
                    cache.set(
                        f"artifact_{thread_id}_{i}",
                        f"hash_{thread_id}_{i}",
                        ExecutionStatus.COMPLETED,
                        {"thread": thread_id, "index": i},
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Verify all artifacts were written
        artifacts = cache.list_artifacts()
        assert len(artifacts) == 250  # 5 threads * 50 artifacts

    def test_concurrent_reads_and_writes(self, cache: ExecutionCache) -> None:
        """Concurrent reads and writes don't cause corruption."""
        # Pre-populate some data
        for i in range(100):
            cache.set(f"artifact_{i}", f"hash_{i}", ExecutionStatus.COMPLETED)

        errors: list[Exception] = []
        read_results: list[CachedExecution | None] = []

        def reader() -> None:
            try:
                for i in range(100):
                    result = cache.get(f"artifact_{i}")
                    read_results.append(result)
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for i in range(100, 200):
                    cache.set(f"artifact_{i}", f"hash_{i}", ExecutionStatus.COMPLETED)
            except Exception as e:
                errors.append(e)

        readers = [threading.Thread(target=reader) for _ in range(3)]
        writers = [threading.Thread(target=writer) for _ in range(2)]

        all_threads = readers + writers
        for t in all_threads:
            t.start()
        for t in all_threads:
            t.join()

        assert len(errors) == 0
        # All reads should have succeeded (None or valid result)
        assert len(read_results) == 300  # 3 readers * 100 reads

    def test_concurrent_provenance_operations(self, cache: ExecutionCache) -> None:
        """Concurrent provenance operations are thread-safe."""
        errors: list[Exception] = []

        def add_provenance(thread_id: int) -> None:
            try:
                for i in range(20):
                    cache.add_provenance(f"dep_{thread_id}_{i}", f"base_{thread_id}", "requires")
            except Exception as e:
                errors.append(e)

        def query_provenance(thread_id: int) -> None:
            try:
                for _ in range(20):
                    cache.get_upstream(f"dep_{thread_id}_0")
                    cache.get_downstream(f"base_{thread_id}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=add_provenance, args=(i,)))
            threads.append(threading.Thread(target=query_provenance, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_skip_recording(self, cache: ExecutionCache) -> None:
        """Concurrent skip recordings don't lose counts."""
        cache.set("artifact_1", "hash", ExecutionStatus.COMPLETED)

        errors: list[Exception] = []

        def record_skips() -> None:
            try:
                for _ in range(100):
                    cache.record_skip("artifact_1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_skips) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        result = cache.get("artifact_1")
        assert result is not None
        assert result.skip_count == 1000  # 10 threads * 100 skips


# =============================================================================
# Execution Runs
# =============================================================================


class TestExecutionRuns:
    """Tests for execution run tracking."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_start_and_finish_run(self, cache: ExecutionCache) -> None:
        """Start and finish run tracking."""
        cache.start_run("run_001", total_artifacts=10)

        run = cache.get_run("run_001")
        assert run is not None
        assert run["status"] == "running"
        assert run["total_artifacts"] == 10

        cache.finish_run("run_001", executed=8, skipped=2, failed=0)

        run = cache.get_run("run_001")
        assert run is not None
        assert run["status"] == "completed"
        assert run["executed"] == 8
        assert run["skipped"] == 2
        assert run["failed"] == 0

    def test_get_nonexistent_run(self, cache: ExecutionCache) -> None:
        """Getting non-existent run returns None."""
        run = cache.get_run("nonexistent")
        assert run is None


# =============================================================================
# Goal Tracking
# =============================================================================


class TestGoalTracking:
    """Tests for goal-based tracking."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_record_and_get_goal_execution(self, cache: ExecutionCache) -> None:
        """Record and retrieve goal execution."""
        cache.record_goal_execution(
            "goal_hash_123",
            ["artifact_a", "artifact_b", "artifact_c"],
            execution_time_ms=1500.0,
        )

        artifacts = cache.get_artifacts_for_goal("goal_hash_123")
        assert artifacts == ["artifact_a", "artifact_b", "artifact_c"]

        goal = cache.get_goal_execution("goal_hash_123")
        assert goal is not None
        assert goal["goal_hash"] == "goal_hash_123"
        assert goal["artifact_ids"] == ["artifact_a", "artifact_b", "artifact_c"]
        assert goal["execution_time_ms"] == 1500.0

    def test_get_nonexistent_goal(self, cache: ExecutionCache) -> None:
        """Getting non-existent goal returns None."""
        assert cache.get_artifacts_for_goal("nonexistent") is None
        assert cache.get_goal_execution("nonexistent") is None


# =============================================================================
# Statistics and Maintenance
# =============================================================================


class TestStatisticsAndMaintenance:
    """Tests for statistics and maintenance operations."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_get_stats(self, cache: ExecutionCache) -> None:
        """Statistics are calculated correctly."""
        cache.set("a1", "h1", ExecutionStatus.COMPLETED, execution_time_ms=100)
        cache.set("a2", "h2", ExecutionStatus.COMPLETED, execution_time_ms=200)
        cache.set("a3", "h3", ExecutionStatus.FAILED)
        cache.set("a4", "h4", ExecutionStatus.SKIPPED)

        cache.record_skip("a1")
        cache.record_skip("a1")

        stats = cache.get_stats()

        assert stats["total_artifacts"] == 4
        assert stats["by_status"]["completed"] == 2
        assert stats["by_status"]["failed"] == 1
        assert stats["by_status"]["skipped"] == 1
        assert stats["total_skips"] == 2
        assert stats["avg_execution_time_ms"] == 150.0  # (100+200)/2

    def test_clear_all(self, cache: ExecutionCache) -> None:
        """Clear removes all data."""
        cache.set("a1", "h1", ExecutionStatus.COMPLETED)
        cache.set("a2", "h2", ExecutionStatus.COMPLETED)
        cache.add_provenance("a2", "a1", "requires")
        cache.start_run("run1", 2)

        cache.clear()

        assert cache.get("a1") is None
        assert cache.get("a2") is None
        assert cache.get_direct_dependencies("a2") == []
        assert cache.list_artifacts() == []

    def test_vacuum(self, cache: ExecutionCache) -> None:
        """Vacuum doesn't error."""
        cache.set("a1", "h1", ExecutionStatus.COMPLETED)
        cache.delete("a1")
        cache.vacuum()  # Should not raise

    def test_list_artifacts(self, cache: ExecutionCache) -> None:
        """list_artifacts returns all artifacts."""
        cache.set("a1", "h1", ExecutionStatus.COMPLETED)
        cache.set("a2", "h2", ExecutionStatus.FAILED)

        artifacts = cache.list_artifacts()

        assert len(artifacts) == 2
        ids = {a["artifact_id"] for a in artifacts}
        assert ids == {"a1", "a2"}

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager properly closes connection."""
        cache_path = tmp_path / "context_test.db"

        with ExecutionCache(cache_path) as cache:
            cache.set("a1", "h1", ExecutionStatus.COMPLETED)
            result = cache.get("a1")
            assert result is not None

        # Connection should be closed, but this is hard to verify directly
        # At minimum, no exception should be raised
