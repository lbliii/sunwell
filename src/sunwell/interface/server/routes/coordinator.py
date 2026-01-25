"""Parallel worker coordination routes (RFC-100)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from sunwell.server.routes._models import CamelModel

router = APIRouter(prefix="/api/coordinator", tags=["coordinator"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class StartWorkersRequest(CamelModel):
    project_path: str
    num_workers: int = 4
    dry_run: bool = False


class PauseWorkerRequest(CamelModel):
    project_path: str
    worker_id: int


# ═══════════════════════════════════════════════════════════════
# COORDINATOR ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("/state")
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
                    "progress": 0,
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


@router.post("/start-workers")
async def start_workers(request: StartWorkersRequest) -> dict[str, Any]:
    """Start parallel workers."""
    import asyncio

    from sunwell.parallel.config import MultiInstanceConfig
    from sunwell.parallel.coordinator import Coordinator

    project_path = Path(request.project_path).expanduser().resolve()
    if not project_path.exists():
        return {"error": "Project path does not exist"}

    try:
        config = MultiInstanceConfig(
            num_workers=request.num_workers,
            dry_run=request.dry_run,
        )
        coordinator = Coordinator(project_path, config=config)

        asyncio.create_task(coordinator.execute())

        return {"status": "started", "num_workers": request.num_workers}
    except Exception as e:
        return {"error": str(e)}


@router.post("/pause-worker")
async def pause_worker(request: PauseWorkerRequest) -> dict[str, Any]:
    """Pause a specific worker."""
    workers_dir = Path(request.project_path) / ".sunwell" / "workers"
    pause_file = workers_dir / f"worker-{request.worker_id}.pause"
    pause_file.parent.mkdir(parents=True, exist_ok=True)
    pause_file.touch()
    return {"status": "paused", "worker_id": request.worker_id}


@router.post("/resume-worker")
async def resume_worker(request: PauseWorkerRequest) -> dict[str, Any]:
    """Resume a paused worker."""
    workers_dir = Path(request.project_path) / ".sunwell" / "workers"
    pause_file = workers_dir / f"worker-{request.worker_id}.pause"
    if pause_file.exists():
        pause_file.unlink()
    return {"status": "resumed", "worker_id": request.worker_id}


@router.get("/state-dag")
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
            "root": str(dag.root) if hasattr(dag, "root") else str(project_path),
            "scanned_at": datetime.now().isoformat(),
            "lens_name": None,
            "overall_health": getattr(dag, "overall_health", 1.0),
            "node_count": len(getattr(dag, "nodes", [])),
            "edge_count": len(getattr(dag, "edges", [])),
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
