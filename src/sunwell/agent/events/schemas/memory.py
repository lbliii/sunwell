"""Memory event schemas."""

from typing import TypedDict


class MemoryLoadData(TypedDict, total=False):
    """Data for memory_load event."""
    session_id: str | None


class MemoryLoadedData(TypedDict, total=False):
    """Data for memory_loaded event."""
    session_id: str | None
    fact_count: int
    dead_end_count: int


class MemoryNewData(TypedDict, total=False):
    """Data for memory_new event."""
    session_id: str | None


class MemoryDeadEndData(TypedDict, total=False):
    """Data for memory_dead_end event."""
    approach: str  # Required
    reason: str


class MemoryCheckpointData(TypedDict, total=False):
    """Data for memory_checkpoint event."""
    session_id: str | None
    fact_count: int


class MemorySavedData(TypedDict, total=False):
    """Data for memory_saved event."""
    session_id: str | None
    fact_count: int
    dead_end_count: int
