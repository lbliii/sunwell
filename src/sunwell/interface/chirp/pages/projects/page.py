"""Projects list page."""

from chirp import Page


def get() -> Page:
    """Render projects list page.

    Shows all registered projects with ability to:
    - Create new project
    - Set default project
    - View project details
    - See validity status
    """
    # TODO: Inject ProjectRegistry via service provider
    # For now, access directly
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import validate_workspace

    registry = ProjectRegistry()
    default_id = registry.default_project_id
    projects_data = []

    for project in registry.list_projects():
        # Check if still valid
        valid = True
        error_message = None
        try:
            if not project.root.exists():
                valid = False
                error_message = "Path no longer exists"
            else:
                validate_workspace(project.root)
        except Exception as e:
            valid = False
            error_message = str(e)

        # Get last_used from registry
        entry = registry.projects.get(project.id, {})
        last_used = entry.get("last_used")

        # Convert last_used to float if it's a string/timestamp
        last_used_float = 0.0
        if last_used:
            try:
                last_used_float = float(last_used)
            except (ValueError, TypeError):
                last_used_float = 0.0

        projects_data.append({
            "id": project.id,
            "name": project.name,
            "root": str(project.root),
            "valid": valid,
            "error_message": error_message,
            "is_default": (project.id == default_id),
            "last_used": last_used_float,
        })

    # Sort by last_used descending
    projects_data.sort(key=lambda p: p["last_used"], reverse=True)

    return Page(
        "projects/page.html",
        "content",
        current_page="projects",
        projects=projects_data,
        has_default=default_id is not None,
        title="Projects",
    )
