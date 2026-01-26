"""Workspace registry for multi-project architecture.

Manages workspaces stored at ~/.sunwell/workspaces/ as TOML files.
Each workspace groups related projects together for:
- Cross-project context and memory
- Smart query routing
- Tiered indexing (L1 signatures, L2 full)
"""

import asyncio
import logging
import tomllib
from datetime import datetime
from pathlib import Path

from sunwell.knowledge.workspace.types import (
    ProjectRole,
    Workspace,
    WorkspaceDependencies,
    WorkspaceProject,
)

logger = logging.getLogger(__name__)

__all__ = [
    "WorkspaceRegistry",
    "WorkspaceRegistryError",
    "create_workspace",
    "get_default_workspace",
]


class WorkspaceRegistryError(Exception):
    """Raised when workspace registry operations fail."""


def _get_workspaces_dir() -> Path:
    """Get path to workspaces directory."""
    return Path.home() / ".sunwell" / "workspaces"


def _get_default_workspace_path() -> Path:
    """Get path to default workspace state file."""
    return Path.home() / ".sunwell" / "current_workspace.json"


class WorkspaceRegistry:
    """Manages workspaces stored at ~/.sunwell/workspaces/.

    Each workspace is a TOML file that groups related projects:

        # ~/.sunwell/workspaces/myapp.toml
        [workspace]
        id = "myapp"
        name = "MyApp"

        [[projects]]
        id = "myapp-frontend"
        path = "~/Code/myapp-frontend"
        role = "frontend"

        [[projects]]
        id = "myapp-backend"
        path = "~/Code/myapp-backend"
        role = "backend"

        [dependencies]
        frontend = ["shared"]
        backend = ["shared"]

    Usage:
        >>> registry = WorkspaceRegistry()
        >>> ws = registry.get("myapp")
        >>> registry.list_workspaces()
        >>> registry.create(workspace)
    """

    def __init__(self) -> None:
        """Initialize registry."""
        self._workspaces_dir = _get_workspaces_dir()
        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Workspace] = {}

    def list_workspaces(self) -> list[Workspace]:
        """List all registered workspaces.

        Returns:
            List of Workspace instances.
        """
        workspaces: list[Workspace] = []

        for toml_file in self._workspaces_dir.glob("*.toml"):
            try:
                ws = self._load_workspace(toml_file)
                if ws:
                    workspaces.append(ws)
            except Exception as e:
                logger.warning(f"Failed to load workspace {toml_file}: {e}")
                continue

        return workspaces

    def get(self, workspace_id: str) -> Workspace | None:
        """Get a workspace by ID.

        Args:
            workspace_id: Workspace identifier.

        Returns:
            Workspace instance or None if not found.
        """
        # Check cache
        if workspace_id in self._cache:
            return self._cache[workspace_id]

        # Load from disk
        toml_path = self._workspaces_dir / f"{workspace_id}.toml"
        if not toml_path.exists():
            return None

        ws = self._load_workspace(toml_path)
        if ws:
            self._cache[workspace_id] = ws
        return ws

    def create(self, workspace: Workspace) -> None:
        """Create and save a new workspace.

        Args:
            workspace: Workspace to create.

        Raises:
            WorkspaceRegistryError: If workspace already exists.
        """
        toml_path = self._workspaces_dir / f"{workspace.id}.toml"
        if toml_path.exists():
            raise WorkspaceRegistryError(f"Workspace already exists: {workspace.id}")

        self._save_workspace(workspace, toml_path)
        self._cache[workspace.id] = workspace

    def update(self, workspace: Workspace) -> None:
        """Update an existing workspace.

        Args:
            workspace: Workspace with updated data.

        Raises:
            WorkspaceRegistryError: If workspace doesn't exist.
        """
        toml_path = self._workspaces_dir / f"{workspace.id}.toml"
        if not toml_path.exists():
            raise WorkspaceRegistryError(f"Workspace not found: {workspace.id}")

        self._save_workspace(workspace, toml_path)
        self._cache[workspace.id] = workspace

    def delete(self, workspace_id: str) -> bool:
        """Delete a workspace.

        Args:
            workspace_id: Workspace to delete.

        Returns:
            True if deleted, False if not found.
        """
        toml_path = self._workspaces_dir / f"{workspace_id}.toml"
        if not toml_path.exists():
            return False

        try:
            toml_path.unlink()
            self._cache.pop(workspace_id, None)
            return True
        except OSError as e:
            raise WorkspaceRegistryError(f"Failed to delete workspace: {e}") from e

    async def ensure_l1_indexed(self, workspace_id: str) -> dict[str, int]:
        """Ensure workspace has L1 signature index.

        Triggers background L1 indexing if needed. This is a lightweight
        operation that only extracts public API signatures.

        Args:
            workspace_id: Workspace to index.

        Returns:
            Dict of project_id -> signature count.

        Raises:
            WorkspaceRegistryError: If workspace not found.
        """
        ws = self.get(workspace_id)
        if not ws:
            raise WorkspaceRegistryError(f"Workspace not found: {workspace_id}")

        from sunwell.knowledge.workspace.workspace_index import WorkspaceSignatureIndex

        index = WorkspaceSignatureIndex(ws)
        return await index.scan_all()

    def trigger_l1_indexing_background(self, workspace_id: str) -> None:
        """Trigger L1 indexing in the background.

        Non-blocking call that starts L1 indexing without waiting.

        Args:
            workspace_id: Workspace to index.
        """
        ws = self.get(workspace_id)
        if not ws:
            logger.warning(f"Cannot trigger L1 indexing: workspace {workspace_id} not found")
            return

        async def _index_background():
            try:
                from sunwell.knowledge.workspace.workspace_index import WorkspaceSignatureIndex
                index = WorkspaceSignatureIndex(ws)
                stats = await index.scan_all()
                logger.info(f"L1 indexing complete for {workspace_id}: {sum(stats.values())} signatures")
            except Exception as e:
                logger.warning(f"Background L1 indexing failed for {workspace_id}: {e}")

        # Start indexing in background task
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_index_background())
        except RuntimeError:
            # No running event loop, skip background indexing
            logger.debug("No event loop for background L1 indexing, skipping")

    def add_project(
        self,
        workspace_id: str,
        project_id: str,
        project_path: Path,
        role: ProjectRole = ProjectRole.UNKNOWN,
        is_primary: bool = False,
    ) -> Workspace:
        """Add a project to a workspace.

        Args:
            workspace_id: Workspace to add to.
            project_id: Project identifier.
            project_path: Path to project root.
            role: Semantic role hint.
            is_primary: Whether this is the primary project.

        Returns:
            Updated Workspace.

        Raises:
            WorkspaceRegistryError: If workspace not found.
        """
        ws = self.get(workspace_id)
        if not ws:
            raise WorkspaceRegistryError(f"Workspace not found: {workspace_id}")

        # Check if project already exists
        existing_ids = {p.id for p in ws.projects}
        if project_id in existing_ids:
            raise WorkspaceRegistryError(
                f"Project {project_id} already in workspace {workspace_id}"
            )

        # Create new project list
        new_project = WorkspaceProject(
            id=project_id,
            path=project_path.resolve(),
            role=role,
            is_primary=is_primary,
        )

        # If this is primary, unmark others
        if is_primary:
            new_projects = tuple(
                WorkspaceProject(
                    id=p.id,
                    path=p.path,
                    role=p.role,
                    is_primary=False,
                )
                for p in ws.projects
            ) + (new_project,)
        else:
            new_projects = ws.projects + (new_project,)

        # Create updated workspace
        updated_ws = Workspace(
            id=ws.id,
            name=ws.name,
            projects=new_projects,
            dependencies=ws.dependencies,
            created_at=ws.created_at,
            root=ws.root,
        )

        self.update(updated_ws)
        return updated_ws

    def remove_project(self, workspace_id: str, project_id: str) -> Workspace:
        """Remove a project from a workspace.

        Args:
            workspace_id: Workspace to remove from.
            project_id: Project to remove.

        Returns:
            Updated Workspace.

        Raises:
            WorkspaceRegistryError: If workspace or project not found.
        """
        ws = self.get(workspace_id)
        if not ws:
            raise WorkspaceRegistryError(f"Workspace not found: {workspace_id}")

        existing_ids = {p.id for p in ws.projects}
        if project_id not in existing_ids:
            raise WorkspaceRegistryError(
                f"Project {project_id} not in workspace {workspace_id}"
            )

        # Remove project and update dependencies
        new_projects = tuple(p for p in ws.projects if p.id != project_id)
        new_deps_edges = tuple(
            (src, dep) for src, dep in ws.dependencies.edges
            if src != project_id and dep != project_id
        )

        updated_ws = Workspace(
            id=ws.id,
            name=ws.name,
            projects=new_projects,
            dependencies=WorkspaceDependencies(edges=new_deps_edges),
            created_at=ws.created_at,
            root=ws.root,
        )

        self.update(updated_ws)
        return updated_ws

    def find_workspace_for_project(self, project_id: str) -> Workspace | None:
        """Find which workspace a project belongs to.

        Args:
            project_id: Project to search for.

        Returns:
            Workspace containing the project, or None.
        """
        for ws in self.list_workspaces():
            if project_id in ws.project_ids:
                return ws
        return None

    def _load_workspace(self, toml_path: Path) -> Workspace | None:
        """Load a workspace from TOML file."""
        try:
            content = toml_path.read_bytes()
            data = tomllib.loads(content.decode("utf-8"))
            return Workspace.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to parse workspace {toml_path}: {e}")
            return None

    def _save_workspace(self, workspace: Workspace, toml_path: Path) -> None:
        """Save a workspace to TOML file."""
        try:
            import tomli_w
        except ImportError:
            # Fallback to manual TOML generation
            self._save_workspace_manual(workspace, toml_path)
            return

        data = workspace.to_dict()
        toml_path.write_bytes(tomli_w.dumps(data))

    def _save_workspace_manual(self, workspace: Workspace, toml_path: Path) -> None:
        """Save workspace to TOML without tomli_w dependency."""
        lines: list[str] = []

        # Workspace section
        lines.append("[workspace]")
        lines.append(f'id = "{workspace.id}"')
        lines.append(f'name = "{workspace.name}"')
        lines.append(f'created = "{workspace.created_at.isoformat()}"')
        if workspace.root:
            lines.append(f'root = "{workspace.root}"')
        lines.append("")

        # Projects
        for project in workspace.projects:
            lines.append("[[projects]]")
            lines.append(f'id = "{project.id}"')
            lines.append(f'path = "{project.path}"')
            lines.append(f'role = "{project.role.value}"')
            if project.is_primary:
                lines.append("is_primary = true")
            lines.append("")

        # Dependencies
        if workspace.dependencies.edges:
            lines.append("[dependencies]")
            deps_dict = workspace.dependencies.to_dict()
            for src, deps in deps_dict.items():
                deps_str = ", ".join(f'"{d}"' for d in deps)
                lines.append(f'{src} = [{deps_str}]')
            lines.append("")

        toml_path.write_text("\n".join(lines), encoding="utf-8")


def create_workspace(
    workspace_id: str,
    name: str | None = None,
    projects: list[tuple[str, Path, ProjectRole]] | None = None,
    root: Path | None = None,
) -> Workspace:
    """Create and register a new workspace.

    Args:
        workspace_id: Unique identifier.
        name: Human-readable name (defaults to ID).
        projects: List of (project_id, path, role) tuples.
        root: Optional root directory for co-located projects.

    Returns:
        Created Workspace.

    Raises:
        WorkspaceRegistryError: If workspace already exists.
    """
    workspace_projects: list[WorkspaceProject] = []
    if projects:
        for i, (pid, path, role) in enumerate(projects):
            workspace_projects.append(
                WorkspaceProject(
                    id=pid,
                    path=path.resolve(),
                    role=role,
                    is_primary=i == 0,  # First project is primary
                )
            )

    workspace = Workspace(
        id=workspace_id,
        name=name or workspace_id,
        projects=tuple(workspace_projects),
        root=root.resolve() if root else None,
    )

    registry = WorkspaceRegistry()
    registry.create(workspace)

    return workspace


def get_default_workspace() -> Workspace | None:
    """Get the default Sunwell workspace.

    The default workspace contains all projects in ~/Sunwell/projects/.
    Created automatically if it doesn't exist.

    Returns:
        The default Sunwell workspace.
    """
    registry = WorkspaceRegistry()

    # Check if default workspace exists
    default = registry.get("sunwell-internal")
    if default:
        return default

    # Create default workspace
    from sunwell.knowledge.workspace.resolver import default_workspace_root

    sunwell_projects = default_workspace_root()
    if not sunwell_projects.exists():
        return None

    # Find all project directories
    projects: list[WorkspaceProject] = []
    try:
        for item in sunwell_projects.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                projects.append(
                    WorkspaceProject(
                        id=item.name,
                        path=item,
                        is_primary=len(projects) == 0,
                    )
                )
    except (OSError, PermissionError):
        pass

    default = Workspace(
        id="sunwell-internal",
        name="Sunwell Projects",
        projects=tuple(projects),
        root=sunwell_projects.parent,  # ~/Sunwell/
    )

    # Don't save automatically - let the system create it when needed
    return default
