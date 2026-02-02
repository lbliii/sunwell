"""Restore file from specific backup tool."""

import json
from pathlib import Path

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.implementations.undo_file import record_backup
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
    name="restore_file",
    simple_description="Restore file from a specific backup",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use restore_file to restore a file from a specific backup index. Use list_backups first to see available indices.",
)
class RestoreFileTool(BaseTool):
    """Restore a file from a specific backup by index."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to restore (relative to workspace)",
            },
            "index": {
                "type": "integer",
                "description": "Backup index (0 = most recent, use list_backups to see options)",
                "default": 0,
            },
        },
        "required": ["path"],
    }

    async def execute(self, arguments: dict) -> str:
        user_path = arguments["path"]
        backup_index = arguments.get("index", 0)
        path = self.resolve_path(user_path)
        workspace = self.project.root
        backup_dir = _get_backup_dir(workspace)

        index = _load_index(workspace)

        if user_path not in index or not index[user_path]:
            return f"No backups found for {user_path}"

        entries = index[user_path]
        if backup_index < 0 or backup_index >= len(entries):
            return f"Invalid backup index {backup_index}. Available: 0-{len(entries) - 1}"

        entry = entries[backup_index]
        backup_path = backup_dir / entry["backup_path"]

        if not backup_path.exists():
            return f"Backup file missing: {entry['backup_path']}"

        # Read backup content
        backup_content = backup_path.read_text(encoding="utf-8")

        # Save current state before restoring
        if path.exists():
            current_content = path.read_text(encoding="utf-8", errors="replace")
            record_backup(workspace, user_path, current_content, "restore_previous")

        # Restore the file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(backup_content, encoding="utf-8")

        timestamp = entry["timestamp"]
        operation = entry["operation"]

        return (
            f"✓ Restored {user_path}\n"
            f"  From backup index [{backup_index}]: {timestamp}\n"
            f"  Original operation: {operation}\n"
            f"  Size: {entry['size_bytes']:,} bytes"
        )
