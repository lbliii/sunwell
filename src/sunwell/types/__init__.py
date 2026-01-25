"""DEPRECATED: Use sunwell.foundation.types instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.types is deprecated. Use sunwell.foundation.types instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.types import *  # noqa: F403, F401
