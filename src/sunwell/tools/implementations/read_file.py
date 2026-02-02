"""Read file tool implementation."""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="read_file",
    simple_description="Read file contents",
    trust_level=ToolTrust.READ_ONLY,
    essential=True,  # Core tool, always available
    usage_guidance=(
        "Use read_file to inspect file contents before editing. "
        "For large files (>1MB), consider using search_files to find specific content."
    ),
)
class ReadFileTool(BaseTool):
    """Read contents of a file. Returns the file content wrapped in code fences."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to workspace root",
            },
        },
        "required": ["path"],
    }

    async def execute(self, arguments: dict) -> str:
        """Read file contents.

        Args:
            arguments: Must contain 'path' key

        Returns:
            File content wrapped in code fences with byte count

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is a directory
        """
        user_path = arguments["path"]
        path = self.resolve_path(user_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {user_path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {user_path}")

        size = path.stat().st_size
        if size > 1_000_000:
            return (
                f"File too large ({size:,} bytes). "
                "Use search_files to find specific content."
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        return f"```\n{content}\n```\n({len(content):,} bytes)"
