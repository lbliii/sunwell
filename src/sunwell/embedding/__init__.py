"""DEPRECATED: Use sunwell.knowledge.embedding instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.embedding is deprecated. Use sunwell.knowledge.embedding instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.embedding import *  # noqa: F403, F401
