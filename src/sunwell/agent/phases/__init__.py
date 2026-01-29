"""Agent execution phases.

Part of the Agent refactoring (Week 3 work) to extract phases into
separate, testable modules.

Phases:
- OrientationPhase: Load memory context and identify constraints
- LearningPhase: Extract learnings from execution
- (Future) PlanningPhase: Extract signals and build task graph
- (Future) ExecutionPhase: Execute tasks with gates

Each phase is independent and can be tested in isolation.
"""

from sunwell.agent.phases.learning import LearningPhase, LearningResult
from sunwell.agent.phases.orientation import OrientationPhase, OrientationResult

__all__ = [
    "OrientationPhase",
    "OrientationResult",
    "LearningPhase",
    "LearningResult",
]
