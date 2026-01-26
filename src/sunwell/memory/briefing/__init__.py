"""Briefing system for rolling handoff notes (RFC-071)."""

from sunwell.memory.briefing.briefing import Briefing, BriefingStatus, ExecutionSummary
from sunwell.memory.briefing.compression import compress_briefing
from sunwell.memory.briefing.prefetch import (
    PrefetchedContext,
    PrefetchPlan,
    briefing_to_learning,
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
