"""Memory page - Browse memories and learnings."""

from chirp import Page
from sunwell.interface.chirp.services import MemoryService


def get(memory_svc: MemoryService) -> Page:
    """Render memory browser page."""
    memories = memory_svc.list_memories()

    return Page(
        "memory/page.html",
        "content",
        current_page="memory",
        memories=memories,
        title="Memory",
    )
