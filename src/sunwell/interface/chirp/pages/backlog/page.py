"""Backlog page - Goal and task management."""

from chirp import Page
from sunwell.interface.chirp.services import BacklogService


def get(backlog_svc: BacklogService) -> Page:
    """Render backlog page showing goals and tasks."""
    goals = backlog_svc.list_goals()

    return Page(
        "backlog/page.html",
        "content",
        current_page="backlog",
        goals=goals,
        title="Backlog",
    )
