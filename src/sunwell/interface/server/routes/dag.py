"""DAG operations routes (RFC-105)."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/dag", tags=["dag"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class RefreshWorkspaceDagRequest(BaseModel):
    path: str


class DagAppendRequest(BaseModel):
    path: str
    goal: dict[str, Any]


class DagExecuteRequest(BaseModel):
    path: str
    node_id: str


# ═══════════════════════════════════════════════════════════════
# DAG ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("")
async def get_dag(path: str) -> dict[str, Any]:
    """Get DAG for a project."""
    return {"nodes": [], "edges": [], "metadata": {}}


@router.get("/index")
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


@router.get("/goal/{goal_id}")
async def get_dag_goal(goal_id: str, path: str) -> dict[str, Any] | None:
    """Get a specific goal node from the DAG."""
    return None


@router.get("/workspace")
async def get_workspace_dag(path: str) -> dict[str, Any]:
    """Get workspace-level DAG index."""
    return {
        "workspace_path": path,
        "projects": [],
        "total_projects": 0,
    }


@router.post("/workspace/refresh")
async def refresh_workspace_dag(request: RefreshWorkspaceDagRequest) -> dict[str, Any]:
    """Refresh workspace DAG index."""
    return {
        "workspace_path": request.path,
        "projects": [],
        "total_projects": 0,
    }


@router.get("/environment")
async def get_environment_dag() -> dict[str, Any]:
    """Get environment-level DAG."""
    return {
        "workspaces": [],
        "total_workspaces": 0,
    }


@router.get("/plan")
async def get_dag_plan(path: str) -> dict[str, Any]:
    """Get incremental execution plan for a DAG."""
    return {"toExecute": [], "toSkip": [], "reason": "No cached state"}


@router.post("/append")
async def append_goal_to_dag(request: DagAppendRequest) -> dict[str, Any]:
    """Append a completed goal to the DAG."""
    return {"status": "appended"}


@router.post("/execute")
async def execute_dag_node(request: DagExecuteRequest) -> dict[str, Any]:
    """Execute a DAG node."""
    return {"status": "started", "node_id": request.node_id}
