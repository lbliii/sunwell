"""DEPRECATED: Use sunwell.planning.routing instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.routing is deprecated. Use sunwell.planning.routing instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.planning.routing import *  # noqa: F403, F401
