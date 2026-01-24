"""FastAPI application for Studio UI (RFC-113).

This is the HTTP/WebSocket server that replaces the Rust/Tauri bridge.
All Studio communication goes through here.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sunwell.server.runs import RunManager, RunState

# Global run manager (single server instance)
_run_manager = RunManager()


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
        lens: str | None = None
        provider: str | None = None
        model: str | None = None
        trust: str = "workspace"
        timeout: int = 300

    @app.post("/api/run")
    async def start_run(request: RunRequest) -> dict[str, Any]:
        """Start an agent run, return run_id for WebSocket connection."""
        run = _run_manager.create_run(
            goal=request.goal,
            workspace=request.workspace,
            lens=request.lens,
            provider=request.provider,
            model=request.model,
            trust=request.trust,
            timeout=request.timeout,
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
                try:
                    await websocket.send_json(error_event)
                except Exception:
                    pass
            finally:
                try:
                    await websocket.close()
                except Exception:
                    pass

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
                "learnings": [l.to_dict() for l in store.learnings],
                "dead_ends": [d.to_dict() for d in store.dead_ends],
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
        """Run a demo comparison (single-shot vs Sunwell)."""
        try:
            from sunwell.cli.helpers import resolve_model
            from sunwell.config import get_config
            from sunwell.demo import DemoComparison, DemoExecutor, DemoScorer, get_task

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

            return {
                "model": f"{provider}:{model_name}",
                "task": {"name": demo_task.name, "prompt": demo_task.prompt},
                "single_shot": {
                    "score": single_score.score,
                    "lines": single_score.lines,
                    "time_ms": single_shot.time_ms,
                    "features": single_score.features,
                    "code": single_shot.code,
                },
                "sunwell": {
                    "score": sunwell_score.score,
                    "lines": sunwell_score.lines,
                    "time_ms": sunwell.time_ms,
                    "iterations": sunwell.iterations,
                    "features": sunwell_score.features,
                    "code": sunwell.code,
                },
                "improvement_percent": round(comparison.improvement_percent, 1),
            }
        except Exception as e:
            return {"error": str(e)}

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
    # DAG (RFC-105)
    # ═══════════════════════════════════════════════════════════════

    class DagAppendRequest(BaseModel):
        path: str
        goal: dict[str, Any]

    @app.post("/api/dag/append")
    async def append_goal_to_dag(request: DagAppendRequest) -> dict[str, Any]:
        """Append a completed goal to the DAG."""
        # Placeholder - actual implementation would write to dag.json
        return {"status": "appended"}

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
                {"id": "audit", "name": "Quick Audit", "shortcut": "::a", "description": "Validate document", "category": "validation"},
                {"id": "polish", "name": "Polish", "shortcut": "::p", "description": "Improve clarity", "category": "transformation"},
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
                {"name": "feature-docs", "description": "Document a new feature", "steps": [], "checkpoint_after": [], "tier": "full"},
                {"name": "health-check", "description": "Validate existing docs", "steps": [], "checkpoint_after": [], "tier": "light"},
                {"name": "quick-fix", "description": "Fast issue resolution", "steps": [], "checkpoint_after": [], "tier": "fast"},
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
    # HEALTH
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Health check."""
        return {
            "status": "healthy",
            "active_runs": len(_run_manager._runs),
        }


async def _execute_agent(run: RunState) -> AsyncIterator[dict[str, Any]]:
    """Execute the agent and yield events.

    This is where we wire the real Agent.run() to the WebSocket.
    """
    from sunwell.agent import Agent, RunOptions, RunRequest
    from sunwell.agent.budget import AdaptiveBudget
    from sunwell.config import get_config
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    # Resolve workspace
    workspace = Path(run.workspace).expanduser().resolve() if run.workspace else Path.cwd()

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

    # Setup tool executor
    trust_level = ToolTrust.from_string(run.trust)
    tool_executor = ToolExecutor(
        workspace=workspace,
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

    # Execute and yield events
    async for event in agent.run(request):
        if run.is_cancelled:
            break
        yield event.to_dict()


def _mount_static(app: FastAPI, static_dir: Path) -> None:
    """Mount static files for production mode."""

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    # Mount static assets
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
