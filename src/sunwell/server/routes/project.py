"""Project management routes (RFC-113, RFC-117)."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sunwell.server.routes._models import CamelModel

router = APIRouter(prefix="/api", tags=["project"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class ProjectPathRequest(BaseModel):
    path: str


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
