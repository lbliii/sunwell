"""Memory response models (RFC-013, RFC-014, RFC-084)."""

from sunwell.interface.server.routes.models.base import CamelModel


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
