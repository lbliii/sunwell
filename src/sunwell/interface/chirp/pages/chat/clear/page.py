"""Chat clear - POST handler. Clears conversation and returns empty state."""

from chirp import Fragment, OOB, Request
from chirp.context import g

from sunwell.interface.chirp.services.chat import ChatService

_CHAT_SESSION_COOKIE = "sunwell_chat_session"


async def post(request: Request, chat_svc: ChatService) -> OOB:
    """Clear conversation history and return empty chat state.

    Creates a new session. Middleware sets cookie from g.chat_session_id.
    """
    form = await request.form()
    session_id = request.cookies.get(_CHAT_SESSION_COOKIE) or form.get("session_id")

    if session_id and chat_svc.has_session(session_id):
        session = chat_svc._get_or_create_session(session_id)
        session.conversation_history.clear()
        chat_svc._broadcast(session, None)

    new_session_id = ChatService.new_session_id()
    g.chat_session_id = new_session_id

    main = Fragment(
        "chat/_message.html",
        "chat_cleared",
        session_id=new_session_id,
        messages=[],
    )
    session_input = Fragment(
        "chat/_message.html",
        "chat_session_input",
        target="chat-form-session-id",
        session_id=new_session_id,
    )
    activity_feed = Fragment(
        "chat/_message.html",
        "chat_activity_feed",
        target="chat-activity-feed",
        session_id=new_session_id,
    )
    return OOB(main, session_input, activity_feed)
