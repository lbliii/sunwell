"""Chat send - POST handler. Returns Fragment scaffolding (Pattern 3) or full response."""

from chirp import Fragment, Request

from sunwell.interface.chirp.services.chat import ChatService

_CHAT_SESSION_COOKIE = "sunwell_chat_session"


async def post(request: Request, chat_svc: ChatService) -> Fragment:
    """Receive message. If stream=1, start agent in background and return scaffolding.
    If stream=0, run synchronously and return chat_response (user + assistant).
    """
    form = await request.form()
    message = (form.get("message") or "").strip()
    session_id = form.get("session_id") or request.cookies.get(
        _CHAT_SESSION_COOKIE
    ) or ChatService.new_session_id()
    stream = form.get("stream") == "1"

    if not message:
        return Fragment(
            "chat/_message.html",
            "error_message",
            message="Empty message",
            error="",
        )

    if stream:
        err_frag = chat_svc.start_send(session_id, message, stream=True)
        if err_frag is not None:
            return err_frag
        return Fragment(
            "chat/_message.html",
            "chat_start",
            user_content=message,
            session_id=session_id,
        )

    content, err = await chat_svc.send_sync(session_id, message)
    if err:
        return Fragment(
            "chat/_message.html",
            "error_message",
            message=err,
            error="",
        )
    return Fragment(
        "chat/_message.html",
        "chat_response",
        user_content=message,
        assistant_content=content or "",
    )
