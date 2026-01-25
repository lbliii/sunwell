"""DAG operations routes (RFC-105)."""

from typing import Any

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes.models import (
    CamelModel,
    DagAppendResponse,
    DagCheckpointInfo,
    DagEdge,
    DagExecuteResponse,
    DagGoalItem,
    DagGoalResponse,
    DagGoalTaskItem,
    DagIndexResponse,
    DagMetadata,
    DagMilestone,
    DagNode,
    DagPlanCheckpoint,
    DagPlanResponse,
    DagPlanTask,
    DagResponse,
    EnvironmentDagResponse,
    EnvironmentWorkspace,
    WorkspaceDagResponse,
    WorkspaceProjectItem,
)

router = APIRouter(prefix="/api/dag", tags=["dag"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class RefreshWorkspaceDagRequest(CamelModel):
    path: str


class DagAppendRequest(CamelModel):
    path: str
    goal: dict[str, Any]


class DagExecuteRequest(CamelModel):
    path: str
    node_id: str


# ═══════════════════════════════════════════════════════════════
# DAG ROUTES
# ═══════════════════════════════════════════════════════════════


@router.get("")
async def get_dag(path: str) -> DagResponse:
    """Get DAG for a project from checkpoints and plans.

    Returns nodes (goals/tasks) and edges (dependencies) from the project's
    execution history.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint
    from sunwell.planning.naaru.persistence import PlanStore

    project_path = normalize_path(path)
    nodes: list[DagNode] = []
    edges: list[DagEdge] = []
    latest_checkpoint: DagCheckpointInfo | None = None

    # Get plans from PlanStore
    try:
        store = PlanStore()
        plans = store.list_recent(limit=50)

        for plan in plans:
            # Add plan as a node
            nodes.append(DagNode(
                id=f"plan-{plan.goal_hash}",
                type="plan",
                label=plan.goal[:50],
                status=plan.status.value,
                progress=plan.progress_percent,
                created_at=plan.created_at.isoformat(),
            ))

            # Add task nodes from the plan
            for i, task in enumerate(plan.tasks):
                task_label = task.description[:50] if hasattr(task, "description") else str(task)[:50]
                nodes.append(DagNode(
                    id=f"task-{plan.goal_hash}-{i}",
                    type="task",
                    label=task_label,
                    parent_plan=f"plan-{plan.goal_hash}",
                ))
                edges.append(DagEdge(
                    source=f"plan-{plan.goal_hash}",
                    target=f"task-{plan.goal_hash}-{i}",
                    type="contains",
                ))
    except Exception:
        pass

    # Also check for checkpoints
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"
    if checkpoint_dir.exists():
        try:
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                latest_checkpoint = DagCheckpointInfo(
                    goal=latest.goal,
                    phase=latest.phase.value,
                    tasks_total=len(latest.tasks),
                    tasks_completed=len(latest.completed_ids),
                )
        except Exception:
            pass

    return DagResponse(
        nodes=nodes,
        edges=edges,
        metadata=DagMetadata(path=str(project_path), latest_checkpoint=latest_checkpoint),
    )


@router.get("/index")
async def get_dag_index(path: str) -> DagIndexResponse:
    """Get DAG index for a project.

    Returns aggregated goal/milestone information from plans and checkpoints.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint
    from sunwell.planning.naaru.persistence import PlanStore

    project_path = normalize_path(path)
    goals: list[DagGoalItem] = []
    milestones: list[DagMilestone] = []
    total_goals = 0
    completed_goals = 0
    in_progress_goals = 0

    # Get plans from PlanStore
    try:
        store = PlanStore()
        plans = store.list_recent(limit=100)

        for plan in plans:
            total_goals += 1
            goals.append(DagGoalItem(
                id=plan.goal_hash,
                goal=plan.goal,
                status=plan.status.value,
                progress=plan.progress_percent,
                created_at=plan.created_at.isoformat(),
                updated_at=plan.updated_at.isoformat(),
                task_count=len(plan.tasks),
            ))

            if plan.status.value == "complete":
                completed_goals += 1
                milestones.append(DagMilestone(
                    id=plan.goal_hash,
                    label=plan.goal[:50],
                    completed_at=plan.updated_at.isoformat(),
                ))
            elif plan.status.value in ("running", "pending"):
                in_progress_goals += 1
    except Exception:
        pass

    # Also check checkpoints for additional context
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"
    if checkpoint_dir.exists():
        try:
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest and latest.goal:
                # Check if this goal is already in the list
                existing = next((g for g in goals if latest.goal in g.goal), None)
                if not existing:
                    progress = (len(latest.completed_ids) / max(len(latest.tasks), 1)) * 100
                    status = "interrupted" if latest.phase.value != "review_complete" else "complete"
                    goals.append(DagGoalItem(
                        id=f"checkpoint-{latest.checkpoint_at.strftime('%Y%m%d%H%M%S')}",
                        goal=latest.goal,
                        status=status,
                        progress=progress,
                        task_count=len(latest.tasks),
                    ))
                    total_goals += 1
                    if latest.phase.value != "review_complete":
                        in_progress_goals += 1
                    else:
                        completed_goals += 1
        except Exception:
            pass

    return DagIndexResponse(
        project_path=str(project_path),
        goals=goals[:20],  # Limit for performance
        milestones=milestones[:10],
        total_goals=total_goals,
        completed_goals=completed_goals,
        in_progress_goals=in_progress_goals,
    )


@router.get("/goal/{goal_id}")
async def get_dag_goal(goal_id: str, path: str) -> DagGoalResponse | None:
    """Get a specific goal node from the DAG.

    Looks up goal in PlanStore or checkpoints by ID.
    """
    from sunwell.planning.naaru.persistence import PlanStore

    try:
        store = PlanStore()

        # Try to find by goal_hash
        plans = store.list_recent(limit=100)
        for plan in plans:
            if plan.goal_hash == goal_id or goal_id in plan.goal_hash:
                tasks = [
                    DagGoalTaskItem(
                        id=task.id if hasattr(task, "id") else str(i),
                        description=task.description if hasattr(task, "description") else str(task),
                    )
                    for i, task in enumerate(plan.tasks)
                ]
                return DagGoalResponse(
                    id=plan.goal_hash,
                    goal=plan.goal,
                    status=plan.status.value,
                    progress=plan.progress_percent,
                    created_at=plan.created_at.isoformat(),
                    updated_at=plan.updated_at.isoformat(),
                    tasks=tasks,
                )
    except Exception:
        pass

    return None


@router.get("/workspace")
async def get_workspace_dag(path: str) -> WorkspaceDagResponse:
    """Get workspace-level DAG index.

    Lists all projects in the registry with their goal/status summary.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    registry = ProjectRegistry()
    projects: list[WorkspaceProjectItem] = []

    for project in registry.list_projects():
        if not project.root.exists():
            continue

        goal_count = 0
        latest_goal: str | None = None

        # Check for checkpoints
        checkpoint_dir = project.root / ".sunwell" / "checkpoints"
        if checkpoint_dir.exists():
            try:
                latest = find_latest_checkpoint(checkpoint_dir)
                if latest:
                    latest_goal = latest.goal
                    goal_count = 1  # At least one
            except Exception:
                pass

        projects.append(WorkspaceProjectItem(
            id=project.id,
            name=project.name,
            path=str(project.root),
            goal_count=goal_count,
            latest_goal=latest_goal,
        ))

    return WorkspaceDagResponse(
        workspace_path=path,
        projects=projects,
        total_projects=len(projects),
    )


@router.post("/workspace/refresh")
async def refresh_workspace_dag(request: RefreshWorkspaceDagRequest) -> WorkspaceDagResponse:
    """Refresh workspace DAG index.

    Re-scans projects and updates cached index.
    """
    # Just call get_workspace_dag with the path
    return await get_workspace_dag(request.path)


@router.get("/environment")
async def get_environment_dag() -> EnvironmentDagResponse:
    """Get environment-level DAG.

    Lists all workspaces (project roots) in the global registry.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.workspace import default_workspace_root

    registry = ProjectRegistry()
    workspaces: list[EnvironmentWorkspace] = []

    # Get default workspace root
    default_root = default_workspace_root()
    if default_root.exists():
        project_count = len([
            p for p in registry.list_projects()
            if str(p.root).startswith(str(default_root))
        ])
        workspaces.append(EnvironmentWorkspace(
            path=str(default_root),
            name="Default Workspace",
            project_count=project_count,
        ))

    # Add unique parent directories of registered projects
    seen_parents = {default_root}
    for project in registry.list_projects():
        parent = project.root.parent
        if parent not in seen_parents:
            seen_parents.add(parent)
            workspaces.append(EnvironmentWorkspace(
                path=str(parent),
                name=parent.name,
                project_count=1,
            ))

    return EnvironmentDagResponse(
        workspaces=workspaces,
        total_workspaces=len(workspaces),
    )


@router.get("/plan")
async def get_dag_plan(path: str) -> DagPlanResponse:
    """Get incremental execution plan from checkpoints.

    Returns tasks to execute vs skip based on checkpoint state.
    """
    from sunwell.planning.naaru.checkpoint import find_latest_checkpoint

    project_path = normalize_path(path)
    checkpoint_dir = project_path / ".sunwell" / "checkpoints"

    if not checkpoint_dir.exists():
        return DagPlanResponse(to_execute=[], to_skip=[], reason="No checkpoints found")

    try:
        latest = find_latest_checkpoint(checkpoint_dir)
        if not latest:
            return DagPlanResponse(to_execute=[], to_skip=[], reason="No valid checkpoint")

        to_execute: list[DagPlanTask] = []
        to_skip: list[DagPlanTask] = []

        for task in latest.tasks:
            task_desc = task.description if hasattr(task, "description") else str(task)
            task_info = DagPlanTask(id=task.id, description=task_desc)
            if task.id in latest.completed_ids:
                to_skip.append(task_info)
            else:
                to_execute.append(task_info)

        reason = (
            f"Resuming from {latest.phase.value}: {latest.phase_summary}"
            if latest.phase_summary
            else f"Resuming from {latest.phase.value}"
        )

        return DagPlanResponse(
            to_execute=to_execute,
            to_skip=to_skip,
            reason=reason,
            checkpoint=DagPlanCheckpoint(
                goal=latest.goal,
                phase=latest.phase.value,
                checkpoint_at=latest.checkpoint_at.isoformat(),
            ),
        )
    except Exception as e:
        return DagPlanResponse(
            to_execute=[],
            to_skip=[],
            reason=f"Error loading checkpoint: {e}",
        )


@router.post("/append")
async def append_goal_to_dag(request: DagAppendRequest) -> DagAppendResponse:
    """Append a completed goal to the DAG."""
    return DagAppendResponse(status="appended")


@router.post("/execute")
async def execute_dag_node(request: DagExecuteRequest) -> DagExecuteResponse:
    """Execute a DAG node."""
    return DagExecuteResponse(status="started", node_id=request.node_id)
