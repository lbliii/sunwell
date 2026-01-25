"""DEPRECATED: Use sunwell.features.team instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.team is deprecated. Use sunwell.features.team instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.team import *  # noqa: F403, F401
