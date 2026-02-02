"""Undo file changes tool."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

MAX_BACKUPS_PER_FILE = 10
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


def _save_index(workspace: Path, index: dict[str, list[dict]]) -> None:
    """Save the backup index to disk."""
    backup_dir = _get_backup_dir(workspace)
    backup_dir.mkdir(parents=True, exist_ok=True)
    index_path = backup_dir / BACKUP_METADATA_FILE
    index_path.write_text(json.dumps(index, indent=2))


def _get_backup_filename(path: str, content: str) -> str:
    """Generate a unique backup filename."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = path.replace("/", "_").replace("\\", "_")
    return f"{safe_name}_{timestamp}_{content_hash}.bak"


def record_backup(
    workspace: Path, original_path: str, content: str, operation: str = "edit"
) -> Path:
    """Record a backup for a file."""
    backup_dir = _get_backup_dir(workspace)
    backup_dir.mkdir(parents=True, exist_ok=True)
    index = _load_index(workspace)

    # Create dated subdirectory
    date_dir = backup_dir / datetime.now().strftime("%Y-%m-%d")
    date_dir.mkdir(exist_ok=True)

    # Generate backup filename and write content
    backup_filename = _get_backup_filename(original_path, content)
    backup_path = date_dir / backup_filename
    backup_path.write_text(content, encoding="utf-8")

    # Record in index
    entry = {
        "original_path": original_path,
        "backup_path": str(backup_path.relative_to(backup_dir)),
        "timestamp": datetime.now().isoformat(),
        "size_bytes": len(content),
        "operation": operation,
    }

    if original_path not in index:
        index[original_path] = []

    index[original_path].insert(0, entry)  # Most recent first

    # Prune old backups
    if len(index[original_path]) > MAX_BACKUPS_PER_FILE:
        old_entries = index[original_path][MAX_BACKUPS_PER_FILE:]
        index[original_path] = index[original_path][:MAX_BACKUPS_PER_FILE]

        # Delete old backup files
        for old_entry in old_entries:
            old_path = backup_dir / old_entry["backup_path"]
            if old_path.exists():
                old_path.unlink()

    _save_index(workspace, index)
    return backup_path


@tool_metadata(
    name="undo_file",
    simple_description="Restore file from most recent backup",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use undo_file to restore a file to its previous state after an edit or write operation.",
)
class UndoFileTool(BaseTool):
    """Restore a file from its most recent backup."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to restore (relative to workspace)",
            },
        },
        "required": ["path"],
    }

    async def execute(self, arguments: dict) -> str:
        user_path = arguments["path"]
        path = self.resolve_path(user_path)
        workspace = self.project.root
        backup_dir = _get_backup_dir(workspace)

        index = _load_index(workspace)

        if user_path not in index or not index[user_path]:
            return f"No backups found for {user_path}"

        # Get most recent backup
        latest = index[user_path][0]
        backup_path = backup_dir / latest["backup_path"]

        if not backup_path.exists():
            # Remove stale entry
            index[user_path].pop(0)
            _save_index(workspace, index)
            return f"Backup file missing: {latest['backup_path']}"

        # Read backup content
        backup_content = backup_path.read_text(encoding="utf-8")

        # Save current state as a new backup before restoring
        if path.exists():
            current_content = path.read_text(encoding="utf-8", errors="replace")
            record_backup(workspace, user_path, current_content, "undo_previous")

        # Restore the file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(backup_content, encoding="utf-8")

        # Remove used backup from index
        index[user_path].pop(0)
        _save_index(workspace, index)

        timestamp = latest["timestamp"]
        operation = latest["operation"]

        return (
            f"✓ Restored {user_path}\n"
            f"  From backup: {timestamp}\n"
            f"  Original operation: {operation}\n"
            f"  Size: {latest['size_bytes']:,} bytes"
        )
