"""Cognitive routing for intent-aware retrieval.

The routing module contains:
- CognitiveRouter (RFC-020): Intent-aware routing with tiny LLMs
- TieredAttunement (RFC-022): Enhanced routing with DORI-inspired techniques

This is the "DORI-killer" — IDE-agnostic intelligent routing that works
anywhere Sunwell runs.
"""

from sunwell.routing.cognitive_router import (
    CognitiveRouter,
    RoutingDecision,
    IntentTaxonomy,
    Intent,
    Complexity,
    HybridRouter,
)

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
    # RFC-020: Cognitive Router
    "CognitiveRouter",
    "RoutingDecision",
    "IntentTaxonomy",
    "Intent",
    "Complexity",
    "HybridRouter",
    # RFC-022: Tiered Attunement
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
