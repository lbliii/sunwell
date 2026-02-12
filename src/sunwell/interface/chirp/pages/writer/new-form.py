"""New document form (GET endpoint for modal)."""

from chirp import Fragment


def get() -> Fragment:
    """Render new document form in a modal."""
    return Fragment(
        "writer/new-form.html",
        "modal_content",
    )
