"""DEPRECATED: Use sunwell.features.external instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.external is deprecated. Use sunwell.features.external instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.external import *  # noqa: F403, F401
