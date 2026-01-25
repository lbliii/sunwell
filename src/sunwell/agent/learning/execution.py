"""Execution learning extraction (RFC-122)."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.agent.learning.extractor import LearningExtractor
    from sunwell.agent.learning.store import LearningStore


async def learn_from_execution(
    goal: str,
    success: bool,
    task_graph: Any,
    learning_store: LearningStore,
    learning_extractor: LearningExtractor,
    files_changed: list[str],
    last_planning_context: Any,
    memory: Any | None = None,
) -> AsyncIterator[tuple[str, str]]:
    """Extract learnings from completed execution (RFC-122).

    Called after all tasks complete to:
    1. Record usage of learnings that were retrieved for planning
    2. Extract template patterns from successful novel tasks
    3. Extract ordering heuristics from successful executions

    Args:
        goal: The completed goal
        success: Whether execution succeeded
        task_graph: The task graph that was executed
        learning_store: Store for learnings
        learning_extractor: Extractor for learnings
        files_changed: Files modified during execution
        last_planning_context: Planning context that was used
        memory: PersistentMemory for storing learnings (optional for recovery)

    Yields:
        Tuples of (fact, category) for each new learning
    """
    # Get tasks from task graph
    if not task_graph:
        return

    tasks = task_graph.tasks

    # Get planning context that was used
    planning_context = last_planning_context

    # Record usage of learnings that were retrieved
    if planning_context and success:
        for learning in planning_context.all_learnings:
            learning_store.record_usage(learning.id, success=True)

    # Only extract new learnings on success
    if not success:
        return

    # Collect artifacts created
    artifacts_created = [
        artifact for task in tasks for artifact in (task.produces or [])
    ]

    # Try to extract template from successful novel task
    # Novel = no high-confidence template was used
    template_was_used = (
        planning_context
        and planning_context.best_template
        and planning_context.best_template.confidence >= 0.8
    )

    # Get simulacrum from memory if available
    simulacrum = memory.simulacrum if memory else None

    if not template_was_used and len(artifacts_created) >= 2:
        try:
            template_learning = await learning_extractor.extract_template(
                goal=goal,
                files_changed=files_changed,
                artifacts_created=artifacts_created,
                tasks=tasks,
            )
            if template_learning and simulacrum:
                simulacrum.get_dag().add_learning(template_learning)
                yield (template_learning.fact, "template")
        except Exception:
            pass  # Don't fail run on learning extraction errors

    # Try to extract ordering heuristics
    if len(tasks) >= 3:
        try:
            heuristic_learning = learning_extractor.extract_heuristic(
                goal=goal,
                tasks=tasks,
            )
            if heuristic_learning and simulacrum:
                simulacrum.get_dag().add_learning(heuristic_learning)
                yield (heuristic_learning.fact, "heuristic")
        except Exception:
            pass  # Don't fail run on learning extraction errors
