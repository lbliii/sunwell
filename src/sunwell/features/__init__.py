"""Features domain - Opt-in specialized capabilities.

This domain consolidates optional features that don't fit in core domains.

RFC-138: Module Architecture Consolidation
"""

# Re-exports from new locations (Phase 10)
from sunwell.features.vortex import *  # noqa: F403, F401
from sunwell.features.mirror import *  # noqa: F403, F401
from sunwell.features.fount import *  # noqa: F403, F401
from sunwell.features.team import *  # noqa: F403, F401
from sunwell.features.external import *  # noqa: F403, F401
from sunwell.features.backlog import *  # noqa: F403, F401
from sunwell.features.autonomous import *  # noqa: F403, F401
from sunwell.features.workflow import *  # noqa: F403, F401
from sunwell.features.mirror.self import *  # noqa: F403, F401
from sunwell.features.external.integration import *  # noqa: F403, F401
