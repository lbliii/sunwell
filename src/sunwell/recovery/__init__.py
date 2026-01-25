"""DEPRECATED: Use sunwell.agent.recovery instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.recovery is deprecated. Use sunwell.agent.recovery instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.recovery import *  # noqa: F403, F401
