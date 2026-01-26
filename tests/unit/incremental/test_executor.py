"""Tests for should_skip, ExecutionPlan, and skip decision logic.

Tests edge cases in skip decision making and execution planning.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from sunwell.agent.incremental.cache import ExecutionCache, ExecutionStatus
from sunwell.agent.incremental.executor import (
    ExecutionPlan,
    IncrementalResult,
    SkipDecision,
    SkipReason,
    should_skip,
)


# =============================================================================
# Mock ArtifactSpec for testing
# =============================================================================


@dataclass
class MockArtifactSpec:
    """Mock artifact spec for testing."""

    id: str
    description: str = "test artifact"
    contract: str = "test contract"
    requires: tuple[str, ...] = ()
    produces_file: str | None = None


# =============================================================================
# should_skip Tests
# =============================================================================


class TestShouldSkip:
    """Tests for the should_skip function."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ExecutionCache:
        """Create a temporary cache for testing."""
        cache_path = tmp_path / "test_cache.db"
        cache = ExecutionCache(cache_path)
        yield cache
        cache.close()

    def test_no_cache_entry(self, cache: ExecutionCache) -> None:
        """When no cache entry exists, should not skip."""
        spec = MockArtifactSpec(id="artifact_1")

        decision = should_skip(spec, cache, dependency_hashes={})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.NO_CACHE
        assert decision.artifact_id == "artifact_1"
        assert decision.current_hash != ""
        assert decision.previous_hash is None

    def test_force_rerun_overrides_cache(self, cache: ExecutionCache) -> None:
        """force_rerun=True always prevents skipping."""
        spec = MockArtifactSpec(id="artifact_1")

        # Pre-populate cache with matching hash
        hash_val = should_skip(spec, cache, {}).current_hash
        cache.set("artifact_1", hash_val, ExecutionStatus.COMPLETED, {"result": "cached"})

        decision = should_skip(spec, cache, dependency_hashes={}, force_rerun=True)

        assert decision.can_skip is False
        assert decision.reason == SkipReason.FORCE_RERUN

    def test_previous_failed_status(self, cache: ExecutionCache) -> None:
        """When previous execution failed, should not skip (retry)."""
        spec = MockArtifactSpec(id="artifact_1")

        cache.set("artifact_1", "some_hash", ExecutionStatus.FAILED, error="previous error")

        decision = should_skip(spec, cache, dependency_hashes={})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.PREVIOUS_FAILED

    def test_previous_pending_status(self, cache: ExecutionCache) -> None:
        """When previous execution is pending, should not skip."""
        spec = MockArtifactSpec(id="artifact_1")

        cache.set("artifact_1", "some_hash", ExecutionStatus.PENDING)

        decision = should_skip(spec, cache, dependency_hashes={})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.PREVIOUS_INCOMPLETE

    def test_previous_running_status(self, cache: ExecutionCache) -> None:
        """When previous execution is running, should not skip."""
        spec = MockArtifactSpec(id="artifact_1")

        cache.set("artifact_1", "some_hash", ExecutionStatus.RUNNING)

        decision = should_skip(spec, cache, dependency_hashes={})

        assert decision.can_skip is False
        assert decision.reason == SkipReason.PREVIOUS_INCOMPLETE

    def test_hash_changed(self, cache: ExecutionCache) -> None:
        """When hash changed, should not skip."""
        spec = MockArtifactSpec(id="artifact_1")

        # Cache with old hash
        cache.set("artifact_1", "old_hash", ExecutionStatus.COMPLETED, {"result": "old"})

        decision = should_skip(spec, cache, dependency_hashes={})

        # Current hash will differ from "old_hash"
        assert decision.can_skip is False
        assert decision.reason == SkipReason.HASH_CHANGED
        assert decision.previous_hash == "old_hash"
        assert decision.current_hash != "old_hash"

    def test_can_skip_when_hash_matches(self, cache: ExecutionCache) -> None:
        """When hash matches and status is completed, can skip."""
        spec = MockArtifactSpec(id="artifact_1")

        # First, compute the hash
        hash_val = should_skip(spec, cache, {}).current_hash

        # Cache with matching hash
        cache.set("artifact_1", hash_val, ExecutionStatus.COMPLETED, {"result": "cached"})

        decision = should_skip(spec, cache, dependency_hashes={})

        assert decision.can_skip is True
        assert decision.reason == SkipReason.UNCHANGED_SUCCESS
        assert decision.cached_result == {"result": "cached"}

    def test_dependency_hash_affects_skip_decision(self, cache: ExecutionCache) -> None:
        """Changes in dependency hashes cause hash mismatch."""
        spec = MockArtifactSpec(id="artifact_1", requires=("dep_a",))

        # Compute hash with one dependency state
        decision1 = should_skip(spec, cache, dependency_hashes={"dep_a": "hash_v1"})
        cache.set("artifact_1", decision1.current_hash, ExecutionStatus.COMPLETED)

        # Now with changed dependency
        decision2 = should_skip(spec, cache, dependency_hashes={"dep_a": "hash_v2"})

        assert decision2.can_skip is False
        assert decision2.reason == SkipReason.HASH_CHANGED
        assert decision2.current_hash != decision1.current_hash

    def test_skipped_status_allows_skip(self, cache: ExecutionCache) -> None:
        """SKIPPED status with matching hash allows skip."""
        spec = MockArtifactSpec(id="artifact_1")

        hash_val = should_skip(spec, cache, {}).current_hash
        cache.set("artifact_1", hash_val, ExecutionStatus.SKIPPED, {"result": "from_skip"})

        decision = should_skip(spec, cache, dependency_hashes={})

        # SKIPPED is a successful terminal state
        assert decision.can_skip is True
        assert decision.reason == SkipReason.UNCHANGED_SUCCESS


# =============================================================================
# SkipDecision Tests
# =============================================================================


class TestSkipDecision:
    """Tests for SkipDecision dataclass."""

    def test_skip_decision_is_frozen(self) -> None:
        """SkipDecision is immutable."""
        decision = SkipDecision(
            artifact_id="test",
            can_skip=True,
            reason=SkipReason.UNCHANGED_SUCCESS,
            current_hash="hash123",
        )

        with pytest.raises(AttributeError):
            decision.can_skip = False  # type: ignore[misc]

    def test_skip_decision_optional_fields(self) -> None:
        """Optional fields default to None."""
        decision = SkipDecision(
            artifact_id="test",
            can_skip=False,
            reason=SkipReason.NO_CACHE,
            current_hash="hash123",
        )

        assert decision.previous_hash is None
        assert decision.cached_result is None


# =============================================================================
# ExecutionPlan Tests
# =============================================================================


class TestExecutionPlan:
    """Tests for ExecutionPlan dataclass."""

    def test_total_property(self) -> None:
        """total returns sum of execute and skip lists."""
        plan = ExecutionPlan(
            to_execute=["a", "b", "c"],
            to_skip=["d", "e"],
            decisions={},
            computed_hashes={},
        )

        assert plan.total == 5

    def test_skip_percentage_with_items(self) -> None:
        """skip_percentage calculates correctly."""
        plan = ExecutionPlan(
            to_execute=["a", "b"],
            to_skip=["c", "d", "e"],
            decisions={},
            computed_hashes={},
        )

        assert plan.skip_percentage == 60.0

    def test_skip_percentage_empty(self) -> None:
        """skip_percentage returns 0 for empty plan."""
        plan = ExecutionPlan(
            to_execute=[],
            to_skip=[],
            decisions={},
            computed_hashes={},
        )

        assert plan.skip_percentage == 0.0

    def test_skip_percentage_all_skip(self) -> None:
        """skip_percentage returns 100 when all skip."""
        plan = ExecutionPlan(
            to_execute=[],
            to_skip=["a", "b", "c"],
            decisions={},
            computed_hashes={},
        )

        assert plan.skip_percentage == 100.0

    def test_to_dict(self) -> None:
        """to_dict produces valid JSON-serializable output."""
        decision = SkipDecision(
            artifact_id="a",
            can_skip=True,
            reason=SkipReason.UNCHANGED_SUCCESS,
            current_hash="hash_a",
            previous_hash="hash_a",
        )

        plan = ExecutionPlan(
            to_execute=["b"],
            to_skip=["a"],
            decisions={"a": decision},
            computed_hashes={"a": "hash_a", "b": "hash_b"},
        )

        d = plan.to_dict()

        assert d["total_artifacts"] == 2
        assert d["to_execute"] == 1
        assert d["to_skip"] == 1
        assert d["skip_percentage"] == 50.0
        assert d["execute_ids"] == ["b"]
        assert d["skip_ids"] == ["a"]
        assert "a" in d["decisions"]
        assert d["decisions"]["a"]["reason"] == "unchanged_success"


# =============================================================================
# IncrementalResult Tests
# =============================================================================


class TestIncrementalResult:
    """Tests for IncrementalResult dataclass."""

    def test_success_when_no_failures(self) -> None:
        """success is True when no failures."""
        result = IncrementalResult(
            completed={"a": {}, "b": {}},
            failed={},
            skipped={"c": None},
            run_id="test",
        )

        assert result.success is True

    def test_success_false_with_failures(self) -> None:
        """success is False when failures exist."""
        result = IncrementalResult(
            completed={"a": {}},
            failed={"b": "error message"},
            skipped={},
            run_id="test",
        )

        assert result.success is False

    def test_total_property(self) -> None:
        """total counts all artifacts."""
        result = IncrementalResult(
            completed={"a": {}, "b": {}},
            failed={"c": "error"},
            skipped={"d": None, "e": None},
            run_id="test",
        )

        assert result.total == 5

    def test_empty_result(self) -> None:
        """Empty result is valid and successful."""
        result = IncrementalResult(
            completed={},
            failed={},
            skipped={},
            run_id="test",
        )

        assert result.success is True
        assert result.total == 0


# =============================================================================
# SkipReason Tests
# =============================================================================


class TestSkipReason:
    """Tests for SkipReason enum."""

    def test_all_reasons_have_values(self) -> None:
        """All reasons have string values."""
        for reason in SkipReason:
            assert isinstance(reason.value, str)
            assert len(reason.value) > 0

    def test_can_skip_reasons(self) -> None:
        """Identify which reasons allow skipping."""
        can_skip_reasons = {SkipReason.UNCHANGED_SUCCESS}

        cannot_skip_reasons = {
            SkipReason.NO_CACHE,
            SkipReason.HASH_CHANGED,
            SkipReason.PREVIOUS_FAILED,
            SkipReason.FORCE_RERUN,
            SkipReason.DEPENDENCY_CHANGED,
            SkipReason.PREVIOUS_INCOMPLETE,
        }

        assert can_skip_reasons.isdisjoint(cannot_skip_reasons)
        assert len(can_skip_reasons) + len(cannot_skip_reasons) == len(SkipReason)
