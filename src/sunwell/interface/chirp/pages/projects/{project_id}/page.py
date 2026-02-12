"""Project detail page."""

from chirp import FormAction, NotFound, Page, Response


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


def delete(project_id: str) -> FormAction | Response:
    """Delete a project.

    Args:
        project_id: Project ID to delete

    Returns:
        FormAction redirecting to projects list or error response
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import RegistryError

    registry = ProjectRegistry()

    # Validate project exists
    project = registry.get(project_id)
    if not project:
        return Response(
            f"Project not found: {project_id}",
            status=404,
        )

    # Check if it's the default project
    is_default = registry.default_project_id == project_id

    try:
        # Remove from registry
        registry.remove(project_id)

        # If it was the default, clear the default
        if is_default:
            # Try to set another project as default if one exists
            remaining_projects = registry.list_projects()
            if remaining_projects:
                registry.set_default(remaining_projects[0].id)

    except RegistryError as e:
        return Response(str(e), status=400)
    except Exception as e:
        return Response(f"Failed to delete project: {e}", status=500)

    # Redirect to projects list
    return FormAction("/projects")
