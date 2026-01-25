"""DEPRECATED: Use sunwell.features.mirror.self instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.self is deprecated. Use sunwell.features.mirror.self instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.mirror.self import *  # noqa: F403, F401
