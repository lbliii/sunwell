"""Autonomous execution module (RFC-130).

Provides fully autonomous multi-agent workflows with:
- Dynamic specialist spawning
- Semantic checkpoints for crash recovery
- Adaptive guards that learn from violations
- Memory-informed prefetch for warm starts
"""

from sunwell.features.autonomous.workflow import (
    AutonomousConfig,
    AutonomousState,
    autonomous_goal,
    resume_autonomous,
)

__all__ = [
    "AutonomousConfig",
    "AutonomousState",
    "autonomous_goal",
    "resume_autonomous",
]
