"""Importance scoring for memory retrieval.

Implements MIRA-inspired graph scoring that combines multiple signals
beyond pure semantic similarity:

- Semantic: Vector similarity + BM25 (existing hybrid score)
- Graph: Hub connectivity based on inbound references
- Behavioral: Access patterns, mentions, confidence
- Temporal: Recency decay, newness boost, deadline proximity

The key insight from MIRA is using "activity days" instead of calendar days
for decay calculations. This means memories don't decay during periods of
inactivity (vacations, weekends), providing fairer importance scoring.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from sunwell.memory.simulacrum.core.turn import Learning


@dataclass(frozen=True, slots=True)
class ImportanceConfig:
    """Configuration for importance scoring.

    Weights control how much each signal contributes to final score.
    All weights should sum to 1.0 for normalized output.
    """

    # Component weights (should sum to 1.0)
    semantic_weight: float = 0.5
    """Weight for semantic similarity (vector + BM25)."""

    graph_weight: float = 0.2
    """Weight for graph/hub connectivity."""

    behavioral_weight: float = 0.2
    """Weight for access patterns and confidence."""

    temporal_weight: float = 0.1
    """Weight for recency and temporal relevance."""

    # Behavioral constants
    baseline_access_rate: float = 0.02
    """Expected access rate: 1 access per 50 activity days."""

    momentum_decay_rate: float = 0.95
    """Decay factor per activity day for access momentum (5% fade)."""

    # Graph constants
    hub_linear_threshold: int = 10
    """Number of inbound links before diminishing returns."""

    hub_score_per_link: float = 0.04
    """Score contribution per inbound link (up to threshold)."""

    # Temporal constants
    newness_boost: float = 2.0
    """Maximum boost for brand-new memories."""

    newness_decay_days: int = 15
    """Activity days over which newness boost decays to 0."""

    recency_decay_rate: float = 0.015
    """Decay rate for recency (higher = faster decay)."""

    # Sigmoid normalization
    sigmoid_center: float = 2.0
    """Center point for sigmoid normalization."""


# Pre-defined configs for different learning categories
CATEGORY_CONFIGS: dict[str, ImportanceConfig] = {
    "dead_end": ImportanceConfig(
        behavioral_weight=0.4,  # Dead ends should surface when relevant but decay faster
        temporal_weight=0.3,
        semantic_weight=0.2,
        graph_weight=0.1,
    ),
    "preference": ImportanceConfig(
        behavioral_weight=0.3,  # Preferences should be sticky
        recency_decay_rate=0.005,  # Much slower decay
    ),
    "pattern": ImportanceConfig(
        graph_weight=0.3,  # Patterns often connect to other patterns
        semantic_weight=0.4,
    ),
    "template": ImportanceConfig(
        semantic_weight=0.6,  # Templates are heavily goal-matching
        behavioral_weight=0.2,
        graph_weight=0.1,
        temporal_weight=0.1,
    ),
    "heuristic": ImportanceConfig(
        behavioral_weight=0.3,  # Heuristics prove value through use
        semantic_weight=0.4,
    ),
}


def get_config_for_category(category: str) -> ImportanceConfig:
    """Get the appropriate config for a learning category.

    Args:
        category: Learning category (fact, preference, constraint, etc.)

    Returns:
        ImportanceConfig tuned for that category, or default
    """
    return CATEGORY_CONFIGS.get(category, ImportanceConfig())


def compute_importance(
    learning: Learning,
    query_similarity: float,
    activity_days: int,
    inbound_link_count: int = 0,
    config: ImportanceConfig | None = None,
) -> float:
    """Compute unified importance score for a learning.

    Combines semantic, graph, behavioral, and temporal signals into
    a single importance score normalized to 0-1 range.

    Args:
        learning: The learning to score
        query_similarity: Pre-computed semantic similarity (0-1)
        activity_days: Current cumulative activity day count
        inbound_link_count: Number of other learnings linking to this one
        config: Scoring config (defaults to category-specific config)

    Returns:
        Importance score between 0.0 and 1.0
    """
    if config is None:
        config = get_config_for_category(learning.category)

    # 1. Semantic score (already computed externally)
    semantic = query_similarity

    # 2. Graph score (hub connectivity)
    graph = compute_graph_score(inbound_link_count, config)

    # 3. Behavioral score (access patterns + confidence)
    behavioral = compute_behavioral_score(learning, activity_days, config)

    # 4. Temporal score (recency + deadline proximity)
    temporal = compute_temporal_score(learning, activity_days, config)

    # Combine with weighted sum
    raw_score = (
        config.semantic_weight * semantic
        + config.graph_weight * graph
        + config.behavioral_weight * behavioral
        + config.temporal_weight * temporal
    )

    # Sigmoid normalization to 0-1 range
    # This prevents any single signal from dominating
    return 1.0 / (1.0 + math.exp(-(raw_score - config.sigmoid_center)))


def compute_graph_score(
    inbound_link_count: int,
    config: ImportanceConfig,
) -> float:
    """Compute hub score based on inbound references.

    Memories that are referenced by many other memories are "hubs" of
    knowledge and should rank higher. Uses diminishing returns after
    a threshold to prevent runaway scores.

    Args:
        inbound_link_count: Number of other learnings linking to this one
        config: Scoring configuration

    Returns:
        Graph score component (typically 0-1 range)
    """
    if inbound_link_count == 0:
        return 0.0

    if inbound_link_count <= config.hub_linear_threshold:
        # Linear scaling up to threshold
        return inbound_link_count * config.hub_score_per_link
    else:
        # Diminishing returns after threshold
        base = config.hub_linear_threshold * config.hub_score_per_link
        excess = inbound_link_count - config.hub_linear_threshold
        # Logarithmic diminishing returns
        return base + (excess * 0.02) / (1 + excess * 0.05)


def compute_behavioral_score(
    learning: Learning,
    activity_days: int,
    config: ImportanceConfig,
) -> float:
    """Compute score based on access patterns and confidence.

    Higher scores for:
    - Frequently accessed memories
    - Recently accessed memories (with momentum decay)
    - Explicitly mentioned memories (strongest signal)
    - High-confidence memories

    Args:
        learning: The learning to score
        activity_days: Current cumulative activity day count
        config: Scoring configuration

    Returns:
        Behavioral score component (typically 0-1 range)
    """
    # Access rate with momentum decay
    # Older accesses contribute less than recent accesses
    days_since_access = activity_days - learning.activity_day_accessed
    effective_access = learning.use_count * (config.momentum_decay_rate**days_since_access)

    days_since_creation = activity_days - learning.activity_day_created
    age_days = max(7, days_since_creation)  # Minimum 7 days to prevent spikes

    access_rate = effective_access / age_days
    value_score = math.log1p(access_rate / config.baseline_access_rate) * 0.8

    # Mention score (explicit agent references are strongest signal)
    mention = learning.mention_count
    if mention == 0:
        mention_score = 0.0
    elif mention <= 5:
        # Linear up to 5 mentions
        mention_score = mention * 0.08
    else:
        # Logarithmic diminishing returns after 5
        mention_score = 0.4 + math.log1p(mention - 5) * 0.1

    # Confidence factor (0.8 baseline + 0.2 from confidence)
    # High confidence memories get slight boost, low confidence slight penalty
    confidence_factor = 0.8 + 0.2 * learning.confidence

    return (value_score + mention_score) * confidence_factor


def compute_temporal_score(
    learning: Learning,
    activity_days: int,
    config: ImportanceConfig,
) -> float:
    """Compute score based on recency and temporal relevance.

    Components:
    - Newness boost: Grace period for new memories to accumulate signals
    - Recency decay: Based on activity days, not calendar days
    - Deadline proximity: Boost for upcoming events (calendar-based)
    - Expiration decay: Trail-off for expiring content

    Args:
        learning: The learning to score
        activity_days: Current cumulative activity day count
        config: Scoring configuration

    Returns:
        Temporal score component (typically 0-3 range before clamping)
    """
    score = 1.0

    # Newness boost (grace period for new memories)
    # New memories get a boost that decays linearly over newness_decay_days
    days_since_creation = activity_days - learning.activity_day_created
    if days_since_creation < config.newness_decay_days:
        newness = config.newness_boost * (1 - days_since_creation / config.newness_decay_days)
        score += newness

    # Recency decay (activity-based, not calendar-based)
    # More recent accesses = higher score
    days_since_access = activity_days - learning.activity_day_accessed
    recency = 1.0 / (1.0 + days_since_access * config.recency_decay_rate)
    score *= recency

    # Deadline proximity boost (calendar-based for real deadlines)
    if learning.happens_at:
        score *= _compute_deadline_multiplier(learning.happens_at)

    # Expiration decay (calendar-based)
    if learning.expires_at:
        score *= _compute_expiration_multiplier(learning.expires_at)

    return score


def _compute_deadline_multiplier(happens_at: str) -> float:
    """Compute boost for upcoming deadlines.

    Events happening soon get progressively higher boost.
    Past events get no boost.

    Args:
        happens_at: ISO timestamp of the event

    Returns:
        Multiplier (1.0 = no change, >1.0 = boost)
    """
    try:
        event_time = datetime.fromisoformat(happens_at)
        now = datetime.now()
        delta = event_time - now

        if delta.total_seconds() < 0:
            # Past event - no boost
            return 1.0

        days_until = delta.total_seconds() / 86400

        if days_until <= 1:
            # Within 24 hours - maximum boost
            return 3.0
        elif days_until <= 7:
            # Within a week - sliding boost
            return 1.0 + 2.0 * (1 - days_until / 7)
        elif days_until <= 30:
            # Within a month - slight boost
            return 1.0 + 0.5 * (1 - days_until / 30)
        else:
            # More than a month away - no boost yet
            return 1.0

    except (ValueError, TypeError):
        return 1.0


def _compute_expiration_multiplier(expires_at: str) -> float:
    """Compute decay for expiring content.

    Content approaching expiration trails off gradually.
    Expired content gets heavily penalized.

    Args:
        expires_at: ISO timestamp of expiration

    Returns:
        Multiplier (1.0 = no change, <1.0 = penalty)
    """
    try:
        expire_time = datetime.fromisoformat(expires_at)
        now = datetime.now()
        delta = expire_time - now

        if delta.total_seconds() < 0:
            # Already expired - heavy penalty (but don't zero out)
            return 0.1

        days_until = delta.total_seconds() / 86400

        if days_until <= 1:
            # Expiring within 24 hours - moderate penalty
            return 0.5
        elif days_until <= 7:
            # Expiring within a week - slight penalty
            return 0.7 + 0.3 * (days_until / 7)
        else:
            # More than a week - no penalty
            return 1.0

    except (ValueError, TypeError):
        return 1.0
