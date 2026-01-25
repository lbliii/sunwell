"""Cognitive routing for intent-aware retrieval.

The routing module provides:
- UnifiedRouter (RFC-030): Single-model routing for all decisions

UnifiedRouter handles ALL pre-processing decisions in one inference call:
- Intent Classification — What kind of task is this?
- Complexity Assessment — How complex is this task?
- Lens Selection — Which lens should handle it?
- Tool Prediction — What tools might be needed?
- User Mood Detection — What's the user's emotional state?
- Expertise Level — What's the user's technical level?

Usage:
    router = UnifiedRouter(model)
    decision = await router.route(request)
"""

from typing import Any, Protocol

from sunwell.types.protocol import Serializable


# =============================================================================
# Protocols for routing components
# =============================================================================


class HasStats(Protocol):
    """Protocol for classes that provide statistics.

    Implemented by: UnifiedRouter
    """

    def get_stats(self) -> dict[str, Any]: ...


# RFC-030: Unified Router
from sunwell.routing.unified import (
    Complexity,
    Intent,
    RoutingDecision,
    UnifiedRouter,
    UserExpertise,
    UserMood,
    create_unified_router,
)

# RFC-022 Enhancement: Deterministic confidence and tiered execution
from sunwell.routing.unified import (
    ConfidenceRubric,
    ExecutionTier,
    RoutingExemplar,
    TierBehavior,
)

__all__ = [
    # Protocols
    "HasStats",
    "Serializable",
    # RFC-030: Unified Router
    "UnifiedRouter",
    "RoutingDecision",
    "Intent",
    "Complexity",
    "UserMood",
    "UserExpertise",
    "create_unified_router",
    # RFC-022 Enhancement: Confidence & Tiers
    "ConfidenceRubric",
    "ExecutionTier",
    "TierBehavior",
    "RoutingExemplar",
]
