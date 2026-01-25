"""DEPRECATED: Use sunwell.features.external.integration instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.integration is deprecated. Use sunwell.features.external.integration instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.features.external.integration import *  # noqa: F403, F401
