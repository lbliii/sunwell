"""Routing decision dataclass (RFC-030).

The unified output from the router, replacing:
- CognitiveRouter's RoutingDecision (intent, lens, focus)
- TieredAttunement's AttunementResult (tier, confidence)
- Discernment's quick validation (confidence gating)
- Mirror's mood/expertise detection
"""

from dataclasses import dataclass
from typing import Any

from sunwell.planning.routing.types import (
    Complexity,
    ExecutionTier,
    Intent,
    TierBehavior,
    UserExpertise,
    UserMood,
)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """All routing decisions in one immutable struct.

    Thread-safe: Immutable (frozen=True) + no mutable defaults.
    """

    intent: Intent
    complexity: Complexity
    lens: str | None                    # Selected lens (None = no specific lens)
    tools: tuple[str, ...]              # Predicted tools: file_read, file_write, search, terminal
    mood: UserMood
    expertise: UserExpertise
    confidence: float                   # 0.0-1.0 routing confidence
    reasoning: str                      # One-sentence explanation

    # Retrieval hints (derived from intent)
    focus: tuple[str, ...] = ()         # Keywords for retrieval boosting
    secondary_lenses: tuple[str, ...] = ()

    # RFC-070: Skill suggestions based on trigger matching
    suggested_skills: tuple[str, ...] = ()
    """Skills whose triggers match the input."""

    skill_confidence: float = 0.0
    """Confidence in skill suggestions (0.0-1.0)."""

    # RFC-022 Enhancement: Deterministic confidence
    confidence_breakdown: str = ""
    """Explanation of how confidence was calculated."""

    matched_exemplar: str | None = None
    """Name of matched routing exemplar, if any."""

    rubric_confidence: float | None = None
    """Confidence from deterministic rubric (0-1), if calculated."""

    # RFC-022 Enhancement: Tiered execution
    tier: ExecutionTier = ExecutionTier.LIGHT
    """Execution tier based on confidence."""

    @property
    def behavior(self) -> TierBehavior:
        """Get behavior configuration for this decision's tier."""
        return TierBehavior.for_tier(self.tier)

    @property
    def top_k(self) -> int:
        """Retrieval depth based on complexity."""
        return {
            Complexity.TRIVIAL: 3,
            Complexity.STANDARD: 5,
            Complexity.COMPLEX: 8,
        }.get(self.complexity, 5)

    @property
    def threshold(self) -> float:
        """Retrieval threshold based on complexity."""
        return {
            Complexity.TRIVIAL: 0.4,
            Complexity.STANDARD: 0.3,
            Complexity.COMPLEX: 0.2,
        }.get(self.complexity, 0.3)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent.value,
            "complexity": self.complexity.value,
            "lens": self.lens,
            "tools": list(self.tools),
            "mood": self.mood.value,
            "expertise": self.expertise.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "focus": list(self.focus),
            "secondary_lenses": list(self.secondary_lenses),
            "suggested_skills": list(self.suggested_skills),
            "skill_confidence": self.skill_confidence,
            "confidence_breakdown": self.confidence_breakdown,
            "matched_exemplar": self.matched_exemplar,
            "rubric_confidence": self.rubric_confidence,
            "tier": self.tier.value,
            "top_k": self.top_k,
            "threshold": self.threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingDecision:
        """Create from dictionary."""
        return cls(
            intent=Intent(data.get("intent", "code")),
            complexity=Complexity(data.get("complexity", "standard")),
            lens=data.get("lens"),
            tools=tuple(data.get("tools", [])),
            mood=UserMood(data.get("mood", "neutral")),
            expertise=UserExpertise(data.get("expertise", "intermediate")),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
            focus=tuple(data.get("focus", [])),
            secondary_lenses=tuple(data.get("secondary_lenses", [])),
            suggested_skills=tuple(data.get("suggested_skills", [])),
            skill_confidence=float(data.get("skill_confidence", 0.0)),
            confidence_breakdown=data.get("confidence_breakdown", ""),
            matched_exemplar=data.get("matched_exemplar"),
            rubric_confidence=data.get("rubric_confidence"),
            tier=ExecutionTier(data.get("tier", 1)),
        )
