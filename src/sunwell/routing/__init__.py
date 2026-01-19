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

# RFC-030: Unified Router (recommended)
from sunwell.routing.unified import (
    UnifiedRouter,
    RoutingDecision as UnifiedRoutingDecision,
    Intent as UnifiedIntent,
    Complexity as UnifiedComplexity,
    UserMood,
    UserExpertise,
    LegacyRoutingAdapter,
    create_unified_router,
)

# RFC-020: Cognitive Router (deprecated - use UnifiedRouter)
from sunwell.routing.cognitive_router import (
    CognitiveRouter,
    RoutingDecision,
    IntentTaxonomy,
    Intent,
    Complexity,
    HybridRouter,
)

# RFC-022: Tiered Attunement (deprecated - use UnifiedRouter)
from sunwell.routing.tiered_attunement import (
    TieredAttunement,
    AttunementResult,
    Tier,
    TierBehavior,
    RoutingExemplar,
    ConfidenceRubric,
    VerificationResult,
    ROUTING_EXEMPLARS,
    create_tiered_attunement,
)

__all__ = [
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
