"""DEPRECATED: Use sunwell.agent.execution instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.execution is deprecated. Use sunwell.agent.execution instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.execution import *  # noqa: F403, F401
