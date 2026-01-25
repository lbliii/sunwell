"""Harmonic Planner - Multi-candidate optimization with variance strategies.

This package provides HarmonicPlanner for RFC-038: Iterative DAG Shape Optimization.

Structure:
- planner.py: Main HarmonicPlanner class (orchestration)
- candidate.py: Candidate generation logic
- scoring.py: Scoring and metrics calculation (RFC-116)
- refinement.py: Refinement logic
- template.py: Template-guided planning (RFC-122)
- parsing.py: JSON parsing helpers
- utils.py: Utility functions (keyword extraction, etc.)
"""

from sunwell.planning.naaru.planners.harmonic.planner import HarmonicPlanner, ScoringVersion
from sunwell.planning.naaru.planners.metrics import PlanMetrics, PlanMetricsV2
from sunwell.planning.naaru.planners.variance import VarianceStrategy

# Re-export package exports
__all__ = [
    "HarmonicPlanner",
    "ScoringVersion",
    "PlanMetrics",
    "PlanMetricsV2",
    "VarianceStrategy",
]
