"""Run detail page with event log."""

from chirp import NotFound, Page
from sunwell.interface.chirp.services import SessionService


def get(run_id: str, session_svc: SessionService) -> Page:
    """Render run detail page with events.

    Shows:
    - Run metadata
    - Event timeline
    - File changes
    - Visualizations (Phase 2)
    """
    session = session_svc.get_session(run_id)

    if not session:
        raise NotFound(f"Run not found: {run_id}")

    return Page(
        "observatory/runs/{run_id}/page.html",
        "content",
        current_page="observatory",
        run=session,
        page_title=f"Run: {session['goal'][:50]} - Sunwell Studio",
        breadcrumb_label=session["goal"][:50],
        breadcrumb_prefix=[
            {"label": "Observatory", "href": "/observatory"},
        ],
    )
