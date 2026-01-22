"""Resonance Amplification — Feedback Loop Signal Enhancement.

The hypothesis: Good patterns should be amplified across iterations;
bad patterns should decay. Like acoustic resonance amplifying certain
frequencies while damping others.

This tests whether iterative feedback actually improves quality,
and finds the optimal number of iterations before diminishing returns.

Example:
    >>> from sunwell.experiments.resonance_amp import (
    ...     resonance_experiment,
    ...     find_resonance_peak,
    ... )
    >>>
    >>> result = await resonance_experiment(
    ...     task="Explain how async/await works in Python",
    ...     model=OllamaModel("gemma3:1b"),
    ...     max_iterations=5,
    ... )
    >>> peak = find_resonance_peak(result)
    >>> print(f"Quality peaked at iteration {peak.iteration}")
    >>> print(f"Peak quality: {peak.quality_score:.2%}")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True)
class IterationResult:
    """Result from a single resonance iteration."""

    iteration: int
    """Which iteration (0 = initial, 1+ = refined)."""

    response: str
    """The response at this iteration."""

    quality_score: float
    """Quality metric (from judge or self-assessment)."""

    confidence: float
    """Self-reported confidence."""

    feedback: str
    """Feedback that drove refinement (empty for iteration 0)."""

    improvement_from_prev: float
    """Quality change from previous iteration."""

    latency_ms: float
    """Time for this iteration."""


@dataclass(frozen=True, slots=True)
class ResonanceResult:
    """Complete result from resonance experiment."""

    task: str
    """Original task."""

    iterations: tuple[IterationResult, ...]
    """All iteration results."""

    # Curve characteristics
    peak_iteration: int
    """Iteration with highest quality."""

    peak_quality: float
    """Quality at peak."""

    final_quality: float
    """Quality at last iteration."""

    total_improvement: float
    """Improvement from iteration 0 to peak."""

    # Pattern analysis
    pattern: str
    """'monotonic_increase', 'peak_decay', 'oscillating', 'flat'."""

    effective_iterations: int
    """Number of iterations that improved quality."""

    # Timing
    total_latency_ms: float
    """Total time across all iterations."""


@dataclass(frozen=True, slots=True)
class ResonanceExperimentResult:
    """Result from running resonance experiment on multiple tasks."""

    results: tuple[ResonanceResult, ...]
    """Per-task results."""

    avg_peak_iteration: float
    """Average iteration where quality peaked."""

    avg_improvement: float
    """Average total improvement."""

    pattern_distribution: dict[str, int]
    """Distribution of improvement patterns."""

    recommended_iterations: int
    """Recommended number of iterations based on data."""


# =============================================================================
# Feedback Generation
# =============================================================================


async def generate_feedback(
    response: str,
    task: str,
    model: ModelProtocol,
    judge_mode: str = "constructive",
) -> tuple[str, float]:
    """Generate feedback for a response.

    Args:
        response: The response to evaluate
        task: Original task for context
        model: Model to use for judging
        judge_mode: 'constructive', 'critical', or 'balanced'

    Returns:
        (feedback_text, quality_score)
    """
    if judge_mode == "critical":
        prompt = f"""Critically evaluate this response. Focus on what's WRONG or could be better.

TASK: {task}

RESPONSE: {response}

Be specific about:
1. What's incorrect or misleading
2. What's missing
3. What could be clearer

Then rate overall quality (0.0-1.0).

Format:
FEEDBACK: [your critique]
QUALITY: [0.0-1.0]"""

    elif judge_mode == "constructive":
        prompt = f"""Evaluate this response and provide constructive feedback.

TASK: {task}

RESPONSE: {response}

Note:
1. What's good (briefly)
2. What could be improved
3. Specific suggestions

Then rate overall quality (0.0-1.0).

Format:
FEEDBACK: [your feedback]
QUALITY: [0.0-1.0]"""

    else:  # balanced
        prompt = f"""Evaluate this response with balanced perspective.

TASK: {task}

RESPONSE: {response}

Consider:
1. Accuracy and correctness
2. Completeness
3. Clarity
4. Relevance

Then rate overall quality (0.0-1.0).

Format:
FEEDBACK: [your evaluation]
QUALITY: [0.0-1.0]"""

    result = await model.generate(prompt)
    response_text = result.content if hasattr(result, "content") else str(result)

    return _parse_feedback(response_text)


def _parse_feedback(response: str) -> tuple[str, float]:
    """Parse feedback and quality from judge response."""
    import re

    feedback_match = re.search(
        r"FEEDBACK:\s*(.+?)(?:QUALITY:|$)",
        response,
        re.DOTALL | re.IGNORECASE,
    )
    quality_match = re.search(r"QUALITY:\s*([\d.]+)", response, re.IGNORECASE)

    feedback = feedback_match.group(1).strip() if feedback_match else response[:300]
    quality = float(quality_match.group(1)) if quality_match else 0.5

    return feedback, min(1.0, max(0.0, quality))


# =============================================================================
# Refinement
# =============================================================================


async def refine_response(
    task: str,
    previous_response: str,
    feedback: str,
    model: ModelProtocol,
) -> tuple[str, float]:
    """Generate refined response based on feedback.

    Args:
        task: Original task
        previous_response: Response to improve
        feedback: Feedback to incorporate
        model: Model to use

    Returns:
        (refined_response, self_confidence)
    """
    prompt = f"""ORIGINAL TASK: {task}

YOUR PREVIOUS RESPONSE:
{previous_response}

FEEDBACK RECEIVED:
{feedback}

Generate an IMPROVED response that addresses the feedback.
Be specific about what you changed.
Rate your confidence in the improved version (0.0-1.0).

Format:
IMPROVED: [your improved response]
CONFIDENCE: [0.0-1.0]"""

    result = await model.generate(prompt)
    response_text = result.content if hasattr(result, "content") else str(result)

    return _parse_refined_response(response_text)


def _parse_refined_response(response: str) -> tuple[str, float]:
    """Parse refined response and confidence."""
    import re

    improved_match = re.search(
        r"IMPROVED:\s*(.+?)(?:CONFIDENCE:|$)",
        response,
        re.DOTALL | re.IGNORECASE,
    )
    conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response, re.IGNORECASE)

    improved = improved_match.group(1).strip() if improved_match else response
    confidence = float(conf_match.group(1)) if conf_match else 0.5

    return improved, min(1.0, max(0.0, confidence))


# =============================================================================
# Core Experiment
# =============================================================================


async def resonance_experiment(
    task: str,
    model: ModelProtocol,
    judge: ModelProtocol | None = None,
    max_iterations: int = 5,
    judge_mode: str = "constructive",
    stop_on_plateau: bool = True,
    plateau_threshold: float = 0.02,
) -> ResonanceResult:
    """Run the resonance amplification experiment.

    Tests whether iterative feedback improves quality, and finds
    the optimal number of iterations.

    Args:
        task: The task to solve
        model: Model for generating responses
        judge: Model for judging (defaults to same model)
        max_iterations: Maximum refinement iterations
        judge_mode: How to generate feedback
        stop_on_plateau: Stop early if quality plateaus
        plateau_threshold: Minimum improvement to continue

    Returns:
        ResonanceResult with iteration-by-iteration analysis
    """
    judge = judge or model
    iterations: list[IterationResult] = []

    # Iteration 0: Initial response
    start = time.perf_counter()
    result = await model.generate(task)
    initial_response = result.content if hasattr(result, "content") else str(result)
    initial_latency = (time.perf_counter() - start) * 1000

    # Judge initial response
    feedback, quality = await generate_feedback(
        initial_response, task, judge, judge_mode
    )

    iterations.append(IterationResult(
        iteration=0,
        response=initial_response,
        quality_score=quality,
        confidence=quality,  # Use judge quality as proxy
        feedback="",  # No prior feedback
        improvement_from_prev=0.0,
        latency_ms=initial_latency,
    ))

    # Refinement iterations
    current_response = initial_response
    prev_quality = quality

    for i in range(1, max_iterations + 1):
        start = time.perf_counter()

        # Refine based on feedback
        refined, confidence = await refine_response(
            task, current_response, feedback, model
        )

        # Judge refined response
        new_feedback, new_quality = await generate_feedback(
            refined, task, judge, judge_mode
        )

        latency = (time.perf_counter() - start) * 1000
        improvement = new_quality - prev_quality

        iterations.append(IterationResult(
            iteration=i,
            response=refined,
            quality_score=new_quality,
            confidence=confidence,
            feedback=feedback,  # Feedback that drove this refinement
            improvement_from_prev=improvement,
            latency_ms=latency,
        ))

        # Check for plateau
        if stop_on_plateau and improvement < plateau_threshold and i > 1:
            break

        current_response = refined
        feedback = new_feedback
        prev_quality = new_quality

    # Analyze results
    return _analyze_resonance(task, tuple(iterations))


def _analyze_resonance(
    task: str,
    iterations: tuple[IterationResult, ...],
) -> ResonanceResult:
    """Analyze the resonance pattern."""
    qualities = [it.quality_score for it in iterations]

    peak_idx = qualities.index(max(qualities))
    peak_quality = qualities[peak_idx]
    final_quality = qualities[-1]
    initial_quality = qualities[0]

    total_improvement = peak_quality - initial_quality
    effective_iterations = sum(1 for it in iterations if it.improvement_from_prev > 0)

    # Determine pattern
    pattern = _classify_pattern(qualities)

    total_latency = sum(it.latency_ms for it in iterations)

    return ResonanceResult(
        task=task,
        iterations=iterations,
        peak_iteration=peak_idx,
        peak_quality=peak_quality,
        final_quality=final_quality,
        total_improvement=total_improvement,
        pattern=pattern,
        effective_iterations=effective_iterations,
        total_latency_ms=total_latency,
    )


def _classify_pattern(qualities: list[float]) -> str:
    """Classify the quality progression pattern."""
    if len(qualities) < 2:
        return "flat"

    # Check monotonic increase
    diffs = [qualities[i + 1] - qualities[i] for i in range(len(qualities) - 1)]

    if all(d >= -0.01 for d in diffs):  # Allow tiny decreases
        return "monotonic_increase"

    # Check peak then decay
    peak_idx = qualities.index(max(qualities))
    if 0 < peak_idx < len(qualities) - 1:
        return "peak_decay"

    # Check oscillation
    sign_changes = sum(
        1 for i in range(len(diffs) - 1)
        if (diffs[i] > 0) != (diffs[i + 1] > 0)
    )
    if sign_changes >= 2:
        return "oscillating"

    # Check flat
    if max(qualities) - min(qualities) < 0.1:
        return "flat"

    return "other"


# =============================================================================
# Batch Experiment
# =============================================================================


async def run_resonance_batch(
    tasks: list[str],
    model: ModelProtocol,
    judge: ModelProtocol | None = None,
    max_iterations: int = 5,
    max_parallel: int | None = None,
) -> ResonanceExperimentResult:
    """Run resonance experiment on multiple tasks in parallel.

    Args:
        tasks: List of tasks to test
        model: Model for generating
        judge: Model for judging
        max_iterations: Max iterations per task
        max_parallel: Max concurrent experiments. None = auto-detect from
            OLLAMA_NUM_PARALLEL (default: 4).

    Returns:
        ResonanceExperimentResult with aggregate analysis
    """
    from sunwell.runtime.ollama_parallel import DEFAULT_CAPACITY

    parallel = max_parallel or DEFAULT_CAPACITY.num_parallel

    # Process in batches to respect Ollama parallelism limits
    results: list[ResonanceResult] = []
    for i in range(0, len(tasks), parallel):
        batch = tasks[i : i + parallel]
        batch_results = await asyncio.gather(*[
            resonance_experiment(
                task=task,
                model=model,
                judge=judge,
                max_iterations=max_iterations,
            )
            for task in batch
        ])
        results.extend(batch_results)

    return _aggregate_resonance_results(tuple(results))


def _aggregate_resonance_results(
    results: tuple[ResonanceResult, ...],
) -> ResonanceExperimentResult:
    """Aggregate results across tasks."""
    from collections import Counter

    avg_peak = sum(r.peak_iteration for r in results) / len(results) if results else 0
    avg_improvement = sum(r.total_improvement for r in results) / len(results) if results else 0

    patterns = Counter(r.pattern for r in results)

    # Recommend iterations based on average peak
    recommended = max(1, round(avg_peak))

    return ResonanceExperimentResult(
        results=results,
        avg_peak_iteration=avg_peak,
        avg_improvement=avg_improvement,
        pattern_distribution=dict(patterns),
        recommended_iterations=recommended,
    )


# =============================================================================
# Analysis Functions
# =============================================================================


def find_resonance_peak(result: ResonanceResult) -> IterationResult:
    """Find the iteration with peak quality."""
    return result.iterations[result.peak_iteration]


def get_quality_curve(result: ResonanceResult) -> list[float]:
    """Get the quality progression curve."""
    return [it.quality_score for it in result.iterations]


def format_resonance_report(result: ResonanceResult) -> str:
    """Format resonance result as human-readable report."""
    lines = [
        f"Task: {result.task[:80]}...",
        "",
        "=== RESONANCE ANALYSIS ===",
        f"Pattern: {result.pattern}",
        f"Iterations: {len(result.iterations)}",
        f"Effective iterations: {result.effective_iterations}",
        "",
        "=== QUALITY PROGRESSION ===",
    ]

    for it in result.iterations:
        indicator = "★" if it.iteration == result.peak_iteration else " "
        delta = f"+{it.improvement_from_prev:.1%}" if it.improvement_from_prev > 0 else f"{it.improvement_from_prev:.1%}"
        lines.append(
            f"  {indicator} Iter {it.iteration}: {it.quality_score:.2%} ({delta})"
        )

    lines.extend([
        "",
        "=== SUMMARY ===",
        f"Initial quality: {result.iterations[0].quality_score:.2%}",
        f"Peak quality: {result.peak_quality:.2%} (iter {result.peak_iteration})",
        f"Final quality: {result.final_quality:.2%}",
        f"Total improvement: {result.total_improvement:+.2%}",
        f"Total time: {result.total_latency_ms:.0f}ms",
    ])

    return "\n".join(lines)


def plot_resonance_curve(result: ResonanceResult) -> str:
    """Generate ASCII plot of quality curve."""
    qualities = get_quality_curve(result)
    max_q = max(qualities)
    min_q = min(qualities)
    height = 10

    if max_q == min_q:
        # Flat line
        return "Quality: " + "─" * len(qualities) + f" ({max_q:.2%})"

    lines = []
    for row in range(height, -1, -1):
        threshold = min_q + (max_q - min_q) * (row / height)
        line = ""
        for i, q in enumerate(qualities):
            if q >= threshold:
                line += "█" if i == result.peak_iteration else "▓"
            else:
                line += " "
        label = f"{threshold:.0%}" if row in [0, height // 2, height] else ""
        lines.append(f"{label:>4} │{line}")

    lines.append("     └" + "─" * len(qualities))
    lines.append("      " + "".join(str(i) for i in range(len(qualities))))

    return "\n".join(lines)
