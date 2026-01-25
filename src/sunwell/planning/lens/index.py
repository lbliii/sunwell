"""Lens index management (RFC-101 Phase 1).

Provides O(1) library listing via a global index file.
The index is the source of truth for fast lookups;
individual manifests provide full details on demand.

Storage Layout:
    ~/.sunwell/lenses/
        index.json              # Global index (fast library listing)
        my-custom-writer/
            manifest.json       # Identity + version list
            current.lens        # Symlink to latest version
            v1.0.0.lens
            v1.1.0.lens
"""

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from sunwell.foundation.identity import ResourceIdentity, SunwellURI
from sunwell.planning.lens.identity import (
    LensIndexEntry,
    LensLineage,
    LensManifest,
    LensVersionInfo,
)

# Index file version for migration
INDEX_VERSION = 1


@dataclass(frozen=True, slots=True)
class LensIndex:
    """Global lens index.

    Contains lightweight entries for all lenses for O(1) listing.

    Attributes:
        version: Index schema version for migrations
        updated_at: ISO timestamp of last index update
        lenses: URI -> LensIndexEntry mapping (immutable)
    """

    version: int
    updated_at: str
    lenses: Mapping[str, LensIndexEntry]

    @classmethod
    def empty(cls) -> LensIndex:
        """Create an empty index."""
        return cls(
            version=INDEX_VERSION,
            updated_at=datetime.now(UTC).isoformat(),
            lenses=MappingProxyType({}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LensIndex:
        """Create from dictionary representation."""
        lenses = {
            uri: LensIndexEntry.from_dict(entry)
            for uri, entry in data.get("lenses", {}).items()
        }
        return cls(
            version=data.get("version", INDEX_VERSION),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            lenses=MappingProxyType(lenses),
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "lenses": {uri: entry.to_dict() for uri, entry in self.lenses.items()},
        }

    def with_entry(self, entry: LensIndexEntry) -> LensIndex:
        """Return new index with added/updated entry."""
        new_lenses = dict(self.lenses)
        new_lenses[entry.uri] = entry
        return LensIndex(
            version=self.version,
            updated_at=datetime.now(UTC).isoformat(),
            lenses=MappingProxyType(new_lenses),
        )

    def without_entry(self, uri: str) -> LensIndex:
        """Return new index with entry removed."""
        new_lenses = {k: v for k, v in self.lenses.items() if k != uri}
        return LensIndex(
            version=self.version,
            updated_at=datetime.now(UTC).isoformat(),
            lenses=MappingProxyType(new_lenses),
        )


@dataclass(slots=True)
class LensIndexManager:
    """Manages the global lens index.

    Thread-safe index operations with caching.

    Attributes:
        user_lens_dir: Directory for user lenses (~/.sunwell/lenses)
        builtin_lens_dir: Directory for built-in lenses
    """

    user_lens_dir: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "lenses"
    )
    builtin_lens_dir: Path | None = None

    _index: LensIndex | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.user_lens_dir.mkdir(parents=True, exist_ok=True)

    @property
    def index_path(self) -> Path:
        """Path to the global index file."""
        return self.user_lens_dir / "index.json"

    def get_index(self, *, force_reload: bool = False) -> LensIndex:
        """Get the current index, loading from disk if needed.

        Args:
            force_reload: Force reload from disk even if cached

        Returns:
            Current lens index
        """
        with self._lock:
            if self._index is None or force_reload:
                self._index = self._load_index()
            return self._index

    def _load_index(self) -> LensIndex:
        """Load index from disk."""
        if not self.index_path.exists():
            return LensIndex.empty()

        try:
            data = json.loads(self.index_path.read_text())
            return LensIndex.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            # Corrupted index - rebuild
            return self._rebuild_index()

    def _save_index(self, index: LensIndex) -> None:
        """Save index to disk."""
        self.index_path.write_text(json.dumps(index.to_dict(), indent=2))
        self._index = index

    def list_lenses(
        self,
        *,
        namespace: str | None = None,
        domain: str | None = None,
    ) -> list[LensIndexEntry]:
        """List lenses with optional filtering.

        O(1) for full list, O(n) for filtered (n = number of lenses).

        Args:
            namespace: Filter by namespace (builtin, user, etc.)
            domain: Filter by domain

        Returns:
            List of matching index entries, sorted by default/name
        """
        index = self.get_index()
        entries = list(index.lenses.values())

        if namespace:
            entries = [e for e in entries if e.namespace == namespace]

        if domain:
            entries = [e for e in entries if e.domain == domain]

        # Sort: defaults first, then by namespace, then by name
        entries.sort(
            key=lambda e: (
                not e.is_default,
                0 if e.namespace == "user" else 1,
                e.display_name.lower(),
            )
        )

        return entries

    def get_entry(self, uri: str) -> LensIndexEntry | None:
        """Get index entry by URI.

        O(1) lookup.

        Args:
            uri: Full URI string

        Returns:
            Index entry or None if not found
        """
        index = self.get_index()
        return index.lenses.get(uri)

    def get_entry_by_id(self, id_str: str) -> LensIndexEntry | None:
        """Get index entry by UUID.

        O(n) scan - use URI lookup when possible.

        Args:
            id_str: UUID string

        Returns:
            Index entry or None if not found
        """
        index = self.get_index()
        for entry in index.lenses.values():
            if entry.id == id_str:
                return entry
        return None

    def resolve_slug(self, slug: str) -> LensIndexEntry | None:
        """Resolve a bare slug to an index entry.

        Resolution order: user -> builtin

        Args:
            slug: Bare lens slug (e.g., "tech-writer")

        Returns:
            Index entry or None if not found
        """
        index = self.get_index()

        # Try user namespace first
        user_uri = f"sunwell:lens/user/{slug}"
        if user_uri in index.lenses:
            return index.lenses[user_uri]

        # Try builtin namespace
        builtin_uri = f"sunwell:lens/builtin/{slug}"
        if builtin_uri in index.lenses:
            return index.lenses[builtin_uri]

        return None

    def add_lens(
        self,
        manifest: LensManifest,
        *,
        is_default: bool = False,
    ) -> None:
        """Add or update a lens in the index.

        Args:
            manifest: Full lens manifest
            is_default: Whether this is the default lens
        """
        with self._lock:
            index = self.get_index()
            entry = LensIndexEntry.from_manifest(manifest, is_default=is_default)
            new_index = index.with_entry(entry)
            self._save_index(new_index)

    def remove_lens(self, uri: str) -> bool:
        """Remove a lens from the index.

        Args:
            uri: Full URI string

        Returns:
            True if lens was found and removed
        """
        with self._lock:
            index = self.get_index()
            if uri not in index.lenses:
                return False
            new_index = index.without_entry(uri)
            self._save_index(new_index)
            return True

    def set_default(self, uri: str | None) -> bool:
        """Set the default lens.

        Args:
            uri: URI of lens to make default, or None to clear

        Returns:
            True if successful
        """
        with self._lock:
            index = self.get_index()
            new_lenses = {}

            for entry_uri, entry in index.lenses.items():
                # Create updated entry with new default status
                new_entry = LensIndexEntry(
                    uri=entry.uri,
                    id=entry.id,
                    display_name=entry.display_name,
                    namespace=entry.namespace,
                    domain=entry.domain,
                    current_version=entry.current_version,
                    version_count=entry.version_count,
                    is_default=(entry_uri == uri),
                    last_modified=entry.last_modified,
                )
                new_lenses[entry_uri] = new_entry

            new_index = LensIndex(
                version=index.version,
                updated_at=datetime.now(UTC).isoformat(),
                lenses=MappingProxyType(new_lenses),
            )
            self._save_index(new_index)
            return True

    def rebuild_index(self) -> LensIndex:
        """Force rebuild of the index from filesystem.

        Scans all lens directories and regenerates the index.
        Use when index is corrupted or out of sync.

        Returns:
            Rebuilt index
        """
        with self._lock:
            return self._rebuild_index()

    def _rebuild_index(self) -> LensIndex:
        """Internal rebuild without locking."""
        lenses: dict[str, LensIndexEntry] = {}

        # Scan user lenses (new directory structure)
        for lens_dir in self.user_lens_dir.iterdir():
            if lens_dir.is_dir() and not lens_dir.name.startswith("."):
                manifest_path = lens_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        data = json.loads(manifest_path.read_text())
                        manifest = LensManifest.from_dict(data)
                        entry = LensIndexEntry.from_manifest(manifest)
                        lenses[entry.uri] = entry
                    except (json.JSONDecodeError, KeyError):
                        continue

        # Scan user lenses (legacy flat structure)
        for lens_file in self.user_lens_dir.glob("*.lens"):
            slug = lens_file.stem
            uri = f"sunwell:lens/user/{slug}"
            if uri not in lenses:
                # Create minimal entry for legacy lens
                entry = self._create_legacy_entry(lens_file, "user")
                if entry:
                    lenses[entry.uri] = entry

        # Scan builtin lenses
        if self.builtin_lens_dir and self.builtin_lens_dir.exists():
            for lens_file in self.builtin_lens_dir.glob("*.lens"):
                entry = self._create_legacy_entry(lens_file, "builtin")
                if entry:
                    lenses[entry.uri] = entry

        new_index = LensIndex(
            version=INDEX_VERSION,
            updated_at=datetime.now(UTC).isoformat(),
            lenses=MappingProxyType(lenses),
        )
        self._save_index(new_index)
        return new_index

    def _create_legacy_entry(
        self, lens_file: Path, namespace: str
    ) -> LensIndexEntry | None:
        """Create an index entry for a legacy flat lens file."""
        import yaml

        try:
            content = lens_file.read_text()
            data = yaml.safe_load(content)
            lens_data = data.get("lens", {})
            metadata = lens_data.get("metadata", {})

            slug = lens_file.stem
            uri = f"sunwell:lens/{namespace}/{slug}"

            # Generate stable UUID from content hash
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            # Use first 32 chars as UUID (deterministic)
            stable_uuid = (
                f"{content_hash[:8]}-{content_hash[8:12]}-"
                f"{content_hash[12:16]}-{content_hash[16:20]}-{content_hash[20:32]}"
            )

            mtime = lens_file.stat().st_mtime
            last_modified = datetime.fromtimestamp(mtime, UTC).isoformat()

            return LensIndexEntry(
                uri=uri,
                id=stable_uuid,
                display_name=metadata.get("name", slug),
                namespace=namespace,
                domain=metadata.get("domain"),
                current_version=metadata.get("version", "1.0.0"),
                version_count=1,
                is_default=False,
                last_modified=last_modified,
            )
        except Exception:
            return None


def create_lens_manifest(
    slug: str,
    display_name: str,
    namespace: str,
    content: str,
    *,
    domain: str | None = None,
    tags: tuple[str, ...] = (),
    heuristics_count: int = 0,
    skills_count: int = 0,
    forked_from: str | None = None,
    version: str = "1.0.0",
    message: str | None = None,
) -> LensManifest:
    """Create a new lens manifest.

    Args:
        slug: Filesystem-safe identifier
        display_name: Human-readable name
        namespace: Lens namespace (user, project slug, etc.)
        content: Lens YAML content (for hashing)
        domain: Optional lens domain
        tags: Searchable tags
        heuristics_count: Number of heuristics
        skills_count: Number of skills
        forked_from: URI of parent lens if this is a fork
        version: Initial version
        message: Version message

    Returns:
        New LensManifest
    """
    uri = SunwellURI.for_lens(namespace, slug)
    identity = ResourceIdentity.create(uri)

    # Create lineage
    if forked_from:
        lineage = LensLineage(
            forked_from=forked_from,
            forked_at=datetime.now(UTC).isoformat(),
        )
    else:
        lineage = LensLineage.root()

    # Create initial version
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_info = LensVersionInfo(
        version=version,
        sha256=content_hash,
        created_at=datetime.now(UTC).isoformat(),
        message=message,
        size_bytes=len(content.encode()),
    )

    return LensManifest(
        identity=identity,
        display_name=display_name,
        lineage=lineage,
        current_version=version,
        versions=(version_info,),
        domain=domain,
        tags=tags,
        heuristics_count=heuristics_count,
        skills_count=skills_count,
    )


def add_version_to_manifest(
    manifest: LensManifest,
    version: str,
    content: str,
    *,
    message: str | None = None,
    max_versions: int = 50,
) -> LensManifest:
    """Add a new version to a manifest.

    Args:
        manifest: Existing manifest
        version: New version string
        content: Lens YAML content
        message: Version message
        max_versions: Maximum versions to keep

    Returns:
        Updated manifest with new version
    """
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_info = LensVersionInfo(
        version=version,
        sha256=content_hash,
        created_at=datetime.now(UTC).isoformat(),
        message=message,
        size_bytes=len(content.encode()),
    )

    # Prepend new version, prune old ones
    versions = (version_info,) + manifest.versions
    if len(versions) > max_versions:
        versions = versions[:max_versions]

    return LensManifest(
        identity=manifest.identity,
        display_name=manifest.display_name,
        lineage=manifest.lineage,
        current_version=version,
        versions=versions,
        domain=manifest.domain,
        tags=manifest.tags,
        heuristics_count=manifest.heuristics_count,
        skills_count=manifest.skills_count,
    )
