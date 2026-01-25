"""DEPRECATED: Use sunwell.knowledge.indexing instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.indexing is deprecated. Use sunwell.knowledge.indexing instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.indexing import *  # noqa: F403, F401
