"""Create new project handler."""

from dataclasses import dataclass

from chirp import FormAction, Request, ValidationError, form_or_errors


@dataclass(frozen=True, slots=True)
class NewProjectForm:
    """Form for creating a new project."""

    name: str
    path: str = ""


async def post(request: Request) -> FormAction | ValidationError:
    """Create a new project.

    Returns FormAction that redirects to the projects list or
    ValidationError if validation fails.
    """
    from pathlib import Path

    from sunwell.foundation.utils import normalize_path
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import RegistryError, init_project
    from sunwell.knowledge.workspace import default_workspace_root

    # Use form_or_errors for automatic binding and error handling
    result = await form_or_errors(
        request, NewProjectForm, "projects/new-form.html", "modal_content"
    )

    if isinstance(result, ValidationError):
        return result

    form = result  # Now it's a NewProjectForm instance

    # Validate name
    name = form.name.strip()
    if not name:
        return ValidationError(
            "projects/new-form.html",
            "modal_content",
            errors={"name": ["Project name cannot be empty"]},
            form={"name": form.name, "path": form.path},
        )
    if len(name) > 64:
        return ValidationError(
            "projects/new-form.html",
            "modal_content",
            errors={"name": ["Project name too long (max 64 characters)"]},
            form={"name": form.name, "path": form.path},
        )
    if "/" in name or "\\" in name:
        return ValidationError(
            "projects/new-form.html",
            "modal_content",
            errors={"name": ["Project name cannot contain path separators"]},
            form={"name": form.name, "path": form.path},
        )

    # Determine path
    if form.path:
        try:
            project_path = normalize_path(form.path)
        except Exception as e:
            return ValidationError(
                "projects/new-form.html",
                "modal_content",
                errors={"path": [f"Invalid path: {e}"]},
                form={"name": name, "path": form.path},
            )
    else:
        # Default location with slugified name
        from sunwell.interface.server.routes.project.models import generate_slug

        slug = generate_slug(name)
        project_path = default_workspace_root() / slug

    # Ensure parent exists
    project_path.parent.mkdir(parents=True, exist_ok=True)

    # Create directory
    project_path.mkdir(parents=True, exist_ok=True)

    # Generate slug for project ID
    from sunwell.interface.server.routes.project.models import generate_slug

    slug = generate_slug(name)

    # Initialize project
    try:
        project = init_project(
            root=project_path,
            project_id=slug,
            name=name,
            trust="workspace",
            register=True,
        )
    except RegistryError as e:
        if "already initialized" in str(e).lower():
            return ValidationError(
                "projects/new-form.html",
                "modal_content",
                errors={"path": ["Project already exists at this location"]},
                form={"name": name, "path": form.path},
            )
        return ValidationError(
            "projects/new-form.html",
            "modal_content",
            errors={"name": [str(e)]},
            form={"name": name, "path": form.path},
        )

    # Auto-set as default if no default exists
    registry = ProjectRegistry()
    if registry.get_default() is None:
        registry.set_default(project.id)

    # Redirect to projects list
    return FormAction("/projects")
