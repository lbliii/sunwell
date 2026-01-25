"""Project lifecycle management routes (RFC-141).

Provides API endpoints for project lifecycle operations:
- Delete (unregister, purge, full)
- Rename/Move
- Cleanup orphaned data
- Active run checks

All endpoints delegate to WorkspaceManager since projects and workspaces
are conceptually the same in Sunwell.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes.models.base import CamelModel
from sunwell.knowledge.project import ProjectRegistry
from sunwell.knowledge.workspace import WorkspaceManager

router = APIRouter(prefix="/project", tags=["project"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class LifecycleDeleteResponse(CamelModel):
    """Response from project deletion."""

    status: str
    """Operation status: deleted, partial, error."""

    mode: str
    """Deletion mode used."""

    project_id: str
    """Project ID that was deleted."""

    deleted_items: list[str]
    """List of items that were deleted."""

    failed_items: list[str]
    """List of items that failed to delete."""

    runs_deleted: int
    """Number of runs deleted."""

    runs_orphaned: int
    """Number of runs marked as orphaned."""

    was_current: bool
    """Whether this was the current project."""

    error: str | None = None
    """Error message if operation failed."""


class UpdateProjectRequest(CamelModel):
    """Request to update project properties."""

    id: str | None = None
    """New project ID (for rename)."""

    name: str | None = None
    """New project name."""

    path: str | None = None
    """New project path (for move)."""


class UpdateProjectResponse(CamelModel):
    """Response from project update."""

    status: str
    """Operation status: updated, error."""

    old_id: str | None = None
    """Previous project ID (for rename)."""

    new_id: str | None = None
    """New project ID (for rename)."""

    old_path: str | None = None
    """Previous path (for move)."""

    new_path: str | None = None
    """New path (for move)."""

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
    """Project IDs with missing paths."""

    cleaned_runs: int
    """Number of runs cleaned."""

    cleaned_registrations: int
    """Number of invalid registrations removed."""


class ActiveRunsResponse(CamelModel):
    """Response with active runs for a project."""

    project_id: str
    """Project ID checked."""

    active_runs: list[str]
    """List of active run IDs."""

    has_active_runs: bool
    """Whether there are any active runs."""


# ═══════════════════════════════════════════════════════════════
# LIFECYCLE ENDPOINTS (RFC-141)
# ═══════════════════════════════════════════════════════════════


@router.delete("/lifecycle/{project_id}")
async def delete_project_lifecycle(
    project_id: str,
    mode: str = Query("unregister", description="Deletion mode: unregister, purge, full"),
    confirm: bool = Query(False, description="Confirm destructive operations"),
    delete_runs: bool = Query(False, description="Delete associated runs"),
    force: bool = Query(False, description="Force deletion with active runs"),
) -> LifecycleDeleteResponse:
    """Delete a project with full lifecycle management (RFC-141).

    Modes:
    - unregister: Remove from registry, keep all files
    - purge: Remove from registry and delete .sunwell/ directory
    - full: Remove from registry and delete entire project directory

    Args:
        project_id: The project ID to delete.
        mode: Deletion mode (unregister, purge, full).
        confirm: Required for purge/full modes.
        delete_runs: Whether to delete associated runs.
        force: Force deletion even if runs are active.

    Returns:
        LifecycleDeleteResponse with operation outcome.
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
            result = manager.unregister(project_id)
            return LifecycleDeleteResponse(
                status="deleted",
                mode=result.mode.value,
                project_id=result.workspace_id,
                deleted_items=list(result.deleted_items),
                failed_items=list(result.failed_items),
                runs_deleted=result.runs_deleted,
                runs_orphaned=result.runs_orphaned,
                was_current=result.was_current,
            )

        elif mode == "purge":
            result = manager.purge(
                project_id,
                delete_runs=delete_runs,
                force=force,
            )
            return LifecycleDeleteResponse(
                status="deleted" if result.success else "partial",
                mode="purge",
                project_id=result.workspace_id,
                deleted_items=list(result.deleted_dirs) + list(result.deleted_files),
                failed_items=list(result.failed_items),
                runs_deleted=result.runs_deleted,
                runs_orphaned=0,
                was_current=result.was_current,
                error=result.error,
            )

        else:  # mode == "full"
            result = manager.delete(
                project_id,
                delete_runs=delete_runs,
                force=force,
            )
            return LifecycleDeleteResponse(
                status="deleted" if result.success else "partial",
                mode=result.mode.value,
                project_id=result.workspace_id,
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


@router.patch("/lifecycle/{project_id}")
async def update_project_lifecycle(
    project_id: str,
    request: UpdateProjectRequest,
) -> UpdateProjectResponse:
    """Update project properties (RFC-141).

    Supports:
    - Rename: Change project ID and/or name
    - Move: Update project path after manual move

    Args:
        project_id: The project ID to update.
        request: Update request with new properties.

    Returns:
        UpdateProjectResponse with updated project info.
    """
    # Validate input before processing
    if request.id is None and request.name is None and request.path is None:
        raise HTTPException(
            status_code=400,
            detail="No update fields provided. Use id, name, or path.",
        )

    manager = WorkspaceManager()

    try:
        # Handle rename
        if request.id is not None or request.name is not None:
            new_id = request.id or project_id
            result = manager.rename(
                project_id,
                new_id=new_id,
                new_name=request.name,
            )

            return UpdateProjectResponse(
                status="updated",
                old_id=result.old_id,
                new_id=result.new_id,
                runs_updated=result.runs_updated,
            )

        # Handle move
        if request.path is not None:
            new_path = normalize_path(request.path)
            result = manager.move(project_id, new_path)

            return UpdateProjectResponse(
                status="updated",
                old_path=str(result.old_path),
                new_path=str(result.new_path),
            )

        # Should never reach here given the validation above
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


@router.post("/lifecycle/cleanup")
async def cleanup_orphaned(request: CleanupRequest) -> CleanupResponse:
    """Find and optionally clean up orphaned data (RFC-141).

    Finds:
    - Runs that reference non-existent projects
    - Registry entries with missing project paths

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


@router.get("/lifecycle/{project_id}/active-runs")
async def get_active_runs(project_id: str) -> ActiveRunsResponse:
    """Check for active runs in a project (RFC-141).

    Args:
        project_id: The project ID to check.

    Returns:
        ActiveRunsResponse with list of active run IDs.
    """
    manager = WorkspaceManager()

    try:
        active_runs = manager.has_active_runs(project_id)

        return ActiveRunsResponse(
            project_id=project_id,
            active_runs=active_runs,
            has_active_runs=len(active_runs) > 0,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check active runs: {type(e).__name__}"
        ) from e
