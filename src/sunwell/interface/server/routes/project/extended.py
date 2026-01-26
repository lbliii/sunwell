"""Extended project operations: memory stats, intelligence, DAG, learnings."""

import json

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes.models import (
    DagEdge,
    DagMetadata,
    DagNode,
    DagResponse,
    MemoryStatsResponse,
    ProjectIntelligenceResponse,
    ProjectLearningsResponse,
)

router = APIRouter(prefix="/project", tags=["project"])


@router.get("/learnings")
async def get_project_learnings(path: str) -> ProjectLearningsResponse:
    """Get project learnings from memory and checkpoints.

    Returns accumulated knowledge: learnings, dead ends, completed/pending tasks.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    project_path = normalize_path(path)
    simulacrum_path = project_path / ".sunwell" / "simulacrum"
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"

    original_goal: str | None = None
    decisions: list[str] = []
    failures: list[str] = []
    completed_tasks: list[str] = []
    pending_tasks: list[str] = []

    # Get latest checkpoint for goal and tasks
    if checkpoint_dir.exists():
        try:
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                original_goal = latest.goal
                for task in latest.tasks:
                    task_desc = (
                        task.description if hasattr(task, "description") else str(task)
                    )
                    if task.id in latest.completed_ids:
                        completed_tasks.append(task_desc)
                    else:
                        pending_tasks.append(task_desc)
        except Exception:
            pass

    # Load learnings from simulacrum DAG
    if simulacrum_path.exists():
        hot_path = simulacrum_path / "hot"
        if hot_path.exists():
            for session_file in hot_path.glob("*.json"):
                try:
                    with open(session_file) as f:
                        data = json.load(f)
                        learnings_data = data.get("learnings", {})
                        dead_ends = set(data.get("dead_ends", []))

                        # Extract learnings as decisions
                        for learning_id, learning in learnings_data.items():
                            fact = learning.get("fact", "")
                            category = learning.get("category", "general")
                            confidence = learning.get("confidence", 0)

                            if category == "decision" or "decided" in fact.lower():
                                decisions.append(fact)
                            elif confidence > 0.5:
                                decisions.append(f"[{category}] {fact}")

                        # Extract dead ends as failures
                        turns = data.get("turns", {})
                        for turn_id in dead_ends:
                            if turn_id in turns:
                                content = turns[turn_id].get("content", "")[:200]
                                failures.append(f"Dead end: {content}...")
                except Exception:
                    continue

    return ProjectLearningsResponse(
        original_goal=original_goal,
        decisions=decisions[:20],  # Limit for performance
        failures=failures[:10],
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
    )


@router.get("/dag")
async def get_project_dag(path: str) -> DagResponse:
    """Get project DAG from checkpoints and plans.

    Delegates to the DAG routes for full implementation.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    project_path = normalize_path(path)
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"

    nodes: list[DagNode] = []
    edges: list[DagEdge] = []
    latest_checkpoint: str | None = None

    if checkpoint_dir.exists():
        try:
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                latest_checkpoint = latest.checkpoint_at.isoformat()
                # Add goal node
                nodes.append(
                    DagNode(
                        id="goal",
                        type="goal",
                        label=latest.goal[:50],
                        status=latest.phase.value,
                    )
                )

                # Add task nodes
                for i, task in enumerate(latest.tasks):
                    task_id = task.id if hasattr(task, "id") else f"task-{i}"
                    is_complete = task_id in latest.completed_ids
                    nodes.append(
                        DagNode(
                            id=task_id,
                            type="task",
                            label=(
                                task.description[:50]
                                if hasattr(task, "description")
                                else str(task)[:50]
                            ),
                            status="complete" if is_complete else "pending",
                        )
                    )
                    edges.append(
                        DagEdge(
                            source="goal",
                            target=task_id,
                            type="contains",
                        )
                    )
        except Exception:
            pass

    return DagResponse(
        nodes=nodes,
        edges=edges,
        metadata=DagMetadata(
            path=str(project_path), latest_checkpoint=latest_checkpoint
        ),
    )


@router.get("/memory/stats")
async def get_project_memory_stats(path: str) -> MemoryStatsResponse:
    """Get project memory statistics.

    Returns MemoryStatsResponse with automatic camelCase conversion.
    """
    project_path = normalize_path(path)
    simulacrum_path = project_path / ".sunwell" / "simulacrum"

    total_learnings = 0
    total_dead_ends = 0
    hot_turns = 0
    warm_files = 0
    warm_size_bytes = 0
    cold_files = 0
    cold_size_bytes = 0
    branches = 0
    concept_edges = 0
    session_id: str | None = None

    if not simulacrum_path.exists():
        return MemoryStatsResponse(
            session_id=None,
            hot_turns=0,
            warm_files=0,
            warm_size_mb=0,
            cold_files=0,
            cold_size_mb=0,
            total_turns=0,
            branches=0,
            dead_ends=0,
            learnings=0,
            concept_edges=0,
        )

    try:
        # Count sessions from hot path
        hot_path = simulacrum_path / "hot"
        warm_path = simulacrum_path / "warm"
        cold_path = simulacrum_path / "cold"

        if hot_path.exists():
            session_files = list(hot_path.glob("*.json"))

            # Get stats from each session
            for session_file in session_files:
                try:
                    with open(session_file) as f:
                        data = json.load(f)
                        total_learnings += len(data.get("learnings", {}))
                        total_dead_ends += len(data.get("dead_ends", []))
                        hot_turns += len(data.get("turns", {}))
                        branches += len(data.get("branch_points", []))
                        session_id = data.get("session_id", session_file.stem)
                except Exception:
                    continue

        if warm_path.exists():
            warm_file_list = list(warm_path.glob("*.jsonl"))
            warm_files = len(warm_file_list)
            warm_size_bytes = sum(f.stat().st_size for f in warm_file_list)

        if cold_path.exists():
            cold_file_list = list(cold_path.glob("*"))
            cold_files = len(cold_file_list)
            cold_size_bytes = sum(f.stat().st_size for f in cold_file_list)

        return MemoryStatsResponse(
            session_id=session_id,
            hot_turns=hot_turns,
            warm_files=warm_files,
            warm_size_mb=round(warm_size_bytes / 1024 / 1024, 2),
            cold_files=cold_files,
            cold_size_mb=round(cold_size_bytes / 1024 / 1024, 2),
            total_turns=hot_turns,
            branches=branches,
            dead_ends=total_dead_ends,
            learnings=total_learnings,
            concept_edges=concept_edges,
        )
    except Exception:
        return MemoryStatsResponse(
            session_id=None,
            hot_turns=0,
            warm_files=0,
            warm_size_mb=0,
            cold_files=0,
            cold_size_mb=0,
            total_turns=0,
            branches=0,
            dead_ends=0,
            learnings=0,
            concept_edges=0,
        )


@router.get("/intelligence")
async def get_project_intelligence(path: str) -> ProjectIntelligenceResponse:
    """Get project intelligence data."""
    return ProjectIntelligenceResponse(
        signals=[],
        context_quality=1.0,
    )
