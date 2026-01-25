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


class ChunkItem(CamelModel):
    """A memory chunk item."""

    id: str
    content: str | None = None
    summary: str | None = None
    token_count: int = 0
    timestamp: str | None = None


class MemoryChunksResponse(CamelModel):
    """Memory chunks organized by tier."""

    hot: list[ChunkItem]
    warm: list[ChunkItem]
    cold: list[ChunkItem]
    message: str | None = None
    error: str | None = None


class MemoryGraphNode(CamelModel):
    """A node in the memory graph."""

    id: str
    type: str
    label: str
    content: str | None = None
    timestamp: str | None = None


class MemoryGraphEdge(CamelModel):
    """An edge in the memory graph."""

    source: str
    target: str
    type: str


class MemoryGraphResponse(CamelModel):
    """Memory graph structure."""

    nodes: list[MemoryGraphNode]
    edges: list[MemoryGraphEdge]
    stats: dict[str, int] | None = None
    message: str | None = None
    error: str | None = None


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
# DAG RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class DagNode(CamelModel):
    """A node in the DAG."""

    id: str
    type: str
    label: str
    status: str | None = None
    phase: str | None = None


class DagEdge(CamelModel):
    """An edge in the DAG."""

    source: str
    target: str
    type: str


class DagMetadata(CamelModel):
    """Metadata for a DAG."""

    path: str | None = None
    checkpoint: dict[str, int | str] | None = None


class DagResponse(CamelModel):
    """DAG structure response."""

    nodes: list[DagNode]
    edges: list[DagEdge]
    metadata: DagMetadata | None = None


class DagPlanTask(CamelModel):
    """A task in the execution plan."""

    id: str
    description: str


class DagPlanResponse(CamelModel):
    """Incremental execution plan."""

    to_execute: list[DagPlanTask]
    to_skip: list[DagPlanTask]
    reason: str
    checkpoint: dict[str, str | int] | None = None


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
