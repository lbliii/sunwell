"""List backups tool."""

import json
from pathlib import Path

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

BACKUP_METADATA_FILE = "backup_index.json"


def _get_backup_dir(workspace: Path) -> Path:
    """Get backup directory path."""
    return workspace / ".sunwell" / "backups"


def _load_index(workspace: Path) -> dict[str, list[dict]]:
    """Load or create the backup index."""
    backup_dir = _get_backup_dir(workspace)
    index_path = backup_dir / BACKUP_METADATA_FILE
    if index_path.exists():
        try:
            return json.loads(index_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


@tool_metadata(
    name="list_backups",
    simple_description="List available file backups",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use list_backups to see available restore points before using undo_file or restore_file.",
)
class ListBackupsTool(BaseTool):
    """List available backups for a file or all files."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Filter by file path (optional, lists all if omitted)",
            },
        },
        "required": [],
    }

    async def execute(self, arguments: dict) -> str:
        filter_path = arguments.get("path")
        workspace = self.project.root
        index = _load_index(workspace)

        if not index:
            return "No backups available"

        if filter_path:
            if filter_path not in index or not index[filter_path]:
                return f"No backups found for {filter_path}"

            entries = index[filter_path]
            lines = [f"Backups for {filter_path} ({len(entries)} available):"]
            for i, entry in enumerate(entries):
                lines.append(
                    f"  [{i}] {entry['timestamp']} - {entry['operation']} "
                    f"({entry['size_bytes']:,} bytes)"
                )
            return "\n".join(lines)

        # List all files with backups
        lines = [f"Files with backups ({len(index)} files):"]
        for file_path, entries in sorted(index.items()):
            if entries:
                latest = entries[0]
                lines.append(
                    f"  {file_path}: {len(entries)} backup(s), "
                    f"latest {latest['timestamp']}"
                )
        return "\n".join(lines)
