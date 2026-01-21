#!/usr/bin/env python3
"""Check the size of Cursor's SQLite databases without modifying them."""

import os
from pathlib import Path
from typing import Iterator


def find_cursor_databases() -> Iterator[Path]:
    """Find all SQLite database files in Cursor's application support directory."""
    cursor_support = Path.home() / "Library/Application Support/Cursor"
    
    if not cursor_support.exists():
        print(f"❌ Cursor support directory not found: {cursor_support}")
        return
    
    # Common database file patterns (including VS Code/Cursor databases)
    patterns = ["*.db", "*.sqlite", "*.sqlite3", "*.vscdb"]
    
    for pattern in patterns:
        for db_file in cursor_support.rglob(pattern):
            # Skip temporary files
            if db_file.name.startswith(".") or "journal" in db_file.name:
                continue
            yield db_file


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def main() -> None:
    """Main entry point."""
    print("🔍 Checking Cursor database sizes...\n")
    
    cursor_support = Path.home() / "Library/Application Support/Cursor"
    if not cursor_support.exists():
        print(f"❌ Cursor support directory not found: {cursor_support}")
        return
    
    databases = list(find_cursor_databases())
    
    if not databases:
        print("❌ No database files found in Cursor's support directory.")
        print("   Make sure Cursor is installed and has been used.")
        return
    
    print(f"Found {len(databases)} database file(s):\n")
    
    total_size = 0
    large_dbs = []
    
    for db_path in sorted(databases, key=lambda p: p.stat().st_size, reverse=True):
        size = db_path.stat().st_size
        total_size += size
        rel_path = db_path.relative_to(Path.home())
        
        size_str = format_size(size)
        print(f"📁 {rel_path}")
        print(f"   Size: {size_str}")
        
        # Flag databases larger than 100MB as potentially needing vacuum
        if size > 100 * 1024 * 1024:  # 100MB
            large_dbs.append((db_path, size))
        print()
    
    print("=" * 60)
    print(f"Total database size: {format_size(total_size)}")
    print()
    
    # Check for old backup files that can be deleted
    old_backups = [
        db_path for db_path in databases
        if ".old" in db_path.name or ".backup.old" in db_path.name
    ]
    
    if old_backups:
        old_backup_size = sum(p.stat().st_size for p in old_backups)
        print(f"🗑️  Found {len(old_backups)} old backup file(s) that can be safely deleted:")
        for db_path in sorted(old_backups, key=lambda p: p.stat().st_size, reverse=True):
            rel_path = db_path.relative_to(Path.home())
            print(f"   • {rel_path}: {format_size(db_path.stat().st_size)}")
        print(f"   Total recoverable: {format_size(old_backup_size)}")
        print()
    
    if large_dbs:
        print(f"⚠️  Found {len(large_dbs)} database(s) larger than 100MB:")
        for db_path, size in large_dbs:
            rel_path = db_path.relative_to(Path.home())
            print(f"   • {rel_path}: {format_size(size)}")
        print()
        print("💡 These databases may benefit from VACUUM to reclaim space.")
        print("   Run: python scripts/vacuum_cursor_db.py")
    else:
        print("✅ All active databases are reasonably sized (< 100MB)")
        print("   Vacuum may not be necessary, but won't hurt if you want to optimize.")
    
    if old_backups:
        print()
        print("💡 To delete old backup files and free up space:")
        print("   Run: python scripts/clean_cursor_backups.py")


if __name__ == "__main__":
    main()
