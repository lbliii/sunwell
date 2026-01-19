"""Interference Patterns — Agreement/Disagreement as Signal.

The hypothesis: When multiple perspectives agree, confidence should be high.
When they disagree, that's valuable information—edge case, ambiguity, or
model uncertainty.

Like wave interference:
- Constructive: Waves align → amplified signal (high confidence)
- Destructive: Waves cancel → weak signal (low confidence, needs escalation)

The PATTERN of agreement/disagreement is itself information.

Example:
    >>> from sunwell.experiments.interference import (
    ...     interference_scan,
    ...     measure_agreement,
    ... )
    >>>
    >>> result = await interference_scan(
    ...     task="Is 'twice X' multiplication or addition?",
    ...     model=OllamaModel("gemma3:1b"),
    ...     n_perspectives=5,
    ... )
    >>> print(f"Agreement: {result.agreement_score:.2f}")
    >>> print(f"Prediction: {result.consensus_answer}")
    >>> if result.agreement_score < 0.6:
    ...     print("Low agreement - consider escalation")
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True)
class PerspectiveResponse:
    """Response from a single perspective."""

    perspective_name: str
    """Name of the perspective (e.g., 'skeptic', 'optimist')."""

    prompt: str
    """The prompt sent to the model."""

    response: str
    """Full model response."""

    extracted_answer: str | None
    """Extracted structured answer (if parseable)."""

    latency_ms: float
    """Time for this perspective to respond."""


@dataclass(frozen=True, slots=True)
class InterferenceResult:
    """Result from interference pattern analysis."""

    task: str
    """Original task."""

    perspectives: tuple[PerspectiveResponse, ...]
    """All perspective responses."""

    agreement_score: float
    """0.0 = total disagreement, 1.0 = perfect consensus."""

    consensus_answer: str | None
    """The majority answer (if one exists)."""

    answer_distribution: dict[str, int]
    """Distribution of answers across perspectives."""

    interference_pattern: str
    """'constructive' (high agreement) or 'destructive' (disagreement)."""

    confidence_recommendation: str
    """'high', 'medium', 'low', or 'escalate'."""

    semantic_similarity: float
    """Average pairwise semantic similarity of responses."""


@dataclass(frozen=True, slots=True)
class InterferenceExperimentResult:
    """Result from running interference experiment on multiple tasks."""

    results: tuple[InterferenceResult, ...]
    """Per-task results."""

    # Correlation metrics (if ground truth provided)
    agreement_accuracy_correlation: float | None
    """Correlation between agreement score and actual correctness."""

    low_agreement_accuracy: float | None
    """Accuracy on tasks with low agreement."""

    high_agreement_accuracy: float | None
    """Accuracy on tasks with high agreement."""

    optimal_threshold: float | None
    """Optimal agreement threshold for escalation decisions."""


# =============================================================================
# Default Perspectives
# =============================================================================

DEFAULT_PERSPECTIVES = [
    ("analyst", "As a careful, methodical analyst who examines all details"),
    ("skeptic", "As a skeptic who looks for flaws and edge cases"),
    ("optimist", "As an optimist who sees the straightforward interpretation"),
    ("pragmatist", "As a pragmatist focused on the simplest solution"),
    ("expert", "As a domain expert with deep knowledge"),
]

CLASSIFICATION_PERSPECTIVES = [
    ("literal", "Interpret this literally and precisely"),
    ("contextual", "Consider the broader context and common usage"),
    ("adversarial", "Look for tricks, edge cases, or ambiguity"),
    ("naive", "Give the most obvious, first-impression answer"),
    ("systematic", "Break this down step by step"),
]


# =============================================================================
# Core Functions
# =============================================================================


async def interference_scan(
    task: str,
    model: ModelProtocol,
    perspectives: list[tuple[str, str]] | None = None,
    n_perspectives: int = 5,
    extract_answer: bool = True,
    answer_format: str | None = None,
) -> InterferenceResult:
    """Run task through multiple perspectives and analyze interference pattern.

    Args:
        task: The task/question to analyze
        model: Model to use for all perspectives
        perspectives: List of (name, description) tuples. Defaults to DEFAULT_PERSPECTIVES.
        n_perspectives: Number of perspectives to use (if using defaults)
        extract_answer: Whether to try extracting structured answers
        answer_format: Expected answer format for extraction (e.g., "A/B/C" or "yes/no")

    Returns:
        InterferenceResult with agreement analysis
    """
    import time

    perspectives = perspectives or DEFAULT_PERSPECTIVES[:n_perspectives]

    # Build prompts for each perspective
    async def run_perspective(name: str, description: str) -> PerspectiveResponse:
        prompt = f"""{description}:

{task}

Provide your answer clearly and concisely."""

        start = time.perf_counter()
        result = await model.generate(prompt)
        latency = (time.perf_counter() - start) * 1000

        response_text = result.content if hasattr(result, "content") else str(result)

        # Try to extract structured answer
        extracted = None
        if extract_answer:
            extracted = _extract_answer(response_text, answer_format)

        return PerspectiveResponse(
            perspective_name=name,
            prompt=prompt,
            response=response_text,
            extracted_answer=extracted,
            latency_ms=latency,
        )

    # Run all perspectives in parallel
    responses = await asyncio.gather(*[
        run_perspective(name, desc) for name, desc in perspectives
    ])

    # Analyze interference pattern
    return _analyze_interference(task, tuple(responses))


def _extract_answer(response: str, expected_format: str | None = None) -> str | None:
    """Extract structured answer from response.

    Tries multiple patterns:
    1. Explicit "Answer: X" format
    2. First word/letter if expected format given
    3. Last sentence
    """
    response = response.strip()

    # Pattern 1: Explicit answer markers
    patterns = [
        r"(?:answer|result|conclusion)[\s:]+([^\n.]+)",
        r"(?:is|are|should be)[\s:]+([^\n.]+)",
        r"\*\*([^*]+)\*\*",  # Bold text often indicates answer
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Pattern 2: If expected format given, look for it
    if expected_format:
        options = [o.strip() for o in expected_format.split("/")]
        for option in options:
            if option.lower() in response.lower():
                return option

    # Pattern 3: Return first line as answer
    first_line = response.split("\n")[0].strip()
    if len(first_line) < 100:
        return first_line

    return None


def _analyze_interference(
    task: str,
    responses: tuple[PerspectiveResponse, ...],
) -> InterferenceResult:
    """Analyze the interference pattern from multiple perspectives."""
    # Count answers
    answers = [r.extracted_answer for r in responses if r.extracted_answer]
    answer_counts = Counter(answers)

    # Calculate agreement score
    if not answers:
        agreement_score = 0.0
        consensus = None
    else:
        most_common = answer_counts.most_common(1)[0]
        consensus = most_common[0]
        agreement_count = most_common[1]
        agreement_score = agreement_count / len(responses)

    # Calculate semantic similarity (average pairwise)
    semantic_sim = _calculate_semantic_similarity(responses)

    # Determine interference pattern
    if agreement_score >= 0.8:
        pattern = "constructive"
        confidence = "high"
    elif agreement_score >= 0.6:
        pattern = "constructive"
        confidence = "medium"
    elif agreement_score >= 0.4:
        pattern = "destructive"
        confidence = "low"
    else:
        pattern = "destructive"
        confidence = "escalate"

    return InterferenceResult(
        task=task,
        perspectives=responses,
        agreement_score=agreement_score,
        consensus_answer=consensus,
        answer_distribution=dict(answer_counts),
        interference_pattern=pattern,
        confidence_recommendation=confidence,
        semantic_similarity=semantic_sim,
    )


def _calculate_semantic_similarity(
    responses: tuple[PerspectiveResponse, ...],
) -> float:
    """Calculate average pairwise similarity of responses.

    Uses simple sequence matching. For production, use embeddings.
    """
    if len(responses) < 2:
        return 1.0

    similarities = []
    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            r1 = responses[i].response.lower()
            r2 = responses[j].response.lower()
            sim = SequenceMatcher(None, r1, r2).ratio()
            similarities.append(sim)

    return sum(similarities) / len(similarities) if similarities else 0.0


# =============================================================================
# Experiment Runner
# =============================================================================


async def run_interference_experiment(
    tasks: list[str],
    model: ModelProtocol,
    ground_truth: list[str] | None = None,
    perspectives: list[tuple[str, str]] | None = None,
    n_perspectives: int = 5,
    max_parallel: int | None = None,
) -> InterferenceExperimentResult:
    """Run interference experiment on multiple tasks in parallel.

    Args:
        tasks: List of tasks to test
        model: Model to use
        ground_truth: Optional list of correct answers (for correlation analysis)
        perspectives: Perspectives to use
        n_perspectives: Number of perspectives
        max_parallel: Max concurrent experiments. None = auto-detect from
            OLLAMA_NUM_PARALLEL (default: 4).

    Returns:
        InterferenceExperimentResult with aggregate analysis
    """
    from sunwell.runtime.ollama_parallel import DEFAULT_CAPACITY

    parallel = max_parallel or DEFAULT_CAPACITY.num_parallel

    # Process in batches to respect Ollama parallelism limits
    results: list[InterferenceResult] = []
    for i in range(0, len(tasks), parallel):
        batch = tasks[i : i + parallel]
        batch_results = await asyncio.gather(*[
            interference_scan(
                task=task,
                model=model,
                perspectives=perspectives,
                n_perspectives=n_perspectives,
            )
            for task in batch
        ])
        results.extend(batch_results)

    # Calculate correlation metrics if ground truth provided
    correlation = None
    low_acc = None
    high_acc = None
    optimal_threshold = None

    if ground_truth and len(ground_truth) == len(tasks):
        correlation, low_acc, high_acc, optimal_threshold = _analyze_correlation(
            results, ground_truth
        )

    return InterferenceExperimentResult(
        results=tuple(results),
        agreement_accuracy_correlation=correlation,
        low_agreement_accuracy=low_acc,
        high_agreement_accuracy=high_acc,
        optimal_threshold=optimal_threshold,
    )


def _analyze_correlation(
    results: list[InterferenceResult],
    ground_truth: list[str],
) -> tuple[float | None, float | None, float | None, float | None]:
    """Analyze correlation between agreement and correctness.

    Returns: (correlation, low_agreement_accuracy, high_agreement_accuracy, optimal_threshold)
    """
    # Check correctness for each result
    correctness = []
    agreements = []

    for result, truth in zip(results, ground_truth, strict=True):
        is_correct = (
            result.consensus_answer
            and result.consensus_answer.lower().strip() == truth.lower().strip()
        )
        correctness.append(1.0 if is_correct else 0.0)
        agreements.append(result.agreement_score)

    # Simple correlation (Pearson)
    if len(correctness) < 2:
        return None, None, None, None

    mean_corr = sum(correctness) / len(correctness)
    mean_agree = sum(agreements) / len(agreements)

    numerator = sum(
        (c - mean_corr) * (a - mean_agree)
        for c, a in zip(correctness, agreements, strict=True)
    )
    denom_corr = sum((c - mean_corr) ** 2 for c in correctness) ** 0.5
    denom_agree = sum((a - mean_agree) ** 2 for a in agreements) ** 0.5

    correlation = (
        numerator / (denom_corr * denom_agree)
        if denom_corr > 0 and denom_agree > 0
        else 0.0
    )

    # Split by agreement threshold (0.6)
    threshold = 0.6
    low_correct = [c for c, a in zip(correctness, agreements, strict=True) if a < threshold]
    high_correct = [c for c, a in zip(correctness, agreements, strict=True) if a >= threshold]

    low_acc = sum(low_correct) / len(low_correct) if low_correct else None
    high_acc = sum(high_correct) / len(high_correct) if high_correct else None

    # Find optimal threshold (maximize accuracy difference)
    best_threshold = 0.6
    best_diff = 0.0

    for thresh in [0.4, 0.5, 0.6, 0.7, 0.8]:
        low = [c for c, a in zip(correctness, agreements, strict=True) if a < thresh]
        high = [c for c, a in zip(correctness, agreements, strict=True) if a >= thresh]

        if low and high:
            diff = (sum(high) / len(high)) - (sum(low) / len(low))
            if diff > best_diff:
                best_diff = diff
                best_threshold = thresh

    return correlation, low_acc, high_acc, best_threshold


# =============================================================================
# Utility Functions
# =============================================================================


def interference_to_confidence(result: InterferenceResult) -> float:
    """Convert interference result to confidence score (0.0-1.0).

    Combines agreement score and semantic similarity.
    """
    # Weight: 70% agreement, 30% semantic similarity
    return 0.7 * result.agreement_score + 0.3 * result.semantic_similarity


def should_escalate(result: InterferenceResult, threshold: float = 0.5) -> bool:
    """Determine if task should be escalated to larger model.

    Args:
        result: Interference analysis result
        threshold: Agreement threshold below which to escalate

    Returns:
        True if escalation recommended
    """
    return result.agreement_score < threshold


def format_interference_report(result: InterferenceResult) -> str:
    """Format interference result as human-readable report."""
    lines = [
        f"Task: {result.task[:80]}...",
        "",
        f"Interference Pattern: {result.interference_pattern.upper()}",
        f"Agreement Score: {result.agreement_score:.2%}",
        f"Semantic Similarity: {result.semantic_similarity:.2%}",
        "",
        "Answer Distribution:",
    ]

    for answer, count in sorted(
        result.answer_distribution.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        pct = count / len(result.perspectives) * 100
        lines.append(f"  {answer}: {count} ({pct:.0f}%)")

    lines.extend([
        "",
        f"Consensus: {result.consensus_answer or 'No consensus'}",
        f"Confidence: {result.confidence_recommendation.upper()}",
    ])

    if result.confidence_recommendation == "escalate":
        lines.append("⚠️  ESCALATION RECOMMENDED - High disagreement detected")

    return "\n".join(lines)
