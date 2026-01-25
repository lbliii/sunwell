"""Speculative Parallel Discovery — Race N models, first valid wins.

The hypothesis: Fire multiple tiny models in parallel with temperature variance.
First valid result wins, cancel the rest. Race condition as a feature.

With free-threading (Python 3.14t), this is nearly free — we're already paying
for the slowest model. Speculative execution lets us hedge against slow/bad outputs.

Example:
    >>> from sunwell.planning.naaru.experiments import speculative_discover
    >>>
    >>> artifacts = await speculative_discover(
    ...     goal="Build a REST API",
    ...     model=OllamaModel("gemma3:1b"),
    ...     n_candidates=5,
    ...     temperatures=[0.3, 0.5, 0.7, 0.9, 1.1],
    ... )
    >>> print(f"Winner returned in {artifacts.latency_ms}ms")
"""


import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.planning.naaru.artifacts import ArtifactGraph


@dataclass(frozen=True, slots=True)
class SpeculativeResult:
    """Result from speculative parallel discovery."""

    graph: ArtifactGraph
    """The winning artifact graph."""

    winner_index: int
    """Which candidate won (0-indexed)."""

    winner_temperature: float
    """Temperature of the winning candidate."""

    latency_ms: float
    """Time to first valid result."""

    candidates_completed: int
    """How many candidates finished before winner."""

    candidates_cancelled: int
    """How many candidates were cancelled."""


async def speculative_discover(
    goal: str,
    model: ModelProtocol,
    context: dict[str, Any] | None = None,
    n_candidates: int = 5,
    temperatures: list[float] | None = None,
    timeout_seconds: float = 30.0,
) -> SpeculativeResult:
    """Race N discovery calls, return first valid result.

    Fires multiple discovery prompts in parallel with different temperatures.
    First valid artifact graph wins, others are cancelled.

    Args:
        goal: The goal to discover artifacts for
        model: The model to use (same model, different temps)
        context: Optional context
        n_candidates: Number of parallel candidates (default 5)
        temperatures: Temperature for each candidate (default spreads 0.3-1.1)
        timeout_seconds: Max time to wait for any result

    Returns:
        SpeculativeResult with winning graph and metrics

    Raises:
        asyncio.TimeoutError: If no valid result within timeout
        ValueError: If all candidates fail
    """
    from sunwell.planning.naaru.artifacts import ArtifactLimits
    from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

    # Default temperature spread
    if temperatures is None:
        temperatures = [0.3, 0.5, 0.7, 0.9, 1.1][:n_candidates]

    # Pad if needed
    while len(temperatures) < n_candidates:
        temperatures.append(temperatures[-1] + 0.2)

    start_time = time.perf_counter()

    # Create event to signal first valid result
    first_valid = asyncio.Event()
    winner: dict[str, Any] = {}
    completed_count = 0
    errors: list[Exception] = []

    async def run_candidate(index: int, temp: float) -> None:
        """Run one discovery candidate."""
        nonlocal completed_count, winner

        try:
            # Create planner with specific temperature
            # Note: We'd need model to support temperature override
            # For now, we simulate variance through the prompt
            planner = ArtifactPlanner(
                model=model,
                limits=ArtifactLimits(max_artifacts=20),
            )

            # Add temperature hint to context
            temp_context = dict(context or {})
            temp_context["_temperature_hint"] = temp
            temp_context["_candidate_index"] = index

            # Run discovery
            graph = await planner.discover_graph(goal, temp_context)

            # Validate result
            if graph and len(graph) > 0:
                completed_count += 1

                # First valid wins
                if not winner:
                    winner["graph"] = graph
                    winner["index"] = index
                    winner["temperature"] = temp
                    winner["latency_ms"] = (time.perf_counter() - start_time) * 1000
                    winner["completed_before"] = completed_count - 1
                    first_valid.set()

        except Exception as e:
            errors.append(e)

    # Fire all candidates in parallel
    tasks = [
        asyncio.create_task(run_candidate(i, temperatures[i]))
        for i in range(n_candidates)
    ]

    try:
        # Wait for first valid or timeout
        await asyncio.wait_for(first_valid.wait(), timeout=timeout_seconds)

        # Cancel remaining tasks
        cancelled = 0
        for task in tasks:
            if not task.done():
                task.cancel()
                cancelled += 1

        # Wait for cancellations to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        return SpeculativeResult(
            graph=winner["graph"],
            winner_index=winner["index"],
            winner_temperature=winner["temperature"],
            latency_ms=winner["latency_ms"],
            candidates_completed=winner["completed_before"],
            candidates_cancelled=cancelled,
        )

    except TimeoutError:
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if errors:
            raise ValueError(f"All {n_candidates} candidates failed: {errors[0]}") from errors[0]
        raise


async def speculative_classify(
    goal: str,
    model: ModelProtocol,
    n_candidates: int = 3,
) -> tuple[str, float]:
    """Race N classification calls, return consensus.

    Simpler version for just classification (complexity, intent, etc.)
    Returns the most common result and confidence based on agreement.

    Args:
        goal: The goal to classify
        model: The model to use
        n_candidates: Number of parallel candidates

    Returns:
        Tuple of (classification, confidence)
    """
    from collections import Counter

    from sunwell.planning.routing import UnifiedRouter

    router = UnifiedRouter(model=model)

    # Fire N classifications in parallel
    results = await asyncio.gather(*[
        router.route(goal) for _ in range(n_candidates)
    ], return_exceptions=True)

    # Filter out exceptions
    valid_results = [r for r in results if not isinstance(r, Exception)]

    if not valid_results:
        raise ValueError("All classification attempts failed")

    # Count complexities
    complexities = [r.complexity for r in valid_results]
    counts = Counter(complexities)
    winner, count = counts.most_common(1)[0]

    confidence = count / len(valid_results)

    return winner, confidence
