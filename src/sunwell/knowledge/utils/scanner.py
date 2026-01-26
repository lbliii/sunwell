"""File scanning utilities for codebase analysis.

RFC-138: Module Architecture Consolidation

Provides helpers for scanning directories and finding code files.
"""

from pathlib import Path

# Common directories to skip when scanning
SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
}


# Common file patterns to skip
SKIP_PATTERNS = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*~",
}


def should_skip_path(path: Path) -> bool:
    """Check if a path should be skipped during scanning.

    Args:
        path: Path to check

    Returns:
        True if path should be skipped

    Example:
        >>> should_skip_path(Path("__pycache__/file.pyc"))
        True
        >>> should_skip_path(Path("src/file.py"))
        False
    """
    # Check if any parent directory is in skip list
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
        if part.startswith(".") and part != ".":
            return True

    # Check file extension patterns
    if any(path.match(pattern) for pattern in SKIP_PATTERNS):
        return True

    return False


def scan_code_files(
    root: Path,
    extensions: set[str] | None = None,
    max_depth: int | None = None,
) -> list[Path]:
    """Scan directory for code files.

    Args:
        root: Root directory to scan
        extensions: Set of file extensions to include (e.g., {".py", ".js"})
            If None, includes all files
        max_depth: Maximum directory depth (None = unlimited)

    Returns:
        List of matching file paths

    Example:
        >>> files = scan_code_files(Path("src"), extensions={".py"})
        >>> len(files) > 0
        True
    """
    if extensions is None:
        extensions = {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c"}

    files: list[Path] = []

    def scan_recursive(path: Path, depth: int = 0) -> None:
        if max_depth is not None and depth > max_depth:
            return

        if should_skip_path(path):
            return

        if path.is_file():
            if path.suffix in extensions:
                files.append(path)
        elif path.is_dir():
            try:
                for child in path.iterdir():
                    scan_recursive(child, depth + 1)
            except PermissionError:
                # Skip directories we can't read
                pass

    scan_recursive(root)
    return sorted(files)


def scan_directory(
    root: Path,
    include_files: bool = True,
    include_dirs: bool = False,
    max_depth: int | None = None,
) -> list[Path]:
    """Scan directory for files and/or directories.

    Args:
        root: Root directory to scan
        include_files: Include files in results
        include_dirs: Include directories in results
        max_depth: Maximum directory depth (None = unlimited)

    Returns:
        List of matching paths

    Example:
        >>> paths = scan_directory(Path("src"), include_files=True)
        >>> len(paths) > 0
        True
    """
    paths: list[Path] = []

    def scan_recursive(path: Path, depth: int = 0) -> None:
        if max_depth is not None and depth > max_depth:
            return

        if should_skip_path(path):
            return

        if path.is_file() and include_files:
            paths.append(path)
        elif path.is_dir():
            if include_dirs and path != root:
                paths.append(path)
            try:
                for child in path.iterdir():
                    scan_recursive(child, depth + 1)
            except PermissionError:
                pass

    scan_recursive(root)
    return sorted(paths)
