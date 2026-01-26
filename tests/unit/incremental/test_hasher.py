"""Tests for content-addressed hashing.

Tests determinism, hash format, and dependency inclusion.
"""

from dataclasses import dataclass

import pytest

from sunwell.agent.incremental.hasher import (
    ArtifactHash,
    compute_input_hash,
    compute_spec_hash,
    create_artifact_hash,
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


# =============================================================================
# compute_input_hash Tests
# =============================================================================


class TestComputeInputHash:
    """Tests for compute_input_hash function."""

    def test_deterministic(self) -> None:
        """Same inputs produce same hash."""
        spec = MockArtifactSpec(id="artifact_1", description="desc", contract="contract")

        hash1 = compute_input_hash(spec, {})
        hash2 = compute_input_hash(spec, {})

        assert hash1 == hash2

    def test_hash_format(self) -> None:
        """Hash is 20 hex characters (80 bits)."""
        spec = MockArtifactSpec(id="artifact_1")

        hash_val = compute_input_hash(spec, {})

        assert len(hash_val) == 20
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_different_id_different_hash(self) -> None:
        """Different artifact IDs produce different hashes."""
        spec1 = MockArtifactSpec(id="artifact_1")
        spec2 = MockArtifactSpec(id="artifact_2")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        assert hash1 != hash2

    def test_different_description_different_hash(self) -> None:
        """Different descriptions produce different hashes."""
        spec1 = MockArtifactSpec(id="artifact_1", description="desc_a")
        spec2 = MockArtifactSpec(id="artifact_1", description="desc_b")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        assert hash1 != hash2

    def test_different_contract_different_hash(self) -> None:
        """Different contracts produce different hashes."""
        spec1 = MockArtifactSpec(id="artifact_1", contract="contract_a")
        spec2 = MockArtifactSpec(id="artifact_1", contract="contract_b")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        assert hash1 != hash2

    def test_dependency_hash_included(self) -> None:
        """Dependency hashes affect the input hash."""
        spec = MockArtifactSpec(id="artifact_1", requires=("dep_a",))

        hash1 = compute_input_hash(spec, {"dep_a": "hash_v1"})
        hash2 = compute_input_hash(spec, {"dep_a": "hash_v2"})

        assert hash1 != hash2

    def test_missing_dependency_uses_marker(self) -> None:
        """Missing dependency uses 'MISSING' marker."""
        spec = MockArtifactSpec(id="artifact_1", requires=("dep_a",))

        hash_with_dep = compute_input_hash(spec, {"dep_a": "actual_hash"})
        hash_missing = compute_input_hash(spec, {})  # dep_a not provided

        assert hash_with_dep != hash_missing

    def test_dependency_order_is_deterministic(self) -> None:
        """Multiple dependencies are processed in sorted order."""
        spec = MockArtifactSpec(id="artifact_1", requires=("z_dep", "a_dep", "m_dep"))

        deps1 = {"z_dep": "h1", "a_dep": "h2", "m_dep": "h3"}
        deps2 = {"a_dep": "h2", "m_dep": "h3", "z_dep": "h1"}  # Different dict order

        hash1 = compute_input_hash(spec, deps1)
        hash2 = compute_input_hash(spec, deps2)

        assert hash1 == hash2  # Same despite dict order

    def test_no_dependencies(self) -> None:
        """Specs with no dependencies produce valid hashes."""
        spec = MockArtifactSpec(id="artifact_1", requires=())

        hash_val = compute_input_hash(spec, {})

        assert len(hash_val) == 20

    def test_empty_strings_are_valid(self) -> None:
        """Empty strings in spec fields produce valid (but different) hashes."""
        spec1 = MockArtifactSpec(id="", description="", contract="")
        spec2 = MockArtifactSpec(id="a", description="", contract="")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        assert len(hash1) == 20
        assert len(hash2) == 20
        assert hash1 != hash2


# =============================================================================
# compute_spec_hash Tests
# =============================================================================


class TestComputeSpecHash:
    """Tests for compute_spec_hash function."""

    def test_deterministic(self) -> None:
        """Same spec produces same hash."""
        spec = MockArtifactSpec(id="artifact_1")

        hash1 = compute_spec_hash(spec)
        hash2 = compute_spec_hash(spec)

        assert hash1 == hash2

    def test_hash_format(self) -> None:
        """Hash is 20 hex characters."""
        spec = MockArtifactSpec(id="artifact_1")

        hash_val = compute_spec_hash(spec)

        assert len(hash_val) == 20
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_includes_requires_but_not_hashes(self) -> None:
        """spec_hash includes requires list but not dependency hashes."""
        spec1 = MockArtifactSpec(id="artifact_1", requires=("dep_a",))
        spec2 = MockArtifactSpec(id="artifact_1", requires=("dep_b",))
        spec3 = MockArtifactSpec(id="artifact_1", requires=())

        hash1 = compute_spec_hash(spec1)
        hash2 = compute_spec_hash(spec2)
        hash3 = compute_spec_hash(spec3)

        # Different requires = different spec_hash
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_differs_from_input_hash(self) -> None:
        """spec_hash differs from input_hash even with no dependencies."""
        spec = MockArtifactSpec(id="artifact_1", requires=("dep_a",))

        spec_hash = compute_spec_hash(spec)
        input_hash = compute_input_hash(spec, {"dep_a": "some_hash"})

        # They're computed differently, so should differ
        # (spec_hash doesn't include dependency hashes, just the requires list)
        assert spec_hash != input_hash


# =============================================================================
# ArtifactHash Tests
# =============================================================================


class TestArtifactHash:
    """Tests for ArtifactHash dataclass."""

    def test_is_frozen(self) -> None:
        """ArtifactHash is immutable."""
        ah = ArtifactHash(
            artifact_id="test",
            input_hash="abc123",
            computed_at=1234567890.0,
        )

        with pytest.raises(AttributeError):
            ah.input_hash = "new_hash"  # type: ignore[misc]

    def test_all_fields_accessible(self) -> None:
        """All fields are accessible."""
        ah = ArtifactHash(
            artifact_id="test",
            input_hash="abc123def456abc1def4",
            computed_at=1234567890.0,
        )

        assert ah.artifact_id == "test"
        assert ah.input_hash == "abc123def456abc1def4"
        assert ah.computed_at == 1234567890.0


# =============================================================================
# create_artifact_hash Tests
# =============================================================================


class TestCreateArtifactHash:
    """Tests for create_artifact_hash factory function."""

    def test_creates_valid_hash(self) -> None:
        """Creates ArtifactHash with computed hash and timestamp."""
        spec = MockArtifactSpec(id="artifact_1")

        ah = create_artifact_hash(spec, {})

        assert ah.artifact_id == "artifact_1"
        assert len(ah.input_hash) == 20
        assert ah.computed_at > 0

    def test_uses_dependency_hashes(self) -> None:
        """Dependency hashes are included in computation."""
        spec = MockArtifactSpec(id="artifact_1", requires=("dep_a",))

        ah1 = create_artifact_hash(spec, {"dep_a": "hash_v1"})
        ah2 = create_artifact_hash(spec, {"dep_a": "hash_v2"})

        assert ah1.input_hash != ah2.input_hash

    def test_timestamp_is_current(self) -> None:
        """computed_at timestamp is reasonably current."""
        import time

        before = time.time()
        spec = MockArtifactSpec(id="artifact_1")
        ah = create_artifact_hash(spec, {})
        after = time.time()

        assert before <= ah.computed_at <= after


# =============================================================================
# Edge Cases
# =============================================================================


class TestHasherEdgeCases:
    """Edge case tests for hashing functions."""

    def test_unicode_in_fields(self) -> None:
        """Unicode characters in fields are handled correctly."""
        spec = MockArtifactSpec(
            id="artifact_日本語",
            description="Описание на русском",
            contract="合同条款",
        )

        hash_val = compute_input_hash(spec, {})

        assert len(hash_val) == 20

    def test_very_long_strings(self) -> None:
        """Very long strings are handled correctly."""
        spec = MockArtifactSpec(
            id="a" * 10000,
            description="b" * 10000,
            contract="c" * 10000,
        )

        hash_val = compute_input_hash(spec, {})

        assert len(hash_val) == 20

    def test_special_characters(self) -> None:
        """Special characters don't cause issues."""
        spec = MockArtifactSpec(
            id="artifact:with/special\\chars\n\t",
            description="desc with 'quotes' and \"double quotes\"",
            contract="contract{with}[brackets]",
        )

        hash_val = compute_input_hash(spec, {})

        assert len(hash_val) == 20

    def test_many_dependencies(self) -> None:
        """Many dependencies are handled correctly."""
        deps = tuple(f"dep_{i}" for i in range(100))
        spec = MockArtifactSpec(id="artifact_1", requires=deps)

        dep_hashes = {d: f"hash_{i}" for i, d in enumerate(deps)}
        hash_val = compute_input_hash(spec, dep_hashes)

        assert len(hash_val) == 20

    def test_collision_resistance(self) -> None:
        """Different inputs produce different hashes (basic collision test)."""
        hashes = set()

        for i in range(1000):
            spec = MockArtifactSpec(id=f"artifact_{i}")
            hash_val = compute_input_hash(spec, {})
            hashes.add(hash_val)

        # All 1000 should be unique
        assert len(hashes) == 1000
