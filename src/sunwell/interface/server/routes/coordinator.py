"""Parallel worker coordination routes (RFC-100)."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from sunwell.interface.server.routes.models import (
    CamelModel,
    CoordinatorConflict,
    CoordinatorStateResponse,
    CoordinatorWorker,
    StateDagResponse,
    WorkerActionResponse,
    WorkerStartResponse,
)

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
async def get_coordinator_state(path: str) -> CoordinatorStateResponse:
    """Get coordinator state for UI."""
    from sunwell.agent.parallel.config import MultiInstanceConfig
    from sunwell.agent.parallel.coordinator import Coordinator

    project_path = Path(path).expanduser().resolve()
    if not project_path.exists():
        return CoordinatorStateResponse(
            workers=[],
            conflicts=[],
            total_progress=0.0,
            merged_branches=[],
            pending_merges=[],
            is_running=False,
            started_at=None,
            last_update=datetime.now().isoformat(),
            error="Project path does not exist",
        )

    try:
        coordinator = Coordinator(project_path, config=MultiInstanceConfig())
        ui_state = await coordinator.get_ui_state()

        workers = [
            CoordinatorWorker(
                id=w.worker_id,
                goal=w.current_goal_id or "",
                status=w.state.value,
                progress=0,
                current_file=None,
                branch=w.branch,
                goals_completed=w.goals_completed,
                goals_failed=w.goals_failed,
                last_heartbeat=w.last_heartbeat.isoformat(),
            )
            for w in ui_state.workers
        ]
        conflicts = [
            CoordinatorConflict(
                path=c.path,
                worker_a=c.worker_a,
                worker_b=c.worker_b,
                conflict_type=c.conflict_type,
                resolution=c.resolution,
                detected_at=c.detected_at.isoformat() if c.detected_at else None,
            )
            for c in ui_state.conflicts
        ]

        return CoordinatorStateResponse(
            workers=workers,
            conflicts=conflicts,
            total_progress=ui_state.total_progress,
            merged_branches=[],
            pending_merges=[],
            is_running=ui_state.is_running,
            started_at=None,
            last_update=datetime.now().isoformat(),
        )
    except Exception as e:
        return CoordinatorStateResponse(
            workers=[],
            conflicts=[],
            total_progress=0.0,
            merged_branches=[],
            pending_merges=[],
            is_running=False,
            started_at=None,
            last_update=datetime.now().isoformat(),
            error=str(e),
        )


@router.post("/start-workers")
async def start_workers(request: StartWorkersRequest) -> WorkerStartResponse:
    """Start parallel workers."""
    import asyncio

    from sunwell.agent.parallel.config import MultiInstanceConfig
    from sunwell.agent.parallel.coordinator import Coordinator

    project_path = Path(request.project_path).expanduser().resolve()
    if not project_path.exists():
        return WorkerStartResponse(status="error", error="Project path does not exist")

    try:
        config = MultiInstanceConfig(
            num_workers=request.num_workers,
            dry_run=request.dry_run,
        )
        coordinator = Coordinator(project_path, config=config)

        asyncio.create_task(coordinator.execute())

        return WorkerStartResponse(status="started", num_workers=request.num_workers)
    except Exception as e:
        return WorkerStartResponse(status="error", error=str(e))


@router.post("/pause-worker")
async def pause_worker(request: PauseWorkerRequest) -> WorkerActionResponse:
    """Pause a specific worker."""
    workers_dir = Path(request.project_path) / ".sunwell" / "workers"
    pause_file = workers_dir / f"worker-{request.worker_id}.pause"
    pause_file.parent.mkdir(parents=True, exist_ok=True)
    pause_file.touch()
    return WorkerActionResponse(status="paused", worker_id=request.worker_id)


@router.post("/resume-worker")
async def resume_worker(request: PauseWorkerRequest) -> WorkerActionResponse:
    """Resume a paused worker."""
    workers_dir = Path(request.project_path) / ".sunwell" / "workers"
    pause_file = workers_dir / f"worker-{request.worker_id}.pause"
    if pause_file.exists():
        pause_file.unlink()
    return WorkerActionResponse(status="resumed", worker_id=request.worker_id)


@router.get("/state-dag")
async def get_coordinator_state_dag(path: str) -> StateDagResponse:
    """Get State DAG for brownfield scanning."""
    try:
        from sunwell.knowledge import StateDagBuilder

        project_path = Path(path).expanduser().resolve()
        if not project_path.exists():
            return StateDagResponse(
                root=None,
                scanned_at=None,
                lens_name=None,
                overall_health=0.0,
                node_count=0,
                edge_count=0,
                unhealthy_count=0,
                critical_count=0,
                nodes=[],
                edges=[],
                metadata={},
                error="Project path does not exist",
            )

        builder = StateDagBuilder(project_path)
        dag = await builder.build()

        return StateDagResponse(
            root=str(dag.root) if hasattr(dag, "root") else str(project_path),
            scanned_at=datetime.now().isoformat(),
            lens_name=None,
            overall_health=getattr(dag, "overall_health", 1.0),
            node_count=len(getattr(dag, "nodes", [])),
            edge_count=len(getattr(dag, "edges", [])),
            unhealthy_count=0,
            critical_count=0,
            nodes=[],
            edges=[],
            metadata={},
        )
    except ImportError:
        return StateDagResponse(
            root=None,
            scanned_at=None,
            lens_name=None,
            overall_health=1.0,
            node_count=0,
            edge_count=0,
            unhealthy_count=0,
            critical_count=0,
            nodes=[],
            edges=[],
            metadata={},
        )
    except Exception as e:
        return StateDagResponse(
            root=None,
            scanned_at=None,
            lens_name=None,
            overall_health=0.0,
            node_count=0,
            edge_count=0,
            unhealthy_count=0,
            critical_count=0,
            nodes=[],
            edges=[],
            metadata={},
            error=str(e),
        )
