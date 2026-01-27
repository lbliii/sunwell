"""Base handler with security utilities."""

import fnmatch
from pathlib import Path

DEFAULT_BLOCKED_PATTERNS = frozenset({
    ".env",
    ".env.*",
    "**/.git/**",
    "**/.git",
    "**/node_modules/**",
    "**/__pycache__/**",
    "*.pem",
    "*.key",
    "**/secrets/**",
    "**/.ssh/**",
    "**/credentials/**",
    "**/*.secret",
})


class PathSecurityError(PermissionError):
    """Raised when a path access is blocked for security reasons."""


class BaseHandler:
    """Base handler with path security enforcement.

    Security: All path operations use _safe_path() which:
    1. Resolves to absolute path
    2. Ensures path stays within workspace (jail)
    3. Checks against blocked patterns
    """

    def __init__(
        self,
        workspace: Path,
        blocked_patterns: frozenset[str] = DEFAULT_BLOCKED_PATTERNS,
        **kwargs,  # Accept extra kwargs for cooperative multiple inheritance
    ) -> None:
        # Don't call super().__init__(**kwargs) - we're the root class
        self.workspace = workspace.resolve()
        self.blocked_patterns = blocked_patterns

    def _safe_path(self, user_path: str) -> Path:
        """Canonicalize path and enforce security restrictions.

        Args:
            user_path: User-provided path (may be relative or absolute)

        Returns:
            Resolved absolute path within workspace

        Raises:
            PathSecurityError: If path escapes workspace or matches blocked pattern
        """
        if not user_path or user_path == "/":
            raise PathSecurityError(
                f"Invalid path: '{user_path}'. Must be a specific file or directory path."
            )

        requested = (self.workspace / user_path).resolve()

        try:
            requested.relative_to(self.workspace)
        except ValueError as err:
            raise PathSecurityError(
                f"Path escapes workspace: {user_path} → {requested}"
            ) from err

        relative_str = str(requested.relative_to(self.workspace))
        for pattern in self.blocked_patterns:
            if fnmatch.fnmatch(relative_str, pattern):
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
            if fnmatch.fnmatch(requested.name, pattern):
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
            simple_pattern = pattern.removeprefix("**/").removesuffix("/**")
            if simple_pattern and simple_pattern in relative_str:
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")

        return requested
