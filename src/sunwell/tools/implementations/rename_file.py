"""Rename/move file tool."""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="rename_file",
    simple_description="Rename or move a file",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use rename_file to move or rename files within the workspace. Creates parent directories for destination automatically.",
)
class RenameFileTool(BaseTool):
    """Rename or move a file within the workspace."""

    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Current file path (relative to workspace)",
            },
            "destination": {
                "type": "string",
                "description": "New file path (relative to workspace)",
            },
        },
        "required": ["source", "destination"],
    }

    async def execute(self, arguments: dict) -> str:
        source_path = arguments["source"]
        dest_path = arguments["destination"]

        src = self.resolve_path(source_path)
        dst = self.resolve_path(dest_path)

        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        if not src.is_file():
            raise ValueError(f"Source is not a file: {source_path}")
        if dst.exists():
            raise ValueError(f"Destination already exists: {dest_path}")

        # Create parent directories for destination
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Perform the rename
        src.rename(dst)

        return f"✓ Renamed {source_path} → {dest_path}"
