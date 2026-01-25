"""Project resolver for RFC-117.

Resolves project context from various sources with explicit precedence.
"""

from pathlib import Path

from sunwell.knowledge.project.manifest import ManifestError, load_manifest
from sunwell.knowledge.project.registry import ProjectRegistry
from sunwell.knowledge.project.types import Project, WorkspaceType
from sunwell.knowledge.project.validation import ProjectValidationError, validate_workspace


class ProjectResolutionError(Exception):
    """Raised when project cannot be resolved."""


class ProjectResolver:
    """Resolves project from context with explicit precedence.

    Resolution order:
    1. Explicit --project-root flag (with validation)
    2. Explicit -p <project-id> flag
    3. .sunwell/project.toml in current directory
    4. Default project from registry
    5. ERROR — no implicit fallback to cwd()

    Example:
        >>> resolver = ProjectResolver()
        >>> project = resolver.resolve(project_root="/path/to/project")
        >>> project = resolver.resolve(project_id="my-app")
        >>> project = resolver.resolve()  # Uses cwd manifest or default
    """

    def __init__(self) -> None:
        """Initialize resolver with registry."""
        self._registry = ProjectRegistry()

    def resolve(
        self,
        *,
        project_root: str | Path | None = None,
        project_id: str | None = None,
        cwd: Path | None = None,
    ) -> Project:
        """Resolve project from provided context.

        Args:
            project_root: Explicit path to project root (highest priority)
            project_id: Project ID from registry
            cwd: Current working directory (for manifest detection)

        Returns:
            Resolved Project instance

        Raises:
            ProjectResolutionError: If no project can be resolved
            ProjectValidationError: If project root is invalid
        """
        # Priority 1: Explicit project root
        if project_root:
            return self._from_root(Path(project_root))

        # Priority 2: Project ID from registry
        if project_id:
            return self._from_registry(project_id)

        # Priority 3: Manifest in current directory
        if cwd:
            project = self._from_cwd_manifest(cwd)
            if project:
                return project

        # Priority 4: Default project from registry
        default = self._registry.get_default()
        if default:
            self._registry.update_last_used(default.id)
            return default

        # Priority 5: Error — no implicit fallback
        raise ProjectResolutionError(
            "No project context found.\n\n"
            "Options:\n"
            "  1. Run from a directory with .sunwell/project.toml\n"
            "  2. Use -p <project-id> to specify a registered project\n"
            "  3. Use --project-root <path> to specify a path\n"
            "  4. Set a default project: sunwell project default <id>\n\n"
            "To initialize a new project:\n"
            "  sunwell project init ."
        )

    def _from_root(self, root: Path) -> Project:
        """Create project from explicit root path."""
        root = root.resolve()

        # Validate the workspace
        validate_workspace(root)

        # Check for existing manifest
        manifest_path = root / ".sunwell" / "project.toml"
        if manifest_path.exists():
            try:
                manifest = load_manifest(manifest_path)
                return Project(
                    id=manifest.id,
                    name=manifest.name,
                    root=root,
                    workspace_type=WorkspaceType.MANIFEST,
                    created_at=manifest.created,
                    manifest=manifest,
                )
            except ManifestError:
                pass  # Fall through to unmanifested project

        # Create project without manifest
        project_id = root.name.lower().replace(" ", "-")
        return Project(
            id=project_id,
            name=root.name,
            root=root,
            workspace_type=WorkspaceType.REGISTERED,
            created_at=__import__("datetime").datetime.now(),
            manifest=None,
        )

    def _from_registry(self, project_id: str) -> Project:
        """Get project from registry by ID."""
        project = self._registry.get(project_id)
        if not project:
            # List available projects for helpful error
            available = [p.id for p in self._registry.list_projects()]
            if available:
                available_str = ", ".join(available)
                raise ProjectResolutionError(
                    f"Project not found: {project_id}\n"
                    f"Available projects: {available_str}"
                )
            else:
                raise ProjectResolutionError(
                    f"Project not found: {project_id}\n"
                    f"No projects registered. Run 'sunwell project init .' to create one."
                )

        # Validate the workspace still exists and is valid
        if not project.root.exists():
            raise ProjectResolutionError(
                f"Project root no longer exists: {project.root}\n"
                f"Remove with: sunwell project remove {project_id}"
            )

        try:
            validate_workspace(project.root)
        except ProjectValidationError as e:
            raise ProjectResolutionError(
                f"Project {project_id} has invalid workspace:\n{e}"
            ) from e

        self._registry.update_last_used(project_id)
        return project

    def _from_cwd_manifest(self, cwd: Path) -> Project | None:
        """Try to load project from manifest in cwd."""
        manifest_path = cwd / ".sunwell" / "project.toml"
        if not manifest_path.exists():
            return None

        try:
            # Validate first
            validate_workspace(cwd)

            manifest = load_manifest(manifest_path)
            return Project(
                id=manifest.id,
                name=manifest.name,
                root=cwd.resolve(),
                workspace_type=WorkspaceType.MANIFEST,
                created_at=manifest.created,
                manifest=manifest,
            )
        except (ManifestError, ProjectValidationError):
            return None


def resolve_project(
    *,
    project_root: str | Path | None = None,
    project_id: str | None = None,
    cwd: Path | None = None,
) -> Project:
    """Convenience function to resolve project.

    See ProjectResolver.resolve() for details.
    """
    resolver = ProjectResolver()
    return resolver.resolve(
        project_root=project_root,
        project_id=project_id,
        cwd=cwd,
    )
