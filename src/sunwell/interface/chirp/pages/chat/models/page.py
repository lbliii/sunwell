"""Chat models - GET handler. Returns model selector fragment."""

from chirp import Fragment, Request

from sunwell.interface.chirp.services.chat import ChatService

_CHAT_SESSION_COOKIE = "sunwell_chat_session"


async def get(
    request: Request, chat_svc: ChatService
) -> Fragment:
    """Return model dropdown fragment for HTMX.

    Lists Ollama models; falls back to current model only if list fails.
    """
    session_id = request.cookies.get(_CHAT_SESSION_COOKIE) or request.query_params.get(
        "session_id"
    )
    models = chat_svc.list_ollama_models()
    current = (
        chat_svc.get_session_model(session_id) if session_id else "llama3.1:8b"
    )
    if not models:
        models = [current]
    elif current not in models:
        models = [current] + [m for m in models if m != current]
    return Fragment(
        "chat/_message.html",
        "model_selector",
        models=models,
        current=current,
        session_id=session_id or "",
    )
