"""Create new goal endpoint."""

from chirp import FormAction, Request, ValidationError, form_or_errors

from sunwell.interface.chirp.schemas import NewGoalForm
from sunwell.interface.chirp.services import BacklogService


async def post(request: Request, backlog_svc: BacklogService) -> FormAction | ValidationError:
    """Create a new goal.

    Returns FormAction that redirects to the backlog page or
    ValidationError if validation fails.
    """
    # Use form_or_errors for automatic binding and error handling
    result = await form_or_errors(
        request, NewGoalForm, "backlog/new-form.html", "modal_content"
    )

    if isinstance(result, ValidationError):
        return result

    form = result  # Now it's a NewGoalForm instance

    # Validate description
    description = form.description.strip()
    if not description:
        return ValidationError(
            "backlog/new-form.html",
            "modal_content",
            errors={"description": ["Goal description cannot be empty"]},
            form={"description": form.description, "priority": form.priority},
        )
    if len(description) > 500:
        return ValidationError(
            "backlog/new-form.html",
            "modal_content",
            errors={"description": ["Goal description too long (max 500 characters)"]},
            form={"description": form.description, "priority": form.priority},
        )

    # Validate priority
    valid_priorities = ["high", "medium", "low"]
    if form.priority not in valid_priorities:
        return ValidationError(
            "backlog/new-form.html",
            "modal_content",
            errors={"priority": [f"Invalid priority: {form.priority}"]},
            form={"description": description, "priority": form.priority},
        )

    # Create the goal
    goal = backlog_svc.create_goal(description, form.priority)

    # Redirect to backlog page
    return FormAction("/backlog")
