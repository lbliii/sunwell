"""DEPRECATED: Use sunwell.quality.verification instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.verification is deprecated. Use sunwell.quality.verification instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.quality.verification import *  # noqa: F403, F401
