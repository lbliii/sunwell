"""Harmonic Planner for RFC-038: Iterative DAG Shape Optimization.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from `sunwell.naaru.planners.harmonic` instead.

Migration guide:
    # Old (still works)
    from sunwell.naaru.planners.harmonic import HarmonicPlanner, ScoringVersion

    # New (preferred)
    from sunwell.naaru.planners.harmonic import HarmonicPlanner, ScoringVersion
"""

# Re-export everything from the new modular structure for backward compatibility
from sunwell.naaru.planners.harmonic import (
    HarmonicPlanner,
    PlanMetrics,
    PlanMetricsV2,
    ScoringVersion,
    VarianceStrategy,
)

__all__ = [
    "HarmonicPlanner",
    "ScoringVersion",
    "PlanMetrics",
    "PlanMetricsV2",
    "VarianceStrategy",
]
