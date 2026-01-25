"""Plan refinement event schemas."""

from typing import TypedDict


class PlanRefineStartData(TypedDict, total=False):
    """Data for plan_refine_start event."""
    round: int  # Required
    total_rounds: int  # Required
    current_score: float
    improvements_identified: list[str]


class PlanRefineAttemptData(TypedDict, total=False):
    """Data for plan_refine_attempt event."""
    round: int  # Required
    improvements_applied: list[str]
    new_score: float


class PlanRefineCompleteData(TypedDict, total=False):
    """Data for plan_refine_complete event.

    Required: round
    Optional: All other fields

    RFC-060: Field names aligned with frontend expectations.
    """
    round: int  # REQUIRED - which refinement round (1-indexed)
    improved: bool  # Did this round improve the plan?
    old_score: float | None  # Score before refinement
    new_score: float | None  # Score after refinement
    improvement: float | None  # Delta (new_score - old_score)
    reason: str | None  # Why refinement stopped or continued
    improvements_applied: list[str]  # List of improvements made


class PlanRefineFinalData(TypedDict, total=False):
    """Data for plan_refine_final event."""
    total_rounds: int  # Required
    final_score: float
    total_improvements: int
