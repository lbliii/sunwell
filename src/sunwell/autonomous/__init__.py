"""DEPRECATED: Use sunwell.features.autonomous instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.autonomous is deprecated. Use sunwell.features.autonomous instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.autonomous import *  # noqa: F403, F401
