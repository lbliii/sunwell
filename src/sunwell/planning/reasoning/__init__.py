"""Reasoned Decisions - LLM-driven judgment over rule-based logic (RFC-073).

Replace rule-based decisions throughout Sunwell with reasoned decisions —
LLM-driven judgments that consider context, history, and nuance. Instead
of `if X then Y`, the system asks "given X, what should we do and why?"

Key insight: Traditional software encodes decisions in code. AI-native
software delegates decisions to intelligence. The rules aren't the product —
**the reasoning that generates appropriate responses is the product.**

Components:
- DecisionType: Enum of decision types (severity, recovery, approval, etc.)
- ReasonedDecision: Result of LLM reasoning with confidence and rationale
- Reasoner: Core class that assembles context and invokes LLM
- ConfidenceCalibrator: Learns from outcomes to calibrate confidence

Example:
    >>> from sunwell.reasoning import Reasoner, DecisionType
    >>> reasoner = Reasoner(model=wisdom_model)
    >>> decision = await reasoner.decide(
    ...     DecisionType.SEVERITY_ASSESSMENT,
    ...     {"signal_type": "todo_comment", "content": "validate payments"},
    ... )
    >>> print(decision.outcome)  # "critical"
    >>> print(decision.confidence)  # 0.92
    >>> print(decision.rationale)  # "Payment validation in billing..."

See: RFC-073-reasoned-decisions.md
"""

from sunwell.reasoning.calibration import (
    CalibrationRecord,
    CalibrationStats,
    ConfidenceCalibrator,
)
from sunwell.reasoning.decisions import (
    APPROVAL_OUTCOMES,
    CONFIDENCE_THRESHOLDS,
    DISPLAY_VARIANTS,
    RECOVERY_STRATEGIES,
    SEVERITY_LEVELS,
    DecisionType,
    ReasonedDecision,
    RecoveryDecision,
)
from sunwell.reasoning.enrichment import ContextEnricher
from sunwell.reasoning.fast_classifier import (
    BINARY_TEMPLATE,
    COMPLEXITY_TEMPLATE,
    INTENT_TEMPLATE,
    RISK_TEMPLATE,
    SCORE_TEMPLATE,
    SEVERITY_TEMPLATE,
    ClassificationResult,
    ClassificationTemplate,
    FastClassifier,
    get_recommended_model,
)
from sunwell.reasoning.prompts import PromptBuilder
from sunwell.reasoning.reasoner import Reasoner

__all__ = [
    # Core reasoning (complex decisions, tool calling)
    "DecisionType",
    "ReasonedDecision",
    "RecoveryDecision",
    "Reasoner",
    # Context enrichment
    "ContextEnricher",
    # Prompt building
    "PromptBuilder",
    # Fast classification (simple decisions, JSON output)
    "FastClassifier",
    "ClassificationResult",
    "ClassificationTemplate",
    "get_recommended_model",
    # Calibration
    "ConfidenceCalibrator",
    "CalibrationRecord",
    "CalibrationStats",
    # Constants
    "SEVERITY_LEVELS",
    "RECOVERY_STRATEGIES",
    "DISPLAY_VARIANTS",
    "APPROVAL_OUTCOMES",
    "CONFIDENCE_THRESHOLDS",
    # Templates
    "SEVERITY_TEMPLATE",
    "COMPLEXITY_TEMPLATE",
    "INTENT_TEMPLATE",
    "RISK_TEMPLATE",
    "BINARY_TEMPLATE",
    "SCORE_TEMPLATE",
]
