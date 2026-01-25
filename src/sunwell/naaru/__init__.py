"""DEPRECATED: Use sunwell.planning.naaru instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.naaru is deprecated. Use sunwell.planning.naaru instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.planning.naaru import *  # noqa: F403, F401
