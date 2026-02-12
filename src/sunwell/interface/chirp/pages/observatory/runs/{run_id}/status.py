"""Live status updates for a running session."""

from chirp import Fragment, Response
from sunwell.interface.chirp.services import SessionService


def get(run_id: str, session_svc: SessionService) -> Fragment | Response:
    """Return updated status info for HTMX polling.

    This endpoint is called every 2 seconds when a session is running
    to provide live updates without full page refresh.

    Args:
        run_id: Session ID to get status for
        session_svc: Service for accessing sessions

    Returns:
        Fragment with updated status HTML or error response
    """
    session = session_svc.get_session(run_id)

    if not session:
        return Response("Session not found", status=404)

    # If session is no longer running, stop polling by returning full content
    # with no hx-trigger attribute
    is_active = session["status"] in ["running", "pending"]

    return Fragment(
        "observatory/runs/{run_id}/_status.html",
        "run_info",
        run=session,
        is_active=is_active,
    )
