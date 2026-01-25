"""Session management for RFC-101: Session Identity System."""

import json
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING

from sunwell.memory.simulacrum.core.dag import ConversationDAG

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore


class SessionManager:
    """Manages session lifecycle with project-scoped storage (RFC-101)."""

    def __init__(
        self,
        base_path: Path,
        hot_dag_getter: Callable[[], ConversationDAG],
        hot_dag_setter: Callable[[ConversationDAG], None],
        unified_store: "UnifiedMemoryStore | None" = None,
    ) -> None:
        """Initialize session manager.

        Args:
            base_path: Base directory for storage
            hot_dag_getter: Function to get current hot DAG
            hot_dag_setter: Function to set hot DAG
            unified_store: Optional unified memory store
        """
        self.base_path = base_path
        self._get_hot_dag = hot_dag_getter
        self._set_hot_dag = hot_dag_setter
        self._unified_store = unified_store
        self._session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._project: str = "default"
        self._session_uri: str | None = None

    def new_session(
        self,
        name: str | None = None,
        project: str | None = None,
    ) -> str:
        """Start a new conversation session.

        RFC-101: Sessions are now project-scoped to prevent collisions.

        Args:
            name: Optional session name (defaults to timestamp)
            project: Optional project slug (defaults to current project)

        Returns:
            Session ID (slug)
        """
        self._session_id = name or datetime.now().strftime("%Y%m%d_%H%M%S")
        if project:
            self._project = project
        self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"
        self._set_hot_dag(ConversationDAG())
        return self._session_id

    @property
    def session_uri(self) -> str:
        """Get the full session URI (RFC-101)."""
        if not self._session_uri:
            self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"
        return self._session_uri

    @property
    def project(self) -> str:
        """Get the current project slug."""
        return self._project

    def set_project(self, project: str) -> None:
        """Set the project context for session scoping.

        Args:
            project: Project slug
        """
        self._project = project
        # Update URI if session exists
        if self._session_id:
            self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"

    def list_sessions(self, project: str | None = None) -> list[dict[str, Any]]:
        """List all saved sessions.

        RFC-101: Can filter by project.

        Args:
            project: Optional project filter (None = all projects)

        Returns:
            List of session metadata dicts
        """
        sessions = []

        # RFC-101: Check project-scoped sessions first
        projects_dir = self.base_path / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    if project and project_dir.name != project:
                        continue
                    for path in project_dir.glob("*.json"):
                        if path.stem.endswith("_dag"):
                            continue
                        try:
                            with open(path) as f:
                                meta = json.load(f)
                            sessions.append({
                                "id": path.stem,
                                "uri": f"sunwell:session/{project_dir.name}/{path.stem}",
                                "project": project_dir.name,
                                "name": meta.get("name", path.stem),
                                "created": meta.get("created"),
                                "turns": meta.get("turn_count", 0),
                                "path": str(path),
                            })
                        except (json.JSONDecodeError, OSError):
                            continue

        return sorted(sessions, key=lambda s: s.get("created") or "", reverse=True)

    def save_session(self, name: str | None = None) -> Path:
        """Save current session to disk.

        RFC-101: Saves to project-scoped directory.
        """
        session_name = name or self._session_id

        # RFC-101: Use project-scoped storage
        session_dir = self.base_path / "projects" / self._project
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save DAG
        dag_path = session_dir / f"{session_name}_dag.json"
        self._get_hot_dag().save(dag_path)

        # Save unified store (RFC-014)
        if self._unified_store:
            self._unified_store.save()

        # Save metadata with identity info (RFC-101)
        meta_path = session_dir / f"{session_name}.json"
        meta = {
            "name": session_name,
            "uri": f"sunwell:session/{self._project}/{session_name}",
            "project": self._project,
            "created": datetime.now().isoformat(),
            "turn_count": len(self._get_hot_dag().turns),
            "stats": self._get_hot_dag().stats,
            "unified_store_nodes": len(self._unified_store._nodes) if self._unified_store else 0,
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        return meta_path

    def load_session(
        self,
        session_id: str,
        project: str | None = None,
    ) -> ConversationDAG:
        """Load a saved session.

        RFC-101: Supports loading by URI or slug with project context.

        Args:
            session_id: Session slug or full URI
            project: Optional project context (for slug resolution)

        Returns:
            Loaded ConversationDAG

        Raises:
            FileNotFoundError: If session not found
        """
        # Parse URI if provided
        if session_id.startswith("sunwell:session/"):
            parts = session_id[17:].split("/", 1)  # Remove "sunwell:session/"
            if len(parts) == 2:
                project = parts[0]
                session_id = parts[1]

        # Set project context
        if project:
            self._project = project

        # Use project-scoped path (RFC-101)
        dag_path = self.base_path / "projects" / self._project / f"{session_id}_dag.json"
        if not dag_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        loaded_dag = ConversationDAG.load(dag_path)
        self._set_hot_dag(loaded_dag)
        self._session_id = session_id
        self._session_uri = f"sunwell:session/{self._project}/{self._session_id}"

        return loaded_dag
