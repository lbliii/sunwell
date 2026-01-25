"""Code parsing utilities.

RFC-138: Module Architecture Consolidation

Provides helpers for parsing code files and detecting file types.
"""

import ast
from pathlib import Path


def is_python_file(path: Path) -> bool:
    """Check if path is a Python file.

    Args:
        path: File path

    Returns:
        True if path has .py extension

    Example:
        >>> is_python_file(Path("file.py"))
        True
        >>> is_python_file(Path("file.txt"))
        False
    """
    return path.suffix == ".py"


def parse_python_file(path: Path) -> ast.Module | None:
    """Parse a Python file into an AST.

    Args:
        path: Path to Python file

    Returns:
        AST Module node, or None if parsing fails

    Example:
        >>> tree = parse_python_file(Path("file.py"))
        >>> isinstance(tree, ast.Module)
        True
    """
    try:
        content = path.read_text(encoding="utf-8")
        return ast.parse(content, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def get_file_encoding(path: Path) -> str:
    """Detect file encoding (simple heuristic).

    Args:
        path: File path

    Returns:
        Encoding name (defaults to 'utf-8')

    Note:
        This is a simple heuristic. For robust detection, use chardet.
    """
    try:
        # Try UTF-8 first
        path.read_text(encoding="utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        # Fallback to latin-1 (always works, but may be wrong)
        return "latin-1"
