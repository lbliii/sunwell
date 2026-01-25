"""Autonomous Backlog - RFC-046: Self-Directed Goal Generation.

Autonomous Backlog enables Sunwell to generate, prioritize, and pursue goals
without explicit user commands. Instead of waiting for "Build X", Sunwell
continuously observes project state and identifies what should exist but doesn't.

Components:
- SignalExtractor: Extract observable signals from code (tests, TODOs, type errors)
- GoalGenerator: Convert signals to prioritized goals
- BacklogManager: Maintain goal DAG with dependencies
- AutonomousLoop: Execute goals using ArtifactPlanner and Agent
- EpicDecomposer: Decompose ambitious goals into milestones (RFC-115)
- MilestoneTracker: Track progress and transitions (RFC-115)

See: RFC-046-autonomous-backlog.md, RFC-115-hierarchical-goal-decomposition.md
"""

from sunwell.backlog.decomposer import EpicDecomposer
from sunwell.backlog.goals import Goal, GoalGenerator, GoalPolicy, GoalResult, GoalScope
from sunwell.backlog.loop import AutonomousLoop
from sunwell.backlog.manager import Backlog, BacklogManager
from sunwell.backlog.signals import ObservableSignal, SignalExtractor
from sunwell.backlog.tracker import (
    DictSerializable,
    LearningStore,
    MilestoneLearning,
    MilestoneProgress,
    MilestoneTracker,
)

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
    # RFC-115: Hierarchical Goal Decomposition
    "EpicDecomposer",
    "MilestoneTracker",
    "MilestoneProgress",
    "MilestoneLearning",
    "LearningStore",
    # Protocols
    "DictSerializable",
]
