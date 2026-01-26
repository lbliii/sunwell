"""Project types for RFC-117.

Defines the core Project entity and related types for workspace isolation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from sunwell.foundation.types.protocol import Serializable

__all__ = ["Serializable", "WorkspaceType", "AgentConfig", "ProjectManifest", "Project"]


class WorkspaceType(Enum):
    """How the workspace was established."""

    MANIFEST = "manifest"
    """Has .sunwell/project.toml — fully configured."""

    REGISTERED = "registered"
    """Manually registered via CLI, no manifest."""

    TEMPORARY = "temporary"
    """Ephemeral sandbox (e.g., benchmark runs)."""


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Agent-specific configuration from manifest.

    Attributes:
        trust: Default trust level for this project
        protected: Directories agent should NOT modify
    """

    trust: str = "workspace"
    """Default trust level (discovery, read_only, workspace, full)."""

    protected: tuple[str, ...] = (".git", "node_modules", "__pycache__")
    """Paths the agent should not modify."""


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    """Contents of .sunwell/project.toml.

    Attributes:
        id: Unique project identifier
        name: Human-readable name
        created: When project was initialized
        workspace_type: How workspace behaves (existing, sandboxed)
        agent: Agent-specific configuration
    """

    id: str
    """Unique identifier (e.g., 'my-fastapi-app')."""

    name: str
    """Human-readable name."""

    created: datetime
    """When this project was initialized."""

    workspace_type: str = "existing"
    """'existing' = write directly, 'sandboxed' = stage for review (future)."""

    agent: AgentConfig = field(default_factory=AgentConfig)
    """Agent-specific configuration."""

    @classmethod
    def from_dict(cls, data: dict) -> ProjectManifest:
        """Create manifest from parsed TOML dict."""
        project = data.get("project", {})
        workspace = data.get("workspace", {})
        agent_data = data.get("agent", {})

        # Parse created timestamp
        created_str = project.get("created", "")
        if created_str:
            # Handle both ISO format and date-only
            if "T" in created_str:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            else:
                created = datetime.fromisoformat(created_str)
        else:
            created = datetime.now()

        # Parse agent config
        agent = AgentConfig(
            trust=agent_data.get("trust", "workspace"),
            protected=tuple(agent_data.get("protected", [".git"])),
        )

        return cls(
            id=project.get("id", "unnamed"),
            name=project.get("name", project.get("id", "Unnamed Project")),
            created=created,
            workspace_type=workspace.get("type", "existing"),
            agent=agent,
        )

    def to_dict(self) -> dict:
        """Convert manifest to TOML-compatible dict."""
        return {
            "project": {
                "id": self.id,
                "name": self.name,
                "created": self.created.isoformat(),
            },
            "workspace": {
                "type": self.workspace_type,
            },
            "agent": {
                "trust": self.agent.trust,
                "protected": list(self.agent.protected),
            },
        }


@dataclass(frozen=True, slots=True)
class Project:
    """A project with explicit boundaries.

    Projects are first-class entities that define where the agent can
    read/write files. No more implicit cwd() — all file operations are
    scoped to a project.

    Projects can belong to a Workspace, which groups related projects
    (e.g., frontend + backend + shared). The workspace enables:
    - Cross-project context and memory
    - Smart query routing
    - Tiered indexing for scalability

    Attributes:
        id: Unique identifier (e.g., 'my-fastapi-app')
        name: Human-readable name
        root: Absolute path to project root
        workspace_type: How the workspace was created/validated
        created_at: When this project was registered
        manifest: Parsed manifest if .sunwell/project.toml exists
        workspace_id: ID of the workspace this project belongs to (if any)
    """

    id: str
    """Unique identifier."""

    name: str
    """Human-readable name."""

    root: Path
    """Absolute path to project root. All file ops relative to this."""

    workspace_type: WorkspaceType
    """How the workspace was established."""

    created_at: datetime
    """When this project was registered."""

    manifest: ProjectManifest | None = None
    """Parsed manifest if it exists."""

    workspace_id: str | None = None
    """ID of the workspace this project belongs to."""

    def __post_init__(self) -> None:
        """Validate project on construction."""
        # Ensure root is absolute
        if not self.root.is_absolute():
            object.__setattr__(self, "root", self.root.resolve())

    @property
    def manifest_path(self) -> Path:
        """Path to .sunwell/project.toml."""
        return self.root / ".sunwell" / "project.toml"

    @property
    def state_dir(self) -> Path:
        """Path to .sunwell/ directory for project state."""
        return self.root / ".sunwell"

    @property
    def trust_level(self) -> str:
        """Default trust level for this project."""
        if self.manifest:
            return self.manifest.agent.trust
        return "workspace"

    @property
    def protected_paths(self) -> tuple[str, ...]:
        """Paths the agent should not modify."""
        if self.manifest:
            return self.manifest.agent.protected
        return (".git",)

    def to_registry_entry(self) -> dict:
        """Convert to registry JSON format."""
        entry = {
            "root": str(self.root),
            "manifest": str(self.manifest_path) if self.manifest else None,
            "last_used": datetime.now().isoformat(),
            "workspace_type": self.workspace_type.value,
        }
        if self.workspace_id:
            entry["workspace_id"] = self.workspace_id
        return entry

    @classmethod
    def from_registry_entry(cls, project_id: str, entry: dict) -> Project:
        """Create Project from registry entry."""
        root = Path(entry["root"])
        workspace_type = WorkspaceType(entry.get("workspace_type", "registered"))
        workspace_id = entry.get("workspace_id")

        # Try to load manifest if it exists
        manifest = None
        manifest_path = root / ".sunwell" / "project.toml"
        if manifest_path.exists():
            from sunwell.knowledge.project.manifest import load_manifest

            manifest = load_manifest(manifest_path)
            workspace_type = WorkspaceType.MANIFEST

        return cls(
            id=project_id,
            name=manifest.name if manifest else project_id,
            root=root,
            workspace_type=workspace_type,
            created_at=manifest.created if manifest else datetime.now(),
            manifest=manifest,
            workspace_id=workspace_id,
        )
