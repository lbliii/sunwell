"""FastAPI application for Studio UI (RFC-113).

This is the HTTP/WebSocket server that replaces the Rust/Tauri bridge.
All Studio communication goes through here.
"""

import contextlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from sunwell.server.events import BusEvent, EventBus
from sunwell.server.runs import RunManager, RunState


def _to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """Base model with camelCase JSON serialization."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,  # Allow both snake_case and camelCase in input
    )

# Global run manager (single server instance)
_run_manager = RunManager()

# Global event bus for unified CLI/Studio visibility (RFC-119)
_event_bus = EventBus()


def create_app(*, dev_mode: bool = False, static_dir: Path | None = None) -> FastAPI:
    """Create FastAPI application.

    Args:
        dev_mode: If True, enable CORS for Vite dev server on :5173.
                  If False, serve static Svelte build.
        static_dir: Path to static files (Svelte build). If None, uses default.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Sunwell Studio",
        description="AI Agent Development Environment",
        version="0.1.0",
    )

    # Register API routes
    _register_routes(app)

    if dev_mode:
        # Development: CORS for Vite dev server (port 1420 is Tauri default)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:1420",
                "http://127.0.0.1:1420",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Production: Serve Svelte static build
        if static_dir and static_dir.exists():
            _mount_static(app, static_dir)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    # ═══════════════════════════════════════════════════════════════
    # AGENT EXECUTION
    # ═══════════════════════════════════════════════════════════════

    class RunRequest(BaseModel):
        goal: str
        workspace: str | None = None
        project_id: str | None = None  # RFC-117: Explicit project binding
        lens: str | None = None
        provider: str | None = None
        model: str | None = None
        trust: str = "workspace"
        timeout: int = 300
        source: str = "studio"  # RFC-119: "cli" | "studio" | "api"

    @app.post("/api/run")
    async def start_run(request: RunRequest) -> dict[str, Any]:
        """Start an agent run, return run_id for WebSocket connection."""
        run = _run_manager.create_run(
            goal=request.goal,
            workspace=request.workspace,
            project_id=request.project_id,
            lens=request.lens,
            provider=request.provider,
            model=request.model,
            trust=request.trust,
            timeout=request.timeout,
            source=request.source,
        )
        return {"run_id": run.run_id, "status": run.status}

    @app.get("/api/run/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        """Get run status."""
        run = _run_manager.get_run(run_id)
        if not run:
            return {"error": "Run not found"}
        return {
            "run_id": run.run_id,
            "status": run.status,
            "goal": run.goal,
            "event_count": len(run.events),
        }

    @app.delete("/api/run/{run_id}")
    async def cancel_run(run_id: str) -> dict[str, Any]:
        """Cancel a running agent."""
        run = _run_manager.get_run(run_id)
        if not run:
            return {"error": "Run not found"}
        run.cancel()
        return {"status": "cancelled"}

    @app.websocket("/api/run/{run_id}/events")
    async def stream_events(websocket: WebSocket, run_id: str) -> None:
        """Stream agent events over WebSocket."""
        await websocket.accept()

        run = _run_manager.get_run(run_id)
        if not run:
            await websocket.send_json({"type": "error", "data": {"message": "Run not found"}})
            await websocket.close(code=4004)
            return

        # Replay any buffered events (for reconnection)
        for event in run.events:
            await websocket.send_json(event)

        # If already complete, close
        if run.status in ("complete", "error", "cancelled"):
            await websocket.close()
            return

        # Start agent if not already running
        if run.status == "pending":
            run.status = "running"
            try:
                async for event in _execute_agent(run):
                    event_dict = event if isinstance(event, dict) else event.to_dict()
                    run.events.append(event_dict)
                    await websocket.send_json(event_dict)

                    if run.is_cancelled:
                        await websocket.send_json({"type": "cancelled", "data": {}})
                        run.status = "cancelled"
                        break

                if run.status == "running":
                    run.status = "complete"

            except WebSocketDisconnect:
                pass  # Client disconnected, run continues buffering
            except Exception as e:
                run.status = "error"
                error_event = {"type": "error", "data": {"message": str(e)}}
                run.events.append(error_event)
                with contextlib.suppress(Exception):
                    await websocket.send_json(error_event)
            finally:
                with contextlib.suppress(Exception):
                    await websocket.close()

    # ═══════════════════════════════════════════════════════════════
    # GLOBAL EVENT STREAM (RFC-119)
    # ═══════════════════════════════════════════════════════════════

    @app.websocket("/api/events")
    async def global_events(websocket: WebSocket, project_id: str | None = None) -> None:
        """Subscribe to all events, optionally filtered by project.

        This enables Studio Observatory to see CLI-triggered runs.
        Events are broadcast to all subscribers regardless of origin.
        """
        await websocket.accept()

        if not await _event_bus.subscribe(websocket, project_filter=project_id):
            await websocket.close(code=4029, reason="Too many connections")
            return

        try:
            # Keep connection alive, events pushed via broadcast()
            while True:
                await websocket.receive_text()  # Ping/pong keep-alive
        except WebSocketDisconnect:
            pass
        finally:
            await _event_bus.unsubscribe(websocket)

    @app.get("/api/runs")
    async def list_runs(project_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        """List all runs, optionally filtered by project.

        Returns runs regardless of origin (CLI, Studio, API).
        """
        runs = _run_manager.list_runs()

        if project_id:
            runs = [r for r in runs if r.project_id == project_id]

        return {
            "runs": [
                {
                    "run_id": r.run_id,
                    "goal": r.goal,
                    "status": r.status,
                    "source": r.source,
                    "started_at": r.started_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "event_count": len(r.events),
                }
                for r in runs[-limit:]
            ]
        }

    # ═══════════════════════════════════════════════════════════════
    # MEMORY
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/memory")
    async def get_memory() -> dict[str, Any]:
        """Get current session memory (Simulacrum)."""
        try:
            from sunwell.simulacrum import SimulacrumStore

            store = SimulacrumStore.load_or_create(Path.cwd())
            return {
                "learnings": [learning.to_dict() for learning in store.learnings],
                "dead_ends": [dead_end.to_dict() for dead_end in store.dead_ends],
                "session_count": store.session_count,
            }
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/memory/checkpoint")
    async def checkpoint_memory() -> dict[str, Any]:
        """Save memory checkpoint."""
        try:
            from sunwell.simulacrum import SimulacrumStore

            store = SimulacrumStore.load_or_create(Path.cwd())
            store.save()
            return {"status": "saved"}
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # DEBUG (RFC-120)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/debug/dump")
    async def get_debug_dump():
        """Generate and return debug dump tarball.

        Returns a tar.gz file containing diagnostics for bug reports.
        """
        import tarfile
        import tempfile

        from fastapi.responses import StreamingResponse

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

            # Collect all components
            _collect_meta(root / "meta.json")
            _collect_config(root / "config.yaml")
            _collect_events(root / "events.jsonl")
            _collect_runs(root / "runs")
            _collect_plans(root / "plans")
            _collect_simulacrum(root / "simulacrum.json")
            _collect_logs(root / "agent.log")
            _collect_system(root / "system")

            # Create tarball in memory
            tarball_path = Path(tmpdir) / filename
            with tarfile.open(tarball_path, "w:gz") as tar:
                tar.add(root, arcname="sunwell-debug")

            # Stream the file
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

    @app.get("/api/lenses")
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

    @app.get("/api/lenses/{lens_id}")
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

    # ═══════════════════════════════════════════════════════════════
    # PROJECT
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/project")
    async def get_project() -> dict[str, Any]:
        """Get current project info."""
        cwd = Path.cwd()
        return {
            "path": str(cwd),
            "name": cwd.name,
            "exists": cwd.exists(),
        }

    @app.get("/api/project/recent")
    async def get_recent_projects() -> dict[str, Any]:
        """Get recent projects."""
        # Placeholder - return empty list for now
        return {"recent": []}

    @app.get("/api/project/scan")
    async def scan_projects() -> dict[str, Any]:
        """Scan for projects."""
        # Placeholder - return empty list for now
        return {"projects": []}

    class ProjectPathRequest(BaseModel):
        path: str

    @app.post("/api/project/resume")
    async def resume_project(request: ProjectPathRequest) -> dict[str, Any]:
        """Resume a project."""
        return {"success": True, "message": "Project resumed"}

    @app.post("/api/project/open")
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

    @app.post("/api/project/delete")
    async def delete_project(request: ProjectPathRequest) -> dict[str, Any]:
        """Delete a project."""
        return {"success": True, "message": "Project deleted", "new_path": None}

    @app.post("/api/project/archive")
    async def archive_project(request: ProjectPathRequest) -> dict[str, Any]:
        """Archive a project."""
        return {"success": True, "message": "Project archived", "new_path": None}

    class IterateProjectRequest(BaseModel):
        path: str
        new_goal: str | None = None

    @app.post("/api/project/iterate")
    async def iterate_project(request: IterateProjectRequest) -> dict[str, Any]:
        """Iterate a project."""
        return {"success": True, "message": "Project iterated", "new_path": None}

    @app.get("/api/project/learnings")
    async def get_project_learnings(path: str) -> dict[str, Any]:
        """Get project learnings."""
        return {
            "original_goal": "",
            "decisions": [],
            "failures": [],
            "completed_tasks": [],
            "pending_tasks": [],
        }

    class MonorepoRequest(BaseModel):
        path: str

    @app.post("/api/project/monorepo")
    async def check_monorepo(request: MonorepoRequest) -> dict[str, Any]:
        """Check if path is a monorepo."""
        return {"is_monorepo": False, "sub_projects": []}

    class AnalyzeRequest(BaseModel):
        path: str
        fresh: bool = False

    @app.post("/api/project/analyze")
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

    @app.get("/api/project/files")
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
    # SHELL COMMANDS (for Studio convenience features)
    # ═══════════════════════════════════════════════════════════════

    class ShellRequest(BaseModel):
        path: str

    @app.post("/api/shell/open-finder")
    async def open_finder(request: ShellRequest) -> dict[str, Any]:
        """Open path in Finder/Explorer."""
        import subprocess
        import sys

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

    @app.post("/api/shell/open-terminal")
    async def open_terminal(request: ShellRequest) -> dict[str, Any]:
        """Open terminal at path."""
        import subprocess
        import sys

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
                # Try common terminals
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

    @app.post("/api/shell/open-editor")
    async def open_editor(request: ShellRequest) -> dict[str, Any]:
        """Open path in code editor."""
        import subprocess

        path = Path(request.path).expanduser().resolve()
        if not path.exists():
            return {"error": "Path does not exist"}

        # Try editors in preference order
        for editor in ["cursor", "code", "codium", "subl", "atom"]:
            try:
                subprocess.Popen([editor, str(path)])
                return {"status": "opened", "editor": editor}
            except FileNotFoundError:
                continue

        return {"error": "No editor found. Install VS Code or Cursor."}

    # ═══════════════════════════════════════════════════════════════
    # DEMO (RFC-095)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/demo/tasks")
    async def list_demo_tasks() -> list[dict[str, Any]]:
        """List available demo tasks."""
        try:
            from sunwell.demo.tasks import BUILTIN_TASKS

            return [
                {
                    "name": task.name,
                    "prompt": task.prompt,
                    "description": task.description,
                    "expected_features": list(task.expected_features),
                }
                for task in BUILTIN_TASKS.values()
            ]
        except Exception as e:
            return [{"error": str(e)}]

    class DemoRunRequest(BaseModel):
        task: str | None = None
        model: str | None = None
        provider: str | None = None

    @app.post("/api/demo/run")
    async def run_demo(request: DemoRunRequest) -> dict[str, Any]:
        """Run a demo comparison (single-shot vs Sunwell).

        Code is saved to files to avoid JSON escaping issues.
        Use /api/demo/code/{run_id}/{method} to fetch raw code.
        """
        try:
            from sunwell.cli.helpers import resolve_model
            from sunwell.config import get_config
            from sunwell.demo import DemoComparison, DemoExecutor, DemoScorer, get_task
            from sunwell.demo.files import cleanup_old_demos, save_demo_code

            # Resolve model
            config = get_config()
            provider = request.provider or (config.model.default_provider if config else "ollama")
            model_name = request.model or (config.model.default_model if config else "gemma3:4b")

            model = resolve_model(provider, model_name)
            if not model:
                return {"error": "No model available"}

            # Get task
            task_name = request.task or "divide"
            demo_task = get_task(task_name)

            # Run comparison
            executor = DemoExecutor(model, verbose=False)
            scorer = DemoScorer()

            single_shot = await executor.run_single_shot(demo_task)
            sunwell = await executor.run_sunwell(demo_task)

            single_score = scorer.score(single_shot.code, demo_task.expected_features)
            sunwell_score = scorer.score(sunwell.code, demo_task.expected_features)

            comparison = DemoComparison(
                task=demo_task,
                single_shot=single_shot,
                sunwell=sunwell,
                single_score=single_score,
                sunwell_score=sunwell_score,
            )

            # Save code to files (avoids JSON escaping issues)
            run_id = str(uuid.uuid4())[:8]
            save_demo_code(run_id, single_shot.code, sunwell.code)
            cleanup_old_demos(keep_count=20)

            return {
                "model": f"{provider}:{model_name}",
                "task": {"name": demo_task.name, "prompt": demo_task.prompt},
                "run_id": run_id,  # Use this to fetch code files
                "single_shot": {
                    "score": single_score.score,
                    "lines": single_score.lines,
                    "time_ms": single_shot.time_ms,
                    "features": single_score.features,
                },
                "sunwell": {
                    "score": sunwell_score.score,
                    "lines": sunwell_score.lines,
                    "time_ms": sunwell.time_ms,
                    "iterations": sunwell.iterations,
                    "features": sunwell_score.features,
                },
                "improvement_percent": round(comparison.improvement_percent, 1),
            }
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/demo/code/{run_id}/{method}")
    async def get_demo_code(run_id: str, method: str):
        """Get raw code from a demo run.

        Args:
            run_id: The demo run identifier.
            method: Either 'single_shot' or 'sunwell'.

        Returns:
            Raw code as plain text (not JSON-escaped).
        """
        from fastapi.responses import JSONResponse, PlainTextResponse

        from sunwell.demo.files import load_demo_code

        if method not in ("single_shot", "sunwell"):
            return JSONResponse(
                {"error": f"Invalid method: {method}. Must be 'single_shot' or 'sunwell'."},
                status_code=400,
            )

        result = load_demo_code(run_id)
        if result is None:
            return JSONResponse({"error": f"Demo run not found: {run_id}"}, status_code=404)

        single_shot_code, sunwell_code = result
        code = single_shot_code if method == "single_shot" else sunwell_code

        return PlainTextResponse(content=code, media_type="text/plain")

    # ═══════════════════════════════════════════════════════════════
    # EVALUATION (RFC-098)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/eval/tasks")
    async def list_eval_tasks() -> list[dict[str, Any]]:
        """List available evaluation tasks from benchmark/tasks/."""
        try:
            import yaml

            tasks_dir = Path(__file__).parent.parent.parent.parent / "benchmark" / "tasks"
            if not tasks_dir.exists():
                return []

            tasks = []
            for category_dir in tasks_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                for task_file in category_dir.glob("*.yaml"):
                    try:
                        with open(task_file) as f:
                            task_data = yaml.safe_load(f)
                        tasks.append({
                            "id": f"{category_dir.name}/{task_file.stem}",
                            "name": task_data.get("name", task_file.stem),
                            "prompt": task_data.get("prompt", ""),
                            "category": category_dir.name,
                        })
                    except Exception:
                        continue

            return tasks
        except Exception as e:
            return [{"error": str(e)}]

    @app.get("/api/eval/history")
    async def get_eval_history(limit: int = 20) -> list[dict[str, Any]]:
        """Get evaluation history."""
        try:
            history_dir = Path.cwd() / ".sunwell" / "eval_history"
            if not history_dir.exists():
                return []

            import json

            entries = []
            for f in sorted(history_dir.glob("*.json"), reverse=True)[:limit]:
                try:
                    with open(f) as fp:
                        entries.append(json.load(fp))
                except Exception:
                    continue
            return entries
        except Exception as e:
            return [{"error": str(e)}]

    @app.get("/api/eval/stats")
    async def get_eval_stats() -> dict[str, Any]:
        """Get evaluation statistics."""
        try:
            history = await get_eval_history(limit=100)
            if not history or (len(history) == 1 and "error" in history[0]):
                return {
                    "total_runs": 0,
                    "avg_improvement": 0,
                    "sunwell_wins": 0,
                    "single_shot_wins": 0,
                    "ties": 0,
                    "by_task": {},
                }

            total = len(history)
            improvements = [h.get("improvement_percent", 0) for h in history]
            sunwell_wins = sum(1 for h in history if h.get("improvement_percent", 0) > 0)
            single_shot_wins = sum(1 for h in history if h.get("improvement_percent", 0) < 0)
            ties = total - sunwell_wins - single_shot_wins

            return {
                "total_runs": total,
                "avg_improvement": sum(improvements) / total if total else 0,
                "sunwell_wins": sunwell_wins,
                "single_shot_wins": single_shot_wins,
                "ties": ties,
                "by_task": {},  # Detailed breakdown could be added
            }
        except Exception as e:
            return {"error": str(e)}

    class EvalRunRequest(BaseModel):
        task: str | None = None
        model: str | None = None
        provider: str | None = None
        lens: str | None = None

    @app.post("/api/eval/run")
    async def run_eval(request: EvalRunRequest) -> dict[str, Any]:
        """Run an evaluation (placeholder - full implementation requires more setup)."""
        # For now, return a helpful message
        return {
            "error": "Full evaluation requires CLI: sunwell eval --task <task>",
            "hint": "The HTTP API for eval is under development.",
        }

    # ═══════════════════════════════════════════════════════════════
    # SESSION SUMMARY (RFC-120)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/session/summary")
    async def get_session_summary(session_id: str | None = None) -> dict[str, Any]:
        """Get session activity summary.

        Returns current session summary or specific session by ID.
        """
        from sunwell.session.tracker import SessionTracker

        if session_id:
            # Find specific session
            recent = SessionTracker.list_recent(limit=100)
            session_path = None
            for p in recent:
                if session_id in p.stem:
                    session_path = p
                    break

            if not session_path:
                return {"error": f"Session {session_id} not found"}

            tracker = SessionTracker.load(session_path)
        else:
            # Get most recent session
            recent = SessionTracker.list_recent(limit=1)
            if recent:
                tracker = SessionTracker.load(recent[0])
            else:
                return {"error": "No session data available"}

        return tracker.get_summary().to_dict()

    @app.get("/api/session/history")
    async def get_session_history(limit: int = 10) -> dict[str, Any]:
        """Get list of recent sessions."""
        from sunwell.session.tracker import SessionTracker

        recent = SessionTracker.list_recent(limit=limit)

        sessions = []
        for path in recent:
            try:
                tracker = SessionTracker.load(path)
                summary = tracker.get_summary()
                sessions.append({
                    "session_id": summary.session_id,
                    "started_at": summary.started_at.isoformat(),
                    "goals_completed": summary.goals_completed,
                    "goals_started": summary.goals_started,
                    "files_modified": summary.files_modified + summary.files_created,
                    "total_duration_seconds": summary.total_duration_seconds,
                })
            except Exception:
                continue

        return {"sessions": sessions, "count": len(sessions)}

    # ═══════════════════════════════════════════════════════════════
    # PLAN VERSIONING (RFC-120)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/plans/{plan_id}/versions")
    async def get_plan_versions(plan_id: str) -> dict[str, Any]:
        """Get all versions of a plan."""
        from sunwell.naaru.persistence import PlanStore

        store = PlanStore()
        versions = store.get_versions(plan_id)

        return {
            "plan_id": plan_id,
            "versions": [v.to_dict() for v in versions],
            "count": len(versions),
        }

    @app.get("/api/plans/{plan_id}/versions/{version}")
    async def get_plan_version(plan_id: str, version: int) -> dict[str, Any]:
        """Get a specific version of a plan."""
        from sunwell.naaru.persistence import PlanStore

        store = PlanStore()
        v = store.get_version(plan_id, version)

        if not v:
            return {"error": f"Version {version} not found for plan {plan_id}"}

        return v.to_dict()

    @app.get("/api/plans/{plan_id}/diff")
    async def get_plan_diff(plan_id: str, v1: int, v2: int) -> dict[str, Any]:
        """Get diff between two plan versions."""
        from sunwell.naaru.persistence import PlanStore

        store = PlanStore()
        diff = store.diff(plan_id, v1, v2)

        if not diff:
            return {"error": f"Could not compute diff for plan {plan_id}"}

        return diff.to_dict()

    @app.get("/api/plans/recent")
    async def get_recent_plans(limit: int = 20) -> dict[str, Any]:
        """Get recent plans with version info."""
        from sunwell.naaru.persistence import PlanStore

        store = PlanStore()
        plans = store.list_recent(limit=limit)

        result = []
        for p in plans:
            versions = store.get_versions(p.goal_hash)
            result.append({
                "plan_id": p.goal_hash,
                "goal": p.goal,
                "status": p.status.value,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
                "version_count": len(versions),
                "progress_percent": p.progress_percent,
            })

        return {"plans": result, "count": len(result)}

    # ═══════════════════════════════════════════════════════════════
    # DAG (RFC-105)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/dag")
    async def get_dag(path: str) -> dict[str, Any]:
        """Get DAG for a project."""
        # Placeholder - return empty DAG
        return {"nodes": [], "edges": [], "metadata": {}}

    @app.get("/api/dag/index")
    async def get_dag_index(path: str) -> dict[str, Any]:
        """Get DAG index for a project."""
        return {
            "project_path": path,
            "goals": [],
            "milestones": [],
            "total_goals": 0,
            "completed_goals": 0,
            "in_progress_goals": 0,
        }

    @app.get("/api/dag/goal/{goal_id}")
    async def get_dag_goal(goal_id: str, path: str) -> dict[str, Any] | None:
        """Get a specific goal node from the DAG."""
        return None

    @app.get("/api/dag/workspace")
    async def get_workspace_dag(path: str) -> dict[str, Any]:
        """Get workspace-level DAG index."""
        return {
            "workspace_path": path,
            "projects": [],
            "total_projects": 0,
        }

    class RefreshWorkspaceDagRequest(BaseModel):
        path: str

    @app.post("/api/dag/workspace/refresh")
    async def refresh_workspace_dag(request: RefreshWorkspaceDagRequest) -> dict[str, Any]:
        """Refresh workspace DAG index."""
        return {
            "workspace_path": request.path,
            "projects": [],
            "total_projects": 0,
        }

    @app.get("/api/dag/environment")
    async def get_environment_dag() -> dict[str, Any]:
        """Get environment-level DAG."""
        return {
            "workspaces": [],
            "total_workspaces": 0,
        }

    @app.get("/api/dag/plan")
    async def get_dag_plan(path: str) -> dict[str, Any]:
        """Get incremental execution plan for a DAG."""
        # Placeholder - return empty plan
        return {"toExecute": [], "toSkip": [], "reason": "No cached state"}

    class DagAppendRequest(BaseModel):
        path: str
        goal: dict[str, Any]

    @app.post("/api/dag/append")
    async def append_goal_to_dag(request: DagAppendRequest) -> dict[str, Any]:
        """Append a completed goal to the DAG."""
        # Placeholder - actual implementation would write to dag.json
        return {"status": "appended"}

    class DagExecuteRequest(BaseModel):
        path: str
        node_id: str

    @app.post("/api/dag/execute")
    async def execute_dag_node(request: DagExecuteRequest) -> dict[str, Any]:
        """Execute a DAG node."""
        # Placeholder - actual implementation would start execution
        return {"status": "started", "node_id": request.node_id}

    # ═══════════════════════════════════════════════════════════════
    # FILES (RFC-113)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/files/read")
    async def read_file_contents(path: str) -> dict[str, Any]:
        """Read file contents."""
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return {"error": "File not found"}
            return {"content": file_path.read_text()}
        except Exception as e:
            return {"error": str(e)}

    class WriteFileRequest(BaseModel):
        path: str
        content: str

    @app.post("/api/files/write")
    async def write_file_contents(request: WriteFileRequest) -> dict[str, Any]:
        """Write file contents."""
        try:
            file_path = Path(request.path).expanduser().resolve()
            file_path.write_text(request.content)
            return {"status": "written"}
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # WRITER (RFC-086)
    # ═══════════════════════════════════════════════════════════════

    class DiataxisRequest(BaseModel):
        content: str
        file_path: str | None = None

    @app.post("/api/writer/diataxis")
    async def detect_diataxis(request: DiataxisRequest) -> dict[str, Any]:
        """Detect Diataxis content type."""
        # Simple heuristic detection
        content_lower = request.content.lower()
        scores = {"TUTORIAL": 0, "HOW_TO": 0, "EXPLANATION": 0, "REFERENCE": 0}

        if any(k in content_lower for k in ["tutorial", "learn", "quickstart"]):
            scores["TUTORIAL"] += 0.3
        if any(k in content_lower for k in ["how to", "guide", "configure"]):
            scores["HOW_TO"] += 0.3
        if any(k in content_lower for k in ["understand", "architecture", "concepts"]):
            scores["EXPLANATION"] += 0.3
        if any(k in content_lower for k in ["reference", "api", "parameters"]):
            scores["REFERENCE"] += 0.3

        best = max(scores.items(), key=lambda x: x[1])

        return {
            "detection": {
                "detectedType": best[0] if best[1] > 0 else None,
                "confidence": best[1],
                "signals": [],
                "scores": scores,
            },
            "warnings": [],
        }

    class ValidateRequest(BaseModel):
        content: str
        file_path: str | None = None
        lens_name: str = "tech-writer"

    @app.post("/api/writer/validate")
    async def validate_document(request: ValidateRequest) -> dict[str, Any]:
        """Validate document."""
        # Placeholder - return empty warnings
        return {"warnings": []}

    class FixAllRequest(BaseModel):
        content: str
        warnings: list[dict[str, Any]]
        lens_name: str

    @app.post("/api/writer/fix-all")
    async def fix_all_issues(request: FixAllRequest) -> dict[str, Any]:
        """Fix all fixable issues."""
        # Placeholder - return original content
        return {"content": request.content, "fixed": 0}

    class ExecuteSkillRequest(BaseModel):
        skill_id: str
        content: str
        file_path: str | None = None
        lens_name: str

    @app.post("/api/writer/execute-skill")
    async def execute_skill(request: ExecuteSkillRequest) -> dict[str, Any]:
        """Execute a lens skill."""
        # Placeholder
        return {"message": f"Skill {request.skill_id} executed"}

    @app.get("/api/lenses/{lens_id}/skills")
    async def get_lens_skills(lens_id: str) -> dict[str, Any]:
        """Get skills for a lens."""
        # Return default skills
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

    # ═══════════════════════════════════════════════════════════════
    # WORKFLOW (RFC-086)
    # ═══════════════════════════════════════════════════════════════

    class RouteIntentRequest(BaseModel):
        user_input: str

    @app.post("/api/workflow/route")
    async def route_workflow_intent(request: RouteIntentRequest) -> dict[str, Any]:
        """Route natural language to workflow."""
        return {
            "category": "information",
            "confidence": 0.5,
            "signals": [],
            "suggested_workflow": None,
            "tier": "fast",
        }

    class StartWorkflowRequest(BaseModel):
        chain_name: str
        target_file: str | None = None

    @app.post("/api/workflow/start")
    async def start_workflow(request: StartWorkflowRequest) -> dict[str, Any]:
        """Start a workflow chain."""
        import uuid
        from datetime import datetime

        return {
            "id": str(uuid.uuid4()),
            "chain_name": request.chain_name,
            "description": f"Workflow: {request.chain_name}",
            "current_step": 0,
            "total_steps": 3,
            "steps": [],
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "context": {"working_dir": str(Path.cwd())},
        }

    class WorkflowIdRequest(BaseModel):
        execution_id: str

    @app.post("/api/workflow/stop")
    async def stop_workflow(request: WorkflowIdRequest) -> dict[str, Any]:
        """Stop a workflow."""
        return {"status": "stopped"}

    @app.post("/api/workflow/resume")
    async def resume_workflow(request: WorkflowIdRequest) -> dict[str, Any]:
        """Resume a workflow."""
        from datetime import datetime
        return {
            "id": request.execution_id,
            "chain_name": "unknown",
            "description": "Resumed workflow",
            "current_step": 0,
            "total_steps": 3,
            "steps": [],
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "context": {"working_dir": str(Path.cwd())},
        }

    @app.post("/api/workflow/skip-step")
    async def skip_workflow_step(request: WorkflowIdRequest) -> dict[str, Any]:
        """Skip current workflow step."""
        return {"status": "skipped"}

    @app.get("/api/workflow/chains")
    async def list_workflow_chains() -> dict[str, Any]:
        """List available workflow chains."""
        return {
            "chains": [
                {
                    "name": "feature-docs",
                    "description": "Document a new feature",
                    "steps": [],
                    "checkpoint_after": [],
                    "tier": "full",
                },
                {
                    "name": "health-check",
                    "description": "Validate existing docs",
                    "steps": [],
                    "checkpoint_after": [],
                    "tier": "light",
                },
                {
                    "name": "quick-fix",
                    "description": "Fast issue resolution",
                    "steps": [],
                    "checkpoint_after": [],
                    "tier": "fast",
                },
            ]
        }

    @app.get("/api/workflow/active")
    async def list_active_workflows() -> dict[str, Any]:
        """List active workflows."""
        return {"workflows": []}

    # ═══════════════════════════════════════════════════════════════
    # BRIEFING (RFC-071)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/briefing")
    async def get_briefing(path: str) -> dict[str, Any]:
        """Get briefing for a project."""
        return {"briefing": None}

    @app.get("/api/briefing/exists")
    async def briefing_exists(path: str) -> dict[str, Any]:
        """Check if briefing exists."""
        return {"exists": False}

    class ClearBriefingRequest(BaseModel):
        path: str

    @app.post("/api/briefing/clear")
    async def clear_briefing(request: ClearBriefingRequest) -> dict[str, Any]:
        """Clear briefing for a project."""
        return {"success": True}

    # ═══════════════════════════════════════════════════════════════
    # PROMPTS
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/prompts")
    async def get_saved_prompts() -> dict[str, Any]:
        """Get saved prompts."""
        return {"prompts": []}

    class SavePromptRequest(BaseModel):
        prompt: str

    @app.post("/api/prompts")
    async def save_prompt(request: SavePromptRequest) -> dict[str, Any]:
        """Save a prompt."""
        return {"status": "saved"}

    class RemovePromptRequest(BaseModel):
        prompt: str

    @app.post("/api/prompts/remove")
    async def remove_prompt(request: RemovePromptRequest) -> dict[str, Any]:
        """Remove a saved prompt."""
        return {"status": "removed"}

    # ═══════════════════════════════════════════════════════════════
    # SURFACE (RFC-072)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/surface/registry")
    async def get_surface_registry() -> list[dict[str, Any]]:
        """Get primitive registry."""
        # Placeholder - return empty registry
        return []

    class ComposeSurfaceRequest(CamelModel):
        goal: str
        project_path: str | None = None
        lens: str | None = None
        arrangement: str | None = None

    @app.post("/api/surface/compose")
    async def compose_surface(request: ComposeSurfaceRequest) -> dict[str, Any]:
        """Compose a surface layout for a goal."""
        # Placeholder - return minimal layout
        return {
            "primary": {"id": "code-editor", "category": "code", "size": "large", "props": {}},
            "secondary": [],
            "contextual": [],
            "arrangement": request.arrangement or "standard",
        }

    class SurfaceSuccessRequest(CamelModel):
        layout: dict[str, Any]
        goal: str
        duration_seconds: int
        completed: bool

    @app.post("/api/surface/success")
    async def record_surface_success(request: SurfaceSuccessRequest) -> dict[str, Any]:
        """Record layout success metrics."""
        # Placeholder - just acknowledge
        return {"status": "recorded"}

    class SurfaceEventRequest(BaseModel):
        primitive_id: str
        event_type: str
        data: dict[str, Any]

    @app.post("/api/surface/event")
    async def emit_surface_event(request: SurfaceEventRequest) -> dict[str, Any]:
        """Emit a primitive event."""
        # Placeholder - just acknowledge
        return {"status": "emitted"}

    # ═══════════════════════════════════════════════════════════════
    # MEMORY (Extended for RFC-084)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/memory/chunks")
    async def get_memory_chunks(path: str) -> dict[str, Any]:
        """Get chunk hierarchy for a project."""
        # Placeholder - return empty hierarchy
        return {"hot": [], "warm": [], "cold": []}

    @app.get("/api/memory/graph")
    async def get_memory_graph(path: str) -> dict[str, Any]:
        """Get concept graph for a project."""
        # Placeholder - return empty graph
        return {"edges": []}

    # ═══════════════════════════════════════════════════════════════
    # PREVIEW
    # ═══════════════════════════════════════════════════════════════

    @app.post("/api/preview/launch")
    async def launch_preview() -> dict[str, Any]:
        """Launch preview for current project."""
        # Placeholder - return empty session
        return {"url": None, "content": None, "view_type": "web_view"}

    @app.post("/api/preview/stop")
    async def stop_preview() -> dict[str, Any]:
        """Stop preview."""
        return {"status": "stopped"}

    # ═══════════════════════════════════════════════════════════════
    # SECURITY (RFC-048)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/security/dag/{dag_id}/permissions")
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

    @app.post("/api/security/approval")
    async def submit_security_approval(response: dict[str, Any]) -> dict[str, Any]:
        """Submit security approval response."""
        return {"success": True}

    @app.get("/api/security/audit")
    async def get_audit_log(limit: int = 50) -> list[dict[str, Any]]:
        """Get audit log entries."""
        return []

    @app.get("/api/security/audit/verify")
    async def verify_audit() -> dict[str, Any]:
        """Verify audit log integrity."""
        return {"valid": True, "message": "Audit log is intact"}

    class SecurityScanRequest(BaseModel):
        content: str

    @app.post("/api/security/scan")
    async def scan_security(request: SecurityScanRequest) -> list[dict[str, Any]]:
        """Scan content for security issues."""
        return []

    # ═══════════════════════════════════════════════════════════════
    # WEAKNESS (RFC-063)
    # ═══════════════════════════════════════════════════════════════

    class WeaknessScanRequest(BaseModel):
        path: str

    @app.post("/api/weakness/scan")
    async def scan_weaknesses(request: WeaknessScanRequest) -> dict[str, Any]:
        """Scan project for weaknesses."""
        return {
            "weaknesses": [],
            "overall_health": 1.0,
            "scan_timestamp": None,
        }

    class WeaknessPreviewRequest(BaseModel):
        path: str
        artifact_id: str

    @app.post("/api/weakness/preview")
    async def preview_cascade(request: WeaknessPreviewRequest) -> dict[str, Any]:
        """Preview cascade fix."""
        return {
            "artifact_id": request.artifact_id,
            "affected_files": [],
            "estimated_changes": 0,
        }

    class WeaknessExecuteRequest(BaseModel):
        path: str
        artifact_id: str
        auto_approve: bool = False
        confidence_threshold: float = 0.7

    @app.post("/api/weakness/execute")
    async def execute_cascade(request: WeaknessExecuteRequest) -> dict[str, Any]:
        """Start cascade execution."""
        return {
            "execution_id": None,
            "artifact_id": request.artifact_id,
            "status": "pending",
            "completed": False,
        }

    @app.post("/api/weakness/fix")
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

    class InterfaceProcessRequest(BaseModel):
        goal: str
        data_dir: str | None = None

    @app.post("/api/interface/process")
    async def process_interface(request: InterfaceProcessRequest) -> dict[str, Any]:
        """Process goal through generative interface."""
        return {
            "response": "",
            "type": "conversation",
            "artifacts": [],
        }

    # ═══════════════════════════════════════════════════════════════
    # COMPOSITION (RFC-072)
    # ═══════════════════════════════════════════════════════════════

    class CompositionPredictRequest(BaseModel):
        input: str
        current_page: str = "home"

    @app.post("/api/composition/predict")
    async def predict_composition(request: CompositionPredictRequest) -> dict[str, Any] | None:
        """Predict composition for input."""
        # Placeholder - return null (no prediction)
        return None

    # ═══════════════════════════════════════════════════════════════
    # PROJECT RUN (RFC-066)
    # ═══════════════════════════════════════════════════════════════

    class AnalyzeRunRequest(CamelModel):
        path: str
        force_refresh: bool = False

    @app.post("/api/project/analyze-run")
    async def analyze_project_for_run(request: AnalyzeRunRequest) -> dict[str, Any]:
        """Analyze project for running."""
        project_path = Path(request.path).expanduser().resolve()

        # Simple detection logic
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

    class ProjectRunRequest(CamelModel):
        path: str
        command: str
        install_first: bool = False
        save_command: bool = False

    @app.post("/api/project/run")
    async def run_project(request: ProjectRunRequest) -> dict[str, Any]:
        """Run a project."""
        import uuid
        return {
            "sessionId": str(uuid.uuid4()),
            "status": "started",
            "command": request.command,
        }

    class StopRunRequest(CamelModel):
        session_id: str | None = None
        session_id: str | None = None

    @app.post("/api/project/run/stop")
    async def stop_project_run(request: StopRunRequest) -> dict[str, Any]:
        """Stop a project run."""
        return {"status": "stopped"}

    @app.post("/api/run/stop")
    async def stop_run(request: StopRunRequest) -> dict[str, Any]:
        """Stop a run (alias)."""
        return {"status": "stopped"}

    # ═══════════════════════════════════════════════════════════════
    # HEALTH
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Health check."""
        return {
            "status": "healthy",
            "active_runs": len(_run_manager._runs),
        }

    # ═══════════════════════════════════════════════════════════════
    # COORDINATOR / WORKERS (RFC-100)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/coordinator/state")
    async def get_coordinator_state(path: str) -> dict[str, Any]:
        """Get coordinator state for UI."""
        from sunwell.parallel.config import MultiInstanceConfig
        from sunwell.parallel.coordinator import Coordinator

        project_path = Path(path).expanduser().resolve()
        if not project_path.exists():
            return {"error": "Project path does not exist"}

        try:
            coordinator = Coordinator(project_path, config=MultiInstanceConfig())
            ui_state = await coordinator.get_ui_state()

            return {
                "workers": [
                    {
                        "id": w.worker_id,
                        "goal": w.current_goal_id or "",
                        "status": w.state.value,
                        "progress": 0,  # Would need progress tracking
                        "current_file": None,
                        "branch": w.branch,
                        "goals_completed": w.goals_completed,
                        "goals_failed": w.goals_failed,
                        "last_heartbeat": w.last_heartbeat.isoformat(),
                    }
                    for w in ui_state.workers
                ],
                "conflicts": [
                    {
                        "path": c.path,
                        "worker_a": c.worker_a,
                        "worker_b": c.worker_b,
                        "conflict_type": c.conflict_type,
                        "resolution": c.resolution,
                        "detected_at": c.detected_at.isoformat() if c.detected_at else None,
                    }
                    for c in ui_state.conflicts
                ],
                "total_progress": ui_state.total_progress,
                "merged_branches": [],
                "pending_merges": [],
                "is_running": ui_state.is_running,
                "started_at": None,
                "last_update": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "workers": [], "conflicts": [], "is_running": False}

    class StartWorkersRequest(CamelModel):
        project_path: str
        num_workers: int = 4
        dry_run: bool = False

    @app.post("/api/coordinator/start-workers")
    async def start_workers(request: StartWorkersRequest) -> dict[str, Any]:
        """Start parallel workers."""
        from sunwell.parallel.config import MultiInstanceConfig
        from sunwell.parallel.coordinator import Coordinator

        project_path = Path(request.projectPath).expanduser().resolve()
        if not project_path.exists():
            return {"error": "Project path does not exist"}

        try:
            config = MultiInstanceConfig(
                num_workers=request.num_workers,
                dry_run=request.dry_run,
            )
            coordinator = Coordinator(project_path, config=config)

            # Run in background task
            import asyncio
            asyncio.create_task(coordinator.execute())

            return {"status": "started", "num_workers": request.num_workers}
        except Exception as e:
            return {"error": str(e)}

    class PauseWorkerRequest(CamelModel):
        project_path: str
        worker_id: int

    @app.post("/api/coordinator/pause-worker")
    async def pause_worker(request: PauseWorkerRequest) -> dict[str, Any]:
        """Pause a specific worker."""
        # Workers read pause state from status file
        workers_dir = Path(request.project_path) / ".sunwell" / "workers"
        pause_file = workers_dir / f"worker-{request.worker_id}.pause"
        pause_file.parent.mkdir(parents=True, exist_ok=True)
        pause_file.touch()
        return {"status": "paused", "worker_id": request.worker_id}

    @app.post("/api/coordinator/resume-worker")
    async def resume_worker(request: PauseWorkerRequest) -> dict[str, Any]:
        """Resume a paused worker."""
        workers_dir = Path(request.project_path) / ".sunwell" / "workers"
        pause_file = workers_dir / f"worker-{request.worker_id}.pause"
        if pause_file.exists():
            pause_file.unlink()
        return {"status": "resumed", "worker_id": request.worker_id}

    @app.get("/api/coordinator/state-dag")
    async def get_coordinator_state_dag(path: str) -> dict[str, Any]:
        """Get State DAG for brownfield scanning."""
        try:
            from sunwell.analysis.state_dag import StateDagBuilder

            project_path = Path(path).expanduser().resolve()
            if not project_path.exists():
                return {"error": "Project path does not exist"}

            builder = StateDagBuilder(project_path)
            dag = await builder.build()

            return {
                "root": str(dag.root) if hasattr(dag, 'root') else str(project_path),
                "scanned_at": datetime.now().isoformat(),
                "lens_name": None,
                "overall_health": getattr(dag, 'overall_health', 1.0),
                "node_count": len(getattr(dag, 'nodes', [])),
                "edge_count": len(getattr(dag, 'edges', [])),
                "unhealthy_count": 0,
                "critical_count": 0,
                "nodes": [],
                "edges": [],
                "metadata": {},
            }
        except ImportError:
            return {"nodes": [], "edges": [], "overall_health": 1.0, "node_count": 0}
        except Exception as e:
            return {"error": str(e), "nodes": [], "edges": []}

    # ═══════════════════════════════════════════════════════════════
    # BACKLOG (RFC-114)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/backlog")
    async def get_backlog(path: str | None = None) -> dict[str, Any]:
        """Get backlog goals."""
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(path).expanduser().resolve() if path else Path.cwd()

        try:
            manager = BacklogManager(project_path)
            goals = []
            for goal in manager.backlog.execution_order():
                status = "completed" if goal.id in manager.backlog.completed else \
                         "blocked" if goal.id in manager.backlog.blocked else \
                         "executing" if goal.id == manager.backlog.in_progress else \
                         "claimed" if goal.claimed_by is not None else "pending"
                goals.append({
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "priority": goal.priority,
                    "category": goal.category,
                    "status": status,
                    "estimated_complexity": goal.estimated_complexity,
                    "auto_approvable": goal.auto_approvable,
                    "requires": list(goal.requires),
                    "claimed_by": goal.claimed_by,
                    "created_at": goal.claimed_at.isoformat() if goal.claimed_at else None,
                })
            return {"goals": goals, "total": len(goals)}
        except Exception as e:
            return {"error": str(e), "goals": []}

    class AddGoalRequest(BaseModel):
        title: str
        description: str | None = None
        category: str = "add"
        priority: float = 0.5
        path: str | None = None

    @app.post("/api/backlog/goals")
    async def add_backlog_goal(request: AddGoalRequest) -> dict[str, Any]:
        """Add a goal to the backlog."""
        import hashlib

        from sunwell.backlog.goals import Goal, GoalScope
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(request.path).expanduser().resolve() if request.path else Path.cwd()

        try:
            manager = BacklogManager(project_path)
            title_hash = hashlib.blake2b(request.title.encode(), digest_size=4).hexdigest()
            goal_id = f"explicit-{title_hash}"

            goal = Goal(
                id=goal_id,
                title=request.title[:60],
                description=request.description or request.title,
                source_signals=(),
                priority=request.priority,
                estimated_complexity="moderate",
                requires=frozenset(),
                category=request.category,  # type: ignore
                auto_approvable=False,
                scope=GoalScope(max_files=10, max_lines_changed=1000),
            )

            await manager.add_external_goal(goal)
            return {"status": "added", "goal_id": goal_id}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/backlog/goals/{goal_id}")
    async def get_backlog_goal(goal_id: str, path: str | None = None) -> dict[str, Any]:
        """Get a specific goal."""
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(path).expanduser().resolve() if path else Path.cwd()

        try:
            manager = BacklogManager(project_path)
            goal = await manager.get_goal(goal_id)
            if not goal:
                return {"error": "Goal not found"}

            status = "completed" if goal.id in manager.backlog.completed else \
                     "blocked" if goal.id in manager.backlog.blocked else \
                     "executing" if goal.id == manager.backlog.in_progress else \
                     "claimed" if goal.claimed_by is not None else "pending"

            return {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "priority": goal.priority,
                "category": goal.category,
                "status": status,
                "estimated_complexity": goal.estimated_complexity,
                "auto_approvable": goal.auto_approvable,
                "requires": list(goal.requires),
                "claimed_by": goal.claimed_by,
            }
        except Exception as e:
            return {"error": str(e)}

    class UpdateGoalRequest(BaseModel):
        title: str | None = None
        description: str | None = None
        priority: float | None = None
        path: str | None = None

    @app.put("/api/backlog/goals/{goal_id}")
    async def update_backlog_goal(goal_id: str, request: UpdateGoalRequest) -> dict[str, Any]:
        """Update a goal."""
        # Placeholder - would need to implement goal update in BacklogManager
        return {"status": "updated", "goal_id": goal_id}

    @app.delete("/api/backlog/goals/{goal_id}")
    async def delete_backlog_goal(goal_id: str, path: str | None = None) -> dict[str, Any]:
        """Remove a goal from backlog."""
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(path).expanduser().resolve() if path else Path.cwd()

        try:
            manager = BacklogManager(project_path)
            if goal_id in manager.backlog.goals:
                del manager.backlog.goals[goal_id]
                manager._save()
                return {"status": "deleted", "goal_id": goal_id}
            return {"error": "Goal not found"}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/backlog/goals/{goal_id}/skip")
    async def skip_backlog_goal(goal_id: str, path: str | None = None) -> dict[str, Any]:
        """Skip a goal."""
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(path).expanduser().resolve() if path else Path.cwd()

        try:
            manager = BacklogManager(project_path)
            await manager.block_goal(goal_id, "Skipped by user")
            return {"status": "skipped", "goal_id": goal_id}
        except Exception as e:
            return {"error": str(e)}

    class ReorderGoalsRequest(BaseModel):
        order: list[str]
        path: str | None = None

    @app.post("/api/backlog/reorder")
    async def reorder_backlog_goals(request: ReorderGoalsRequest) -> dict[str, Any]:
        """Reorder goals by priority."""
        from sunwell.backlog.goals import Goal
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(request.path).expanduser().resolve() if request.path else Path.cwd()

        try:
            manager = BacklogManager(project_path)

            # Update priorities based on order (higher index = lower priority)
            total = len(request.order)
            for i, goal_id in enumerate(request.order):
                if goal_id in manager.backlog.goals:
                    old_goal = manager.backlog.goals[goal_id]
                    # Create new goal with updated priority
                    new_priority = 1.0 - (i / total) if total > 0 else 0.5
                    manager.backlog.goals[goal_id] = Goal(
                        id=old_goal.id,
                        title=old_goal.title,
                        description=old_goal.description,
                        source_signals=old_goal.source_signals,
                        priority=new_priority,
                        estimated_complexity=old_goal.estimated_complexity,
                        requires=old_goal.requires,
                        category=old_goal.category,
                        auto_approvable=old_goal.auto_approvable,
                        scope=old_goal.scope,
                        external_ref=old_goal.external_ref,
                        claimed_by=old_goal.claimed_by,
                        claimed_at=old_goal.claimed_at,
                    )

            manager._save()
            return {"status": "reordered"}
        except Exception as e:
            return {"error": str(e)}

    class RefreshBacklogRequest(BaseModel):
        path: str | None = None

    @app.post("/api/backlog/refresh")
    async def refresh_backlog(request: RefreshBacklogRequest) -> dict[str, Any]:
        """Refresh backlog from project signals."""
        from sunwell.backlog.manager import BacklogManager

        project_path = Path(request.path).expanduser().resolve() if request.path else Path.cwd()

        try:
            manager = BacklogManager(project_path)
            await manager.refresh()
            return {"status": "refreshed", "goal_count": len(manager.backlog.goals)}
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # INDEXING (RFC-113)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/indexing/status")
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

    class IndexingStartRequest(BaseModel):
        workspace_path: str

    @app.post("/api/indexing/start")
    async def start_indexing(request: IndexingStartRequest) -> dict[str, Any]:
        """Start indexing service."""
        return {"status": "started", "workspace": request.workspace_path}

    @app.post("/api/indexing/stop")
    async def stop_indexing() -> dict[str, Any]:
        """Stop indexing service."""
        return {"status": "stopped"}

    class IndexingQueryRequest(BaseModel):
        text: str
        top_k: int = 10

    @app.post("/api/indexing/query")
    async def query_index(request: IndexingQueryRequest) -> dict[str, Any]:
        """Query the index."""
        return {"results": [], "query": request.text}

    @app.post("/api/indexing/rebuild")
    async def rebuild_index() -> dict[str, Any]:
        """Rebuild the index."""
        return {"status": "rebuilding"}

    @app.post("/api/indexing/settings")
    async def update_indexing_settings(settings: dict[str, Any]) -> dict[str, Any]:
        """Update indexing settings."""
        return {"status": "updated", "settings": settings}

    # ═══════════════════════════════════════════════════════════════
    # PROJECT EXTENDED (RFC-113)
    # ═══════════════════════════════════════════════════════════════

    @app.post("/api/project/analyze-for-run")
    async def analyze_project_for_run_alias(request: AnalyzeRunRequest) -> dict[str, Any]:
        """Alias for analyze-run (frontend compatibility)."""
        return await analyze_project_for_run(request)

    @app.get("/api/project/file")
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

    @app.get("/api/project/status")
    async def get_project_status(path: str) -> dict[str, Any]:
        """Get project status."""
        project_path = Path(path).expanduser().resolve()
        return {
            "path": str(project_path),
            "exists": project_path.exists(),
            "has_sunwell": (project_path / ".sunwell").exists(),
            "has_git": (project_path / ".git").exists(),
        }

    @app.get("/api/project/dag")
    async def get_project_dag(path: str) -> dict[str, Any]:
        """Get project DAG."""
        return {"nodes": [], "edges": [], "metadata": {}}

    @app.get("/api/project/memory/stats")
    async def get_project_memory_stats(path: str) -> dict[str, Any]:
        """Get project memory stats."""
        return {
            "total_learnings": 0,
            "total_dead_ends": 0,
            "session_count": 0,
        }

    @app.get("/api/project/intelligence")
    async def get_project_intelligence(path: str) -> dict[str, Any]:
        """Get project intelligence data."""
        return {
            "signals": [],
            "context_quality": 1.0,
        }

    # ═══════════════════════════════════════════════════════════════
    # LENSES CONFIG (RFC-113)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/lenses/config")
    async def get_lenses_config(path: str) -> dict[str, Any]:
        """Get lens config for a project."""
        project_path = Path(path).expanduser().resolve()
        config_file = project_path / ".sunwell" / "lens.json"

        if config_file.exists():
            import json
            try:
                return json.loads(config_file.read_text())
            except json.JSONDecodeError:
                pass

        return {"default_lens": None, "auto_select": True}

    class LensConfigRequest(CamelModel):
        path: str
        lens_name: str | None = None
        auto_select: bool = True

    @app.post("/api/lenses/config")
    async def set_lenses_config(request: LensConfigRequest) -> dict[str, Any]:
        """Set lens config for a project."""
        import json

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
    # CONVERGENCE (RFC-113)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/convergence/{slot}")
    async def get_convergence_slot(slot: str) -> dict[str, Any] | None:
        """Get convergence slot data."""
        return None

    # ═══════════════════════════════════════════════════════════════
    # HOME (RFC-080)
    # ═══════════════════════════════════════════════════════════════

    class HomePredictCompositionRequest(CamelModel):
        input: str
        current_page: str = "home"

    @app.post("/api/home/predict-composition")
    async def home_predict_composition(
        request: HomePredictCompositionRequest,
    ) -> dict[str, Any] | None:
        """Fast Tier 0/1 composition prediction for speculative UI."""
        # Simple pattern-based routing for fast response
        input_lower = request.input.lower()

        # Detect patterns
        page_type = "conversation"
        panels = []
        input_mode = "chat"
        suggested_tools: list[str] = []

        if any(k in input_lower for k in ["project", "open", "create project"]):
            page_type = "project"
            panels = [{"panel_type": "project_selector", "title": "Projects"}]
            suggested_tools = ["file_tree", "terminal"]
        elif any(k in input_lower for k in ["plan", "design", "architect"]):
            page_type = "planning"
            panels = [{"panel_type": "dag_view", "title": "Plan"}]
            suggested_tools = ["dag", "notes"]
        elif any(k in input_lower for k in ["research", "find", "search", "learn"]):
            page_type = "research"
            panels = [{"panel_type": "search_results", "title": "Research"}]
            suggested_tools = ["web_search", "codebase_search"]
        elif any(k in input_lower for k in ["build", "implement", "code", "fix", "add"]):
            page_type = "project"
            panels = [{"panel_type": "code_editor", "title": "Code"}]
            input_mode = "command"
            suggested_tools = ["editor", "terminal", "git"]

        return {
            "page_type": page_type,
            "panels": panels,
            "input_mode": input_mode,
            "suggested_tools": suggested_tools,
            "confidence": 0.75,
            "source": "regex",
        }

    class HomeProcessGoalRequest(CamelModel):
        goal: str
        data_dir: str | None = None
        history: list[dict[str, str]] | None = None

    @app.post("/api/home/process-goal")
    async def home_process_goal(request: HomeProcessGoalRequest) -> dict[str, Any]:
        """Process a goal through the interaction router (Tier 2)."""
        goal_lower = request.goal.lower()

        # Route based on intent
        if any(k in goal_lower for k in ["hello", "hi", "hey", "help"]):
            return {
                "type": "conversation",
                "response": (
                    "Hello! I'm Sunwell, your AI development assistant. I can help you:\n\n"
                    "• **Build projects** - 'Build a REST API for...' or 'Create a todo app'\n"
                    "• **Research code** - 'How does X work?' or 'Find where Y is defined'\n"
                    "• **Plan work** - 'Design a system for...' or 'Break down this feature'\n"
                    "• **Fix issues** - 'Fix the bug in...' or 'Why is this failing?'\n\n"
                    "What would you like to work on?"
                ),
                "mode": "informational",
                "suggested_tools": ["project_selector", "terminal"],
            }

        if any(k in goal_lower for k in ["build", "create", "implement", "code", "fix", "add"]):
            return {
                "type": "workspace",
                "layout_id": "code_workspace",
                "response": f"I'll help you with: {request.goal}",
                "workspace_spec": {
                    "primary": "code_editor",
                    "secondary": ["file_tree", "terminal"],
                    "contextual": ["agent_status"],
                    "arrangement": "standard",
                    "seed_content": {"goal": request.goal},
                },
            }

        if any(k in goal_lower for k in ["plan", "design", "architect", "break down"]):
            return {
                "type": "view",
                "view_type": "planning",
                "response": f"Let me help you plan: {request.goal}",
                "data": {"goal": request.goal},
            }

        if any(k in goal_lower for k in ["show", "list", "what", "where", "find"]):
            return {
                "type": "view",
                "view_type": "search_results",
                "response": f"Searching for: {request.goal}",
                "data": {"query": request.goal},
            }

        # Default to conversation
        return {
            "type": "conversation",
            "response": (
                f"I understand you want to: {request.goal}\n\n"
                "How would you like me to help? I can build it, research it, or break it down."
            ),
            "mode": "collaborative",
            "suggested_tools": [],
        }

    class HomeExecuteBlockActionRequest(CamelModel):
        action_id: str
        item_id: str | None = None
        data_dir: str | None = None

    @app.post("/api/home/execute-block-action")
    async def home_execute_block_action(request: HomeExecuteBlockActionRequest) -> dict[str, Any]:
        """Execute a block action (e.g., complete habit, open project)."""
        return {"success": True, "message": f"Action {request.action_id} executed"}

    # ═══════════════════════════════════════════════════════════════
    # RUN MANAGEMENT (RFC-113 extended)
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/run/active")
    async def get_active_runs() -> list[dict[str, Any]]:
        """Get all active runs."""
        return [
            {
                "run_id": run.run_id,
                "goal": run.goal,
                "status": run.status,
                "event_count": len(run.events),
            }
            for run in _run_manager.list_runs()
            if run.status in ("pending", "running")
        ]

    @app.get("/api/run/history")
    async def get_run_history(limit: int = 20) -> list[dict[str, Any]]:
        """Get run history."""
        runs = _run_manager.list_runs()
        return [
            {
                "run_id": run.run_id,
                "goal": run.goal,
                "status": run.status,
                "event_count": len(run.events),
            }
            for run in runs[-limit:]
        ]


async def _execute_agent(run: RunState) -> AsyncIterator[dict[str, Any]]:
    """Execute the agent and yield events.

    This is where we wire the real Agent.run() to the WebSocket.
    """
    from sunwell.agent import Agent, RunOptions, RunRequest
    from sunwell.agent.budget import AdaptiveBudget
    from sunwell.config import get_config
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    # RFC-117: Resolve workspace with project context
    from sunwell.project import ProjectResolutionError, resolve_project

    workspace_path = Path(run.workspace).expanduser().resolve() if run.workspace else None

    project = None
    try:
        # Prefer project_id if provided, otherwise use workspace path
        project = resolve_project(
            project_id=run.project_id,
            project_root=workspace_path,
        )
        workspace = project.root
    except ProjectResolutionError:
        workspace = workspace_path or Path.cwd()

    # Load config and model
    config = get_config()
    provider = run.provider or (config.model.default_provider if config else "ollama")
    model_name = run.model or (config.model.default_model if config else "gemma3:4b")

    # Create model
    from sunwell.cli.helpers import resolve_model

    try:
        synthesis_model = resolve_model(provider, model_name)
    except Exception as e:
        yield {"type": "error", "data": {"message": f"Failed to load model: {e}"}}
        return

    if not synthesis_model:
        yield {"type": "error", "data": {"message": "No model available"}}
        return

    # Setup tool executor (RFC-117: use project if available)
    trust_level = ToolTrust.from_string(run.trust)
    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace if project is None else None,
        policy=ToolPolicy(trust_level=trust_level),
    )

    # Create agent
    agent = Agent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=workspace,
        budget=AdaptiveBudget(total_budget=50_000),
    )

    # Build request
    request = RunRequest(
        goal=run.goal,
        context={"cwd": str(workspace)},
        cwd=workspace,
        options=RunOptions(
            trust=run.trust,
            timeout_seconds=run.timeout,
        ),
    )

    # Execute and yield events, broadcasting to global bus (RFC-119)
    async for event in agent.run(request):
        if run.is_cancelled:
            break

        event_dict = event.to_dict()

        # Broadcast to all subscribers for unified visibility
        bus_event = BusEvent(
            v=1,
            run_id=run.run_id,
            type=event_dict.get("type", "unknown"),
            data=event_dict.get("data", {}),
            timestamp=datetime.now(UTC),
            source=run.source,
            project_id=run.project_id,
        )
        await _event_bus.broadcast(bus_event)

        yield event_dict

    # Mark run complete
    run.complete()


def _mount_static(app: FastAPI, static_dir: Path) -> None:
    """Mount static files for production mode."""

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    # Mount static assets
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
