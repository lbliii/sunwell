"""DEPRECATED: Use sunwell.quality.weakness instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.weakness is deprecated. Use sunwell.quality.weakness instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.quality.weakness import *  # noqa: F403, F401
