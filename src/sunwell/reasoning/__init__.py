"""DEPRECATED: Use sunwell.planning.reasoning instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.reasoning is deprecated. Use sunwell.planning.reasoning instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.planning.reasoning import *  # noqa: F403, F401
