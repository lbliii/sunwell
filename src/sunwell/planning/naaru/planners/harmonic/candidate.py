"""Candidate generation for harmonic planning."""

import asyncio
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.planners.metrics import CandidateResult
from sunwell.planning.naaru.planners.variance import apply_variance, get_variance_configs

if TYPE_CHECKING:
    from sunwell.planning.naaru.convergence import Convergence


async def generate_candidates(
    planner: Any,  # HarmonicPlanner - avoid circular import
    goal: str,
    context: dict[str, Any] | None,
) -> list[CandidateResult]:
    """Generate N candidate plans in parallel.

    Returns CandidateResult objects with stable IDs for reliable
    frontend/backend alignment (no index confusion).
    """
    from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

    # Create base planner
    base_planner = ArtifactPlanner(
        model=planner.model,
        limits=planner.limits,
        project_schema=planner.project_schema,
    )

    # Pre-populate convergence if available
    if planner.convergence:
        await warm_convergence(planner.convergence, goal, context)

    # Generate variance configurations
    configs = get_variance_configs(planner.variance, planner.candidates)

    # RFC-058: Emit candidate generation start event
    planner._emit_event("plan_candidate_start", {
        "total_candidates": len(configs),
        "variance_strategy": planner.variance.value,
    })

    # Discover all plans in parallel
    async def discover_with_config(
        config: dict, index: int
    ) -> CandidateResult | None:
        # Generate stable ID for this candidate
        candidate_id = f"candidate-{index}"

        try:
            # Apply variance to goal prompt
            varied_goal = apply_variance(goal, config)
            graph = await base_planner.discover_graph(varied_goal, context)

            # Build normalized variance_config
            variance_config = {
                "prompt_style": config.get("prompt_style", "default"),
                "temperature": config.get("temperature"),
                "constraint": config.get("constraint"),
            }

            # Emit candidate generated event with ID
            planner._emit_event("plan_candidate_generated", {
                "candidate_id": candidate_id,
                "artifact_count": len(graph),
                "progress": index + 1,
                "total_candidates": len(configs),
                "variance_config": variance_config,
            })

            return CandidateResult(
                id=candidate_id,
                graph=graph,
                variance_config=variance_config,
            )
        except Exception:
            return None  # Skip failed discoveries

    results = await asyncio.gather(
        *[discover_with_config(c, i) for i, c in enumerate(configs)],
        return_exceptions=True,
    )

    # Filter successful plans
    candidates = [r for r in results if isinstance(r, CandidateResult)]

    # RFC-058: Emit candidates complete event
    planner._emit_event("plan_candidates_complete", {
        "total_candidates": len(configs),
        "successful_candidates": len(candidates),
        "failed_candidates": len(configs) - len(candidates),
    })

    return candidates


async def warm_convergence(
    convergence: Convergence,
    goal: str,
    context: dict[str, Any] | None,
) -> None:
    """Pre-populate Convergence with shared context."""
    from sunwell.planning.naaru.convergence import Slot, SlotSource

    # Add goal context
    await convergence.add(
        Slot(
            id="harmonic:goal",
            content=goal,
            relevance=1.0,
            source=SlotSource.CONTEXT_PREPARER,
            ttl=300,
        )
    )

    # Add project context if available
    if context:
        await convergence.add(
            Slot(
                id="harmonic:context",
                content=context,
                relevance=0.9,
                source=SlotSource.CONTEXT_PREPARER,
                ttl=300,
            )
        )
