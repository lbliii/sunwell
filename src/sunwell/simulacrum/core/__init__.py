"""Core simulacrum abstractions.

RFC-025: Extracted from root simulacrum module.
RFC-084: Unified memory architecture - SimulacrumStore is the canonical Simulacrum.
"""

from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.store import PlanningContext, SimulacrumStore, StorageConfig
from sunwell.simulacrum.core.turn import Learning, Turn, TurnType

# Re-export Episode from types.memory for convenience
from sunwell.types.memory import Episode

# RFC-084: SimulacrumStore is now the unified Simulacrum class
Simulacrum = SimulacrumStore

__all__ = [
    # RFC-084: Primary exports
    "Simulacrum",  # Alias for SimulacrumStore (unified class)
    "SimulacrumStore",
    "StorageConfig",
    "PlanningContext",  # RFC-122 with RFC-022 episode integration
    "ConversationDAG",
    "Turn",
    "TurnType",
    "Learning",
    "Episode",
]
