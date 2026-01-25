"""Memory and session tracking routes (RFC-084, RFC-120)."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from sunwell.planning.naaru.persistence import PlanStore
from sunwell.memory.session.tracker import SessionTracker
from sunwell.memory.simulacrum import SimulacrumStore

router = APIRouter(prefix="/api", tags=["memory"])


# ═══════════════════════════════════════════════════════════════
# MEMORY ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("/memory")
async def get_memory() -> dict[str, Any]:
    """Get current session memory (Simulacrum)."""
    try:
        store = SimulacrumStore.load_or_create(Path.cwd())
        return {
            "learnings": [learning.to_dict() for learning in store.learnings],
            "dead_ends": [dead_end.to_dict() for dead_end in store.dead_ends],
            "session_count": store.session_count,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/memory/checkpoint")
async def checkpoint_memory() -> dict[str, Any]:
    """Save memory checkpoint."""
    try:
        store = SimulacrumStore.load_or_create(Path.cwd())
        store.save()
        return {"status": "saved"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/memory/chunks")
async def get_memory_chunks(path: str) -> dict[str, Any]:
    """Get chunk hierarchy for a project."""
    return {"hot": [], "warm": [], "cold": []}


@router.get("/memory/graph")
async def get_memory_graph(path: str) -> dict[str, Any]:
    """Get concept graph for a project."""
    return {"edges": []}


# ═══════════════════════════════════════════════════════════════
# SESSION SUMMARY (RFC-120)
# ═══════════════════════════════════════════════════════════════


@router.get("/session/summary")
async def get_session_summary(session_id: str | None = None) -> dict[str, Any]:
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
            return {"error": f"Session {session_id} not found"}

        tracker = SessionTracker.load(session_path)
    else:
        recent = SessionTracker.list_recent(limit=1)
        if recent:
            tracker = SessionTracker.load(recent[0])
        else:
            return {"error": "No session data available"}

    return tracker.get_summary().to_dict()


@router.get("/session/history")
async def get_session_history(limit: int = 10) -> dict[str, Any]:
    """Get list of recent sessions."""
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


@router.get("/plans/{plan_id}/versions")
async def get_plan_versions(plan_id: str) -> dict[str, Any]:
    """Get all versions of a plan."""
    store = PlanStore()
    versions = store.get_versions(plan_id)

    return {
        "plan_id": plan_id,
        "versions": [v.to_dict() for v in versions],
        "count": len(versions),
    }


@router.get("/plans/{plan_id}/versions/{version}")
async def get_plan_version(plan_id: str, version: int) -> dict[str, Any]:
    """Get a specific version of a plan."""
    store = PlanStore()
    v = store.get_version(plan_id, version)

    if not v:
        return {"error": f"Version {version} not found for plan {plan_id}"}

    return v.to_dict()


@router.get("/plans/{plan_id}/diff")
async def get_plan_diff(plan_id: str, v1: int, v2: int) -> dict[str, Any]:
    """Get diff between two plan versions."""
    store = PlanStore()
    diff = store.diff(plan_id, v1, v2)

    if not diff:
        return {"error": f"Could not compute diff for plan {plan_id}"}

    return diff.to_dict()


@router.get("/plans/recent")
async def get_recent_plans(limit: int = 20) -> dict[str, Any]:
    """Get recent plans with version info."""
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
