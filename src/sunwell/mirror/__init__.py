"""DEPRECATED: Use sunwell.features.mirror instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.mirror is deprecated. Use sunwell.features.mirror instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.mirror import *  # noqa: F403, F401
