"""DEPRECATED: Use sunwell.agent.convergence instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.convergence is deprecated. Use sunwell.agent.convergence instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.convergence import *  # noqa: F403, F401
