"""Lens identity types (RFC-101 Phase 1).

Provides lens-specific identity types including versioning, lineage tracking,
and manifest structures for the global index.
"""

from dataclasses import dataclass

from sunwell.core.identity import ResourceIdentity


@dataclass(frozen=True, slots=True)
class LensLineage:
    """Fork tracking for lenses.

    Tracks where a lens was forked from, enabling:
    - Upstream update notifications
    - Fork graph visualization
    - Attribution tracking

    Attributes:
        forked_from: URI of the parent lens (as string)
        forked_at: ISO timestamp when the fork occurred
    """

    forked_from: str | None
    forked_at: str | None

    @classmethod
    def root(cls) -> LensLineage:
        """Create lineage for an original (non-forked) lens."""
        return cls(forked_from=None, forked_at=None)

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> LensLineage:
        """Create from dictionary representation."""
        return cls(
            forked_from=data.get("forked_from"),
            forked_at=data.get("forked_at"),
        )

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary representation."""
        return {
            "forked_from": self.forked_from,
            "forked_at": self.forked_at,
        }

    @property
    def is_fork(self) -> bool:
        """Check if this lens is a fork of another."""
        return self.forked_from is not None


@dataclass(frozen=True, slots=True)
class LensVersionInfo:
    """Version metadata (no content).

    Lightweight version entry for manifest and index.
    Actual content is stored separately by version.

    Attributes:
        version: Semantic version string (e.g., "1.2.3")
        sha256: Content hash for integrity and content-addressing
        created_at: ISO timestamp of version creation
        message: Optional version message/changelog
        size_bytes: Content size for UI display
    """

    version: str
    sha256: str
    created_at: str
    message: str | None
    size_bytes: int

    @classmethod
    def from_dict(cls, data: dict[str, str | int | None]) -> LensVersionInfo:
        """Create from dictionary representation."""
        return cls(
            version=str(data["version"]),
            sha256=str(data["sha256"]),
            created_at=str(data["created_at"]),
            message=str(data["message"]) if data.get("message") else None,
            size_bytes=int(data.get("size_bytes") or 0),
        )

    def to_dict(self) -> dict[str, str | int | None]:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "message": self.message,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class LensManifest:
    """Full lens manifest.

    Contains all metadata about a lens for the index and detail views.
    Stored as manifest.json within the lens directory.

    Attributes:
        identity: UUID and URI for stable identification
        display_name: Human-readable name
        lineage: Fork tracking information
        current_version: Currently active version string
        versions: All available versions (newest first)
        domain: Lens domain (e.g., "documentation", "code-review")
        tags: Searchable tags for filtering
        heuristics_count: Number of heuristics (for UI display)
        skills_count: Number of skills (for UI display)
    """

    identity: ResourceIdentity
    display_name: str
    lineage: LensLineage
    current_version: str
    versions: tuple[LensVersionInfo, ...]
    domain: str | None
    tags: tuple[str, ...]
    heuristics_count: int
    skills_count: int

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LensManifest:
        """Create from dictionary representation."""
        return cls(
            identity=ResourceIdentity.from_dict(data["identity"]),
            display_name=data["display_name"],
            lineage=LensLineage.from_dict(data.get("lineage", {})),
            current_version=data["current_version"],
            versions=tuple(
                LensVersionInfo.from_dict(v) for v in data.get("versions", [])
            ),
            domain=data.get("domain"),
            tags=tuple(data.get("tags", [])),
            heuristics_count=data.get("heuristics_count", 0),
            skills_count=data.get("skills_count", 0),
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "identity": self.identity.to_dict(),
            "display_name": self.display_name,
            "lineage": self.lineage.to_dict(),
            "current_version": self.current_version,
            "versions": [v.to_dict() for v in self.versions],
            "domain": self.domain,
            "tags": list(self.tags),
            "heuristics_count": self.heuristics_count,
            "skills_count": self.skills_count,
        }

    @property
    def version_count(self) -> int:
        """Get the number of available versions."""
        return len(self.versions)

    def get_version(self, version: str) -> LensVersionInfo | None:
        """Get info for a specific version."""
        for v in self.versions:
            if v.version == version:
                return v
        return None

    def get_version_by_sha(self, sha: str) -> LensVersionInfo | None:
        """Get info by content hash (content-addressable lookup)."""
        # Normalize sha prefix
        search_sha = sha[4:] if sha.startswith("sha:") else sha
        for v in self.versions:
            # Match full or truncated hash
            if v.sha256.startswith(search_sha) or search_sha.startswith(v.sha256):
                return v
        return None


@dataclass(frozen=True, slots=True)
class LensIndexEntry:
    """Lightweight entry for global index.

    Contains only the data needed for fast library listing.
    Full manifest is loaded on demand from the lens directory.

    Attributes:
        uri: Full URI as string (e.g., "sunwell:lens/user/my-writer")
        id: UUID as string
        display_name: Human-readable name
        namespace: Namespace (builtin, user, project slug)
        domain: Lens domain
        current_version: Active version string
        version_count: Number of available versions
        is_default: Whether this is the default lens
        last_modified: ISO timestamp of last modification
    """

    uri: str
    id: str
    display_name: str
    namespace: str
    domain: str | None
    current_version: str
    version_count: int
    is_default: bool
    last_modified: str

    @classmethod
    def from_manifest(
        cls,
        manifest: LensManifest,
        is_default: bool = False,
        last_modified: str | None = None,
    ) -> LensIndexEntry:
        """Create index entry from a full manifest.

        Args:
            manifest: Full lens manifest
            is_default: Whether this is the default lens
            last_modified: Override last modified time

        Returns:
            Lightweight index entry
        """
        # Use the latest version's timestamp if not provided
        if last_modified is None and manifest.versions:
            last_modified = manifest.versions[0].created_at
        elif last_modified is None:
            last_modified = manifest.identity.created_at

        return cls(
            uri=str(manifest.identity.uri),
            id=str(manifest.identity.id),
            display_name=manifest.display_name,
            namespace=manifest.identity.uri.namespace,
            domain=manifest.domain,
            current_version=manifest.current_version,
            version_count=len(manifest.versions),
            is_default=is_default,
            last_modified=last_modified,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LensIndexEntry:
        """Create from dictionary representation."""
        return cls(
            uri=data["uri"],
            id=data["id"],
            display_name=data["display_name"],
            namespace=data["namespace"],
            domain=data.get("domain"),
            current_version=data["current_version"],
            version_count=data.get("version_count", 1),
            is_default=data.get("is_default", False),
            last_modified=data["last_modified"],
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "uri": self.uri,
            "id": self.id,
            "display_name": self.display_name,
            "namespace": self.namespace,
            "domain": self.domain,
            "current_version": self.current_version,
            "version_count": self.version_count,
            "is_default": self.is_default,
            "last_modified": self.last_modified,
        }
