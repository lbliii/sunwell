"""Domain Classification for Expertise-Aware Planning (RFC-039).

Fast, local classification of goal domain to enable automatic lens selection.
Uses keyword matching with weighted signals - no LLM required.

Example:
    >>> classifier = DomainClassifier()
    >>> result = classifier.classify("Write API documentation for the auth module")
    >>> result.domain
    Domain.DOCUMENTATION
    >>> result.confidence
    0.85
    >>> result.signals
    ['docs', 'documentation', 'api']
"""


from dataclasses import dataclass, field
from enum import Enum


class Domain(Enum):
    """Recognized goal domains."""

    DOCUMENTATION = "documentation"
    CODE = "code"
    REVIEW = "review"
    PROJECT = "project"
    TEST = "test"
    REFACTOR = "refactor"
    GENERAL = "general"


@dataclass(frozen=True, slots=True)
class DomainClassification:
    """Result of domain classification."""

    domain: Domain
    confidence: float  # 0.0 to 1.0
    signals: tuple[str, ...]  # Keywords that triggered classification

    @property
    def is_confident(self) -> bool:
        """Whether classification confidence is high enough for expertise loading."""
        return self.confidence >= 0.3


# Domain signal definitions with weights
# Higher weight = stronger signal
DOMAIN_SIGNALS: dict[Domain, dict[str, float]] = {
    Domain.DOCUMENTATION: {
        # Strong signals
        "documentation": 1.0,
        "docs": 1.0,
        "document": 0.9,
        "write docs": 1.0,
        "api docs": 1.0,
        "readme": 0.9,
        # Medium signals
        "tutorial": 0.8,
        "guide": 0.7,
        "explain": 0.6,
        "describe": 0.5,
        "quickstart": 0.8,
        "getting started": 0.8,
        # Diataxis types
        "how-to": 0.8,
        "how to": 0.7,
        "reference": 0.6,
        "explanation": 0.7,
    },
    Domain.CODE: {
        # Strong signals
        "implement": 1.0,
        "create function": 1.0,
        "write code": 1.0,
        "build": 0.8,
        "code": 0.7,
        "add feature": 0.9,
        "new feature": 0.9,
        # Medium signals
        "module": 0.6,
        "class": 0.5,
        "api": 0.5,
        "endpoint": 0.7,
        "cli": 0.6,
        "script": 0.7,
    },
    Domain.REVIEW: {
        # Strong signals
        "review": 1.0,
        "code review": 1.0,
        "audit": 0.9,
        "security": 0.8,
        # Medium signals
        "check": 0.5,
        "analyze": 0.6,
        "performance": 0.6,
        "vulnerability": 0.8,
        "best practices": 0.7,
    },
    Domain.TEST: {
        # Strong signals
        "test": 0.9,
        "tests": 0.9,
        "write tests": 1.0,
        "unit test": 1.0,
        "integration test": 1.0,
        # Medium signals
        "coverage": 0.7,
        "pytest": 0.8,
        "mock": 0.6,
        "fixture": 0.7,
    },
    Domain.REFACTOR: {
        # Strong signals
        "refactor": 1.0,
        "refactoring": 1.0,
        "restructure": 0.9,
        "reorganize": 0.8,
        # Medium signals
        "clean up": 0.7,
        "simplify": 0.6,
        "extract": 0.5,
        "rename": 0.5,
    },
    Domain.PROJECT: {
        # Strong signals
        "project": 0.8,
        "setup": 0.7,
        "initialize": 0.9,
        "scaffold": 1.0,
        "bootstrap": 0.9,
        # Medium signals
        "structure": 0.6,
        "directory": 0.5,
        "config": 0.5,
        "ci/cd": 0.8,
        "pipeline": 0.6,
    },
}

# Negative signals that reduce confidence for specific domains
NEGATIVE_SIGNALS: dict[Domain, dict[str, float]] = {
    Domain.DOCUMENTATION: {
        "fix bug": -0.5,
        "implement": -0.3,
        "refactor": -0.4,
    },
    Domain.CODE: {
        "document": -0.4,
        "review": -0.3,
    },
}


@dataclass
class DomainClassifier:
    """Classify goals into domains for expertise selection.

    Uses weighted keyword matching for fast, local classification.
    No LLM required - purely heuristic-based.

    Example:
        >>> classifier = DomainClassifier()
        >>> result = classifier.classify("Write docs for the CLI module")
        >>> result.domain
        Domain.DOCUMENTATION
    """

    # Custom signal overrides
    custom_signals: dict[Domain, dict[str, float]] = field(default_factory=dict)

    # Minimum confidence to return a domain (else GENERAL)
    min_confidence: float = 0.1

    def classify(self, goal: str) -> DomainClassification:
        """Classify a goal into a domain.

        Args:
            goal: The user's goal string

        Returns:
            DomainClassification with domain, confidence, and matched signals
        """
        goal_lower = goal.lower()

        # Score each domain
        domain_scores: dict[Domain, tuple[float, list[str]]] = {}

        for domain in Domain:
            if domain == Domain.GENERAL:
                continue

            score, signals = self._score_domain(goal_lower, domain)
            domain_scores[domain] = (score, signals)

        # Find best domain
        if not domain_scores:
            return DomainClassification(
                domain=Domain.GENERAL,
                confidence=0.0,
                signals=(),
            )

        best_domain = max(domain_scores, key=lambda d: domain_scores[d][0])
        best_score, best_signals = domain_scores[best_domain]

        # Normalize confidence (cap at 1.0)
        confidence = min(best_score, 1.0)

        # Fall back to GENERAL if confidence too low
        if confidence < self.min_confidence:
            return DomainClassification(
                domain=Domain.GENERAL,
                confidence=confidence,
                signals=tuple(best_signals),
            )

        return DomainClassification(
            domain=best_domain,
            confidence=confidence,
            signals=tuple(best_signals),
        )

    def _score_domain(
        self,
        goal_lower: str,
        domain: Domain,
    ) -> tuple[float, list[str]]:
        """Calculate score for a domain.

        Returns (score, matched_signals).
        """
        # Get signals for this domain
        signals = DOMAIN_SIGNALS.get(domain, {})
        custom = self.custom_signals.get(domain, {})

        # Merge custom signals (custom overrides default)
        all_signals = {**signals, **custom}

        score = 0.0
        matched = []

        for signal, weight in all_signals.items():
            if signal in goal_lower:
                score += weight
                matched.append(signal)

        # Apply negative signals
        negative = NEGATIVE_SIGNALS.get(domain, {})
        for signal, penalty in negative.items():
            if signal in goal_lower:
                score += penalty  # penalty is negative

        return (score, matched)

    def add_signal(self, domain: Domain, signal: str, weight: float = 1.0) -> None:
        """Add a custom signal for a domain.

        Args:
            domain: Target domain
            signal: Keyword or phrase to match (lowercase)
            weight: Signal weight (0.0 to 1.0)
        """
        if domain not in self.custom_signals:
            self.custom_signals[domain] = {}
        self.custom_signals[domain][signal.lower()] = weight


# Convenience function for quick classification
def classify_domain(goal: str) -> DomainClassification:
    """Classify a goal into a domain.

    Convenience function using default DomainClassifier.

    Args:
        goal: The user's goal string

    Returns:
        DomainClassification with domain, confidence, and matched signals
    """
    return DomainClassifier().classify(goal)
