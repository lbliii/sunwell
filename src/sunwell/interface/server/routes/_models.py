"""Shared Pydantic models for API routes.

All response models inherit from CamelModel which automatically converts
snake_case Python fields to camelCase in JSON responses.

Run `python scripts/generate_api_types.py` to generate TypeScript types.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


def _to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """Base model with camelCase JSON serialization."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


# ═══════════════════════════════════════════════════════════════
# MEMORY RESPONSE MODELS (RFC-013, RFC-014, RFC-084)
# ═══════════════════════════════════════════════════════════════


class MemoryStatsResponse(CamelModel):
    """Memory statistics for a project."""

    session_id: str | None
    hot_turns: int
    warm_files: int
    warm_size_mb: float
    cold_files: int
    cold_size_mb: float
    total_turns: int
    branches: int
    dead_ends: int
    learnings: int
    concept_edges: int


class MemoryResponse(CamelModel):
    """Current session memory state."""

    learnings: list[dict[str, str | int | float]]
    dead_ends: list[dict[str, str | int | float]]
    session_count: int
    error: str | None = None


class MemoryCheckpointResponse(CamelModel):
    """Result of memory checkpoint save."""

    status: str
    error: str | None = None


class HotChunkItem(CamelModel):
    """A hot tier memory chunk item."""

    id: str
    type: str
    timestamp: str | None = None
    content_preview: str
    session: str


class WarmChunkItem(CamelModel):
    """A warm tier memory shard."""

    date: str
    file: str
    turn_count: int


class ColdChunkItem(CamelModel):
    """A cold tier memory archive."""

    date: str
    file: str
    compressed: bool
    size_bytes: int


class MemoryChunksResponse(CamelModel):
    """Memory chunks organized by tier."""

    hot: list[HotChunkItem]
    warm: list[WarmChunkItem]
    cold: list[ColdChunkItem]
    message: str | None = None
    error: str | None = None


class MemoryGraphNode(CamelModel):
    """A node in the memory graph."""

    id: str
    type: str
    timestamp: str | None = None
    content_preview: str | None = None
    is_dead_end: bool = False
    is_head: bool = False
    tags: list[str] | None = None
    # Learning-specific fields
    fact: str | None = None
    confidence: float | None = None
    category: str | None = None


class MemoryGraphEdge(CamelModel):
    """An edge in the memory graph."""

    source: str
    target: str
    type: str


class MemoryGraphStats(CamelModel):
    """Statistics for the memory graph."""

    total_nodes: int
    total_edges: int
    turn_count: int
    learning_count: int


class MemoryGraphResponse(CamelModel):
    """Memory graph structure."""

    nodes: list[MemoryGraphNode]
    edges: list[MemoryGraphEdge]
    stats: MemoryGraphStats | None = None
    message: str | None = None
    error: str | None = None


# ═══════════════════════════════════════════════════════════════
# SESSION RESPONSE MODELS (RFC-120)
# ═══════════════════════════════════════════════════════════════


class SessionSummaryResponse(CamelModel):
    """Session activity summary."""

    session_id: str
    started_at: str
    goals_completed: int
    goals_started: int
    files_modified: int
    files_created: int
    total_duration_seconds: float
    error: str | None = None


class SessionHistoryItem(CamelModel):
    """A session in the history list."""

    session_id: str
    started_at: str
    goals_completed: int
    goals_started: int
    files_modified: int
    total_duration_seconds: float


class SessionHistoryResponse(CamelModel):
    """List of recent sessions."""

    sessions: list[SessionHistoryItem]
    count: int


# ═══════════════════════════════════════════════════════════════
# PLAN VERSIONING RESPONSE MODELS (RFC-120)
# ═══════════════════════════════════════════════════════════════


class PlanVersionsResponse(CamelModel):
    """Plan version history."""

    plan_id: str
    versions: list[dict[str, str | int | float]]
    count: int


class RecentPlanItem(CamelModel):
    """A plan in the recent plans list."""

    plan_id: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    version_count: int
    progress_percent: float


class RecentPlansResponse(CamelModel):
    """List of recent plans."""

    plans: list[RecentPlanItem]
    count: int


# ═══════════════════════════════════════════════════════════════
# PROJECT RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class ProjectLearningsResponse(CamelModel):
    """Project learnings from memory and checkpoints."""

    original_goal: str | None
    decisions: list[str]
    failures: list[str]
    completed_tasks: list[str]
    pending_tasks: list[str]


# ═══════════════════════════════════════════════════════════════
# BRIEFING RESPONSE MODELS (RFC-071)
# ═══════════════════════════════════════════════════════════════

BriefingStatus = Literal["not_started", "in_progress", "blocked", "complete"]


class BriefingResponse(CamelModel):
    """Briefing state for a project."""

    mission: str
    status: BriefingStatus
    progress: str
    last_action: str
    next_action: str | None = None
    hazards: list[str]
    blockers: list[str]
    hot_files: list[str]
    goal_hash: str | None = None
    related_learnings: list[str]

    # Dispatch hints (optional)
    predicted_skills: list[str] | None = None
    suggested_lens: str | None = None
    complexity_estimate: str | None = None
    estimated_files_touched: int | None = None

    # Metadata
    updated_at: str
    session_id: str


class BriefingExistsResponse(CamelModel):
    """Whether briefing exists."""

    exists: bool


class BriefingClearResponse(CamelModel):
    """Result of clearing briefing."""

    success: bool
    message: str | None = None


# ═══════════════════════════════════════════════════════════════
# PROMPTS RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class SavedPromptItem(CamelModel):
    """A saved prompt."""

    text: str
    last_used: int


class SavedPromptsResponse(CamelModel):
    """List of saved prompts."""

    prompts: list[SavedPromptItem]


class PromptActionResponse(CamelModel):
    """Result of prompt save/remove action."""

    status: str
    total: int


# ═══════════════════════════════════════════════════════════════
# INDEXING RESPONSE MODELS (RFC-108)
# ═══════════════════════════════════════════════════════════════

IndexChunkType = Literal["function", "class", "module", "block", "prose", "scene"]


class IndexChunk(CamelModel):
    """A chunk from the index search."""

    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_type: IndexChunkType
    name: str | None = None
    score: float


class IndexQueryResponse(CamelModel):
    """Result of an index query."""

    chunks: list[IndexChunk]
    fallback_used: bool
    query_time_ms: int
    total_chunks_searched: int
    error: str | None = None


# ═══════════════════════════════════════════════════════════════
# WRITER RESPONSE MODELS (RFC-086)
# ═══════════════════════════════════════════════════════════════

ValidationSeverity = Literal["warning", "error", "info"]


class ValidationWarning(CamelModel):
    """A validation warning for a document."""

    line: int
    column: int | None = None
    message: str
    rule: str
    severity: ValidationSeverity
    suggestion: str | None = None


class ValidationResponse(CamelModel):
    """Result of document validation."""

    warnings: list[ValidationWarning]


class FixAllResponse(CamelModel):
    """Result of fixing all issues."""

    content: str
    fixed: int


# ═══════════════════════════════════════════════════════════════
# DAG RESPONSE MODELS (RFC-105)
# ═══════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════
# COMMON RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class SuccessResponse(CamelModel):
    """Generic success response."""

    success: bool
    message: str | None = None


class ErrorResponse(CamelModel):
    """Generic error response."""

    error: str
    message: str | None = None
