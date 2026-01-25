"""RFC-132: Project Gate endpoints for validation and management."""

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes._models import (
    DefaultProjectItem,
    DefaultProjectResponse,
    SuccessResponse,
)
from sunwell.interface.server.routes.project.models import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectInfo,
    ProjectPathRequest,
    SetDefaultRequest,
    ValidationResult,
    generate_slug,
)

router = APIRouter(prefix="/project", tags=["project"])


@router.post("/validate")
async def validate_project_path(request: ProjectPathRequest) -> ValidationResult:
    """Validate a workspace path before using it (RFC-132).

    Returns structured error with suggestion instead of raising.
    """
    from sunwell.knowledge.project import ProjectValidationError, validate_workspace
    from sunwell.knowledge.workspace import default_workspace_root

    path = normalize_path(request.path)

    if not path.exists():
        return ValidationResult(
            valid=False,
            error_code="not_found",
            error_message=f"Path does not exist: {path}",
        )

    try:
        validate_workspace(path)
        return ValidationResult(valid=True)
    except ProjectValidationError as e:
        # Determine error type for structured response
        error_msg = str(e)

        if "sunwell" in error_msg.lower() and "repository" in error_msg.lower():
            return ValidationResult(
                valid=False,
                error_code="sunwell_repo",
                error_message="Cannot use Sunwell's own repository as project workspace",
                suggestion=str(default_workspace_root()),
            )

        return ValidationResult(
            valid=False,
            error_code="invalid_workspace",
            error_message=error_msg,
        )


@router.get("/list")
async def list_projects() -> dict[str, list[ProjectInfo]]:
    """List all registered projects with validity status (RFC-132).

    Returns projects ordered by last_used descending.
    Includes validity check so UI can warn about broken projects.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import validate_workspace

    registry = ProjectRegistry()
    default_id = registry.default_project_id
    projects = []

    for project in registry.list_projects():
        # Check if still valid
        valid = True
        try:
            if not project.root.exists():
                valid = False
            else:
                validate_workspace(project.root)
        except Exception:
            valid = False

        # Get last_used from registry entry
        entry = registry.projects.get(project.id, {})
        last_used = entry.get("last_used")

        projects.append(
            ProjectInfo(
                id=project.id,
                name=project.name,
                root=str(project.root),
                valid=valid,
                is_default=(project.id == default_id),
                last_used=last_used,
            )
        )

    # Sort by last_used descending (most recent first)
    projects.sort(key=lambda p: p.last_used or "", reverse=True)

    return {"projects": projects}


@router.post("/create")
async def create_project(request: CreateProjectRequest) -> CreateProjectResponse:
    """Create a new project in the specified or default location (RFC-132).

    If path is not provided, creates in ~/Sunwell/projects/{slugified_name}.
    Auto-sets as default if no default project exists.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import RegistryError, init_project
    from sunwell.knowledge.workspace import default_workspace_root

    # Validate name
    name = request.name.strip()
    if not name:
        return CreateProjectResponse(
            project={},
            path="",
            is_new=False,
            is_default=False,
            error="invalid_name",
            message="Project name cannot be empty",
        )
    if len(name) > 64:
        return CreateProjectResponse(
            project={},
            path="",
            is_new=False,
            is_default=False,
            error="invalid_name",
            message="Project name too long (max 64 chars)",
        )
    if "/" in name or "\\" in name:
        return CreateProjectResponse(
            project={},
            path="",
            is_new=False,
            is_default=False,
            error="invalid_name",
            message="Project name cannot contain path separators",
        )

    # Determine path
    if request.path:
        project_path = normalize_path(request.path)
    else:
        # Default location with slugified name
        slug = generate_slug(name)
        project_path = default_workspace_root() / slug

    # Ensure parent exists
    project_path.parent.mkdir(parents=True, exist_ok=True)

    # Create directory
    is_new = not project_path.exists()
    project_path.mkdir(parents=True, exist_ok=True)

    # Generate slug for project ID
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
            return CreateProjectResponse(
                project={},
                path=str(project_path),
                is_new=False,
                is_default=False,
                error="already_exists",
                message=str(e),
            )
        raise

    # Auto-set as default if no default exists
    registry = ProjectRegistry()
    became_default = False
    if registry.get_default() is None:
        registry.set_default(project.id)
        became_default = True

    return CreateProjectResponse(
        project={
            "id": project.id,
            "name": project.name,
            "root": str(project.root),
        },
        path=str(project_path),
        is_new=is_new,
        is_default=became_default,
    )


@router.get("/default")
async def get_default_project() -> DefaultProjectResponse:
    """Get the default project (RFC-132).

    Returns project info if default is set and valid, null otherwise.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import validate_workspace

    registry = ProjectRegistry()
    default = registry.get_default()

    if not default:
        return DefaultProjectResponse(project=None)

    # Verify default is still valid
    try:
        if not default.root.exists():
            return DefaultProjectResponse(
                project=None, warning="Default project no longer exists"
            )
        validate_workspace(default.root)
    except Exception:
        return DefaultProjectResponse(
            project=None, warning="Default project is no longer valid"
        )

    return DefaultProjectResponse(
        project=DefaultProjectItem(
            id=default.id,
            name=default.name,
            root=str(default.root),
        )
    )


@router.put("/default")
async def set_default_project(request: SetDefaultRequest) -> SuccessResponse:
    """Set the default project (RFC-132).

    Validates project exists in registry before setting.
    """
    from sunwell.knowledge import ProjectRegistry
    from sunwell.knowledge.project import RegistryError

    registry = ProjectRegistry()

    # Validate project exists
    project = registry.get(request.project_id)
    if not project:
        available = [p.id for p in registry.list_projects()]
        return SuccessResponse(
            success=False,
            message=f"Project not found: {request.project_id}. Available: {available}",
        )

    try:
        registry.set_default(request.project_id)
    except RegistryError as e:
        return SuccessResponse(success=False, message=str(e))

    return SuccessResponse(success=True, message=request.project_id)
