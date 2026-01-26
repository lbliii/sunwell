"""Memory subsystem for Sunwell.

Contains:
- PersistentMemory: Unified memory access facade (the main entry point)
- Briefing: Rolling handoff notes between sessions (RFC-071)
- Simulacrum: Conversation memory with hierarchical storage (RFC-013/014)
- Lineage: Artifact provenance tracking (RFC-121)
- Session: Session-level tracking and summarization (RFC-120)

Import from subpackages for specialized types:
    from sunwell.memory.simulacrum import SimulacrumStore, Turn
    from sunwell.memory.lineage import LineageStore, ArtifactLineage
    from sunwell.memory.session import SessionTracker

RFC-138: Module Architecture Consolidation
"""

# Core types
# Briefing system (RFC-071)
from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchedContext,
    PrefetchPlan,
    briefing_to_learning,
    compress_briefing,
)
from sunwell.memory.core.types import (
    MemoryContext,
    Promptable,
    SyncResult,
    TaskMemoryContext,
)

# Persistent memory facade - THE main entry point
from sunwell.memory.facade import GoalMemory, PersistentMemory
from sunwell.memory.lineage import ArtifactLineage, LineageStore
from sunwell.memory.session import SessionTracker

# Key types from subpackages (import more from subpackages directly)
from sunwell.memory.simulacrum import Learning, SimulacrumStore, Turn

__all__ = [
    # === Primary API ===
    "PersistentMemory",
    "GoalMemory",
    # === Briefing (RFC-071) ===
    "Briefing",
    "BriefingStatus",
    "ExecutionSummary",
    "PrefetchPlan",
    "PrefetchedContext",
    "briefing_to_learning",
    "compress_briefing",
    # === Core Types ===
    "MemoryContext",
    "Promptable",
    "TaskMemoryContext",
    "SyncResult",
    # === Key Subpackage Types (for convenience) ===
    "SimulacrumStore",
    "Turn",
    "Learning",
    "LineageStore",
    "ArtifactLineage",
    "SessionTracker",
]
