"""DEPRECATED: Use sunwell.quality.security instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.security is deprecated. Use sunwell.quality.security instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.quality.security import *  # noqa: F403, F401
