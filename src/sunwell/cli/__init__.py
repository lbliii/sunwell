"""DEPRECATED: Use sunwell.interface.cli instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.cli is deprecated. Use sunwell.interface.cli instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.interface.cli import *  # noqa: F403, F401
