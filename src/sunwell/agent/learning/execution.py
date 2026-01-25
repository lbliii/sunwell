"""Learning extraction from execution (RFC-042, RFC-122).

Extracts learnings from completed agent executions:
- Code patterns from generated files
- Fix strategies from successful corrections
- Templates from novel task completions
- Heuristics from task ordering
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.learning.extractor import LearningExtractor
    from sunwell.agent.learning.store import LearningStore
    from sunwell.agent.planning.types import PlanningContext
    from sunwell.memory.persistent import PersistentMemory


async def learn_from_execution(
    *,
    goal: str,
    success: bool,
    task_graph: "TaskGraph",
    learning_store: "LearningStore",
    learning_extractor: "LearningExtractor",
    files_changed: list[str],
    last_planning_context: "PlanningContext | None",
    memory: "PersistentMemory | None",
) -> AsyncIterator[tuple[str, str]]:
    """Extract learnings from completed execution (RFC-122).

    Analyzes the completed execution to extract:
    - Code patterns from generated files
    - Fix strategies from successful corrections
    - Templates from novel tasks
    - Heuristics from task ordering

    Args:
        goal: The goal that was executed
        success: Whether execution succeeded
        task_graph: The task graph that was executed
        learning_store: Store for persisting learnings
        learning_extractor: Extractor for pattern recognition
        files_changed: List of files that were modified
        last_planning_context: Context from planning phase
        memory: Persistent memory for cross-session learnings

    Yields:
        Tuples of (fact, category) for each extracted learning
    """
    # TODO: Implement full learning extraction (RFC-122)
    # For now, this is a stub that yields nothing to unblock the system.
    #
    # Future implementation should:
    # 1. Extract code patterns from files_changed using learning_extractor
    # 2. Extract templates from novel tasks using learning_extractor.extract_template
    # 3. Extract heuristics from task ordering using learning_extractor.extract_heuristic
    # 4. Store learnings in learning_store
    # 5. Optionally sync to memory for cross-session persistence

    # Yield nothing for now - stub implementation
    return
    yield  # Make this a generator
