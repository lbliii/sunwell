"""Learning extraction from execution (RFC-042, RFC-122, RFC-135).

Extracts learnings from completed agent executions:
- Code patterns from generated files
- Fix strategies from successful corrections
- Templates from novel task completions
- Heuristics from task ordering

RFC-135: Learnings are persisted to .sunwell/intelligence/ via PersistentMemory,
not created as project artifacts.

Durability: Learnings are appended to a journal BEFORE yielding events,
ensuring they survive crashes. The journal is the source of truth.

Phase 2.2 (Unified Memory Coordination): After journaling, learnings are
published to the LearningBus for real-time sharing with in-process agents.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.core.journal import LearningJournal
from sunwell.memory.core.learning_bus import get_learning_bus

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.learning.extractor import LearningExtractor
    from sunwell.agent.learning.learning import Learning
    from sunwell.agent.learning.store import LearningStore
    from sunwell.memory.facade.persistent import PersistentMemory
    from sunwell.memory.simulacrum.core.planning_context import PlanningContext

logger = logging.getLogger(__name__)

# Module-level journal cache to avoid repeated instantiation
_journal_cache: dict[Path, LearningJournal] = {}


def _get_journal(workspace: Path) -> LearningJournal:
    """Get or create a cached journal for a workspace."""
    if workspace not in _journal_cache:
        memory_dir = workspace / ".sunwell" / "memory"
        _journal_cache[workspace] = LearningJournal(memory_dir)
    return _journal_cache[workspace]


async def learn_from_execution(
    *,
    goal: str,
    success: bool,
    task_graph: TaskGraph,
    learning_store: LearningStore,
    learning_extractor: LearningExtractor,
    files_changed: list[str],
    last_planning_context: PlanningContext | None,
    memory: PersistentMemory | None,
    force: bool = False,
) -> AsyncIterator[tuple[str, str]]:
    """Extract learnings from completed execution (RFC-122, RFC-135).

    Analyzes the completed execution to extract:
    - Code patterns from generated files
    - Fix strategies from successful corrections
    - Templates from novel tasks
    - Heuristics from task ordering
    - Session-level insights (when force=True)

    RFC-135: All learnings are persisted through PersistentMemory to
    .sunwell/memory/learnings.jsonl (the journal).

    Durability: Each learning is written to the journal BEFORE yielding,
    ensuring it survives crashes. The journal append is atomic and fsynced.

    Args:
        goal: The goal that was executed
        success: Whether execution succeeded
        task_graph: The task graph that was executed
        learning_store: Store for session learnings
        learning_extractor: Extractor for pattern recognition
        files_changed: List of files that were modified
        last_planning_context: Context from planning phase
        memory: Persistent memory for cross-session learnings
        force: If True, extract learnings even without code changes

    Yields:
        Tuples of (fact, category) for each extracted learning
    """
    extracted_count = 0

    # Get journal for durable writes (if memory is configured)
    journal: LearningJournal | None = None
    if memory:
        journal = _get_journal(memory.workspace)

    # Helper to persist and publish a learning
    def _persist_learning(learning: Learning) -> None:
        # Add to session store (in-memory)
        learning_store.add_learning(learning)

        # Add to persistent memory
        if memory:
            _add_to_persistent_memory(memory, learning)

        # DURABILITY: Append to journal
        if journal:
            try:
                journal.append(learning)
            except OSError as e:
                logger.warning("Failed to append learning to journal: %s", e)

        # Publish to LearningBus for in-process sharing
        try:
            bus = get_learning_bus()
            bus.publish(learning)
        except Exception as e:
            logger.debug("Failed to publish learning to bus: %s", e)

    # 1. Extract code patterns from changed files
    for file_path in files_changed[:10]:  # Limit to avoid long extraction
        path = Path(file_path)
        if not path.exists():
            continue

        # Expanded file types (beyond just code)
        extractable_suffixes = (
            ".py", ".js", ".ts", ".jsx", ".tsx",  # Code
            ".yaml", ".yml", ".json", ".toml",     # Config
        )
        if path.suffix not in extractable_suffixes:
            continue

        try:
            content = path.read_text()
            learnings = learning_extractor.extract_from_code(content, str(path))

            for learning in learnings:
                _persist_learning(learning)
                yield (learning.fact, learning.category)
                extracted_count += 1

        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Failed to extract from %s: %s", file_path, e)
            continue

    # 2. Extract heuristics from task ordering
    # On success: learn what worked
    # On failure with force: learn what to avoid
    if task_graph and task_graph.tasks:
        from sunwell.agent.learning.learning import Learning

        if success:
            # Learn successful patterns
            heuristic = learning_extractor.extract_heuristic(goal, task_graph.tasks)
            if heuristic:
                learning = Learning(
                    fact=heuristic.fact,
                    category="heuristic",
                    confidence=heuristic.confidence,
                )
                _persist_learning(learning)
                yield (learning.fact, "heuristic")
                extracted_count += 1
        elif force:
            # Learn from failure: record what approach didn't work
            failed_tasks = [
                t for t in task_graph.tasks
                if t.id not in task_graph.completed_ids
            ]
            if failed_tasks:
                failed_task = failed_tasks[0]
                learning = Learning(
                    fact=f"Approach failed for '{goal[:50]}': {failed_task.description[:100]}",
                    category="heuristic",
                    confidence=0.6,  # Lower confidence for failure learnings
                )
                _persist_learning(learning)
                yield (learning.fact, "heuristic")
                extracted_count += 1

    # 3. Extract session-level insights when force=True
    if force and extracted_count == 0:
        # No code learnings extracted - create a session summary learning
        from sunwell.agent.learning.learning import Learning

        tasks_completed = len(task_graph.completed_ids) if task_graph else 0
        tasks_total = len(task_graph.tasks) if task_graph else 0

        if tasks_total > 0:
            status = "succeeded" if success else "failed"
            learning = Learning(
                fact=f"Goal '{goal[:50]}' {status}: {tasks_completed}/{tasks_total} tasks completed",
                category="session",
                confidence=1.0,
            )
            _persist_learning(learning)
            yield (learning.fact, "session")
            extracted_count += 1

    # 4. Record dead ends from learning store as failures
    if learning_store.dead_ends and memory and memory.failures:
        for dead_end in learning_store.dead_ends:
            try:
                from sunwell.knowledge import FailedApproach

                failure = FailedApproach(
                    id="",  # Will be generated
                    description=dead_end.approach,
                    error_type="dead_end",
                    error_message=dead_end.reason,
                    context=dead_end.context or goal,
                    session_id="",
                )
                await memory.add_failure(failure)
            except Exception as e:
                logger.debug("Failed to record dead end as failure: %s", e)

    # 5. Sync session learnings to SimulacrumStore
    if memory:
        try:
            synced = learning_store.sync_to_simulacrum(memory.simulacrum)
            if synced > 0:
                logger.debug("Synced %d learnings to persistent memory", synced)
        except Exception as e:
            logger.warning("Failed to sync learnings to memory: %s", e)

    logger.debug("Extracted %d learnings from execution", extracted_count)


def _add_to_persistent_memory(
    memory: PersistentMemory,
    learning: Learning,
) -> None:
    """Add a learning to PersistentMemory.

    Helper to handle the conversion between Learning types.
    """
    try:
        # Try to use PersistentMemory.add_learning
        memory.add_learning(learning)
    except Exception as e:
        # If that fails, learnings will still be synced via sync_to_simulacrum
        logger.debug("Failed to add learning to persistent memory: %s", e)
