"""Workspace readiness checks for isolation features.

Provides pre-flight checks to ensure the workspace is ready for
parallel task execution with proper isolation.

This module is called early in goal/chat execution to:
- Detect if workspace is a git repository
- Suggest or auto-init git if needed for worktree isolation
- Configure fallback isolation if git isn't available
"""

import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkspaceIsolationMode(Enum):
    """Available isolation modes for the workspace."""

    WORKTREE = "worktree"
    """Git worktree isolation (preferred) - full filesystem isolation per task."""

    STAGING = "staging"
    """In-memory staging fallback - validates before commit but shared filesystem."""

    NONE = "none"
    """No isolation - parallel tasks share filesystem (legacy behavior)."""


@dataclass(frozen=True, slots=True)
class WorkspaceReadiness:
    """Result of workspace readiness check.

    Attributes:
        is_git_repo: Whether the workspace is a git repository
        isolation_mode: Recommended isolation mode
        can_init_git: Whether git init is possible/recommended
        message: Human-readable status message
        warning: Optional warning message
    """

    is_git_repo: bool
    """Whether the workspace is a git repository."""

    isolation_mode: WorkspaceIsolationMode
    """Recommended isolation mode based on workspace state."""

    can_init_git: bool
    """Whether git init would be beneficial and safe."""

    message: str
    """Human-readable status message."""

    warning: str | None = None
    """Optional warning message."""


def check_workspace_readiness(
    workspace: Path,
    require_git: bool = False,
) -> WorkspaceReadiness:
    """Check if workspace is ready for parallel task isolation.

    This should be called early in goal/chat execution to determine
    the best isolation strategy.

    Args:
        workspace: Path to the workspace root
        require_git: If True, strongly recommend git init for non-git workspaces

    Returns:
        WorkspaceReadiness with isolation mode recommendation
    """
    # Check if workspace is a git repo
    is_git = _is_git_repo(workspace)

    if is_git:
        return WorkspaceReadiness(
            is_git_repo=True,
            isolation_mode=WorkspaceIsolationMode.WORKTREE,
            can_init_git=False,
            message="Workspace is a git repository - worktree isolation available",
        )

    # Not a git repo - check if we can/should init
    can_init = _can_init_git(workspace)

    if require_git and can_init:
        return WorkspaceReadiness(
            is_git_repo=False,
            isolation_mode=WorkspaceIsolationMode.STAGING,
            can_init_git=True,
            message="Workspace is not a git repository",
            warning=(
                "Parallel task isolation works best with git. "
                "Consider running 'git init' for full worktree isolation."
            ),
        )

    if can_init:
        return WorkspaceReadiness(
            is_git_repo=False,
            isolation_mode=WorkspaceIsolationMode.STAGING,
            can_init_git=True,
            message="Workspace is not a git repository - using in-memory staging",
            warning=(
                "Using in-memory staging for isolation. "
                "Run 'git init' for better parallel task isolation."
            ),
        )

    # Can't init git (maybe read-only or nested repo issue)
    return WorkspaceReadiness(
        is_git_repo=False,
        isolation_mode=WorkspaceIsolationMode.STAGING,
        can_init_git=False,
        message="Using in-memory staging for isolation",
    )


def _is_git_repo(workspace: Path) -> bool:
    """Check if workspace is a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=workspace,
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _can_init_git(workspace: Path) -> bool:
    """Check if git init would be possible and safe."""
    # Don't init if:
    # 1. Inside another git repo (nested repos are problematic)
    # 2. Workspace doesn't exist or isn't a directory
    # 3. Workspace isn't writable

    if not workspace.exists() or not workspace.is_dir():
        return False

    # Check if writable
    try:
        test_file = workspace / ".sunwell_test_write"
        test_file.touch()
        test_file.unlink()
    except (PermissionError, OSError):
        return False

    # Check if we're inside another git repo (would be nested)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # We're inside a git repo - check if it's this workspace
            git_root = Path(result.stdout.strip())
            if git_root.resolve() != workspace.resolve():
                # We're inside a different repo - don't init
                return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return True


async def ensure_git_repo(
    workspace: Path,
    auto_init: bool = False,
) -> bool:
    """Ensure workspace is a git repository, optionally initializing.

    Args:
        workspace: Path to the workspace root
        auto_init: If True and workspace isn't a git repo, initialize it

    Returns:
        True if workspace is now a git repo, False otherwise
    """
    readiness = check_workspace_readiness(workspace)

    if readiness.is_git_repo:
        return True

    if not auto_init or not readiness.can_init_git:
        return False

    # Initialize git repository
    try:
        result = subprocess.run(
            ["git", "init"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info("Initialized git repository in %s", workspace)

            # Create initial commit so worktrees have a base
            subprocess.run(
                ["git", "config", "user.email", "sunwell@local"],
                cwd=workspace,
                capture_output=True,
                timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.name", "Sunwell"],
                cwd=workspace,
                capture_output=True,
                timeout=5,
            )

            # Create .gitignore if it doesn't exist
            gitignore = workspace / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    "# Sunwell workspace\n"
                    ".sunwell/\n"
                    "__pycache__/\n"
                    "*.pyc\n"
                    ".env\n"
                    "node_modules/\n"
                )

            # Initial commit
            subprocess.run(
                ["git", "add", "-A"],
                cwd=workspace,
                capture_output=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit (Sunwell workspace)"],
                cwd=workspace,
                capture_output=True,
                timeout=30,
            )

            return True

        logger.warning("Failed to initialize git: %s", result.stderr)
        return False

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Failed to initialize git: %s", e)
        return False


def get_isolation_recommendation(
    workspace: Path,
    parallel_tasks: int = 1,
) -> str:
    """Get a human-readable isolation recommendation.

    Args:
        workspace: Path to the workspace root
        parallel_tasks: Number of parallel tasks planned

    Returns:
        Recommendation message for the user
    """
    readiness = check_workspace_readiness(workspace)

    if parallel_tasks <= 1:
        return "Single task - no isolation needed"

    if readiness.isolation_mode == WorkspaceIsolationMode.WORKTREE:
        return (
            f"✓ Git worktree isolation available for {parallel_tasks} parallel tasks"
        )

    if readiness.can_init_git:
        return (
            f"⚠ {parallel_tasks} parallel tasks planned but workspace isn't a git repo.\n"
            f"  Run 'git init' for full worktree isolation, or continue with staging fallback."
        )

    return (
        f"ℹ Using in-memory staging for {parallel_tasks} parallel tasks"
    )
