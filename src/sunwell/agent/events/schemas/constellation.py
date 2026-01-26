"""Agent constellation event schemas (RFC-130)."""

from typing import TypedDict


class SpecialistSpawnedData(TypedDict, total=False):
    """Data for specialist_spawned event."""

    specialist_id: str  # Required
    task_id: str
    parent_id: str
    role: str
    focus: str
    budget_tokens: int


class SpecialistCompletedData(TypedDict, total=False):
    """Data for specialist_completed event."""

    specialist_id: str  # Required
    success: bool
    summary: str
    tokens_used: int
    duration_seconds: float


class CheckpointFoundData(TypedDict, total=False):
    """Data for checkpoint_found event."""

    phase: str
    checkpoint_at: str
    goal: str


class CheckpointSavedData(TypedDict, total=False):
    """Data for checkpoint_saved event."""

    phase: str
    summary: str
    tasks_completed: int


class PhaseCompleteData(TypedDict, total=False):
    """Data for phase_complete event."""

    phase: str
    duration_seconds: float


class AutonomousActionBlockedData(TypedDict, total=False):
    """Data for autonomous_action_blocked event."""

    action_type: str
    path: str | None
    reason: str
    blocking_rule: str
    risk_level: str


class GuardEvolutionSuggestedData(TypedDict, total=False):
    """Data for guard_evolution_suggested event."""

    guard_id: str
    evolution_type: str
    reason: str
    confidence: float
