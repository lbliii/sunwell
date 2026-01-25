"""DEPRECATED: Use sunwell.foundation.schema instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.schema is deprecated. Use sunwell.foundation.schema instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.schema import *  # noqa: F403, F401
