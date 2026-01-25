"""DEPRECATED: Use sunwell.foundation.identity instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.core.identity is deprecated. Use sunwell.foundation.identity instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.identity import *  # noqa: F403, F401
