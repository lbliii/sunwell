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


# =============================================================================
# RFC-MEMORY: Unified Memory Events
# =============================================================================


class OrientData(TypedDict, total=False):
    """Data for orient event (RFC-MEMORY)."""

    learnings: int
    constraints: int
    dead_ends: int


class LearningAddedData(TypedDict, total=False):
    """Data for learning_added event (RFC-MEMORY)."""

    fact: str
    category: str
    confidence: float


class DecisionMadeData(TypedDict, total=False):
    """Data for decision_made event (RFC-MEMORY)."""

    category: str
    question: str
    choice: str
    rejected_count: int


class FailureRecordedData(TypedDict, total=False):
    """Data for failure_recorded event (RFC-MEMORY)."""

    description: str
    error_type: str
    context: str


class BriefingUpdatedData(TypedDict, total=False):
    """Data for briefing_updated event (RFC-MEMORY)."""

    status: str
    next_action: str | None
    hot_files: list[str]


class KnowledgeRetrievedData(TypedDict, total=False):
    """Data for knowledge_retrieved event."""

    query: str | None
    results_count: int | None


class TemplateMatchedData(TypedDict, total=False):
    """Data for template_matched event."""

    template_id: str | None
    confidence: float | None
