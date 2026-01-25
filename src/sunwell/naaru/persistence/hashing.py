"""Content hashing utilities for change detection."""

import hashlib
from pathlib import Path


def hash_goal(goal: str) -> str:
    """Hash a goal string for deterministic lookup.

    Args:
        goal: The goal text

    Returns:
        16-character hex hash
    """
    return hashlib.sha256(goal.encode()).hexdigest()[:16]


def hash_content(content: str | bytes) -> str:
    """Hash content for change detection.

    Args:
        content: String or bytes to hash

    Returns:
        16-character hex hash
    """
    if isinstance(content, str):
        content = content.encode()
    return hashlib.sha256(content).hexdigest()[:16]


def hash_file(path: Path) -> str | None:
    """Hash a file's contents for change detection.

    Args:
        path: Path to file

    Returns:
        16-character hex hash, or None if file doesn't exist
    """
    if not path.exists():
        return None
    return hash_content(path.read_bytes())
