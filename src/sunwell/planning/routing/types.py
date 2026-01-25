"""Routing type definitions (RFC-030).

Core enums and types for the unified routing system:
- Intent: Primary task classification
- Complexity: Task complexity levels
- UserMood: Detected user emotional state
- UserExpertise: Detected user expertise level
- ExecutionTier: Adaptive response depth tiers
- TierBehavior: Behavior configuration per tier
"""

from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    """Primary intent for task classification.

    Simplified from CognitiveRouter's 8 intents to 6 core intents
    that align with common user patterns.
    """

    CODE = "code"           # Write, modify, or generate code
    EXPLAIN = "explain"     # Explain concepts, code, or decisions
    DEBUG = "debug"         # Fix bugs, troubleshoot errors
    CHAT = "chat"           # Casual conversation, greetings
    SEARCH = "search"       # Find information, explore codebase
    REVIEW = "review"       # Review code, audit, analyze


class Complexity(str, Enum):
    """Task complexity levels."""

    TRIVIAL = "trivial"     # Single-file, obvious change
    STANDARD = "standard"   # Multi-file, typical task
    COMPLEX = "complex"     # Multi-faceted, needs planning


class UserMood(str, Enum):
    """Detected user emotional state.

    Affects response tone and verbosity.
    """

    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"  # ALL CAPS, urgency markers
    CURIOUS = "curious"        # Questions, exploration
    RUSHED = "rushed"          # Time pressure indicators
    CONFUSED = "confused"      # Uncertainty markers


class UserExpertise(str, Enum):
    """Detected user expertise level.

    Affects explanation depth and assumed knowledge.
    """

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


# =============================================================================
# Execution Tiers (RFC-022 Enhancement)
# =============================================================================


class ExecutionTier(int, Enum):
    """Execution tiers for adaptive response depth.

    Higher confidence → faster, lighter response.
    Lower confidence → more reasoning, possible confirmation.
    """

    FAST = 0    # No analysis, direct dispatch, ~50ms
    LIGHT = 1   # Brief acknowledgment, auto-proceed, ~200ms
    FULL = 2    # Full CoT reasoning, confirmation required, ~500ms


@dataclass(frozen=True, slots=True)
class TierBehavior:
    """Behavior configuration for each execution tier.

    Affects how the agent responds based on routing confidence.
    """

    show_reasoning: bool
    """Whether to show chain-of-thought reasoning."""

    require_confirmation: bool
    """Whether to ask for confirmation before proceeding."""

    output_format: str  # "compact" | "standard" | "detailed"
    """Verbosity of the response."""

    @classmethod
    def for_tier(cls, tier: ExecutionTier) -> "TierBehavior":
        """Get behavior configuration for a tier."""
        behaviors = {
            ExecutionTier.FAST: cls(
                show_reasoning=False,
                require_confirmation=False,
                output_format="compact",
            ),
            ExecutionTier.LIGHT: cls(
                show_reasoning=False,
                require_confirmation=False,
                output_format="standard",
            ),
            ExecutionTier.FULL: cls(
                show_reasoning=True,
                require_confirmation=True,
                output_format="detailed",
            ),
        }
        return behaviors[tier]


def determine_tier(confidence: float, has_shortcut: bool) -> ExecutionTier:
    """Determine execution tier from confidence score.

    Args:
        confidence: 0.0-1.0 confidence score
        has_shortcut: Whether request is an explicit shortcut (::command)

    Returns:
        ExecutionTier for the given confidence level
    """
    if has_shortcut or confidence >= 0.85:
        return ExecutionTier.FAST
    elif confidence >= 0.60:
        return ExecutionTier.LIGHT
    else:
        return ExecutionTier.FULL


