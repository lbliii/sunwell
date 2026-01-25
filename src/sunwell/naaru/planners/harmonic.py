"""Harmonic Planner for RFC-038: Iterative DAG Shape Optimization.

This planner implements Harmonic Planning: generate multiple plan candidates,
evaluate them against performance metrics, and select the best.

The key insight: Just as Harmonic Synthesis uses structured variance (personas)
to improve output quality, Harmonic Planning uses structured variance
(temperature, prompting strategies) to improve plan quality.

RFC-116: Harmonic Scoring v2 adds domain-aware metrics that recognize:
- Irreducible depth (some goals require sequential phases)
- Mid-graph parallelism (fat waves in the middle matter)
- Semantic coherence (plans should cover the goal)

Example:
    >>> planner = HarmonicPlanner(model=my_model, candidates=5)
    >>> graph, metrics = await planner.plan_with_metrics("Build REST API")
    >>> print(f"Selected: depth={metrics.depth}, parallelism={metrics.parallelism_factor:.2f}")
"""


import asyncio
import json
import logging
import re
import statistics
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import (
    DEFAULT_LIMITS,
    ArtifactGraph,
    ArtifactLimits,
    ArtifactSpec,
    artifacts_to_tasks,
)
from sunwell.naaru.planners.metrics import CandidateResult, PlanMetrics, PlanMetricsV2
from sunwell.naaru.planners.variance import (
    VarianceStrategy,
    apply_variance,
    get_variance_configs,
)
from sunwell.naaru.types import Task, TaskMode

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.convergence import Convergence
    from sunwell.project.schema import ProjectSchema
    from sunwell.simulacrum.core.planning_context import PlanningContext
    from sunwell.simulacrum.core.store import SimulacrumStore
    from sunwell.simulacrum.core.turn import Learning, TemplateData


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


# Stopwords for keyword extraction (fast, no LLM)
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "was", "are", "were", "been", "be", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "shall", "can", "need", "dare", "ought", "used", "it", "its",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "our", "their", "what", "which",
    "who", "whom", "where", "when", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "same", "so", "than", "too", "very", "just", "also", "now", "here", "there",
    "then", "once", "into", "onto", "upon", "after", "before", "above", "below",
    "between", "under", "over", "through", "during", "without", "within", "along",
    "following", "across", "behind", "beyond", "plus", "except", "about", "like",
    "create", "build", "make", "add", "implement", "write", "using", "use",
})

# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_RE_JSON_OBJECT = re.compile(r"\{[^}]+\}")
_RE_WORD_SPLIT = re.compile(r"[^a-zA-Z0-9]+")
_RE_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_RE_JSON_CODE_BLOCK = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)


# =============================================================================
# HarmonicPlanner
# =============================================================================


@dataclass(slots=True)
class HarmonicPlanner:
    """Plans by generating multiple candidates and selecting the best (RFC-038).

    Implements Harmonic Planning: structured variance in plan generation
    followed by quantitative evaluation and selection.

    RFC-116: Supports v2 scoring with domain-aware metrics.

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
    _base_planner: Any = field(default=None, init=False)
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
        """
        if self.event_callback is None:
            return

        try:
            from sunwell.agent.event_schema import create_validated_event
            from sunwell.agent.events import EventType

            # RFC-060: Validate event data against schema
            event = create_validated_event(EventType(event_type), data)
            self.event_callback(event)
        except ValueError as e:
            # Invalid event type or validation failure (strict mode)
            import logging
            logging.warning(f"Event validation failed for '{event_type}': {e}")
        except Exception as e:
            # Other errors - log but don't break planning
            import logging
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
            return await self._plan_with_template(goal, template, planning_context, context)

        # Build context with knowledge if available
        enriched_context = dict(context) if context else {}
        if planning_context:
            enriched_context["knowledge_context"] = planning_context.to_prompt_section()

        # Generate candidates in parallel (returns CandidateResult objects with stable IDs)
        candidates = await self._generate_candidates(goal, enriched_context)

        if not candidates:
            # Fallback: single discovery
            from sunwell.naaru.planners.artifact import ArtifactPlanner

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
            effective_score = self._get_effective_score(candidate.score)
            self._emit_event("plan_candidate_scored", {
                "candidate_id": candidate.id,
                "score": effective_score,
                "scoring_version": self.scoring_version.value,
                "progress": i + 1,
                "total_candidates": len(candidates),
                "metrics": self._metrics_to_dict(candidate.score),
            })

        # Emit scoring complete event
        self._emit_event("plan_scoring_complete", {
            "total_scored": len(scores),
            "scoring_version": self.scoring_version.value,
        })

        # Sort by effective score (V1 or V2) and select best
        scored_candidates.sort(
            key=lambda c: self._get_effective_score(c.score), reverse=True
        )
        best = scored_candidates[0]

        # Track refinement state
        initial_score = self._get_effective_score(best.score)
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
        final_score = self._get_effective_score(best_metrics)
        self._emit_event("plan_winner", {
            "tasks": len(best_graph),
            "artifact_count": len(best_graph),
            "selected_candidate_id": best.id,
            "total_candidates": len(candidates),
            "score": final_score,
            "scoring_version": self.scoring_version.value,
            "metrics": self._metrics_to_dict(best_metrics),
            "selection_reason": self._format_selection_reason(
                best_metrics, scored_candidates
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

    def _metrics_to_dict(self, metrics: PlanMetrics | PlanMetricsV2) -> dict[str, Any]:
        """Convert metrics to dict for event emission."""
        base = {
            "depth": metrics.depth,
            "width": metrics.width,
            "leaf_count": metrics.leaf_count,
            "artifact_count": metrics.artifact_count,
            "parallelism_factor": metrics.parallelism_factor,
            "balance_factor": metrics.balance_factor,
            "file_conflicts": metrics.file_conflicts,
            "estimated_waves": metrics.estimated_waves,
            "score_v1": metrics.score,
        }
        if isinstance(metrics, PlanMetricsV2):
            base.update({
                "score_v2": metrics.score_v2,
                "wave_sizes": list(metrics.wave_sizes),
                "avg_wave_width": metrics.avg_wave_width,
                "parallel_work_ratio": metrics.parallel_work_ratio,
                "wave_variance": metrics.wave_variance,
                "keyword_coverage": metrics.keyword_coverage,
                "has_convergence": metrics.has_convergence,
                "depth_utilization": metrics.depth_utilization,
            })
        return base

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
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        # Create base planner for artifact creation
        base_planner = ArtifactPlanner(
            model=self.model,
            limits=self.limits,
            project_schema=self.project_schema,
        )

        # Delegate to base planner
        return await base_planner.create_artifact(artifact, context)

    # =========================================================================
    # RFC-122: Template-Guided Planning
    # =========================================================================

    async def _plan_with_template(
        self,
        goal: str,
        template: Learning,
        planning_context: PlanningContext,
        additional_context: dict[str, Any] | None,
    ) -> tuple[ArtifactGraph, PlanMetrics | PlanMetricsV2]:
        """Plan using template structure (RFC-122).

        When a high-confidence template matches, we use its structure
        to generate artifacts directly instead of harmonic candidate generation.

        Args:
            goal: Task goal
            template: Matched template Learning
            planning_context: Full planning context
            additional_context: Additional context from caller

        Returns:
            Tuple of (artifact_graph, metrics)
        """
        template_data = template.template_data

        # Extract variables from goal
        variables = await self._extract_template_variables(goal, template_data)

        # Build artifacts from template
        artifacts: list[ArtifactSpec] = []
        for artifact_pattern in template_data.expected_artifacts:
            resolved = self._substitute_variables(artifact_pattern, variables)
            artifacts.append(ArtifactSpec(
                id=resolved.replace("/", "_").replace(".", "_"),
                description=f"Create {resolved}",
                produces=(resolved,),
                produces_file=resolved,
                requires=frozenset(
                    self._substitute_variables(r, variables)
                    for r in template_data.requires
                ),
            ))

        # Build graph
        graph = ArtifactGraph(limits=self.limits)
        for artifact in artifacts:
            try:
                graph.add(artifact)
            except ValueError:
                continue  # Skip duplicates

        # Compute metrics
        metrics = self._score_plan(graph, goal)

        # Emit template planning complete event
        self._emit_event("plan_winner", {
            "tasks": len(graph),
            "artifact_count": len(graph),
            "selected_candidate_id": "template-guided",
            "total_candidates": 1,
            "score": self._get_effective_score(metrics),
            "scoring_version": self.scoring_version.value,
            "metrics": self._metrics_to_dict(metrics),
            "selection_reason": f"Template-guided: {template_data.name}",
            "variance_strategy": "template",
            "variance_config": {
                "template_name": template_data.name,
                "template_id": template.id,
                "variables": variables,
            },
            "refinement_rounds": 0,
            "final_score_improvement": 0.0,
        })

        return graph, metrics

    async def _extract_template_variables(
        self,
        goal: str,
        template_data: TemplateData,
    ) -> dict[str, str]:
        """Extract variable values from goal text using LLM (RFC-122).

        Args:
            goal: The task goal
            template_data: Template with variable definitions

        Returns:
            Dict mapping variable names to extracted values
        """
        if not template_data.variables:
            return {}

        from sunwell.models.protocol import GenerateOptions

        var_specs = "\n".join(
            f"- {v.name}: {v.description} (hints: {', '.join(v.extraction_hints)})"
            for v in template_data.variables
        )

        prompt = f"""Extract template variables from this goal.

Template: {template_data.name}
Variables to extract:
{var_specs}

Goal: "{goal}"

Return JSON mapping variable names to extracted values.
Example: {{"entity": "Product"}}

IMPORTANT: Return ONLY the JSON object, no other text."""

        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.1, max_tokens=200),
            )

            # Parse JSON from response
            json_match = _RE_JSON_OBJECT.search(result.text or result.content)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except (json.JSONDecodeError, Exception):
            return {}

    def _substitute_variables(
        self,
        pattern: str,
        variables: dict[str, str],
    ) -> str:
        """Substitute {{var}} patterns in template strings (RFC-122).

        Supports:
        - {{var}} - direct substitution
        - {{var_lower}} - lowercase version
        - {{var_upper}} - uppercase version

        Args:
            pattern: Template pattern with {{var}} placeholders
            variables: Variable name to value mapping

        Returns:
            Pattern with variables substituted
        """
        result = pattern
        for name, value in variables.items():
            # Direct substitution: {{name}}
            result = result.replace("{{" + name + "}}", value)
            # Lowercase: {{name_lower}}
            result = result.replace("{{" + name + "_lower}}", value.lower())
            # Uppercase: {{name_upper}}
            result = result.replace("{{" + name + "_upper}}", value.upper())
        return result

    @property
    def last_planning_context(self) -> PlanningContext | None:
        """Get the last planning context retrieved (RFC-122).

        Useful for the Agent learning loop to know what knowledge was used.
        """
        return self._last_planning_context

    # =========================================================================
    # Candidate Generation
    # =========================================================================

    async def _generate_candidates(
        self,
        goal: str,
        context: dict[str, Any] | None,
    ) -> list[CandidateResult]:
        """Generate N candidate plans in parallel.

        Returns CandidateResult objects with stable IDs for reliable
        frontend/backend alignment (no index confusion).
        """
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        # Create base planner
        base_planner = ArtifactPlanner(
            model=self.model,
            limits=self.limits,
            project_schema=self.project_schema,
        )

        # Pre-populate convergence if available
        if self.convergence:
            await self._warm_convergence(goal, context)

        # Generate variance configurations
        configs = get_variance_configs(self.variance, self.candidates)

        # RFC-058: Emit candidate generation start event
        self._emit_event("plan_candidate_start", {
            "total_candidates": len(configs),
            "variance_strategy": self.variance.value,
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
                self._emit_event("plan_candidate_generated", {
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
        self._emit_event("plan_candidates_complete", {
            "total_candidates": len(configs),
            "successful_candidates": len(candidates),
            "failed_candidates": len(configs) - len(candidates),
        })

        return candidates


    async def _warm_convergence(
        self,
        goal: str,
        context: dict[str, Any] | None,
    ) -> None:
        """Pre-populate Convergence with shared context."""
        if not self.convergence:
            return

        from sunwell.naaru.convergence import Slot, SlotSource

        # Add goal context
        await self.convergence.add(
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
            await self.convergence.add(
                Slot(
                    id="harmonic:context",
                    content=context,
                    relevance=0.9,
                    source=SlotSource.CONTEXT_PREPARER,
                    ttl=300,
                )
            )

    # =========================================================================
    # Plan Scoring (RFC-116: V1 and V2 support)
    # =========================================================================

    def _score_plan(self, graph: ArtifactGraph, goal: str = "") -> PlanMetrics | PlanMetricsV2:
        """Compute metrics for a plan.

        RFC-116: Returns PlanMetricsV2 when scoring_version is V2 or AUTO,
        otherwise returns PlanMetrics (V1).
        """
        if self.scoring_version in (ScoringVersion.V2, ScoringVersion.AUTO):
            return self._compute_metrics_v2(graph, goal)
        return self._compute_metrics_v1(graph)

    def _compute_metrics_v1(self, graph: ArtifactGraph) -> PlanMetrics:
        """Compute V1 metrics for a plan."""
        depth = graph.max_depth()
        leaves = graph.leaves()
        artifacts = list(graph.artifacts.values())
        waves = graph.execution_waves()

        # Compute width (max artifacts in any wave)
        width = max(len(w) for w in waves) if waves else 1

        # Count file conflicts
        file_artifacts: dict[str, list[str]] = {}
        for a in artifacts:
            if a.produces_file:
                file_artifacts.setdefault(a.produces_file, []).append(a.id)
        conflicts = sum(
            len(ids) * (len(ids) - 1) // 2  # Combinations
            for ids in file_artifacts.values()
            if len(ids) > 1
        )

        artifact_count = len(artifacts)

        return PlanMetrics(
            depth=depth,
            width=width,
            leaf_count=len(leaves),
            artifact_count=artifact_count,
            parallelism_factor=len(leaves) / max(artifact_count, 1),
            balance_factor=width / max(depth, 1),
            file_conflicts=conflicts,
            estimated_waves=len(waves),
        )

    def _compute_metrics_v2(self, graph: ArtifactGraph, goal: str) -> PlanMetricsV2:
        """Compute V2 metrics for a plan (RFC-116).

        V2 adds:
        - Wave analysis (avg_wave_width, parallel_work_ratio, wave_variance)
        - Semantic signals (keyword_coverage, has_convergence)
        - Depth utilization (using depth productively)
        """
        # Base metrics (same as V1)
        depth = graph.max_depth()
        leaves = graph.leaves()
        artifacts = list(graph.artifacts.values())
        waves = graph.execution_waves()

        # Compute width (max artifacts in any wave)
        width = max(len(w) for w in waves) if waves else 1

        # Count file conflicts
        file_artifacts: dict[str, list[str]] = {}
        for a in artifacts:
            if a.produces_file:
                file_artifacts.setdefault(a.produces_file, []).append(a.id)
        conflicts = sum(
            len(ids) * (len(ids) - 1) // 2  # Combinations
            for ids in file_artifacts.values()
            if len(ids) > 1
        )

        artifact_count = len(artifacts)
        num_waves = len(waves)

        # V2: Wave analysis
        wave_sizes = tuple(len(w) for w in waves)
        avg_wave_width = artifact_count / max(num_waves, 1)
        parallel_work_ratio = (artifact_count - 1) / max(num_waves - 1, 1)
        wave_variance = statistics.stdev(wave_sizes) if len(wave_sizes) > 1 else 0.0

        # V2: Depth utilization — high value = doing parallel work relative to depth
        depth_utilization = avg_wave_width / max(depth, 1)

        # V2: Lightweight semantic check — keyword coverage
        goal_keywords = set(self._extract_keywords(goal))
        artifact_keywords: set[str] = set()
        for artifact in artifacts:
            artifact_keywords.update(self._extract_keywords(artifact.description))
            artifact_keywords.update(self._extract_keywords(artifact.id))

        if goal_keywords:
            keyword_coverage = len(goal_keywords & artifact_keywords) / len(goal_keywords)
        else:
            keyword_coverage = 1.0  # No keywords = assume full coverage

        # V2: Convergence check — single root is proper DAG structure
        roots = graph.roots()
        has_convergence = len(roots) == 1

        return PlanMetricsV2(
            # Base metrics (V1)
            depth=depth,
            width=width,
            leaf_count=len(leaves),
            artifact_count=artifact_count,
            parallelism_factor=len(leaves) / max(artifact_count, 1),
            balance_factor=width / max(depth, 1),
            file_conflicts=conflicts,
            estimated_waves=num_waves,
            # V2 extensions
            wave_sizes=wave_sizes,
            avg_wave_width=avg_wave_width,
            parallel_work_ratio=parallel_work_ratio,
            wave_variance=wave_variance,
            keyword_coverage=keyword_coverage,
            has_convergence=has_convergence,
            depth_utilization=depth_utilization,
        )

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract significant keywords from text (fast, no LLM).

        RFC-116: Used for lightweight semantic checking.
        Filters stopwords and short words, returns lowercase keywords.
        """
        if not text:
            return []
        # Split on non-alphanumeric, lowercase, filter
        words = _RE_WORD_SPLIT.split(text.lower())
        return [w for w in words if len(w) > 3 and w not in _STOPWORDS]

    def _get_effective_score(self, metrics: PlanMetrics | PlanMetricsV2) -> float:
        """Get the effective score based on scoring version.

        RFC-116: V2 metrics use score_v2, V1 metrics use score.
        """
        if isinstance(metrics, PlanMetricsV2):
            return metrics.score_v2
        return metrics.score

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
    # Iterative Refinement
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
        initial_score = self._get_effective_score(metrics)

        for round_num in range(self.refinement_rounds):
            # Identify improvement opportunities
            feedback = self._identify_improvements(current_metrics)

            if not feedback:
                break  # No improvements identified

            # RFC-058: Emit refine start event
            current_score = self._get_effective_score(current_metrics)
            self._emit_event("plan_refine_start", {
                "round": round_num + 1,
                "total_rounds": self.refinement_rounds,
                "current_score": current_score,
                "improvements_identified": feedback,
            })

            # Ask LLM to refine
            refined = await self._refine_with_feedback(
                goal, current_graph, feedback, context
            )

            if refined is None:
                break  # Refinement failed

            # RFC-116: Re-score with goal for V2
            refined_metrics = self._score_plan(refined, goal)

            # RFC-058: Emit refine attempt event
            self._emit_event("plan_refine_attempt", {
                "round": round_num + 1,
                "improvements_applied": self._extract_applied_improvements(refined, current_graph),
            })

            # Only accept if improved (use effective score)
            new_score = self._get_effective_score(refined_metrics)
            old_score = self._get_effective_score(current_metrics)
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
        final_score = self._get_effective_score(current_metrics)
        self._emit_event("plan_refine_final", {
            "total_rounds": round_num + 1 if round_num < self.refinement_rounds else self.refinement_rounds,
            "initial_score": initial_score,
            "final_score": final_score,
            "total_improvement": final_score - initial_score,
        })

        return current_graph, current_metrics

    def _extract_applied_improvements(
        self,
        refined: ArtifactGraph,
        original: ArtifactGraph,
    ) -> str:
        """Extract description of improvements applied (RFC-058)."""
        # Simple heuristic: compare artifact counts and structure
        if len(refined) > len(original):
            return f"Added {len(refined) - len(original)} artifacts"
        elif len(refined) < len(original):
            return f"Removed {len(original) - len(refined)} artifacts"
        else:
            return "Restructured dependencies"

    def _identify_improvements(self, metrics: PlanMetrics | PlanMetricsV2) -> str | None:
        """Identify what could be improved in the plan.

        RFC-116: V2 metrics add wave analysis and semantic checks.
        """
        suggestions = []

        # V1-compatible checks
        if metrics.depth > 3:
            suggestions.append(
                f"Critical path is {metrics.depth} steps. "
                "Can any artifacts be parallelized instead of sequential?"
            )

        if metrics.parallelism_factor < 0.3:
            suggestions.append(
                f"Only {metrics.leaf_count}/{metrics.artifact_count} artifacts are leaves. "
                "Can more artifacts have no dependencies?"
            )

        if metrics.file_conflicts > 0:
            suggestions.append(
                f"Found {metrics.file_conflicts} file conflicts. "
                "Can artifacts write to different files?"
            )

        if metrics.balance_factor < 0.5:
            suggestions.append(
                "Graph is unbalanced (deep and narrow). "
                "Can the structure be flattened?"
            )

        # V2-specific checks (RFC-116)
        if isinstance(metrics, PlanMetricsV2):
            if metrics.wave_variance > 5.0:
                suggestions.append(
                    f"Wave sizes are unbalanced (variance={metrics.wave_variance:.1f}). "
                    "Can work be distributed more evenly across waves?"
                )

            if metrics.keyword_coverage < 0.5:
                suggestions.append(
                    f"Low keyword coverage ({metrics.keyword_coverage:.0%}). "
                    "Are all aspects of the goal addressed by artifacts?"
                )

            if not metrics.has_convergence:
                suggestions.append(
                    "Graph has multiple roots (no single convergence point). "
                    "Should there be a final integration artifact?"
                )

            if metrics.depth_utilization < 1.0 and metrics.depth > 2:
                suggestions.append(
                    f"Depth utilization is low ({metrics.depth_utilization:.1f}). "
                    "Depth is not being used productively for parallelism."
                )

        return " ".join(suggestions) if suggestions else None

    async def _refine_with_feedback(
        self,
        goal: str,
        graph: ArtifactGraph,
        feedback: str,
        context: dict[str, Any] | None,
    ) -> ArtifactGraph | None:
        """Ask LLM to refine a plan based on feedback."""
        artifacts_desc = "\n".join(
            f"- {a.id}: requires {list(a.requires)}" for a in graph.artifacts.values()
        )

        prompt = f"""GOAL: {goal}

CURRENT PLAN:
{artifacts_desc}

METRICS:
- Depth (critical path): {graph.max_depth()}
- Leaves (parallel start): {len(graph.leaves())}
- Total artifacts: {len(graph.artifacts)}

IMPROVEMENT FEEDBACK:
{feedback}

=== REFINEMENT TASK ===

Restructure the artifact graph to address the feedback.
Keep the same essential artifacts but reorganize dependencies
for better parallelism and shallower depth.

Consider:
1. Can sequential artifacts become parallel (remove a dependency)?
2. Can a deep chain be split into parallel branches?
3. Can a bottleneck artifact be split into independent pieces?

Output the COMPLETE revised artifact list as JSON array:
[
  {{
    "id": "ArtifactName",
    "description": "What it is",
    "contract": "What it must satisfy",
    "requires": ["DependencyId"],
    "produces_file": "path/to/file.py",
    "domain_type": "protocol|model|service|etc"
  }}
]"""

        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=3000),
        )

        # Parse and build graph
        artifacts = self._parse_artifacts(result.content or "")
        if not artifacts:
            return None

        refined_graph = ArtifactGraph()
        for artifact in artifacts:
            try:
                refined_graph.add(artifact)
            except ValueError:
                # Duplicate ID - skip
                continue

        # Validate no cycles introduced
        if refined_graph.detect_cycle():
            return None

        return refined_graph

    def _parse_artifacts(self, response: str) -> list[ArtifactSpec]:
        """Parse LLM response into ArtifactSpec objects."""
        # Strategy 1: Find JSON array with regex
        json_match = _RE_JSON_ARRAY.search(response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return self._specs_from_data(data)
            except json.JSONDecodeError:
                pass

        # Strategy 2: Look for code block with JSON
        code_match = _RE_JSON_CODE_BLOCK.search(response)
        if code_match:
            try:
                data = json.loads(code_match.group(1))
                return self._specs_from_data(data)
            except json.JSONDecodeError:
                pass

        return []

    def _specs_from_data(self, data: list[dict]) -> list[ArtifactSpec]:
        """Convert parsed JSON to ArtifactSpec list."""
        artifacts = []
        for item in data:
            try:
                artifact = ArtifactSpec(
                    id=item["id"],
                    description=item.get("description", f"Artifact {item['id']}"),
                    contract=item.get("contract", ""),
                    produces_file=item.get("produces_file"),
                    requires=frozenset(item.get("requires", [])),
                    domain_type=item.get("domain_type"),
                    metadata=item.get("metadata", {}),
                )
                artifacts.append(artifact)
            except (KeyError, TypeError):
                continue
        return artifacts

    # =========================================================================
    # Candidate Info (for verbose output)
    # =========================================================================

    def _format_selection_reason(
        self,
        best_metrics: PlanMetrics | PlanMetricsV2,
        candidates: list[CandidateResult],
    ) -> str:
        """Format selection reason for winner event.

        RFC-116: Different descriptions for V1 vs V2 scoring.
        """
        if len(candidates) == 1:
            return "Only candidate generated"

        if isinstance(best_metrics, PlanMetricsV2):
            return (
                "Highest V2 score (parallel_work_ratio + depth_utilization "
                "+ keyword_coverage + wave_balance - conflicts)"
            )
        return "Highest V1 score (parallelism + balance - depth penalty)"

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
