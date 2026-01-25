"""DEPRECATED: Use sunwell.interface.server instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.server is deprecated. Use sunwell.interface.server instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.interface.server import *  # noqa: F403, F401
