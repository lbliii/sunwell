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
) -> AsyncIterator[tuple[str, str]]:
    """Extract learnings from completed execution (RFC-122, RFC-135).

    Analyzes the completed execution to extract:
    - Code patterns from generated files
    - Fix strategies from successful corrections
    - Templates from novel tasks
    - Heuristics from task ordering

    RFC-135: All learnings are persisted through PersistentMemory to
    .sunwell/intelligence/, NOT as project artifacts.

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

    Yields:
        Tuples of (fact, category) for each extracted learning
    """
    extracted_count = 0

    # Get journal for durable writes (if memory is configured)
    journal: LearningJournal | None = None
    if memory:
        journal = _get_journal(memory.workspace)

    # 1. Extract code patterns from changed files
    for file_path in files_changed[:10]:  # Limit to avoid long extraction
        path = Path(file_path)
        if not path.exists():
            continue

        # Only extract from supported file types
        if path.suffix not in (".py", ".js", ".ts", ".jsx", ".tsx"):
            continue

        try:
            content = path.read_text()
            learnings = learning_extractor.extract_from_code(content, str(path))

            for learning in learnings:
                # Add to session store (in-memory)
                learning_store.add_learning(learning)

                # Add to persistent memory (RFC-135)
                if memory:
                    _add_to_persistent_memory(memory, learning)

                # DURABILITY: Append to journal BEFORE yielding
                # This ensures the learning survives crashes
                if journal:
                    try:
                        journal.append(learning)
                    except OSError as e:
                        logger.warning("Failed to append learning to journal: %s", e)

                # Phase 2.2: Publish to LearningBus for in-process sharing
                # Other agents/subagents subscribed to the bus will receive this
                try:
                    bus = get_learning_bus()
                    bus.publish(learning)
                except Exception as e:
                    logger.debug("Failed to publish learning to bus: %s", e)

                yield (learning.fact, learning.category)
                extracted_count += 1

        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Failed to extract from %s: %s", file_path, e)
            continue

    # 2. Extract heuristics from task ordering (if enough tasks)
    if task_graph and success:
        tasks = task_graph.tasks  # TaskGraph.tasks is already a list[Task]
        heuristic = learning_extractor.extract_heuristic(goal, tasks)
        if heuristic:
            # Convert SimLearning to Learning for consistency
            from sunwell.agent.learning.learning import Learning

            learning = Learning(
                fact=heuristic.fact,
                category="heuristic",
                confidence=heuristic.confidence,
            )
            learning_store.add_learning(learning)

            if memory:
                _add_to_persistent_memory(memory, learning)

            # DURABILITY: Append to journal BEFORE yielding
            if journal:
                try:
                    journal.append(learning)
                except OSError as e:
                    logger.warning("Failed to append heuristic to journal: %s", e)

            # Phase 2.2: Publish to LearningBus for in-process sharing
            try:
                bus = get_learning_bus()
                bus.publish(learning)
            except Exception as e:
                logger.debug("Failed to publish heuristic to bus: %s", e)

            yield (learning.fact, "heuristic")
            extracted_count += 1

    # 3. Sync session learnings to persistent storage (RFC-135)
    # This is now a secondary persistence path; journal is primary
    if memory:
        try:
            synced = learning_store.sync_to_simulacrum(memory.simulacrum)
            if synced > 0:
                logger.debug("Synced %d learnings to persistent memory", synced)
        except Exception as e:
            logger.warning("Failed to sync learnings to memory: %s", e)

    # 4. Also save to disk directly as backup (legacy path)
    if memory:
        try:
            saved = learning_store.save_to_disk(memory.workspace)
            if saved > 0:
                logger.debug("Saved %d learnings to disk", saved)
        except Exception as e:
            logger.warning("Failed to save learnings to disk: %s", e)

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
