"""DEPRECATED: Use sunwell.quality.confidence instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.confidence is deprecated. Use sunwell.quality.confidence instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.quality.confidence import *  # noqa: F403, F401
