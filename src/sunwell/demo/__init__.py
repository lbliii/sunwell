"""DEPRECATED: Use sunwell.benchmark.demo instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.demo is deprecated. Use sunwell.benchmark.demo instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.benchmark.demo import *  # noqa: F403, F401
