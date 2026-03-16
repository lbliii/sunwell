"""Projects list page - Using ProjectService."""

from pathlib import Path

from sunwell.interface.chirp.services import ProjectService


def get(project_svc: ProjectService) -> dict:
    """Render projects list page."""
    from sunwell.knowledge.project import validate_workspace

    projects_raw = project_svc.list_projects()

    projects_data = []
    for proj in projects_raw:
        project_id = proj.get("id", "")
        project_name = proj.get("name", "")
        project_root = Path(proj.get("path", ""))

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

        projects_data.append(
            {
                "id": project_id,
                "name": project_name,
                "root": str(project_root),
                "valid": valid,
                "error_message": error_message,
                "is_default": proj.get("is_default", False),
                "last_used": proj.get("last_used", 0.0),
            }
        )

    projects_data.sort(key=lambda p: p["last_used"], reverse=True)
    has_default = any(p["is_default"] for p in projects_data)

    return {
        "projects": projects_data,
        "has_default": has_default,
        "page_title": "Projects - Sunwell Studio",
        "breadcrumb_label": "Projects",
    }
