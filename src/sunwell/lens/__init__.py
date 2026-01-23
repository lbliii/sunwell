"""Lens management module (RFC-070, RFC-101).

Provides CRUD operations, versioning, and library functionality for lenses.

RFC-101 adds:
- URI-based identification (sunwell:lens/namespace/slug@version)
- Global index for O(1) library listing
- Content-addressable versioning
- Namespace isolation (builtin, user, project)
"""

from sunwell.lens.identity import (
    LensIndexEntry,
    LensLineage,
    LensManifest,
    LensVersionInfo,
)
from sunwell.lens.index import (
    LensIndex,
    LensIndexManager,
    add_version_to_manifest,
    create_lens_manifest,
)
from sunwell.lens.manager import (
    LensLibraryEntry,
    LensManager,
)

__all__ = [
    # Manager
    "LensLibraryEntry",
    "LensManager",
    # Identity types (RFC-101)
    "LensIndexEntry",
    "LensLineage",
    "LensManifest",
    "LensVersionInfo",
    # Index management (RFC-101)
    "LensIndex",
    "LensIndexManager",
    "add_version_to_manifest",
    "create_lens_manifest",
]
