"""Harmonic Planner - Main orchestration class (RFC-038, RFC-116, RFC-122).

This module provides the HarmonicPlanner class that orchestrates:
- Candidate generation (candidate.py)
- Scoring (scoring.py)
- Refinement (refinement.py)
- Template planning (template.py)
- Parsing (parsing.py)
- Utilities (utils.py)
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import (
    DEFAULT_LIMITS,
    ArtifactGraph,
    ArtifactLimits,
    ArtifactSpec,
    artifacts_to_tasks,
)
from sunwell.planning.naaru.planners.metrics import CandidateResult, PlanMetrics, PlanMetricsV2
from sunwell.planning.naaru.planners.variance import VarianceStrategy
from sunwell.planning.naaru.types import Task, TaskMode

from .candidate import generate_candidates
from .refinement import (
    extract_applied_improvements,
    identify_improvements,
    refine_with_feedback,
)
from .scoring import compute_metrics_v1, compute_metrics_v2
from .template import plan_with_template
from .utils import (
    format_selection_reason,
    get_effective_score,
    metrics_to_dict,
)

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.convergence import Convergence
    from sunwell.knowledge.project.schema import ProjectSchema
    from sunwell.memory.simulacrum.core.planning_context import PlanningContext
    from sunwell.memory.simulacrum.core.store import SimulacrumStore


# =============================================================================
# Scoring Version (RFC-116)
# =============================================================================


class ScoringVersion(Enum):
    """Harmonic scoring formula version.

    RFC-116: Scoring v2 replaces parallelism-biased scoring with
    domain-aware metrics that recognize irreducible depth and mid-graph parallelism.
    """

    V1 = "v1"
    """Original scoring: parallelism_factor * 40 + balance * 30 + 1/depth * 20 + conflicts * 10."""

    V2 = "v2"
    """RFC-116: Wave analysis + semantic coherence + depth utilization."""

    AUTO = "auto"
    """Use V2 with V1 fallback if V2 score is suspiciously low."""


# =============================================================================
# HarmonicPlanner
# =============================================================================


@dataclass(slots=True)
class HarmonicPlanner:
    """Plans by generating multiple candidates and selecting the best (RFC-038).

    Implements Harmonic Planning: structured variance in plan generation
    followed by quantitative evaluation and selection.

    RFC-116: Supports v2 scoring with domain-aware metrics.
    RFC-122: Integrates knowledge from SimulacrumStore via Convergence.

    Example:
        >>> planner = HarmonicPlanner(
        ...     model=my_model,
        ...     candidates=5,
        ...     variance=VarianceStrategy.PROMPTING,
        ...     scoring_version=ScoringVersion.V2,
        ... )
        >>> graph, metrics = await planner.plan_with_metrics("Build REST API")
        >>> print(f"Selected: depth={metrics.depth}, score={metrics.score:.1f}")
    """

    model: ModelProtocol
    """Model for artifact discovery."""

    candidates: int = 5
    """Number of plan candidates to generate."""

    variance: VarianceStrategy = VarianceStrategy.PROMPTING
    """Strategy for generating plan variance."""

    refinement_rounds: int = 1
    """Rounds of iterative refinement after selection (0 to disable)."""

    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    """Artifact limits passed to underlying ArtifactPlanner."""

    # RFC-035: Schema-aware planning
    project_schema: ProjectSchema | None = None
    """Project schema for domain-specific artifact types."""

    # Naaru integration
    convergence: Convergence | None = None
    """Shared working memory for context caching."""

    use_free_threading: bool = True
    """Use ThreadPoolExecutor for parallel scoring (benefits from 3.14t)."""

    # RFC-058: Event callback for planning visibility
    event_callback: Callable[[Any], None] | None = None
    """Optional callback for emitting planning visibility events (RFC-058)."""

    # RFC-116: Harmonic Scoring v2
    scoring_version: ScoringVersion = ScoringVersion.V2
    """Scoring formula version (V1=original, V2=domain-aware, AUTO=adaptive)."""

    log_scoring_disagreements: bool = True
    """Log when V1 and V2 would select different candidates (for A/B analysis)."""

    # RFC-122: Knowledge integration via SimulacrumStore
    simulacrum: SimulacrumStore | None = None
    """Reference to SimulacrumStore for knowledge retrieval (RFC-122)."""

    # Internal state
    _logger: logging.Logger = field(default=None, init=False)
    _last_planning_context: PlanningContext | None = field(default=None, init=False)
    """Last planning context retrieved (for Agent learning loop)."""

    def __post_init__(self) -> None:
        """Initialize logger for RFC-116 scoring disagreement logging."""
        object.__setattr__(self, "_logger", logging.getLogger(__name__))

    @property
    def mode(self) -> TaskMode:
        """This planner produces composite tasks."""
        return TaskMode.COMPOSITE

    # =========================================================================
    # RFC-058: Event Emission
    # =========================================================================

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event via callback if configured (RFC-058).

        RFC-060: Uses create_validated_event() for schema validation.
        Validation mode controlled by SUNWELL_EVENT_VALIDATION env var.
        RFC-112: Debug logging for Observatory event flow verification.
        """
        self._logger.debug(f"[Observatory] Emitting event: {event_type} (callback={'set' if self.event_callback else 'NOT SET'})")

        if self.event_callback is None:
            self._logger.debug(f"[Observatory] Event {event_type} dropped - no callback configured")
            return

        try:
            from sunwell.agent.events.schemas import create_validated_event
            from sunwell.agent.events import EventType

            # RFC-060: Validate event data against schema
            event = create_validated_event(EventType(event_type), data)
            self.event_callback(event)
            self._logger.debug(f"[Observatory] Event {event_type} delivered successfully")
        except ValueError as e:
            # Invalid event type or validation failure (strict mode)
            self._logger.warning(f"Event validation failed for '{event_type}': {e}")
        except Exception as e:
            # Other errors - log but don't break planning
            logging.warning(f"Event emission failed for '{event_type}': {e}")

    # =========================================================================
    # Main API
    # =========================================================================

    async def plan(
        self,
        goals: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Plan with harmonic optimization, return RFC-034 tasks.

        This is the TaskPlanner protocol implementation.

        Args:
            goals: User-specified goals
            context: Optional context (cwd, files, etc.)

        Returns:
            List of Tasks with dependencies in execution order
        """
        goal = goals[0] if goals else "No goal specified"
        graph, _ = await self.plan_with_metrics(goal, context)
        return artifacts_to_tasks(graph)

    async def plan_with_metrics(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[ArtifactGraph, PlanMetrics | PlanMetricsV2]:
        """Plan with harmonic optimization, return graph and metrics.

        This is the main entry point that:
        1. RFC-122: Retrieves relevant knowledge from SimulacrumStore
        2. RFC-122: If template matches with high confidence, uses template-guided planning
        3. Generates N candidate plans in parallel
        4. Scores each plan (V1 or V2 based on scoring_version)
        5. Selects the best
        6. Optionally refines

        RFC-116: Returns PlanMetricsV2 when scoring_version is V2 or AUTO.
        RFC-122: Integrates knowledge from SimulacrumStore via Convergence.

        Args:
            goal: The goal to achieve
            context: Optional context

        Returns:
            Tuple of (best_graph, metrics)
        """
        # RFC-122: Retrieve relevant knowledge from SimulacrumStore
        planning_context = None
        if self.simulacrum:
            planning_context = await self.simulacrum.retrieve_for_planning(goal)
            object.__setattr__(self, "_last_planning_context", planning_context)

            # Emit knowledge retrieved event
            self._emit_event("knowledge_retrieved", {
                "facts_count": len(planning_context.facts),
                "constraints_count": len(planning_context.constraints),
                "dead_ends_count": len(planning_context.dead_ends),
                "templates_count": len(planning_context.templates),
                "heuristics_count": len(planning_context.heuristics),
                "patterns_count": len(planning_context.patterns),
            })

            # Inject into Convergence for use during generation
            if self.convergence and planning_context:
                for slot in planning_context.to_convergence_slots():
                    await self.convergence.add(slot)

        # RFC-122: Check for high-confidence template match
        template = planning_context.best_template if planning_context else None
        if template and template.template_data and template.confidence >= 0.8:
            self._emit_event("template_matched", {
                "template_id": template.id,
                "template_name": template.template_data.name,
                "confidence": template.confidence,
            })
            return await plan_with_template(self, goal, template, planning_context, context)

        # Build context with knowledge if available
        enriched_context = dict(context) if context else {}
        if planning_context:
            enriched_context["knowledge_context"] = planning_context.to_prompt_section()

        # Generate candidates in parallel (returns CandidateResult objects with stable IDs)
        candidates = await generate_candidates(self, goal, enriched_context)

        if not candidates:
            # Fallback: single discovery
            from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

            fallback = ArtifactPlanner(
                model=self.model,
                limits=self.limits,
                project_schema=self.project_schema,
            )
            graph = await fallback.discover_graph(goal, context)
            return graph, self._score_plan(graph, goal)

        # Score each candidate (parallel if free-threading enabled)
        # RFC-116: Pass goal for V2 keyword coverage
        graphs = [c.graph for c in candidates]
        if self.use_free_threading and len(graphs) > 1:
            scores = await self._score_plans_parallel(graphs, goal)
        else:
            scores = [self._score_plan(g, goal) for g in graphs]

        # Create scored candidates (immutable, so create new with score)
        scored_candidates = [
            CandidateResult(
                id=c.id,
                graph=c.graph,
                variance_config=c.variance_config,
                score=scores[i],
            )
            for i, c in enumerate(candidates)
        ]

        # RFC-116: Log V1/V2 disagreements for A/B analysis
        if self.log_scoring_disagreements and self.scoring_version != ScoringVersion.V1:
            self._log_scoring_disagreement(scored_candidates, goal)

        # Emit scored events (use candidate_id for reliable matching)
        for i, candidate in enumerate(scored_candidates):
            effective_score = get_effective_score(candidate.score)
            self._emit_event("plan_candidate_scored", {
                "candidate_id": candidate.id,
                "score": effective_score,
                "scoring_version": self.scoring_version.value,
                "progress": i + 1,
                "total_candidates": len(candidates),
                "metrics": metrics_to_dict(candidate.score),
            })

        # Emit scoring complete event
        self._emit_event("plan_scoring_complete", {
            "total_scored": len(scores),
            "scoring_version": self.scoring_version.value,
        })

        # Sort by effective score (V1 or V2) and select best
        scored_candidates.sort(
            key=lambda c: get_effective_score(c.score), reverse=True
        )
        best = scored_candidates[0]

        # Track refinement state
        initial_score = get_effective_score(best.score)
        refinement_rounds_applied = 0
        best_graph = best.graph
        best_metrics = best.score

        # Optional refinement
        if self.refinement_rounds > 0:
            best_graph, best_metrics = await self._refine_plan(
                goal, best_graph, best_metrics, context
            )
            refinement_rounds_applied = self.refinement_rounds

        # Emit winner event with candidate_id (reliable matching)
        final_score = get_effective_score(best_metrics)
        self._emit_event("plan_winner", {
            "tasks": len(best_graph),
            "artifact_count": len(best_graph),
            "selected_candidate_id": best.id,
            "total_candidates": len(candidates),
            "score": final_score,
            "scoring_version": self.scoring_version.value,
            "metrics": metrics_to_dict(best_metrics),
            "selection_reason": format_selection_reason(
                best_metrics, len(scored_candidates)
            ),
            "variance_strategy": self.variance.value,
            "variance_config": best.variance_config,
            "refinement_rounds": refinement_rounds_applied,
            "final_score_improvement": (
                final_score - initial_score
                if refinement_rounds_applied > 0
                else 0.0
            ),
        })

        return best_graph, best_metrics

    def _log_scoring_disagreement(
        self,
        candidates: list[CandidateResult],
        goal: str,
    ) -> None:
        """Log when V1 and V2 would select different candidates (RFC-116).

        This helps with A/B analysis during migration.
        """
        if len(candidates) < 2:
            return

        # Sort by V1 score
        v1_sorted = sorted(candidates, key=lambda c: c.score.score, reverse=True)
        v1_winner = v1_sorted[0]

        # Sort by V2 score (if available)
        v2_sorted = sorted(
            candidates,
            key=lambda c: (
                c.score.score_v2 if isinstance(c.score, PlanMetricsV2) else c.score.score
            ),
            reverse=True,
        )
        v2_winner = v2_sorted[0]

        # Check for disagreement
        if v1_winner.id != v2_winner.id:
            v1_score = v1_winner.score.score
            v2_score_v1_winner = (
                v1_winner.score.score_v2
                if isinstance(v1_winner.score, PlanMetricsV2)
                else v1_winner.score.score
            )
            v2_score_v2_winner = (
                v2_winner.score.score_v2
                if isinstance(v2_winner.score, PlanMetricsV2)
                else v2_winner.score.score
            )
            v1_score_v2_winner = v2_winner.score.score

            self._logger.info(
                "RFC-116 scoring disagreement: "
                "V1 selects %s (v1=%.1f, v2=%.1f), "
                "V2 selects %s (v1=%.1f, v2=%.1f) | goal='%s'",
                v1_winner.id,
                v1_score,
                v2_score_v1_winner,
                v2_winner.id,
                v1_score_v2_winner,
                v2_score_v2_winner,
                goal[:50],
            )

    async def discover_graph(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ArtifactGraph:
        """Discover artifacts using harmonic planning.

        Compatibility with ArtifactPlanner interface.
        """
        graph, _ = await self.plan_with_metrics(goal, context)
        return graph

    async def create_artifact(
        self,
        artifact: ArtifactSpec,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Create the content for an artifact by delegating to base ArtifactPlanner.

        HarmonicPlanner uses ArtifactPlanner for actual artifact creation.
        This method is called during execution phase after planning completes.

        Args:
            artifact: The artifact specification
            context: Optional context (completed artifacts, cwd, etc.)

        Returns:
            Generated content as a string
        """
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

        # Create base planner for artifact creation
        base_planner = ArtifactPlanner(
            model=self.model,
            limits=self.limits,
            project_schema=self.project_schema,
        )

        # Delegate to base planner
        return await base_planner.create_artifact(artifact, context)

    @property
    def last_planning_context(self) -> PlanningContext | None:
        """Get the last planning context retrieved (RFC-122).

        Useful for the Agent learning loop to know what knowledge was used.
        """
        return self._last_planning_context

    # =========================================================================
    # Scoring (delegates to scoring.py)
    # =========================================================================

    def _score_plan(self, graph: ArtifactGraph, goal: str = "") -> PlanMetrics | PlanMetricsV2:
        """Compute metrics for a plan.

        RFC-116: Returns PlanMetricsV2 when scoring_version is V2 or AUTO,
        otherwise returns PlanMetrics (V1).
        """
        if self.scoring_version in (ScoringVersion.V2, ScoringVersion.AUTO):
            return compute_metrics_v2(graph, goal)
        return compute_metrics_v1(graph)

    async def _score_plans_parallel(
        self,
        candidates: list[ArtifactGraph],
        goal: str,
    ) -> list[PlanMetrics | PlanMetricsV2]:
        """Score all candidates in parallel threads.

        With free-threading (Python 3.14t):
        - Each thread computes metrics for one candidate
        - No GIL contention — true parallelism
        - CPU-bound work (graph traversal, metric computation)

        RFC-116: Pass goal for V2 keyword coverage computation.
        """

        def score_one(graph: ArtifactGraph) -> PlanMetrics | PlanMetricsV2:
            return self._score_plan(graph, goal)

        # Use thread pool for parallel scoring
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
            futures = [loop.run_in_executor(executor, score_one, g) for g in candidates]
            return list(await asyncio.gather(*futures))

    # =========================================================================
    # Iterative Refinement (delegates to refinement.py)
    # =========================================================================

    async def _refine_plan(
        self,
        goal: str,
        graph: ArtifactGraph,
        metrics: PlanMetrics | PlanMetricsV2,
        context: dict[str, Any] | None,
    ) -> tuple[ArtifactGraph, PlanMetrics | PlanMetricsV2]:
        """Iteratively refine the best plan.

        RFC-116: Uses effective score (V1 or V2 based on scoring_version).
        """
        current_graph = graph
        current_metrics = metrics
        initial_score = get_effective_score(metrics)

        for round_num in range(self.refinement_rounds):
            # Identify improvement opportunities
            feedback = identify_improvements(current_metrics)

            if not feedback:
                break  # No improvements identified

            # RFC-058: Emit refine start event
            current_score = get_effective_score(current_metrics)
            self._emit_event("plan_refine_start", {
                "round": round_num + 1,
                "total_rounds": self.refinement_rounds,
                "current_score": current_score,
                "improvements_identified": feedback,
            })

            # Ask LLM to refine
            refined = await refine_with_feedback(
                self, goal, current_graph, feedback, context
            )

            if refined is None:
                break  # Refinement failed

            # RFC-116: Re-score with goal for V2
            refined_metrics = self._score_plan(refined, goal)

            # RFC-058: Emit refine attempt event
            self._emit_event("plan_refine_attempt", {
                "round": round_num + 1,
                "improvements_applied": extract_applied_improvements(refined, current_graph),
            })

            # Only accept if improved (use effective score)
            new_score = get_effective_score(refined_metrics)
            old_score = get_effective_score(current_metrics)
            if new_score > old_score:
                current_graph = refined
                current_metrics = refined_metrics

                # RFC-058: Emit refine complete event (improved)
                self._emit_event("plan_refine_complete", {
                    "round": round_num + 1,
                    "improved": True,
                    "old_score": old_score,
                    "new_score": new_score,
                    "improvement": new_score - old_score,
                })
            else:
                # RFC-058: Emit refine complete event (no improvement)
                self._emit_event("plan_refine_complete", {
                    "round": round_num + 1,
                    "improved": False,
                    "reason": "Score did not improve",
                })
                break  # No improvement, stop

        # RFC-058: Emit refine final event
        final_score = get_effective_score(current_metrics)
        self._emit_event("plan_refine_final", {
            "total_rounds": round_num + 1 if round_num < self.refinement_rounds else self.refinement_rounds,
            "initial_score": initial_score,
            "final_score": final_score,
            "total_improvement": final_score - initial_score,
        })

        return current_graph, current_metrics

    # =========================================================================
    # Candidate Info (for verbose output)
    # =========================================================================

    def get_candidate_summary(
        self,
        candidates: list[ArtifactGraph],
        scores: list[PlanMetrics | PlanMetricsV2],
    ) -> list[dict]:
        """Get summary info for each candidate (for verbose CLI output).

        RFC-116: Includes V2 metrics when available.
        """
        summaries = []
        for i, (_graph, metrics) in enumerate(zip(candidates, scores, strict=True)):
            summary = {
                "index": i,
                "depth": metrics.depth,
                "leaves": metrics.leaf_count,
                "artifacts": metrics.artifact_count,
                "score_v1": metrics.score,
                "parallelism_factor": metrics.parallelism_factor,
                "balance_factor": metrics.balance_factor,
            }
            # Add V2 metrics if available
            if isinstance(metrics, PlanMetricsV2):
                summary.update({
                    "score_v2": metrics.score_v2,
                    "avg_wave_width": metrics.avg_wave_width,
                    "parallel_work_ratio": metrics.parallel_work_ratio,
                    "wave_variance": metrics.wave_variance,
                    "keyword_coverage": metrics.keyword_coverage,
                    "has_convergence": metrics.has_convergence,
                    "depth_utilization": metrics.depth_utilization,
                })
            summaries.append(summary)
        return summaries
