"""Memory subsystem for Sunwell.

Contains the briefing system (RFC-071) for rolling handoff notes.
"""

from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchedContext,
    PrefetchPlan,
    briefing_to_learning,
    compress_briefing,
)

__all__ = [
    "Briefing",
    "BriefingStatus",
    "ExecutionSummary",
    "PrefetchPlan",
    "PrefetchedContext",
    "briefing_to_learning",
    "compress_briefing",
]
