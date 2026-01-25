"""DEPRECATED: Use sunwell.memory.simulacrum instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.simulacrum is deprecated. Use sunwell.memory.simulacrum instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.memory.simulacrum import *  # noqa: F403, F401
