"""Memory and session tracking routes (RFC-084, RFC-120)."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from sunwell.interface.server.routes._models import (
    ColdChunkItem,
    HotChunkItem,
    MemoryCheckpointResponse,
    MemoryChunksResponse,
    MemoryGraphEdge,
    MemoryGraphNode,
    MemoryGraphResponse,
    MemoryGraphStats,
    MemoryResponse,
    PlanVersionsResponse,
    RecentPlanItem,
    RecentPlansResponse,
    SessionHistoryItem,
    SessionHistoryResponse,
    SessionSummaryResponse,
    WarmChunkItem,
)
from sunwell.memory.session.tracker import SessionTracker
from sunwell.memory.simulacrum import SimulacrumStore
from sunwell.planning.naaru.persistence import PlanStore

router = APIRouter(prefix="/api", tags=["memory"])


# ═══════════════════════════════════════════════════════════════
# MEMORY ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("/memory")
async def get_memory() -> MemoryResponse:
    """Get current session memory (Simulacrum)."""
    try:
        store = SimulacrumStore.load_or_create(Path.cwd())
        return MemoryResponse(
            learnings=[learning.to_dict() for learning in store.learnings],
            dead_ends=[dead_end.to_dict() for dead_end in store.dead_ends],
            session_count=store.session_count,
        )
    except Exception as e:
        return MemoryResponse(learnings=[], dead_ends=[], session_count=0, error=str(e))


@router.post("/memory/checkpoint")
async def checkpoint_memory() -> MemoryCheckpointResponse:
    """Save memory checkpoint."""
    try:
        store = SimulacrumStore.load_or_create(Path.cwd())
        store.save()
        return MemoryCheckpointResponse(status="saved")
    except Exception as e:
        return MemoryCheckpointResponse(status="error", error=str(e))


@router.get("/memory/chunks")
async def get_memory_chunks(path: str) -> MemoryChunksResponse:
    """Get chunk hierarchy for a project's memory storage.

    Returns hot (in-memory), warm (disk), and cold (archived) tier data.
    """
    import json

    project_path = Path(path).expanduser().resolve()
    simulacrum_path = project_path / ".sunwell" / "simulacrum"

    if not simulacrum_path.exists():
        return MemoryChunksResponse(hot=[], warm=[], cold=[], message="No memory data found")

    hot_items: list[HotChunkItem] = []
    warm_items: list[WarmChunkItem] = []
    cold_items: list[ColdChunkItem] = []

    try:
        # Hot tier: recent turns in memory (from hot/*.json files)
        hot_path = simulacrum_path / "hot"
        if hot_path.exists():
            for session_file in hot_path.glob("*.json"):
                try:
                    with open(session_file) as f:
                        data = json.load(f)
                        turns = data.get("turns", {})
                        for turn_id, turn_data in list(turns.items())[-20:]:  # Last 20
                            hot_items.append(HotChunkItem(
                                id=turn_id,
                                type=turn_data.get("turn_type", "unknown"),
                                timestamp=turn_data.get("timestamp"),
                                content_preview=turn_data.get("content", "")[:100],
                                session=session_file.stem,
                            ))
                except Exception:
                    continue

        # Warm tier: date-sharded JSONL files
        warm_path = simulacrum_path / "warm"
        if warm_path.exists():
            for shard_file in sorted(warm_path.glob("*.jsonl"), reverse=True)[:10]:
                try:
                    line_count = sum(1 for _ in open(shard_file))
                    warm_items.append(WarmChunkItem(
                        date=shard_file.stem,
                        file=str(shard_file),
                        turn_count=line_count,
                    ))
                except Exception:
                    continue

        # Cold tier: compressed archives
        cold_path = simulacrum_path / "cold"
        if cold_path.exists():
            for archive in sorted(cold_path.glob("*.jsonl*"), reverse=True)[:10]:
                cold_items.append(ColdChunkItem(
                    date=archive.stem.split(".")[0],
                    file=str(archive),
                    compressed=archive.suffix in (".gz", ".zst"),
                    size_bytes=archive.stat().st_size,
                ))

        return MemoryChunksResponse(hot=hot_items, warm=warm_items, cold=cold_items)
    except Exception as e:
        return MemoryChunksResponse(hot=[], warm=[], cold=[], error=str(e))


@router.get("/memory/graph")
async def get_memory_graph(path: str) -> MemoryGraphResponse:
    """Get conversation graph structure for a project.

    Returns nodes (turns) and edges (parent-child relationships) from the DAG.
    """
    import json

    project_path = Path(path).expanduser().resolve()
    simulacrum_path = project_path / ".sunwell" / "simulacrum"

    if not simulacrum_path.exists():
        return MemoryGraphResponse(nodes=[], edges=[], message="No memory data found")

    nodes: list[MemoryGraphNode] = []
    edges: list[MemoryGraphEdge] = []

    try:
        # Load from hot tier session files
        hot_path = simulacrum_path / "hot"
        if hot_path.exists():
            for session_file in hot_path.glob("*.json"):
                try:
                    with open(session_file) as f:
                        data = json.load(f)
                        turns = data.get("turns", {})
                        learnings = data.get("learnings", {})
                        dead_ends = set(data.get("dead_ends", []))
                        heads = set(data.get("heads", []))

                        # Build nodes from turns
                        for turn_id, turn_data in turns.items():
                            nodes.append(MemoryGraphNode(
                                id=turn_id,
                                type=turn_data.get("turn_type", "unknown"),
                                timestamp=turn_data.get("timestamp"),
                                content_preview=turn_data.get("content", "")[:50],
                                is_dead_end=turn_id in dead_ends,
                                is_head=turn_id in heads,
                                tags=turn_data.get("tags", []),
                            ))

                            # Build edges from parent_ids
                            for parent_id in turn_data.get("parent_ids", []):
                                edges.append(MemoryGraphEdge(
                                    source=parent_id,
                                    target=turn_id,
                                    type="follows",
                                ))

                        # Add learning nodes
                        for learning_id, learning_data in learnings.items():
                            nodes.append(MemoryGraphNode(
                                id=learning_id,
                                type="learning",
                                fact=learning_data.get("fact", "")[:100],
                                confidence=learning_data.get("confidence", 0),
                                category=learning_data.get("category", "general"),
                            ))

                            # Connect learnings to source turns
                            for source_turn in learning_data.get("source_turns", []):
                                edges.append(MemoryGraphEdge(
                                    source=source_turn,
                                    target=learning_id,
                                    type="produces_learning",
                                ))
                except Exception:
                    continue

        turn_count = len([n for n in nodes if n.type != "learning"])
        learning_count = len([n for n in nodes if n.type == "learning"])

        return MemoryGraphResponse(
            nodes=nodes,
            edges=edges,
            stats=MemoryGraphStats(
                total_nodes=len(nodes),
                total_edges=len(edges),
                turn_count=turn_count,
                learning_count=learning_count,
            ),
        )
    except Exception as e:
        return MemoryGraphResponse(nodes=[], edges=[], error=str(e))


# ═══════════════════════════════════════════════════════════════
# SESSION SUMMARY (RFC-120)
# ═══════════════════════════════════════════════════════════════


@router.get("/session/summary")
async def get_session_summary(session_id: str | None = None) -> SessionSummaryResponse:
    """Get session activity summary.

    Returns current session summary or specific session by ID.
    """
    if session_id:
        recent = SessionTracker.list_recent(limit=100)
        session_path = None
        for p in recent:
            if session_id in p.stem:
                session_path = p
                break

        if not session_path:
            return SessionSummaryResponse(
                session_id="",
                started_at="",
                goals_completed=0,
                goals_started=0,
                files_modified=0,
                files_created=0,
                total_duration_seconds=0,
                error=f"Session {session_id} not found",
            )

        tracker = SessionTracker.load(session_path)
    else:
        recent = SessionTracker.list_recent(limit=1)
        if recent:
            tracker = SessionTracker.load(recent[0])
        else:
            return SessionSummaryResponse(
                session_id="",
                started_at="",
                goals_completed=0,
                goals_started=0,
                files_modified=0,
                files_created=0,
                total_duration_seconds=0,
                error="No session data available",
            )

    summary = tracker.get_summary()
    return SessionSummaryResponse(
        session_id=summary.session_id,
        started_at=summary.started_at.isoformat(),
        goals_completed=summary.goals_completed,
        goals_started=summary.goals_started,
        files_modified=summary.files_modified,
        files_created=summary.files_created,
        total_duration_seconds=summary.total_duration_seconds,
    )


@router.get("/session/history")
async def get_session_history(limit: int = 10) -> SessionHistoryResponse:
    """Get list of recent sessions."""
    recent = SessionTracker.list_recent(limit=limit)

    sessions: list[SessionHistoryItem] = []
    for path in recent:
        try:
            tracker = SessionTracker.load(path)
            summary = tracker.get_summary()
            sessions.append(SessionHistoryItem(
                session_id=summary.session_id,
                started_at=summary.started_at.isoformat(),
                goals_completed=summary.goals_completed,
                goals_started=summary.goals_started,
                files_modified=summary.files_modified + summary.files_created,
                total_duration_seconds=summary.total_duration_seconds,
            ))
        except Exception:
            continue

    return SessionHistoryResponse(sessions=sessions, count=len(sessions))


# ═══════════════════════════════════════════════════════════════
# PLAN VERSIONING (RFC-120)
# ═══════════════════════════════════════════════════════════════


@router.get("/plans/{plan_id}/versions")
async def get_plan_versions(plan_id: str) -> PlanVersionsResponse:
    """Get all versions of a plan."""
    store = PlanStore()
    versions = store.get_versions(plan_id)

    return PlanVersionsResponse(
        plan_id=plan_id,
        versions=[v.to_dict() for v in versions],
        count=len(versions),
    )


@router.get("/plans/{plan_id}/versions/{version}")
async def get_plan_version(plan_id: str, version: int) -> dict[str, Any]:
    """Get a specific version of a plan.

    Returns the raw version dict (passthrough for flexibility).
    """
    store = PlanStore()
    v = store.get_version(plan_id, version)

    if not v:
        return {"error": f"Version {version} not found for plan {plan_id}"}

    return v.to_dict()


@router.get("/plans/{plan_id}/diff")
async def get_plan_diff(plan_id: str, v1: int, v2: int) -> dict[str, Any]:
    """Get diff between two plan versions.

    Returns the raw diff dict (passthrough for flexibility).
    """
    store = PlanStore()
    diff = store.diff(plan_id, v1, v2)

    if not diff:
        return {"error": f"Could not compute diff for plan {plan_id}"}

    return diff.to_dict()


@router.get("/plans/recent")
async def get_recent_plans(limit: int = 20) -> RecentPlansResponse:
    """Get recent plans with version info."""
    store = PlanStore()
    plans = store.list_recent(limit=limit)

    result: list[RecentPlanItem] = []
    for p in plans:
        versions = store.get_versions(p.goal_hash)
        result.append(RecentPlanItem(
            plan_id=p.goal_hash,
            goal=p.goal,
            status=p.status.value,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
            version_count=len(versions),
            progress_percent=p.progress_percent,
        ))

    return RecentPlansResponse(plans=result, count=len(result))
