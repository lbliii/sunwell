"""Workspace management routes (RFC-140)."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes.models import CamelModel
from sunwell.knowledge.workspace import (
    WorkspaceInfo,
    WorkspaceManager,
    WorkspaceStatus,
    sanitize_workspace_id,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class SwitchWorkspaceRequest(BaseModel):
    """Request to switch workspace."""

    workspace_id: str | None = None
    """Workspace ID or path."""


class WorkspaceInfoResponse(CamelModel):
    """Workspace information response."""

    id: str
    name: str
    path: str
    is_registered: bool
    is_current: bool
    status: str
    workspace_type: str
    last_used: str | None = None


class WorkspaceListResponse(CamelModel):
    """List of workspaces."""

    workspaces: list[WorkspaceInfoResponse]
    current: WorkspaceInfoResponse | None = None


class WorkspaceStatusResponse(CamelModel):
    """Workspace status response."""

    status: str
    valid: bool
    path: str


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════


def _workspace_info_to_response(info: WorkspaceInfo) -> WorkspaceInfoResponse:
    """Convert WorkspaceInfo to response model."""
    return WorkspaceInfoResponse(
        id=info.id,
        name=info.name,
        path=str(info.path),
        is_registered=info.is_registered,
        is_current=info.is_current,
        status=info.status.value,
        workspace_type=info.workspace_type,
        last_used=info.last_used,
    )


@router.get("/list")
async def list_workspaces() -> WorkspaceListResponse:
    """List all workspaces (registered + discovered).

    Returns workspaces sorted by: current first, then registered, then by last_used.
    """
    try:
        manager = WorkspaceManager()
        workspaces = manager.discover_workspaces()
        current = manager.get_current()

        return WorkspaceListResponse(
            workspaces=[_workspace_info_to_response(w) for w in workspaces],
            current=_workspace_info_to_response(current) if current else None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list workspaces: {type(e).__name__}"
        ) from e


@router.get("/current")
async def get_current_workspace() -> WorkspaceInfoResponse | None:
    """Get current workspace.

    Returns None if no current workspace is set.
    """
    try:
        manager = WorkspaceManager()
        current = manager.get_current()

        if not current:
            return None

        return _workspace_info_to_response(current)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get current workspace: {type(e).__name__}"
        ) from e


@router.post("/switch")
async def switch_workspace(request: SwitchWorkspaceRequest) -> WorkspaceInfoResponse:
    """Switch workspace context.

    Sets the workspace as current and updates last_used if registered.
    """
    if not request.workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")

    manager = WorkspaceManager()

    try:
        workspace_info = manager.switch_workspace(request.workspace_id)
        return _workspace_info_to_response(workspace_info)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {type(e).__name__}"
        ) from e


@router.post("/discover")
async def discover_workspaces(root: str | None = Query(None)) -> WorkspaceListResponse:
    """Trigger workspace discovery scan.

    Args:
        root: Optional root directory to scan (defaults to common locations)

    Returns:
        List of discovered workspaces
    """
    manager = WorkspaceManager()
    scan_root = None

    try:
        if root:
            scan_root = Path(root).resolve()
            if not scan_root.is_dir():
                raise HTTPException(
                    status_code=400, detail=f"Root must be a directory: {root}"
                )
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        workspaces = manager.discover_workspaces(scan_root)
        current = manager.get_current()

        return WorkspaceListResponse(
            workspaces=[_workspace_info_to_response(w) for w in workspaces],
            current=_workspace_info_to_response(current) if current else None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Discovery failed: {type(e).__name__}"
        ) from e


@router.get("/status")
async def get_workspace_status(path: str = Query(...)) -> WorkspaceStatusResponse:
    """Get workspace status/health.

    Args:
        path: Workspace path

    Returns:
        Workspace status information
    """
    try:
        workspace_path = normalize_path(path)
    except (ValueError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

    try:
        manager = WorkspaceManager()
        status = manager.get_status(workspace_path)

        return WorkspaceStatusResponse(
            status=status.value,
            valid=status == WorkspaceStatus.VALID,
            path=str(workspace_path),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Status check failed: {type(e).__name__}"
        ) from e


@router.get("/info")
async def get_workspace_info(path: str = Query(...)) -> WorkspaceInfoResponse:
    """Get detailed workspace information.

    Args:
        path: Workspace path

    Returns:
        Detailed workspace information
    """
    try:
        workspace_path = normalize_path(path)
    except (ValueError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

    try:
        manager = WorkspaceManager()

        # Try to find in registry first
        from sunwell.knowledge.project import ProjectRegistry

        registry = ProjectRegistry()
        project = registry.find_by_root(workspace_path)

        if project:
            current = manager.get_current()
            is_current = (
                current is not None
                and current.path.resolve().resolve()
                == workspace_path.resolve().resolve()
            )
            status = manager.get_status(workspace_path)
            last_used = registry.projects.get(project.id, {}).get("last_used")

            info = WorkspaceInfo(
                id=project.id,
                name=project.name,
                path=project.root.resolve().resolve(),  # Canonical
                is_registered=True,
                is_current=is_current,
                status=status,
                workspace_type=project.workspace_type.value,
                last_used=last_used,
                project=project,
            )
        else:
            # Not registered, create info from path
            if not workspace_path.exists():
                raise HTTPException(
                    status_code=404, detail=f"Workspace not found: {workspace_path}"
                )

            current = manager.get_current()
            is_current = (
                current is not None
                and current.path.resolve().resolve()
                == workspace_path.resolve().resolve()
            )
            status = manager.get_status(workspace_path)

            info = WorkspaceInfo(
                id=sanitize_workspace_id(workspace_path.name),
                name=workspace_path.name,
                path=workspace_path.resolve().resolve(),  # Canonical
                is_registered=False,
                is_current=is_current,
                status=status,
                workspace_type="discovered",
            )

        return _workspace_info_to_response(info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workspace info: {type(e).__name__}"
        ) from e
