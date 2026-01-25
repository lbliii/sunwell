"""Cognitive routing for intent-aware retrieval.

The routing module contains:
- UnifiedRouter (RFC-030): Single-model routing for all decisions (RECOMMENDED)
- CognitiveRouter (RFC-020): Intent-aware routing with tiny LLMs (DEPRECATED)
- TieredAttunement (RFC-022): Enhanced routing with DORI-inspired techniques (DEPRECATED)

RFC-030 Migration:
    UnifiedRouter replaces CognitiveRouter, TieredAttunement, Discernment,
    and model routing with a single tiny model that handles ALL decisions
    in one inference call.

    Old: router = CognitiveRouter(model, lenses)
         decision = await router.route(task)

    New: router = UnifiedRouter(model)
         decision = await router.route(request)

    The new RoutingDecision includes intent, complexity, lens, tools,
    mood, expertise, and confidence - all in one call.
"""

from typing import Any, Protocol

from sunwell.types.protocol import Serializable


# =============================================================================
# Protocols for routing components
# =============================================================================


class HasStats(Protocol):
    """Protocol for classes that provide statistics.

    Implemented by: CognitiveRouter, HybridRouter, UnifiedRouter, TieredAttunement
    """

    def get_stats(self) -> dict[str, Any]: ...


# Re-export Serializable for backwards compatibility
__all__ = ["HasStats", "Serializable"]

# RFC-030: Unified Router (recommended)
# RFC-020: Cognitive Router (deprecated - use UnifiedRouter)
from sunwell.routing.cognitive_router import (
    CognitiveRouter,
    Complexity,
    HybridRouter,
    Intent,
    IntentTaxonomy,
    RoutingDecision,
)

# RFC-022: Tiered Attunement (deprecated - use UnifiedRouter)
from sunwell.routing.tiered_attunement import (
    ROUTING_EXEMPLARS,
    AttunementResult,
    ConfidenceRubric,
    RoutingExemplar,
    Tier,
    TierBehavior,
    TieredAttunement,
    VerificationResult,
    create_tiered_attunement,
)
from sunwell.routing.unified import (
    Complexity as UnifiedComplexity,
)
from sunwell.routing.unified import (
    Intent as UnifiedIntent,
)
from sunwell.routing.unified import (
    LegacyRoutingAdapter,
    UnifiedRouter,
    UserExpertise,
    UserMood,
    create_unified_router,
)
from sunwell.routing.unified import (
    RoutingDecision as UnifiedRoutingDecision,
)

__all__ = [
    # Protocols
    "HasStats",
    "Serializable",
    # RFC-030: Unified Router (recommended)
    "UnifiedRouter",
    "UnifiedRoutingDecision",
    "UnifiedIntent",
    "UnifiedComplexity",
    "UserMood",
    "UserExpertise",
    "LegacyRoutingAdapter",
    "create_unified_router",
    # RFC-020: Cognitive Router (deprecated)
    "CognitiveRouter",
    "RoutingDecision",
    "IntentTaxonomy",
    "Intent",
    "Complexity",
    "HybridRouter",
    # RFC-022: Tiered Attunement (deprecated)
    "TieredAttunement",
    "AttunementResult",
    "Tier",
    "TierBehavior",
    "RoutingExemplar",
    "ConfidenceRubric",
    "VerificationResult",
    "ROUTING_EXEMPLARS",
    "create_tiered_attunement",
]
