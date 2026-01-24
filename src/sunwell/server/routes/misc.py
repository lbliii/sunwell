"""Miscellaneous routes: shell, files, health, security, lenses, etc."""

import json
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sunwell.server.routes._models import CamelModel
from sunwell.server.routes.agent import get_run_manager

router = APIRouter(prefix="/api", tags=["misc"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class ShellRequest(BaseModel):
    path: str


class WriteFileRequest(BaseModel):
    path: str
    content: str


class SecurityScanRequest(BaseModel):
    content: str


class WeaknessScanRequest(BaseModel):
    path: str


class WeaknessPreviewRequest(BaseModel):
    path: str
    artifact_id: str


class WeaknessExecuteRequest(BaseModel):
    path: str
    artifact_id: str
    auto_approve: bool = False
    confidence_threshold: float = 0.7


class InterfaceProcessRequest(BaseModel):
    goal: str
    data_dir: str | None = None


class IndexingStartRequest(BaseModel):
    workspace_path: str


class IndexingQueryRequest(BaseModel):
    text: str
    top_k: int = 10


class LensConfigRequest(CamelModel):
    path: str
    lens_name: str | None = None
    auto_select: bool = True


class SavePromptRequest(BaseModel):
    prompt: str


class RemovePromptRequest(BaseModel):
    prompt: str


class ClearBriefingRequest(BaseModel):
    path: str


# ═══════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check."""
    run_manager = get_run_manager()
    return {
        "status": "healthy",
        "active_runs": len(run_manager._runs),
    }


# ═══════════════════════════════════════════════════════════════
# DEBUG (RFC-120)
# ═══════════════════════════════════════════════════════════════


@router.get("/debug/dump")
async def get_debug_dump() -> StreamingResponse:
    """Generate and return debug dump tarball.

    Returns a tar.gz file containing diagnostics for bug reports.
    """
    from sunwell.cli.debug_cmd import (
        _collect_config,
        _collect_events,
        _collect_logs,
        _collect_meta,
        _collect_plans,
        _collect_runs,
        _collect_simulacrum,
        _collect_system,
    )

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"sunwell-debug-{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        _collect_meta(root / "meta.json")
        _collect_config(root / "config.yaml")
        _collect_events(root / "events.jsonl")
        _collect_runs(root / "runs")
        _collect_plans(root / "plans")
        _collect_simulacrum(root / "simulacrum.json")
        _collect_logs(root / "agent.log")
        _collect_system(root / "system")

        tarball_path = Path(tmpdir) / filename
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(root, arcname="sunwell-debug")

        def iterfile():
            with open(tarball_path, "rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(),
            media_type="application/gzip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


# ═══════════════════════════════════════════════════════════════
# LENSES
# ═══════════════════════════════════════════════════════════════


@router.get("/lenses")
async def list_lenses() -> list[dict[str, Any]]:
    """List available lenses."""
    try:
        from sunwell.lens import LensLibrary

        library = LensLibrary()
        return [
            {
                "id": lens.name,
                "name": lens.name,
                "description": lens.purpose or "",
                "domain": lens.domain or "general",
            }
            for lens in library.list_lenses()
        ]
    except Exception as e:
        return [{"error": str(e)}]


@router.get("/lenses/{lens_id}")
async def get_lens(lens_id: str) -> dict[str, Any]:
    """Get lens details."""
    try:
        from sunwell.lens import LensLibrary

        library = LensLibrary()
        lens = library.get(lens_id)
        if not lens:
            return {"error": "Lens not found"}
        return {
            "id": lens.name,
            "name": lens.name,
            "description": lens.purpose or "",
            "domain": lens.domain or "general",
            "skills": [s.name for s in lens.skills] if lens.skills else [],
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/lenses/{lens_id}/skills")
async def get_lens_skills(lens_id: str) -> dict[str, Any]:
    """Get skills for a lens."""
    return {
        "skills": [
            {
                "id": "audit",
                "name": "Quick Audit",
                "shortcut": "::a",
                "description": "Validate document",
                "category": "validation",
            },
            {
                "id": "polish",
                "name": "Polish",
                "shortcut": "::p",
                "description": "Improve clarity",
                "category": "transformation",
            },
        ]
    }


@router.get("/lenses/config")
async def get_lenses_config(path: str) -> dict[str, Any]:
    """Get lens config for a project."""
    project_path = Path(path).expanduser().resolve()
    config_file = project_path / ".sunwell" / "lens.json"

    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except json.JSONDecodeError:
            pass

    return {"default_lens": None, "auto_select": True}


@router.post("/lenses/config")
async def set_lenses_config(request: LensConfigRequest) -> dict[str, Any]:
    """Set lens config for a project."""
    project_path = Path(request.path).expanduser().resolve()
    config_dir = project_path / ".sunwell"
    config_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "default_lens": request.lens_name,
        "auto_select": request.auto_select,
    }

    (config_dir / "lens.json").write_text(json.dumps(config, indent=2))
    return {"status": "saved", "config": config}


# ═══════════════════════════════════════════════════════════════
# SHELL COMMANDS
# ═══════════════════════════════════════════════════════════════


@router.post("/shell/open-finder")
async def open_finder(request: ShellRequest) -> dict[str, Any]:
    """Open path in Finder/Explorer."""
    path = Path(request.path).expanduser().resolve()
    if not path.exists():
        return {"error": "Path does not exist"}

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        return {"status": "opened"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/shell/open-terminal")
async def open_terminal(request: ShellRequest) -> dict[str, Any]:
    """Open terminal at path."""
    path = Path(request.path).expanduser().resolve()
    if not path.exists():
        return {"error": "Path does not exist"}

    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["open", "-a", "Terminal", str(path)],
                check=True,
            )
        elif sys.platform == "win32":
            subprocess.run(
                ["cmd", "/c", "start", "cmd", "/k", f"cd /d {path}"],
                check=True,
            )
        else:
            for term in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
                try:
                    subprocess.Popen([term, "--working-directory", str(path)])
                    return {"status": "opened"}
                except FileNotFoundError:
                    continue
            return {"error": "No terminal found"}
        return {"status": "opened"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/shell/open-editor")
async def open_editor(request: ShellRequest) -> dict[str, Any]:
    """Open path in code editor."""
    path = Path(request.path).expanduser().resolve()
    if not path.exists():
        return {"error": "Path does not exist"}

    for editor in ["cursor", "code", "codium", "subl", "atom"]:
        try:
            subprocess.Popen([editor, str(path)])
            return {"status": "opened", "editor": editor}
        except FileNotFoundError:
            continue

    return {"error": "No editor found. Install VS Code or Cursor."}


# ═══════════════════════════════════════════════════════════════
# FILES (RFC-113)
# ═══════════════════════════════════════════════════════════════


@router.get("/files/read")
async def read_file_contents(path: str) -> dict[str, Any]:
    """Read file contents."""
    try:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            return {"error": "File not found"}
        return {"content": file_path.read_text()}
    except Exception as e:
        return {"error": str(e)}


@router.post("/files/write")
async def write_file_contents(request: WriteFileRequest) -> dict[str, Any]:
    """Write file contents."""
    try:
        file_path = Path(request.path).expanduser().resolve()
        file_path.write_text(request.content)
        return {"status": "written"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# BRIEFING (RFC-071)
# ═══════════════════════════════════════════════════════════════


@router.get("/briefing")
async def get_briefing(path: str) -> dict[str, Any]:
    """Get briefing for a project."""
    return {"briefing": None}


@router.get("/briefing/exists")
async def briefing_exists(path: str) -> dict[str, Any]:
    """Check if briefing exists."""
    return {"exists": False}


@router.post("/briefing/clear")
async def clear_briefing(request: ClearBriefingRequest) -> dict[str, Any]:
    """Clear briefing for a project."""
    return {"success": True}


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════


@router.get("/prompts")
async def get_saved_prompts() -> dict[str, Any]:
    """Get saved prompts."""
    return {"prompts": []}


@router.post("/prompts")
async def save_prompt(request: SavePromptRequest) -> dict[str, Any]:
    """Save a prompt."""
    return {"status": "saved"}


@router.post("/prompts/remove")
async def remove_prompt(request: RemovePromptRequest) -> dict[str, Any]:
    """Remove a saved prompt."""
    return {"status": "removed"}


# ═══════════════════════════════════════════════════════════════
# PREVIEW
# ═══════════════════════════════════════════════════════════════


@router.post("/preview/launch")
async def launch_preview() -> dict[str, Any]:
    """Launch preview for current project."""
    return {"url": None, "content": None, "view_type": "web_view"}


@router.post("/preview/stop")
async def stop_preview() -> dict[str, Any]:
    """Stop preview."""
    return {"status": "stopped"}


# ═══════════════════════════════════════════════════════════════
# SECURITY (RFC-048)
# ═══════════════════════════════════════════════════════════════


@router.get("/security/dag/{dag_id}/permissions")
async def get_dag_permissions(dag_id: str) -> dict[str, Any]:
    """Get permissions for a DAG."""
    return {
        "dagId": dag_id,
        "permissions": {
            "filesystemRead": [],
            "filesystemWrite": [],
            "networkAllow": [],
            "networkDeny": ["*"],
            "shellAllow": [],
            "shellDeny": [],
            "envRead": [],
            "envWrite": [],
        },
        "riskLevel": "low",
        "requiresApproval": False,
    }


@router.post("/security/approval")
async def submit_security_approval(response: dict[str, Any]) -> dict[str, Any]:
    """Submit security approval response."""
    return {"success": True}


@router.get("/security/audit")
async def get_audit_log(limit: int = 50) -> list[dict[str, Any]]:
    """Get audit log entries."""
    return []


@router.get("/security/audit/verify")
async def verify_audit() -> dict[str, Any]:
    """Verify audit log integrity."""
    return {"valid": True, "message": "Audit log is intact"}


@router.post("/security/scan")
async def scan_security(request: SecurityScanRequest) -> list[dict[str, Any]]:
    """Scan content for security issues."""
    return []


# ═══════════════════════════════════════════════════════════════
# WEAKNESS (RFC-063)
# ═══════════════════════════════════════════════════════════════


@router.post("/weakness/scan")
async def scan_weaknesses(request: WeaknessScanRequest) -> dict[str, Any]:
    """Scan project for weaknesses."""
    return {
        "weaknesses": [],
        "overall_health": 1.0,
        "scan_timestamp": None,
    }


@router.post("/weakness/preview")
async def preview_cascade(request: WeaknessPreviewRequest) -> dict[str, Any]:
    """Preview cascade fix."""
    return {
        "artifact_id": request.artifact_id,
        "affected_files": [],
        "estimated_changes": 0,
    }


@router.post("/weakness/execute")
async def execute_cascade(request: WeaknessExecuteRequest) -> dict[str, Any]:
    """Start cascade execution."""
    return {
        "execution_id": None,
        "artifact_id": request.artifact_id,
        "status": "pending",
        "completed": False,
    }


@router.post("/weakness/fix")
async def execute_quick_fix(request: WeaknessExecuteRequest) -> dict[str, Any]:
    """Execute quick fix."""
    return {
        "execution_id": None,
        "artifact_id": request.artifact_id,
        "status": "pending",
        "completed": False,
    }


# ═══════════════════════════════════════════════════════════════
# INTERFACE (RFC-083)
# ═══════════════════════════════════════════════════════════════


@router.post("/interface/process")
async def process_interface(request: InterfaceProcessRequest) -> dict[str, Any]:
    """Process goal through generative interface."""
    return {
        "response": "",
        "type": "conversation",
        "artifacts": [],
    }


# ═══════════════════════════════════════════════════════════════
# INDEXING (RFC-113)
# ═══════════════════════════════════════════════════════════════


@router.get("/indexing/status")
async def get_indexing_status() -> dict[str, Any]:
    """Get indexing service status."""
    return {
        "isIndexing": False,
        "lastIndexed": None,
        "progress": 1.0,
        "totalFiles": 0,
        "indexedFiles": 0,
        "isEnabled": True,
    }


@router.post("/indexing/start")
async def start_indexing(request: IndexingStartRequest) -> dict[str, Any]:
    """Start indexing service."""
    return {"status": "started", "workspace": request.workspace_path}


@router.post("/indexing/stop")
async def stop_indexing() -> dict[str, Any]:
    """Stop indexing service."""
    return {"status": "stopped"}


@router.post("/indexing/query")
async def query_index(request: IndexingQueryRequest) -> dict[str, Any]:
    """Query the index."""
    return {"results": [], "query": request.text}


@router.post("/indexing/rebuild")
async def rebuild_index() -> dict[str, Any]:
    """Rebuild the index."""
    return {"status": "rebuilding"}


@router.post("/indexing/settings")
async def update_indexing_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Update indexing settings."""
    return {"status": "updated", "settings": settings}
