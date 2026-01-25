"""Agent execution and event streaming routes (RFC-119)."""

import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from sunwell.server.events import BusEvent, EventBus
from sunwell.server.runs import RunManager, RunState
from sunwell.server.workspace_manager import get_workspace_manager

router = APIRouter(prefix="/api", tags=["agent"])

# Global instances (shared across requests)
_run_manager = RunManager()
_event_bus = EventBus()
_workspace_manager = get_workspace_manager()


def get_run_manager() -> RunManager:
    """Get the global run manager."""
    return _run_manager


def get_event_bus() -> EventBus:
    """Get the global event bus."""
    return _event_bus


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class RunRequest(BaseModel):
    goal: str
    workspace: str | None = None
    project_id: str | None = None
    lens: str | None = None
    provider: str | None = None
    model: str | None = None
    trust: str = "workspace"
    timeout: int = 300
    source: str = "studio"
    use_v2: bool = False
    """Use new SessionContext + PersistentMemory architecture."""


class StopRunRequest(BaseModel):
    session_id: str | None = None


# ═══════════════════════════════════════════════════════════════
# AGENT EXECUTION ROUTES
# ═══════════════════════════════════════════════════════════════


@router.post("/run")
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
        use_v2=request.use_v2,
    )
    return {"run_id": run.run_id, "status": run.status, "use_v2": run.use_v2}


@router.get("/run/{run_id}")
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


@router.delete("/run/{run_id}")
async def cancel_run(run_id: str) -> dict[str, Any]:
    """Cancel a running agent."""
    run = _run_manager.get_run(run_id)
    if not run:
        return {"error": "Run not found"}
    run.cancel()
    return {"status": "cancelled"}


@router.websocket("/run/{run_id}/events")
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
            async for event in _execute_agent(run, use_v2=run.use_v2):
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


@router.websocket("/events")
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


@router.get("/runs")
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
# RUN MANAGEMENT EXTENDED
# ═══════════════════════════════════════════════════════════════


@router.get("/run/active")
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


@router.get("/run/history")
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


@router.post("/run/stop")
async def stop_run(request: StopRunRequest) -> dict[str, Any]:
    """Stop a run."""
    return {"status": "stopped"}


# ═══════════════════════════════════════════════════════════════
# AGENT EXECUTION
# ═══════════════════════════════════════════════════════════════


async def _execute_agent(run: RunState, *, use_v2: bool = False) -> AsyncIterator[dict[str, Any]]:
    """Execute the agent and yield events.

    This is where we wire the real Agent.run() to the WebSocket.

    Args:
        run: The run state containing goal, workspace, options.
        use_v2: Deprecated, always uses SessionContext + PersistentMemory.
    """
    from sunwell.agent import Agent
    from sunwell.agent.budget import AdaptiveBudget
    from sunwell.config import get_config
    from sunwell.project import (
        ProjectResolutionError,
        ProjectValidationError,
        resolve_project,
    )
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust
    from sunwell.workspace import default_workspace_root

    workspace_path = Path(run.workspace).expanduser().resolve() if run.workspace else None

    project = None
    try:
        project = resolve_project(
            project_id=run.project_id,
            project_root=workspace_path,
        )
        workspace = project.root
    except ProjectValidationError:
        # Workspace is invalid (e.g., Sunwell's own repo) - auto-create in default location
        workspace = _create_default_workspace(run.goal, default_workspace_root())
        yield {
            "type": "info",
            "data": {"message": f"Created project workspace: {workspace}"},
        }
    except ProjectResolutionError:
        workspace = workspace_path or Path.cwd()

    config = get_config()
    provider = run.provider or (config.model.default_provider if config else "ollama")
    model_name = run.model or (config.model.default_model if config else "gemma3:4b")

    from sunwell.cli.helpers import resolve_model

    try:
        synthesis_model = resolve_model(provider, model_name)
    except Exception as e:
        yield {"type": "error", "data": {"message": f"Failed to load model: {e}"}}
        return

    if not synthesis_model:
        yield {"type": "error", "data": {"message": "No model available"}}
        return

    trust_level = ToolTrust.from_string(run.trust)
    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace if project is None else None,
        policy=ToolPolicy(trust_level=trust_level),
    )

    agent = Agent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=workspace,
        budget=AdaptiveBudget(total_budget=50_000),
    )

    # RFC-MEMORY: Single unified execution path
    # Build session and load memory via WorkspaceManager
    session, memory = await _workspace_manager.build_session_async(
        workspace,
        run.goal,
        trust=run.trust,
        timeout=run.timeout,
        model=run.model,
    )

    async for event in agent.run(session, memory):
        if run.is_cancelled:
            break

        event_dict = event.to_dict()

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

    run.complete()


def _create_default_workspace(goal: str, default_root: Path) -> Path:
    """Create a workspace in the default location based on goal.

    Args:
        goal: User's goal text (used to derive project name)
        default_root: Default workspace root (e.g., ~/Sunwell/projects/)

    Returns:
        Path to created workspace
    """
    import re
    import time

    # Extract a name from the goal
    # Take first few words, remove special chars
    words = re.sub(r"[^\w\s-]", "", goal.lower()).split()[:3]
    name = "-".join(words) if words else "project"

    # Ensure unique name
    workspace = default_root / name
    if workspace.exists():
        workspace = default_root / f"{name}-{int(time.time()) % 10000}"

    # Create the directory
    workspace.mkdir(parents=True, exist_ok=True)

    return workspace
