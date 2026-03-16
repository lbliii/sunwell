"""Memory page - Browse memories and learnings."""

from chirp import Request

from sunwell.interface.chirp.services import MemoryService


def get(memory_svc: MemoryService, request: Request) -> dict:
    """Render memory browser page with optional filtering."""
    memory_type = request.query.get("type")
    search_query = request.query.get("search", "")

    memories = memory_svc.list_memories(limit=100)

    if memory_type:
        memories = [m for m in memories if m["type"] == memory_type]

    if search_query:
        search_lower = search_query.lower()
        memories = [m for m in memories if search_lower in m["content"].lower()]

    return {
        "memories": memories,
        "current_type": memory_type or "all",
        "search_query": search_query,
        "page_title": "Memory - Sunwell Studio",
        "breadcrumb_label": "Memory",
    }
