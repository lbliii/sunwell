"""Autonomous Backlog - RFC-046: Self-Directed Goal Generation.

Autonomous Backlog enables Sunwell to generate, prioritize, and pursue goals
without explicit user commands. Instead of waiting for "Build X", Sunwell
continuously observes project state and identifies what should exist but doesn't.

Components:
- SignalExtractor: Extract observable signals from code (tests, TODOs, type errors)
- GoalGenerator: Convert signals to prioritized goals
- BacklogManager: Maintain goal DAG with dependencies
- AutonomousLoop: Execute goals using ArtifactPlanner and Agent

See: RFC-046-autonomous-backlog.md
"""

from sunwell.backlog.goals import Goal, GoalGenerator, GoalPolicy, GoalResult, GoalScope
from sunwell.backlog.loop import AutonomousLoop
from sunwell.backlog.manager import Backlog, BacklogManager
from sunwell.backlog.signals import ObservableSignal, SignalExtractor

__all__ = [
    # Signals
    "ObservableSignal",
    "SignalExtractor",
    # Goals
    "Goal",
    "GoalGenerator",
    "GoalPolicy",
    "GoalResult",
    "GoalScope",
    # Backlog
    "Backlog",
    "BacklogManager",
    # Loop
    "AutonomousLoop",
]
