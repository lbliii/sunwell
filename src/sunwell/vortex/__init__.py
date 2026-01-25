"""DEPRECATED: Use sunwell.features.vortex instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.vortex is deprecated. Use sunwell.features.vortex instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.vortex import *  # noqa: F403, F401
