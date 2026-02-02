"""Mkdir tool implementation."""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="mkdir",
    simple_description="Create a directory",
    trust_level=ToolTrust.WORKSPACE,
    usage_guidance=(
        "Creates parent directories automatically (like mkdir -p). "
        "Returns success if directory already exists."
    ),
)
class MkdirTool(BaseTool):
    """Create a directory. Creates parent directories if needed (like mkdir -p)."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to create, relative to workspace root",
            },
        },
        "required": ["path"],
    }

    async def execute(self, arguments: dict) -> str:
        """Create directory.

        Args:
            arguments: Must contain 'path'

        Returns:
            Success message

        Raises:
            ValueError: If path exists but is not a directory
        """
        user_path = arguments["path"]
        path = self.resolve_path(user_path)

        if path.exists():
            if path.is_dir():
                return f"Directory already exists: {user_path}"
            else:
                raise ValueError(f"Path exists but is not a directory: {user_path}")

        path.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {user_path}"
