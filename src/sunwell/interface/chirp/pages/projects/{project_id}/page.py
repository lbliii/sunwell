"""Project detail page."""

from chirp import NotFound, Page


def get(project_id: str) -> Page:
    """Render project detail page.

    Shows:
    - Project metadata
    - Recent runs
    - Quick actions (run, analyze, etc.)
    """
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    project = registry.get(project_id)

    if not project:
        raise NotFound(f"Project not found: {project_id}")

    # Check if valid
    valid = project.root.exists()

    # Check if default
    is_default = registry.default_project_id == project_id

    return Page(
        "projects/{project_id}/page.html",
        "content",
        current_page="projects",
        project={
            "id": project.id,
            "name": project.name,
            "root": str(project.root),
            "valid": valid,
            "is_default": is_default,
        },
        title=project.name,
    )
