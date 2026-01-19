#!/usr/bin/env python3
"""Strip RFC references from source files.

This script removes internal RFC IDs from docstrings and comments while
preserving the descriptive content.

Usage:
    python scripts/strip_rfc_references.py [--dry-run]
"""

import re
import sys
from pathlib import Path


def strip_rfc_from_content(content: str) -> tuple[str, int]:
    """Remove RFC references from file content.
    
    Returns (modified_content, change_count).
    """
    changes = 0
    original = content
    
    # Pattern 1: Standalone RFC comments like "# RFC-XXX" or "# : Description"
    # Remove entire line
    content, n = re.subn(r'^[ \t]*#\s*RFC-\d{3}[^\n]*\n', '', content, flags=re.MULTILINE)
    changes += n
    
    # Pattern 2: "(RFC-XXX)" in parentheses - remove the parenthesized part
    content, n = re.subn(r'\s*\(RFC-\d{3}\)', '', content)
    changes += n
    
    # Pattern 3: " - RFC-XXX" or ", RFC-XXX" - remove
    content, n = re.subn(r'\s*[-,]\s*RFC-\d{3}', '', content)
    changes += n
    
    # Pattern 4: "RFC-XXX features" → "features" (in prose)
    content, n = re.subn(r'RFC-\d{3}\s+features', 'features', content)
    changes += n
    
    # Pattern 5: "RFC-XXX " standalone mentions
    content, n = re.subn(r'\bRFC-\d{3}\b\s*', '', content)
    changes += n
    
    # Clean up double spaces and trailing whitespace
    content = re.sub(r'  +', ' ', content)
    content = re.sub(r' +$', '', content, flags=re.MULTILINE)
    
    # Clean up empty comment lines that might remain
    content = re.sub(r'^[ \t]*#\s*$\n', '', content, flags=re.MULTILINE)
    
    return content, changes


def process_file(filepath: Path, dry_run: bool = False) -> int:
    """Process a single file. Returns number of changes made."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return 0
    
    new_content, changes = strip_rfc_from_content(content)
    
    if changes > 0 and not dry_run:
        filepath.write_text(new_content, encoding='utf-8')
    
    return changes


def main():
    dry_run = '--dry-run' in sys.argv
    
    src_dir = Path(__file__).parent.parent / 'src' / 'sunwell'
    tests_dir = Path(__file__).parent.parent / 'tests'
    
    # Collect all Python files
    files = list(src_dir.rglob('*.py')) + list(tests_dir.rglob('*.py'))
    
    total_changes = 0
    modified_files = 0
    
    for filepath in sorted(files):
        changes = process_file(filepath, dry_run)
        if changes > 0:
            modified_files += 1
            total_changes += changes
            if dry_run:
                print(f"Would modify: {filepath.relative_to(src_dir.parent.parent)} ({changes} changes)")
            else:
                print(f"Modified: {filepath.relative_to(src_dir.parent.parent)} ({changes} changes)")
    
    action = "Would modify" if dry_run else "Modified"
    print(f"\n{action} {modified_files} files with {total_changes} total changes")
    
    if dry_run:
        print("\nRun without --dry-run to apply changes")


if __name__ == '__main__':
    main()
