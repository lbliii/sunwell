"""Middleware to set chat session cookie on /chat GET responses."""

from chirp.context import g
from chirp.http.request import Request
from chirp.middleware.protocol import AnyResponse, Next

_CHAT_SESSION_COOKIE = "sunwell_chat_session"
_COOKIE_MAX_AGE = 86400  # 24h


async def chat_session_cookie_middleware(request: Request, next: Next) -> AnyResponse:
    """Add Set-Cookie for chat session when g.chat_session_id is set."""
    response = await next(request)
    try:
        session_id = g.chat_session_id
    except AttributeError:
        return response
    if session_id and hasattr(response, "with_cookie"):
        response = response.with_cookie(
            _CHAT_SESSION_COOKIE,
            session_id,
            max_age=_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
    return response
