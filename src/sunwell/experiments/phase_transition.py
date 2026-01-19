"""Phase Transition Detection — Finding Critical Points.

The hypothesis: There's a critical point where adding more perspectives
or iterations causes a QUALITATIVE jump in quality, not linear improvement.

Like water freezing at 0°C — gradual cooling, then sudden phase change.

This experiment sweeps parameters to find:
1. Where quality jumps discontinuously
2. Diminishing returns boundaries
3. Optimal configuration for cost/quality tradeoff

Example:
    >>> from sunwell.experiments.phase_transition import (
    ...     sweep_parameters,
    ...     find_phase_transitions,
    ... )
    >>>
    >>> results = await sweep_parameters(
    ...     task="Classify this math operation",
    ...     model=OllamaModel("gemma3:1b"),
    ...     max_perspectives=8,
    ...     max_iterations=5,
    ... )
    >>> transitions = find_phase_transitions(results)
    >>> print(f"Phase transition at: {transitions.critical_perspectives} perspectives")
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True)
class SweepPoint:
    """Single point in the parameter sweep."""

    n_perspectives: int
    """Number of perspectives used."""

    n_iterations: int
    """Number of refinement iterations."""

    quality_score: float
    """Quality metric (0.0-1.0)."""

    confidence: float
    """Model's self-reported confidence."""

    agreement: float
    """Agreement across perspectives (if applicable)."""

    latency_ms: float
    """Total time for this configuration."""

    token_cost: int
    """Estimated token cost."""


@dataclass(frozen=True, slots=True)
class PhaseTransition:
    """A detected phase transition point."""

    parameter: str
    """Which parameter ('perspectives' or 'iterations')."""

    before_value: int
    """Parameter value before transition."""

    after_value: int
    """Parameter value after transition."""

    quality_jump: float
    """Size of the quality jump."""

    is_significant: bool
    """Whether jump exceeds noise threshold."""


@dataclass(frozen=True, slots=True)
class SweepResult:
    """Result from full parameter sweep."""

    task: str
    """The task that was tested."""

    points: tuple[SweepPoint, ...]
    """All sweep points."""

    # Detected transitions
    transitions: tuple[PhaseTransition, ...]
    """Detected phase transitions."""

    # Optimal configurations
    optimal_quality: SweepPoint
    """Configuration with highest quality."""

    optimal_efficiency: SweepPoint
    """Best quality/cost ratio."""

    # Curve characteristics
    perspective_marginal_returns: list[float]
    """Marginal quality gain per additional perspective."""

    iteration_marginal_returns: list[float]
    """Marginal quality gain per additional iteration."""

    # Summary
    has_phase_transition: bool
    """Whether a significant phase transition was detected."""


# =============================================================================
# Core Sweep Functions
# =============================================================================


async def sweep_parameters(
    task: str,
    model: ModelProtocol,
    max_perspectives: int = 8,
    max_iterations: int = 5,
    quality_evaluator: Any | None = None,
    ground_truth: str | None = None,
) -> SweepResult:
    """Sweep perspective and iteration parameters to find phase transitions.

    Args:
        task: The task to test
        model: Model to use
        max_perspectives: Maximum perspectives to test
        max_iterations: Maximum iterations to test
        quality_evaluator: Optional function to evaluate quality
        ground_truth: Optional ground truth for accuracy calculation

    Returns:
        SweepResult with all points and detected transitions
    """
    points: list[SweepPoint] = []

    for n_persp in range(1, max_perspectives + 1):
        for n_iter in range(1, max_iterations + 1):
            point = await _run_configuration(
                task=task,
                model=model,
                n_perspectives=n_persp,
                n_iterations=n_iter,
                ground_truth=ground_truth,
            )
            points.append(point)

    # Analyze for transitions
    transitions = _detect_transitions(points)

    # Find optimal configurations
    optimal_quality = max(points, key=lambda p: p.quality_score)
    optimal_efficiency = max(
        points,
        key=lambda p: p.quality_score / (p.token_cost + 1),  # +1 to avoid div by 0
    )

    # Calculate marginal returns
    persp_returns = _calculate_marginal_returns(points, "perspectives")
    iter_returns = _calculate_marginal_returns(points, "iterations")

    return SweepResult(
        task=task,
        points=tuple(points),
        transitions=tuple(transitions),
        optimal_quality=optimal_quality,
        optimal_efficiency=optimal_efficiency,
        perspective_marginal_returns=persp_returns,
        iteration_marginal_returns=iter_returns,
        has_phase_transition=any(t.is_significant for t in transitions),
    )


async def _run_configuration(
    task: str,
    model: ModelProtocol,
    n_perspectives: int,
    n_iterations: int,
    ground_truth: str | None = None,
) -> SweepPoint:
    """Run a single configuration and measure quality."""
    from sunwell.experiments.interference import interference_scan

    start = time.perf_counter()
    total_tokens = 0

    # Generate perspectives
    perspectives = _generate_perspectives(n_perspectives)

    # Run interference scan
    interference_result = await interference_scan(
        task=task,
        model=model,
        perspectives=perspectives,
        n_perspectives=n_perspectives,
    )

    # If iterations > 1, refine the consensus
    current_answer = interference_result.consensus_answer or ""
    current_confidence = interference_result.agreement_score

    for _i in range(n_iterations - 1):
        # Refinement iteration
        refine_prompt = f"""Previous answer: {current_answer}
Previous confidence: {current_confidence:.2%}

Task: {task}

Improve on the previous answer. Be more precise and confident.
Format: ANSWER: [your answer] | CONFIDENCE: [0.0-1.0]"""

        result = await model.generate(refine_prompt)
        response = result.content if hasattr(result, "content") else str(result)
        total_tokens += len(response.split()) * 2  # Rough estimate

        # Parse refined answer
        current_answer, current_confidence = _parse_refined(response)

    latency = (time.perf_counter() - start) * 1000

    # Calculate quality score
    quality = current_confidence  # Use confidence as proxy

    # If ground truth provided, use accuracy
    if ground_truth:
        quality = 1.0 if _answers_match(current_answer, ground_truth) else 0.0

    # Estimate token cost
    total_tokens += n_perspectives * 200  # Rough estimate per perspective

    return SweepPoint(
        n_perspectives=n_perspectives,
        n_iterations=n_iterations,
        quality_score=quality,
        confidence=current_confidence,
        agreement=interference_result.agreement_score,
        latency_ms=latency,
        token_cost=total_tokens,
    )


def _generate_perspectives(n: int) -> list[tuple[str, str]]:
    """Generate n diverse perspectives."""
    all_perspectives = [
        ("analyst", "As a careful, methodical analyst"),
        ("skeptic", "As a skeptic looking for flaws"),
        ("optimist", "As an optimist seeing the straightforward path"),
        ("pragmatist", "As a pragmatist focused on simplicity"),
        ("expert", "As a domain expert"),
        ("novice", "As a beginner approaching this fresh"),
        ("contrarian", "As someone who challenges assumptions"),
        ("systematic", "As someone who breaks things into steps"),
    ]
    return all_perspectives[:n]


def _parse_refined(response: str) -> tuple[str, float]:
    """Parse refined answer and confidence."""
    import re

    answer_match = re.search(r"ANSWER:\s*([^|]+)", response, re.IGNORECASE)
    conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response, re.IGNORECASE)

    answer = answer_match.group(1).strip() if answer_match else response[:100]
    confidence = float(conf_match.group(1)) if conf_match else 0.5

    return answer, min(1.0, max(0.0, confidence))


def _answers_match(answer: str, ground_truth: str) -> bool:
    """Check if answer matches ground truth (fuzzy)."""
    a = answer.lower().strip()
    g = ground_truth.lower().strip()

    # Exact match
    if a == g:
        return True

    # Contains match
    if g in a or a in g:
        return True

    # First word match (for single-word answers)
    return a.split()[0] == g.split()[0]


# =============================================================================
# Phase Transition Detection
# =============================================================================


def _detect_transitions(points: list[SweepPoint]) -> list[PhaseTransition]:
    """Detect phase transitions in the sweep data."""
    transitions = []

    # Analyze perspective dimension (fix iterations at 1)
    persp_points = sorted(
        [p for p in points if p.n_iterations == 1],
        key=lambda p: p.n_perspectives,
    )

    for i in range(1, len(persp_points)):
        prev = persp_points[i - 1]
        curr = persp_points[i]
        jump = curr.quality_score - prev.quality_score

        # Significant jump = more than 15% improvement
        if jump > 0.15:
            transitions.append(PhaseTransition(
                parameter="perspectives",
                before_value=prev.n_perspectives,
                after_value=curr.n_perspectives,
                quality_jump=jump,
                is_significant=True,
            ))

    # Analyze iteration dimension (fix perspectives at max tested)
    max_persp = max(p.n_perspectives for p in points)
    iter_points = sorted(
        [p for p in points if p.n_perspectives == max_persp],
        key=lambda p: p.n_iterations,
    )

    for i in range(1, len(iter_points)):
        prev = iter_points[i - 1]
        curr = iter_points[i]
        jump = curr.quality_score - prev.quality_score

        if jump > 0.15:
            transitions.append(PhaseTransition(
                parameter="iterations",
                before_value=prev.n_iterations,
                after_value=curr.n_iterations,
                quality_jump=jump,
                is_significant=True,
            ))

    return transitions


def _calculate_marginal_returns(
    points: list[SweepPoint],
    dimension: str,
) -> list[float]:
    """Calculate marginal quality gain for each step in a dimension."""
    if dimension == "perspectives":
        # Fix iterations at 1
        dim_points = sorted(
            [p for p in points if p.n_iterations == 1],
            key=lambda p: p.n_perspectives,
        )
    else:
        # Fix perspectives at max
        max_persp = max(p.n_perspectives for p in points)
        dim_points = sorted(
            [p for p in points if p.n_perspectives == max_persp],
            key=lambda p: p.n_iterations,
        )

    returns = []
    for i in range(1, len(dim_points)):
        marginal = dim_points[i].quality_score - dim_points[i - 1].quality_score
        returns.append(marginal)

    return returns


# =============================================================================
# Analysis Functions
# =============================================================================


def find_diminishing_returns_point(result: SweepResult) -> tuple[int, int]:
    """Find where adding more perspectives/iterations stops helping.

    Returns (n_perspectives, n_iterations) where returns become marginal.
    """
    # Find where marginal return drops below 5%
    persp_cutoff = 1
    for i, ret in enumerate(result.perspective_marginal_returns):
        if ret < 0.05:
            persp_cutoff = i + 1
            break
    else:
        persp_cutoff = len(result.perspective_marginal_returns) + 1

    iter_cutoff = 1
    for i, ret in enumerate(result.iteration_marginal_returns):
        if ret < 0.05:
            iter_cutoff = i + 1
            break
    else:
        iter_cutoff = len(result.iteration_marginal_returns) + 1

    return persp_cutoff, iter_cutoff


def format_sweep_report(result: SweepResult) -> str:
    """Format sweep result as human-readable report."""
    lines = [
        f"Task: {result.task[:80]}...",
        "",
        "=== SWEEP SUMMARY ===",
        f"Points tested: {len(result.points)}",
        f"Phase transitions detected: {len(result.transitions)}",
        "",
        "=== OPTIMAL CONFIGURATIONS ===",
        f"Best Quality: {result.optimal_quality.n_perspectives}P × {result.optimal_quality.n_iterations}I",
        f"  Quality: {result.optimal_quality.quality_score:.2%}",
        f"  Latency: {result.optimal_quality.latency_ms:.0f}ms",
        "",
        f"Best Efficiency: {result.optimal_efficiency.n_perspectives}P × {result.optimal_efficiency.n_iterations}I",
        f"  Quality: {result.optimal_efficiency.quality_score:.2%}",
        f"  Tokens: ~{result.optimal_efficiency.token_cost}",
        "",
    ]

    if result.transitions:
        lines.append("=== PHASE TRANSITIONS ===")
        for t in result.transitions:
            lines.append(
                f"  {t.parameter}: {t.before_value} → {t.after_value} "
                f"(+{t.quality_jump:.1%} jump)"
            )
        lines.append("")

    lines.append("=== MARGINAL RETURNS ===")
    lines.append("Perspectives: " + " → ".join(
        f"{r:+.1%}" for r in result.perspective_marginal_returns
    ))
    lines.append("Iterations: " + " → ".join(
        f"{r:+.1%}" for r in result.iteration_marginal_returns
    ))

    persp_cut, iter_cut = find_diminishing_returns_point(result)
    lines.append("")
    lines.append(f"Recommended cutoff: {persp_cut}P × {iter_cut}I")

    return "\n".join(lines)


# =============================================================================
# Batch Experiment
# =============================================================================


async def run_phase_experiment(
    tasks: list[str],
    model: ModelProtocol,
    ground_truths: list[str] | None = None,
    max_perspectives: int = 6,
    max_iterations: int = 4,
) -> list[SweepResult]:
    """Run phase transition experiment on multiple tasks.

    Args:
        tasks: List of tasks to test
        model: Model to use
        ground_truths: Optional ground truths for accuracy
        max_perspectives: Max perspectives to sweep
        max_iterations: Max iterations to sweep

    Returns:
        List of sweep results
    """
    results = []

    for i, task in enumerate(tasks):
        ground_truth = ground_truths[i] if ground_truths else None
        result = await sweep_parameters(
            task=task,
            model=model,
            max_perspectives=max_perspectives,
            max_iterations=max_iterations,
            ground_truth=ground_truth,
        )
        results.append(result)

    return results


def aggregate_phase_results(results: list[SweepResult]) -> dict[str, Any]:
    """Aggregate phase results across multiple tasks."""
    all_transitions = []
    avg_optimal_persp = 0
    avg_optimal_iter = 0

    for result in results:
        all_transitions.extend(result.transitions)
        avg_optimal_persp += result.optimal_quality.n_perspectives
        avg_optimal_iter += result.optimal_quality.n_iterations

    n = len(results)
    return {
        "total_tasks": n,
        "tasks_with_transitions": sum(1 for r in results if r.has_phase_transition),
        "avg_optimal_perspectives": avg_optimal_persp / n if n else 0,
        "avg_optimal_iterations": avg_optimal_iter / n if n else 0,
        "common_transition_points": _find_common_transitions(all_transitions),
    }


def _find_common_transitions(transitions: list[PhaseTransition]) -> dict[str, int]:
    """Find most common transition points."""
    from collections import Counter

    persp_transitions = Counter(
        t.after_value for t in transitions if t.parameter == "perspectives"
    )
    iter_transitions = Counter(
        t.after_value for t in transitions if t.parameter == "iterations"
    )

    return {
        "perspectives": persp_transitions.most_common(1)[0] if persp_transitions else (0, 0),
        "iterations": iter_transitions.most_common(1)[0] if iter_transitions else (0, 0),
    }
