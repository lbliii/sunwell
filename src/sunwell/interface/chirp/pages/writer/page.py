"""Writer page - Document editing and validation."""

from chirp import Page
from sunwell.interface.chirp.services import WriterService


def get(writer_svc: WriterService) -> Page:
    """Render writer page with document list."""
    documents = writer_svc.list_documents()

    return Page(
        "writer/page.html",
        "content",
        current_page="writer",
        documents=documents,
        title="Writer",
    )
