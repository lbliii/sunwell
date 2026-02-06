"""Project registry for RFC-117 + RFC-133 Phase 2.

Tracks known projects in ~/.sunwell/projects.json for quick switching.
Extended with URL slug support for human-readable deep linking.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from sunwell.knowledge.project.types import Project, WorkspaceType


class RegistryError(Exception):
    """Raised when registry operations fail."""


def _get_registry_path() -> Path:
    """Get path to global registry file."""
    return Path.home() / ".sunwell" / "projects.json"


def _load_registry() -> dict:
    """Load registry from disk with graceful fallback on corruption."""
    path = _get_registry_path()
    if not path.exists():
        return {"projects": {}, "slugs": {}, "default_project": None}

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)

        # Validate structure
        if not isinstance(data, dict):
            raise ValueError("Registry must be a dictionary")
        if "projects" not in data:
            data["projects"] = {}
        if "slugs" not in data:
            data["slugs"] = {}
        if "default_project" not in data:
            data["default_project"] = None

        return data
    except (json.JSONDecodeError, OSError, ValueError):
        # On corruption, try to backup and return empty registry
        backup_path = path.with_suffix(".json.bak")
        try:
            if path.exists():
                import shutil
                shutil.copy2(path, backup_path)
        except Exception:
            pass  # Backup failed, continue

        # Return empty registry instead of raising
        # This allows the system to continue functioning
        return {"projects": {}, "slugs": {}, "default_project": None}


# ═══════════════════════════════════════════════════════════════════════════════
# RFC-133 Phase 2: Slug Generation and Resolution
# ═══════════════════════════════════════════════════════════════════════════════

def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a project name.
    
    Args:
        name: Project name (e.g., "My Cool App")
        
    Returns:
        URL-safe slug (e.g., "my-cool-app")
    """
    # Lowercase and replace spaces/underscores with hyphens
    slug = name.lower().replace(" ", "-").replace("_", "-")

    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate to 30 characters
    if len(slug) > 30:
        slug = slug[:30].rstrip("-")

    # Ensure we have something
    return slug or "project"


def is_valid_slug(slug: str) -> bool:
    """Check if a string is a valid URL slug.
    
    Args:
        slug: String to validate
        
    Returns:
        True if valid slug format
    """
    if not slug:
        return False
    # Slugs: lowercase alphanumeric + hyphens, optional ~N disambiguator
    return bool(re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]?(~\d+)?$", slug)) or len(slug) == 1


def _save_registry(data: dict) -> None:
    """Save registry to disk."""
    path = _get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = json.dumps(data, indent=2)
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        raise RegistryError(f"Failed to save registry: {e}") from e


class ProjectRegistry:
    """Manages the global project registry.

    Registry is stored at ~/.sunwell/projects.json and tracks:
    - Known projects with their root paths
    - URL slugs for human-readable deep linking (RFC-133 Phase 2)
    - Default project for CLI commands
    - Last used timestamps

    Example:
        >>> registry = ProjectRegistry()
        >>> registry.register(project)
        >>> project = registry.get("my-app")
        >>> registry.set_default("my-app")
        >>> # RFC-133: Slug resolution
        >>> project = registry.resolve_slug("my-app")
        >>> slug = registry.get_slug("proj_abc123")
    """

    def __init__(self) -> None:
        """Initialize registry, loading from disk."""
        self._data = _load_registry()

    def _save(self) -> None:
        """Save current state to disk."""
        _save_registry(self._data)

    @property
    def projects(self) -> dict[str, dict]:
        """Get all registered projects."""
        return self._data.get("projects", {})

    @property
    def slugs(self) -> dict[str, str]:
        """Get slug -> project_id mapping."""
        return self._data.get("slugs", {})

    @property
    def default_project_id(self) -> str | None:
        """Get default project ID."""
        return self._data.get("default_project")

    def list_projects(self) -> list[Project]:
        """List all registered projects.

        Returns:
            List of Project instances
        """
        result = []
        for project_id, entry in self.projects.items():
            try:
                project = Project.from_registry_entry(project_id, entry)
                result.append(project)
            except Exception:
                # Skip invalid entries
                continue
        return result

    def get(self, project_id: str) -> Project | None:
        """Get a project by ID.

        Args:
            project_id: Project identifier

        Returns:
            Project instance or None if not found
        """
        entry = self.projects.get(project_id)
        if not entry:
            return None

        try:
            return Project.from_registry_entry(project_id, entry)
        except Exception:
            return None

    def get_default(self) -> Project | None:
        """Get the default project.

        Returns:
            Default Project or None if not set
        """
        default_id = self.default_project_id
        if not default_id:
            return None
        return self.get(default_id)

    def register(self, project: Project) -> str:
        """Register a project and generate its URL slug.

        Args:
            project: Project to register

        Returns:
            The URL slug assigned to this project
        """
        self._data.setdefault("projects", {})
        self._data["projects"][project.id] = project.to_registry_entry()

        # RFC-133: Generate URL slug
        slug = self.ensure_slug(project.id, project.name)

        self._save()
        return slug

    def unregister(self, project_id: str) -> bool:
        """Remove a project from registry.

        Args:
            project_id: Project to remove

        Returns:
            True if removed, False if not found
        """
        if project_id not in self.projects:
            return False

        del self._data["projects"][project_id]

        # RFC-133: Remove slug mapping
        self.remove_slug(project_id)

        # Clear default if it was this project
        if self.default_project_id == project_id:
            self._data["default_project"] = None

        self._save()
        return True

    def set_default(self, project_id: str) -> None:
        """Set the default project.

        Args:
            project_id: Project to make default

        Raises:
            RegistryError: If project not found
        """
        if project_id not in self.projects:
            raise RegistryError(f"Project not found: {project_id}")

        self._data["default_project"] = project_id
        self._save()

    def update_last_used(self, project_id: str) -> None:
        """Update last_used timestamp for a project.

        Args:
            project_id: Project to update
        """
        if project_id in self.projects:
            self._data["projects"][project_id]["last_used"] = datetime.now().isoformat()
            self._save()

    def find_by_root(self, root: Path) -> Project | None:
        """Find a project by its root path.

        Args:
            root: Path to search for

        Returns:
            Project if found, None otherwise
        """
        root = root.resolve()
        for project_id, entry in self.projects.items():
            if Path(entry["root"]).resolve() == root:
                return Project.from_registry_entry(project_id, entry)
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # RFC-133 Phase 2: URL Slug Support
    # ═══════════════════════════════════════════════════════════════════════════

    def get_slug(self, project_id: str) -> str | None:
        """Get the URL slug for a project.

        Args:
            project_id: Project identifier

        Returns:
            URL slug or None if project not found
        """
        # Reverse lookup: find slug that maps to this project_id
        for slug, pid in self.slugs.items():
            if pid == project_id:
                return slug
        return None

    def resolve_slug(self, slug: str) -> tuple[Project | None, list[Project] | None]:
        """Resolve a URL slug to a project.

        Args:
            slug: URL slug (e.g., "my-app")

        Returns:
            Tuple of (project, ambiguous_list):
            - (Project, None) if unique match found
            - (None, [projects]) if ambiguous (shouldn't happen with proper registry)
            - (None, None) if not found
        """
        # Direct lookup in slug registry
        project_id = self.slugs.get(slug)
        if project_id:
            project = self.get(project_id)
            if project:
                return (project, None)

        # Try as project ID fallback
        project = self.get(slug)
        if project:
            return (project, None)

        # Not found
        return (None, None)

    def ensure_slug(self, project_id: str, preferred_name: str | None = None) -> str:
        """Ensure a project has a URL slug, generating one if needed.

        Args:
            project_id: Project identifier
            preferred_name: Preferred name to derive slug from (defaults to project name)

        Returns:
            The URL slug for this project
        """
        # Check if already has a slug
        existing = self.get_slug(project_id)
        if existing:
            return existing

        # Get project to derive name
        project = self.get(project_id)
        if not project and not preferred_name:
            # Can't generate without a name, use project_id as slug
            slug = generate_slug(project_id)
        else:
            name = preferred_name or (project.name if project else project_id)
            slug = generate_slug(name)

        # Ensure uniqueness
        slug = self._make_unique_slug(slug, project_id)

        # Register the slug
        self._data.setdefault("slugs", {})
        self._data["slugs"][slug] = project_id
        self._save()

        return slug

    def _make_unique_slug(self, base_slug: str, project_id: str) -> str:
        """Make a slug unique by adding a disambiguator if needed.

        Args:
            base_slug: Initial slug
            project_id: Project ID this slug is for

        Returns:
            Unique slug (base_slug or base_slug~N)
        """
        # Check if base slug is available
        existing_id = self.slugs.get(base_slug)
        if existing_id is None or existing_id == project_id:
            return base_slug

        # Find next available disambiguator
        counter = 2
        while True:
            candidate = f"{base_slug}~{counter}"
            existing_id = self.slugs.get(candidate)
            if existing_id is None or existing_id == project_id:
                return candidate
            counter += 1
            if counter > 100:
                # Safety valve - fall back to project_id
                return project_id

    def remove_slug(self, project_id: str) -> bool:
        """Remove a project's slug mapping.

        Args:
            project_id: Project identifier

        Returns:
            True if a slug was removed
        """
        slug = self.get_slug(project_id)
        if slug and slug in self._data.get("slugs", {}):
            del self._data["slugs"][slug]
            self._save()
            return True
        return False

    def list_slugs(self) -> list[tuple[str, str, str]]:
        """List all slug mappings.

        Returns:
            List of (slug, project_id, project_path) tuples
        """
        result = []
        for slug, project_id in self.slugs.items():
            entry = self.projects.get(project_id, {})
            path = entry.get("root", "")
            result.append((slug, project_id, path))
        return result


def init_project(
    root: Path,
    project_id: str | None = None,
    name: str | None = None,
    trust: str = "workspace",
    register: bool = True,
    state_dir: str | None = None,
) -> Project:
    """Initialize a new project at the given path.

    Creates .sunwell/project.toml and optionally registers in global registry.

    Args:
        root: Project root directory
        project_id: Unique identifier (defaults to directory name)
        name: Human-readable name (defaults to id)
        trust: Default trust level
        register: Whether to add to global registry
        state_dir: Optional out-of-tree path for runtime state. When set,
            generated state (backlog, memory, index, etc.) is stored
            externally instead of under .sunwell/ in the workspace.

    Returns:
        Initialized Project instance

    Raises:
        RegistryError: If project already exists at this path
    """
    from sunwell.knowledge.project.manifest import create_manifest, save_manifest
    from sunwell.knowledge.project.validation import validate_workspace

    root = root.resolve()

    # Validate workspace
    validate_workspace(root)

    # Check if already initialized
    manifest_path = root / ".sunwell" / "project.toml"
    if manifest_path.exists():
        raise RegistryError(
            f"Project already initialized at {root}\n"
            f"Manifest: {manifest_path}"
        )

    # Generate ID from directory name if not provided
    if not project_id:
        project_id = root.name.lower().replace(" ", "-").replace("_", "-")

    # Create manifest (with optional external state_dir)
    manifest = create_manifest(
        project_id=project_id,
        name=name or project_id,
        trust=trust,
        state_dir=state_dir,
    )
    save_manifest(manifest, manifest_path)

    # Create external state directory if specified
    if state_dir:
        Path(state_dir).mkdir(parents=True, exist_ok=True)

    # Create Project instance
    state_root = Path(state_dir) if state_dir else None
    project = Project(
        id=project_id,
        name=manifest.name,
        root=root,
        workspace_type=WorkspaceType.MANIFEST,
        created_at=manifest.created,
        manifest=manifest,
        state_root=state_root,
    )

    # Register globally
    if register:
        registry = ProjectRegistry()
        registry.register(project)

    return project
