"""Chat model - POST handler. Sets per-session model."""

from chirp import Fragment, Request
from chirp.context import g

from sunwell.interface.chirp.services.chat import ChatService

_CHAT_SESSION_COOKIE = "sunwell_chat_session"


async def post(request: Request, chat_svc: ChatService) -> Fragment:
    """Set session model and return updated selector fragment."""
    form = await request.form()
    model = (form.get("model") or "").strip()
    session_id = request.cookies.get(_CHAT_SESSION_COOKIE) or form.get("session_id")

    if not model:
        return Fragment(
            "chat/_message.html",
            "model_selector",
            models=chat_svc.list_ollama_models() or ["llama3.1:8b"],
            current=chat_svc.get_session_model(session_id or ""),
            session_id=session_id or "",
        )

    if session_id:
        chat_svc.set_session_model(session_id, model)
        g.chat_session_id = session_id

    models = chat_svc.list_ollama_models()
    if not models:
        models = [model]
    elif model not in models:
        models = [model] + [m for m in models if m != model]

    return Fragment(
        "chat/_message.html",
        "model_selector",
        models=models,
        current=model,
        session_id=session_id or "",
    )
