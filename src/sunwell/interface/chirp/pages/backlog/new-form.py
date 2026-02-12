"""New goal form (GET endpoint for modal)."""

from chirp import Fragment


def get() -> Fragment:
    """Render new goal form in a modal."""
    return Fragment(
        "backlog/new-form.html",
        "modal_content",
    )
