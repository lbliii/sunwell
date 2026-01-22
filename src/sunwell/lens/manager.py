"""Lens management operations (RFC-070).

Provides CRUD operations, versioning, and library functionality for lenses.
"""


import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from sunwell.core.lens import Lens
from sunwell.core.types import SemanticVersion
from sunwell.schema.loader import LensLoader

# Maximum versions to keep per lens (prevents disk bloat)
MAX_VERSIONS_PER_LENS = 50


@dataclass(frozen=True, slots=True)
class LensVersionInfo:
    """Version metadata for a lens."""

    version: SemanticVersion
    created_at: str
    message: str | None
    checksum: str
    parent_lens: str | None = None
    parent_version: str | None = None


@dataclass(frozen=True, slots=True)
class LensLibraryEntry:
    """Lens with library metadata for UI display."""

    lens: Lens
    source: str  # "builtin", "user", "project"
    path: Path
    is_default: bool
    is_editable: bool
    version_count: int
    last_modified: str | None


@dataclass
class LensManager:
    """Manages lens library operations.

    Handles listing, loading, forking, editing, deleting,
    and version tracking of lenses.
    """

    user_lens_dir: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "lenses"
    )
    builtin_lens_dir: Path = field(default_factory=lambda: Path.cwd() / "lenses")
    config_path: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "config.yaml"
    )

    _loader: LensLoader = field(default_factory=LensLoader, init=False)

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.user_lens_dir.mkdir(parents=True, exist_ok=True)
        (self.user_lens_dir / ".versions").mkdir(exist_ok=True)

    # =========================================================================
    # Library Operations
    # =========================================================================

    async def list_library(self) -> list[LensLibraryEntry]:
        """List all lenses in the library.

        Returns both built-in and user lenses, sorted by source then name.
        """
        entries: list[LensLibraryEntry] = []
        default_lens = self._get_global_default()

        # Built-in lenses
        if self.builtin_lens_dir.exists():
            for path in self.builtin_lens_dir.glob("*.lens"):
                lens = self._load_lens_sync(path)
                if lens:
                    entries.append(
                        LensLibraryEntry(
                            lens=lens,
                            source="builtin",
                            path=path,
                            is_default=lens.metadata.name == default_lens,
                            is_editable=False,
                            version_count=0,  # Built-ins don't track versions
                            last_modified=self._get_mtime(path),
                        )
                    )

        # User lenses
        for path in self.user_lens_dir.glob("*.lens"):
            lens = self._load_lens_sync(path)
            if lens:
                slug = path.stem
                version_count = self._count_versions(slug)
                entries.append(
                    LensLibraryEntry(
                        lens=lens,
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

    async def get_lens_detail(self, name: str) -> Lens | None:
        """Get full lens details by name."""
        # Check user lenses first (by slug)
        user_path = self.user_lens_dir / f"{name}.lens"
        if user_path.exists():
            return self._load_lens_sync(user_path)

        # Check built-in lenses (by slug)
        builtin_path = self.builtin_lens_dir / f"{name}.lens"
        if builtin_path.exists():
            return self._load_lens_sync(builtin_path)

        # Try by metadata name
        for entry in await self.list_library():
            if entry.lens.metadata.name.lower() == name.lower():
                return entry.lens

        return None

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def fork_lens(
        self,
        source_name: str,
        new_name: str,
        message: str | None = None,
    ) -> Path:
        """Fork a lens to create a new editable copy.

        Args:
            source_name: Name of lens to fork
            new_name: Name for the new lens (used as filename)
            message: Optional message for version history

        Returns:
            Path to the new lens file

        Raises:
            ValueError: If source lens not found or new name already exists
        """
        # Find source lens
        source_lens = await self.get_lens_detail(source_name)
        if not source_lens:
            msg = f"Source lens not found: {source_name}"
            raise ValueError(msg)

        # Validate new name
        slug = self._slugify(new_name)
        self._validate_slug(slug)
        new_path = self.user_lens_dir / f"{slug}.lens"
        if new_path.exists():
            msg = f"Lens already exists: {new_name}"
            raise ValueError(msg)

        # Read source content
        source_path = source_lens.source_path
        if not source_path or not source_path.exists():
            msg = f"Cannot read source lens: {source_name}"
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

        # Create initial version
        self._create_version(
            lens_name=slug,
            version="1.0.0",
            content=new_content,
            message=message or f"Forked from {source_name}",
            parent_lens=source_name,
        )

        return new_path

    async def save_lens(
        self,
        name: str,
        content: str,
        message: str | None = None,
        bump: str = "patch",  # "major", "minor", "patch"
    ) -> SemanticVersion:
        """Save changes to a user lens with version tracking.

        Args:
            name: Lens name (slug)
            content: Full YAML content
            message: Version message
            bump: Which version component to bump

        Returns:
            New version number

        Raises:
            ValueError: If lens not found or not editable
        """
        path = self.user_lens_dir / f"{name}.lens"
        if not path.exists():
            msg = f"Lens not found: {name}"
            raise ValueError(msg)

        # Parse to validate and get current version
        data = yaml.safe_load(content)

        # Get current version
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

        # Create version snapshot
        self._create_version(
            lens_name=name,
            version=str(new_version),
            content=new_content,
            message=message,
            parent_version=str(current_version),
        )

        return new_version

    async def delete_lens(self, name: str, keep_versions: bool = True) -> None:
        """Delete a user lens.

        Args:
            name: Lens name (slug)
            keep_versions: Whether to keep version history

        Raises:
            ValueError: If lens not found or is built-in
        """
        path = self.user_lens_dir / f"{name}.lens"
        if not path.exists():
            msg = f"Lens not found: {name}"
            raise ValueError(msg)

        # Delete lens file
        path.unlink()

        # Optionally delete version history
        if not keep_versions:
            version_dir = self.user_lens_dir / ".versions" / name
            if version_dir.exists():
                shutil.rmtree(version_dir)

    # =========================================================================
    # Version Operations
    # =========================================================================

    def get_versions(self, name: str) -> list[LensVersionInfo]:
        """Get version history for a lens."""
        manifest_path = self.user_lens_dir / ".versions" / name / "manifest.json"
        if not manifest_path.exists():
            return []

        data = json.loads(manifest_path.read_text())
        return [
            LensVersionInfo(
                version=SemanticVersion.parse(v["version"]),
                created_at=v["created_at"],
                message=v.get("message"),
                checksum=v["checksum"],
                parent_lens=v.get("parent_lens"),
                parent_version=v.get("parent_version"),
            )
            for v in data.get("versions", [])
        ]

    async def rollback(self, name: str, version: str) -> None:
        """Rollback a lens to a previous version.

        Args:
            name: Lens name (slug)
            version: Version to rollback to

        Raises:
            ValueError: If lens or version not found
        """
        version_path = self.user_lens_dir / ".versions" / name / f"{version}.lens"
        if not version_path.exists():
            msg = f"Version not found: {name}@{version}"
            raise ValueError(msg)

        # Copy version content to main lens file
        content = version_path.read_text()

        # Save as new version with rollback message
        await self.save_lens(
            name=name,
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

    def set_global_default(self, name: str | None) -> None:
        """Set the global default lens."""
        config: dict[str, object] = {}
        if self.config_path.exists():
            config = yaml.safe_load(self.config_path.read_text()) or {}

        if name:
            config["default_lens"] = name
        else:
            config.pop("default_lens", None)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.dump(config))

    # =========================================================================
    # Content Access
    # =========================================================================

    def get_lens_content(self, name: str) -> str | None:
        """Get raw lens content for editing."""
        # Check user lenses first
        user_path = self.user_lens_dir / f"{name}.lens"
        if user_path.exists():
            return user_path.read_text()

        # Check built-in lenses
        builtin_path = self.builtin_lens_dir / f"{name}.lens"
        if builtin_path.exists():
            return builtin_path.read_text()

        return None

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _get_global_default(self) -> str | None:
        """Get global default from config."""
        if not self.config_path.exists():
            return None

        config = yaml.safe_load(self.config_path.read_text()) or {}
        return config.get("default_lens")

    def _load_lens_sync(self, path: Path) -> Lens | None:
        """Load a lens from path synchronously."""
        try:
            return self._loader.load(path)
        except Exception:
            return None

    def _create_version(
        self,
        lens_name: str,
        version: str,
        content: str,
        message: str | None,
        parent_lens: str | None = None,
        parent_version: str | None = None,
    ) -> None:
        """Create a version snapshot."""
        version_dir = self.user_lens_dir / ".versions" / lens_name
        version_dir.mkdir(parents=True, exist_ok=True)

        # Write version file
        version_path = version_dir / f"{version}.lens"
        version_path.write_text(content)

        # Update manifest
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
            # Keep newest versions
            old_versions = manifest["versions"][:-MAX_VERSIONS_PER_LENS]
            manifest["versions"] = manifest["versions"][-MAX_VERSIONS_PER_LENS:]

            # Delete old version files
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

    def _slugify(self, name: str) -> str:
        """Convert name to filesystem-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug or "lens"

    def _validate_slug(self, slug: str) -> None:
        """Validate slug for path traversal attacks."""
        if ".." in slug or "/" in slug or "\\" in slug or "\x00" in slug:
            msg = f"Invalid lens name: {slug}"
            raise ValueError(msg)
