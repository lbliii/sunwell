"""Project registry for RFC-117.

Tracks known projects in ~/.sunwell/projects.json for quick switching.
"""

import json
from datetime import datetime
from pathlib import Path

from sunwell.project.types import Project, WorkspaceType


class RegistryError(Exception):
    """Raised when registry operations fail."""


def _get_registry_path() -> Path:
    """Get path to global registry file."""
    return Path.home() / ".sunwell" / "projects.json"


def _load_registry() -> dict:
    """Load registry from disk."""
    path = _get_registry_path()
    if not path.exists():
        return {"projects": {}, "default_project": None}

    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        raise RegistryError(f"Failed to load registry: {e}") from e


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
    - Default project for CLI commands
    - Last used timestamps

    Example:
        >>> registry = ProjectRegistry()
        >>> registry.register(project)
        >>> project = registry.get("my-app")
        >>> registry.set_default("my-app")
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

    def register(self, project: Project) -> None:
        """Register a project.

        Args:
            project: Project to register
        """
        self._data.setdefault("projects", {})
        self._data["projects"][project.id] = project.to_registry_entry()
        self._save()

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


def init_project(
    root: Path,
    project_id: str | None = None,
    name: str | None = None,
    trust: str = "workspace",
    register: bool = True,
) -> Project:
    """Initialize a new project at the given path.

    Creates .sunwell/project.toml and optionally registers in global registry.

    Args:
        root: Project root directory
        project_id: Unique identifier (defaults to directory name)
        name: Human-readable name (defaults to id)
        trust: Default trust level
        register: Whether to add to global registry

    Returns:
        Initialized Project instance

    Raises:
        RegistryError: If project already exists at this path
    """
    from sunwell.project.manifest import create_manifest, save_manifest
    from sunwell.project.validation import validate_workspace

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

    # Create manifest
    manifest = create_manifest(
        project_id=project_id,
        name=name or project_id,
        trust=trust,
    )
    save_manifest(manifest, manifest_path)

    # Create Project instance
    project = Project(
        id=project_id,
        name=manifest.name,
        root=root,
        workspace_type=WorkspaceType.MANIFEST,
        created_at=manifest.created,
        manifest=manifest,
    )

    # Register globally
    if register:
        registry = ProjectRegistry()
        registry.register(project)

    return project
