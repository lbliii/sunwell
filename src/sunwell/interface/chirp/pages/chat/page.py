"""Chat page - GET handler."""

from chirp import Request
from chirp.context import g

from sunwell.interface.chirp.services.chat import ChatService

_CHAT_SESSION_COOKIE = "sunwell_chat_session"


async def get(request: Request, chat_svc: ChatService) -> dict:
    """Render chat page with conversation history and session ID.

    Session persists via cookie. Creates new only if cookie missing.
    """
    session_id = request.cookies.get(_CHAT_SESSION_COOKIE) or ChatService.new_session_id()
    g.chat_session_id = session_id  # Middleware adds Set-Cookie to response
    messages = chat_svc.get_conversation_history(session_id)
    models = chat_svc.list_ollama_models()
    current_model = chat_svc.get_session_model(session_id)
    if not models:
        models = [current_model]

    return {
        "page_title": "Chat - Sunwell Studio",
        "breadcrumb_label": "Chat",
        "session_id": session_id,
        "messages": messages,
        "models": models,
        "current_model": current_model,
    }
