"""Briefing-Driven Prefetch Dispatcher (RFC-071).

Uses the briefing as a dispatch signal to pre-load context before the main
agent starts. A tiny/fast model analyzes the briefing and generates a prefetch
plan, which is then executed in parallel with timeout protection.

Key insight: The briefing is tiny (~300 tokens), so a cheap model can read it
instantly and tell the system what to pre-load. This transforms cold starts
into warm starts.
"""


import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.memory.briefing import Briefing, PrefetchPlan, PrefetchedContext

if TYPE_CHECKING:
    from sunwell.adaptive.learning import Learning

# Default prefetch timeout (seconds)
PREFETCH_TIMEOUT = 2.0


async def analyze_briefing_for_prefetch(
    briefing: Briefing,
    router_model: str = "gpt-4o-mini",
) -> PrefetchPlan:
    """Use cheap model to analyze briefing and plan prefetch.

    This runs BEFORE the main agent, using a tiny model to:
    1. Parse the briefing signals
    2. Predict what context will be needed
    3. Return a prefetch plan

    The main agent then starts with warm context.

    Args:
        briefing: The current briefing to analyze
        router_model: Model to use for dispatch (should be fast/cheap)

    Returns:
        PrefetchPlan with what to pre-load
    """
    # If briefing already has dispatch hints, use them directly
    if briefing.predicted_skills or briefing.suggested_lens:
        return PrefetchPlan(
            files_to_read=briefing.hot_files,
            learnings_to_load=briefing.related_learnings,
            skills_needed=briefing.predicted_skills,
            dag_nodes_to_fetch=(briefing.goal_hash,) if briefing.goal_hash else (),
            suggested_lens=briefing.suggested_lens,
        )

    # Otherwise, use routing heuristics
    from sunwell.routing.briefing_router import (
        predict_skills_from_briefing,
        suggest_lens_from_briefing,
    )

    skills = predict_skills_from_briefing(briefing)
    lens = suggest_lens_from_briefing(briefing)

    return PrefetchPlan(
        files_to_read=briefing.hot_files,
        learnings_to_load=briefing.related_learnings,
        skills_needed=tuple(skills),
        dag_nodes_to_fetch=(briefing.goal_hash,) if briefing.goal_hash else (),
        suggested_lens=lens,
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
            files=files,
            learnings=learnings,
            dag_context=dag_context,
            active_skills=plan.skills_needed,
            lens=plan.suggested_lens,
        )

    try:
        return await asyncio.wait_for(_do_prefetch(), timeout=timeout)
    except asyncio.TimeoutError:
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
        from sunwell.adaptive.learning import LearningStore

        store = LearningStore()
        store.load_from_disk(project_path)

        # Match learnings by ID
        matched: list[Learning] = []
        for lrn in store.learnings:
            if lrn.id in ids:
                matched.append(lrn)

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
