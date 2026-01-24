"""Memory subsystem for Sunwell.

Contains:
- Briefing system (RFC-071) for rolling handoff notes
- PersistentMemory facade for unified memory access
- Memory context types for planning and execution
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
from sunwell.memory.persistent import PersistentMemory
from sunwell.memory.types import MemoryContext, SyncResult, TaskMemoryContext

__all__ = [
    # Briefing types
    "Briefing",
    "BriefingStatus",
    "ExecutionSummary",
    "PrefetchPlan",
    "PrefetchedContext",
    "briefing_to_learning",
    "compress_briefing",
    # Persistent memory facade
    "PersistentMemory",
    # Memory context types
    "MemoryContext",
    "TaskMemoryContext",
    "SyncResult",
]
