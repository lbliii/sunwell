"""Tests for RFC-074 ExecutionCache."""

from pathlib import Path

import pytest

from sunwell.agent.incremental.cache import (
    ExecutionCache,
    ExecutionStatus,
)


@pytest.fixture
def cache(tmp_path: Path) -> ExecutionCache:
    """Create a test cache."""
    return ExecutionCache(tmp_path / "test_cache.db")


class TestExecutionCache:
    """Tests for ExecutionCache."""

    def test_set_and_get(self, cache: ExecutionCache) -> None:
        """Can set and get cached execution."""
        cache.set(
            "artifact_a",
            "hash123",
            ExecutionStatus.COMPLETED,
            {"output": "value"},
            execution_time_ms=100,
        )

        cached = cache.get("artifact_a")

        assert cached is not None
        assert cached.artifact_id == "artifact_a"
        assert cached.input_hash == "hash123"
        assert cached.status == ExecutionStatus.COMPLETED
        assert cached.result == {"output": "value"}
        assert cached.execution_time_ms == 100
        assert cached.skip_count == 0

    def test_get_nonexistent(self, cache: ExecutionCache) -> None:
        """Getting nonexistent artifact returns None."""
        cached = cache.get("nonexistent")

        assert cached is None

    def test_upsert(self, cache: ExecutionCache) -> None:
        """Setting an existing artifact updates it."""
        cache.set("artifact_a", "hash1", ExecutionStatus.RUNNING)
        cache.set("artifact_a", "hash2", ExecutionStatus.COMPLETED, {"result": "done"})

        cached = cache.get("artifact_a")

        assert cached is not None
        assert cached.input_hash == "hash2"
        assert cached.status == ExecutionStatus.COMPLETED
        assert cached.result == {"result": "done"}

    def test_record_skip(self, cache: ExecutionCache) -> None:
        """Recording skip increments skip_count."""
        cache.set("artifact_a", "hash123", ExecutionStatus.COMPLETED)

        cache.record_skip("artifact_a")
        cache.record_skip("artifact_a")
        cache.record_skip("artifact_a")

        cached = cache.get("artifact_a")
        assert cached is not None
        assert cached.skip_count == 3

    def test_delete(self, cache: ExecutionCache) -> None:
        """Can delete cached execution."""
        cache.set("artifact_a", "hash123", ExecutionStatus.COMPLETED)

        deleted = cache.delete("artifact_a")
        cached = cache.get("artifact_a")

        assert deleted is True
        assert cached is None

    def test_delete_nonexistent(self, cache: ExecutionCache) -> None:
        """Deleting nonexistent returns False."""
        deleted = cache.delete("nonexistent")

        assert deleted is False


class TestProvenance:
    """Tests for provenance tracking."""

    def test_add_provenance(self, cache: ExecutionCache) -> None:
        """Can add provenance relationships."""
        cache.add_provenance("B", "A", "requires")

        deps = cache.get_direct_dependencies("B")
        dependents = cache.get_direct_dependents("A")

        assert deps == ["A"]
        assert dependents == ["B"]

    def test_get_upstream(self, cache: ExecutionCache) -> None:
        """Can get upstream artifacts (transitive dependencies)."""
        # A → B → C (C depends on B, B depends on A)
        cache.add_provenance("B", "A")
        cache.add_provenance("C", "B")

        upstream = cache.get_upstream("C")

        assert set(upstream) == {"A", "B"}

    def test_get_downstream(self, cache: ExecutionCache) -> None:
        """Can get downstream artifacts (transitive dependents)."""
        # A → B → C (C depends on B, B depends on A)
        cache.add_provenance("B", "A")
        cache.add_provenance("C", "B")

        downstream = cache.get_downstream("A")

        assert set(downstream) == {"B", "C"}

    def test_invalidate_downstream(self, cache: ExecutionCache) -> None:
        """Changing an artifact invalidates all downstream."""
        # Set up provenance: A → B → C
        cache.add_provenance("B", "A")
        cache.add_provenance("C", "B")

        # All completed
        cache.set("A", "hash_a", ExecutionStatus.COMPLETED)
        cache.set("B", "hash_b", ExecutionStatus.COMPLETED)
        cache.set("C", "hash_c", ExecutionStatus.COMPLETED)

        # Invalidate A's downstream
        invalidated = cache.invalidate_downstream("A")

        assert set(invalidated) == {"B", "C"}
        assert cache.get("B") is not None
        assert cache.get("B").status == ExecutionStatus.PENDING
        assert cache.get("C") is not None
        assert cache.get("C").status == ExecutionStatus.PENDING

    def test_upstream_respects_max_depth(self, cache: ExecutionCache) -> None:
        """Upstream query respects max_depth."""
        # Long chain: A → B → C → D → E
        cache.add_provenance("B", "A")
        cache.add_provenance("C", "B")
        cache.add_provenance("D", "C")
        cache.add_provenance("E", "D")

        upstream = cache.get_upstream("E", max_depth=2)

        # Only D and C (depth 1 and 2)
        assert "D" in upstream
        assert "C" in upstream
        # A and B should be excluded (depth 3 and 4)
        assert len(upstream) == 2


class TestExecutionRuns:
    """Tests for execution run tracking."""

    def test_start_and_finish_run(self, cache: ExecutionCache) -> None:
        """Can track execution runs."""
        cache.start_run("run1", total_artifacts=10)

        run = cache.get_run("run1")
        assert run is not None
        assert run["status"] == "running"
        assert run["total_artifacts"] == 10

        cache.finish_run("run1", executed=8, skipped=2, failed=0, status="completed")

        run = cache.get_run("run1")
        assert run is not None
        assert run["status"] == "completed"
        assert run["executed"] == 8
        assert run["skipped"] == 2
        assert run["failed"] == 0


class TestStatistics:
    """Tests for cache statistics."""

    def test_get_stats(self, cache: ExecutionCache) -> None:
        """Can get cache statistics."""
        cache.set("a", "hash_a", ExecutionStatus.COMPLETED, execution_time_ms=100)
        cache.set("b", "hash_b", ExecutionStatus.COMPLETED, execution_time_ms=200)
        cache.set("c", "hash_c", ExecutionStatus.FAILED)

        cache.record_skip("a")
        cache.record_skip("a")

        stats = cache.get_stats()

        assert stats["total_artifacts"] == 3
        assert stats["by_status"]["completed"] == 2
        assert stats["by_status"]["failed"] == 1
        assert stats["total_skips"] == 2
        assert stats["avg_execution_time_ms"] == 150.0

    def test_clear(self, cache: ExecutionCache) -> None:
        """Can clear all cached data."""
        cache.set("a", "hash_a", ExecutionStatus.COMPLETED)
        cache.set("b", "hash_b", ExecutionStatus.COMPLETED)
        cache.add_provenance("b", "a")

        cache.clear()

        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get_direct_dependencies("b") == []


class TestContextManager:
    """Tests for context manager protocol."""

    def test_context_manager(self, tmp_path: Path) -> None:
        """Cache works as context manager."""
        cache_path = tmp_path / "ctx_cache.db"

        with ExecutionCache(cache_path) as cache:
            cache.set("a", "hash_a", ExecutionStatus.COMPLETED)
            cached = cache.get("a")
            assert cached is not None

        # After exiting, connection is closed
        # But file persists
        assert cache_path.exists()
