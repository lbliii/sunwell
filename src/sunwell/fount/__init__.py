"""DEPRECATED: Use sunwell.features.fount instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.fount is deprecated. Use sunwell.features.fount instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.fount import *  # noqa: F403, F401
