"""Coordinator page - Worker management and monitoring."""

from chirp import Page
from sunwell.interface.chirp.services import CoordinatorService


def get(coordinator_svc: CoordinatorService) -> Page:
    """Render coordinator page showing worker status."""
    workers = coordinator_svc.list_workers()

    return Page(
        "coordinator/page.html",
        "content",
        current_page="coordinator",
        workers=workers,
        title="Coordinator",
    )
