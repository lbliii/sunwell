"""DEPRECATED: Use sunwell.knowledge.codebase instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.intelligence is deprecated. Use sunwell.knowledge.codebase instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.knowledge.codebase import *  # noqa: F403, F401
