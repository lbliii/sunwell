"""Chat cancel - POST handler. Cancels in-progress run."""

from chirp import Fragment, Request

from sunwell.interface.chirp.services.chat import ChatService

_CHAT_SESSION_COOKIE = "sunwell_chat_session"


async def post(request: Request, chat_svc: ChatService) -> Fragment:
    """Cancel in-progress run for session. Returns empty or status fragment."""
    form = await request.form()
    session_id = request.cookies.get(_CHAT_SESSION_COOKIE) or form.get("session_id")

    if not session_id:
        return Fragment(
            "chat/_message.html",
            "error_message",
            message="No session",
            error="",
        )

    cancelled = chat_svc.cancel_run(session_id)
    if cancelled:
        return Fragment(
            "chat/_message.html",
            "chat_cancelled",
            session_id=session_id,
        )
    return Fragment(
        "chat/_message.html",
        "chat_cancel_ignored",
        session_id=session_id,
    )
