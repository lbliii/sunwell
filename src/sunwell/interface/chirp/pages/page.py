"""Home page route using page convention."""

from sunwell.interface.chirp.services import ProjectService, SessionService


def get(project_svc: ProjectService, session_svc: SessionService) -> dict:
    """Render the home page."""
    projects = project_svc.list_projects()

    recent_projects = [
        {
            "id": project["id"],
            "name": project["name"],
            "description": f"Project at {project['path']}",
            "last_modified": project["last_used"],
        }
        for project in projects[:6]
    ]

    running_sessions = session_svc.get_running_count()

    return {
        "recent_projects": recent_projects,
        "running_sessions": running_sessions,
        "project_count": len(projects),
        "page_title": "Home - Sunwell Studio",
        "breadcrumb_label": "Home",
    }
