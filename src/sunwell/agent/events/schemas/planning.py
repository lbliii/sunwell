"""Planning event schemas."""

from typing import Any, TypedDict


class PlanCandidateData(TypedDict, total=False):
    """Data for plan_candidate event (legacy)."""
    candidate_id: str  # Use candidate_id for matching
    artifact_count: int
    description: str


class PlanExpandedData(TypedDict, total=False):
    """Data for plan_expanded event."""
    new_tasks: int
    total_tasks: int
    reason: str


class PlanAssessData(TypedDict, total=False):
    """Data for plan_assess event."""
    complete: bool
    remaining_tasks: int
    assessment: str


class PlanDiscoveryProgressData(TypedDict, total=False):
    """Data for plan_discovery_progress event (RFC-059)."""
    artifacts_discovered: int  # Required
    phase: str  # Required: "discovering" | "parsing" | "validating" | "building_graph" | "complete"
    total_estimated: int | None  # Optional: if known
    current_artifact: str | None  # Optional: current artifact being processed
