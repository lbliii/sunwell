"""Harmonic Planner for RFC-038: Iterative DAG Shape Optimization.

This planner implements Harmonic Planning: generate multiple plan candidates,
evaluate them against performance metrics, and select the best.

The key insight: Just as Harmonic Synthesis uses structured variance (personas)
to improve output quality, Harmonic Planning uses structured variance
(temperature, prompting strategies) to improve plan quality.

Example:
    >>> planner = HarmonicPlanner(model=my_model, candidates=5)
    >>> graph, metrics = await planner.plan_with_metrics("Build REST API")
    >>> print(f"Selected: depth={metrics.depth}, parallelism={metrics.parallelism_factor:.2f}")
"""


import asyncio
import json
import re
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
from sunwell.naaru.types import Task, TaskMode

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.convergence import Convergence
    from sunwell.project.schema import ProjectSchema


# =============================================================================
# Plan Quality Metrics
# =============================================================================


@dataclass(frozen=True, slots=True)
class PlanMetrics:
    """Quantitative measures of plan quality.

    These metrics enable comparison and selection of plan candidates.
    Higher composite score = better plan for parallel execution.

    Attributes:
        depth: Critical path length (longest dependency chain)
        width: Maximum parallel artifacts at any level
        leaf_count: Artifacts with no dependencies (can start immediately)
        artifact_count: Total artifacts in the graph
        parallelism_factor: leaf_count / artifact_count (higher = more parallel)
        balance_factor: width / depth (higher = more balanced tree)
        file_conflicts: Pairs of artifacts that modify the same file
        estimated_waves: Minimum execution waves (topological levels)
    """

    depth: int
    """Critical path length (longest dependency chain)."""

    width: int
    """Maximum parallel artifacts at any level."""

    leaf_count: int
    """Artifacts with no dependencies (can start immediately)."""

    artifact_count: int
    """Total artifacts in the graph."""

    parallelism_factor: float
    """leaf_count / artifact_count — higher is more parallel."""

    balance_factor: float
    """width / depth — higher means more balanced tree."""

    file_conflicts: int
    """Pairs of artifacts that modify the same file."""

    estimated_waves: int
    """Minimum execution waves (topological levels)."""

    @property
    def score(self) -> float:
        """Composite score (higher is better).

        Formula balances parallelism against complexity:
        - Reward: high parallelism_factor, high balance_factor
        - Penalize: deep graphs, many file conflicts
        """
        return (
            self.parallelism_factor * 40
            + self.balance_factor * 30
            + (1 / max(self.depth, 1)) * 20
            + (1 / (1 + self.file_conflicts)) * 10
        )


# =============================================================================
# Candidate Result (ID-based tracking)
# =============================================================================


@dataclass(frozen=True, slots=True)
class CandidateResult:
    """A plan candidate with stable ID for tracking through transformations.

    Using explicit IDs instead of array indices prevents alignment bugs
    between frontend and backend when candidates are filtered or reordered.
    """

    id: str
    """Stable identifier (e.g., 'candidate-0', 'candidate-1')."""

    graph: ArtifactGraph
    """The artifact graph for this candidate."""

    variance_config: dict[str, Any]
    """Configuration used to generate this candidate."""

    score: PlanMetrics | None = None
    """Computed metrics (added after scoring)."""


# =============================================================================
# Variance Strategies
# =============================================================================


class VarianceStrategy(Enum):
    """Strategies for generating plan variance."""

    PROMPTING = "prompting"
    """Vary the discovery prompt emphasis (parallel-first, minimal, thorough)."""

    TEMPERATURE = "temperature"
    """Vary temperature (0.2, 0.4, 0.6) for different exploration."""

    CONSTRAINTS = "constraints"
    """Add different constraints (max depth, min parallelism)."""

    MIXED = "mixed"
    """Mix of prompting and temperature strategies."""


# Variance prompt templates - different prompts bias toward different plan shapes
VARIANCE_PROMPTS: dict[str, str] = {
    "parallel_first": """
OPTIMIZATION GOAL: MAXIMUM PARALLELISM

Prioritize:
1. Many leaf artifacts (no dependencies) that can execute in parallel
2. Shallow dependency chains (prefer wide over deep)
3. Split large artifacts into smaller, independent pieces

Ask: "Can this artifact be split? Can this dependency be removed?"
""",
    "minimal": """
OPTIMIZATION GOAL: MINIMUM ARTIFACTS

Prioritize:
1. Combine related artifacts where possible
2. Only essential artifacts (no nice-to-haves)
3. Direct paths from leaves to root

Ask: "Is this artifact truly necessary? Can two artifacts merge?"
""",
    "thorough": """
OPTIMIZATION GOAL: COMPLETE COVERAGE

Prioritize:
1. All edge cases and error handling
2. Complete test coverage as artifacts
3. Documentation and validation artifacts

Ask: "What could go wrong? What's missing for production-ready?"
""",
    "balanced": """
OPTIMIZATION GOAL: BALANCED STRUCTURE

Prioritize:
1. Consistent depth across branches
2. No single bottleneck artifact
3. Clear separation of concerns

Ask: "Is one branch deeper than others? Is there a bottleneck?"
""",
    "default": """
Discover artifacts naturally based on the goal.
Focus on what must exist when the goal is complete.
""",
}


# =============================================================================
# HarmonicPlanner
# =============================================================================


@dataclass
class HarmonicPlanner:
    """Plans by generating multiple candidates and selecting the best (RFC-038).

    Implements Harmonic Planning: structured variance in plan generation
    followed by quantitative evaluation and selection.

    Example:
        >>> planner = HarmonicPlanner(
        ...     model=my_model,
        ...     candidates=5,
        ...     variance=VarianceStrategy.PROMPTING,
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

    # Internal state
    _base_planner: Any = field(default=None, init=False)

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
    ) -> tuple[ArtifactGraph, PlanMetrics]:
        """Plan with harmonic optimization, return graph and metrics.

        This is the main entry point that:
        1. Generates N candidate plans in parallel
        2. Scores each plan
        3. Selects the best
        4. Optionally refines

        Args:
            goal: The goal to achieve
            context: Optional context

        Returns:
            Tuple of (best_graph, metrics)
        """
        # Generate candidates in parallel (returns CandidateResult objects with stable IDs)
        candidates = await self._generate_candidates(goal, context)

        if not candidates:
            # Fallback: single discovery
            from sunwell.naaru.planners.artifact import ArtifactPlanner

            fallback = ArtifactPlanner(
                model=self.model,
                limits=self.limits,
                project_schema=self.project_schema,
            )
            graph = await fallback.discover_graph(goal, context)
            return graph, self._score_plan(graph)

        # Score each candidate (parallel if free-threading enabled)
        graphs = [c.graph for c in candidates]
        if self.use_free_threading and len(graphs) > 1:
            scores = await self._score_plans_parallel(graphs)
        else:
            scores = [self._score_plan(g) for g in graphs]

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

        # Emit scored events (use candidate_id for reliable matching)
        for i, candidate in enumerate(scored_candidates):
            self._emit_event("plan_candidate_scored", {
                "candidate_id": candidate.id,
                "score": candidate.score.score,
                "progress": i + 1,
                "total_candidates": len(candidates),
                "metrics": {
                    "depth": candidate.score.depth,
                    "width": candidate.score.width,
                    "leaf_count": candidate.score.leaf_count,
                    "artifact_count": candidate.score.artifact_count,
                    "parallelism_factor": candidate.score.parallelism_factor,
                    "balance_factor": candidate.score.balance_factor,
                    "file_conflicts": candidate.score.file_conflicts,
                    "estimated_waves": candidate.score.estimated_waves,
                },
            })

        # Emit scoring complete event
        self._emit_event("plan_scoring_complete", {
            "total_scored": len(scores),
        })

        # Sort by score (descending) and select best
        scored_candidates.sort(key=lambda c: c.score.score, reverse=True)
        best = scored_candidates[0]

        # Track refinement state
        initial_score = best.score.score
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
        self._plan_winner_emitted = True
        self._emit_event("plan_winner", {
            "tasks": len(best_graph),
            "artifact_count": len(best_graph),
            "selected_candidate_id": best.id,
            "total_candidates": len(candidates),
            "score": best_metrics.score,
            "metrics": {
                "score": best_metrics.score,
                "depth": best_metrics.depth,
                "width": best_metrics.width,
                "leaf_count": best_metrics.leaf_count,
                "parallelism_factor": best_metrics.parallelism_factor,
                "balance_factor": best_metrics.balance_factor,
                "file_conflicts": best_metrics.file_conflicts,
                "estimated_waves": best_metrics.estimated_waves,
            },
            "selection_reason": self._format_selection_reason(
                best_metrics, scored_candidates
            ),
            "variance_strategy": self.variance.value,
            "variance_config": best.variance_config,
            "refinement_rounds": refinement_rounds_applied,
            "final_score_improvement": (
                best_metrics.score - initial_score
                if refinement_rounds_applied > 0
                else 0.0
            ),
        })

        return best_graph, best_metrics

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
        configs = self._get_variance_configs()

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
                varied_goal = self._apply_variance(goal, config)
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

    def _get_variance_configs(self) -> list[dict]:
        """Get variance configurations based on strategy."""
        if self.variance == VarianceStrategy.PROMPTING:
            configs = [
                {"prompt_style": "parallel_first"},
                {"prompt_style": "minimal"},
                {"prompt_style": "thorough"},
                {"prompt_style": "balanced"},
                {"prompt_style": "default", "temperature": 0.5},
            ]
            return configs[: self.candidates]

        elif self.variance == VarianceStrategy.TEMPERATURE:
            temps = [0.2, 0.3, 0.4, 0.5, 0.6][: self.candidates]
            return [{"temperature": t, "prompt_style": "default"} for t in temps]

        elif self.variance == VarianceStrategy.CONSTRAINTS:
            return [
                {"constraint": "max_depth=2", "prompt_style": "default"},
                {"constraint": "min_leaves=5", "prompt_style": "default"},
                {"constraint": "max_artifacts=8", "prompt_style": "default"},
                {"constraint": "no_bottlenecks", "prompt_style": "default"},
                {"constraint": None, "prompt_style": "default"},
            ][: self.candidates]

        elif self.variance == VarianceStrategy.MIXED:
            return [
                {"prompt_style": "parallel_first"},
                {"prompt_style": "minimal", "temperature": 0.4},
                {"prompt_style": "balanced"},
                {"prompt_style": "default", "temperature": 0.6},
                {"prompt_style": "thorough", "temperature": 0.3},
            ][: self.candidates]

        else:
            # Default: mix of strategies
            return [{"prompt_style": "default"}] * self.candidates

    def _apply_variance(self, goal: str, config: dict) -> str:
        """Apply variance configuration to the goal prompt."""
        prompt_style = config.get("prompt_style", "default")
        variance_prompt = VARIANCE_PROMPTS.get(prompt_style, VARIANCE_PROMPTS["default"])

        # Add constraint if present
        constraint = config.get("constraint")
        constraint_text = ""
        if constraint:
            constraint_text = f"\n\nCONSTRAINT: {constraint}"

        return f"{goal}\n\n{variance_prompt}{constraint_text}"

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
    # Plan Scoring
    # =========================================================================

    def _score_plan(self, graph: ArtifactGraph) -> PlanMetrics:
        """Compute metrics for a plan."""
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

    async def _score_plans_parallel(
        self,
        candidates: list[ArtifactGraph],
    ) -> list[PlanMetrics]:
        """Score all candidates in parallel threads.

        With free-threading (Python 3.14t):
        - Each thread computes metrics for one candidate
        - No GIL contention — true parallelism
        - CPU-bound work (graph traversal, metric computation)
        """

        def score_one(graph: ArtifactGraph) -> PlanMetrics:
            return self._score_plan(graph)

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
        metrics: PlanMetrics,
        context: dict[str, Any] | None,
    ) -> tuple[ArtifactGraph, PlanMetrics]:
        """Iteratively refine the best plan."""
        current_graph = graph
        current_metrics = metrics
        initial_score = metrics.score

        for round_num in range(self.refinement_rounds):
            # Identify improvement opportunities
            feedback = self._identify_improvements(current_metrics)

            if not feedback:
                break  # No improvements identified

            # RFC-058: Emit refine start event
            self._emit_event("plan_refine_start", {
                "round": round_num + 1,
                "total_rounds": self.refinement_rounds,
                "current_score": current_metrics.score,
                "improvements_identified": feedback,
            })

            # Ask LLM to refine
            refined = await self._refine_with_feedback(
                goal, current_graph, feedback, context
            )

            if refined is None:
                break  # Refinement failed

            refined_metrics = self._score_plan(refined)

            # RFC-058: Emit refine attempt event
            self._emit_event("plan_refine_attempt", {
                "round": round_num + 1,
                "improvements_applied": self._extract_applied_improvements(refined, current_graph),
            })

            # Only accept if improved
            if refined_metrics.score > current_metrics.score:
                old_score = current_metrics.score
                current_graph = refined
                current_metrics = refined_metrics

                # RFC-058: Emit refine complete event (improved)
                self._emit_event("plan_refine_complete", {
                    "round": round_num + 1,
                    "improved": True,
                    "old_score": old_score,
                    "new_score": refined_metrics.score,
                    "improvement": refined_metrics.score - old_score,
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
        self._emit_event("plan_refine_final", {
            "total_rounds": round_num + 1 if round_num < self.refinement_rounds else self.refinement_rounds,
            "initial_score": initial_score,
            "final_score": current_metrics.score,
            "total_improvement": current_metrics.score - initial_score,
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

    def _identify_improvements(self, metrics: PlanMetrics) -> str | None:
        """Identify what could be improved in the plan."""
        suggestions = []

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
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return self._specs_from_data(data)
            except json.JSONDecodeError:
                pass

        # Strategy 2: Look for code block with JSON
        code_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
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
        best_metrics: PlanMetrics,
        candidates: list[CandidateResult],
    ) -> str:
        """Format selection reason for winner event."""
        if len(candidates) == 1:
            return "Only candidate generated"
        return "Highest composite score (parallelism + balance - depth penalty)"

    def get_candidate_summary(
        self,
        candidates: list[ArtifactGraph],
        scores: list[PlanMetrics],
    ) -> list[dict]:
        """Get summary info for each candidate (for verbose CLI output)."""
        summaries = []
        for i, (_graph, metrics) in enumerate(zip(candidates, scores, strict=True)):
            summaries.append(
                {
                    "index": i,
                    "depth": metrics.depth,
                    "leaves": metrics.leaf_count,
                    "artifacts": metrics.artifact_count,
                    "score": metrics.score,
                    "parallelism_factor": metrics.parallelism_factor,
                    "balance_factor": metrics.balance_factor,
                }
            )
        return summaries
