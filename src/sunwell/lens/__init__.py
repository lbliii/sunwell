"""Lens management module (RFC-070).

Provides CRUD operations, versioning, and library functionality for lenses.
"""

from sunwell.lens.manager import (
    LensLibraryEntry,
    LensManager,
    LensVersionInfo,
)

__all__ = [
    "LensLibraryEntry",
    "LensManager",
    "LensVersionInfo",
]
