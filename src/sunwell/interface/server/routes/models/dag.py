"""DAG response models (RFC-105)."""

from __future__ import annotations

from sunwell.interface.server.routes.models.base import CamelModel


class DagCheckpointInfo(CamelModel):
    """Checkpoint information in DAG metadata."""

    goal: str
    phase: str
    tasks_total: int
    tasks_completed: int
    checkpoint_at: str | None = None


class DagMetadata(CamelModel):
    """Metadata for a DAG."""

    path: str | None = None
    checkpoint: dict[str, int | str] | None = None
    latest_checkpoint: DagCheckpointInfo | None = None


class DagNode(CamelModel):
    """A node in the DAG."""

    id: str
    type: str
    label: str
    status: str | None = None
    phase: str | None = None
    progress: float | None = None
    created_at: str | None = None
    parent_plan: str | None = None


class DagEdge(CamelModel):
    """An edge in the DAG."""

    source: str
    target: str
    type: str


class DagResponse(CamelModel):
    """DAG structure response."""

    nodes: list[DagNode]
    edges: list[DagEdge]
    metadata: DagMetadata | None = None


class DagPlanTask(CamelModel):
    """A task in the execution plan."""

    id: str
    description: str


class DagPlanCheckpoint(CamelModel):
    """Checkpoint information in execution plan."""

    goal: str
    phase: str
    checkpoint_at: str


class DagPlanResponse(CamelModel):
    """Incremental execution plan."""

    to_execute: list[DagPlanTask]
    to_skip: list[DagPlanTask]
    reason: str
    checkpoint: DagPlanCheckpoint | None = None


class DagGoalItem(CamelModel):
    """A goal in the DAG index."""

    id: str
    goal: str
    status: str
    progress: float
    created_at: str | None = None
    updated_at: str | None = None
    task_count: int


class DagMilestone(CamelModel):
    """A milestone (completed goal)."""

    id: str
    label: str
    completed_at: str


class DagIndexResponse(CamelModel):
    """DAG index with goals and milestones."""

    project_path: str
    goals: list[DagGoalItem]
    milestones: list[DagMilestone]
    total_goals: int
    completed_goals: int
    in_progress_goals: int


class DagGoalTaskItem(CamelModel):
    """A task within a goal."""

    id: str
    description: str


class DagGoalResponse(CamelModel):
    """A specific goal from the DAG."""

    id: str
    goal: str
    status: str
    progress: float
    created_at: str
    updated_at: str
    tasks: list[DagGoalTaskItem]


class WorkspaceProjectItem(CamelModel):
    """A project in the workspace DAG."""

    id: str
    name: str
    path: str
    goal_count: int
    latest_goal: str | None = None


class WorkspaceDagResponse(CamelModel):
    """Workspace-level DAG response."""

    workspace_path: str
    projects: list[WorkspaceProjectItem]
    total_projects: int


class EnvironmentWorkspace(CamelModel):
    """A workspace in the environment."""

    path: str
    name: str
    project_count: int


class EnvironmentDagResponse(CamelModel):
    """Environment-level DAG response."""

    workspaces: list[EnvironmentWorkspace]
    total_workspaces: int


class DagExecuteResponse(CamelModel):
    """Result of executing a DAG node."""

    status: str
    node_id: str


class DagAppendResponse(CamelModel):
    """Result of appending a goal to the DAG."""

    status: str
