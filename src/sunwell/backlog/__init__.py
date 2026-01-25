"""DEPRECATED: Use sunwell.features.backlog instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.backlog is deprecated. Use sunwell.features.backlog instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.backlog import *  # noqa: F403, F401
