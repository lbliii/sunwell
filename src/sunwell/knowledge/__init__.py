"""Knowledge domain - Codebase understanding and analysis.

This domain consolidates all modules that help understand code, projects, and workspaces.

RFC-138: Module Architecture Consolidation
"""

# Re-exports from new locations (Phase 4)
from sunwell.knowledge.analysis import *  # noqa: F403, F401
from sunwell.knowledge.indexing import *  # noqa: F403, F401
from sunwell.knowledge.workspace import *  # noqa: F403, F401
from sunwell.knowledge.project import *  # noqa: F403, F401
from sunwell.knowledge.bootstrap import *  # noqa: F403, F401
from sunwell.knowledge.embedding import *  # noqa: F403, F401
from sunwell.knowledge.navigation import *  # noqa: F403, F401
from sunwell.knowledge.codebase import *  # noqa: F403, F401
from sunwell.knowledge.environment import *  # noqa: F403, F401
from sunwell.knowledge.extraction import *  # noqa: F403, F401
