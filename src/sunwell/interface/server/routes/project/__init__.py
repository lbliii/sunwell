"""Project management routes (RFC-113, RFC-117, RFC-132, RFC-133, RFC-141).

This module combines all project-related routers:
- gate: RFC-132 project gate endpoints (validate, list, create, default)
- core: Core operations (get, recent, scan, resume, open, delete, archive, iterate)
- analysis: Analysis endpoints (analyze, monorepo, files, status)
- run: Run-related endpoints (RFC-066)
- extended: Extended operations (memory stats, intelligence, DAG, learnings)
- current: Current project operations (RFC-140)
- lifecycle: RFC-141 lifecycle management (delete modes, rename, move, cleanup)
- slug: RFC-133 Phase 2 URL slug resolution for deep linking
"""

from fastapi import APIRouter

from sunwell.interface.server.routes.project.analysis import router as analysis_router
from sunwell.interface.server.routes.project.core import router as core_router
from sunwell.interface.server.routes.project.current import router as current_router
from sunwell.interface.server.routes.project.extended import router as extended_router
from sunwell.interface.server.routes.project.gate import router as gate_router
from sunwell.interface.server.routes.project.lifecycle import router as lifecycle_router
from sunwell.interface.server.routes.project.run import router as run_router
from sunwell.interface.server.routes.project.slug import router as slug_router

# Main router that combines all project sub-routers
router = APIRouter(prefix="/api", tags=["project"])

# Include all sub-routers
router.include_router(gate_router)
router.include_router(core_router)
router.include_router(analysis_router)
router.include_router(run_router)
router.include_router(extended_router)
router.include_router(current_router)
router.include_router(lifecycle_router)
router.include_router(slug_router)
