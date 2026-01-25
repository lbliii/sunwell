"""Base event schemas - common events used across the system."""

from typing import Any, TypedDict


class PlanStartData(TypedDict, total=False):
    """Data for plan_start event."""
    goal: str


class PlanWinnerData(TypedDict, total=False):
    """Data for plan_winner event.

    Required: tasks
    Optional: All other fields (backward-compatible with non-Harmonic planners)

    RFC-060: This schema is the single source of truth for plan_winner events.
    """
    # Core fields (legacy)
    tasks: int  # REQUIRED - enforced via REQUIRED_FIELDS
    artifact_count: int
    gates: int
    technique: str

    # RFC-058: Harmonic planning fields
    selected_candidate_id: str  # REQUIRED - ID of selected candidate (e.g., 'candidate-0')
    total_candidates: int  # How many candidates were generated
    metrics: dict[str, int | float | bool | list[int]]  # PlanMetrics as dict (score, depth, width, etc.)
    selection_reason: str  # Human-readable selection reason
    variance_strategy: str  # "prompting" | "temperature" | "constraints" | "mixed"
    variance_config: dict[str, str | int | float | bool]  # Variance config used for selected candidate
    refinement_rounds: int  # How many refinement rounds were run
    final_score_improvement: float  # Total score improvement from refinement
    score: float  # CANONICAL - top-level score (same as metrics.score)

    # RFC-090: Plan transparency - detailed task/gate lists
    task_list: list[dict[str, Any]]  # List of TaskSummary dicts
    gate_list: list[dict[str, Any]]  # List of GateSummary dicts


class TaskStartData(TypedDict, total=False):
    """Data for task_start event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    description: str  # Required


class TaskProgressData(TypedDict, total=False):
    """Data for task_progress event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    progress: int  # 0-100
    message: str


class TaskCompleteData(TypedDict, total=False):
    """Data for task_complete event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    duration_ms: int  # Required
    file: str | None


class TaskFailedData(TypedDict, total=False):
    """Data for task_failed event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    error: str  # Required


class MemoryLearningData(TypedDict, total=False):
    """Data for memory_learning event."""
    fact: str  # Required
    category: str  # Required


class CompleteData(TypedDict, total=False):
    """Data for complete event."""
    tasks_completed: int  # Required
    tasks_failed: int
    gates_passed: int
    duration_s: float
    learnings_count: int
    completed: int  # Alias for tasks_completed
    failed: int  # Alias for tasks_failed


class ErrorData(TypedDict, total=False):
    """Data for error event."""
    message: str  # Required
    phase: str | None  # "planning" | "discovery" | "execution" | "validation"
    context: dict[str, Any] | None  # Additional context (artifact_id, task_id, etc.)
    error_type: str | None  # Exception class name
    traceback: str | None  # Optional: full traceback for verbose mode


class EscalateData(TypedDict, total=False):
    """Data for escalate event."""
    reason: str  # Required
    action: str
    context: dict[str, Any] | None
