"""Workspace types for multi-project architecture.

A Workspace is a lightweight container that groups related Projects.
This enables:
- Cross-project context (shared memory, knowledge)
- Smart query routing (determine which projects a query relates to)
- Tiered indexing (L0 manifest, L1 signatures, L2 full, L3 deep)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

__all__ = [
    "IndexTier",
    "ProjectRole",
    "WorkspaceProject",
    "WorkspaceDependencies",
    "Workspace",
]


class IndexTier(Enum):
    """Indexing tiers for scalable multi-project workspaces.

    L0: Manifest - Project list, roles, dependencies (instant)
    L1: Signatures - Exports, public APIs, types (lightweight, background)
    L2: Full - Everything in active project (on focus)
    L3: Deep - Cross-project detailed search (on demand)
    """

    L0_MANIFEST = "l0_manifest"
    L1_SIGNATURES = "l1_signatures"
    L2_FULL = "l2_full"
    L3_DEEP = "l3_deep"


class ProjectRole(Enum):
    """Semantic role hints for projects in a workspace.

    Used by query routing to understand project relationships.
    """

    FRONTEND = "frontend"
    BACKEND = "backend"
    API = "api"
    SHARED = "shared"
    INFRA = "infra"
    DOCS = "docs"
    MOBILE = "mobile"
    CLI = "cli"
    LIBRARY = "library"
    MONOREPO = "monorepo"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class WorkspaceProject:
    """A project reference within a workspace.

    This is a lightweight reference, not the full Project object.
    The full Project is loaded lazily when needed.
    """

    id: str
    """Project identifier."""

    path: Path
    """Absolute path to project root."""

    role: ProjectRole = ProjectRole.UNKNOWN
    """Semantic role hint for query routing."""

    is_primary: bool = False
    """Whether this is the primary/default project in the workspace."""

    def to_dict(self) -> dict:
        """Convert to TOML-serializable dict."""
        return {
            "id": self.id,
            "path": str(self.path),
            "role": self.role.value,
            "is_primary": self.is_primary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceProject":
        """Create from parsed dict."""
        role_str = data.get("role", "unknown")
        try:
            role = ProjectRole(role_str)
        except ValueError:
            role = ProjectRole.UNKNOWN

        return cls(
            id=data["id"],
            path=Path(data["path"]).expanduser().resolve(),
            role=role,
            is_primary=data.get("is_primary", False),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceDependencies:
    """Explicit dependency relationships between projects.

    Example: frontend depends on shared, backend depends on shared.
    Used by query routing to include shared dependencies.
    """

    edges: tuple[tuple[str, str], ...]
    """(from_project_id, to_project_id) dependency edges."""

    def get_dependencies(self, project_id: str) -> tuple[str, ...]:
        """Get projects that the given project depends on."""
        return tuple(dep for src, dep in self.edges if src == project_id)

    def get_dependents(self, project_id: str) -> tuple[str, ...]:
        """Get projects that depend on the given project."""
        return tuple(src for src, dep in self.edges if dep == project_id)

    def get_shared_dependencies(self, project_ids: list[str]) -> tuple[str, ...]:
        """Get common dependencies for multiple projects."""
        if not project_ids:
            return ()

        dep_sets = [set(self.get_dependencies(pid)) for pid in project_ids]
        if not dep_sets:
            return ()

        # Intersection of all dependency sets
        common = dep_sets[0]
        for deps in dep_sets[1:]:
            common &= deps

        return tuple(common)

    def to_dict(self) -> dict[str, list[str]]:
        """Convert to TOML-serializable dict."""
        result: dict[str, list[str]] = {}
        for src, dep in self.edges:
            if src not in result:
                result[src] = []
            result[src].append(dep)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> "WorkspaceDependencies":
        """Create from parsed dict."""
        edges: list[tuple[str, str]] = []
        for src, deps in data.items():
            for dep in deps:
                edges.append((src, dep))
        return cls(edges=tuple(edges))


@dataclass(frozen=True, slots=True)
class Workspace:
    """A workspace grouping related projects.

    Workspaces are lightweight containers that:
    - Group related projects (e.g., frontend + backend + shared)
    - Enable cross-project context and memory
    - Support tiered indexing for scalability
    - Allow smart query routing based on project roles

    The default Sunwell workspace contains all projects in ~/Sunwell/projects/.
    Custom workspaces can group external projects anywhere on disk.
    """

    id: str
    """Unique workspace identifier."""

    name: str
    """Human-readable name."""

    projects: tuple[WorkspaceProject, ...]
    """Projects in this workspace."""

    dependencies: WorkspaceDependencies = field(
        default_factory=lambda: WorkspaceDependencies(edges=())
    )
    """Explicit project dependency relationships."""

    created_at: datetime = field(default_factory=datetime.now)
    """When this workspace was created."""

    root: Path | None = None
    """Optional root directory (for co-located projects like ~/Sunwell/)."""

    @property
    def project_ids(self) -> tuple[str, ...]:
        """All project IDs in this workspace."""
        return tuple(p.id for p in self.projects)

    @property
    def primary_project(self) -> WorkspaceProject | None:
        """Get the primary project, or first project if none marked."""
        for p in self.projects:
            if p.is_primary:
                return p
        return self.projects[0] if self.projects else None

    def get_project(self, project_id: str) -> WorkspaceProject | None:
        """Get a project by ID."""
        for p in self.projects:
            if p.id == project_id:
                return p
        return None

    def get_projects_by_role(self, role: ProjectRole) -> tuple[WorkspaceProject, ...]:
        """Get all projects with a specific role."""
        return tuple(p for p in self.projects if p.role == role)

    def to_dict(self) -> dict:
        """Convert to TOML-serializable dict."""
        return {
            "workspace": {
                "id": self.id,
                "name": self.name,
                "created": self.created_at.isoformat(),
                "root": str(self.root) if self.root else None,
            },
            "projects": [p.to_dict() for p in self.projects],
            "dependencies": self.dependencies.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workspace":
        """Create from parsed TOML dict."""
        ws_data = data.get("workspace", {})

        # Parse created timestamp
        created_str = ws_data.get("created", "")
        if created_str:
            if "T" in created_str:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            else:
                created = datetime.fromisoformat(created_str)
        else:
            created = datetime.now()

        # Parse root
        root_str = ws_data.get("root")
        root = Path(root_str).expanduser().resolve() if root_str else None

        # Parse projects
        projects_data = data.get("projects", [])
        projects = tuple(WorkspaceProject.from_dict(p) for p in projects_data)

        # Parse dependencies
        deps_data = data.get("dependencies", {})
        dependencies = WorkspaceDependencies.from_dict(deps_data)

        return cls(
            id=ws_data.get("id", "unnamed"),
            name=ws_data.get("name", ws_data.get("id", "Unnamed Workspace")),
            projects=projects,
            dependencies=dependencies,
            created_at=created,
            root=root,
        )

    @classmethod
    def single_project(cls, project_id: str, project_path: Path, name: str | None = None) -> "Workspace":
        """Create a workspace with a single project.

        Convenience factory for the common case of working with one project.
        """
        return cls(
            id=project_id,
            name=name or project_id,
            projects=(
                WorkspaceProject(
                    id=project_id,
                    path=project_path,
                    is_primary=True,
                ),
            ),
        )
