"""Filesystem isolation for parallel task execution.

This module provides isolation mechanisms for parallel task execution:
- Git worktree isolation (primary): Each parallel task gets its own worktree
- In-memory staging (fallback): For non-git workspaces

The isolation ensures parallel tasks can write files without conflicts,
with changes merged back to the main workspace after validation.

Workspace Readiness:
- Check workspace git status before parallel execution
- Auto-init git if needed for full worktree isolation
- Graceful fallback to staging if git unavailable
"""

from sunwell.agent.isolation.worktree import (
    WorktreeInfo,
    WorktreeManager,
)
from sunwell.agent.isolation.merge import (
    MergeResult,
    MergeStrategy,
)
from sunwell.agent.isolation.validators import (
    ContentSanityValidator,
    ValidationResult,
    get_content_validator,
    validate_content,
)
from sunwell.agent.isolation.fallback import (
    FallbackIsolation,
    StagedFile,
    StagingBuffer,
)
from sunwell.agent.isolation.workspace import (
    WorkspaceIsolationMode,
    WorkspaceReadiness,
    check_workspace_readiness,
    ensure_git_repo,
    get_isolation_recommendation,
)

__all__ = [
    # Worktree management
    "WorktreeInfo",
    "WorktreeManager",
    # Merge
    "MergeResult",
    "MergeStrategy",
    # Validation
    "ContentSanityValidator",
    "ValidationResult",
    "get_content_validator",
    "validate_content",
    # Fallback
    "FallbackIsolation",
    "StagedFile",
    "StagingBuffer",
    # Workspace readiness
    "WorkspaceIsolationMode",
    "WorkspaceReadiness",
    "check_workspace_readiness",
    "ensure_git_repo",
    "get_isolation_recommendation",
]
