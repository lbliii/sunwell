"""DEPRECATED: Use sunwell.agent.incremental instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.incremental is deprecated. Use sunwell.agent.incremental instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.incremental import *  # noqa: F403, F401
