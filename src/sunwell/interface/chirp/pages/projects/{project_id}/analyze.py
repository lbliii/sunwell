"""Analyze project structure and dependencies."""

from chirp import Fragment, Response


def post(project_id: str) -> Fragment | Response:
    """Analyze project structure and dependencies.

    Args:
        project_id: Project ID to analyze

    Returns:
        Success fragment or error response
    """
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    project = registry.get(project_id)

    if not project:
        return Response(
            f"Project not found: {project_id}",
            status=404,
        )

    if not project.root.exists():
        return Response(
            "Project path no longer exists",
            status=400,
        )

    # TODO: Implement actual project analysis
    # For now, return a success message
    return Fragment(
        "projects/{project_id}/_action_status.html",
        "action_status",
        success=True,
        message=f"Project analysis started for {project.name}. This feature is coming soon!",
    )
