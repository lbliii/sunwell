"""Route modules for Sunwell Studio API.

Each module defines an APIRouter for a specific domain:
- agent: Run management, event streaming (RFC-119)
- project: Project operations (RFC-113, RFC-117)
- backlog: Goal backlog management (RFC-114)
- lineage: Artifact lineage tracking (RFC-121)
- recovery: Recovery state management (RFC-125)
- dag: DAG operations (RFC-105)
- coordinator: Parallel worker coordination (RFC-100)
- demo: Demo comparison, evaluation (RFC-095, RFC-098)
- writer: Document writing, workflows (RFC-086)
- memory: Memory, session tracking (RFC-084, RFC-120)
- surface: Surface composition, home (RFC-072, RFC-080)
- misc: Shell, files, health, security, etc.
"""

from sunwell.interface.server.routes.agent import router as agent_router
from sunwell.interface.server.routes.backlog import router as backlog_router
from sunwell.interface.server.routes.coordinator import router as coordinator_router
from sunwell.interface.server.routes.dag import router as dag_router
from sunwell.interface.server.routes.demo import router as demo_router
from sunwell.interface.server.routes.lineage import router as lineage_router
from sunwell.interface.server.routes.memory import router as memory_router
from sunwell.interface.server.routes.misc import router as misc_router
from sunwell.interface.server.routes.project import router as project_router
from sunwell.interface.server.routes.recovery import router as recovery_router
from sunwell.interface.server.routes.surface import router as surface_router
from sunwell.interface.server.routes.writer import router as writer_router

__all__ = [
    "agent_router",
    "backlog_router",
    "coordinator_router",
    "dag_router",
    "demo_router",
    "lineage_router",
    "memory_router",
    "misc_router",
    "project_router",
    "recovery_router",
    "surface_router",
    "writer_router",
]
