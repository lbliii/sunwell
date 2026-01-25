"""Memory subsystem for Sunwell.

Contains:
- Briefing system (RFC-071) for rolling handoff notes
- PersistentMemory facade for unified memory access
- Memory context types for planning and execution
- Simulacrum, lineage, and session tracking

RFC-138: Module Architecture Consolidation
"""

# Core types
from sunwell.memory.core.types import (
    MemoryContext,
    Promptable,
    SyncResult,
    TaskMemoryContext,
)

# Briefing system
from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchPlan,
    PrefetchedContext,
    briefing_to_learning,
    compress_briefing,
)

# Persistent memory facade
from sunwell.memory.facade import GoalMemory, PersistentMemory

# Re-exports from consolidated modules (Phase 5)
from sunwell.memory.simulacrum import *  # noqa: F403, F401
from sunwell.memory.lineage import *  # noqa: F403, F401
from sunwell.memory.session import *  # noqa: F403, F401

__all__ = [
    # Core types
    "MemoryContext",
    "Promptable",
    "TaskMemoryContext",
    "SyncResult",
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
    "GoalMemory",
]
