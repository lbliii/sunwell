"""Primitive Scoring (RFC-072 prep for RFC-075).

Scores and ranks primitives for surface composition based on:
- Intent signals from goal
- Lens affordances
- Historical success patterns
- Contextual factors (project type, open files, etc.)
"""

from dataclasses import dataclass, field

from sunwell.core.lens import Affordances
from sunwell.surface.intent import IntentSignals, match_triggers
from sunwell.surface.registry import PrimitiveRegistry


@dataclass(frozen=True, slots=True)
class ScoredPrimitive:
    """A primitive with its computed score."""

    primitive_id: str
    """Primitive ID."""

    score: float
    """Composite score (0.0-1.0)."""

    reasons: tuple[str, ...] = ()
    """Why this primitive scored this way."""

    suggested_size: str = "panel"
    """Suggested size based on scoring context."""


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """Result of scoring primitives for a goal."""

    primary_candidates: tuple[ScoredPrimitive, ...]
    """Top candidates for primary primitive (sorted by score)."""

    secondary_candidates: tuple[ScoredPrimitive, ...]
    """Top candidates for secondary primitives (sorted by score)."""

    contextual_candidates: tuple[ScoredPrimitive, ...]
    """Top candidates for contextual widgets (sorted by score)."""


@dataclass
class ScoringContext:
    """Context for scoring primitives."""

    intent: IntentSignals
    """Extracted intent from goal."""

    affordances: Affordances | None = None
    """Lens affordances (if available)."""

    project_domain: str | None = None
    """Detected project domain."""

    memory_patterns: dict[str, float] = field(default_factory=dict)
    """Historical primitive success rates: {primitive_id: success_rate}."""


# =============================================================================
# DEFAULT SCORES BY DOMAIN
# =============================================================================

# Default primary primitive for each domain
DOMAIN_PRIMARY_DEFAULTS: dict[str, str] = {
    "code": "CodeEditor",
    "planning": "Kanban",
    "writing": "ProseEditor",
    "data": "DataTable",
    "universal": "CodeEditor",
}

# Default secondary primitives for each domain
DOMAIN_SECONDARY_DEFAULTS: dict[str, tuple[str, ...]] = {
    "code": ("FileTree", "Terminal"),
    "planning": ("GoalTree", "Metrics"),
    "writing": ("Outline", "References"),
    "data": ("Chart", "QueryBuilder"),
    "universal": ("FileTree",),
}


def score_primitives(
    goal: str,
    registry: PrimitiveRegistry,
    context: ScoringContext,
) -> ScoringResult:
    """Score all primitives for a goal.

    Scoring algorithm:
    1. Base score from domain match
    2. Boost from lens affordances
    3. Boost from trigger keyword matches
    4. Boost from historical success
    5. Penalty for capability mismatch

    Args:
        goal: User's goal string
        registry: Primitive registry
        context: Scoring context

    Returns:
        Scored and ranked primitives for each slot
    """
    all_primitives = registry.list_all()

    # Score each primitive
    scored: list[ScoredPrimitive] = []
    for prim_def in all_primitives:
        score, reasons, size = _score_primitive(
            primitive_id=prim_def.id,
            category=prim_def.category,
            default_size=prim_def.default_size,
            goal=goal,
            context=context,
        )
        scored.append(
            ScoredPrimitive(
                primitive_id=prim_def.id,
                score=score,
                reasons=tuple(reasons),
                suggested_size=size,
            )
        )

    # Sort by score descending
    scored.sort(key=lambda s: s.score, reverse=True)

    # Separate by capability
    primary_cap = registry.list_primary_capable()
    secondary_cap = registry.list_secondary_capable()
    contextual_cap = registry.list_contextual_capable()

    primary_ids = {p.id for p in primary_cap}
    secondary_ids = {p.id for p in secondary_cap}
    contextual_ids = {p.id for p in contextual_cap}

    primary_candidates = tuple(s for s in scored if s.primitive_id in primary_ids)
    secondary_candidates = tuple(s for s in scored if s.primitive_id in secondary_ids)
    contextual_candidates = tuple(s for s in scored if s.primitive_id in contextual_ids)

    return ScoringResult(
        primary_candidates=primary_candidates,
        secondary_candidates=secondary_candidates,
        contextual_candidates=contextual_candidates,
    )


def _score_primitive(
    primitive_id: str,
    category: str,
    default_size: str,
    goal: str,
    context: ScoringContext,
) -> tuple[float, list[str], str]:
    """Score a single primitive.

    Returns:
        Tuple of (score, reasons, suggested_size)
    """
    score = 0.0
    reasons: list[str] = []
    size = default_size

    # 1. Domain match (0.0-0.3)
    domain_score = context.intent.domain_scores.get(category, 0.0)
    if domain_score > 0.1:
        score += domain_score * 0.3
        reasons.append(f"domain_match:{domain_score:.2f}")

    # 2. Primary domain bonus (0.0-0.2)
    if category == context.intent.primary_domain:
        score += 0.2
        reasons.append("primary_domain")

    # 3. Lens affordance boost (0.0-0.3)
    if context.affordances:
        affordance_score, affordance_size = _score_from_affordances(
            primitive_id, goal, context.affordances
        )
        if affordance_score > 0:
            score += affordance_score * 0.3
            reasons.append(f"affordance:{affordance_score:.2f}")
            if affordance_size:
                size = affordance_size

    # 4. Trigger keyword match (0.0-0.2)
    if primitive_id in context.intent.triggered_primitives:
        score += 0.2
        reasons.append("trigger_match")

    # 5. Historical success boost (0.0-0.1)
    if primitive_id in context.memory_patterns:
        memory_boost = context.memory_patterns[primitive_id] * 0.1
        score += memory_boost
        reasons.append(f"memory:{memory_boost:.2f}")

    # 6. Default for domain boost (0.1)
    if _is_domain_default(primitive_id, context.intent.primary_domain):
        score += 0.1
        reasons.append("domain_default")

    # Clamp to [0.0, 1.0]
    score = max(0.0, min(1.0, score))

    return score, reasons, size


def _score_from_affordances(
    primitive_id: str,
    goal: str,
    affordances: Affordances,
) -> tuple[float, str | None]:
    """Score a primitive based on lens affordances.

    Returns:
        Tuple of (score, suggested_size or None)
    """
    # Check primary affordances
    for aff in affordances.primary:
        if aff.primitive == primitive_id and (
            aff.trigger is None or match_triggers(aff.trigger, goal)
        ):
            return aff.weight, aff.default_size

    # Check secondary affordances (slightly lower weight than primary)
    for aff in affordances.secondary:
        if aff.primitive == primitive_id and (
            aff.trigger is None or match_triggers(aff.trigger, goal)
        ):
            return aff.weight * 0.8, aff.default_size

    # Check contextual affordances (lower weight for contextual)
    for aff in affordances.contextual:
        if aff.primitive == primitive_id and (
            aff.trigger is None or match_triggers(aff.trigger, goal)
        ):
            return aff.weight * 0.6, aff.default_size

    return 0.0, None


def _is_domain_default(primitive_id: str, domain: str) -> bool:
    """Check if a primitive is a domain default."""
    if DOMAIN_PRIMARY_DEFAULTS.get(domain) == primitive_id:
        return True
    return primitive_id in DOMAIN_SECONDARY_DEFAULTS.get(domain, ())


def select_primitives(
    scoring_result: ScoringResult,
    max_secondary: int = 3,
    max_contextual: int = 2,
    min_score: float = 0.1,
) -> tuple[ScoredPrimitive | None, tuple[ScoredPrimitive, ...], tuple[ScoredPrimitive, ...]]:
    """Select primitives from scoring result.

    Args:
        scoring_result: Scored primitives
        max_secondary: Maximum secondary primitives
        max_contextual: Maximum contextual primitives
        min_score: Minimum score to include

    Returns:
        Tuple of (primary, secondary tuple, contextual tuple)
    """
    # Select primary (highest scoring)
    primary = None
    if scoring_result.primary_candidates:
        primary = scoring_result.primary_candidates[0]

    # Select secondary (top N above threshold, excluding primary)
    primary_id = primary.primitive_id if primary else None
    secondary = tuple(
        s
        for s in scoring_result.secondary_candidates[:max_secondary + 1]
        if s.score >= min_score and s.primitive_id != primary_id
    )[:max_secondary]

    # Select contextual (top N above threshold, excluding primary and secondary)
    excluded_ids = {primary_id} | {s.primitive_id for s in secondary}
    contextual = tuple(
        s
        for s in scoring_result.contextual_candidates[:max_contextual + 1]
        if s.score >= min_score and s.primitive_id not in excluded_ids
    )[:max_contextual]

    return primary, secondary, contextual
