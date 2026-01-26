"""Core simulacrum abstractions.

RFC-025: Extracted from root simulacrum module.
RFC-084: Unified memory architecture - SimulacrumStore is the canonical Simulacrum.
"""

# Re-export Episode from types.memory for convenience
from sunwell.foundation.types.memory import Episode
from sunwell.memory.simulacrum.core.config import StorageConfig
from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.memory.simulacrum.core.episodes import EpisodeManager
from sunwell.memory.simulacrum.core.planning_context import PlanningContext
from sunwell.memory.simulacrum.core.retrieval import (
    ContextAssembler,
    PlanningRetriever,
    SemanticRetriever,
)
from sunwell.memory.simulacrum.core.session_manager import SessionManager
from sunwell.memory.simulacrum.core.store import SimulacrumStore
from sunwell.memory.simulacrum.core.tier_manager import TierManager
from sunwell.memory.simulacrum.core.turn import Learning, Turn, TurnType

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
    # Modular components
    "EpisodeManager",
    "SessionManager",
    "TierManager",
    # Retrieval modules
    "ContextAssembler",
    "PlanningRetriever",
    "SemanticRetriever",
]
