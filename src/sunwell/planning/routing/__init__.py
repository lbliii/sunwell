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

from sunwell.routing.decision import RoutingDecision
from sunwell.routing.exemplars import (
    ROUTING_EXEMPLARS,
    RoutingExemplar,
    match_exemplar,
)
from sunwell.routing.rubric import DEFAULT_RUBRIC, ConfidenceRubric
from sunwell.routing.types import (
    Complexity,
    ExecutionTier,
    Intent,
    TierBehavior,
    UserExpertise,
    UserMood,
    determine_tier,
)
from sunwell.routing.unified import (
    INTENT_FOCUS_MAP,
    INTENT_LENS_MAP,
    LENS_NAME_MAP,
    UNIFIED_ROUTER_PROMPT,
    UnifiedRouter,
    create_unified_router,
)
from sunwell.types.protocol import Serializable


class HasStats(Protocol):
    """Protocol for classes that provide statistics.

    Implemented by: UnifiedRouter
    """

    def get_stats(self) -> dict[str, Any]: ...


__all__ = [
    # Protocols
    "HasStats",
    "Serializable",
    # Types (RFC-030)
    "Intent",
    "Complexity",
    "UserMood",
    "UserExpertise",
    "ExecutionTier",
    "TierBehavior",
    "determine_tier",
    # Confidence Rubric (RFC-022)
    "ConfidenceRubric",
    "DEFAULT_RUBRIC",
    # Exemplars (RFC-022)
    "RoutingExemplar",
    "ROUTING_EXEMPLARS",
    "match_exemplar",
    # Decision (RFC-030)
    "RoutingDecision",
    # Router (RFC-030)
    "UnifiedRouter",
    "create_unified_router",
    "UNIFIED_ROUTER_PROMPT",
    "LENS_NAME_MAP",
    "INTENT_LENS_MAP",
    "INTENT_FOCUS_MAP",
]
