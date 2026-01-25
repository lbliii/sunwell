"""DEPRECATED: Use sunwell.planning.skills instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.skills is deprecated. Use sunwell.planning.skills instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.planning.skills import *  # noqa: F403, F401
