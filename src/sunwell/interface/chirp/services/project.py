"""Project management service for Chirp interface."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sunwell.knowledge.project.registry import ProjectRegistry


@dataclass
class ProjectService:
    """Service for project management."""

    def __init__(self):
        self.registry = ProjectRegistry()

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects with metadata.

        Returns:
            List of project dicts with id, name, path, last_used, etc.
        """
        projects = []
        default_id = self.registry.default_project_id

        for project in self.registry.list_projects():
            # Validate project still exists
            if not project.root.exists():
                continue

            # Get last_used timestamp (convert datetime to float)
            last_used_float = 0.0
            if project.created_at:
                try:
                    last_used_float = project.created_at.timestamp()
                except (AttributeError, TypeError):
                    pass

            projects.append({
                "id": project.id,
                "name": project.name,
                "path": str(project.root),
                "last_used": last_used_float,
                "is_default": project.id == default_id,
            })

        # Sort by last_used (most recent first)
        projects.sort(key=lambda p: p["last_used"], reverse=True)

        return projects

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Get single project by ID."""
        project = self.registry.get(project_id)
        if not project:
            return None

        last_used_float = 0.0
        if project.created_at:
            try:
                last_used_float = project.created_at.timestamp()
            except (AttributeError, TypeError):
                pass

        return {
            "id": project.id,
            "name": project.name,
            "path": str(project.root),
            "last_used": last_used_float,
            "is_default": project.id == self.registry.default_project_id,
        }

    def create_project(self, name: str, path: str | None = None) -> dict[str, Any]:
        """Create new project.

        Args:
            name: Project name
            path: Optional project path (defaults to current dir)

        Returns:
            Created project dict
        """
        from sunwell.knowledge.project.init import init_project

        project_path = Path(path) if path else Path.cwd()
        init_project(project_path, name=name)

        return {
            "id": name,  # TODO: Generate proper ID
            "name": name,
            "path": str(project_path),
            "last_used": 0.0,
            "is_default": False,
        }

    def set_default_project(self, project_id: str) -> bool:
        """Set default project.

        Args:
            project_id: Project ID to set as default

        Returns:
            True if successful
        """
        return self.registry.set_default_project(project_id)
