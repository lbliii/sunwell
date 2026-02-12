"""New project form (GET endpoint for modal)."""

from chirp import Fragment


def get() -> Fragment:
    """Render new project form in a modal."""
    return Fragment(
        "projects/new-form.html",
        "modal_content",
        form=None,  # No form data on initial GET
        errors=None,  # No errors on initial GET
    )
