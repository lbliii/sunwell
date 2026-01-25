"""DEPRECATED: Use sunwell.foundation.freethreading instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.core.freethreading is deprecated. Use sunwell.foundation.freethreading instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.foundation.freethreading import *  # noqa: F403, F401
