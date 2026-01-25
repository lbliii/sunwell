"""Core project operations: get, recent, scan, resume, open, delete, archive, iterate."""

import shutil
from pathlib import Path

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes._models import (
    CurrentProjectItem,
    CurrentProjectResponse,
    ProjectArchiveResponse,
    ProjectDeleteResponse,
    ProjectIterateResponse,
    RecentProjectItem,
    RecentProjectsResponse,
    ResumeProjectResponse,
    ResumeTaskItem,
    ScanProjectsResponse,
    ScannedProjectItem,
    ScannedProjectTask,
    SuccessResponse,
)
from sunwell.interface.server.routes.project_models import (
    IterateProjectRequest,
    ProjectPathRequest,
)

router = APIRouter(prefix="/project", tags=["project"])


@router.get("")
async def get_project() -> CurrentProjectResponse:
    """Get current project info."""
    cwd = Path.cwd()
    if not cwd.exists():
        return CurrentProjectResponse(project=None, workspace_root=str(cwd))
    return CurrentProjectResponse(
        project=CurrentProjectItem(
            id=str(hash(str(cwd))),
            name=cwd.name,
            root=str(cwd),
            trust="workspace",
            project_type=None,
        ),
        workspace_root=str(cwd),
    )


@router.get("/recent")
async def get_recent_projects() -> RecentProjectsResponse:
    """Get recently used projects sorted by last_used timestamp.

    Returns a simplified list of recent projects for quick access.
    Uses the registry's last_used tracking.
    """
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    recent: list[RecentProjectItem] = []

    for project in registry.list_projects():
        # Skip projects that no longer exist
        if not project.root.exists():
            continue

        # Get last_used from registry
        entry = registry.projects.get(project.id, {})
        last_used = entry.get("last_used")

        # Try to detect project type from files
        project_type = "general"
        if (project.root / "pyproject.toml").exists():
            project_type = "code_python"
        elif (project.root / "package.json").exists():
            project_type = "code_js"
        elif (project.root / "Cargo.toml").exists():
            project_type = "code_rust"
        elif (project.root / "go.mod").exists():
            project_type = "code_go"
        elif (project.root / "index.html").exists():
            project_type = "code_web"

        # Try to get description from manifest
        description: str | None = None
        manifest_path = project.root / ".sunwell" / "project.toml"
        if manifest_path.exists():
            try:
                import tomllib

                with open(manifest_path, "rb") as f:
                    manifest = tomllib.load(f)
                    description = manifest.get("project", {}).get("description")
            except Exception:
                pass

        recent.append(
            RecentProjectItem(
                path=str(project.root),
                name=project.name,
                project_type=project_type,
                description=description,
                last_opened=last_used or 0,
            )
        )

    # Sort by last_opened descending
    recent.sort(key=lambda p: p.last_opened, reverse=True)

    # Limit to most recent 20
    return RecentProjectsResponse(recent=recent[:20])


@router.get("/scan")
async def scan_projects() -> ScanProjectsResponse:
    """Scan for projects from registry and filesystem.

    Returns projects with their status, checkpoint info, and activity data.
    This is the primary endpoint for the Home page project list.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    registry = ProjectRegistry()
    projects: list[ScannedProjectItem] = []

    for project in registry.list_projects():
        # Get registry entry for last_used
        entry = registry.projects.get(project.id, {})
        last_used = entry.get("last_used")

        # Check if project root still exists
        if not project.root.exists():
            continue

        # Look for checkpoints to determine status
        checkpoint_dir = project.root / ".sunwell" / "checkpoints"
        status = "none"
        last_goal: str | None = None
        tasks_completed = 0
        tasks_total = 0
        tasks: list[ScannedProjectTask] = []
        last_activity = last_used

        if checkpoint_dir.exists():
            try:
                latest_cp = find_latest_checkpoint(checkpoint_dir)
                if latest_cp:
                    last_goal = latest_cp.goal
                    tasks_total = len(latest_cp.tasks)
                    tasks_completed = len(latest_cp.completed_ids)
                    last_activity = latest_cp.checkpoint_at.isoformat()

                    # Determine status from checkpoint phase
                    phase = latest_cp.phase.value
                    if phase in ("implementation_complete", "review_complete"):
                        status = "complete"
                    elif phase in ("task_complete", "plan_complete", "design_approved"):
                        status = "interrupted"  # Has progress but not complete
                    else:
                        status = "interrupted"

                    # Build task list
                    for task in latest_cp.tasks:
                        tasks.append(
                            ScannedProjectTask(
                                id=task.id,
                                description=task.description,
                                completed=task.id in latest_cp.completed_ids,
                            )
                        )
            except Exception:
                # If we can't read checkpoints, that's okay
                pass

        # Build display path (relative to home)
        try:
            display_path = f"~/{project.root.relative_to(Path.home())}"
        except ValueError:
            display_path = str(project.root)

        projects.append(
            ScannedProjectItem(
                id=project.id,
                path=str(project.root),
                display_path=display_path,
                name=project.name,
                status=status,
                last_goal=last_goal,
                tasks_completed=tasks_completed if tasks_total > 0 else None,
                tasks_total=tasks_total if tasks_total > 0 else None,
                tasks=tasks if tasks else None,
                last_activity=str(last_activity) if last_activity else None,
            )
        )

    # Sort by last_activity descending (most recent first)
    projects.sort(key=lambda p: p.last_activity or "", reverse=True)

    return ScanProjectsResponse(projects=projects, total=len(projects))


@router.post("/resume")
async def resume_project(request: ProjectPathRequest) -> ResumeProjectResponse:
    """Resume an interrupted project by loading its latest checkpoint.

    Finds the most recent checkpoint and returns info for the agent to resume.
    The actual resume is handled by the agent run flow.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    path = normalize_path(request.path)

    if not path.exists():
        return ResumeProjectResponse(
            goal=None, tasks=[], phase=None, checkpoint_exists=False
        )

    checkpoint_dir = path / ".sunwell" / "checkpoints"

    if not checkpoint_dir.exists():
        return ResumeProjectResponse(
            goal=None, tasks=[], phase=None, checkpoint_exists=False
        )

    try:
        latest_cp = find_latest_checkpoint(checkpoint_dir)
        if not latest_cp:
            return ResumeProjectResponse(
                goal=None, tasks=[], phase=None, checkpoint_exists=False
            )

        tasks = [
            ResumeTaskItem(
                id=task.id,
                description=task.description,
                completed=task.id in latest_cp.completed_ids,
            )
            for task in latest_cp.tasks
        ]

        return ResumeProjectResponse(
            goal=latest_cp.goal,
            tasks=tasks,
            phase=latest_cp.phase.value,
            checkpoint_exists=True,
        )
    except Exception:
        return ResumeProjectResponse(
            goal=None, tasks=[], phase=None, checkpoint_exists=False
        )


@router.post("/open")
async def open_project(request: ProjectPathRequest) -> SuccessResponse:
    """Open a project."""
    path = normalize_path(request.path)
    if not path.exists():
        return SuccessResponse(success=False, message=f"Path not found: {path}")
    return SuccessResponse(success=True, message=str(path))


@router.post("/delete")
async def delete_project(request: ProjectPathRequest) -> ProjectDeleteResponse:
    """Delete a project permanently.

    Removes from registry and optionally deletes files from disk.
    Currently only removes from registry (safe delete).
    """
    from sunwell.knowledge import ProjectRegistry

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)

    if not project:
        return ProjectDeleteResponse(
            success=False,
            message=f"Project not found in registry: {path}",
        )

    try:
        # Remove from registry
        registry.unregister(project.id)

        # Delete .sunwell directory (keeps user files, removes sunwell metadata)
        sunwell_dir = path / ".sunwell"
        if sunwell_dir.exists():
            shutil.rmtree(sunwell_dir)

        return ProjectDeleteResponse(
            success=True,
            message=f"Project '{project.name}' removed from registry",
        )
    except Exception as e:
        return ProjectDeleteResponse(
            success=False,
            message=f"Failed to delete project: {e}",
        )


@router.post("/archive")
async def archive_project(request: ProjectPathRequest) -> ProjectArchiveResponse:
    """Archive a project by moving to ~/Sunwell/archived/.

    Moves entire project directory and updates registry.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.workspace import default_workspace_root

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)

    if not project:
        return ProjectArchiveResponse(
            success=False,
            message=f"Project not found in registry: {path}",
            archive_path=None,
        )

    if not path.exists():
        # Project directory doesn't exist, just remove from registry
        registry.unregister(project.id)
        return ProjectArchiveResponse(
            success=True,
            message=f"Project '{project.name}' removed (directory not found)",
            archive_path=None,
        )

    try:
        # Create archive directory
        archive_root = default_workspace_root().parent / "archived"
        archive_root.mkdir(parents=True, exist_ok=True)

        # Generate unique archive name
        archive_name = project.name
        archive_path = archive_root / archive_name
        counter = 1
        while archive_path.exists():
            archive_name = f"{project.name}-{counter}"
            archive_path = archive_root / archive_name
            counter += 1

        # Move project directory
        shutil.move(str(path), str(archive_path))

        # Remove from registry
        registry.unregister(project.id)

        return ProjectArchiveResponse(
            success=True,
            message=f"Project '{project.name}' archived",
            archive_path=str(archive_path),
        )
    except Exception as e:
        return ProjectArchiveResponse(
            success=False,
            message=f"Failed to archive project: {e}",
            archive_path=None,
        )


@router.post("/iterate")
async def iterate_project(request: IterateProjectRequest) -> ProjectIterateResponse:
    """Create a new iteration of a project.

    Copies the project to a new location with learnings preserved.
    Useful for starting fresh while keeping accumulated knowledge.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import init_project
    from sunwell.knowledge.workspace import default_workspace_root

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)

    if not project:
        return ProjectIterateResponse(
            success=False,
            message=f"Project not found in registry: {path}",
            new_path=None,
        )

    if not path.exists():
        return ProjectIterateResponse(
            success=False,
            message=f"Project directory not found: {path}",
            new_path=None,
        )

    try:
        # Generate new iteration name
        base_name = project.name.rstrip("0123456789").rstrip("-v").rstrip("-")
        iteration = 2
        new_name = f"{base_name}-v{iteration}"
        new_path = default_workspace_root() / new_name.lower().replace(" ", "-")

        while new_path.exists() or registry.get(new_name.lower().replace(" ", "-")):
            iteration += 1
            new_name = f"{base_name}-v{iteration}"
            new_path = default_workspace_root() / new_name.lower().replace(" ", "-")

        # Create new project directory
        new_path.mkdir(parents=True, exist_ok=True)

        # Copy .sunwell directory (learnings, checkpoints, etc.)
        old_sunwell = path / ".sunwell"
        if old_sunwell.exists():
            new_sunwell = new_path / ".sunwell"
            shutil.copytree(old_sunwell, new_sunwell)

            # Update manifest with iteration info
            manifest_path = new_sunwell / "project.toml"
            if manifest_path.exists():
                try:
                    content = manifest_path.read_text()
                    # Add iteration note
                    if "[project]" in content:
                        content = content.replace(
                            "[project]",
                            f"[project]\n# Iterated from: {project.name}",
                        )
                    manifest_path.write_text(content)
                except Exception:
                    pass

        # Initialize as new project in registry
        init_project(
            root=new_path,
            project_id=new_name.lower().replace(" ", "-"),
            name=new_name,
            trust="workspace",
            register=True,
        )

        return ProjectIterateResponse(
            success=True,
            message=f"Created iteration '{new_name}' from '{project.name}'",
            new_path=str(new_path),
        )
    except Exception as e:
        return ProjectIterateResponse(
            success=False,
            message=f"Failed to iterate project: {e}",
            new_path=None,
        )
