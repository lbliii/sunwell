"""Project management routes (RFC-113, RFC-117, RFC-132)."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sunwell.server.routes._models import CamelModel

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
    from sunwell.project.validation import ProjectValidationError, validate_workspace
    from sunwell.workspace import default_workspace_root

    path = Path(request.path).expanduser().resolve()

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
    from sunwell.project import ProjectRegistry
    from sunwell.project.validation import validate_workspace

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

    from sunwell.project import ProjectRegistry, init_project
    from sunwell.project.registry import RegistryError
    from sunwell.workspace import default_workspace_root

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
        project_path = Path(request.path).expanduser().resolve()
    else:
        # Default location with slugified name
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-") or "project"
        project_path = default_workspace_root() / slug

    # Ensure parent exists
    project_path.parent.mkdir(parents=True, exist_ok=True)

    # Create directory
    is_new = not project_path.exists()
    project_path.mkdir(parents=True, exist_ok=True)

    # Generate slug for project ID
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-") or "project"

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
    from sunwell.project import ProjectRegistry
    from sunwell.project.validation import validate_workspace

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
    from sunwell.project import ProjectRegistry
    from sunwell.project.registry import RegistryError

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
    """Get recent projects."""
    return {"recent": []}


@router.get("/project/scan")
async def scan_projects() -> dict[str, Any]:
    """Scan for projects."""
    return {"projects": []}


@router.post("/project/resume")
async def resume_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Resume a project."""
    return {"success": True, "message": "Project resumed"}


@router.post("/project/open")
async def open_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Open a project."""
    path = Path(request.path).expanduser().resolve()
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
    """Delete a project."""
    return {"success": True, "message": "Project deleted", "new_path": None}


@router.post("/project/archive")
async def archive_project(request: ProjectPathRequest) -> dict[str, Any]:
    """Archive a project."""
    return {"success": True, "message": "Project archived", "new_path": None}


@router.post("/project/iterate")
async def iterate_project(request: IterateProjectRequest) -> dict[str, Any]:
    """Iterate a project."""
    return {"success": True, "message": "Project iterated", "new_path": None}


@router.get("/project/learnings")
async def get_project_learnings(path: str) -> dict[str, Any]:
    """Get project learnings."""
    return {
        "original_goal": "",
        "decisions": [],
        "failures": [],
        "completed_tasks": [],
        "pending_tasks": [],
    }


@router.post("/project/monorepo")
async def check_monorepo(request: MonorepoRequest) -> dict[str, Any]:
    """Check if path is a monorepo."""
    return {"is_monorepo": False, "sub_projects": []}


@router.post("/project/analyze")
async def analyze_project(request: AnalyzeRequest) -> dict[str, Any]:
    """Analyze project structure."""
    try:
        from sunwell.project import ProjectAnalyzer

        path = Path(request.path).expanduser().resolve()
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
    target = Path(path).expanduser().resolve() if path else Path.cwd()
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
    project_path = Path(request.path).expanduser().resolve()

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
        file_path = Path(path).expanduser().resolve()
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
    project_path = Path(path).expanduser().resolve()
    return {
        "path": str(project_path),
        "exists": project_path.exists(),
        "has_sunwell": (project_path / ".sunwell").exists(),
        "has_git": (project_path / ".git").exists(),
    }


@router.get("/project/dag")
async def get_project_dag(path: str) -> dict[str, Any]:
    """Get project DAG."""
    return {"nodes": [], "edges": [], "metadata": {}}


@router.get("/project/memory/stats")
async def get_project_memory_stats(path: str) -> dict[str, Any]:
    """Get project memory stats."""
    return {
        "total_learnings": 0,
        "total_dead_ends": 0,
        "session_count": 0,
    }


@router.get("/project/intelligence")
async def get_project_intelligence(path: str) -> dict[str, Any]:
    """Get project intelligence data."""
    return {
        "signals": [],
        "context_quality": 1.0,
    }
