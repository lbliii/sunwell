"""DEPRECATED: Use sunwell.agent.prefetch instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.prefetch is deprecated. Use sunwell.agent.prefetch instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.prefetch import *  # noqa: F403, F401
