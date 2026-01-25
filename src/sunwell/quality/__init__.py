"""Quality domain - Verification, guardrails, security, confidence scoring, weakness detection.

This domain consolidates all quality assurance modules.

RFC-138: Module Architecture Consolidation
"""

# Re-exports from new locations (Phase 8)
from sunwell.quality.verification import *  # noqa: F403, F401
from sunwell.quality.guardrails import *  # noqa: F403, F401
from sunwell.quality.security import *  # noqa: F403, F401
from sunwell.quality.confidence import *  # noqa: F403, F401
from sunwell.quality.weakness import *  # noqa: F403, F401
