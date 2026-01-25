"""Decision types for LLM-driven judgment (RFC-073).

Replaces rule-based decisions with reasoned judgments that consider
context, history, and nuance. Every `match` statement, every severity
mapping, every threshold check is a candidate for reasoned judgment.

Key insight: Traditional software encodes decisions in code.
AI-native software delegates decisions to intelligence.

Example:
    >>> decision = ReasonedDecision(
    ...     decision_type=DecisionType.SEVERITY_ASSESSMENT,
    ...     outcome="critical",
    ...     confidence=0.92,
    ...     rationale="Payment validation in billing webhook is critical path",
    ...     context_used=("hot_path", "downstream_artifacts", "past_failure"),
    ... )
    >>> decision.is_confident
    True
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DecisionType(Enum):
    """Types of decisions that can be reasoned about.

    Organized by phase:
    - Phase 1: Signal Assessment (severity, fixability, priority)
    - Phase 2: Error Recovery (diagnosis, strategy, retry)
    - Phase 3: Approval & Escalation (approval, escalation, risk)
    - Phase 4: Learning (root cause, patterns, preferences)
    """

    # Phase 1: Signal Assessment
    SEVERITY_ASSESSMENT = "severity_assessment"
    """Assess severity of a code signal (TODO, FIXME, type error, etc.)."""

    AUTO_FIXABLE = "auto_fixable"
    """Determine if a signal can be auto-fixed without human judgment."""

    GOAL_PRIORITY = "goal_priority"
    """Prioritize goals based on urgency, dependencies, and patterns."""

    # Phase 2: Error Recovery
    FAILURE_DIAGNOSIS = "failure_diagnosis"
    """Diagnose the root cause of a failure."""

    RECOVERY_STRATEGY = "recovery_strategy"
    """Choose a recovery strategy for a failure."""

    RETRY_VS_ABORT = "retry_vs_abort"
    """Decide whether to retry an operation or abort."""

    # Phase 3: Approval & Escalation
    SEMANTIC_APPROVAL = "semantic_approval"
    """Decide if a change can be auto-approved based on semantic analysis."""

    ESCALATION_OPTIONS = "escalation_options"
    """Generate contextual escalation options for human review."""

    RISK_ASSESSMENT = "risk_assessment"
    """Assess the risk of a proposed change."""

    # Phase 4: Learning
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    """Analyze the root cause of a failure for memory."""

    PATTERN_EXTRACTION = "pattern_extraction"
    """Extract patterns from user behavior or code."""

    PREFERENCE_INFERENCE = "preference_inference"
    """Infer user preferences from feedback signals."""

    # Display (TypeScript frontend)
    DISPLAY_VARIANT = "display_variant"
    """Decide how to display a decision in the UI (badge, banner, modal)."""


@dataclass(frozen=True, slots=True)
class ReasonedDecision:
    """Result of LLM reasoning about a decision.

    Every decision includes:
    - outcome: The actual decision (type depends on decision_type)
    - confidence: How certain the reasoning is (0.0 - 1.0)
    - rationale: Human-readable explanation for the decision
    - context_used: What factors influenced the decision
    - similar_decisions: IDs of past similar decisions (for consistency)

    Confidence thresholds:
    - >= 0.90: High confidence, silent action
    - >= 0.70: Moderate, show rationale but proceed
    - >= 0.50: Low, require confirmation
    - <  0.50: Uncertain, fallback to rules

    Example:
        >>> decision = ReasonedDecision(
        ...     decision_type=DecisionType.SEVERITY_ASSESSMENT,
        ...     outcome="critical",
        ...     confidence=0.92,
        ...     rationale="Payment validation TODO in billing.py is in hot path",
        ... )
        >>> decision.is_confident
        True
        >>> decision.confidence_level
        'high'
    """

    decision_type: DecisionType
    """What kind of decision this is."""

    outcome: Any
    """The decision result. Type depends on decision_type:
    - SEVERITY_ASSESSMENT: Literal["critical", "high", "medium", "low"]
    - AUTO_FIXABLE: bool
    - GOAL_PRIORITY: int (1-10)
    - RECOVERY_STRATEGY: Literal["retry", "retry_different", "escalate", "abort"]
    - SEMANTIC_APPROVAL: Literal["approve", "flag", "deny"]
    - DISPLAY_VARIANT: Literal["badge", "banner", "modal", "silent"]
    """

    confidence: float
    """Confidence in this decision (0.0 - 1.0)."""

    rationale: str
    """Human-readable explanation for why this decision was made."""

    similar_decisions: tuple[str, ...] = ()
    """IDs of past similar decisions (for consistency checking)."""

    context_used: tuple[str, ...] = ()
    """What context factors influenced this decision."""

    @property
    def is_confident(self) -> bool:
        """Whether confidence meets threshold for autonomous action (>=70%)."""
        return self.confidence >= 0.70

    @property
    def is_high_confidence(self) -> bool:
        """Whether confidence is high enough for silent action (>=90%)."""
        return self.confidence >= 0.90

    @property
    def confidence_level(self) -> str:
        """Human-readable confidence level.

        Returns:
            'high' (90-100%), 'moderate' (70-89%), 'low' (50-69%), 'uncertain' (<50%)
        """
        if self.confidence >= 0.90:
            return "high"
        elif self.confidence >= 0.70:
            return "moderate"
        elif self.confidence >= 0.50:
            return "low"
        else:
            return "uncertain"

    @property
    def confidence_emoji(self) -> str:
        """Emoji indicator for confidence level."""
        if self.confidence >= 0.90:
            return "🟢"
        elif self.confidence >= 0.70:
            return "🟡"
        elif self.confidence >= 0.50:
            return "🟠"
        else:
            return "🔴"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "decision_type": self.decision_type.value,
            "outcome": self.outcome,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "similar_decisions": list(self.similar_decisions),
            "context_used": list(self.context_used),
            "confidence_level": self.confidence_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasonedDecision:
        """Create from dictionary (e.g., from JSON)."""
        return cls(
            decision_type=DecisionType(data["decision_type"]),
            outcome=data["outcome"],
            confidence=data["confidence"],
            rationale=data["rationale"],
            similar_decisions=tuple(data.get("similar_decisions", [])),
            context_used=tuple(data.get("context_used", [])),
        )


@dataclass(frozen=True, slots=True)
class RecoveryDecision(ReasonedDecision):
    """Specialized decision for error recovery (Phase 2).

    Extends ReasonedDecision with recovery-specific fields:
    - strategy: The recovery approach to take
    - retry_hint: Guidance for retry attempt (if strategy is retry)
    - escalation_reason: Why human intervention is needed (if strategy is escalate)
    - past_successful_recovery: What worked for similar failures before
    """

    strategy: str = "abort"
    """Recovery strategy: 'retry', 'retry_different', 'escalate', 'abort'."""

    retry_hint: str | None = None
    """Guidance for how to retry (if strategy is retry or retry_different)."""

    escalation_reason: str | None = None
    """Why human intervention is needed (if strategy is escalate)."""

    similar_failure_ids: tuple[str, ...] = ()
    """IDs of similar past failures."""

    past_successful_recovery: str | None = None
    """What recovery strategy worked for similar failures."""


# Severity levels for type safety
SEVERITY_LEVELS = frozenset({"critical", "high", "medium", "low"})

# Recovery strategies for type safety
RECOVERY_STRATEGIES = frozenset({"retry", "retry_different", "escalate", "abort"})

# Display variants for type safety
DISPLAY_VARIANTS = frozenset({"badge", "banner", "modal", "silent"})

# Approval outcomes for type safety
APPROVAL_OUTCOMES = frozenset({"approve", "flag", "deny"})


# Confidence thresholds (shared across Python, Rust, TypeScript)
CONFIDENCE_THRESHOLDS = {
    "autonomous_action": 0.70,  # Can act without human approval
    "high_confidence": 0.90,  # Skip confirmation dialogs
    "needs_confirmation": 0.70,  # Show rationale in UI
    "escalate_to_human": 0.50,  # Require explicit approval
    "fallback_to_rules": 0.50,  # Use heuristic instead of reasoning
}
