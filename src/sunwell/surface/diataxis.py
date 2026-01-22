"""Diataxis Detection — Content type classification (RFC-086).

Detects Diataxis content type (TUTORIAL, HOW_TO, EXPLANATION, REFERENCE)
from document content and structure.
"""


import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DiataxisType = Literal["TUTORIAL", "HOW_TO", "EXPLANATION", "REFERENCE"]


@dataclass(frozen=True, slots=True)
class DiataxisSignal:
    """A signal contributing to Diataxis type detection."""

    dtype: DiataxisType
    """The Diataxis type this signal indicates."""

    weight: float
    """Signal weight (0.0-1.0)."""

    reason: str
    """Why this signal was detected."""


@dataclass(frozen=True, slots=True)
class DiataxisDetection:
    """Result of Diataxis content type detection."""

    detected_type: DiataxisType | None
    """Detected content type, or None if unclear."""

    confidence: float
    """Confidence score (0.0-1.0)."""

    signals: tuple[DiataxisSignal, ...]
    """Signals that contributed to detection."""

    scores: dict[str, float] = field(default_factory=dict)
    """Per-type scores for mixed content detection."""

    mixed_warning: str | None = None
    """Warning if content mixes types."""


# =============================================================================
# DIATAXIS SIGNALS
# =============================================================================

DIATAXIS_SIGNALS: dict[DiataxisType, dict[str, tuple[str, ...] | float]] = {
    "TUTORIAL": {
        "triggers": (
            "tutorial",
            "getting started",
            "learn",
            "first steps",
            "quickstart",
            "your first",
            "beginner",
            "introduction to",
            "learn how",
        ),
        "structure": (
            "learning objectives",
            "prerequisites",
            "step 1",
            "next steps",
            "what you'll learn",
            "by the end",
        ),
        "weight": 1.0,
    },
    "HOW_TO": {
        "triggers": (
            "how to",
            "guide",
            "configure",
            "set up",
            "deploy",
            "fix",
            "troubleshoot",
            "install",
            "migrate",
            "upgrade",
        ),
        "structure": (
            "goal",
            "steps",
            "troubleshooting",
            "before you begin",
            "procedure",
        ),
        "weight": 1.0,
    },
    "EXPLANATION": {
        "triggers": (
            "understand",
            "architecture",
            "concepts",
            "overview",
            "why",
            "how it works",
            "background",
            "theory",
            "design",
        ),
        "structure": (
            "context",
            "how it works",
            "design",
            "rationale",
            "key concepts",
        ),
        "weight": 1.0,
    },
    "REFERENCE": {
        "triggers": (
            "reference",
            "api",
            "parameters",
            "configuration",
            "options",
            "specification",
            "schema",
            "glossary",
        ),
        "structure": (
            "table",
            "parameters",
            "returns",
            "examples",
            "syntax",
            "properties",
        ),
        "weight": 1.0,
    },
}


def detect_diataxis(content: str, file_path: Path | None = None) -> DiataxisDetection:
    """Detect Diataxis content type from document.

    Args:
        content: Document content
        file_path: Optional file path for filename-based signals

    Returns:
        DiataxisDetection with type, confidence, and signals

    Example:
        >>> detection = detect_diataxis(doc_content, Path("docs/getting-started.md"))
        >>> detection.detected_type
        'TUTORIAL'
        >>> detection.confidence
        0.87
    """
    scores: dict[DiataxisType, float] = {
        "TUTORIAL": 0.0,
        "HOW_TO": 0.0,
        "EXPLANATION": 0.0,
        "REFERENCE": 0.0,
    }
    signals: list[DiataxisSignal] = []

    content_lower = content.lower()

    # Extract intro (first 500 chars) for trigger matching
    intro = content_lower[:500]

    # Extract filename if provided
    filename = file_path.stem.lower() if file_path else ""

    # Check each type's signals
    for dtype, config in DIATAXIS_SIGNALS.items():
        triggers = config["triggers"]
        structure = config["structure"]

        # Check triggers in filename (high weight)
        for trigger in triggers:  # type: ignore
            if trigger.replace(" ", "-") in filename or trigger.replace(" ", "_") in filename:
                scores[dtype] += 0.3
                signals.append(DiataxisSignal(dtype, 0.3, f"'{trigger}' in filename"))

        # Check triggers in intro (medium weight)
        for trigger in triggers:  # type: ignore
            if trigger in intro:
                scores[dtype] += 0.2
                signals.append(DiataxisSignal(dtype, 0.2, f"'{trigger}' in introduction"))

        # Check structure patterns in full content (lower weight)
        for pattern in structure:  # type: ignore
            # Use word boundary matching
            if re.search(rf"\b{re.escape(pattern)}\b", content_lower):
                scores[dtype] += 0.1
                signals.append(DiataxisSignal(dtype, 0.1, f"'{pattern}' structure detected"))

    # Additional structural signals
    scores = _detect_structural_signals(content, scores, signals)

    # Find best type
    total_score = sum(scores.values())
    if total_score == 0:
        return DiataxisDetection(
            detected_type=None,
            confidence=0.0,
            signals=tuple(signals),
            scores={k: 0.0 for k in scores},
        )

    best_type = max(scores, key=lambda t: scores[t])
    confidence = scores[best_type] / total_score

    # Check for mixed content
    mixed_warning = _check_mixed_content(scores, best_type)

    # Only return type if confidence is above threshold
    detected = best_type if confidence > 0.4 else None

    return DiataxisDetection(
        detected_type=detected,
        confidence=round(confidence, 2),
        signals=tuple(signals),
        scores={k: round(v, 2) for k, v in scores.items()},
        mixed_warning=mixed_warning,
    )


def _detect_structural_signals(
    content: str,
    scores: dict[DiataxisType, float],
    signals: list[DiataxisSignal],
) -> dict[DiataxisType, float]:
    """Detect structural signals from content patterns.

    Args:
        content: Document content
        scores: Current scores to update
        signals: Signal list to append to

    Returns:
        Updated scores
    """
    # Count numbered steps (suggests TUTORIAL or HOW_TO)
    step_pattern = r"^#{1,3}\s*(step\s+\d+|[0-9]+\.)"
    step_matches = len(re.findall(step_pattern, content, re.MULTILINE | re.IGNORECASE))

    if step_matches >= 3:
        scores["TUTORIAL"] += 0.15
        scores["HOW_TO"] += 0.1
        signals.append(DiataxisSignal("TUTORIAL", 0.15, f"{step_matches} numbered steps"))

    # Count code blocks (suggests REFERENCE or HOW_TO)
    code_blocks = len(re.findall(r"```\w*\n", content))

    if code_blocks >= 5:
        scores["REFERENCE"] += 0.1
        signals.append(DiataxisSignal("REFERENCE", 0.1, f"{code_blocks} code blocks"))
    elif code_blocks >= 2:
        scores["HOW_TO"] += 0.05
        signals.append(DiataxisSignal("HOW_TO", 0.05, f"{code_blocks} code blocks"))

    # Count tables (suggests REFERENCE)
    tables = len(re.findall(r"\|[^|]+\|[^|]+\|", content))

    if tables >= 5:
        scores["REFERENCE"] += 0.2
        signals.append(DiataxisSignal("REFERENCE", 0.2, "Multiple tables detected"))

    # Check for Q&A pattern (suggests EXPLANATION)
    qa_pattern = r"\*\*(why|what|how)\b.*\?\*\*"
    if re.search(qa_pattern, content, re.IGNORECASE):
        scores["EXPLANATION"] += 0.1
        signals.append(DiataxisSignal("EXPLANATION", 0.1, "Q&A format detected"))

    # Check for "Note:" or "Warning:" (neutral but suggests docs)
    if re.search(r"^(?:note|warning|tip|important):", content, re.MULTILINE | re.IGNORECASE):
        scores["HOW_TO"] += 0.05

    return scores


def _check_mixed_content(
    scores: dict[DiataxisType, float],
    best_type: DiataxisType,
) -> str | None:
    """Check if content mixes Diataxis types.

    Args:
        scores: Type scores
        best_type: Best detected type

    Returns:
        Warning message if mixed, None otherwise
    """
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])

    if len(sorted_scores) >= 2:
        first_type, first_score = sorted_scores[0]
        second_type, second_score = sorted_scores[1]

        # If second type has >30% of first type's score, warn
        if first_score > 0 and second_score > first_score * 0.3:
            return (
                f"Mixed content types detected: {first_type} + {second_type}. "
                f"Consider splitting into separate pages."
            )

    return None


def check_diataxis_purity(detection: DiataxisDetection) -> list[str]:
    """Check if document maintains Diataxis purity.

    Args:
        detection: Detection result

    Returns:
        List of warning messages (empty if pure)
    """
    warnings = []

    if detection.mixed_warning:
        warnings.append(detection.mixed_warning)

    if detection.confidence < 0.5:
        warnings.append(
            f"Low confidence ({detection.confidence:.0%}) in content type detection. "
            f"Consider clarifying the document's purpose."
        )

    return warnings


def suggest_diataxis_type(goal: str) -> DiataxisType:
    """Suggest appropriate Diataxis type for a writing goal.

    Args:
        goal: Description of what to write

    Returns:
        Suggested Diataxis type
    """
    goal_lower = goal.lower()

    # Check for clear indicators
    for dtype, config in DIATAXIS_SIGNALS.items():
        for trigger in config["triggers"]:  # type: ignore
            if trigger in goal_lower:
                return dtype

    # Default based on common patterns
    if any(word in goal_lower for word in ("teach", "learn", "new user", "beginner")):
        return "TUTORIAL"
    if any(word in goal_lower for word in ("accomplish", "task", "fix", "deploy")):
        return "HOW_TO"
    if any(word in goal_lower for word in ("explain", "understand", "architecture")):
        return "EXPLANATION"
    if any(word in goal_lower for word in ("api", "all options", "complete list")):
        return "REFERENCE"

    # Default to HOW_TO as most common
    return "HOW_TO"
