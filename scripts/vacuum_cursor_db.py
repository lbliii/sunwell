#!/usr/bin/env python3
"""Vacuum Cursor's SQLite databases to reclaim space and optimize performance.

WARNING: Close Cursor completely before running this script.
VACUUM requires exclusive database access.
"""

import sqlite3
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


def get_db_size(path: Path) -> int:
    """Get database file size in bytes."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def vacuum_database(db_path: Path) -> tuple[bool, str, int, int]:
    """Vacuum a SQLite database and return success status, message, and size change."""
    original_size = get_db_size(db_path)
    
    try:
        # Connect and vacuum
        conn = sqlite3.connect(str(db_path))
        conn.execute("VACUUM")
        conn.close()
        
        new_size = get_db_size(db_path)
        size_saved = original_size - new_size
        
        return True, "✅ Success", original_size, size_saved
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            return False, "🔒 Database is locked (Cursor may be running)", original_size, 0
        return False, f"❌ Error: {e}", original_size, 0
    except Exception as e:
        return False, f"❌ Error: {e}", original_size, 0


def main() -> None:
    """Main entry point."""
    print("🔍 Searching for Cursor database files...\n")
    
    databases = list(find_cursor_databases())
    
    if not databases:
        print("❌ No database files found in Cursor's support directory.")
        print("   Make sure Cursor is installed and has been used.")
        return
    
    print(f"Found {len(databases)} database file(s):\n")
    
    total_original = 0
    total_saved = 0
    successful = 0
    
    # Skip old backup files - they should be deleted, not vacuumed
    active_databases = [
        db for db in databases
        if ".old" not in db.name and ".backup.old" not in db.name
    ]
    
    if len(active_databases) < len(databases):
        skipped = len(databases) - len(active_databases)
        print(f"⏭️  Skipping {skipped} old backup file(s) (should be deleted, not vacuumed)\n")
    
    for db_path in active_databases:
        rel_path = db_path.relative_to(Path.home())
        print(f"📁 {rel_path}")
        print(f"   Size: {format_size(get_db_size(db_path))}")
        
        success, message, original_size, saved = vacuum_database(db_path)
        total_original += original_size
        
        if success:
            successful += 1
            total_saved += saved
            print(f"   {message}")
            if saved > 0:
                print(f"   Reclaimed: {format_size(saved)}")
            else:
                print(f"   Already optimized")
        else:
            print(f"   {message}")
        
        print()
    
    print("=" * 60)
    print(f"Summary:")
    print(f"  Databases processed: {len(databases)}")
    print(f"  Successful: {successful}")
    print(f"  Total original size: {format_size(total_original)}")
    if total_saved > 0:
        print(f"  Total space reclaimed: {format_size(total_saved)}")
    print()
    
    if successful < len(databases):
        print("⚠️  Some databases couldn't be vacuumed.")
        print("   Make sure Cursor is completely closed and try again.")


if __name__ == "__main__":
    main()
