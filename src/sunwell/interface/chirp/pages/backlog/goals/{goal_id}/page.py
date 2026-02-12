"""Goal detail page."""

from chirp import NotFound, Page
from sunwell.interface.chirp.services import BacklogService


def get(goal_id: str, backlog_svc: BacklogService) -> Page:
    """Render goal detail page.

    Shows:
    - Goal metadata
    - Task breakdown
    - Progress tracking
    - Agent execution options
    """
    # Get all goals and find the matching one
    goals = backlog_svc.list_goals()
    goal = None
    for g in goals:
        if g["id"] == goal_id:
            goal = g
            break

    if not goal:
        raise NotFound(f"Goal not found: {goal_id}")

    return Page(
        "backlog/goals/{goal_id}/page.html",
        "content",
        current_page="backlog",
        goal=goal,
        title=f"Goal: {goal['description'][:50]}...",
    )
