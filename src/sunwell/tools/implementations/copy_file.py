"""Copy file tool."""

import shutil

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="copy_file",
    simple_description="Copy a file to a new location",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use copy_file to duplicate files within the workspace. Creates parent directories for destination automatically.",
)
class CopyFileTool(BaseTool):
    """Copy a file within the workspace."""

    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Source file path (relative to workspace)",
            },
            "destination": {
                "type": "string",
                "description": "Destination file path (relative to workspace)",
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

        # Perform the copy (preserves metadata)
        shutil.copy2(src, dst)

        size = dst.stat().st_size
        return f"✓ Copied {source_path} → {dest_path} ({size:,} bytes)"
