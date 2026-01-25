"""DEPRECATED: Use sunwell.planning.lens instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.lens is deprecated. Use sunwell.planning.lens instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.planning.lens import *  # noqa: F403, F401
