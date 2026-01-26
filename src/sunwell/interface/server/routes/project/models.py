"""Shared request/response models for project routes."""

import re

from sunwell.interface.server.routes.models import CamelModel

# Pre-compiled regex for slug generation (avoid recompiling per call)
_RE_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


class ProjectPathRequest(CamelModel):
    """Request with a project path."""

    path: str


# RFC-132: Project Gate validation models
class ValidationResult(CamelModel):
    """Result of workspace validation."""

    valid: bool
    error_code: str | None = None
    error_message: str | None = None
    suggestion: str | None = None


class ProjectInfo(CamelModel):
    """Project info for listing."""

    id: str
    name: str
    root: str
    valid: bool
    is_default: bool
    last_used: str | None


class CreateProjectRequest(CamelModel):
    """Request to create a new project."""

    name: str
    path: str | None = None


class CreateProjectResponse(CamelModel):
    """Response from project creation."""

    project: dict[str, str]
    path: str
    is_new: bool
    is_default: bool
    error: str | None = None
    message: str | None = None


class SetDefaultRequest(CamelModel):
    """Request to set default project."""

    project_id: str


class MonorepoRequest(CamelModel):
    """Request to check monorepo."""

    path: str


class AnalyzeRequest(CamelModel):
    """Request to analyze project."""

    path: str
    fresh: bool = False


class AnalyzeRunRequest(CamelModel):
    """Request to analyze project for running."""

    path: str
    force_refresh: bool = False


class ProjectRunRequest(CamelModel):
    """Request to run a project."""

    path: str
    command: str
    install_first: bool = False
    save_command: bool = False


class StopRunRequest(CamelModel):
    """Request to stop a project run."""

    session_id: str | None = None


class IterateProjectRequest(CamelModel):
    """Request to iterate a project."""

    path: str
    new_goal: str | None = None


class SwitchProjectRequest(CamelModel):
    """Request to switch project context."""

    project_id: str


# ═══════════════════════════════════════════════════════════════════════════════
# RFC-133 Phase 2: URL Slug Resolution Models
# ═══════════════════════════════════════════════════════════════════════════════


class SlugResolveRequest(CamelModel):
    """Request to resolve a URL slug to a project."""

    slug: str


class SlugResolveResponse(CamelModel):
    """Response from slug resolution."""

    project: ProjectInfo | None = None
    """Resolved project if unique match found."""

    ambiguous: list[ProjectInfo] | None = None
    """Multiple candidates if ambiguous (shouldn't happen with proper registry)."""

    error: str | None = None
    """Error code if resolution failed (e.g., 'not_found')."""


class SlugRequest(CamelModel):
    """Request to get slug for a project path."""

    path: str


class SlugResponse(CamelModel):
    """Response with a project's URL slug."""

    slug: str | None = None
    project_id: str | None = None
    error: str | None = None


class SlugInfo(CamelModel):
    """Information about a slug mapping."""

    slug: str
    project_id: str
    path: str


class SlugListResponse(CamelModel):
    """List of all slug mappings."""

    slugs: list[SlugInfo]


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a project name."""
    slug = name.lower()
    slug = _RE_SLUG_CHARS.sub("-", slug).strip("-") or "project"
    return slug
