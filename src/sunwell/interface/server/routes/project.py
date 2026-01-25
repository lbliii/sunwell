"""Project management routes (RFC-113, RFC-117, RFC-132).

This module combines all project-related routers:
- project_gate: RFC-132 project gate endpoints (validate, list, create, default)
- project_core: Core operations (get, recent, scan, resume, open, delete, archive, iterate)
- project_analysis: Analysis endpoints (analyze, monorepo, files, status)
- project_run: Run-related endpoints (RFC-066)
- project_extended: Extended operations (memory stats, intelligence, DAG, learnings)
- project_current: Current project operations (RFC-140)
"""

from fastapi import APIRouter

from sunwell.interface.server.routes.project_analysis import router as analysis_router
from sunwell.interface.server.routes.project_core import router as core_router
from sunwell.interface.server.routes.project_current import router as current_router
from sunwell.interface.server.routes.project_extended import router as extended_router
from sunwell.interface.server.routes.project_gate import router as gate_router
from sunwell.interface.server.routes.project_run import router as run_router

# Main router that combines all project sub-routers
router = APIRouter(prefix="/api", tags=["project"])

# Include all sub-routers
router.include_router(gate_router)
router.include_router(core_router)
router.include_router(analysis_router)
router.include_router(run_router)
router.include_router(extended_router)
router.include_router(current_router)
