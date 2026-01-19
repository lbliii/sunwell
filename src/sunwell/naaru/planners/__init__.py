"""Task planners for RFC-032, RFC-034, RFC-036, RFC-038, RFC-039.

Planners decompose goals into executable Task objects.

Available Planners:
- SelfImprovementPlanner: Find opportunities in Sunwell's codebase (RFC-019 behavior)
- AgentPlanner: Decompose arbitrary user goals using LLM (RFC-032, RFC-034)
- ArtifactPlanner: Discover artifacts, dependency resolution determines order (RFC-036)
- HarmonicPlanner: Multi-candidate optimization with variance strategies (RFC-038)
- ExpertiseAwareArtifactPlanner: Artifact planner with expertise injection (RFC-039)

Planning Strategies:
- SEQUENTIAL: Linear task dependencies (RFC-032)
- CONTRACT_FIRST: Contracts before implementations (RFC-034)
- RESOURCE_AWARE: Minimize file conflicts (RFC-034)
- ARTIFACT_FIRST: Artifact discovery with structural parallelism (RFC-036)
- HARMONIC: Multi-candidate generation with quantitative selection (RFC-038)
"""

from sunwell.naaru.planners.agent import AgentPlanner
from sunwell.naaru.planners.artifact import ArtifactPlanner
from sunwell.naaru.planners.expertise_aware import (
    ExpertiseAwareArtifactPlanner,
    create_expertise_aware_planner,
)
from sunwell.naaru.planners.harmonic import (
    HarmonicPlanner,
    PlanMetrics,
    VarianceStrategy,
)
from sunwell.naaru.planners.protocol import PlanningError, PlanningStrategy, TaskPlanner
from sunwell.naaru.planners.self_improvement import SelfImprovementPlanner

__all__ = [
    "TaskPlanner",
    "PlanningError",
    "PlanningStrategy",
    "SelfImprovementPlanner",
    "AgentPlanner",
    "ArtifactPlanner",
    # RFC-038: Harmonic Planning
    "HarmonicPlanner",
    "PlanMetrics",
    "VarianceStrategy",
    # RFC-039: Expertise-Aware Planning
    "ExpertiseAwareArtifactPlanner",
    "create_expertise_aware_planner",
]
