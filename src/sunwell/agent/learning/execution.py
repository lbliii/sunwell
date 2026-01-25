"""Learning extraction for intra-session and cross-session memory (RFC-042).

This module has been modularized. All classes and functions are now in the
`learning/` subdirectory. This file re-exports everything for convenient access.
"""

# Re-export from learning subdirectory
from sunwell.agent.learning import (
    DeadEnd,
    Learning,
    LearningExtractor,
    LearningStore,
    ToolPattern,
    classify_task_type,
    learn_from_execution,
)

__all__ = [
    "Learning",
    "DeadEnd",
    "ToolPattern",
    "classify_task_type",
    "LearningExtractor",
    "LearningStore",
    "learn_from_execution",
]
