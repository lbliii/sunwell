"""Generic content hashing utilities.

RFC-138: Module Architecture Consolidation

Provides zero-dependency hashing functions for any content.
Domain-specific hashing (e.g., artifact hashing) stays in domains.
"""

import hashlib
from pathlib import Path


def compute_hash(content: bytes) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: Bytes to hash

    Returns:
        64-character hexadecimal hash string

    Example:
        >>> compute_hash(b"hello")
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return hashlib.sha256(content).hexdigest()


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file contents.

    Args:
        path: Path to file

    Returns:
        64-character hexadecimal hash string

    Raises:
        FileNotFoundError: If file doesn't exist
        OSError: If file cannot be read

    Example:
        >>> compute_file_hash(Path("test.txt"))
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return compute_hash(path.read_bytes())


def compute_string_hash(text: str) -> str:
    """Compute SHA-256 hash of string (UTF-8 encoded).

    Args:
        text: String to hash

    Returns:
        64-character hexadecimal hash string

    Example:
        >>> compute_string_hash("hello")
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return compute_hash(text.encode("utf-8"))
