"""TaskPlanner protocol for RFC-032 Agent Mode, RFC-034 Contract-Aware Planning.

This module defines the TaskPlanner protocol, PlanningStrategy, and related exceptions.
"""


from enum import Enum
from typing import Any, Protocol, runtime_checkable

from sunwell.naaru.types import Task, TaskMode


class PlanningError(Exception):
    """Raised when task planning fails.

    This can happen when:
    - LLM returns unparseable response
    - Goal is too vague to decompose
    - Required context is missing
    """

    pass


class PlanningStrategy(Enum):
    """How to decompose tasks (RFC-034, RFC-036, RFC-038).

    Controls the planning strategy used by planners:
    - SEQUENTIAL: RFC-032 behavior - linear dependencies, no parallelization hints
    - CONTRACT_FIRST: RFC-034 - identify contracts/interfaces first, then implementations
    - RESOURCE_AWARE: RFC-034 - minimize file conflicts for maximum parallelism
    - ARTIFACT_FIRST: RFC-036 - identify artifacts, let dependencies determine order
    - HARMONIC: RFC-038 - multi-candidate optimization with variance strategies
    """

    SEQUENTIAL = "sequential"
    """RFC-032 behavior: linear dependencies, no parallelization info."""

    CONTRACT_FIRST = "contract_first"
    """RFC-034: identify contracts first, then parallel implementations."""

    RESOURCE_AWARE = "resource_aware"
    """RFC-034: minimize file conflicts for maximum parallelism."""

    ARTIFACT_FIRST = "artifact_first"
    """RFC-036: discover artifacts, dependency resolution determines order.

    Instead of decomposing goals into steps, identifies what must exist
    when the goal is complete. Enables structural parallelism (all leaves
    execute simultaneously) and adaptive model selection (depth determines
    complexity).
    """

    HARMONIC = "harmonic"
    """RFC-038: multi-candidate plan generation with quantitative selection.

    Generates N plan candidates using structured variance (prompting strategies,
    temperature), scores each by parallelism/depth/balance, selects the best.
    Optional iterative refinement improves the winner further.

    Benefits:
    - Better plans through structured variance (like Harmonic Synthesis)
    - Quantitative metrics for plan quality
    - Near-zero overhead with Naaru + free-threading
    """


@runtime_checkable
class TaskPlanner(Protocol):
    """Protocol for task planning/decomposition (RFC-032).

    Implementations:
    - SelfImprovementPlanner: Find opportunities in Sunwell's codebase
    - AgentPlanner: Decompose arbitrary user goals into tasks
    - HybridPlanner: Combines both modes (future)

    Example:
        >>> planner = AgentPlanner(model=my_model, available_tools=frozenset(["write_file"]))
        >>> tasks = await planner.plan(["Build a REST API"])
        >>> for task in tasks:
        ...     print(f"{task.id}: {task.description}")
    """

    async def plan(
        self,
        goals: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Decompose goals into executable tasks.

        Args:
            goals: User-specified goals or objectives
            context: Optional context (current directory, file state, etc.)

        Returns:
            List of Tasks ordered by priority, respecting dependencies

        Raises:
            PlanningError: If planning fails after retries
        """
        ...

    @property
    def mode(self) -> TaskMode:
        """The primary mode this planner produces."""
        ...
