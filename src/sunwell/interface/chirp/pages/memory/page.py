"""Memory page - Browse memories and learnings."""

from chirp import Page, Request
from sunwell.interface.chirp.services import MemoryService


def get(memory_svc: MemoryService, request: Request) -> Page:
    """Render memory browser page with optional filtering.

    Query params:
        type: Filter by memory type (learning, pattern, decision)
        search: Search query
    """
    # Get filter params from request query
    memory_type = request.query.get("type")
    search_query = request.query.get("search", "")

    # Get all memories
    memories = memory_svc.list_memories(limit=100)

    # Apply type filter
    if memory_type:
        memories = [m for m in memories if m["type"] == memory_type]

    # Apply search filter (simple case-insensitive substring match)
    if search_query:
        search_lower = search_query.lower()
        memories = [
            m for m in memories if search_lower in m["content"].lower()
        ]

    return Page(
        "memory/page.html",
        "content",
        current_page="memory",
        memories=memories,
        current_type=memory_type or "all",
        search_query=search_query,
        title="Memory",
    )
