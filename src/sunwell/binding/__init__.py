"""DEPRECATED: Use sunwell.foundation.binding instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.binding is deprecated. Use sunwell.foundation.binding instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.binding import *  # noqa: F403, F401
