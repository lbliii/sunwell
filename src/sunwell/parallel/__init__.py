"""DEPRECATED: Use sunwell.agent.parallel instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.parallel is deprecated. Use sunwell.agent.parallel instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.parallel import *  # noqa: F403, F401
