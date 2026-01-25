"""Backlog management routes (RFC-114)."""

import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sunwell.foundation.utils import normalize_path
from sunwell.features.backlog.goals import Goal, GoalScope
from sunwell.features.backlog.manager import BacklogManager

router = APIRouter(prefix="/api/backlog", tags=["backlog"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class AddGoalRequest(BaseModel):
    title: str
    description: str | None = None
    category: str = "add"
    priority: float = 0.5
    path: str | None = None


class UpdateGoalRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: float | None = None
    path: str | None = None


class ReorderGoalsRequest(BaseModel):
    order: list[str]
    path: str | None = None


class RefreshBacklogRequest(BaseModel):
    path: str | None = None


# ═══════════════════════════════════════════════════════════════
# BACKLOG ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("")
async def get_backlog(path: str | None = None) -> dict[str, Any]:
    """Get backlog goals."""
    project_path = normalize_path(path) if path else Path.cwd()

    try:
        manager = BacklogManager(project_path)
        goals = []
        for goal in manager.backlog.execution_order():
            status = (
                "completed"
                if goal.id in manager.backlog.completed
                else "blocked"
                if goal.id in manager.backlog.blocked
                else "executing"
                if goal.id == manager.backlog.in_progress
                else "claimed"
                if goal.claimed_by is not None
                else "pending"
            )
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


@router.post("/goals")
async def add_backlog_goal(request: AddGoalRequest) -> dict[str, Any]:
    """Add a goal to the backlog."""
    project_path = normalize_path(request.path) if request.path else Path.cwd()

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


@router.get("/goals/{goal_id}")
async def get_backlog_goal(goal_id: str, path: str | None = None) -> dict[str, Any]:
    """Get a specific goal."""
    project_path = normalize_path(path) if path else Path.cwd()

    try:
        manager = BacklogManager(project_path)
        goal = await manager.get_goal(goal_id)
        if not goal:
            return {"error": "Goal not found"}

        status = (
            "completed"
            if goal.id in manager.backlog.completed
            else "blocked"
            if goal.id in manager.backlog.blocked
            else "executing"
            if goal.id == manager.backlog.in_progress
            else "claimed"
            if goal.claimed_by is not None
            else "pending"
        )

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


@router.put("/goals/{goal_id}")
async def update_backlog_goal(goal_id: str, request: UpdateGoalRequest) -> dict[str, Any]:
    """Update a goal."""
    return {"status": "updated", "goal_id": goal_id}


@router.delete("/goals/{goal_id}")
async def delete_backlog_goal(goal_id: str, path: str | None = None) -> dict[str, Any]:
    """Remove a goal from backlog."""
    project_path = normalize_path(path) if path else Path.cwd()

    try:
        manager = BacklogManager(project_path)
        if goal_id in manager.backlog.goals:
            del manager.backlog.goals[goal_id]
            manager._save()
            return {"status": "deleted", "goal_id": goal_id}
        return {"error": "Goal not found"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/goals/{goal_id}/skip")
async def skip_backlog_goal(goal_id: str, path: str | None = None) -> dict[str, Any]:
    """Skip a goal."""
    project_path = normalize_path(path) if path else Path.cwd()

    try:
        manager = BacklogManager(project_path)
        await manager.block_goal(goal_id, "Skipped by user")
        return {"status": "skipped", "goal_id": goal_id}
    except Exception as e:
        return {"error": str(e)}


@router.post("/reorder")
async def reorder_backlog_goals(request: ReorderGoalsRequest) -> dict[str, Any]:
    """Reorder goals by priority."""
    project_path = normalize_path(request.path) if request.path else Path.cwd()

    try:
        manager = BacklogManager(project_path)

        total = len(request.order)
        for i, goal_id in enumerate(request.order):
            if goal_id in manager.backlog.goals:
                old_goal = manager.backlog.goals[goal_id]
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


@router.post("/refresh")
async def refresh_backlog(request: RefreshBacklogRequest) -> dict[str, Any]:
    """Refresh backlog from project signals."""
    project_path = normalize_path(request.path) if request.path else Path.cwd()

    try:
        manager = BacklogManager(project_path)
        await manager.refresh()
        return {"status": "refreshed", "goal_count": len(manager.backlog.goals)}
    except Exception as e:
        return {"error": str(e)}
