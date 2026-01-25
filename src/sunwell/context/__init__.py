"""DEPRECATED: Use sunwell.agent.context instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.context is deprecated. Use sunwell.agent.context instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.context import *  # noqa: F403, F401
