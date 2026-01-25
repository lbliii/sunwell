"""Filesystem-safe path utilities.

RFC-138: Module Architecture Consolidation

Provides zero-dependency path operations used across domains.
"""

import os
import re
from pathlib import Path


def normalize_path(path: str | Path) -> Path:
    """Normalize path (resolve, expand user, make absolute).

    Args:
        path: Path string or Path object

    Returns:
        Normalized absolute Path

    Example:
        >>> normalize_path("~/documents/file.txt")
        Path('/home/user/documents/file.txt')
    """
    p = Path(path)
    return p.expanduser().resolve()


def sanitize_filename(name: str) -> str:
    """Make filename filesystem-safe (remove invalid chars).

    Removes or replaces characters that are invalid in filenames:
    - Path separators (/ \\)
    - Null bytes
    - Control characters
    - Reserved names (CON, PRN, etc. on Windows)

    Args:
        name: Original filename

    Returns:
        Sanitized filename safe for filesystem

    Example:
        >>> sanitize_filename("my/file:name.txt")
        'my-file-name.txt'
    """
    # Remove path separators and null bytes
    sanitized = re.sub(r'[<>:"/\\|?\x00]', "-", name)

    # Remove leading/trailing dots and spaces (Windows issue)
    sanitized = sanitized.strip(". ")

    # Replace multiple dashes with single dash
    sanitized = re.sub(r"-+", "-", sanitized)

    # Remove Windows reserved names (case-insensitive)
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    base = sanitized.split(".", 1)[0].upper()
    if base in reserved:
        sanitized = f"_{sanitized}"

    # Ensure not empty
    return sanitized or "unnamed"


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, return Path.

    Creates parent directories if needed.

    Args:
        path: Directory path

    Returns:
        Path object (guaranteed to exist)

    Example:
        >>> ensure_dir(Path("output/subdir"))
        Path('output/subdir')
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_to_cwd(path: Path) -> Path:
    """Get path relative to current working directory.

    Args:
        path: Path to make relative

    Returns:
        Relative Path if possible, absolute Path otherwise

    Example:
        >>> relative_to_cwd(Path("/home/user/project/file.txt"))
        Path('file.txt')  # if cwd is /home/user/project
    """
    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        # Path is not under cwd, return absolute
        return path.resolve()
