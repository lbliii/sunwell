"""Chat page - GET handler."""

from chirp import Page

from sunwell.interface.chirp.services.chat import ChatService


async def get(chat_svc: ChatService) -> Page:
    """Render chat page with conversation history and session ID."""
    session_id = ChatService.new_session_id()
    messages = chat_svc.get_conversation_history(session_id)

    return Page(
        "chat/page.html",
        "content",
        current_page="chat",
        page_title="Chat - Sunwell Studio",
        breadcrumb_label="Chat",
        session_id=session_id,
        messages=messages,
    )
