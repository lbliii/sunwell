"""Core simulacrum abstractions.

RFC-025: Extracted from root simulacrum module.
RFC-084: Unified memory architecture - SimulacrumStore is now the canonical Simulacrum.
"""

from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.store import SimulacrumStore, StorageConfig
from sunwell.simulacrum.core.turn import Learning, Turn, TurnType

# RFC-084: SimulacrumStore is now the unified Simulacrum class
Simulacrum = SimulacrumStore

# Legacy imports - deprecated, will be removed in future version
# These are kept for backward compatibility during migration
from sunwell.simulacrum.core.memory import (
    Episode,
    EpisodicMemory,
    LongTermMemory,
    MemoryType,
    ProceduralMemory,
    SemanticMemory,
    WorkingMemory,
)

# Legacy Simulacrum class - deprecated
from sunwell.simulacrum.core.core import Simulacrum as LegacySimulacrum

__all__ = [
    # RFC-084: Primary exports
    "Simulacrum",  # Alias for SimulacrumStore (unified class)
    "SimulacrumStore",
    "StorageConfig",
    "ConversationDAG",
    "Turn",
    "TurnType",
    "Learning",
    # Legacy (deprecated)
    "LegacySimulacrum",
    "MemoryType",
    "WorkingMemory",
    "LongTermMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "Episode",
]
