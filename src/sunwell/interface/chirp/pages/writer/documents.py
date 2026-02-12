"""Create new document endpoint."""

from chirp import FormAction, Request, ValidationError, form_or_errors

from sunwell.interface.chirp.schemas import NewDocumentForm
from sunwell.interface.chirp.services import WriterService


async def post(request: Request, writer_svc: WriterService) -> FormAction | ValidationError:
    """Create a new document.

    Returns FormAction that redirects to the writer page or
    ValidationError if validation fails.
    """
    # Use form_or_errors for automatic binding and error handling
    result = await form_or_errors(
        request, NewDocumentForm, "writer/new-form.html", "modal_content"
    )

    if isinstance(result, ValidationError):
        return result

    form = result

    # Validate title
    title = form.title.strip()
    if not title:
        return ValidationError(
            "writer/new-form.html",
            "modal_content",
            errors={"title": ["Document title cannot be empty"]},
            form={"title": form.title, "path": form.path},
        )

    # Validate path
    path = form.path.strip()
    if not path:
        return ValidationError(
            "writer/new-form.html",
            "modal_content",
            errors={"path": ["File path cannot be empty"]},
            form={"title": title, "path": form.path},
        )

    # TODO: Create the actual document file
    # For now, just acknowledge

    # Redirect to writer page
    return FormAction("/writer")
