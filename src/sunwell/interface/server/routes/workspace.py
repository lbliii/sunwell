"""Workspace management routes (RFC-140, RFC-141).

Multi-project workspace container support added for mental models alignment.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes.models import CamelModel
from sunwell.knowledge.workspace import (
    ProjectRole,
    Workspace,
    WorkspaceInfo,
    WorkspaceManager,
    WorkspaceRegistry,
    WorkspaceRegistryError,
    WorkspaceStatus,
    sanitize_workspace_id,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class SwitchWorkspaceRequest(CamelModel):
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


class DeleteWorkspaceRequest(CamelModel):
    """Request to delete a workspace."""

    mode: str = "unregister"
    """Deletion mode: unregister, purge, or full."""

    confirm: bool = False
    """Confirmation required for purge/full modes."""

    delete_runs: bool = False
    """Whether to delete associated runs."""

    force: bool = False
    """Force deletion even if runs are active."""


class DeleteWorkspaceResponse(CamelModel):
    """Response from workspace deletion."""

    status: str
    """Operation status: deleted, error."""

    mode: str
    """Deletion mode used."""

    workspace_id: str
    """Workspace ID that was deleted."""

    deleted_items: list[str]
    """List of items that were deleted."""

    failed_items: list[str]
    """List of items that failed to delete."""

    runs_deleted: int
    """Number of runs deleted."""

    runs_orphaned: int
    """Number of runs marked as orphaned."""

    was_current: bool
    """Whether this was the current workspace."""

    error: str | None = None
    """Error message if operation failed."""


class UpdateWorkspaceRequest(CamelModel):
    """Request to update workspace properties."""

    id: str | None = None
    """New workspace ID (for rename)."""

    name: str | None = None
    """New workspace name."""

    path: str | None = None
    """New workspace path (for move)."""


class UpdateWorkspaceResponse(CamelModel):
    """Response from workspace update."""

    status: str
    """Operation status: updated, error."""

    workspace: WorkspaceInfoResponse | None = None
    """Updated workspace info."""

    runs_updated: int = 0
    """Number of runs updated (for rename)."""

    error: str | None = None
    """Error message if operation failed."""


class CleanupRequest(CamelModel):
    """Request to cleanup orphaned data."""

    dry_run: bool = True
    """If true, only report what would be cleaned."""


class CleanupResponse(CamelModel):
    """Response from cleanup operation."""

    dry_run: bool
    """Whether this was a dry run."""

    orphaned_runs: list[str]
    """Run IDs that are orphaned."""

    invalid_registrations: list[str]
    """Workspace IDs with missing paths."""

    cleaned_runs: int
    """Number of runs cleaned."""

    cleaned_registrations: int
    """Number of invalid registrations removed."""


class ActiveRunsResponse(CamelModel):
    """Response with active runs for a workspace."""

    workspace_id: str
    """Workspace ID checked."""

    active_runs: list[str]
    """List of active run IDs."""

    has_active_runs: bool
    """Whether there are any active runs."""


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


# ═══════════════════════════════════════════════════════════════
# LIFECYCLE ENDPOINTS (RFC-141)
# ═══════════════════════════════════════════════════════════════


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    mode: str = Query("unregister", description="Deletion mode: unregister, purge, full"),
    confirm: bool = Query(False, description="Confirm destructive operations"),
    delete_runs: bool = Query(False, description="Delete associated runs"),
    force: bool = Query(False, description="Force deletion with active runs"),
) -> DeleteWorkspaceResponse:
    """Delete a workspace.

    Modes:
    - unregister: Remove from registry, keep all files
    - purge: Remove from registry and delete .sunwell/ directory
    - full: Remove from registry and delete entire workspace directory

    Args:
        workspace_id: The workspace ID to delete.
        mode: Deletion mode (unregister, purge, full).
        confirm: Required for purge/full modes.
        delete_runs: Whether to delete associated runs.
        force: Force deletion even if runs are active.

    Returns:
        DeleteWorkspaceResponse with operation outcome.
    """
    # Validate mode
    valid_modes = {"unregister", "purge", "full"}
    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}. Must be one of: {valid_modes}",
        )

    # Require confirmation for destructive operations
    if mode in ("purge", "full") and not confirm:
        raise HTTPException(
            status_code=400,
            detail=f"Mode '{mode}' requires confirm=true",
        )

    manager = WorkspaceManager()

    try:
        if mode == "unregister":
            result = manager.unregister(workspace_id)
            return DeleteWorkspaceResponse(
                status="deleted",
                mode=result.mode.value,
                workspace_id=result.workspace_id,
                deleted_items=list(result.deleted_items),
                failed_items=list(result.failed_items),
                runs_deleted=result.runs_deleted,
                runs_orphaned=result.runs_orphaned,
                was_current=result.was_current,
            )

        elif mode == "purge":
            result = manager.purge(
                workspace_id,
                delete_runs=delete_runs,
                force=force,
            )
            return DeleteWorkspaceResponse(
                status="deleted" if result.success else "partial",
                mode="purge",
                workspace_id=result.workspace_id,
                deleted_items=list(result.deleted_dirs) + list(result.deleted_files),
                failed_items=list(result.failed_items),
                runs_deleted=result.runs_deleted,
                runs_orphaned=0,
                was_current=result.was_current,
                error=result.error,
            )

        else:  # mode == "full"
            result = manager.delete(
                workspace_id,
                delete_runs=delete_runs,
                force=force,
            )
            return DeleteWorkspaceResponse(
                status="deleted" if result.success else "partial",
                mode=result.mode.value,
                workspace_id=result.workspace_id,
                deleted_items=list(result.deleted_items),
                failed_items=list(result.failed_items),
                runs_deleted=result.runs_deleted,
                runs_orphaned=result.runs_orphaned,
                was_current=result.was_current,
                error=result.error,
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        # Active runs exist
        raise HTTPException(status_code=409, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Delete failed: {type(e).__name__}: {e}"
        ) from e


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    request: UpdateWorkspaceRequest,
) -> UpdateWorkspaceResponse:
    """Update workspace properties.

    Supports:
    - Rename: Change workspace ID and/or name
    - Move: Update workspace path after manual move

    Args:
        workspace_id: The workspace ID to update.
        request: Update request with new properties.

    Returns:
        UpdateWorkspaceResponse with updated workspace info.
    """
    manager = WorkspaceManager()

    try:
        # Handle rename
        if request.id is not None or request.name is not None:
            new_id = request.id or workspace_id
            result = manager.rename(
                workspace_id,
                new_id=new_id,
                new_name=request.name,
            )

            # Get updated workspace info
            updated_info = manager.get_current()
            if not updated_info or updated_info.id != result.new_id:
                # Get from registry
                from sunwell.knowledge.project import ProjectRegistry
                registry = ProjectRegistry()
                project = registry.get(result.new_id)
                if project:
                    updated_info = WorkspaceInfo(
                        id=project.id,
                        name=project.name,
                        path=project.root.resolve(),
                        is_registered=True,
                        is_current=False,
                        status=manager.get_status(project.root),
                        workspace_type=project.workspace_type.value,
                    )

            return UpdateWorkspaceResponse(
                status="updated",
                workspace=_workspace_info_to_response(updated_info) if updated_info else None,
                runs_updated=result.runs_updated,
            )

        # Handle move
        if request.path is not None:
            new_path = normalize_path(request.path)
            result = manager.move(workspace_id, new_path)

            # Get updated workspace info
            from sunwell.knowledge.project import ProjectRegistry
            registry = ProjectRegistry()
            project = registry.get(workspace_id)
            if project:
                updated_info = WorkspaceInfo(
                    id=project.id,
                    name=project.name,
                    path=project.root.resolve(),
                    is_registered=True,
                    is_current=False,
                    status=manager.get_status(project.root),
                    workspace_type=project.workspace_type.value,
                )
                return UpdateWorkspaceResponse(
                    status="updated",
                    workspace=_workspace_info_to_response(updated_info),
                )

            return UpdateWorkspaceResponse(
                status="updated",
                workspace=None,
            )

        # No update requested
        raise HTTPException(
            status_code=400,
            detail="No update fields provided. Use id, name, or path.",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Update failed: {type(e).__name__}: {e}"
        ) from e


@router.post("/cleanup")
async def cleanup_orphaned(request: CleanupRequest) -> CleanupResponse:
    """Find and optionally clean up orphaned data.

    Finds:
    - Runs that reference non-existent workspaces
    - Registry entries with missing workspace paths

    Args:
        request: Cleanup request with dry_run flag.

    Returns:
        CleanupResponse with findings and actions taken.
    """
    manager = WorkspaceManager()

    try:
        result = manager.cleanup_orphaned(dry_run=request.dry_run)

        return CleanupResponse(
            dry_run=result.dry_run,
            orphaned_runs=list(result.orphaned_runs),
            invalid_registrations=list(result.invalid_registrations),
            cleaned_runs=result.cleaned_runs,
            cleaned_registrations=result.cleaned_registrations,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Cleanup failed: {type(e).__name__}: {e}"
        ) from e


@router.get("/{workspace_id}/active-runs")
async def get_active_runs(workspace_id: str) -> ActiveRunsResponse:
    """Check for active runs in a workspace.

    Args:
        workspace_id: The workspace ID to check.

    Returns:
        ActiveRunsResponse with list of active run IDs.
    """
    manager = WorkspaceManager()

    try:
        active_runs = manager.has_active_runs(workspace_id)

        return ActiveRunsResponse(
            workspace_id=workspace_id,
            active_runs=active_runs,
            has_active_runs=len(active_runs) > 0,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check active runs: {type(e).__name__}"
        ) from e


# ═══════════════════════════════════════════════════════════════
# WORKSPACE CONTAINER ENDPOINTS (Multi-Project Architecture)
# ═══════════════════════════════════════════════════════════════


class ContainerProjectRequest(CamelModel):
    """Request to add a project to a container."""

    id: str
    """Project ID."""

    path: str
    """Project path."""

    role: str = "unknown"
    """Project role: frontend, backend, api, shared, etc."""

    is_primary: bool = False
    """Whether this is the primary project."""


class ContainerProjectResponse(CamelModel):
    """Project within a container."""

    id: str
    path: str
    role: str
    is_primary: bool


class ContainerResponse(CamelModel):
    """Workspace container response."""

    id: str
    name: str
    projects: list[ContainerProjectResponse]
    root: str | None
    created_at: str


class ContainerListResponse(CamelModel):
    """List of workspace containers."""

    containers: list[ContainerResponse]
    current: ContainerResponse | None = None


class CreateContainerRequest(CamelModel):
    """Request to create a workspace container."""

    id: str
    """Container ID."""

    name: str | None = None
    """Container name (defaults to ID)."""

    projects: list[ContainerProjectRequest] = []
    """Initial projects."""


def _workspace_to_container_response(ws: Workspace) -> ContainerResponse:
    """Convert Workspace to ContainerResponse."""
    return ContainerResponse(
        id=ws.id,
        name=ws.name,
        projects=[
            ContainerProjectResponse(
                id=p.id,
                path=str(p.path),
                role=p.role.value,
                is_primary=p.is_primary,
            )
            for p in ws.projects
        ],
        root=str(ws.root) if ws.root else None,
        created_at=ws.created_at.isoformat(),
    )


@router.get("/containers")
async def list_containers() -> ContainerListResponse:
    """List all workspace containers.

    Returns workspace containers that group related projects.
    """
    try:
        registry = WorkspaceRegistry()
        containers = registry.list_workspaces()

        # Determine current container (if any)
        manager = WorkspaceManager()
        current_project = manager.get_current()
        current_container = None

        if current_project:
            for ws in containers:
                if current_project.id in ws.project_ids:
                    current_container = ws
                    break

        return ContainerListResponse(
            containers=[_workspace_to_container_response(ws) for ws in containers],
            current=_workspace_to_container_response(current_container) if current_container else None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list containers: {type(e).__name__}"
        ) from e


@router.post("/containers")
async def create_container(request: CreateContainerRequest) -> ContainerResponse:
    """Create a new workspace container.

    Creates a container that groups related projects together.
    """
    try:
        registry = WorkspaceRegistry()

        # Build project list
        from sunwell.knowledge.workspace.types import WorkspaceProject

        projects: list[WorkspaceProject] = []
        for i, p in enumerate(request.projects):
            try:
                role = ProjectRole(p.role)
            except ValueError:
                role = ProjectRole.UNKNOWN

            projects.append(
                WorkspaceProject(
                    id=p.id,
                    path=Path(p.path).expanduser().resolve(),
                    role=role,
                    is_primary=p.is_primary or (i == 0 and not any(proj.is_primary for proj in request.projects)),
                )
            )

        ws = Workspace(
            id=request.id,
            name=request.name or request.id,
            projects=tuple(projects),
        )

        registry.create(ws)
        return _workspace_to_container_response(ws)

    except WorkspaceRegistryError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create container: {type(e).__name__}"
        ) from e


@router.get("/containers/{container_id}")
async def get_container(container_id: str) -> ContainerResponse:
    """Get a workspace container by ID."""
    try:
        registry = WorkspaceRegistry()
        ws = registry.get(container_id)

        if not ws:
            raise HTTPException(status_code=404, detail=f"Container not found: {container_id}")

        return _workspace_to_container_response(ws)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get container: {type(e).__name__}"
        ) from e


@router.delete("/containers/{container_id}")
async def delete_container(container_id: str) -> dict[str, str]:
    """Delete a workspace container.

    This only removes the container definition, not the projects themselves.
    """
    try:
        registry = WorkspaceRegistry()

        if not registry.delete(container_id):
            raise HTTPException(status_code=404, detail=f"Container not found: {container_id}")

        return {"status": "deleted", "container_id": container_id}
    except HTTPException:
        raise
    except WorkspaceRegistryError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete container: {type(e).__name__}"
        ) from e


@router.post("/containers/{container_id}/switch")
async def switch_to_container(container_id: str) -> ContainerResponse:
    """Switch to a workspace container.

    Sets the container's primary project as the current workspace.
    """
    try:
        registry = WorkspaceRegistry()
        ws = registry.get(container_id)

        if not ws:
            raise HTTPException(status_code=404, detail=f"Container not found: {container_id}")

        # Switch to primary project
        primary = ws.primary_project
        if not primary:
            raise HTTPException(status_code=400, detail="Container has no projects")

        manager = WorkspaceManager()
        manager.switch_workspace(primary.id)

        return _workspace_to_container_response(ws)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to switch container: {type(e).__name__}"
        ) from e


@router.post("/containers/{container_id}/projects")
async def add_project_to_container(
    container_id: str,
    request: ContainerProjectRequest,
) -> ContainerResponse:
    """Add a project to a workspace container."""
    try:
        registry = WorkspaceRegistry()

        try:
            role = ProjectRole(request.role)
        except ValueError:
            role = ProjectRole.UNKNOWN

        ws = registry.add_project(
            container_id,
            project_id=request.id,
            project_path=Path(request.path).expanduser().resolve(),
            role=role,
            is_primary=request.is_primary,
        )

        return _workspace_to_container_response(ws)
    except WorkspaceRegistryError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to add project: {type(e).__name__}"
        ) from e


@router.delete("/containers/{container_id}/projects/{project_id}")
async def remove_project_from_container(
    container_id: str,
    project_id: str,
) -> ContainerResponse:
    """Remove a project from a workspace container."""
    try:
        registry = WorkspaceRegistry()
        ws = registry.remove_project(container_id, project_id)

        return _workspace_to_container_response(ws)
    except WorkspaceRegistryError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to remove project: {type(e).__name__}"
        ) from e
