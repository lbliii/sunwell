"""DEPRECATED: Use sunwell.memory.lineage instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.lineage is deprecated. Use sunwell.memory.lineage instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.memory.lineage import *  # noqa: F403, F401
