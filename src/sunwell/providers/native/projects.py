"""Sunwell Native Projects Provider (RFC-078).

Local project tracking stored in .sunwell/projects.json.
"""

import json
from datetime import datetime
from pathlib import Path

from sunwell.providers.base import Project, ProjectsProvider


class SunwellProjects(ProjectsProvider):
    """Sunwell-native projects provider stored in .sunwell/projects.json."""

    def __init__(self, data_dir: Path, projects_root: Path | None = None) -> None:
        """Initialize with data directory.

        Args:
            data_dir: The .sunwell data directory.
            projects_root: Optional root directory for scanning projects.
                          Defaults to ~/Sunwell/projects/
        """
        self.data_dir = data_dir
        self.path = data_dir / "projects.json"
        self.projects_root = projects_root or Path.home() / "Sunwell" / "projects"
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        """Ensure the projects file exists."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]")

    def _load(self) -> list[dict]:
        """Load projects from JSON file."""
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, projects: list[dict]) -> None:
        """Save projects to JSON file."""
        self.path.write_text(json.dumps(projects, default=str, indent=2))

    def _dict_to_project(self, data: dict) -> Project:
        """Convert dictionary to Project."""
        last_opened = data.get("last_opened")
        if isinstance(last_opened, str):
            last_opened = datetime.fromisoformat(last_opened)
        elif last_opened is None:
            last_opened = datetime.now()

        return Project(
            path=data["path"],
            name=data.get("name", Path(data["path"]).name),
            last_opened=last_opened,
            status=data.get("status", "active"),
            description=data.get("description"),
        )

    async def list_projects(self) -> list[Project]:
        """List all known projects, sorted by last_opened (most recent first)."""
        data = self._load()
        projects = [self._dict_to_project(p) for p in data]
        return sorted(projects, key=lambda p: p.last_opened, reverse=True)

    async def get_project(self, path: str) -> Project | None:
        """Get a specific project by path."""
        data = self._load()
        for p in data:
            if p["path"] == path:
                return self._dict_to_project(p)
        return None

    async def search_projects(self, query: str) -> list[Project]:
        """Search projects by name (case-insensitive substring match)."""
        query_lower = query.lower()
        data = self._load()
        matching = []

        for p in data:
            name = p.get("name", Path(p["path"]).name)
            desc = p.get("description", "")
            if query_lower in name.lower() or (desc and query_lower in desc.lower()):
                matching.append(self._dict_to_project(p))

        return sorted(matching, key=lambda p: p.last_opened, reverse=True)

    async def update_last_opened(self, path: str) -> Project | None:
        """Update last_opened timestamp for a project.

        If project doesn't exist in registry, adds it.
        """
        data = self._load()
        now = datetime.now()

        for p in data:
            if p["path"] == path:
                p["last_opened"] = now.isoformat()
                self._save(data)
                return self._dict_to_project(p)

        # Project not found - add it
        project_path = Path(path)
        if not project_path.exists():
            return None

        new_project = {
            "path": path,
            "name": project_path.name,
            "last_opened": now.isoformat(),
            "status": "active",
            "description": None,
        }
        data.append(new_project)
        self._save(data)
        return self._dict_to_project(new_project)

    async def scan_projects(self) -> list[Project]:
        """Scan projects_root for projects and merge with existing.

        A directory is considered a project if it contains:
        - .sunwell/ directory
        - .git/ directory
        - pyproject.toml
        - package.json
        """
        if not self.projects_root.exists():
            return []

        existing = self._load()
        existing_paths = {p["path"] for p in existing}
        now = datetime.now()

        project_markers = [".sunwell", ".git", "pyproject.toml", "package.json"]

        for entry in self.projects_root.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue

            # Check for project markers
            is_project = any(
                (entry / marker).exists() for marker in project_markers
            )

            if is_project and str(entry) not in existing_paths:
                existing.append({
                    "path": str(entry),
                    "name": entry.name,
                    "last_opened": now.isoformat(),
                    "status": "active",
                    "description": None,
                })

        self._save(existing)
        return await self.list_projects()

    async def add_project(
        self,
        path: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Add a new project to the registry."""
        data = self._load()

        # Check if already exists
        for p in data:
            if p["path"] == path:
                return self._dict_to_project(p)

        project_path = Path(path)
        new_project = {
            "path": path,
            "name": name or project_path.name,
            "last_opened": datetime.now().isoformat(),
            "status": "active",
            "description": description,
        }
        data.append(new_project)
        self._save(data)
        return self._dict_to_project(new_project)

    async def archive_project(self, path: str) -> Project | None:
        """Mark a project as archived."""
        data = self._load()
        for p in data:
            if p["path"] == path:
                p["status"] = "archived"
                self._save(data)
                return self._dict_to_project(p)
        return None
