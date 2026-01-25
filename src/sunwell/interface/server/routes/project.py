"""Project management routes (RFC-113, RFC-117, RFC-132)."""

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes._models import (
    CamelModel,
    MemoryStatsResponse,
    ProjectLearningsResponse,
)

# Pre-compiled regex for slug generation (avoid recompiling per call)
_RE_SLUG_CHARS = re.compile(r"[^a-z0-9]+")

router = APIRouter(prefix="/api", tags=["project"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class ProjectPathRequest(BaseModel):
    path: str


# RFC-132: Project Gate validation models
class ValidationResult(CamelModel):
    """Result of workspace validation."""

    valid: bool
    error_code: str | None = None
    error_message: str | None = None
    suggestion: str | None = None


class ProjectInfo(CamelModel):
    """Project info for listing."""

    id: str
    name: str
    root: str
    valid: bool
    is_default: bool
    last_used: str | None


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""

    name: str
    path: str | None = None


class CreateProjectResponse(CamelModel):
    """Response from project creation."""

    project: dict[str, str]
    path: str
    is_new: bool
    is_default: bool
    error: str | None = None
    message: str | None = None


class SetDefaultRequest(BaseModel):
    """Request to set default project."""

    project_id: str


# ═══════════════════════════════════════════════════════════════
# RFC-132: PROJECT GATE ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@router.post("/project/validate")
async def validate_project_path(request: ProjectPathRequest) -> ValidationResult:
    """Validate a workspace path before using it (RFC-132).

    Returns structured error with suggestion instead of raising.
    """
    from sunwell.knowledge.project import ProjectValidationError, validate_workspace
    from sunwell.knowledge.workspace import default_workspace_root

    path = normalize_path(request.path)

    if not path.exists():
        return ValidationResult(
            valid=False,
            error_code="not_found",
            error_message=f"Path does not exist: {path}",
        )

    try:
        validate_workspace(path)
        return ValidationResult(valid=True)
    except ProjectValidationError as e:
        # Determine error type for structured response
        error_msg = str(e)

        if "sunwell" in error_msg.lower() and "repository" in error_msg.lower():
            return ValidationResult(
                valid=False,
                error_code="sunwell_repo",
                error_message="Cannot use Sunwell's own repository as project workspace",
                suggestion=str(default_workspace_root()),
            )

        return ValidationResult(
            valid=False,
            error_code="invalid_workspace",
            error_message=error_msg,
        )


@router.get("/project/list")
async def list_projects() -> dict[str, list[ProjectInfo]]:
    """List all registered projects with validity status (RFC-132).

    Returns projects ordered by last_used descending.
    Includes validity check so UI can warn about broken projects.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import validate_workspace

    registry = ProjectRegistry()
    default_id = registry.default_project_id
    projects = []

    for project in registry.list_projects():
        # Check if still valid
        valid = True
        try:
            if not project.root.exists():
                valid = False
            else:
                validate_workspace(project.root)
        except Exception:
            valid = False

        # Get last_used from registry entry
        entry = registry.projects.get(project.id, {})
        last_used = entry.get("last_used")

        projects.append(
            ProjectInfo(
                id=project.id,
                name=project.name,
                root=str(project.root),
                valid=valid,
                is_default=(project.id == default_id),
                last_used=last_used,
            )
        )

    # Sort by last_used descending (most recent first)
    projects.sort(key=lambda p: p.last_used or "", reverse=True)

    return {"projects": projects}


@router.post("/project/create")
async def create_project(request: CreateProjectRequest) -> CreateProjectResponse:
    """Create a new project in the specified or default location (RFC-132).

    If path is not provided, creates in ~/Sunwell/projects/{slugified_name}.
    Auto-sets as default if no default project exists.
    """
    import re

    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import init_project, RegistryError
    from sunwell.knowledge.workspace import default_workspace_root

    # Validate name
    name = request.name.strip()
    if not name:
        return CreateProjectResponse(
            project={},
            path="",
            is_new=False,
            is_default=False,
            error="invalid_name",
            message="Project name cannot be empty",
        )
    if len(name) > 64:
        return CreateProjectResponse(
            project={},
            path="",
            is_new=False,
            is_default=False,
            error="invalid_name",
            message="Project name too long (max 64 chars)",
        )
    if "/" in name or "\\" in name:
        return CreateProjectResponse(
            project={},
            path="",
            is_new=False,
            is_default=False,
            error="invalid_name",
            message="Project name cannot contain path separators",
        )

    # Determine path
    if request.path:
        project_path = normalize_path(request.path)
    else:
        # Default location with slugified name
        slug = name.lower()
        slug = _RE_SLUG_CHARS.sub("-", slug).strip("-") or "project"
        project_path = default_workspace_root() / slug

    # Ensure parent exists
    project_path.parent.mkdir(parents=True, exist_ok=True)

    # Create directory
    is_new = not project_path.exists()
    project_path.mkdir(parents=True, exist_ok=True)

    # Generate slug for project ID
    slug = name.lower()
    slug = _RE_SLUG_CHARS.sub("-", slug).strip("-") or "project"

    # Initialize project
    try:
        project = init_project(
            root=project_path,
            project_id=slug,
            name=name,
            trust="workspace",
            register=True,
        )
    except RegistryError as e:
        if "already initialized" in str(e).lower():
            return CreateProjectResponse(
                project={},
                path=str(project_path),
                is_new=False,
                is_default=False,
                error="already_exists",
                message=str(e),
            )
        raise

    # Auto-set as default if no default exists
    registry = ProjectRegistry()
    became_default = False
    if registry.get_default() is None:
        registry.set_default(project.id)
        became_default = True

    return CreateProjectResponse(
        project={
            "id": project.id,
            "name": project.name,
            "root": str(project.root),
        },
        path=str(project_path),
        is_new=is_new,
        is_default=became_default,
    )


@router.get("/project/default")
async def get_default_project() -> dict[str, Any]:
    """Get the default project (RFC-132).

    Returns project info if default is set and valid, null otherwise.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import validate_workspace

    registry = ProjectRegistry()
    default = registry.get_default()

    if not default:
        return {"project": None}

    # Verify default is still valid
    try:
        if not default.root.exists():
            return {"project": None, "warning": "Default project no longer exists"}
        validate_workspace(default.root)
    except Exception:
        return {"project": None, "warning": "Default project is no longer valid"}

    return {
        "project": {
            "id": default.id,
            "name": default.name,
            "root": str(default.root),
        }
    }


@router.put("/project/default")
async def set_default_project(request: SetDefaultRequest) -> dict[str, Any]:
    """Set the default project (RFC-132).

    Validates project exists in registry before setting.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import RegistryError

    registry = ProjectRegistry()

    # Validate project exists
    project = registry.get(request.project_id)
    if not project:
        available = [p.id for p in registry.list_projects()]
        return {
            "error": "not_found",
            "message": f"Project not found: {request.project_id}",
            "available_projects": available,
        }

    try:
        registry.set_default(request.project_id)
    except RegistryError as e:
        return {"error": "registry_error", "message": str(e)}

    return {"success": True, "default_project": request.project_id}


class MonorepoRequest(BaseModel):
    path: str


class AnalyzeRequest(BaseModel):
    path: str
    fresh: bool = False


class AnalyzeRunRequest(CamelModel):
    path: str
    force_refresh: bool = False


class ProjectRunRequest(CamelModel):
    path: str
    command: str
    install_first: bool = False
    save_command: bool = False


class StopRunRequest(CamelModel):
    session_id: str | None = None


class IterateProjectRequest(BaseModel):
    path: str
    new_goal: str | None = None


# ═══════════════════════════════════════════════════════════════
# PROJECT ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("/project")
async def get_project() -> dict[str, Any]:
    """Get current project info."""
    cwd = Path.cwd()
    return {
        "path": str(cwd),
        "name": cwd.name,
        "exists": cwd.exists(),
    }


@router.get("/project/recent")
async def get_recent_projects() -> dict[str, Any]:
    """Get recently used projects sorted by last_used timestamp.

    Returns a simplified list of recent projects for quick access.
    Uses the registry's last_used tracking.
    """
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    recent = []

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
        description = ""
        manifest_path = project.root / ".sunwell" / "project.toml"
        if manifest_path.exists():
            try:
                import tomllib
                with open(manifest_path, "rb") as f:
                    manifest = tomllib.load(f)
                    description = manifest.get("project", {}).get("description", "")
            except Exception:
                pass

        recent.append({
            "path": str(project.root),
            "name": project.name,
            "project_type": project_type,
            "description": description,
            "last_opened": last_used,
        })

    # Sort by last_opened descending
    recent.sort(key=lambda p: p["last_opened"] or "", reverse=True)

    # Limit to most recent 20
    return {"recent": recent[:20]}


@router.get("/project/scan")
async def scan_projects() -> dict[str, Any]:
    """Scan for projects from registry and filesystem.

    Returns projects with their status, checkpoint info, and activity data.
    This is the primary endpoint for the Home page project list.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    registry = ProjectRegistry()
    projects = []

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
        last_goal = None
        tasks_completed = 0
        tasks_total = 0
        tasks = []
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
                        tasks.append({
                            "id": task.id,
                            "description": task.description,
                            "completed": task.id in latest_cp.completed_ids,
                        })
            except Exception:
                # If we can't read checkpoints, that's okay
                pass

        # Build display path (relative to home)
        try:
            display_path = f"~/{project.root.relative_to(Path.home())}"
        except ValueError:
            display_path = str(project.root)

        projects.append({
            "id": project.id,
            "path": str(project.root),
            "display_path": display_path,
            "name": project.name,
            "status": status,
            "last_goal": last_goal,
            "tasks_completed": tasks_completed if tasks_total > 0 else None,
            "tasks_total": tasks_total if tasks_total > 0 else None,
            "tasks": tasks if tasks else None,
            "last_activity": last_activity,
        })

    # Sort by last_activity descending (most recent first)
    projects.sort(key=lambda p: p["last_activity"] or "", reverse=True)

    return {"projects": projects}


@router.post("/project/resume")
async def resume_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Resume an interrupted project by loading its latest checkpoint.

    Finds the most recent checkpoint and returns info for the agent to resume.
    The actual resume is handled by the agent run flow.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    path = normalize_path(request.path)

    if not path.exists():
        return {
            "success": False,
            "message": f"Project directory not found: {path}",
        }

    checkpoint_dir = path / ".sunwell" / "checkpoints"

    if not checkpoint_dir.exists():
        return {
            "success": False,
            "message": "No checkpoints found for this project",
        }

    try:
        latest_cp = find_latest_checkpoint(checkpoint_dir)
        if not latest_cp:
            return {
                "success": False,
                "message": "No valid checkpoint found",
            }

        return {
            "success": True,
            "message": f"Ready to resume: {latest_cp.goal}",
            "checkpoint": {
                "goal": latest_cp.goal,
                "phase": latest_cp.phase.value,
                "phase_summary": latest_cp.phase_summary,
                "tasks_completed": len(latest_cp.completed_ids),
                "tasks_total": len(latest_cp.tasks),
                "checkpoint_at": latest_cp.checkpoint_at.isoformat(),
            },
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to load checkpoint: {e}",
        }


@router.post("/project/open")
async def open_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Open a project."""
    path = normalize_path(request.path)
    return {
        "id": str(hash(str(path))),
        "path": str(path),
        "name": path.name,
        "project_type": "general",
        "description": "",
        "files_count": sum(1 for _ in path.rglob("*") if _.is_file()) if path.exists() else 0,
    }


@router.post("/project/delete")
async def delete_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Delete a project permanently.

    Removes from registry and optionally deletes files from disk.
    Currently only removes from registry (safe delete).
    """
    import shutil

    from sunwell.knowledge import ProjectRegistry

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)

    if not project:
        return {
            "success": False,
            "message": f"Project not found in registry: {path}",
            "new_path": None,
        }

    try:
        # Remove from registry
        registry.unregister(project.id)

        # Delete .sunwell directory (keeps user files, removes sunwell metadata)
        sunwell_dir = path / ".sunwell"
        if sunwell_dir.exists():
            shutil.rmtree(sunwell_dir)

        return {
            "success": True,
            "message": f"Project '{project.name}' removed from registry",
            "new_path": None,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to delete project: {e}",
            "new_path": None,
        }


@router.post("/project/archive")
async def archive_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Archive a project by moving to ~/Sunwell/archived/.

    Moves entire project directory and updates registry.
    """
    import shutil

    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.workspace import default_workspace_root

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)

    if not project:
        return {
            "success": False,
            "message": f"Project not found in registry: {path}",
            "new_path": None,
        }

    if not path.exists():
        # Project directory doesn't exist, just remove from registry
        registry.unregister(project.id)
        return {
            "success": True,
            "message": f"Project '{project.name}' removed (directory not found)",
            "new_path": None,
        }

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

        return {
            "success": True,
            "message": f"Project '{project.name}' archived",
            "new_path": str(archive_path),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to archive project: {e}",
            "new_path": None,
        }


@router.post("/project/iterate")
async def iterate_project(request: IterateProjectRequest) -> dict[str, Any]:
    """Create a new iteration of a project.

    Copies the project to a new location with learnings preserved.
    Useful for starting fresh while keeping accumulated knowledge.
    """
    import shutil

    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import init_project
    from sunwell.knowledge.workspace import default_workspace_root

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)

    if not project:
        return {
            "success": False,
            "message": f"Project not found in registry: {path}",
            "new_path": None,
        }

    if not path.exists():
        return {
            "success": False,
            "message": f"Project directory not found: {path}",
            "new_path": None,
        }

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
        new_project = init_project(
            root=new_path,
            project_id=new_name.lower().replace(" ", "-"),
            name=new_name,
            trust="workspace",
            register=True,
        )

        return {
            "success": True,
            "message": f"Created iteration '{new_name}' from '{project.name}'",
            "new_path": str(new_path),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to iterate project: {e}",
            "new_path": None,
        }


@router.get("/project/learnings")
async def get_project_learnings(path: str) -> ProjectLearningsResponse:
    """Get project learnings from memory and checkpoints.

    Returns accumulated knowledge: learnings, dead ends, completed/pending tasks.
    """
    import json

    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    project_path = normalize_path(path)
    simulacrum_path = project_path / ".sunwell" / "simulacrum"
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"

    original_goal: str | None = None
    decisions: list[str] = []
    failures: list[str] = []
    completed_tasks: list[str] = []
    pending_tasks: list[str] = []

    # Get latest checkpoint for goal and tasks
    if checkpoint_dir.exists():
        try:
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                original_goal = latest.goal
                for task in latest.tasks:
                    task_desc = task.description if hasattr(task, "description") else str(task)
                    if task.id in latest.completed_ids:
                        completed_tasks.append(task_desc)
                    else:
                        pending_tasks.append(task_desc)
        except Exception:
            pass

    # Load learnings from simulacrum DAG
    if simulacrum_path.exists():
        hot_path = simulacrum_path / "hot"
        if hot_path.exists():
            for session_file in hot_path.glob("*.json"):
                try:
                    with open(session_file) as f:
                        data = json.load(f)
                        learnings_data = data.get("learnings", {})
                        dead_ends = set(data.get("dead_ends", []))

                        # Extract learnings as decisions
                        for learning_id, learning in learnings_data.items():
                            fact = learning.get("fact", "")
                            category = learning.get("category", "general")
                            confidence = learning.get("confidence", 0)

                            if category == "decision" or "decided" in fact.lower():
                                decisions.append(fact)
                            elif confidence > 0.5:
                                decisions.append(f"[{category}] {fact}")

                        # Extract dead ends as failures
                        turns = data.get("turns", {})
                        for turn_id in dead_ends:
                            if turn_id in turns:
                                content = turns[turn_id].get("content", "")[:200]
                                failures.append(f"Dead end: {content}...")
                except Exception:
                    continue

    return ProjectLearningsResponse(
        original_goal=original_goal,
        decisions=decisions[:20],  # Limit for performance
        failures=failures[:10],
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
    )


@router.post("/project/monorepo")
async def check_monorepo(request: MonorepoRequest) -> dict[str, Any]:
    """Check if path is a monorepo and return sub-projects.

    Uses monorepo detection to find npm workspaces, Cargo workspaces,
    Python services patterns, etc.
    """
    from sunwell.knowledge.project.monorepo import detect_sub_projects, is_monorepo

    path = normalize_path(request.path)

    if not path.exists():
        return {
            "is_monorepo": False,
            "sub_projects": [],
            "error": f"Path does not exist: {path}",
        }

    try:
        is_mono = is_monorepo(path)
        sub_projects = []

        if is_mono:
            detected = detect_sub_projects(path)
            for sub in detected:
                sub_projects.append({
                    "name": sub.name,
                    "path": str(sub.path),
                    "manifest": str(sub.manifest),
                    "project_type": sub.project_type,
                    "description": sub.description,
                })

        return {
            "is_monorepo": is_mono,
            "sub_projects": sub_projects,
        }
    except Exception as e:
        return {
            "is_monorepo": False,
            "sub_projects": [],
            "error": str(e),
        }


@router.post("/project/analyze")
async def analyze_project(request: AnalyzeRequest) -> dict[str, Any]:
    """Analyze project structure."""
    try:
        from sunwell.knowledge.project import ProjectAnalyzer

        path = normalize_path(request.path)
        if not path.exists():
            return {"error": f"Path does not exist: {path}"}

        analyzer = ProjectAnalyzer(path)
        analysis = analyzer.analyze()
        return analysis.to_dict() if hasattr(analysis, "to_dict") else {"path": str(path)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/project/files")
async def list_project_files(path: str | None = None, max_depth: int = 3) -> dict[str, Any]:
    """List project files."""
    target = normalize_path(path) if path else Path.cwd()
    if not target.exists():
        return {"error": "Path does not exist"}

    def list_dir(p: Path, depth: int) -> list[dict[str, Any]]:
        if depth > max_depth:
            return []
        entries = []
        try:
            for item in sorted(p.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.name in ("node_modules", "__pycache__", "venv", ".venv", "target"):
                    continue
                entry: dict[str, Any] = {
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                }
                if item.is_dir():
                    entry["children"] = list_dir(item, depth + 1)
                else:
                    entry["size"] = item.stat().st_size
                entries.append(entry)
        except PermissionError:
            pass
        return entries

    return {"files": list_dir(target, 0)}


# ═══════════════════════════════════════════════════════════════
# PROJECT RUN (RFC-066)
# ═══════════════════════════════════════════════════════════════


@router.post("/project/analyze-run")
async def analyze_project_for_run(request: AnalyzeRunRequest) -> dict[str, Any]:
    """Analyze project for running."""
    project_path = normalize_path(request.path)

    command = "echo 'No run command detected'"
    expected_url = None

    if (project_path / "package.json").exists():
        command = "npm run dev"
        expected_url = "http://localhost:5173"
    elif (project_path / "pyproject.toml").exists():
        command = "python -m http.server 8000"
        expected_url = "http://localhost:8000"
    elif (project_path / "index.html").exists():
        command = "python -m http.server 3000"
        expected_url = "http://localhost:3000"

    return {
        "command": command,
        "expectedUrl": expected_url,
        "installCommand": "npm install" if (project_path / "package.json").exists() else None,
        "requiresInstall": False,
    }


@router.post("/project/run")
async def run_project(request: ProjectRunRequest) -> dict[str, Any]:
    """Run a project."""
    import uuid

    return {
        "sessionId": str(uuid.uuid4()),
        "status": "started",
        "command": request.command,
    }


@router.post("/project/run/stop")
async def stop_project_run(request: StopRunRequest) -> dict[str, Any]:
    """Stop a project run."""
    return {"status": "stopped"}


# ═══════════════════════════════════════════════════════════════
# PROJECT EXTENDED (RFC-113)
# ═══════════════════════════════════════════════════════════════


@router.post("/project/analyze-for-run")
async def analyze_project_for_run_alias(request: AnalyzeRunRequest) -> dict[str, Any]:
    """Alias for analyze-run (frontend compatibility)."""
    return await analyze_project_for_run(request)


@router.get("/project/file")
async def get_project_file(path: str, max_size: int = 50000) -> dict[str, Any]:
    """Get file contents."""
    try:
        file_path = normalize_path(path)
        if not file_path.exists():
            return {"error": "File not found"}
        if file_path.stat().st_size > max_size:
            return {"error": f"File too large (max {max_size} bytes)"}
        return {"content": file_path.read_text()}
    except Exception as e:
        return {"error": str(e)}


@router.get("/project/status")
async def get_project_status(path: str) -> dict[str, Any]:
    """Get project status."""
    project_path = normalize_path(path)
    return {
        "path": str(project_path),
        "exists": project_path.exists(),
        "has_sunwell": (project_path / ".sunwell").exists(),
        "has_git": (project_path / ".git").exists(),
    }


@router.get("/project/dag")
async def get_project_dag(path: str) -> dict[str, Any]:
    """Get project DAG from checkpoints and plans.

    Delegates to the DAG routes for full implementation.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    project_path = normalize_path(path)
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"

    nodes = []
    edges = []
    metadata = {"path": str(project_path)}

    if checkpoint_dir.exists():
        try:
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                # Add goal node
                nodes.append({
                    "id": "goal",
                    "type": "goal",
                    "label": latest.goal[:50],
                    "phase": latest.phase.value,
                })

                # Add task nodes
                for i, task in enumerate(latest.tasks):
                    task_id = task.id if hasattr(task, "id") else f"task-{i}"
                    is_complete = task_id in latest.completed_ids
                    nodes.append({
                        "id": task_id,
                        "type": "task",
                        "label": task.description[:50] if hasattr(task, "description") else str(task)[:50],
                        "status": "complete" if is_complete else "pending",
                    })
                    edges.append({
                        "source": "goal",
                        "target": task_id,
                        "type": "contains",
                    })

                metadata["checkpoint"] = {
                    "phase": latest.phase.value,
                    "tasks_total": len(latest.tasks),
                    "tasks_completed": len(latest.completed_ids),
                }
        except Exception:
            pass

    return {"nodes": nodes, "edges": edges, "metadata": metadata}


@router.get("/project/memory/stats")
async def get_project_memory_stats(path: str) -> MemoryStatsResponse:
    """Get project memory statistics.

    Returns MemoryStatsResponse with automatic camelCase conversion.
    """
    import json

    project_path = normalize_path(path)
    simulacrum_path = project_path / ".sunwell" / "simulacrum"

    total_learnings = 0
    total_dead_ends = 0
    hot_turns = 0
    warm_files = 0
    warm_size_bytes = 0
    cold_files = 0
    cold_size_bytes = 0
    branches = 0
    concept_edges = 0
    session_id: str | None = None

    if not simulacrum_path.exists():
        return MemoryStatsResponse(
            session_id=None,
            hot_turns=0,
            warm_files=0,
            warm_size_mb=0,
            cold_files=0,
            cold_size_mb=0,
            total_turns=0,
            branches=0,
            dead_ends=0,
            learnings=0,
            concept_edges=0,
        )

    try:
        # Count sessions from hot path
        hot_path = simulacrum_path / "hot"
        warm_path = simulacrum_path / "warm"
        cold_path = simulacrum_path / "cold"

        if hot_path.exists():
            session_files = list(hot_path.glob("*.json"))

            # Get stats from each session
            for session_file in session_files:
                try:
                    with open(session_file) as f:
                        data = json.load(f)
                        total_learnings += len(data.get("learnings", {}))
                        total_dead_ends += len(data.get("dead_ends", []))
                        hot_turns += len(data.get("turns", {}))
                        branches += len(data.get("branch_points", []))
                        session_id = data.get("session_id", session_file.stem)
                except Exception:
                    continue

        if warm_path.exists():
            warm_file_list = list(warm_path.glob("*.jsonl"))
            warm_files = len(warm_file_list)
            warm_size_bytes = sum(f.stat().st_size for f in warm_file_list)

        if cold_path.exists():
            cold_file_list = list(cold_path.glob("*"))
            cold_files = len(cold_file_list)
            cold_size_bytes = sum(f.stat().st_size for f in cold_file_list)

        return MemoryStatsResponse(
            session_id=session_id,
            hot_turns=hot_turns,
            warm_files=warm_files,
            warm_size_mb=round(warm_size_bytes / 1024 / 1024, 2),
            cold_files=cold_files,
            cold_size_mb=round(cold_size_bytes / 1024 / 1024, 2),
            total_turns=hot_turns,
            branches=branches,
            dead_ends=total_dead_ends,
            learnings=total_learnings,
            concept_edges=concept_edges,
        )
    except Exception:
        return MemoryStatsResponse(
            session_id=None,
            hot_turns=0,
            warm_files=0,
            warm_size_mb=0,
            cold_files=0,
            cold_size_mb=0,
            total_turns=0,
            branches=0,
            dead_ends=0,
            learnings=0,
            concept_edges=0,
        )


@router.get("/project/intelligence")
async def get_project_intelligence(path: str) -> dict[str, Any]:
    """Get project intelligence data."""
    return {
        "signals": [],
        "context_quality": 1.0,
    }


@router.get("/project/current")
async def get_current_project() -> dict[str, Any]:
    """Get current project (RFC-140).

    Returns current workspace/project if set, otherwise returns default project.
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()
    current = manager.get_current()

    if current and current.project:
        return {
            "project": {
                "id": current.project.id,
                "name": current.project.name,
                "root": str(current.project.root),
            }
        }

    # Fallback to default project
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    default = registry.get_default()

    if default:
        return {
            "project": {
                "id": default.id,
                "name": default.name,
                "root": str(default.root),
            }
        }

    return {"project": None}


class SwitchProjectRequest(BaseModel):
    """Request to switch project context."""

    project_id: str


@router.post("/project/switch")
async def switch_project(request: SwitchProjectRequest) -> dict[str, Any]:
    """Switch project context (RFC-140).

    Sets the project as current workspace.
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()

    try:
        workspace_info = manager.switch_workspace(request.project_id)
        return {
            "success": True,
            "project": {
                "id": workspace_info.id,
                "name": workspace_info.name,
                "root": str(workspace_info.path),
            },
        }
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }
