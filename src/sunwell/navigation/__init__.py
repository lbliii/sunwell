"""DEPRECATED: Use sunwell.knowledge.navigation instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.navigation is deprecated. Use sunwell.knowledge.navigation instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.navigation import *  # noqa: F403, F401
