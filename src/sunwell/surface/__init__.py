"""DEPRECATED: Use sunwell.interface.surface instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.surface is deprecated. Use sunwell.interface.surface instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.interface.surface import *  # noqa: F403, F401
