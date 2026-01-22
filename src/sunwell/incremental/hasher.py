"""Content-addressed hashing for RFC-074 incremental execution (RFC-094: 80-bit hashes).

Computes deterministic hashes for artifact inputs, enabling cache hits
when inputs haven't changed. The hash captures everything that affects
an artifact's output:

1. Artifact's own specification (id, contract, description)
2. Hashes of all dependencies (transitive closure)

Inspired by Pachyderm's datum hashing pattern:
https://github.com/pachyderm/pachyderm

Hash length: 20 hex characters (80 bits) for reduced collision probability.
- 64 bits → 50% collision at ~5 billion entries (2^32)
- 80 bits → 50% collision at ~1.2 trillion entries (2^40)

Example:
    >>> spec = ArtifactSpec(id="A", description="test", contract="test")
    >>> hash1 = compute_input_hash(spec, {})
    >>> hash2 = compute_input_hash(spec, {})
    >>> assert hash1 == hash2  # Deterministic
"""

import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.naaru.artifacts import ArtifactSpec


@dataclass(frozen=True, slots=True)
class ArtifactHash:
    """Content hash for an artifact's inputs.

    Attributes:
        artifact_id: The artifact this hash is for.
        input_hash: SHA-256 truncated to 80 bits (20 hex chars) for reduced collision risk.
        computed_at: Unix timestamp when hash was computed.
    """

    artifact_id: str
    input_hash: str
    computed_at: float


def compute_input_hash(
    spec: ArtifactSpec,
    dependency_hashes: dict[str, str],
) -> str:
    """Compute deterministic hash of an artifact's inputs.

    The hash captures everything that could affect the artifact's output:
    - The artifact's own specification (id, description, contract)
    - Hashes of all required artifacts (transitively via dependency_hashes)

    Args:
        spec: The artifact specification.
        dependency_hashes: Map of artifact_id → input_hash for all dependencies.

    Returns:
        20-character hex hash (80 bits, RFC-094).

    Example:
        >>> spec = ArtifactSpec(id="A", description="test", contract="test")
        >>> compute_input_hash(spec, {})
        'a1b2c3d4e5f6g7h8i9j0'
    """
    hasher = hashlib.sha256()

    # 1. Include artifact's own identity
    hasher.update(spec.id.encode())
    hasher.update(spec.contract.encode())
    hasher.update(spec.description.encode())

    # 2. Include all dependency hashes in sorted order (deterministic)
    for dep_id in sorted(spec.requires):
        dep_hash = dependency_hashes.get(dep_id, "MISSING")
        hasher.update(f"{dep_id}:{dep_hash}".encode())

    # Truncate to 20 chars (80 bits) for reduced collision probability (RFC-094)
    return hasher.hexdigest()[:20]


def compute_spec_hash(spec: ArtifactSpec) -> str:
    """Compute hash of just the spec (no dependencies).

    Useful for detecting spec changes independently of input changes.

    Args:
        spec: The artifact specification.

    Returns:
        20-character hex hash (80 bits, RFC-094).
    """
    hasher = hashlib.sha256()
    hasher.update(spec.id.encode())
    hasher.update(spec.contract.encode())
    hasher.update(spec.description.encode())
    # Include requirements set (but not their hashes)
    for req in sorted(spec.requires):
        hasher.update(req.encode())
    return hasher.hexdigest()[:20]


def create_artifact_hash(
    spec: ArtifactSpec,
    dependency_hashes: dict[str, str],
) -> ArtifactHash:
    """Create an ArtifactHash record with timestamp.

    Args:
        spec: The artifact specification.
        dependency_hashes: Map of artifact_id → input_hash for all dependencies.

    Returns:
        ArtifactHash with computed hash and timestamp.
    """
    return ArtifactHash(
        artifact_id=spec.id,
        input_hash=compute_input_hash(spec, dependency_hashes),
        computed_at=time.time(),
    )
