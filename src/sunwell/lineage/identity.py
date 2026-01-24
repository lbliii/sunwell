"""Artifact identity resolution for rename detection (RFC-121).

Uses content hashing to detect when a file is moved/renamed
rather than deleted and recreated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sunwell.lineage.models import compute_content_hash, generate_artifact_id

if TYPE_CHECKING:
    from sunwell.lineage.store import LineageStore


class ArtifactIdentityResolver:
    """Resolves artifact identity across renames and moves.

    Algorithm:
    1. On file creation: Generate new artifact_id, store content_hash
    2. On file deletion: Mark as deleted, keep record for 24h
    3. On file creation with matching content_hash: Link to deleted artifact

    Example:
        >>> resolver = ArtifactIdentityResolver(store)
        >>> # New file gets new ID
        >>> artifact_id = resolver.resolve_create("src/new.py", "class New: pass")
        >>> # File with same content as recently deleted reuses ID
        >>> artifact_id = resolver.resolve_create("src/moved.py", same_content)
    """

    DELETED_RETENTION_HOURS = 24

    def __init__(self, store: LineageStore) -> None:
        self.store = store

    def resolve_create(self, path: str, content: str) -> str:
        """Resolve artifact ID for a new file.

        Returns existing artifact_id if this looks like a rename,
        otherwise generates new ID.

        Args:
            path: File path
            content: File content

        Returns:
            Artifact ID (existing if rename detected, new otherwise)
        """
        content_hash = compute_content_hash(content)

        # Check recently deleted artifacts for content match
        deleted = self.store.get_recently_deleted(hours=self.DELETED_RETENTION_HOURS)
        for artifact in deleted:
            if self._content_matches(artifact.content_hash, content_hash):
                # This is a rename/move, reuse artifact_id
                return artifact.artifact_id

        # New artifact
        return generate_artifact_id(path, content)

    def _content_matches(self, hash_a: str, hash_b: str) -> bool:
        """Check if two content hashes indicate identical content.

        For exact match, compare hashes directly.
        Future: Could implement fuzzy matching for minor edits during move.
        """
        return hash_a == hash_b
