"""Delete file tool implementation."""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="delete_file",
    simple_description="Delete a file with backup",
    trust_level=ToolTrust.WORKSPACE,
    usage_guidance=(
        "Creates a backup before deletion for safety. "
        "For version-controlled files, prefer git operations. "
        "Cannot delete directories - use rmdir for that."
    ),
)
class DeleteFileTool(BaseTool):
    """Delete a file.

    Creates a backup before deletion for safety.
    Use with caution - prefer git operations for version-controlled files.
    """

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
        """Delete file with backup.

        Args:
            arguments: Must contain 'path'

        Returns:
            Success message with backup info

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is a directory
        """
        user_path = arguments["path"]
        path = self.resolve_path(user_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {user_path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {user_path}. Use rmdir for directories.")

        # Read content for backup
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            lines_removed = content.count("\n") + 1 if content else 0
        except OSError:
            content = ""
            lines_removed = 0

        # Create backup before deletion
        backup_path = path.with_suffix(path.suffix + ".deleted.bak")
        backup_path.write_text(content, encoding="utf-8")

        # Delete the file
        path.unlink()

        return f"✓ Deleted {user_path} ({lines_removed} lines, backup: {backup_path.name})"
