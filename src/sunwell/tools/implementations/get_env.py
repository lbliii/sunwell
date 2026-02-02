"""Get environment variable tool."""

import fnmatch
import os

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

# Allowlist of safe environment variables
ENV_ALLOWLIST: frozenset[str] = frozenset({
    # System info
    "HOME",
    "USER",
    "SHELL",
    "TERM",
    "LANG",
    "LC_ALL",
    "TZ",
    # Path info
    "PATH",
    "PWD",
    "OLDPWD",
    # Development
    "EDITOR",
    "VISUAL",
    "PAGER",
    # Python
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    # Node
    "NODE_ENV",
    "NPM_CONFIG_PREFIX",
    # Go
    "GOPATH",
    "GOROOT",
    # Rust
    "CARGO_HOME",
    "RUSTUP_HOME",
    # Git
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
    # Docker
    "DOCKER_HOST",
    # CI indicators (read-only)
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "CIRCLECI",
    # Build info
    "BUILD_NUMBER",
    "BUILD_ID",
})

# Patterns for blocked environment variables (may contain secrets)
ENV_BLOCKLIST_PATTERNS: tuple[str, ...] = (
    "*_KEY",
    "*_SECRET",
    "*_TOKEN",
    "*_PASSWORD",
    "*_PASS",
    "*_API_KEY",
    "*_APIKEY",
    "*_CREDENTIAL*",
    "*_AUTH*",
    "AWS_*",
    "AZURE_*",
    "GCP_*",
    "GOOGLE_*",
    "OPENAI_*",
    "ANTHROPIC_*",
    "DATABASE_*",
    "DB_*",
    "REDIS_*",
    "MONGO_*",
    "POSTGRES_*",
    "MYSQL_*",
    "PRIVATE_*",
    "ENCRYPTION_*",
)


def _is_env_blocked(name: str, blocklist_patterns: tuple[str, ...]) -> bool:
    """Check if an environment variable name matches blocked patterns."""
    name_upper = name.upper()
    return any(fnmatch.fnmatch(name_upper, pattern) for pattern in blocklist_patterns)


@tool_metadata(
    name="get_env",
    simple_description="Get environment variable value",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use get_env to read safe environment variables. Use list_env to see available variables.",
)
class GetEnvTool(BaseTool):
    """Get environment variable with security restrictions."""

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Environment variable name",
            },
        },
        "required": ["name"],
    }

    async def execute(self, arguments: dict) -> str:
        name = arguments.get("name")
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
