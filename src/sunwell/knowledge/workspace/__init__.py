"""Workspace detection and codebase indexing.

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
"""

from sunwell.knowledge.workspace.detector import (
    DEFAULT_TRUST,
    Workspace,
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

__all__ = [
    # Detection (RFC-024)
    "WorkspaceDetector",
    "Workspace",
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
]
