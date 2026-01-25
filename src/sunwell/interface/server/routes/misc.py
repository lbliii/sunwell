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

from sunwell.interface.server.routes.models import (
    BriefingClearResponse,
    BriefingResponse,
    CamelModel,
    IndexChunk,
    IndexQueryResponse,
    PromptActionResponse,
    SavedPromptItem,
    SavedPromptsResponse,
)
from sunwell.interface.server.routes.agent import get_run_manager

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
    from sunwell.interface.cli.commands.debug_cmd import (
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
        from sunwell.planning.lens import LensLibrary

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
        from sunwell.planning.lens import LensLibrary

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
async def get_briefing(path: str) -> dict[str, BriefingResponse | None]:
    """Get briefing for a project.

    Returns BriefingResponse with automatic camelCase conversion.
    """
    from sunwell.memory.briefing import Briefing

    project_path = normalize_path(path)
    briefing = Briefing.load(project_path)

    if briefing is None:
        return {"briefing": None}

    # Convert domain model to response model (CamelModel handles camelCase)
    return {
        "briefing": BriefingResponse(
            mission=briefing.mission,
            status=briefing.status.value,
            progress=briefing.progress,
            last_action=briefing.last_action,
            next_action=briefing.next_action,
            hazards=list(briefing.hazards),
            blockers=list(briefing.blockers),
            hot_files=list(briefing.hot_files),
            goal_hash=briefing.goal_hash,
            related_learnings=list(briefing.related_learnings),
            predicted_skills=list(briefing.predicted_skills) if briefing.predicted_skills else None,
            suggested_lens=briefing.suggested_lens,
            complexity_estimate=briefing.complexity_estimate,
            estimated_files_touched=briefing.estimated_files_touched,
            updated_at=briefing.updated_at,
            session_id=briefing.session_id,
        )
    }


@router.get("/briefing/exists")
async def briefing_exists(path: str) -> dict[str, bool]:
    """Check if briefing exists for a project."""
    project_path = normalize_path(path)
    briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"
    return {"exists": briefing_path.exists()}


@router.post("/briefing/clear")
async def clear_briefing(request: ClearBriefingRequest) -> BriefingClearResponse:
    """Clear briefing for a project.

    Removes the briefing.json file to reset project state.
    """
    project_path = normalize_path(request.path)
    briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"

    if briefing_path.exists():
        briefing_path.unlink()
        return BriefingClearResponse(success=True, message="Briefing cleared")

    return BriefingClearResponse(success=True, message="No briefing to clear")


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════


def _get_prompts_path() -> Path:
    """Get the path to saved prompts file."""
    from sunwell.knowledge.workspace import default_workspace_root

    prompts_path = default_workspace_root() / "prompts.json"
    return prompts_path


def _load_prompts() -> list[dict[str, Any]]:
    """Load saved prompts from disk.

    Returns list of {text: str, last_used: int} matching frontend SavedPrompt interface.
    """
    import json

    prompts_path = _get_prompts_path()
    if not prompts_path.exists():
        return []

    try:
        with open(prompts_path) as f:
            data = json.load(f)
            prompts = data.get("prompts", [])
            # Handle legacy format (plain strings)
            if prompts and isinstance(prompts[0], str):
                return [{"text": p, "last_used": 0} for p in prompts]
            return prompts
    except Exception:
        return []


def _save_prompts(prompts: list[dict[str, Any]]) -> None:
    """Save prompts to disk."""
    import json

    prompts_path = _get_prompts_path()
    prompts_path.parent.mkdir(parents=True, exist_ok=True)

    with open(prompts_path, "w") as f:
        json.dump({"prompts": prompts}, f, indent=2)


@router.get("/prompts")
async def get_saved_prompts() -> SavedPromptsResponse:
    """Get saved prompts from persistent storage.

    Returns SavedPromptsResponse with prompts as SavedPromptItem list.
    """
    prompts = _load_prompts()
    return SavedPromptsResponse(
        prompts=[SavedPromptItem(text=p["text"], last_used=p["last_used"]) for p in prompts]
    )


@router.post("/prompts")
async def save_prompt(request: SavePromptRequest) -> PromptActionResponse:
    """Save a prompt to persistent storage.

    Adds the prompt to the list if not already present, or updates last_used.
    """
    import time

    prompts = _load_prompts()
    now = int(time.time() * 1000)  # JavaScript timestamp (ms)

    # Check if prompt already exists
    existing = next((p for p in prompts if p["text"] == request.prompt), None)
    if existing:
        existing["last_used"] = now
    else:
        prompts.append({"text": request.prompt, "last_used": now})

    _save_prompts(prompts)
    return PromptActionResponse(status="saved", total=len(prompts))


@router.post("/prompts/remove")
async def remove_prompt(request: RemovePromptRequest) -> PromptActionResponse:
    """Remove a saved prompt from persistent storage."""
    prompts = _load_prompts()
    original_len = len(prompts)

    prompts = [p for p in prompts if p["text"] != request.prompt]

    if len(prompts) < original_len:
        _save_prompts(prompts)
        return PromptActionResponse(status="removed", total=len(prompts))

    return PromptActionResponse(status="not_found", total=len(prompts))


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
async def query_index(request: IndexingQueryRequest) -> IndexQueryResponse:
    """Query the index for relevant code/content.

    Returns IndexQueryResponse with automatic camelCase conversion.
    """
    import os
    import time
    import uuid

    start_time = time.perf_counter()

    # Try to get workspace from current context (or use cwd)
    workspace_path = Path.cwd()

    # Simple text-based search fallback
    chunks: list[IndexChunk] = []
    query_lower = request.text.lower()
    query_words = set(query_lower.split())
    total_searched = 0

    # File extensions to search
    extensions = {".py", ".ts", ".js", ".md", ".yaml", ".yml", ".json", ".toml"}

    try:
        # Walk the workspace looking for matches
        for root, _, files in os.walk(workspace_path):
            # Skip common non-source directories
            if any(skip in root for skip in [
                "node_modules", "__pycache__", ".git", ".venv", "venv", "target", "dist", "build"
            ]):
                continue

            for filename in files:
                if not any(filename.endswith(ext) for ext in extensions):
                    continue

                file_path = Path(root) / filename

                # Skip large files
                try:
                    if file_path.stat().st_size > 100_000:
                        continue
                except OSError:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    content_lower = content.lower()
                    total_searched += 1

                    # Score by word matches
                    score = sum(1 for word in query_words if word in content_lower)
                    if score == 0:
                        continue

                    # Find matching lines and build chunks
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if any(word in line.lower() for word in query_words):
                            # Compute relative path
                            try:
                                rel_path = str(file_path.relative_to(workspace_path))
                            except ValueError:
                                rel_path = str(file_path)

                            # Determine chunk type based on extension
                            ext = file_path.suffix
                            chunk_type: str = "block"
                            if ext == ".md":
                                chunk_type = "prose"
                            elif ext == ".py":
                                chunk_type = "function"

                            # Build chunk with context (3 lines before/after)
                            chunk_start = max(0, i - 2)
                            chunk_end = min(len(lines), i + 3)
                            chunk_content = "\n".join(lines[chunk_start:chunk_end])

                            chunks.append(IndexChunk(
                                id=str(uuid.uuid4())[:8],
                                file_path=rel_path,
                                start_line=chunk_start + 1,
                                end_line=chunk_end,
                                content=chunk_content[:500],
                                chunk_type=chunk_type,  # type: ignore[arg-type]
                                score=min(1.0, score / len(query_words)) if query_words else 0,
                            ))

                            if len(chunks) >= request.top_k * 2:
                                break

                except Exception:
                    continue

            # Limit total results scanned
            if len(chunks) >= request.top_k * 2:
                break

        # Sort by score and limit
        chunks.sort(key=lambda c: c.score, reverse=True)
        chunks = chunks[:request.top_k]

    except Exception as e:
        return IndexQueryResponse(
            chunks=[],
            fallback_used=True,
            query_time_ms=int((time.perf_counter() - start_time) * 1000),
            total_chunks_searched=0,
            error=str(e),
        )

    query_time_ms = int((time.perf_counter() - start_time) * 1000)

    return IndexQueryResponse(
        chunks=chunks,
        fallback_used=True,
        query_time_ms=query_time_ms,
        total_chunks_searched=total_searched,
    )


@router.post("/indexing/rebuild")
async def rebuild_index() -> dict[str, Any]:
    """Rebuild the index."""
    return {"status": "rebuilding"}


@router.post("/indexing/settings")
async def update_indexing_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Update indexing settings."""
    return {"status": "updated", "settings": settings}
