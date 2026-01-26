"""Property-based tests for incremental package using Hypothesis.

Tests invariants and properties that should hold for all inputs.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from sunwell.agent.incremental.hasher import (
    compute_input_hash,
    compute_spec_hash,
    create_artifact_hash,
)


# =============================================================================
# Mock ArtifactSpec for property testing
# =============================================================================


@dataclass
class MockArtifactSpec:
    """Mock artifact spec for testing."""

    id: str
    description: str
    contract: str
    requires: tuple[str, ...] = ()


# =============================================================================
# Hasher Property Tests
# =============================================================================


class TestHasherProperties:
    """Property-based tests for hashing functions."""

    @given(
        id=st.text(min_size=0, max_size=100),
        description=st.text(min_size=0, max_size=500),
        contract=st.text(min_size=0, max_size=500),
    )
    @settings(max_examples=200)
    def test_hash_always_20_hex_chars(
        self, id: str, description: str, contract: str
    ) -> None:
        """Hash is always exactly 20 hex characters for any input."""
        spec = MockArtifactSpec(id=id, description=description, contract=contract)
        hash_val = compute_input_hash(spec, {})

        assert len(hash_val) == 20
        assert all(c in "0123456789abcdef" for c in hash_val)

    @given(
        id=st.text(min_size=0, max_size=100),
        description=st.text(min_size=0, max_size=500),
        contract=st.text(min_size=0, max_size=500),
    )
    @settings(max_examples=200)
    def test_hash_is_deterministic(
        self, id: str, description: str, contract: str
    ) -> None:
        """Same inputs always produce same hash."""
        spec = MockArtifactSpec(id=id, description=description, contract=contract)

        hash1 = compute_input_hash(spec, {})
        hash2 = compute_input_hash(spec, {})

        assert hash1 == hash2

    @given(
        id=st.text(min_size=1, max_size=50),
        desc1=st.text(min_size=1, max_size=100),
        desc2=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_different_descriptions_usually_different_hashes(
        self, id: str, desc1: str, desc2: str
    ) -> None:
        """Different descriptions produce different hashes (except collisions)."""
        if desc1 == desc2:
            return  # Skip if descriptions are the same

        spec1 = MockArtifactSpec(id=id, description=desc1, contract="contract")
        spec2 = MockArtifactSpec(id=id, description=desc2, contract="contract")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        # Different descriptions should produce different hashes
        # (collision probability is extremely low with 80-bit hashes)
        assert hash1 != hash2

    @given(
        deps=st.lists(
            st.tuples(st.text(min_size=1, max_size=20), st.text(min_size=1, max_size=20)),
            min_size=0,
            max_size=20,
            unique_by=lambda x: x[0],  # Unique keys
        )
    )
    @settings(max_examples=100)
    def test_dependency_order_doesnt_matter(
        self, deps: list[tuple[str, str]]
    ) -> None:
        """Dependency hashes are processed in deterministic order."""
        spec = MockArtifactSpec(
            id="test",
            description="desc",
            contract="contract",
            requires=tuple(d[0] for d in deps),
        )

        dep_hashes = dict(deps)

        # Compute hash multiple times with dict in different orders
        hash1 = compute_input_hash(spec, dep_hashes)
        hash2 = compute_input_hash(spec, dict(reversed(list(dep_hashes.items()))))

        assert hash1 == hash2

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_spec_hash_always_20_hex_chars(self, text: str) -> None:
        """spec_hash is always exactly 20 hex characters."""
        spec = MockArtifactSpec(id=text, description=text, contract=text)
        hash_val = compute_spec_hash(spec)

        assert len(hash_val) == 20
        assert all(c in "0123456789abcdef" for c in hash_val)

    @given(
        id=st.text(min_size=1, max_size=50),
        deps=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_artifact_hash_has_timestamp(self, id: str, deps: list[str]) -> None:
        """create_artifact_hash includes a reasonable timestamp."""
        import time

        spec = MockArtifactSpec(
            id=id,
            description="desc",
            contract="contract",
            requires=tuple(deps),
        )

        before = time.time()
        ah = create_artifact_hash(spec, {d: f"hash_{i}" for i, d in enumerate(deps)})
        after = time.time()

        assert ah.artifact_id == id
        assert len(ah.input_hash) == 20
        assert before <= ah.computed_at <= after


# =============================================================================
# Cache Property Tests
# =============================================================================


class TestCacheProperties:
    """Property-based tests for cache operations."""

    @given(
        artifact_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isprintable()),
        input_hash=st.text(min_size=20, max_size=20, alphabet="0123456789abcdef"),
    )
    @settings(max_examples=50)
    def test_set_then_get_roundtrip(
        self, artifact_id: str, input_hash: str
    ) -> None:
        """Setting and getting an artifact preserves data."""
        import tempfile

        from sunwell.agent.incremental.cache import ExecutionCache, ExecutionStatus

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "cache.db"
            cache = ExecutionCache(cache_path)

            try:
                cache.set(artifact_id, input_hash, ExecutionStatus.COMPLETED)
                result = cache.get(artifact_id)

                assert result is not None
                assert result.artifact_id == artifact_id
                assert result.input_hash == input_hash
                assert result.status == ExecutionStatus.COMPLETED
            finally:
                cache.close()

    @given(
        ids=st.lists(
            st.text(min_size=1, max_size=30).filter(lambda x: x.isprintable()),
            min_size=1,
            max_size=20,
            unique=True,
        )
    )
    @settings(max_examples=30)
    def test_list_artifacts_contains_all_added(self, ids: list[str]) -> None:
        """list_artifacts returns all added artifacts."""
        import tempfile

        from sunwell.agent.incremental.cache import ExecutionCache, ExecutionStatus

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "cache.db"
            cache = ExecutionCache(cache_path)

            try:
                for id in ids:
                    cache.set(id, "hash", ExecutionStatus.COMPLETED)

                artifacts = cache.list_artifacts()
                artifact_ids = {a["artifact_id"] for a in artifacts}

                assert artifact_ids == set(ids)
            finally:
                cache.close()


# =============================================================================
# Deduper Property Tests
# =============================================================================


class TestDeduperProperties:
    """Property-based tests for deduplication."""

    @given(keys=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=30, unique=True))
    @settings(max_examples=50)
    def test_unique_keys_all_execute(self, keys: list[str]) -> None:
        """Each unique key executes exactly once."""
        from sunwell.agent.incremental.deduper import WorkDeduper

        deduper = WorkDeduper[str]()
        execution_counts: dict[str, int] = {k: 0 for k in keys}

        def work_for_key(key: str) -> str:
            execution_counts[key] += 1
            return f"result_{key}"

        for key in keys:
            deduper.do(key, lambda k=key: work_for_key(k))

        # Each key executed exactly once
        assert all(count == 1 for count in execution_counts.values())
        assert deduper.cache_size == len(keys)

    @given(keys=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_duplicate_keys_reuse_results(self, keys: list[str]) -> None:
        """Duplicate keys reuse cached results."""
        from sunwell.agent.incremental.deduper import WorkDeduper

        deduper = WorkDeduper[str]()
        execution_count = 0

        def work() -> str:
            nonlocal execution_count
            execution_count += 1
            return "result"

        for key in keys:
            deduper.do(key, work)

        # Execution count equals unique keys
        unique_keys = len(set(keys))
        assert execution_count == unique_keys
        assert deduper.cache_size == unique_keys


# =============================================================================
# Skip Decision Property Tests
# =============================================================================


class TestSkipDecisionProperties:
    """Property-based tests for skip decisions."""

    @given(
        artifact_id=st.text(min_size=1, max_size=30).filter(lambda x: x.isprintable()),
        force_rerun=st.booleans(),
    )
    @settings(max_examples=50)
    def test_force_rerun_always_executes(
        self, artifact_id: str, force_rerun: bool
    ) -> None:
        """force_rerun=True always results in can_skip=False."""
        import tempfile

        from sunwell.agent.incremental.cache import ExecutionCache, ExecutionStatus
        from sunwell.agent.incremental.executor import SkipReason, should_skip

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ExecutionCache(Path(tmp_dir) / "cache.db")
            spec = MockArtifactSpec(id=artifact_id, description="d", contract="c")

            try:
                # Pre-populate cache with matching hash
                decision = should_skip(spec, cache, {})
                cache.set(artifact_id, decision.current_hash, ExecutionStatus.COMPLETED)

                # Now test with force_rerun
                decision = should_skip(spec, cache, {}, force_rerun=force_rerun)

                if force_rerun:
                    assert decision.can_skip is False
                    assert decision.reason == SkipReason.FORCE_RERUN
                else:
                    assert decision.can_skip is True
            finally:
                cache.close()
