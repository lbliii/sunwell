"""Intent classification for routing."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sunwell.core.types import IntentCategory, Tier
from sunwell.core.lens import Lens


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Result from intent classification."""

    category: IntentCategory
    tier: Tier
    confidence: float
    signals: tuple[str, ...]  # Keywords that triggered this


# Keyword patterns for intent classification
TRIVIAL_PATTERNS = [
    r"\b(typo|indent|format|spacing|whitespace)\b",
    r"\b(fix\s+the\s+typo|correct\s+spelling)\b",
    r"\bminor\s+(fix|change|edit)\b",
]

COMPLEX_PATTERNS = [
    r"\b(architect|design|review|audit)\b",
    r"\b(security|performance|scale|scalability)\b",
    r"\b(refactor|restructure|redesign)\b",
    r"\b(comprehensive|thorough|complete)\s+(review|analysis)\b",
]

AMBIGUOUS_PATTERNS = [
    r"\b(maybe|possibly|might|could)\b",
    r"\b(not\s+sure|uncertain|unclear)\b",
    r"\?.*\?",  # Multiple questions
]


@dataclass
class IntentClassifier:
    """Classifies user intent to determine execution tier.

    Uses keyword signals + optional LLM classification for ambiguous cases.
    """

    lens: Lens

    def classify(self, prompt: str) -> ClassificationResult:
        """Classify a prompt's intent.

        1. Check for keyword triggers in router config
        2. If ambiguous, use LLM classification (optional)
        3. Map to execution tier
        """
        prompt_lower = prompt.lower()
        signals: list[str] = []

        # Check lens router configuration first
        if self.lens.router:
            for tier_config in self.lens.router.tiers:
                for trigger in tier_config.triggers:
                    if trigger.lower() in prompt_lower:
                        signals.append(trigger)
                        return ClassificationResult(
                            category=self._tier_to_category(tier_config.level),
                            tier=tier_config.level,
                            confidence=0.9,
                            signals=tuple(signals),
                        )

        # Check built-in patterns
        tier = self._check_keyword_triggers(prompt_lower, signals)

        if tier is not None:
            return ClassificationResult(
                category=self._tier_to_category(tier),
                tier=tier,
                confidence=0.8,
                signals=tuple(signals),
            )

        # Default to STANDARD tier
        return ClassificationResult(
            category=IntentCategory.STANDARD,
            tier=Tier.STANDARD,
            confidence=0.7,
            signals=(),
        )

    def _check_keyword_triggers(
        self, prompt: str, signals: list[str]
    ) -> Tier | None:
        """Check if prompt matches any tier's keyword triggers."""
        # Check for trivial patterns (FAST_PATH)
        for pattern in TRIVIAL_PATTERNS:
            if match := re.search(pattern, prompt, re.IGNORECASE):
                signals.append(match.group())
                return Tier.FAST_PATH

        # Check for complex patterns (DEEP_LENS)
        for pattern in COMPLEX_PATTERNS:
            if match := re.search(pattern, prompt, re.IGNORECASE):
                signals.append(match.group())
                return Tier.DEEP_LENS

        # Check for ambiguous patterns
        for pattern in AMBIGUOUS_PATTERNS:
            if match := re.search(pattern, prompt, re.IGNORECASE):
                signals.append(match.group())
                # Ambiguous defaults to STANDARD with lower confidence
                return Tier.STANDARD

        return None

    def _tier_to_category(self, tier: Tier) -> IntentCategory:
        """Map tier to intent category."""
        mapping = {
            Tier.FAST_PATH: IntentCategory.TRIVIAL,
            Tier.STANDARD: IntentCategory.STANDARD,
            Tier.DEEP_LENS: IntentCategory.COMPLEX,
        }
        return mapping.get(tier, IntentCategory.STANDARD)
