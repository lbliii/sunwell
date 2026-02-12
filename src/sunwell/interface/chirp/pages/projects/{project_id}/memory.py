"""View project memory page."""

from chirp import NotFound, Page


def get(project_id: str) -> Page:
    """View project-specific memory and learnings.

    Args:
        project_id: Project ID

    Returns:
        Page showing project memory
    """
    from pathlib import Path

    from sunwell.interface.chirp.services import MemoryService
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    project = registry.get(project_id)

    if not project:
        raise NotFound(f"Project not found: {project_id}")

    # Load memory for this specific project
    memory_svc = MemoryService(workspace=project.root)
    memories = memory_svc.list_memories(limit=100)

    return Page(
        "projects/{project_id}/memory.html",
        "content",
        current_page="projects",
        project={
            "id": project.id,
            "name": project.name,
            "root": str(project.root),
        },
        memories=memories,
        title=f"{project.name} - Memory",
    )
