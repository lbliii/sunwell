"""Tool handlers organized by domain.

This module provides specialized handlers for different tool categories:
- FileHandlers: File operations (read, write, edit, list, search)
- GitHandlers: Git operations (status, diff, log, commit, etc.)
- ShellHandlers: Shell operations (run_command, mkdir)
- EnvHandlers: Environment variable operations

Example:
    >>> from sunwell.tools.handlers import FileHandlers, GitHandlers
    >>>
    >>> file_ops = FileHandlers(workspace=Path.cwd())
    >>> result = await file_ops.read_file({"path": "README.md"})
    >>>
    >>> git_ops = GitHandlers(workspace=Path.cwd())
    >>> status = await git_ops.git_status({})
"""


from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.tools.handlers.base import (
    DEFAULT_BLOCKED_PATTERNS,
    BaseHandler,
    PathSecurityError,
)
from sunwell.tools.handlers.env import EnvHandlers
from sunwell.tools.handlers.file import FileHandlers
from sunwell.tools.handlers.git import GitHandlers
from sunwell.tools.handlers.shell import ShellHandlers

if TYPE_CHECKING:
    from sunwell.skills.sandbox import ScriptSandbox


class CoreToolHandlers(FileHandlers, GitHandlers, ShellHandlers, EnvHandlers):
    """Combined handler with all tool operations.

    This class combines all handlers into a single class for convenience.
    For new code, prefer using the specialized handler classes directly.

    Example:
        >>> handlers = CoreToolHandlers(workspace=Path.cwd())
        >>>
        >>> # All operations available
        >>> await handlers.read_file({"path": "file.txt"})
        >>> await handlers.git_status({})
        >>> await handlers.run_command({"command": "ls"})
        >>> await handlers.get_env({"name": "PATH"})
    """

    def __init__(
        self,
        workspace: Path,
        sandbox: ScriptSandbox | None = None,
        blocked_patterns: frozenset[str] = DEFAULT_BLOCKED_PATTERNS,
    ) -> None:
        """Initialize all handlers.

        Args:
            workspace: Root directory for all file operations
            sandbox: ScriptSandbox for run_command
            blocked_patterns: Glob patterns to block access to
        """
        # Initialize base handler (shared by File, Git, Shell)
        BaseHandler.__init__(self, workspace, blocked_patterns)
        self.sandbox = sandbox


__all__ = [
    # Base
    "BaseHandler",
    "PathSecurityError",
    "DEFAULT_BLOCKED_PATTERNS",
    # Specialized handlers
    "FileHandlers",
    "GitHandlers",
    "ShellHandlers",
    "EnvHandlers",
    # Combined handler
    "CoreToolHandlers",
]
