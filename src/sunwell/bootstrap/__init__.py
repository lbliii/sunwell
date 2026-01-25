"""DEPRECATED: Use sunwell.knowledge.bootstrap instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.bootstrap is deprecated. Use sunwell.knowledge.bootstrap instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.bootstrap import *  # noqa: F403, F401
