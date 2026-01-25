"""DEPRECATED: Use sunwell.knowledge.project instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.project is deprecated. Use sunwell.knowledge.project instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.project import *  # noqa: F403, F401
