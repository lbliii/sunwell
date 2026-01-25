"""Core simulacrum abstractions.

RFC-025: Extracted from root simulacrum module.
RFC-084: Unified memory architecture - SimulacrumStore is the canonical Simulacrum.
"""

from sunwell.simulacrum.core.config import StorageConfig
from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.episodes import EpisodeManager
from sunwell.simulacrum.core.planning_context import PlanningContext
from sunwell.simulacrum.core.retrieval import (
    ContextAssembler,
    PlanningRetriever,
    SemanticRetriever,
)
from sunwell.simulacrum.core.session_manager import SessionManager
from sunwell.simulacrum.core.store import SimulacrumStore
from sunwell.simulacrum.core.tier_manager import TierManager
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
    # Modular components
    "EpisodeManager",
    "SessionManager",
    "TierManager",
    # Retrieval modules
    "ContextAssembler",
    "PlanningRetriever",
    "SemanticRetriever",
]
