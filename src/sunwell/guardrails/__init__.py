"""DEPRECATED: Use sunwell.quality.guardrails instead.

RFC-138: Module Architecture Consolidation
"""

import warnings

warnings.warn(
    "sunwell.guardrails is deprecated. Use sunwell.quality.guardrails instead.",
    DeprecationWarning,
    stacklevel=2,
)

from sunwell.quality.guardrails import *  # noqa: F403, F401
