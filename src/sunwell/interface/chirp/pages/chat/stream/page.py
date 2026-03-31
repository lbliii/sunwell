"""Chat stream - GET handler. SSE endpoint for agent events."""

from chirp import EventStream, Request, Response

from sunwell.interface.chirp.services.chat import ChatService

# Heartbeat interval for long agent runs (keeps connection alive)
_SSE_HEARTBEAT_INTERVAL = 30.0


async def get(request: Request, chat_svc: ChatService) -> EventStream | Response:
    """Stream chat events via SSE. Subscribes to ChatService for session.

    Idempotent: multiple subscribers per session (e.g. reconnect) are supported.
    """
    session_id = request.query.get("session_id")
    if not session_id:
        return Response(
            body="Missing session_id query parameter",
            status=400,
            content_type="text/plain; charset=utf-8",
        )
    if not chat_svc.has_session(session_id):
        return Response(
            body="Invalid or expired session_id",
            status=400,
            content_type="text/plain; charset=utf-8",
        )

    async def generate():
        async for item in chat_svc.subscribe(session_id):
            yield item

    return EventStream(
        generate(),
        heartbeat_interval=_SSE_HEARTBEAT_INTERVAL,
    )
