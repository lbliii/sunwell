"""Workspace management for RFC-140.

Unified workspace discovery, switching, and status tracking.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.knowledge.project import ProjectRegistry, create_project_from_workspace
from sunwell.knowledge.project.types import Project
from sunwell.knowledge.project.validation import ProjectValidationError, validate_workspace
from sunwell.knowledge.workspace.resolver import PROJECT_MARKERS, default_workspace_root

if TYPE_CHECKING:
    pass


class WorkspaceStatus(Enum):
    """Workspace health status."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True, slots=True)
class WorkspaceInfo:
    """Information about a workspace."""

    id: str
    """Workspace identifier (project ID if registered, else derived from path)."""

    name: str
    """Human-readable name."""

    path: Path
    """Absolute path to workspace root."""

    is_registered: bool
    """Whether this workspace is registered in the project registry."""

    is_current: bool
    """Whether this is the current workspace."""

    status: WorkspaceStatus
    """Workspace health status."""

    workspace_type: str
    """Type of workspace (manifest, registered, discovered)."""

    last_used: str | None = None
    """Last used timestamp (ISO format)."""

    project: Project | None = None
    """Project instance if registered."""


def _get_current_workspace_path() -> Path:
    """Get path to current workspace state file."""
    return Path.home() / ".sunwell" / "current_workspace.json"


def _load_current_workspace() -> dict | None:
    """Load current workspace state."""
    path = _get_current_workspace_path()
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


def _save_current_workspace(workspace_id: str, workspace_path: Path) -> None:
    """Save current workspace state."""
    path = _get_current_workspace_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "workspace_id": workspace_id,
        "workspace_path": str(workspace_path.resolve()),
        "switched_at": datetime.now().isoformat(),
    }

    try:
        content = json.dumps(data, indent=2)
        path.write_text(content, encoding="utf-8")
    except OSError:
        pass  # Non-critical, fail silently


class WorkspaceManager:
    """Unified workspace management.

    Provides discovery, switching, and status tracking for workspaces.
    """

    def __init__(self) -> None:
        """Initialize workspace manager."""
        self._registry = ProjectRegistry()

    def discover_workspaces(self, root: Path | None = None) -> list[WorkspaceInfo]:
        """Discover workspaces by scanning filesystem.

        Scans common locations and project markers to find workspaces.
        Merges with registered projects and deduplicates.

        Args:
            root: Root directory to scan (defaults to common locations)

        Returns:
            List of discovered workspace info
        """
        current_workspace = self.get_current()
        current_path = current_workspace.path if current_workspace else None

        # Get registered projects
        registered_projects = self._registry.list_projects()
        registered_paths: set[Path] = {p.root.resolve() for p in registered_projects}

        # Scan locations if root not specified
        if root is None:
            scan_roots = [
                default_workspace_root(),
                Path.home() / "Projects",
                Path.home() / "Code",
                Path.home() / "workspace",
                Path.home() / "workspaces",
            ]
        else:
            scan_roots = [root]

        discovered_paths: set[Path] = set()

        # Scan each root location
        for scan_root in scan_roots:
            if not scan_root.exists():
                continue

            # Scan direct children
            try:
                for item in scan_root.iterdir():
                    if not item.is_dir():
                        continue

                    # Check for project markers
                    if self._has_project_markers(item):
                        discovered_paths.add(item.resolve())
            except (OSError, PermissionError):
                continue

        # Merge registered and discovered
        all_paths = registered_paths | discovered_paths

        # Build workspace info list
        workspaces: list[WorkspaceInfo] = []

        for path in all_paths:
            # Check if registered
            project = self._registry.find_by_root(path)
            is_registered = project is not None

            # Get or derive ID and name
            if project:
                workspace_id = project.id
                workspace_name = project.name
                workspace_type = project.workspace_type.value
                last_used = self._registry.projects.get(project.id, {}).get("last_used")
            else:
                workspace_id = path.name.lower().replace(" ", "-").replace("_", "-")
                workspace_name = path.name
                workspace_type = "discovered"
                last_used = None

            # Check status
            status = self._check_status(path)

            # Check if current
            is_current = current_path is not None and path.resolve() == current_path.resolve()

            workspaces.append(
                WorkspaceInfo(
                    id=workspace_id,
                    name=workspace_name,
                    path=path,
                    is_registered=is_registered,
                    is_current=is_current,
                    status=status,
                    workspace_type=workspace_type,
                    last_used=last_used,
                    project=project,
                )
            )

        # Sort by: current first, then registered, then by last_used
        workspaces.sort(
            key=lambda w: (
                not w.is_current,
                not w.is_registered,
                w.last_used or "",
            ),
            reverse=True,
        )

        return workspaces

    def get_current(self) -> WorkspaceInfo | None:
        """Get current workspace.

        Returns:
            Current workspace info or None if not set
        """
        state = _load_current_workspace()
        if not state:
            # Fallback to default project
            default_project = self._registry.get_default()
            if default_project:
                return self._workspace_info_from_project(default_project, is_current=True)
            return None

        workspace_path = Path(state["workspace_path"])
        workspace_id = state.get("workspace_id")

        # Try to find in registry
        project = self._registry.find_by_root(workspace_path)
        if project:
            return self._workspace_info_from_project(project, is_current=True)

        # Not registered, create info from path
        if not workspace_path.exists():
            return None

        status = self._check_status(workspace_path)
        return WorkspaceInfo(
            id=workspace_id or workspace_path.name.lower().replace(" ", "-"),
            name=workspace_path.name,
            path=workspace_path,
            is_registered=False,
            is_current=True,
            status=status,
            workspace_type="discovered",
        )

    def switch_workspace(self, workspace_id: str | Path) -> WorkspaceInfo:
        """Switch to a workspace.

        Args:
            workspace_id: Workspace ID or path

        Returns:
            Workspace info for the switched workspace

        Raises:
            ValueError: If workspace not found
        """
        # Try as ID first
        project = self._registry.get(workspace_id) if isinstance(workspace_id, str) else None

        if project:
            workspace_path = project.root
            actual_id = project.id
        elif isinstance(workspace_id, Path):
            workspace_path = workspace_id.resolve()
            project = self._registry.find_by_root(workspace_path)
            if project:
                actual_id = project.id
            else:
                actual_id = workspace_path.name.lower().replace(" ", "-")
        else:
            # Try to find by path in discovered workspaces
            workspaces = self.discover_workspaces()
            matching = [w for w in workspaces if w.id == workspace_id or str(w.path) == workspace_id]
            if not matching:
                raise ValueError(f"Workspace not found: {workspace_id}")

            workspace_info = matching[0]
            workspace_path = workspace_info.path
            actual_id = workspace_info.id
            project = workspace_info.project

        # Validate workspace exists
        if not workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace_path}")

        # Validate workspace
        try:
            validate_workspace(workspace_path)
        except ProjectValidationError as e:
            raise ValueError(f"Invalid workspace: {e}") from e

        # Save current workspace
        _save_current_workspace(actual_id, workspace_path)

        # Update last used if registered
        if project:
            self._registry.update_last_used(project.id)

        # Return workspace info
        if project:
            return self._workspace_info_from_project(project, is_current=True)

        status = self._check_status(workspace_path)
        return WorkspaceInfo(
            id=actual_id,
            name=workspace_path.name,
            path=workspace_path,
            is_registered=False,
            is_current=True,
            status=status,
            workspace_type="discovered",
        )

    def get_status(self, path: Path) -> WorkspaceStatus:
        """Get workspace status.

        Args:
            path: Workspace path

        Returns:
            Workspace status
        """
        return self._check_status(path)

    def register_discovered(self, path: Path) -> Project:
        """Register a discovered workspace.

        Creates a project from the workspace path and registers it.

        Args:
            path: Workspace path to register

        Returns:
            Registered Project instance

        Raises:
            ValueError: If path is invalid or already registered
        """
        path = path.resolve()

        # Check if already registered
        existing = self._registry.find_by_root(path)
        if existing:
            raise ValueError(f"Workspace already registered as: {existing.id}")

        # Validate workspace
        try:
            validate_workspace(path)
        except ProjectValidationError as e:
            raise ValueError(f"Invalid workspace: {e}") from e

        # Create project from workspace
        project = create_project_from_workspace(path)

        # Register it
        self._registry.register(project)

        return project

    def _has_project_markers(self, path: Path) -> bool:
        """Check if path has project markers.

        Args:
            path: Path to check

        Returns:
            True if markers found
        """
        for marker in PROJECT_MARKERS:
            if (path / marker).exists():
                return True
        return False

    def _check_status(self, path: Path) -> WorkspaceStatus:
        """Check workspace status.

        Args:
            path: Workspace path

        Returns:
            Workspace status
        """
        if not path.exists():
            return WorkspaceStatus.NOT_FOUND

        try:
            validate_workspace(path)
            return WorkspaceStatus.VALID
        except ProjectValidationError:
            return WorkspaceStatus.INVALID

    def _workspace_info_from_project(self, project: Project, is_current: bool = False) -> WorkspaceInfo:
        """Create WorkspaceInfo from Project.

        Args:
            project: Project instance
            is_current: Whether this is the current workspace

        Returns:
            WorkspaceInfo instance
        """
        status = self._check_status(project.root)
        last_used = self._registry.projects.get(project.id, {}).get("last_used")

        return WorkspaceInfo(
            id=project.id,
            name=project.name,
            path=project.root,
            is_registered=True,
            is_current=is_current,
            status=status,
            workspace_type=project.workspace_type.value,
            last_used=last_used,
            project=project,
        )
