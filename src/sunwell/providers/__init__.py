"""DEPRECATED: Use sunwell.models.providers instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.providers is deprecated. Use sunwell.models.providers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.models.providers import *  # noqa: F403, F401
