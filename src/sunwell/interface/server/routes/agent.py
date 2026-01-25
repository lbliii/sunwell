"""Agent execution and event streaming routes (RFC-119, RFC-112 Observatory)."""

import contextlib
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sunwell.interface.server.events import BusEvent, EventBus
from sunwell.interface.server.routes.models import (
    CamelModel,
    RunCancelResponse,
    RunEventsResponse,
    RunHistoryItem,
    RunItem,
    RunsListResponse,
    RunStartResponse,
    RunStatusResponse,
)
from sunwell.interface.server.run_store import get_run_store
from sunwell.interface.server.runs import RunManager, RunState
from sunwell.interface.server.workspace_manager import get_workspace_manager

# Pre-compiled regex for workspace name generation (avoid recompiling per call)
_RE_NON_WORD = re.compile(r"[^\w\s-]")

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


class RunRequest(CamelModel):
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


class StopRunRequest(CamelModel):
    session_id: str | None = None


# ═══════════════════════════════════════════════════════════════
# AGENT EXECUTION ROUTES
# ═══════════════════════════════════════════════════════════════


@router.post("/run")
async def start_run(request: RunRequest) -> RunStartResponse:
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
    return RunStartResponse(run_id=run.run_id, status=run.status, use_v2=run.use_v2)


@router.get("/run/{run_id}")
async def get_run(run_id: str) -> RunStatusResponse:
    """Get run status."""
    run = _run_manager.get_run(run_id)
    if not run:
        return RunStatusResponse(
            run_id=run_id,
            status="not_found",
            goal="",
            event_count=0,
            error="Run not found",
        )
    return RunStatusResponse(
        run_id=run.run_id,
        status=run.status,
        goal=run.goal,
        event_count=len(run.events),
    )


@router.delete("/run/{run_id}")
async def cancel_run(run_id: str) -> RunCancelResponse:
    """Cancel a running agent."""
    run = _run_manager.get_run(run_id)
    if not run:
        return RunCancelResponse(status="error", error="Run not found")
    run.cancel()
    return RunCancelResponse(status="cancelled")


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
                    _run_manager.complete_run(run.run_id, "cancelled")
                    break

            if run.status == "running":
                _run_manager.complete_run(run.run_id, "complete")

        except WebSocketDisconnect:
            pass  # Client disconnected, run continues buffering
        except Exception as e:
            error_event = {"type": "error", "data": {"message": str(e)}}
            run.events.append(error_event)
            _run_manager.complete_run(run.run_id, "error")
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
async def list_runs(
    project_id: str | None = None,
    limit: int = 20,
    include_historical: bool = True,
) -> RunsListResponse:
    """List all runs, optionally filtered by project.

    Returns runs regardless of origin (CLI, Studio, API).
    Includes both in-memory active runs and historical persisted runs.
    """
    result_runs: list[RunItem] = []
    seen_ids: set[str] = set()

    # First, get active runs from RunManager
    active_runs = _run_manager.list_runs()
    if project_id:
        active_runs = [r for r in active_runs if r.project_id == project_id]

    for r in active_runs:
        seen_ids.add(r.run_id)
        result_runs.append(RunItem(
            run_id=r.run_id,
            goal=r.goal,
            status=r.status,
            source=r.source,
            started_at=r.started_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            event_count=len(r.events),
        ))

    # Then, add historical runs from RunStore (if not already in active)
    if include_historical:
        store = get_run_store()
        historical = store.list_runs(limit=limit, project_id=project_id)
        for r in historical:
            if r.run_id not in seen_ids:
                result_runs.append(RunItem(
                    run_id=r.run_id,
                    goal=r.goal,
                    status=r.status,
                    source=r.source,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                    event_count=len(r.events),
                ))

    # Sort by started_at descending and limit
    result_runs.sort(key=lambda x: x.started_at, reverse=True)
    return RunsListResponse(runs=result_runs[:limit])


# ═══════════════════════════════════════════════════════════════
# RUN MANAGEMENT EXTENDED
# ═══════════════════════════════════════════════════════════════


@router.get("/run/active")
async def get_active_runs() -> list[RunItem]:
    """Get all active runs."""
    return [
        RunItem(
            run_id=run.run_id,
            goal=run.goal,
            status=run.status,
            source=run.source,
            started_at=run.started_at.isoformat() if run.started_at else "",
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            event_count=len(run.events),
        )
        for run in _run_manager.list_runs()
        if run.status in ("pending", "running")
    ]


@router.get("/run/history")
async def get_run_history(
    limit: int = 20,
    project_id: str | None = None,
) -> list[RunHistoryItem]:
    """Get run history from persistent storage.

    Returns historical runs that have been persisted to disk.
    """
    store = get_run_store()
    runs = store.list_runs(limit=limit, project_id=project_id)
    return [
        RunHistoryItem(
            run_id=run.run_id,
            goal=run.goal,
            status=run.status,
            source=run.source,
            started_at=run.started_at,
            completed_at=run.completed_at,
            event_count=len(run.events),
            workspace=run.workspace,
            lens=run.lens,
            model=run.model,
        )
        for run in runs
    ]


@router.get("/run/{run_id}/events")
async def get_run_events(run_id: str) -> RunEventsResponse:
    """Get all events for a run (RFC-112 Observatory).

    First checks active runs in memory, then falls back to persistent storage.
    """
    # Check active runs first
    run = _run_manager.get_run(run_id)
    if run:
        return RunEventsResponse(run_id=run_id, events=run.events)

    # Fall back to persistent storage
    store = get_run_store()
    events = store.get_events(run_id)
    if events:
        return RunEventsResponse(run_id=run_id, events=list(events))

    return RunEventsResponse(run_id=run_id, events=[], error="Run not found")


@router.get("/observatory/data/{run_id}")
async def get_observatory_data(run_id: str) -> dict[str, Any]:
    """Get pre-computed Observatory visualization data for a run (RFC-112).

    Returns extracted state for each visualization:
    - ResonanceWave: refinement iterations
    - PrismFracture: candidate generation/scoring
    - ExecutionCinema: task execution
    - MemoryLattice: learnings
    - ConvergenceProgress: convergence loop
    """
    store = get_run_store()

    # Try to get from persistent storage first
    snapshot = store.get_observatory_snapshot(run_id)
    if snapshot:
        return snapshot.to_dict()

    # Try active run (build snapshot from current events)
    run = _run_manager.get_run(run_id)
    if run:
        # Import here to avoid circular imports
        from sunwell.interface.server.run_store import StoredRun, _extract_observatory_snapshot

        # Build a temporary StoredRun from active run
        temp_run = StoredRun(
            run_id=run.run_id,
            goal=run.goal,
            status=run.status,
            source=run.source,
            started_at=run.started_at.isoformat() if run.started_at else "",
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            workspace=run.workspace,
            project_id=run.project_id,
            lens=run.lens,
            model=run.model,
            events=tuple(run.events),
        )
        snapshot = _extract_observatory_snapshot(temp_run)
        return snapshot.to_dict()

    return {"error": "Run not found", "run_id": run_id}


@router.post("/run/stop")
async def stop_run(request: StopRunRequest) -> RunCancelResponse:
    """Stop a run."""
    return RunCancelResponse(status="stopped")


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
    from sunwell.agent.utils.budget import AdaptiveBudget
    from sunwell.foundation.config import get_config
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        ProjectValidationError,
        resolve_project,
    )
    from sunwell.tools.execution import ToolExecutor
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.knowledge.workspace import default_workspace_root

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

    from sunwell.interface.cli.helpers import resolve_model

    try:
        synthesis_model = resolve_model(provider, model_name)
    except Exception as e:
        yield {"type": "error", "data": {"message": f"Failed to load model: {e}"}}
        return

    if not synthesis_model:
        yield {"type": "error", "data": {"message": "No model available"}}
        return

    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
    )
    
    # Ensure we have a project (create from workspace if resolve failed)
    if project is None:
        try:
            project = create_project_from_workspace(workspace)
        except Exception:
            # If workspace validation fails, we can't create tool executor
            yield {"type": "error", "data": {"message": "Invalid workspace"}}
            return
    
    trust_level = ToolTrust.from_string(run.trust)
    tool_executor = ToolExecutor(
        project=project,
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

    # Mark complete and persist to RunStore
    _run_manager.complete_run(run.run_id)


def _create_default_workspace(goal: str, default_root: Path) -> Path:
    """Create a workspace in the default location based on goal.

    Args:
        goal: User's goal text (used to derive project name)
        default_root: Default workspace root (e.g., ~/Sunwell/projects/)

    Returns:
        Path to created workspace
    """
    import time

    # Extract a name from the goal
    # Take first few words, remove special chars
    words = _RE_NON_WORD.sub("", goal.lower()).split()[:3]
    name = "-".join(words) if words else "project"

    # Ensure unique name
    workspace = default_root / name
    if workspace.exists():
        workspace = default_root / f"{name}-{int(time.time()) % 10000}"

    # Create the directory
    workspace.mkdir(parents=True, exist_ok=True)

    return workspace
