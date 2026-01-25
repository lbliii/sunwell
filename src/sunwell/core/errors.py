"""DEPRECATED: Use sunwell.foundation.errors instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.core.errors is deprecated. Use sunwell.foundation.errors instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.errors import *  # noqa: F403, F401
