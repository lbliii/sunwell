"""Binding management module (RFC-101 Phase 2).

Provides binding CRUD operations with URI-based identification
and project-scoped storage.

RFC-101 adds:
- URI-based identification (sunwell:binding/namespace/slug)
- Global index for O(1) listing
- Namespace isolation (global vs project-scoped)
"""

from sunwell.binding.identity import (
    BindingIndex,
    BindingIndexEntry,
    BindingIndexManager,
    create_binding_identity,
    create_binding_uri,
)
from sunwell.binding.manager import (
    Binding,
    BindingManager,
    get_binding_or_create_temp,
)

__all__ = [
    # Manager
    "Binding",
    "BindingManager",
    "get_binding_or_create_temp",
    # Identity types (RFC-101)
    "BindingIndex",
    "BindingIndexEntry",
    "BindingIndexManager",
    "create_binding_identity",
    "create_binding_uri",
]
