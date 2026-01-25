"""DEPRECATED: Use sunwell.foundation.config instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.config is deprecated. Use sunwell.foundation.config instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.config import *  # noqa: F403, F401
