"""Projects list page - Using ProjectService."""

from chirp import Page
from sunwell.interface.chirp.services import ProjectService


def get(project_svc: ProjectService) -> Page:
    """Render projects list page.

    Shows all registered projects with ability to:
    - Create new project
    - Set default project
    - View project details
    - See validity status

    Uses dependency injection to get ProjectService.
    """
    from sunwell.knowledge.project import validate_workspace
    from pathlib import Path

    # Get projects from service
    projects_raw = project_svc.list_projects()

    projects_data = []
    for proj in projects_raw:
        project_id = proj.get("id", "")
        project_name = proj.get("name", "")
        project_root = Path(proj.get("path", ""))

        # Check if still valid
        valid = True
        error_message = None
        try:
            if not project_root.exists():
                valid = False
                error_message = "Path no longer exists"
            else:
                validate_workspace(project_root)
        except Exception as e:
            valid = False
            error_message = str(e)

        # last_used already in proj from service
        last_used_float = proj.get("last_used", 0.0)

        projects_data.append({
            "id": project_id,
            "name": project_name,
            "root": str(project_root),
            "valid": valid,
            "error_message": error_message,
            "is_default": proj.get("is_default", False),
            "last_used": last_used_float,
        })

    # Sort by last_used descending (already sorted by service, but ensure it)
    projects_data.sort(key=lambda p: p["last_used"], reverse=True)

    # Check if any project is default
    has_default = any(p["is_default"] for p in projects_data)

    return Page(
        "projects/page.html",
        "content",
        current_page="projects",
        projects=projects_data,
        has_default=has_default,
        page_title="Projects - Sunwell Studio",
        breadcrumb_label="Projects",
    )
