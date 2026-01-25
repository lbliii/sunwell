"""DEPRECATED: Use sunwell.knowledge.workspace instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.workspace is deprecated. Use sunwell.knowledge.workspace instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.workspace import *  # noqa: F403, F401
