"""DEPRECATED: Use sunwell.interface.generative instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.interface (generative) is deprecated. Use sunwell.interface.generative instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.interface.generative import *  # noqa: F403, F401
