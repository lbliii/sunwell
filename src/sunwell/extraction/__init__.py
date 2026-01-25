"""DEPRECATED: Use sunwell.knowledge.extraction instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.extraction is deprecated. Use sunwell.knowledge.extraction instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.extraction import *  # noqa: F403, F401
