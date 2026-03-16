"""Chat send - POST handler. Returns Fragment scaffolding (Pattern 3)."""

from chirp import Fragment, Request

from sunwell.interface.chirp.services.chat import ChatService


async def post(request: Request, chat_svc: ChatService) -> Fragment:
    """Receive message, start agent in background, return scaffolding.

    Returns Fragment with user bubble + AI div that has sse-connect.
    When swapped in, sse-connect opens GET /chat/stream and receives
    Fragments as the agent works.
    """
    form = await request.form()
    message = (form.get("message") or "").strip()
    session_id = form.get("session_id") or ChatService.new_session_id()

    if not message:
        return Fragment(
            "chat/_message.html",
            "error_message",
            message="Empty message",
            error="",
        )

    chat_svc.start_send(session_id, message)

    return Fragment(
        "chat/_message.html",
        "chat_start",
        user_content=message,
        session_id=session_id,
    )
