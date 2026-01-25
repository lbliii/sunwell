"""Briefing-Driven Prefetch Dispatcher (RFC-071, RFC-130).

Uses the briefing as a dispatch signal to pre-load context before the main
agent starts. A tiny/fast model analyzes the briefing and generates a prefetch
plan, which is then executed in parallel with timeout protection.

Key insight: The briefing is tiny (~300 tokens), so a cheap model can read it
instantly and tell the system what to pre-load. This transforms cold starts
into warm starts.

RFC-130: Now integrates with PersistentMemory to prefetch context from
similar past goals, enabling "memory-informed" warm starts.
"""


import asyncio
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from sunwell.memory.briefing import Briefing, PrefetchedContext, PrefetchPlan

if TYPE_CHECKING:
    from sunwell.agent.learning import Learning
    from sunwell.memory import PersistentMemory

# Default prefetch timeout (seconds)
PREFETCH_TIMEOUT = 2.0


async def analyze_briefing_for_prefetch(
    briefing: Briefing,
    router_model: str = "gpt-4o-mini",
    memory: PersistentMemory | None = None,
) -> PrefetchPlan:
    """Use cheap model to analyze briefing and plan prefetch.

    This runs BEFORE the main agent, using a tiny model to:
    1. Parse the briefing signals
    2. Predict what context will be needed
    3. RFC-130: Query memory for similar past goals
    4. Return a prefetch plan

    The main agent then starts with warm context.

    Args:
        briefing: The current briefing to analyze
        router_model: Model to use for dispatch (should be fast/cheap)
        memory: RFC-130 - PersistentMemory for goal similarity lookup

    Returns:
        PrefetchPlan with what to pre-load
    """
    # Start with briefing-based hints
    files_to_read = list(briefing.hot_files)
    learnings_to_load = list(briefing.related_learnings)
    skills_needed: list[str] = []
    suggested_lens = briefing.suggested_lens
    memory_hints: dict[str, Any] = {}

    # RFC-130: Query memory for similar past goals
    if memory is not None and briefing.next_action:
        similar_goals = await memory.find_similar_goals(
            briefing.next_action,
            limit=3,
        )

        if similar_goals:
            # Extract context from similar past goals
            for goal_memory in similar_goals:
                # Add files that were useful in similar goals
                files_to_read.extend(goal_memory.hot_files[:5])

                # Add learnings from similar goals
                learnings_to_load.extend(goal_memory.learnings[:3])

                # Track what worked in similar goals
                if goal_memory.skills_used:
                    skills_needed.extend(goal_memory.skills_used)

                # Use lens from successful similar goal if none specified
                if not suggested_lens and goal_memory.lens_used:
                    suggested_lens = goal_memory.lens_used

            # Store memory hints for agent
            memory_hints = {
                "similar_goals": [g.goal for g in similar_goals],
                "patterns": [g.success_pattern for g in similar_goals if g.success_pattern],
            }

    # If briefing already has dispatch hints, enhance with memory
    if briefing.predicted_skills or suggested_lens:
        skills = list(briefing.predicted_skills) + skills_needed

        return PrefetchPlan(
            files_to_read=tuple(dict.fromkeys(files_to_read)),  # Dedupe
            learnings_to_load=tuple(dict.fromkeys(learnings_to_load)),  # Dedupe
            skills_needed=tuple(dict.fromkeys(skills)),  # Dedupe
            dag_nodes_to_fetch=(briefing.goal_hash,) if briefing.goal_hash else (),
            suggested_lens=suggested_lens,
            memory_hints=memory_hints,
        )

    # Otherwise, use routing heuristics + memory
    from sunwell.planning.routing.briefing_router import (
        predict_skills_from_briefing,
        suggest_lens_from_briefing,
    )

    heuristic_skills = predict_skills_from_briefing(briefing)
    heuristic_lens = suggest_lens_from_briefing(briefing)

    all_skills = list(heuristic_skills) + skills_needed

    return PrefetchPlan(
        files_to_read=tuple(dict.fromkeys(files_to_read)),
        learnings_to_load=tuple(dict.fromkeys(learnings_to_load)),
        skills_needed=tuple(dict.fromkeys(all_skills)),
        dag_nodes_to_fetch=(briefing.goal_hash,) if briefing.goal_hash else (),
        suggested_lens=suggested_lens or heuristic_lens,
        memory_hints=memory_hints,
    )


async def execute_prefetch(
    plan: PrefetchPlan,
    project_path: Path,
    timeout: float = PREFETCH_TIMEOUT,
) -> PrefetchedContext | None:
    """Execute the prefetch plan in parallel with timeout.

    This can run while the user is still typing or while
    the main agent is being initialized.

    Args:
        plan: The prefetch plan to execute
        project_path: Path to the project
        timeout: Maximum time to wait for prefetch

    Returns:
        PrefetchedContext if successful, None if timeout exceeded
    """

    async def _do_prefetch() -> PrefetchedContext:
        # Run all prefetch operations in parallel
        files_task = asyncio.create_task(_read_files(plan.files_to_read, project_path))
        learnings_task = asyncio.create_task(
            _load_learnings(plan.learnings_to_load, project_path)
        )
        dag_task = asyncio.create_task(_fetch_dag_nodes(plan.dag_nodes_to_fetch, project_path))

        # Wait for all tasks
        files = await files_task
        learnings = await learnings_task
        dag_context = await dag_task

        return PrefetchedContext(
            files=MappingProxyType(files),
            learnings=learnings,
            dag_context=dag_context,
            active_skills=plan.skills_needed,
            lens=plan.suggested_lens,
        )

    try:
        return await asyncio.wait_for(_do_prefetch(), timeout=timeout)
    except TimeoutError:
        return None


async def _read_files(paths: tuple[str, ...], project_path: Path) -> dict[str, str]:
    """Read files into memory."""
    files: dict[str, str] = {}
    for path in paths:
        full_path = project_path / path
        if full_path.exists() and full_path.is_file():
            try:
                files[path] = full_path.read_text()
            except (OSError, UnicodeDecodeError):
                pass  # Skip unreadable files
    return files


async def _load_learnings(
    ids: tuple[str, ...], project_path: Path
) -> tuple[Learning, ...]:
    """Load learnings by ID from memory store."""
    if not ids:
        return ()

    try:
        from sunwell.agent.learning import LearningStore

        store = LearningStore()
        store.load_from_disk(project_path)

        # O(1) lookups instead of O(n) tuple scan
        id_set = set(ids)
        matched = [lrn for lrn in store.learnings if lrn.id in id_set]

        return tuple(matched)
    except ImportError:
        return ()


async def _fetch_dag_nodes(
    ids: tuple[str, ...], project_path: Path
) -> tuple[Any, ...]:
    """Fetch DAG nodes for conversation history.

    Placeholder - implement based on Simulacrum DAG structure.
    """
    # For now, just return empty - can be enhanced when DAG is available
    return ()
