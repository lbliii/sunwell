"""LearningPhase - Extract learnings from execution.

Part of the Agent phase extraction (Week 3 refactoring).

The learning phase:
1. Extracts patterns and facts from changed files
2. Records successes and failures
3. Updates memory stores
4. Syncs to PersistentMemory

This is the final phase extracted from Agent to make the codebase more modular.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.agent.events import AgentEvent, memory_learning_event
from sunwell.agent.learning import learn_from_execution

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.learning import LearningExtractor, LearningStore
    from sunwell.memory import PersistentMemory
    from sunwell.memory.simulacrum.core.planning_context import PlanningContext


@dataclass(frozen=True, slots=True)
class LearningResult:
    """Result of the learning phase.

    Contains the number of learnings extracted.
    """

    facts_extracted: int
    """Number of facts extracted."""

    categories_covered: set[str]
    """Categories of learnings extracted."""


@dataclass(slots=True)
class LearningPhase:
    """Learning phase - extract learnings from execution.

    This is the final phase in the agent execution flow:
    Orient → Plan → Execute → Learn

    The learning phase extracts patterns, facts, and insights from:
    - Changed files (code patterns, types, APIs)
    - Task outcomes (successes, failures)
    - Planning context (heuristics, templates)
    """

    goal: str
    """The goal that was executed."""

    success: bool
    """Whether execution succeeded."""

    task_graph: TaskGraph | None
    """Task graph that was executed."""

    learning_store: LearningStore
    """Store to save learnings to."""

    learning_extractor: LearningExtractor
    """Extractor for patterns and facts."""

    files_changed: list[str]
    """Files that were changed during execution."""

    last_planning_context: PlanningContext | None = None
    """Planning context for template/heuristic extraction."""

    memory: PersistentMemory | None = None
    """Optional memory to sync learnings to."""

    async def run(self) -> AsyncIterator[AgentEvent | LearningResult]:
        """Execute the learning phase.

        Yields:
            AgentEvent for each learning extracted
            LearningResult as final event with summary
        """
        facts_extracted = 0
        categories: set[str] = set()

        # Extract learnings from execution
        async for fact, category in learn_from_execution(
            goal=self.goal,
            success=self.success,
            task_graph=self.task_graph,
            learning_store=self.learning_store,
            learning_extractor=self.learning_extractor,
            files_changed=self.files_changed,
            last_planning_context=self.last_planning_context,
            memory=self.memory,
        ):
            yield memory_learning_event(fact=fact, category=category)
            facts_extracted += 1
            categories.add(category)

        # Return final result
        yield LearningResult(
            facts_extracted=facts_extracted,
            categories_covered=categories,
        )
