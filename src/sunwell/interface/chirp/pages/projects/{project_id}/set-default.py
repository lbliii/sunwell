"""Set project as default."""

from chirp import FormAction, Response


def post(project_id: str) -> FormAction | Response:
    """Set this project as the default project.

    Redirects back to projects list.
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

    try:
        registry.set_default(project_id)
    except RegistryError as e:
        return Response(str(e), status=400)

    # Redirect to projects list
    return FormAction("/projects")
