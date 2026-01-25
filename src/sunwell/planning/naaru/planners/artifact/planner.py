"""Main ArtifactPlanner orchestration class (RFC-036)."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import DEFAULT_LIMITS, ArtifactGraph, ArtifactLimits, artifacts_to_tasks
from sunwell.planning.naaru.planners.artifact import creation, discovery, events
from sunwell.planning.naaru.types import Task, TaskMode

if TYPE_CHECKING:
    from sunwell.agent.events import AgentEvent
    from sunwell.models.protocol import ModelProtocol
    from sunwell.knowledge.project.schema import ProjectSchema
    from sunwell.planning.routing.unified import UnifiedRouter

# Pre-compiled regex patterns
_RE_FILENAME = re.compile(r"(\w+\.(?:py|js|ts|md|txt|json|yaml|yml))")


@dataclass(slots=True)
class ArtifactPlanner:
    """Plans by discovering artifacts, not decomposing steps (RFC-036).

    Instead of procedural decomposition ("what steps?"), this planner
    identifies what artifacts must exist ("what things?") and lets
    dependency resolution determine execution order.

    Benefits:
    - Structural parallelism: leaves execute in parallel automatically
    - Adaptive model selection: depth determines model tier
    - Isolated failures: errors don't cascade to independent branches
    - Complexity-aware: trivial goals skip discovery entirely

    Example:
        >>> planner = ArtifactPlanner(
        ...     model=my_model,
        ...     limits=ArtifactLimits(max_artifacts=30),
        ... )
        >>> graph = await planner.discover_graph("Build a REST API with auth")
        >>> print(graph.execution_waves())
        [["UserProtocol", "AuthInterface"], ["UserModel", "AuthService"], ["App"]]

        # Trivial goals are handled efficiently:
        >>> graph = await planner.discover_graph("Create hello.py that prints Hello")
        >>> print(graph.execution_waves())
        [["main"]]  # Single artifact, no protocol overhead
    """

    model: ModelProtocol
    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    max_retries: int = 3

    # RFC-035: Schema-aware planning
    project_schema: ProjectSchema | None = None
    """Project schema for domain-specific artifact types."""

    # Complexity routing (optional): tiny model to assess before full discovery
    router: UnifiedRouter | None = None
    """Router for complexity assessment. If provided, trivial goals skip discovery."""

    # RFC-059: Event callback for discovery progress
    event_callback: Callable[[AgentEvent], None] | None = None
    """Optional callback for emitting discovery progress events (RFC-059)."""

    @property
    def mode(self) -> TaskMode:
        """This planner produces composite tasks."""
        return TaskMode.COMPOSITE

    async def plan(
        self,
        goals: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Discover artifacts and convert to RFC-034 tasks.

        This is the TaskPlanner protocol implementation, providing
        compatibility with existing execution infrastructure.

        Args:
            goals: User-specified goals
            context: Optional context (cwd, files, etc.)

        Returns:
            List of Tasks with dependencies in execution order

        Raises:
            PlanningError: If discovery fails
        """
        goal = goals[0] if goals else "No goal specified"
        graph = await self.discover_graph(goal, context)
        return artifacts_to_tasks(graph)

    async def discover_graph(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ArtifactGraph:
        """Discover artifacts and build dependency graph.

        Main entry point for artifact-first planning.

        If a router is configured, trivial goals skip full discovery and
        return a single artifact. This prevents over-engineering simple tasks
        like "create hello.py that prints Hello World".

        Args:
            goal: The goal to achieve
            context: Optional context

        Returns:
            ArtifactGraph ready for execution

        Raises:
            DiscoveryFailedError: If discovery fails after retries
            GraphExplosionError: If too many artifacts discovered
            CyclicDependencyError: If artifacts form a dependency cycle
        """
        # RFC-059: Emit discovery start
        events.emit_event(self.event_callback, "plan_discovery_progress", {
            "artifacts_discovered": 0,
            "phase": "discovering",
        })

        # Complexity gate: trivial goals skip full discovery
        if self.router is not None:
            try:
                decision = await self.router.route(goal, context)
                from sunwell.planning.routing.unified import Complexity

                if decision.complexity == Complexity.TRIVIAL:
                    graph = self._trivial_artifact(goal)
                    # RFC-059: Emit complete for trivial case
                    events.emit_event(self.event_callback, "plan_discovery_progress", {
                        "artifacts_discovered": len(graph),
                        "phase": "complete",
                    })
                    return graph
            except Exception:
                pass  # Fall through to full discovery on router failure

        return await discovery.discover_with_recovery(
            self.model,
            goal,
            context,
            self.project_schema,
            self.max_retries,
            self.limits,
            self.event_callback,
        )

    def _trivial_artifact(self, goal: str) -> ArtifactGraph:
        """Create single-artifact graph for trivial goals.

        Extracts filename from goal if mentioned, otherwise uses a sensible default.
        No protocols, no dependencies - just the artifact.
        """
        return discovery.trivial_artifact(goal)

    async def discover(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> list[Any]:  # list[ArtifactSpec]
        """Discover artifacts needed to complete a goal.

        Lower-level API that returns raw artifact specs without
        building the full graph.

        Args:
            goal: The goal to achieve
            context: Optional context

        Returns:
            List of ArtifactSpec objects
        """
        return await discovery.discover(
            self.model,
            goal,
            context,
            self.project_schema,
        )

    async def discover_new_artifacts(
        self,
        goal: str,
        completed: dict[str, Any],
        just_created: Any,  # ArtifactSpec
    ) -> list[Any]:  # list[ArtifactSpec]
        """Discover if creating an artifact revealed new needs.

        Called after creating an artifact to check for:
        - Missing dependencies that should have existed
        - Supporting artifacts needed for completeness
        - Expanded scope from contract refinement

        Args:
            goal: The original goal
            completed: Dict of completed artifact IDs to their results
            just_created: The artifact that was just created

        Returns:
            List of new artifacts to add (empty if none needed)
        """
        return await discovery.discover_new_artifacts(
            self.model,
            goal,
            completed,
            just_created,
        )

    async def create_artifact(
        self,
        artifact: Any,  # ArtifactSpec
        context: dict[str, Any] | None = None,
    ) -> str:
        """Create the content for an artifact based on its specification.

        Uses the model to generate code/content that satisfies the artifact's
        contract and description.

        Args:
            artifact: The artifact specification
            context: Optional context (completed artifacts, cwd, etc.)

        Returns:
            Generated content as a string
        """
        return await creation.create_artifact(
            self.model,
            artifact,
            context,
        )

    async def verify_artifact(
        self,
        artifact: Any,  # ArtifactSpec
        created_content: str,
    ) -> Any:  # VerificationResult
        """Verify that created content satisfies the artifact's contract.

        Uses LLM-based verification to check if the implementation
        matches the specification.

        Args:
            artifact: The artifact specification
            created_content: The actual content that was created

        Returns:
            VerificationResult with pass/fail and explanation
        """
        return await creation.verify_artifact(
            self.model,
            artifact,
            created_content,
        )
