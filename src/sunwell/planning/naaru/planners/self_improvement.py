"""Self-improvement planner for RFC-032 Agent Mode.

This wraps the RFC-019 OpportunityDiscoverer as a TaskPlanner,
converting Opportunities to Tasks for agent mode execution.
"""


from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.naaru.types import Task, TaskMode

if TYPE_CHECKING:
    from sunwell.mirror import MirrorHandler


@dataclass(slots=True)
class SelfImprovementPlanner:
    """Plans self-improvement tasks for Sunwell (RFC-032).

    This is the RFC-019 OpportunityDiscoverer, repackaged as a TaskPlanner.
    It finds things Sunwell could improve about itself.

    Example:
        >>> planner = SelfImprovementPlanner(workspace=Path("."), mirror=mirror)
        >>> tasks = await planner.plan(["improve error handling"])
        >>> for task in tasks:
        ...     print(f"{task.mode}: {task.description}")
    """

    workspace: Path
    mirror: MirrorHandler

    @property
    def mode(self) -> TaskMode:
        """This planner produces self-improvement tasks."""
        return TaskMode.SELF_IMPROVE

    async def plan(
        self,
        goals: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Find improvement opportunities in Sunwell's codebase.

        Args:
            goals: What to focus improvement efforts on
            context: Optional context (unused for self-improvement)

        Returns:
            List of Tasks representing improvement opportunities
        """
        from sunwell.naaru.discovery import OpportunityDiscoverer

        # Use existing discoverer
        discoverer = OpportunityDiscoverer(
            mirror=self.mirror,
            workspace=self.workspace,
        )

        # Discover opportunities
        opportunities = await discoverer.discover(goals)

        # Convert to Tasks directly (no conversion method needed)
        tasks = [
            Task(
                id=opp.id,
                description=opp.description,
                mode=TaskMode.SELF_IMPROVE,
                target_path=opp.target_module,
                category=opp.category.value if hasattr(opp.category, "value") else str(opp.category),
                priority=opp.priority,
                estimated_effort=opp.estimated_effort,
                risk_level=opp.risk_level,
                details=opp.details,
            )
            for opp in opportunities
        ]

        return tasks
