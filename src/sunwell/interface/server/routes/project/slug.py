"""RFC-133 Phase 2: URL Slug Resolution endpoints.

Provides human-readable URL slugs for deep linking to projects.
Supports:
- Slug resolution (slug -> project)
- Slug lookup (path/id -> slug)
- Slug listing
"""

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes.project.models import (
    ProjectInfo,
    SlugInfo,
    SlugListResponse,
    SlugRequest,
    SlugResolveRequest,
    SlugResolveResponse,
    SlugResponse,
)

router = APIRouter(prefix="/project", tags=["project"])


@router.post("/resolve")
async def resolve_slug(request: SlugResolveRequest) -> SlugResolveResponse:
    """Resolve a URL slug to a project (RFC-133 Phase 2).

    Used by frontend to map URL slugs to actual projects.

    Returns:
    - project: ProjectInfo if unique match found
    - ambiguous: list of candidates if multiple matches
    - error: 'not_found' if no match
    """
    from sunwell.knowledge.project import ProjectRegistry, validate_workspace

    registry = ProjectRegistry()
    project, ambiguous = registry.resolve_slug(request.slug)

    if project:
        # Validate project is still accessible
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

        return SlugResolveResponse(
            project=ProjectInfo(
                id=project.id,
                name=project.name,
                root=str(project.root),
                valid=valid,
                is_default=(project.id == registry.default_project_id),
                last_used=last_used,
            )
        )

    if ambiguous:
        # Build list of candidates (shouldn't happen with proper registry)
        candidates = []
        for p in ambiguous:
            entry = registry.projects.get(p.id, {})
            candidates.append(
                ProjectInfo(
                    id=p.id,
                    name=p.name,
                    root=str(p.root),
                    valid=p.root.exists(),
                    is_default=(p.id == registry.default_project_id),
                    last_used=entry.get("last_used"),
                )
            )
        return SlugResolveResponse(ambiguous=candidates)

    # Not found
    return SlugResolveResponse(error="not_found")


@router.post("/slug")
async def get_project_slug(request: SlugRequest) -> SlugResponse:
    """Get the URL slug for a project by its path (RFC-133 Phase 2).

    If project is registered but has no slug, generates one.
    If project is not registered, returns error.
    """
    from sunwell.knowledge.project import ProjectRegistry

    path = normalize_path(request.path)
    registry = ProjectRegistry()

    # Find project by path
    project = registry.find_by_root(path)
    if not project:
        return SlugResponse(error="not_registered")

    # Get or generate slug
    slug = registry.ensure_slug(project.id, project.name)

    return SlugResponse(slug=slug, project_id=project.id)


@router.get("/slugs")
async def list_slugs() -> SlugListResponse:
    """List all registered slug mappings (RFC-133 Phase 2).

    Useful for debugging and admin purposes.
    """
    from sunwell.knowledge.project import ProjectRegistry

    registry = ProjectRegistry()
    mappings = registry.list_slugs()

    return SlugListResponse(
        slugs=[
            SlugInfo(slug=slug, project_id=pid, path=path)
            for slug, pid, path in mappings
        ]
    )


@router.get("/slug/{project_id}")
async def get_slug_by_id(project_id: str) -> SlugResponse:
    """Get the URL slug for a project by its ID (RFC-133 Phase 2).

    Args:
        project_id: The project's unique identifier

    Returns:
        SlugResponse with slug, or error if project not found
    """
    from sunwell.knowledge.project import ProjectRegistry

    registry = ProjectRegistry()

    # Find project by ID
    project = registry.get(project_id)
    if not project:
        return SlugResponse(error="not_found")

    # Get or generate slug
    slug = registry.ensure_slug(project.id, project.name)

    return SlugResponse(slug=slug, project_id=project.id)
