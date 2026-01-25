"""DEPRECATED: Use sunwell.agent.chat instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.chat is deprecated. Use sunwell.agent.chat instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.agent.chat import *  # noqa: F403, F401
