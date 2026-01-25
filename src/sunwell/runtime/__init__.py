"""DEPRECATED: Use sunwell.agent.runtime instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.runtime is deprecated. Use sunwell.agent.runtime instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.runtime import *  # noqa: F403, F401
