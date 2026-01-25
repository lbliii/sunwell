"""Harmonic planning event schemas (RFC-058)."""

from typing import Any, TypedDict


class PlanCandidateStartData(TypedDict, total=False):
    """Data for plan_candidate_start event."""
    total_candidates: int  # Required
    variance_strategy: str  # e.g., "prompting", "temperature"


class PlanCandidateGeneratedData(TypedDict, total=False):
    """Data for plan_candidate_generated event."""
    candidate_id: str  # REQUIRED - stable identifier (e.g., 'candidate-0')
    artifact_count: int  # Required
    progress: int  # Current count (1-based)
    total_candidates: int  # Required
    variance_config: dict[str, Any]  # Variance configuration used


class PlanCandidatesCompleteData(TypedDict, total=False):
    """Data for plan_candidates_complete event.

    RFC-060: Aligned with actual HarmonicPlanner emission.
    """
    total_candidates: int  # Kept for backward compat
    total_artifacts: int  # Kept for backward compat
    successful_candidates: int  # How many candidates succeeded
    failed_candidates: int  # How many candidates failed


class PlanCandidateScoredData(TypedDict, total=False):
    """Data for plan_candidate_scored event."""
    candidate_id: str  # REQUIRED - stable identifier (e.g., 'candidate-0')
    score: float  # Required
    progress: int  # Current count (1-based)
    total_candidates: int  # Required
    metrics: dict[str, Any]  # PlanMetrics as dict


class PlanScoringCompleteData(TypedDict, total=False):
    """Data for plan_scoring_complete event."""
    total_scored: int  # Required
