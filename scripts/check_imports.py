#!/usr/bin/env python3
"""Scan for potentially incorrect imports in the codebase.

This script checks for imports that reference non-existent modules by:
1. Parsing all Python files
2. Extracting import statements
3. Checking if the module path exists in the filesystem
4. Reporting suspicious imports
"""

import ast
import sys
from pathlib import Path
from typing import Any


def get_imports_from_file(file_path: Path) -> list[tuple[str, int]]:
    """Extract all import statements from a Python file.
    
    Returns list of (import_path, line_number) tuples.
    """
    imports = []
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append((node.module, node.lineno))
    except SyntaxError:
        # Skip files with syntax errors
        pass
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
    
    return imports


def check_module_exists(module_path: str, src_root: Path) -> bool:
    """Check if a module path exists in the source tree.
    
    For 'sunwell.interface.cli.helpers', checks if:
    - src/sunwell/interface/cli/helpers/__init__.py exists, OR
    - src/sunwell/interface/cli/helpers.py exists
    """
    if not module_path.startswith("sunwell."):
        # Skip third-party imports
        return True
    
    # Convert module path to filesystem path
    parts = module_path.split(".")
    if parts[0] != "sunwell":
        return True
    
    # Check for __init__.py path
    module_dir = src_root / Path(*parts)
    if (module_dir / "__init__.py").exists():
        return True
    
    # Check for .py file (last part is filename)
    if len(parts) > 1:
        module_file = src_root / Path(*parts[:-1]) / f"{parts[-1]}.py"
        if module_file.exists():
            return True
    
    return False


def scan_directory(directory: Path, src_root: Path | None = None) -> list[tuple[Path, str, int]]:
    """Scan a directory for import errors.
    
    Returns list of (file_path, import_path, line_number) tuples for suspicious imports.
    """
    if src_root is None:
        # Assume we're in the project root
        src_root = directory.parent / "src"
    
    errors = []
    python_files = list(directory.rglob("*.py"))
    
    print(f"Scanning {len(python_files)} Python files...", file=sys.stderr)
    
    for py_file in python_files:
        imports = get_imports_from_file(py_file)
        for import_path, line_num in imports:
            if not check_module_exists(import_path, src_root):
                errors.append((py_file, import_path, line_num))
    
    return errors


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scan for potentially incorrect imports"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=Path("src"),
        type=Path,
        help="Directory to scan (default: src/)"
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        help="Root of source tree (default: directory/../src or directory)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all imports, not just errors"
    )
    
    args = parser.parse_args()
    
    directory = Path(args.directory).resolve()
    if args.src_root:
        src_root = Path(args.src_root).resolve()
    else:
        # Find the project root (contains src/sunwell)
        current = directory
        while current != current.parent:
            src_candidate = current / "src" / "sunwell"
            if src_candidate.exists():
                src_root = current / "src"
                break
            current = current.parent
        else:
            # Fallback: assume src/ is sibling to directory
            src_root = directory.parent / "src"
    
    if not src_root.exists():
        print(f"Error: Source root {src_root} does not exist", file=sys.stderr)
        sys.exit(1)
    
    errors = scan_directory(directory, src_root)
    
    if errors:
        print(f"\n❌ Found {len(errors)} potentially incorrect imports:\n")
        for file_path, import_path, line_num in errors:
            rel_path = file_path.relative_to(directory.parent if directory.name != "src" else directory.parent)
            print(f"  {rel_path}:{line_num}")
            print(f"    {import_path}")
        sys.exit(1)
    else:
        print("\n✅ No suspicious imports found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
