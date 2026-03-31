"""Observatory page - Agent execution visualization."""

from sunwell.interface.chirp.services import SessionService


def get(session_svc: SessionService) -> dict:
    """Render observatory page."""
    sessions = session_svc.list_sessions(limit=50)

    runs = [
        {
            "id": session["id"],
            "goal": session["goal"],
            "status": session["status"],
            "started": session["started_at"] or 0.0,
            "events": session["tasks_completed"],
        }
        for session in sessions
    ]

    return {
        "runs": runs,
        "page_title": "Observatory - Sunwell Studio",
        "breadcrumb_label": "Observatory",
    }
