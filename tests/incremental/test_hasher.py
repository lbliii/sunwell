"""Tests for RFC-074 content hashing."""

import pytest

from sunwell.agent.incremental.hasher import (
    compute_input_hash,
    compute_spec_hash,
    create_artifact_hash,
)
from sunwell.planning.naaru.artifacts import ArtifactSpec


class TestComputeInputHash:
    """Tests for compute_input_hash."""

    def test_deterministic(self) -> None:
        """Same inputs always produce same hash."""
        spec = ArtifactSpec(id="a", description="test", contract="test")

        hash1 = compute_input_hash(spec, {})
        hash2 = compute_input_hash(spec, {})

        assert hash1 == hash2

    def test_different_id_different_hash(self) -> None:
        """Different artifact IDs produce different hashes."""
        spec1 = ArtifactSpec(id="a", description="test", contract="test")
        spec2 = ArtifactSpec(id="b", description="test", contract="test")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        assert hash1 != hash2

    def test_different_contract_different_hash(self) -> None:
        """Different contracts produce different hashes."""
        spec1 = ArtifactSpec(id="a", description="test", contract="contract1")
        spec2 = ArtifactSpec(id="a", description="test", contract="contract2")

        hash1 = compute_input_hash(spec1, {})
        hash2 = compute_input_hash(spec2, {})

        assert hash1 != hash2

    def test_hash_changes_with_dependency(self) -> None:
        """Hash changes when dependency hash changes."""
        spec = ArtifactSpec(id="a", description="test", contract="test", requires=frozenset(["b"]))

        hash1 = compute_input_hash(spec, {"b": "hash1"})
        hash2 = compute_input_hash(spec, {"b": "hash2"})

        assert hash1 != hash2

    def test_hash_ignores_dependency_order(self) -> None:
        """Hash is deterministic regardless of dependency iteration order."""
        spec = ArtifactSpec(
            id="a", description="test", contract="test", requires=frozenset(["b", "c"])
        )

        hash1 = compute_input_hash(spec, {"b": "hashb", "c": "hashc"})
        hash2 = compute_input_hash(spec, {"c": "hashc", "b": "hashb"})

        assert hash1 == hash2

    def test_hash_length(self) -> None:
        """Hash is truncated to 20 characters (80 bits, RFC-094)."""
        spec = ArtifactSpec(id="a", description="test", contract="test")

        hash_value = compute_input_hash(spec, {})

        assert len(hash_value) == 20

    def test_missing_dependency_uses_sentinel(self) -> None:
        """Missing dependencies use MISSING sentinel."""
        spec = ArtifactSpec(id="a", description="test", contract="test", requires=frozenset(["b"]))

        # No dependency hash provided
        hash1 = compute_input_hash(spec, {})

        # MISSING sentinel used
        hash2 = compute_input_hash(spec, {"b": "MISSING"})

        assert hash1 == hash2


class TestComputeSpecHash:
    """Tests for compute_spec_hash."""

    def test_deterministic(self) -> None:
        """Same spec always produces same hash."""
        spec = ArtifactSpec(id="a", description="test", contract="test")

        hash1 = compute_spec_hash(spec)
        hash2 = compute_spec_hash(spec)

        assert hash1 == hash2

    def test_includes_requirements(self) -> None:
        """Hash includes requirements (but not their hashes)."""
        spec1 = ArtifactSpec(id="a", description="test", contract="test", requires=frozenset(["b"]))
        spec2 = ArtifactSpec(id="a", description="test", contract="test", requires=frozenset(["c"]))

        hash1 = compute_spec_hash(spec1)
        hash2 = compute_spec_hash(spec2)

        assert hash1 != hash2

    def test_differs_from_input_hash(self) -> None:
        """Spec hash differs from input hash (no dependency hashes)."""
        spec = ArtifactSpec(id="a", description="test", contract="test", requires=frozenset(["b"]))

        spec_hash = compute_spec_hash(spec)
        input_hash = compute_input_hash(spec, {"b": "somehash"})

        # They're different because input_hash includes dependency hashes
        assert spec_hash != input_hash


class TestCreateArtifactHash:
    """Tests for create_artifact_hash."""

    def test_creates_artifact_hash(self) -> None:
        """Creates ArtifactHash with correct fields."""
        spec = ArtifactSpec(id="test_artifact", description="test", contract="test")

        artifact_hash = create_artifact_hash(spec, {})

        assert artifact_hash.artifact_id == "test_artifact"
        assert len(artifact_hash.input_hash) == 20  # 80 bits, RFC-094
        assert artifact_hash.computed_at > 0

    def test_artifact_hash_is_frozen(self) -> None:
        """ArtifactHash is immutable."""
        spec = ArtifactSpec(id="a", description="test", contract="test")

        artifact_hash = create_artifact_hash(spec, {})

        with pytest.raises(AttributeError):
            artifact_hash.input_hash = "new_hash"  # type: ignore[misc]
