#!/usr/bin/env python3
"""Delete old Cursor database backup files to free up space.

WARNING: This will permanently delete old backup files.
Make sure Cursor is closed before running this script.
"""

import os
from pathlib import Path
from typing import Iterator


def find_old_backups() -> Iterator[Path]:
    """Find old backup database files in Cursor's application support directory."""
    cursor_support = Path.home() / "Library/Application Support/Cursor"
    
    if not cursor_support.exists():
        print(f"❌ Cursor support directory not found: {cursor_support}")
        return
    
    # Look for old backup files
    patterns = ["*.db.old", "*.sqlite.old", "*.sqlite3.old", "*.vscdb.old", "*.vscdb.backup.old"]
    
    for pattern in patterns:
        for backup_file in cursor_support.rglob(pattern):
            yield backup_file


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def main() -> None:
    """Main entry point."""
    print("🔍 Searching for old Cursor backup files...\n")
    
    backups = list(find_old_backups())
    
    if not backups:
        print("✅ No old backup files found.")
        return
    
    total_size = sum(b.stat().st_size for b in backups)
    
    print(f"Found {len(backups)} old backup file(s):\n")
    
    for backup_path in sorted(backups, key=lambda p: p.stat().st_size, reverse=True):
        size = backup_path.stat().st_size
        rel_path = backup_path.relative_to(Path.home())
        print(f"📁 {rel_path}")
        print(f"   Size: {format_size(size)}")
        print()
    
    print("=" * 60)
    print(f"Total size: {format_size(total_size)}")
    print()
    
    response = input("⚠️  Delete these old backup files? (yes/no): ").strip().lower()
    
    if response not in ("yes", "y"):
        print("❌ Cancelled. No files deleted.")
        return
    
    deleted = 0
    deleted_size = 0
    
    for backup_path in backups:
        try:
            size = backup_path.stat().st_size
            backup_path.unlink()
            deleted += 1
            deleted_size += size
            rel_path = backup_path.relative_to(Path.home())
            print(f"✅ Deleted: {rel_path}")
        except OSError as e:
            rel_path = backup_path.relative_to(Path.home())
            print(f"❌ Failed to delete {rel_path}: {e}")
    
    print()
    print("=" * 60)
    print(f"Summary:")
    print(f"  Files deleted: {deleted}/{len(backups)}")
    print(f"  Space freed: {format_size(deleted_size)}")
    print()
    print("✅ Done! You can now run vacuum_cursor_db.py to optimize remaining databases.")


if __name__ == "__main__":
    main()
