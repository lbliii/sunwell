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
from sunwell.memory.core.types import (
    MemoryContext,
    Promptable,
    SyncResult,
    TaskMemoryContext,
)

# Briefing system (RFC-071)
from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchPlan,
    PrefetchedContext,
    briefing_to_learning,
    compress_briefing,
)

# Persistent memory facade - THE main entry point
from sunwell.memory.facade import GoalMemory, PersistentMemory

# Key types from subpackages (import more from subpackages directly)
from sunwell.memory.simulacrum import SimulacrumStore, Turn, Learning
from sunwell.memory.lineage import LineageStore, ArtifactLineage
from sunwell.memory.session import SessionTracker

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
