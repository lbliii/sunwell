"""List environment variables tool."""

import os

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

# Import allowlist from get_env
from sunwell.tools.implementations.get_env import ENV_ALLOWLIST


@tool_metadata(
    name="list_env",
    simple_description="List available environment variables",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use list_env to see which environment variables are available. Use filter to narrow results.",
)
class ListEnvTool(BaseTool):
    """List available environment variables."""

    parameters = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Filter by prefix (case-insensitive)",
            },
        },
        "required": [],
    }

    async def execute(self, arguments: dict) -> str:
        filter_prefix = arguments.get("filter", "").upper()

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
