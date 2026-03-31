"""Run detail page with event log."""

from chirp import NotFound

from sunwell.interface.chirp.services import SessionService


def get(run_id: str, session_svc: SessionService) -> dict:
    """Render run detail page with events."""
    session = session_svc.get_session(run_id)

    if not session:
        raise NotFound(f"Run not found: {run_id}")

    return {
        "run": session,
        "page_title": f"Run: {session['goal'][:50]} - Sunwell Studio",
        "breadcrumb_label": session["goal"][:50],
        "breadcrumb_prefix": [
            {"label": "Observatory", "href": "/observatory"},
        ],
    }
