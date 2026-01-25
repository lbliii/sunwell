"""DEPRECATED: Use sunwell.knowledge.analysis instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.analysis is deprecated. Use sunwell.knowledge.analysis instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.analysis import *  # noqa: F403, F401
