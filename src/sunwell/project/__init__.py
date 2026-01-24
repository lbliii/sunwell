"""Project-centric workspace isolation (RFC-117).

This module provides explicit project binding for all file operations,
eliminating the class of bugs where agent content pollutes Sunwell's
own source tree.

Example:
    >>> from sunwell.project import resolve_project, init_project
    >>>
    >>> # Initialize a new project
    >>> project = init_project(Path("./my-app"))
    >>>
    >>> # Resolve from context
    >>> project = resolve_project(project_id="my-app")
    >>> project = resolve_project(project_root="/path/to/project")
"""

from sunwell.project.manifest import (
    ManifestError,
    create_manifest,
    load_manifest,
    save_manifest,
)
from sunwell.project.registry import (
    ProjectRegistry,
    RegistryError,
    init_project,
)
from sunwell.project.resolver import (
    ProjectResolutionError,
    ProjectResolver,
    resolve_project,
)
from sunwell.project.types import (
    AgentConfig,
    Project,
    ProjectManifest,
    WorkspaceType,
)
from sunwell.project.validation import (
    ProjectValidationError,
    validate_not_sunwell_repo,
    validate_workspace,
)

__all__ = [
    # Types
    "AgentConfig",
    "Project",
    "ProjectManifest",
    "WorkspaceType",
    # Manifest
    "ManifestError",
    "create_manifest",
    "load_manifest",
    "save_manifest",
    # Registry
    "ProjectRegistry",
    "RegistryError",
    "init_project",
    # Resolver
    "ProjectResolutionError",
    "ProjectResolver",
    "resolve_project",
    # Validation
    "ProjectValidationError",
    "validate_not_sunwell_repo",
    "validate_workspace",
]
