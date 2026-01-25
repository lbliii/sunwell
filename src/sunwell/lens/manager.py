"""Lens management operations (RFC-070, RFC-101).

Provides CRUD operations, versioning, and library functionality for lenses.

RFC-101 adds:
- URI-based identification (sunwell:lens/namespace/slug@version)
- Global index for O(1) library listing
- Content-addressable versioning
- Namespace isolation (builtin, user, project)
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from sunwell.core.identity import SunwellURI, URIParseError, slugify, validate_slug
from sunwell.core.lens import Lens
from sunwell.core.types import SemanticVersion
from sunwell.lens.identity import (
    LensIndexEntry,
    LensManifest,
    LensVersionInfo,
)
from sunwell.lens.index import (
    LensIndexManager,
    add_version_to_manifest,
    create_lens_manifest,
)
from sunwell.schema.loader import LensLoader

# Maximum versions to keep per lens (prevents disk bloat)
MAX_VERSIONS_PER_LENS = 50


@dataclass(frozen=True, slots=True)
class LensLibraryEntry:
    """Lens with library metadata for UI display.

    RFC-101: Now includes URI for explicit identification.
    """

    lens: Lens
    uri: str  # RFC-101: Full URI (e.g., "sunwell:lens/user/my-writer")
    source: str  # "builtin", "user", "project" (legacy compat)
    path: Path
    is_default: bool
    is_editable: bool
    version_count: int
    last_modified: str | None


def _find_builtin_lenses_dir() -> Path:
    """Find built-in lenses directory using fallback chain.

    Checks:
    1. Current working directory (developer use case)
    2. Relative to package (installed or editable install)
    3. Falls back to cwd if nothing found (will return empty list)
    """
    candidates = [
        Path.cwd() / "lenses",
        # Relative to this file: manager.py -> lens/ -> sunwell/ -> src/ -> project/lenses
        Path(__file__).parent.parent.parent.parent / "lenses",
    ]
    for c in candidates:
        if c.exists() and list(c.glob("*.lens")):
            return c
    # Fallback (will be empty but won't crash)
    return Path.cwd() / "lenses"


@dataclass(slots=True)
class LensManager:
    """Manages lens library operations.

    Handles listing, loading, forking, editing, deleting,
    and version tracking of lenses.

    RFC-101: Adds URI-based identification and index management.
    """

    user_lens_dir: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "lenses"
    )
    builtin_lens_dir: Path = field(default_factory=_find_builtin_lenses_dir)
    config_path: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "config.yaml"
    )

    _loader: LensLoader = field(default_factory=LensLoader, init=False)
    _index_manager: LensIndexManager = field(init=False)

    def __post_init__(self) -> None:
        """Ensure directories exist and initialize index manager."""
        self.user_lens_dir.mkdir(parents=True, exist_ok=True)
        (self.user_lens_dir / ".versions").mkdir(exist_ok=True)

        # Initialize index manager
        self._index_manager = LensIndexManager(
            user_lens_dir=self.user_lens_dir,
            builtin_lens_dir=self.builtin_lens_dir,
        )

    # =========================================================================
    # RFC-101: URI Resolution
    # =========================================================================

    def resolve_uri(self, identifier: str) -> str:
        """Resolve an identifier to a full URI.

        Accepts:
        - Full URI: "sunwell:lens/user/my-writer" -> passed through
        - Bare slug: "my-writer" -> resolved to first match (user > builtin)

        Args:
            identifier: Full URI or bare slug

        Returns:
            Full URI string

        Raises:
            ValueError: If identifier cannot be resolved
        """
        # Already a full URI?
        if identifier.startswith("sunwell:"):
            return identifier

        # Bare slug - resolve via index
        entry = self._index_manager.resolve_slug(identifier)
        if entry:
            return entry.uri

        # Check filesystem directly for legacy lenses not in index
        user_path = self.user_lens_dir / f"{identifier}.lens"
        if user_path.exists():
            return f"sunwell:lens/user/{identifier}"

        builtin_path = self.builtin_lens_dir / f"{identifier}.lens"
        if builtin_path.exists():
            return f"sunwell:lens/builtin/{identifier}"

        raise ValueError(f"Cannot resolve lens: {identifier}")

    def parse_uri(self, uri: str) -> SunwellURI:
        """Parse a URI string to SunwellURI.

        Args:
            uri: Full URI string

        Returns:
            Parsed SunwellURI
        """
        return SunwellURI.parse(uri)

    # =========================================================================
    # Library Operations
    # =========================================================================

    async def list_library(self) -> list[LensLibraryEntry]:
        """List all lenses in the library.

        RFC-101: Uses index for O(1) listing when available,
        falls back to filesystem scan.

        Returns both built-in and user lenses, sorted by source then name.
        """
        # Ensure index is up to date
        index = self._index_manager.get_index()

        # If index is empty, rebuild from filesystem
        if not index.lenses:
            self._index_manager.rebuild_index()
            index = self._index_manager.get_index()

        entries: list[LensLibraryEntry] = []
        default_lens = self._get_global_default()

        # Process indexed lenses
        for index_entry in index.lenses.values():
            path = self._get_lens_path(index_entry.uri)
            if path and path.exists():
                lens = self._load_lens_sync(path)
                if lens:
                    entries.append(
                        LensLibraryEntry(
                            lens=lens,
                            uri=index_entry.uri,
                            source=index_entry.namespace
                            if index_entry.namespace in ("builtin", "user")
                            else "project",
                            path=path,
                            is_default=lens.metadata.name == default_lens
                            or index_entry.is_default,
                            is_editable=index_entry.namespace != "builtin",
                            version_count=index_entry.version_count,
                            last_modified=index_entry.last_modified,
                        )
                    )

        # Add any filesystem lenses not in index (legacy support)
        indexed_paths = {self._get_lens_path(e.uri) for e in index.lenses.values()}

        # Built-in lenses not in index
        if self.builtin_lens_dir.exists():
            for path in self.builtin_lens_dir.glob("*.lens"):
                if path not in indexed_paths:
                    lens = self._load_lens_sync(path)
                    if lens:
                        uri = f"sunwell:lens/builtin/{path.stem}"
                        entries.append(
                            LensLibraryEntry(
                                lens=lens,
                                uri=uri,
                                source="builtin",
                                path=path,
                                is_default=lens.metadata.name == default_lens,
                                is_editable=False,
                                version_count=0,
                                last_modified=self._get_mtime(path),
                            )
                        )

        # User lenses not in index
        for path in self.user_lens_dir.glob("*.lens"):
            if path not in indexed_paths:
                lens = self._load_lens_sync(path)
                if lens:
                    slug = path.stem
                    uri = f"sunwell:lens/user/{slug}"
                    version_count = self._count_versions(slug)
                    entries.append(
                        LensLibraryEntry(
                            lens=lens,
                            uri=uri,
                            source="user",
                            path=path,
                            is_default=lens.metadata.name == default_lens,
                            is_editable=True,
                            version_count=version_count,
                            last_modified=self._get_mtime(path),
                        )
                    )

        # Sort: defaults first, then by source, then by name
        entries.sort(
            key=lambda e: (
                not e.is_default,
                0 if e.source == "user" else 1,
                e.lens.metadata.name.lower(),
            )
        )

        return entries

    async def get_lens_detail(self, identifier: str) -> Lens | None:
        """Get full lens details by URI or name.

        RFC-101: Accepts full URI or bare slug.
        Bare slugs emit deprecation warning.

        Args:
            identifier: Full URI or bare slug

        Returns:
            Loaded Lens or None if not found
        """
        # Resolve to full URI
        try:
            uri = self.resolve_uri(identifier)
        except ValueError:
            return None

        # Get path and load
        path = self._get_lens_path(uri)
        if path and path.exists():
            return self._load_lens_sync(path)

        return None

    async def get_lens_by_checksum(self, sha: str) -> Lens | None:
        """Get lens by content hash (content-addressable lookup).

        RFC-101: Enables immutable version references.

        Args:
            sha: Full or partial SHA256 hash (with or without "sha:" prefix)

        Returns:
            Loaded Lens or None if not found
        """
        search_sha = sha[4:] if sha.startswith("sha:") else sha

        # Search all manifests for matching version
        for lens_dir in self.user_lens_dir.iterdir():
            if not lens_dir.is_dir() or lens_dir.name.startswith("."):
                continue

            manifest_path = lens_dir / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                data = json.loads(manifest_path.read_text())
                manifest = LensManifest.from_dict(data)
                version_info = manifest.get_version_by_sha(search_sha)
                if version_info:
                    version_path = lens_dir / f"v{version_info.version}.lens"
                    if version_path.exists():
                        return self._load_lens_sync(version_path)
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def fork_lens(
        self,
        source_identifier: str,
        new_name: str,
        message: str | None = None,
    ) -> tuple[Path, str]:
        """Fork a lens to create a new editable copy.

        RFC-101: Creates lens with proper identity and lineage tracking.

        Args:
            source_identifier: URI or name of lens to fork
            new_name: Name for the new lens (used as display name)
            message: Optional message for version history

        Returns:
            Tuple of (path to new lens file, new lens URI)

        Raises:
            ValueError: If source lens not found or new name already exists
        """
        # Resolve source
        try:
            source_uri = self.resolve_uri(source_identifier)
        except ValueError as err:
            msg = f"Source lens not found: {source_identifier}"
            raise ValueError(msg) from err

        source_lens = await self.get_lens_detail(source_uri)
        if not source_lens:
            msg = f"Source lens not found: {source_identifier}"
            raise ValueError(msg)

        # Validate new name
        slug = slugify(new_name)
        validate_slug(slug)

        # Check for existing lens with same slug
        new_uri = f"sunwell:lens/user/{slug}"
        if self._index_manager.get_entry(new_uri):
            msg = f"Lens already exists: {new_name}"
            raise ValueError(msg)

        new_path = self.user_lens_dir / f"{slug}.lens"
        if new_path.exists():
            msg = f"Lens already exists: {new_name}"
            raise ValueError(msg)

        # Read source content
        source_path = source_lens.source_path
        if not source_path or not source_path.exists():
            msg = f"Cannot read source lens: {source_identifier}"
            raise ValueError(msg)

        content = source_path.read_text()

        # Update metadata in content
        data = yaml.safe_load(content)
        data["lens"]["metadata"]["name"] = new_name
        data["lens"]["metadata"]["version"] = "1.0.0"
        if "author" not in data["lens"]["metadata"]:
            data["lens"]["metadata"]["author"] = "User"

        # Write new lens
        new_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        new_path.write_text(new_content)

        # Create manifest with lineage
        manifest = create_lens_manifest(
            slug=slug,
            display_name=new_name,
            namespace="user",
            content=new_content,
            domain=source_lens.metadata.domain,
            tags=source_lens.metadata.tags,
            heuristics_count=len(source_lens.heuristics),
            skills_count=len(source_lens.skills),
            forked_from=source_uri,
            version="1.0.0",
            message=message or f"Forked from {source_identifier}",
        )

        # Save manifest and update index
        self._save_manifest(slug, manifest)
        self._index_manager.add_lens(manifest)

        # Create legacy version for backwards compat
        self._create_version(
            lens_name=slug,
            version="1.0.0",
            content=new_content,
            message=message or f"Forked from {source_identifier}",
            parent_lens=source_identifier,
        )

        return new_path, new_uri

    async def save_lens(
        self,
        identifier: str,
        content: str,
        message: str | None = None,
        bump: str = "patch",
    ) -> SemanticVersion:
        """Save changes to a user lens with version tracking.

        RFC-101: Updates both manifest and legacy version storage.

        Args:
            identifier: Lens URI or slug
            content: Full YAML content
            message: Version message
            bump: Which version component to bump ("major", "minor", "patch")

        Returns:
            New version number

        Raises:
            ValueError: If lens not found or not editable
        """
        # Resolve to URI and get path
        try:
            uri = self.resolve_uri(identifier)
        except ValueError as err:
            msg = f"Lens not found: {identifier}"
            raise ValueError(msg) from err

        parsed_uri = SunwellURI.parse(uri)
        if parsed_uri.namespace == "builtin":
            msg = f"Cannot edit built-in lens: {identifier}"
            raise ValueError(msg)

        path = self._get_lens_path(uri)
        if not path or not path.exists():
            msg = f"Lens not found: {identifier}"
            raise ValueError(msg)

        # Parse to validate and get current version
        data = yaml.safe_load(content)
        current_version = SemanticVersion.parse(
            data["lens"]["metadata"].get("version", "0.1.0")
        )

        # Bump version
        if bump == "major":
            new_version = SemanticVersion(current_version.major + 1, 0, 0)
        elif bump == "minor":
            new_version = SemanticVersion(
                current_version.major, current_version.minor + 1, 0
            )
        else:
            new_version = SemanticVersion(
                current_version.major, current_version.minor, current_version.patch + 1
            )

        # Update version in content
        data["lens"]["metadata"]["version"] = str(new_version)
        new_content = yaml.dump(data, default_flow_style=False, sort_keys=False)

        # Write file
        path.write_text(new_content)

        # Update manifest if it exists
        slug = parsed_uri.slug
        manifest_path = self.user_lens_dir / slug / "manifest.json"
        if manifest_path.exists():
            try:
                manifest_data = json.loads(manifest_path.read_text())
                manifest = LensManifest.from_dict(manifest_data)
                updated_manifest = add_version_to_manifest(
                    manifest,
                    str(new_version),
                    new_content,
                    message=message,
                    max_versions=MAX_VERSIONS_PER_LENS,
                )
                self._save_manifest(slug, updated_manifest)
                self._index_manager.add_lens(updated_manifest)
            except (json.JSONDecodeError, KeyError):
                pass

        # Create legacy version snapshot
        self._create_version(
            lens_name=slug,
            version=str(new_version),
            content=new_content,
            message=message,
            parent_version=str(current_version),
        )

        return new_version

    async def delete_lens(
        self, identifier: str, keep_versions: bool = True
    ) -> None:
        """Delete a user lens.

        RFC-101: Removes from index and filesystem.

        Args:
            identifier: Lens URI or slug
            keep_versions: Whether to keep version history

        Raises:
            ValueError: If lens not found or is built-in
        """
        # Resolve to URI
        try:
            uri = self.resolve_uri(identifier)
        except ValueError as err:
            msg = f"Lens not found: {identifier}"
            raise ValueError(msg) from err

        parsed_uri = SunwellURI.parse(uri)
        if parsed_uri.namespace == "builtin":
            msg = f"Cannot delete built-in lens: {identifier}"
            raise ValueError(msg)

        slug = parsed_uri.slug

        # Delete lens file
        path = self.user_lens_dir / f"{slug}.lens"
        if path.exists():
            path.unlink()

        # Delete manifest directory
        manifest_dir = self.user_lens_dir / slug
        if manifest_dir.exists():
            shutil.rmtree(manifest_dir)

        # Delete legacy version history
        if not keep_versions:
            version_dir = self.user_lens_dir / ".versions" / slug
            if version_dir.exists():
                shutil.rmtree(version_dir)

        # Remove from index
        self._index_manager.remove_lens(uri)

    # =========================================================================
    # Version Operations
    # =========================================================================

    def get_versions(self, identifier: str) -> list[LensVersionInfo]:
        """Get version history for a lens.

        RFC-101: Reads from manifest if available, falls back to legacy.

        Args:
            identifier: Lens URI or slug

        Returns:
            List of version info, newest first
        """
        # Resolve to URI
        try:
            uri = self.resolve_uri(identifier)
        except ValueError:
            return []

        parsed_uri = SunwellURI.parse(uri)
        slug = parsed_uri.slug

        # Try manifest first
        manifest_path = self.user_lens_dir / slug / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                manifest = LensManifest.from_dict(data)
                return list(manifest.versions)
            except (json.JSONDecodeError, KeyError):
                pass

        # Fall back to legacy version storage
        legacy_manifest_path = self.user_lens_dir / ".versions" / slug / "manifest.json"
        if not legacy_manifest_path.exists():
            return []

        data = json.loads(legacy_manifest_path.read_text())
        return [
            LensVersionInfo(
                version=v["version"],
                sha256=v.get("checksum", ""),
                created_at=v["created_at"],
                message=v.get("message"),
                size_bytes=0,
            )
            for v in data.get("versions", [])
        ]

    async def rollback(self, identifier: str, version: str) -> None:
        """Rollback a lens to a previous version.

        Args:
            identifier: Lens URI or slug
            version: Version to rollback to

        Raises:
            ValueError: If lens or version not found
        """
        # Resolve to URI
        try:
            uri = self.resolve_uri(identifier)
        except ValueError as err:
            msg = f"Lens not found: {identifier}"
            raise ValueError(msg) from err

        parsed_uri = SunwellURI.parse(uri)
        slug = parsed_uri.slug

        # Try manifest directory first
        version_path = self.user_lens_dir / slug / f"v{version}.lens"
        if not version_path.exists():
            # Try legacy version storage
            version_path = self.user_lens_dir / ".versions" / slug / f"{version}.lens"

        if not version_path.exists():
            msg = f"Version not found: {identifier}@{version}"
            raise ValueError(msg)

        # Copy version content to main lens file
        content = version_path.read_text()

        # Save as new version with rollback message
        await self.save_lens(
            identifier=identifier,
            content=content,
            message=f"Rolled back to version {version}",
            bump="patch",
        )

    # =========================================================================
    # Default Management
    # =========================================================================

    def get_global_default(self) -> str | None:
        """Get the global default lens name."""
        return self._get_global_default()

    def set_global_default(self, identifier: str | None) -> None:
        """Set the global default lens.

        RFC-101: Accepts URI or slug, updates index.

        Args:
            identifier: Lens URI or slug, or None to clear
        """
        config: dict[str, object] = {}
        if self.config_path.exists():
            config = yaml.safe_load(self.config_path.read_text()) or {}

        if identifier:
            # Resolve to URI for consistency
            try:
                uri = self.resolve_uri(identifier)
                # Store the slug for backwards compat
                parsed = SunwellURI.parse(uri)
                config["default_lens"] = parsed.slug
                # Also store full URI
                config["default_lens_uri"] = uri
                # Update index
                self._index_manager.set_default(uri)
            except ValueError:
                config["default_lens"] = identifier
        else:
            config.pop("default_lens", None)
            config.pop("default_lens_uri", None)
            self._index_manager.set_default(None)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.dump(config))

    # =========================================================================
    # Content Access
    # =========================================================================

    def get_lens_content(self, identifier: str) -> str | None:
        """Get raw lens content for editing.

        Args:
            identifier: Lens URI or slug

        Returns:
            Raw YAML content or None if not found
        """
        # Resolve to URI and get path
        try:
            uri = self.resolve_uri(identifier)
        except ValueError:
            return None

        path = self._get_lens_path(uri)
        if path and path.exists():
            return path.read_text()

        return None

    # =========================================================================
    # Index Management (RFC-101)
    # =========================================================================

    def rebuild_index(self) -> None:
        """Force rebuild of the lens index.

        Use when index is corrupted or out of sync.
        """
        self._index_manager.rebuild_index()

    def get_index_entry(self, uri: str) -> LensIndexEntry | None:
        """Get index entry for a lens.

        Args:
            uri: Full lens URI

        Returns:
            Index entry or None if not found
        """
        return self._index_manager.get_entry(uri)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _get_global_default(self) -> str | None:
        """Get global default from config."""
        if not self.config_path.exists():
            return None

        config = yaml.safe_load(self.config_path.read_text()) or {}
        return config.get("default_lens")

    def _get_lens_path(self, uri: str) -> Path | None:
        """Get filesystem path for a lens URI.

        Args:
            uri: Full lens URI

        Returns:
            Path to lens file or None if cannot determine
        """
        try:
            parsed = SunwellURI.parse(uri)
        except URIParseError:
            return None

        slug = parsed.slug

        if parsed.namespace == "builtin":
            return self.builtin_lens_dir / f"{slug}.lens"
        elif parsed.namespace == "user":
            # Check new directory structure first
            dir_path = self.user_lens_dir / slug
            if dir_path.is_dir():
                current_path = dir_path / "current.lens"
                if current_path.exists():
                    # Follow symlink
                    return current_path.resolve()
                # Check for latest version file
                version_files = sorted(dir_path.glob("v*.lens"), reverse=True)
                if version_files:
                    return version_files[0]

            # Fall back to flat structure
            return self.user_lens_dir / f"{slug}.lens"
        else:
            # Project-scoped lens (future)
            return None

    def _load_lens_sync(self, path: Path) -> Lens | None:
        """Load a lens from path synchronously."""
        try:
            return self._loader.load(path)
        except Exception:
            return None

    def _save_manifest(self, slug: str, manifest: LensManifest) -> None:
        """Save a lens manifest to disk."""
        manifest_dir = self.user_lens_dir / slug
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))

    def _create_version(
        self,
        lens_name: str,
        version: str,
        content: str,
        message: str | None,
        parent_lens: str | None = None,
        parent_version: str | None = None,
    ) -> None:
        """Create a version snapshot (legacy storage)."""
        version_dir = self.user_lens_dir / ".versions" / lens_name
        version_dir.mkdir(parents=True, exist_ok=True)

        # Write version file
        version_path = version_dir / f"{version}.lens"
        version_path.write_text(content)

        # Also write to new directory structure
        manifest_dir = self.user_lens_dir / lens_name
        if manifest_dir.exists():
            new_version_path = manifest_dir / f"v{version}.lens"
            new_version_path.write_text(content)

        # Update legacy manifest
        manifest_path = version_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        else:
            manifest = {"lens_name": lens_name, "versions": []}

        manifest["current_version"] = version
        manifest["versions"].append(
            {
                "version": version,
                "created_at": datetime.now(UTC).isoformat(),
                "message": message,
                "checksum": f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:12]}",
                "parent_lens": parent_lens,
                "parent_version": parent_version,
            }
        )

        # Prune old versions if exceeding limit
        if len(manifest["versions"]) > MAX_VERSIONS_PER_LENS:
            old_versions = manifest["versions"][:-MAX_VERSIONS_PER_LENS]
            manifest["versions"] = manifest["versions"][-MAX_VERSIONS_PER_LENS:]

            for old_v in old_versions:
                old_path = version_dir / f"{old_v['version']}.lens"
                if old_path.exists():
                    old_path.unlink()

        manifest_path.write_text(json.dumps(manifest, indent=2))

    def _count_versions(self, name: str) -> int:
        """Count versions for a lens."""
        manifest_path = self.user_lens_dir / ".versions" / name / "manifest.json"
        if not manifest_path.exists():
            return 0
        data = json.loads(manifest_path.read_text())
        return len(data.get("versions", []))

    def _get_mtime(self, path: Path) -> str | None:
        """Get file modification time as ISO string."""
        try:
            mtime = path.stat().st_mtime
            return datetime.fromtimestamp(mtime, UTC).isoformat()
        except OSError:
            return None
