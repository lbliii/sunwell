"""Undo/rollback operation handlers.

Provides backup management and file restoration capabilities:
- undo_file: Restore from most recent backup
- list_backups: Show available restore points
- restore_file: Restore from specific backup

Backup storage: .sunwell/backups/{date}/{file_hash}.bak
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.tools.handlers.base import BaseHandler

logger = logging.getLogger(__name__)

# Maximum number of backups to retain per file
MAX_BACKUPS_PER_FILE = 10

# Backup metadata filename
BACKUP_METADATA_FILE = "backup_index.json"


@dataclass(frozen=True, slots=True)
class BackupEntry:
    """A single backup entry."""

    original_path: str
    backup_path: str
    timestamp: str
    size_bytes: int
    operation: str  # "edit", "write", "delete", "patch"


class UndoHandlers(BaseHandler):
    """Undo and backup management handlers.

    Manages a structured backup directory for file operations,
    enabling restoration of previous file states.
    """

    def __init__(self, workspace: Path, **kwargs: Any) -> None:
        super().__init__(workspace, **kwargs)
        self._backup_dir = workspace / ".sunwell" / "backups"
        self._index_path = self._backup_dir / BACKUP_METADATA_FILE
        self._backup_index: dict[str, list[dict]] | None = None

    def _ensure_backup_dir(self) -> Path:
        """Ensure backup directory exists."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        return self._backup_dir

    def _load_index(self) -> dict[str, list[dict]]:
        """Load or create the backup index."""
        if self._backup_index is not None:
            return self._backup_index

        if self._index_path.exists():
            try:
                self._backup_index = json.loads(self._index_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._backup_index = {}
        else:
            self._backup_index = {}

        return self._backup_index

    def _save_index(self) -> None:
        """Save the backup index to disk."""
        if self._backup_index is None:
            return

        self._ensure_backup_dir()
        self._index_path.write_text(json.dumps(self._backup_index, indent=2))

    def _get_backup_filename(self, path: str, content: str) -> str:
        """Generate a unique backup filename."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = path.replace("/", "_").replace("\\", "_")
        return f"{safe_name}_{timestamp}_{content_hash}.bak"

    def record_backup(
        self,
        original_path: str,
        content: str,
        operation: str = "edit",
    ) -> Path:
        """Record a backup for a file.

        Called by file handlers before modifying files.

        Args:
            original_path: Relative path to the original file
            content: Content to back up
            operation: Type of operation (edit, write, delete, patch)

        Returns:
            Path to the backup file
        """
        self._ensure_backup_dir()
        index = self._load_index()

        # Create dated subdirectory
        date_dir = self._backup_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)

        # Generate backup filename and write content
        backup_filename = self._get_backup_filename(original_path, content)
        backup_path = date_dir / backup_filename
        backup_path.write_text(content, encoding="utf-8")

        # Record in index
        entry = {
            "original_path": original_path,
            "backup_path": str(backup_path.relative_to(self._backup_dir)),
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
                old_path = self._backup_dir / old_entry["backup_path"]
                if old_path.exists():
                    old_path.unlink()

        self._save_index()
        return backup_path

    async def undo_file(self, args: dict) -> str:
        """Restore a file from its most recent backup.

        Args:
            args: {"path": str} - relative path to restore

        Returns:
            Result message
        """
        user_path = args["path"]
        path = self._safe_path(user_path)

        index = self._load_index()

        if user_path not in index or not index[user_path]:
            return f"No backups found for {user_path}"

        # Get most recent backup
        latest = index[user_path][0]
        backup_path = self._backup_dir / latest["backup_path"]

        if not backup_path.exists():
            # Remove stale entry
            index[user_path].pop(0)
            self._save_index()
            return f"Backup file missing: {latest['backup_path']}"

        # Read backup content
        backup_content = backup_path.read_text(encoding="utf-8")

        # Save current state as a new backup before restoring (in case of mistake)
        if path.exists():
            current_content = path.read_text(encoding="utf-8", errors="replace")
            self.record_backup(user_path, current_content, "undo_previous")

        # Restore the file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(backup_content, encoding="utf-8")

        # Remove used backup from index
        index[user_path].pop(0)
        self._save_index()

        timestamp = latest["timestamp"]
        operation = latest["operation"]

        return (
            f"✓ Restored {user_path}\n"
            f"  From backup: {timestamp}\n"
            f"  Original operation: {operation}\n"
            f"  Size: {latest['size_bytes']:,} bytes"
        )

    async def list_backups(self, args: dict) -> str:
        """List available backups for a file or all files.

        Args:
            args: {"path": str (optional)} - filter by path

        Returns:
            Formatted list of backups
        """
        filter_path = args.get("path")
        index = self._load_index()

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

    async def restore_file(self, args: dict) -> str:
        """Restore a file from a specific backup.

        Args:
            args: {"path": str, "index": int} - path and backup index

        Returns:
            Result message
        """
        user_path = args["path"]
        backup_index = args.get("index", 0)
        path = self._safe_path(user_path)

        index = self._load_index()

        if user_path not in index or not index[user_path]:
            return f"No backups found for {user_path}"

        entries = index[user_path]
        if backup_index < 0 or backup_index >= len(entries):
            return f"Invalid backup index {backup_index}. Available: 0-{len(entries) - 1}"

        entry = entries[backup_index]
        backup_path = self._backup_dir / entry["backup_path"]

        if not backup_path.exists():
            return f"Backup file missing: {entry['backup_path']}"

        # Read backup content
        backup_content = backup_path.read_text(encoding="utf-8")

        # Save current state before restoring
        if path.exists():
            current_content = path.read_text(encoding="utf-8", errors="replace")
            self.record_backup(user_path, current_content, "restore_previous")

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
