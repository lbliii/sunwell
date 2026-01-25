"""DEPRECATED: Use sunwell.features.workflow instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.workflow is deprecated. Use sunwell.features.workflow instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.workflow import *  # noqa: F403, F401
