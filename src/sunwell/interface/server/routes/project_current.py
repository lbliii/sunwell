"""Current project operations (RFC-140)."""

from pathlib import Path

from fastapi import APIRouter

from sunwell.interface.server.routes._models import (
    CurrentProjectItem,
    CurrentProjectResponse,
    SuccessResponse,
)
from sunwell.interface.server.routes.project_models import SwitchProjectRequest

router = APIRouter(prefix="/project", tags=["project"])


@router.get("/current")
async def get_current_project() -> CurrentProjectResponse:
    """Get current project (RFC-140).

    Returns current workspace/project if set, otherwise returns default project.
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()
    current = manager.get_current()

    if current and current.project:
        return CurrentProjectResponse(
            project=CurrentProjectItem(
                id=current.project.id,
                name=current.project.name,
                root=str(current.project.root),
                trust="workspace",
                project_type=None,
            ),
            workspace_root=str(current.project.root),
        )

    # Fallback to default project
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    default = registry.get_default()

    if default:
        return CurrentProjectResponse(
            project=CurrentProjectItem(
                id=default.id,
                name=default.name,
                root=str(default.root),
                trust="workspace",
                project_type=None,
            ),
            workspace_root=str(default.root),
        )

    return CurrentProjectResponse(project=None, workspace_root=str(Path.cwd()))


@router.post("/switch")
async def switch_project(request: SwitchProjectRequest) -> SuccessResponse:
    """Switch project context (RFC-140).

    Sets the project as current workspace.
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()

    try:
        workspace_info = manager.switch_workspace(request.project_id)
        return SuccessResponse(
            success=True,
            message=f"Switched to {workspace_info.name}",
        )
    except ValueError as e:
        return SuccessResponse(
            success=False,
            message=str(e),
        )
