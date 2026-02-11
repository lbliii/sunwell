"""FastAPI application for Studio UI (RFC-113).

Phase 3 Migration Complete:
- Chirp app mounted at / (handles all HTML pages)
- FastAPI routes under /api/* (core API functionality)
- Svelte codebase removed (migrated to Chirp + Kida + htmx)

Routes are organized into modules under sunwell/server/routes/:
- agent: Run management, event streaming (RFC-119)
- project: Project operations (RFC-113, RFC-117)
- backlog: Goal backlog management (RFC-114)
- lineage: Artifact lineage tracking (RFC-121)
- dag: DAG operations (RFC-105)
- coordinator: Parallel worker coordination (RFC-100)
- demo: Demo comparison, evaluation (RFC-095, RFC-098)
- writer: Document writing, workflows (RFC-086)
- memory: Memory, session tracking (RFC-084, RFC-120)
- surface: Surface composition, home (RFC-072, RFC-080)
- misc: Shell, files, health, security, etc.

TODO: Gradually deprecate /api/* routes that are no longer needed.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sunwell.interface.chirp import create_app as create_chirp_app
from sunwell.interface.server.routes import (
    agent_router,
    backlog_router,
    coordinator_router,
    dag_router,
    demo_router,
    lineage_router,
    memory_router,
    misc_router,
    project_router,
    recovery_router,
    session_router,
    surface_router,
    workspace_router,
    writer_router,
)


def create_app(
    *,
    dev_mode: bool = False,
    enable_chirp: bool = True,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        dev_mode: If True, enable CORS for development.
        enable_chirp: If True, mount Chirp app at / (default: True)

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Sunwell Studio",
        description="AI Agent Development Environment",
        version="0.1.0",
    )

    # Register all route modules under /api prefix for Chirp migration
    # This keeps FastAPI routes separate from Chirp routes
    app.include_router(agent_router, prefix="/api")
    app.include_router(project_router, prefix="/api")
    app.include_router(backlog_router, prefix="/api")
    app.include_router(lineage_router, prefix="/api")
    app.include_router(recovery_router, prefix="/api")
    app.include_router(dag_router, prefix="/api")
    app.include_router(coordinator_router, prefix="/api")
    app.include_router(demo_router, prefix="/api")
    app.include_router(writer_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(surface_router, prefix="/api")
    app.include_router(workspace_router, prefix="/api")
    app.include_router(misc_router, prefix="/api")

    # Mount Chirp app at root - handles all HTML pages with SSR
    if enable_chirp:
        # Mount static files first (before Chirp catches all routes)
        static_dir = Path(__file__).parent / "chirp" / "pages" / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        chirp_app = create_chirp_app()
        app.mount("/", chirp_app)

    # Optional: Enable CORS for development/testing
    if dev_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    return app
