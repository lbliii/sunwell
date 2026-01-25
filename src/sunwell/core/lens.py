"""DEPRECATED: Use sunwell.foundation.core.lens instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.core.lens is deprecated. Use sunwell.foundation.core.lens instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.core.lens import *  # noqa: F403, F401
