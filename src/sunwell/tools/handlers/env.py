"""Environment variable handlers."""

import fnmatch
import os


class EnvHandlers:
    """Environment variable handlers with security restrictions."""

    async def get_env(self, args: dict) -> str:
        """Get environment variable with security restrictions."""
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

    async def list_env(self, args: dict) -> str:
        """List available environment variables."""
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


def _is_env_blocked(name: str, blocklist_patterns: tuple[str, ...]) -> bool:
    """Check if an environment variable name matches blocked patterns."""
    name_upper = name.upper()
    return any(fnmatch.fnmatch(name_upper, pattern) for pattern in blocklist_patterns)
