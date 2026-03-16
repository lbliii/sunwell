"""Chat stream - GET handler. SSE endpoint for agent events."""

from chirp import EventStream, Request

from sunwell.interface.chirp.services.chat import ChatService


async def get(request: Request, chat_svc: ChatService) -> EventStream:
    """Stream chat events via SSE. Subscribes to ChatService for session."""
    session_id = request.query.get("session_id") or ChatService.new_session_id()

    async def generate():
        async for fragment in chat_svc.subscribe(session_id):
            yield fragment

    return EventStream(generate())
