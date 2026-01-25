"""DEPRECATED: Use sunwell.memory.session instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.session is deprecated. Use sunwell.memory.session instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.memory.session import *  # noqa: F403, F401
