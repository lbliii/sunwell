"""DEPRECATED: Use sunwell.knowledge.environment instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.environment is deprecated. Use sunwell.knowledge.environment instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.environment import *  # noqa: F403, F401
