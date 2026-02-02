"""Tool loop components.

This package contains supporting modules for the AgentLoop:
- config: LoopConfig, LoopState, ExecutionLane
- routing: Confidence-based routing strategies
- retry: Retry and escalation strategies
- delegation, expertise, recovery, reflection, validation: Loop integrations

Note: Learning injection is now handled via trinket composition
(see agent/trinkets/implementations/learning.py).
"""

# Re-export config for convenience
from sunwell.agent.loop.config import (
    DEFAULT_LANE_CONCURRENCY,
    ExecutionLane,
    LoopConfig,
    LoopState,
)

__all__ = [
    "LoopConfig",
    "LoopState",
    "ExecutionLane",
    "DEFAULT_LANE_CONCURRENCY",
]
