"""Gradient Flow — Confidence Propagation Through Task Graphs.

The hypothesis: Information should flow from certain → uncertain regions.
Solving easy subtasks first creates confidence that propagates to harder ones.

Like temperature gradients creating airflow:
- High confidence regions (solved subtasks) create "pressure"
- Low confidence regions (unsolved) receive that pressure
- The flow carries useful context forward

Example:
    >>> from sunwell.experiments.gradient import (
    ...     gradient_flow_solve,
    ...     compare_with_baseline,
    ... )
    >>>
    >>> result = await gradient_flow_solve(
    ...     goal="Build a REST API with user auth",
    ...     model=OllamaModel("gemma3:1b"),
    ... )
    >>> print(f"Gradient accuracy: {result.gradient_accuracy:.2%}")
    >>> print(f"Baseline accuracy: {result.baseline_accuracy:.2%}")
    >>> print(f"Improvement: {result.gradient_accuracy - result.baseline_accuracy:.2%}")
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
class Subtask:
    """A subtask in a decomposed goal."""

    id: str
    """Unique identifier."""

    description: str
    """What this subtask accomplishes."""

    estimated_difficulty: float
    """Estimated difficulty (0.0 = trivial, 1.0 = very hard)."""

    depends_on: frozenset[str] = frozenset()
    """IDs of subtasks this depends on."""


@dataclass(frozen=True, slots=True)
class SubtaskResult:
    """Result from solving a subtask."""

    subtask: Subtask
    """The subtask that was solved."""

    solution: str
    """The generated solution."""

    confidence: float
    """Confidence in this solution (0.0-1.0)."""

    context_used: str
    """Context provided from prior solutions."""

    latency_ms: float
    """Time to solve this subtask."""


@dataclass(frozen=True, slots=True)
class GradientFlowResult:
    """Result from gradient flow experiment."""

    goal: str
    """Original goal."""

    subtasks: tuple[Subtask, ...]
    """Decomposed subtasks."""

    # Gradient approach results
    gradient_results: tuple[SubtaskResult, ...]
    """Results when solving with confidence propagation."""

    gradient_order: tuple[str, ...]
    """Order subtasks were solved (easiest first)."""

    # Baseline approach results
    baseline_results: tuple[SubtaskResult, ...]
    """Results when solving in parallel (no propagation)."""

    # Comparison metrics
    gradient_accuracy: float
    """Overall accuracy with gradient flow."""

    baseline_accuracy: float
    """Overall accuracy without gradient flow."""

    improvement: float
    """Accuracy improvement from gradient flow."""

    confidence_propagation: dict[str, float]
    """How confidence changed through the graph."""


@dataclass(frozen=True, slots=True)
class PropagationMetrics:
    """Metrics about how confidence propagated."""

    initial_avg_confidence: float
    """Average confidence before propagation."""

    final_avg_confidence: float
    """Average confidence after propagation."""

    confidence_gain: float
    """How much confidence increased."""

    propagation_depth: int
    """How many levels confidence propagated through."""


# =============================================================================
# Task Decomposition
# =============================================================================


async def decompose_with_difficulty(
    goal: str,
    model: ModelProtocol,
) -> list[Subtask]:
    """Decompose goal into subtasks with difficulty estimates.

    Args:
        goal: The goal to decompose
        model: Model to use for decomposition

    Returns:
        List of subtasks with difficulty estimates
    """
    prompt = f"""Decompose this goal into 4-6 concrete subtasks.
For each subtask, estimate difficulty (0.0 = trivial, 1.0 = very hard).

GOAL: {goal}

Respond in this exact format for each subtask:
SUBTASK: [id] | [description] | [difficulty 0.0-1.0] | [depends_on: comma-separated ids or "none"]

Example:
SUBTASK: define_types | Define core type definitions | 0.2 | none
SUBTASK: implement_model | Implement the data model | 0.5 | define_types
"""

    result = await model.generate(prompt)
    response = result.content if hasattr(result, "content") else str(result)

    return _parse_subtasks(response)


def _parse_subtasks(response: str) -> list[Subtask]:
    """Parse subtasks from model response."""
    import re

    subtasks = []
    pattern = r"SUBTASK:\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([\d.]+)\s*\|\s*(.+)"

    for match in re.finditer(pattern, response, re.IGNORECASE):
        subtask_id = match.group(1).strip()
        description = match.group(2).strip()
        difficulty = float(match.group(3).strip())
        deps_str = match.group(4).strip().lower()

        deps = frozenset()
        if deps_str != "none" and deps_str:
            deps = frozenset(d.strip() for d in deps_str.split(",") if d.strip())

        subtasks.append(Subtask(
            id=subtask_id,
            description=description,
            estimated_difficulty=min(1.0, max(0.0, difficulty)),
            depends_on=deps,
        ))

    # If parsing failed, create a single subtask
    if not subtasks:
        subtasks = [Subtask(
            id="main",
            description=f"Complete: {response[:100]}",
            estimated_difficulty=0.5,
        )]

    return subtasks


# =============================================================================
# Solving Strategies
# =============================================================================


async def solve_with_gradient(
    subtasks: list[Subtask],
    model: ModelProtocol,
    goal: str,
) -> tuple[list[SubtaskResult], list[str]]:
    """Solve subtasks using gradient flow (easiest first, propagate context).

    Args:
        subtasks: List of subtasks to solve
        model: Model to use
        goal: Original goal for context

    Returns:
        (results, order) - Results and the order subtasks were solved
    """
    # Sort by difficulty (easiest first), respecting dependencies
    order = _topological_sort_by_difficulty(subtasks)

    results: list[SubtaskResult] = []
    solved: dict[str, SubtaskResult] = {}

    for subtask_id in order:
        subtask = next(s for s in subtasks if s.id == subtask_id)

        # Build context from already-solved dependencies
        context_parts = []
        for dep_id in subtask.depends_on:
            if dep_id in solved:
                dep_result = solved[dep_id]
                context_parts.append(
                    f"[{dep_id}] (confidence: {dep_result.confidence:.2f}):\n"
                    f"{dep_result.solution[:200]}"
                )

        context = "\n\n".join(context_parts) if context_parts else "No prior context."

        # Solve with context
        result = await _solve_subtask(subtask, model, goal, context)
        results.append(result)
        solved[subtask_id] = result

    return results, order


async def solve_parallel_baseline(
    subtasks: list[Subtask],
    model: ModelProtocol,
    goal: str,
) -> list[SubtaskResult]:
    """Solve all subtasks in parallel (no context propagation).

    Args:
        subtasks: List of subtasks to solve
        model: Model to use
        goal: Original goal for context

    Returns:
        Results from parallel solving
    """
    results = await asyncio.gather(*[
        _solve_subtask(subtask, model, goal, "No prior context.")
        for subtask in subtasks
    ])
    return list(results)


async def _solve_subtask(
    subtask: Subtask,
    model: ModelProtocol,
    goal: str,
    context: str,
) -> SubtaskResult:
    """Solve a single subtask with given context."""
    prompt = f"""GOAL: {goal}

CURRENT SUBTASK: {subtask.description}

CONTEXT FROM PRIOR WORK:
{context}

Solve this subtask. Be specific and concrete.
After your solution, rate your confidence (0.0-1.0).

Format:
SOLUTION: [your solution]
CONFIDENCE: [0.0-1.0]"""

    start = time.perf_counter()
    result = await model.generate(prompt)
    latency = (time.perf_counter() - start) * 1000

    response = result.content if hasattr(result, "content") else str(result)

    # Extract solution and confidence
    solution, confidence = _parse_solution(response)

    return SubtaskResult(
        subtask=subtask,
        solution=solution,
        confidence=confidence,
        context_used=context,
        latency_ms=latency,
    )


def _parse_solution(response: str) -> tuple[str, float]:
    """Parse solution and confidence from response."""
    import re

    # Try to extract structured response
    solution_match = re.search(r"SOLUTION:\s*(.+?)(?:CONFIDENCE:|$)", response, re.DOTALL | re.IGNORECASE)
    confidence_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response, re.IGNORECASE)

    solution = solution_match.group(1).strip() if solution_match else response.strip()
    confidence = float(confidence_match.group(1)) if confidence_match else 0.5

    return solution, min(1.0, max(0.0, confidence))


def _topological_sort_by_difficulty(subtasks: list[Subtask]) -> list[str]:
    """Sort subtasks: respect dependencies, then by difficulty (easiest first)."""

    # Build dependency graph
    in_degree: dict[str, int] = {s.id: 0 for s in subtasks}
    dependents: dict[str, list[str]] = {s.id: [] for s in subtasks}

    for subtask in subtasks:
        for dep in subtask.depends_on:
            if dep in in_degree:
                in_degree[subtask.id] += 1
                dependents[dep].append(subtask.id)

    # Kahn's algorithm with difficulty-based priority
    # Use list sorted by difficulty instead of simple queue
    available = [s for s in subtasks if in_degree[s.id] == 0]
    available.sort(key=lambda s: s.estimated_difficulty)

    order = []
    subtask_map = {s.id: s for s in subtasks}

    while available:
        # Take easiest available
        current = available.pop(0)
        order.append(current.id)

        # Update dependents
        for dep_id in dependents[current.id]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                available.append(subtask_map[dep_id])
                available.sort(key=lambda s: s.estimated_difficulty)

    return order


# =============================================================================
# Main Experiment
# =============================================================================


async def gradient_flow_solve(
    goal: str,
    model: ModelProtocol,
    subtasks: list[Subtask] | None = None,
) -> GradientFlowResult:
    """Run the gradient flow experiment.

    Compares solving with gradient flow (easiest first, context propagation)
    vs baseline (parallel, no propagation).

    Args:
        goal: The goal to accomplish
        model: Model to use
        subtasks: Optional pre-defined subtasks (otherwise decomposed by model)

    Returns:
        GradientFlowResult with comparison metrics
    """
    # Decompose if not provided
    if subtasks is None:
        subtasks = await decompose_with_difficulty(goal, model)

    # Run both strategies
    gradient_results, gradient_order = await solve_with_gradient(subtasks, model, goal)
    baseline_results = await solve_parallel_baseline(subtasks, model, goal)

    # Calculate metrics
    gradient_avg_confidence = (
        sum(r.confidence for r in gradient_results) / len(gradient_results)
        if gradient_results else 0.0
    )
    baseline_avg_confidence = (
        sum(r.confidence for r in baseline_results) / len(baseline_results)
        if baseline_results else 0.0
    )

    # Track confidence propagation
    propagation: dict[str, float] = {}
    for _i, result in enumerate(gradient_results):
        subtask_id = result.subtask.id
        # Compare to baseline confidence for same subtask
        baseline_conf = next(
            (r.confidence for r in baseline_results if r.subtask.id == subtask_id),
            0.5
        )
        propagation[subtask_id] = result.confidence - baseline_conf

    return GradientFlowResult(
        goal=goal,
        subtasks=tuple(subtasks),
        gradient_results=tuple(gradient_results),
        gradient_order=tuple(gradient_order),
        baseline_results=tuple(baseline_results),
        gradient_accuracy=gradient_avg_confidence,  # Using confidence as proxy for accuracy
        baseline_accuracy=baseline_avg_confidence,
        improvement=gradient_avg_confidence - baseline_avg_confidence,
        confidence_propagation=propagation,
    )


async def run_gradient_experiment(
    goals: list[str],
    model: ModelProtocol,
    max_parallel: int | None = None,
) -> list[GradientFlowResult]:
    """Run gradient experiment on multiple goals in parallel.

    Args:
        goals: List of goals to test
        model: Model to use
        max_parallel: Max concurrent experiments. None = auto-detect from
            OLLAMA_NUM_PARALLEL (default: 4).

    Returns:
        List of results for each goal
    """
    from sunwell.runtime.ollama_parallel import DEFAULT_CAPACITY

    parallel = max_parallel or DEFAULT_CAPACITY.num_parallel

    # Process in batches to respect Ollama parallelism limits
    results: list[GradientFlowResult] = []
    for i in range(0, len(goals), parallel):
        batch = goals[i : i + parallel]
        batch_results = await asyncio.gather(*[
            gradient_flow_solve(goal, model) for goal in batch
        ])
        results.extend(batch_results)
    return results


# =============================================================================
# Analysis Functions
# =============================================================================


def analyze_propagation(results: list[GradientFlowResult]) -> PropagationMetrics:
    """Analyze how confidence propagated across all experiments."""
    all_gradient_conf = []
    all_baseline_conf = []

    for result in results:
        all_gradient_conf.extend(r.confidence for r in result.gradient_results)
        all_baseline_conf.extend(r.confidence for r in result.baseline_results)

    initial_avg = sum(all_baseline_conf) / len(all_baseline_conf) if all_baseline_conf else 0.0
    final_avg = sum(all_gradient_conf) / len(all_gradient_conf) if all_gradient_conf else 0.0

    # Calculate max propagation depth
    max_depth = max(
        len(result.gradient_order) for result in results
    ) if results else 0

    return PropagationMetrics(
        initial_avg_confidence=initial_avg,
        final_avg_confidence=final_avg,
        confidence_gain=final_avg - initial_avg,
        propagation_depth=max_depth,
    )


def format_gradient_report(result: GradientFlowResult) -> str:
    """Format gradient flow result as human-readable report."""
    lines = [
        f"Goal: {result.goal[:80]}...",
        "",
        f"Subtasks: {len(result.subtasks)}",
        f"Execution order (by difficulty): {' → '.join(result.gradient_order)}",
        "",
        "=== COMPARISON ===",
        f"Gradient Flow Confidence: {result.gradient_accuracy:.2%}",
        f"Baseline Confidence:      {result.baseline_accuracy:.2%}",
        f"Improvement:              {result.improvement:+.2%}",
        "",
        "=== CONFIDENCE PROPAGATION ===",
    ]

    for subtask_id, delta in result.confidence_propagation.items():
        sign = "+" if delta >= 0 else ""
        lines.append(f"  {subtask_id}: {sign}{delta:.2%}")

    return "\n".join(lines)
