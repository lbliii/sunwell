"""Environment variable handlers.

Provides secure environment variable access with allowlist/blocklist enforcement.
"""

import fnmatch
import os


# =============================================================================
# Module-Level Functions (stateless operations)
# =============================================================================


def _is_env_blocked(name: str, blocklist_patterns: tuple[str, ...]) -> bool:
    """Check if an environment variable name matches blocked patterns."""
    name_upper = name.upper()
    return any(fnmatch.fnmatch(name_upper, pattern) for pattern in blocklist_patterns)


async def get_env(args: dict) -> str:
    """Get environment variable with security restrictions.

    Args:
        args: Dict with 'name' key for the environment variable name

    Returns:
        The environment variable value, or an error message if blocked/not found
    """
    from sunwell.tools.builtins import ENV_ALLOWLIST, ENV_BLOCKLIST_PATTERNS

    name = args.get("name")
    if not name:
        raise ValueError("name is required for get_env")

    if _is_env_blocked(name, ENV_BLOCKLIST_PATTERNS):
        return (
            f"[BLOCKED] Environment variable '{name}' may contain secrets "
            "and cannot be accessed."
        )

    if name not in ENV_ALLOWLIST:
        return (
            f"[NOT ALLOWED] Environment variable '{name}' is not in the allowlist. "
            f"Use list_env to see available variables."
        )

    value = os.environ.get(name)
    if value is None:
        return f"[NOT SET] Environment variable '{name}' is not set."

    return value


async def list_env(args: dict) -> str:
    """List available environment variables.

    Args:
        args: Dict with optional 'filter' key for prefix filtering

    Returns:
        Newline-separated list of NAME=value pairs
    """
    from sunwell.tools.builtins import ENV_ALLOWLIST

    filter_prefix = args.get("filter", "").upper()

    available = []
    for name in sorted(ENV_ALLOWLIST):
        if filter_prefix and not name.startswith(filter_prefix):
            continue
        value = os.environ.get(name)
        if value:
            display = value if len(value) <= 50 else f"{value[:47]}..."
            available.append(f"{name}={display}")

    if not available:
        return "No matching environment variables found."

    return "\n".join(available)


# =============================================================================
# Mixin Class (for CoreToolHandlers compatibility)
# =============================================================================


class EnvHandlers:
    """Environment variable handlers mixin.

    Delegates to module-level functions for stateless operations.
    Kept as a class for multiple inheritance compatibility with CoreToolHandlers.
    """

    async def get_env(self, args: dict) -> str:
        """Get environment variable with security restrictions."""
        return await get_env(args)

    async def list_env(self, args: dict) -> str:
        """List available environment variables."""
        return await list_env(args)
