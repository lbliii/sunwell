"""Confidence scoring and aggregation for model nodes (RFC-100).

Provides infrastructure for:
1. Evidence-based confidence scores
2. Provenance tracking
3. Hierarchical confidence propagation

Confidence Formula:
    confidence = Evidence(40) + Consistency(30) + Recency(15) + Tests(15) = 0-100%
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean
from typing import Any


class ConfidenceLevel(Enum):
    """Confidence band levels with emoji indicators."""

    HIGH = "high"           # 🟢 90-100%
    MODERATE = "moderate"   # 🟡 70-89%
    LOW = "low"             # 🟠 50-69%
    UNCERTAIN = "uncertain" # 🔴 <50%


def score_to_band(score: float) -> ConfidenceLevel:
    """Convert a confidence score (0.0-1.0) to a band.

    Args:
        score: Confidence score from 0.0 to 1.0

    Returns:
        ConfidenceLevel enum value
    """
    pct = score * 100
    if pct >= 90:
        return ConfidenceLevel.HIGH
    elif pct >= 70:
        return ConfidenceLevel.MODERATE
    elif pct >= 50:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.UNCERTAIN


def band_to_emoji(level: ConfidenceLevel) -> str:
    """Get emoji for a confidence level."""
    return {
        ConfidenceLevel.HIGH: "🟢",
        ConfidenceLevel.MODERATE: "🟡",
        ConfidenceLevel.LOW: "🟠",
        ConfidenceLevel.UNCERTAIN: "🔴",
    }[level]


@dataclass(frozen=True, slots=True)
class Evidence:
    """Provenance for a confidence claim.

    Evidence traces link claims to their sources:
    - Source files and line ranges
    - Agent reasoning that led to the claim
    - Confidence factors that contributed to the score
    """

    source_file: str
    """Path to source file (relative to workspace root)."""

    line_range: tuple[int, int] | None = None
    """Line range in source (start, end), or None for entire file."""

    reasoning: str = ""
    """Explanation of how this evidence supports the claim."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When this evidence was collected."""

    evidence_type: str = "code"
    """Type of evidence: 'code', 'test', 'memory', 'user', 'inference'."""

    weight: float = 1.0
    """Weight of this evidence in confidence calculation (0.0-1.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_file": self.source_file,
            "line_range": list(self.line_range) if self.line_range else None,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
            "evidence_type": self.evidence_type,
            "weight": self.weight,
        }


@dataclass
class ModelNode:
    """A node in the project mental model with confidence scoring.

    Model nodes represent components/modules in the project model:
    - Services, packages, modules
    - With confidence scores that propagate through hierarchy
    - With provenance traces to evidence
    """

    name: str
    """Name of this component/module."""

    confidence: float
    """Confidence score from 0.0 to 1.0."""

    provenance: tuple[Evidence, ...] = ()
    """Evidence supporting this confidence score."""

    children: tuple[ModelNode, ...] = ()
    """Child nodes in the hierarchy."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional node-specific metadata."""

    @property
    def level(self) -> ConfidenceLevel:
        """Get confidence level band."""
        return score_to_band(self.confidence)

    @property
    def emoji(self) -> str:
        """Get emoji indicator for confidence level."""
        return band_to_emoji(self.level)

    def aggregate_confidence(self) -> float:
        """Roll up confidence from children (conservative approach).

        Returns the minimum of:
        - This node's direct confidence
        - Average of children's aggregated confidence

        This ensures parent confidence doesn't exceed child confidence,
        preventing false confidence in partially-understood areas.
        """
        if not self.children:
            return self.confidence

        child_conf = mean(c.aggregate_confidence() for c in self.children)
        return min(self.confidence, child_conf)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "confidence": self.confidence,
            "level": self.level.value,
            "emoji": self.emoji,
            "aggregated_confidence": self.aggregate_confidence(),
            "provenance": [e.to_dict() for e in self.provenance],
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ConfidenceFactors:
    """Breakdown of factors contributing to confidence score.

    The formula: Evidence(40) + Consistency(30) + Recency(15) + Tests(15)
    """

    evidence_score: float = 0.0
    """Score from direct code evidence (0.0-1.0, weight 40%)."""

    consistency_score: float = 0.0
    """Score from cross-validation consistency (0.0-1.0, weight 30%)."""

    recency_score: float = 0.0
    """Score from recency of information (0.0-1.0, weight 15%)."""

    test_score: float = 0.0
    """Score from test coverage/success (0.0-1.0, weight 15%)."""

    @property
    def total(self) -> float:
        """Calculate weighted total confidence score."""
        return (
            self.evidence_score * 0.40 +
            self.consistency_score * 0.30 +
            self.recency_score * 0.15 +
            self.test_score * 0.15
        )


def aggregate_confidence(
    nodes: list[ModelNode],
    strategy: str = "conservative",
) -> float:
    """Aggregate confidence across multiple nodes.

    Args:
        nodes: List of model nodes
        strategy: Aggregation strategy:
            - 'conservative': Use minimum (default)
            - 'average': Use mean
            - 'weighted': Use weighted mean by evidence count

    Returns:
        Aggregated confidence score (0.0-1.0)
    """
    if not nodes:
        return 1.0  # No nodes = no uncertainty

    scores = [n.aggregate_confidence() for n in nodes]

    if strategy == "conservative":
        return min(scores)
    elif strategy == "average":
        return mean(scores)
    elif strategy == "weighted":
        # Weight by number of evidence items
        weights = [len(n.provenance) + 1 for n in nodes]  # +1 to avoid zero weight
        weighted_sum = sum(s * w for s, w in zip(scores, weights, strict=True))
        return weighted_sum / sum(weights)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def calculate_confidence(
    evidence: list[Evidence],
    consistency_checks: list[bool] | None = None,
    days_since_update: int | None = None,
    test_results: list[bool] | None = None,
) -> tuple[float, ConfidenceFactors]:
    """Calculate confidence score from evidence and factors.

    Args:
        evidence: List of evidence items
        consistency_checks: Results of consistency checks (True=passed)
        days_since_update: Days since last update
        test_results: Results of related tests (True=passed)

    Returns:
        Tuple of (total_score, factors_breakdown)
    """
    # Evidence score (40%)
    if evidence:
        weighted_evidence = sum(e.weight for e in evidence)
        evidence_score = min(1.0, weighted_evidence / 3)  # 3 strong evidence = 100%
    else:
        evidence_score = 0.0

    # Consistency score (30%)
    if consistency_checks:
        consistency_score = sum(consistency_checks) / len(consistency_checks)
    else:
        consistency_score = 0.5  # Neutral if not checked

    # Recency score (15%)
    if days_since_update is not None:
        if days_since_update <= 7:
            recency_score = 1.0
        elif days_since_update <= 30:
            recency_score = 0.9
        elif days_since_update <= 90:
            recency_score = 0.7
        elif days_since_update <= 180:
            recency_score = 0.5
        else:
            recency_score = 0.3
    else:
        recency_score = 0.5  # Neutral if unknown

    # Test score (15%)
    test_score = sum(test_results) / len(test_results) if test_results else 0.5

    factors = ConfidenceFactors(
        evidence_score=evidence_score,
        consistency_score=consistency_score,
        recency_score=recency_score,
        test_score=test_score,
    )

    return factors.total, factors
