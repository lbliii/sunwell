"""Tool handlers for local execution (RFC-012, RFC-024).

DEPRECATED: This module is maintained for backward compatibility.
New code should import from `sunwell.tools.handlers` (the package) instead.

This module re-exports everything from the modular handlers package.
The actual implementations are in:
- `sunwell.tools.handlers.base` - BaseHandler, PathSecurityError, DEFAULT_BLOCKED_PATTERNS
- `sunwell.tools.handlers.file` - FileHandlers
- `sunwell.tools.handlers.git` - GitHandlers
- `sunwell.tools.handlers.shell` - ShellHandlers
- `sunwell.tools.handlers.env` - EnvHandlers, _is_env_blocked
- `sunwell.tools.handlers` (package) - CoreToolHandlers (combined)

Migration guide:
    # Old (still works)
    from sunwell.tools.handlers import CoreToolHandlers

    # New (same import, but now from package)
    from sunwell.tools.handlers import CoreToolHandlers
"""

# Re-export everything from the modular handlers package for backward compatibility
# Import from the package's __init__.py which has the combined CoreToolHandlers
from sunwell.tools.handlers import (
    CoreToolHandlers,
    DEFAULT_BLOCKED_PATTERNS,
    EnvHandlers,
    FileHandlers,
    GitHandlers,
    PathSecurityError,
    ShellHandlers,
)
# Import _is_env_blocked from the env module directly
from sunwell.tools.handlers.env import _is_env_blocked

__all__ = [
    "CoreToolHandlers",
    "DEFAULT_BLOCKED_PATTERNS",
    "EnvHandlers",
    "FileHandlers",
    "GitHandlers",
    "PathSecurityError",
    "ShellHandlers",
    "_is_env_blocked",
]
