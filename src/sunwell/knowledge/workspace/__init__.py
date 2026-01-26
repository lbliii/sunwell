"""Workspace detection, management, and multi-project architecture.

RFC-024 additions:
- WorkspaceConfig: Extended configuration with trust suggestions
- resolve_trust_level: Trust level resolution with precedence rules

RFC-043 additions:
- WorkspaceResult: Resolution result with confidence scoring
- resolve_workspace: Unified resolution for CLI and Desktop
- ensure_workspace_exists: Create workspace directory structure

RFC-141 additions:
- Lifecycle management: deletion, rename, move, cleanup operations
- Cascade behavior for workspace child data

Multi-Project Architecture:
- Workspace: Container grouping related projects
- WorkspaceProject: Reference to a project within a workspace
- IndexTier: Tiered indexing levels (L0-L3) for scalability
- ProjectRole: Semantic hints for query routing
"""

from sunwell.knowledge.workspace.detector import (
    DEFAULT_TRUST,
    Workspace as DetectedWorkspace,  # Legacy: single codebase detection
    WorkspaceConfig,
    WorkspaceDetector,
    resolve_trust_level,
)
from sunwell.knowledge.workspace.indexer import CodebaseIndexer
from sunwell.knowledge.workspace.lifecycle import (
    CleanupResult,
    DeleteResult,
    DeletionMode,
    MoveResult,
    PurgeResult,
    RenameResult,
    WorkspaceLifecycle,
    has_nested_workspaces,
)
from sunwell.knowledge.workspace.manager import (
    WorkspaceInfo,
    WorkspaceManager,
    WorkspaceStatus,
    sanitize_workspace_id,
)
from sunwell.knowledge.workspace.resolver import (
    ResolutionSource,
    WorkspaceResult,
    default_config_root,
    default_workspace_root,
    ensure_workspace_exists,
    format_resolution_message,
    resolve_workspace,
)
from sunwell.knowledge.workspace.types import (
    IndexTier,
    ProjectRole,
    Workspace,  # New: multi-project workspace container
    WorkspaceDependencies,
    WorkspaceProject,
)
from sunwell.knowledge.workspace.registry import (
    WorkspaceRegistry,
    WorkspaceRegistryError,
    create_workspace,
    get_default_workspace,
)

__all__ = [
    # Detection (RFC-024)
    "WorkspaceDetector",
    "DetectedWorkspace",  # Legacy name for single codebase detection
    "WorkspaceConfig",
    "resolve_trust_level",
    "DEFAULT_TRUST",
    # Indexing
    "CodebaseIndexer",
    # Resolution (RFC-043)
    "ResolutionSource",
    "WorkspaceResult",
    "resolve_workspace",
    "ensure_workspace_exists",
    "default_workspace_root",
    "default_config_root",
    "format_resolution_message",
    # Management (RFC-140)
    "WorkspaceManager",
    "WorkspaceInfo",
    "WorkspaceStatus",
    "sanitize_workspace_id",
    # Lifecycle (RFC-141)
    "WorkspaceLifecycle",
    "DeletionMode",
    "DeleteResult",
    "PurgeResult",
    "RenameResult",
    "MoveResult",
    "CleanupResult",
    "has_nested_workspaces",
    # Multi-Project Architecture
    "Workspace",
    "WorkspaceProject",
    "WorkspaceDependencies",
    "IndexTier",
    "ProjectRole",
    # Workspace Registry
    "WorkspaceRegistry",
    "WorkspaceRegistryError",
    "create_workspace",
    "get_default_workspace",
]
