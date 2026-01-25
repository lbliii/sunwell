"""Utility functions for plan persistence."""

from pathlib import Path

from sunwell.planning.naaru.persistence.saved_execution import SavedExecution
from sunwell.planning.naaru.persistence.store import PlanStore

DEFAULT_PLANS_DIR = Path(".sunwell/plans")


def get_latest_execution(goal: str | None = None) -> SavedExecution | None:
    """Get the most recent execution, optionally for a specific goal.

    Args:
        goal: Optional goal text to match

    Returns:
        Most recent SavedExecution, or None
    """
    store = PlanStore()

    if goal:
        return store.find_by_goal(goal)

    recent = store.list_recent(limit=1)
    return recent[0] if recent else None


def save_execution(execution: SavedExecution) -> Path:
    """Save an execution to the default store.

    Args:
        execution: The execution to save

    Returns:
        Path to saved file
    """
    store = PlanStore()
    return store.save(execution)
