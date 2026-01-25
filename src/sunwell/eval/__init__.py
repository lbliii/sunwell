"""DEPRECATED: Use sunwell.benchmark.eval instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.eval is deprecated. Use sunwell.benchmark.eval instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.benchmark.eval import *  # noqa: F403, F401
