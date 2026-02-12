"""Home page route using page convention."""

from chirp import Page
from sunwell.interface.chirp.services import ProjectService, SessionService


def get(project_svc: ProjectService, session_svc: SessionService) -> Page:
    """Render the home page.

    Shows:
    - Recent projects
    - Quick actions
    - System status
    """
    # Get real project data
    projects = project_svc.list_projects()

    # Take the 6 most recently used projects
    recent_projects = []
    for project in projects[:6]:
        recent_projects.append({
            "id": project["id"],
            "name": project["name"],
            "description": f"Project at {project['path']}",
            "last_modified": project["last_used"],
        })

    # Get system stats
    running_sessions = session_svc.get_running_count()

    return Page(
        "page.html",
        "content",
        current_page="home",
        recent_projects=recent_projects,
        running_sessions=running_sessions,
        project_count=len(projects),
        title="Home",
    )
