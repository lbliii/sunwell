"""FastAPI application for Studio UI (RFC-113).

This is the HTTP/WebSocket server that replaces the Rust/Tauri bridge.
All Studio communication goes through here.

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
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
    surface_router,
    writer_router,
)


def create_app(*, dev_mode: bool = False, static_dir: Path | None = None) -> FastAPI:
    """Create FastAPI application.

    Args:
        dev_mode: If True, enable CORS for Vite dev server on :5173.
                  If False, serve static Svelte build.
        static_dir: Path to static files (Svelte build). If None, uses default.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Sunwell Studio",
        description="AI Agent Development Environment",
        version="0.1.0",
    )

    # Register all route modules
    app.include_router(agent_router)
    app.include_router(project_router)
    app.include_router(backlog_router)
    app.include_router(lineage_router)
    app.include_router(recovery_router)
    app.include_router(dag_router)
    app.include_router(coordinator_router)
    app.include_router(demo_router)
    app.include_router(writer_router)
    app.include_router(memory_router)
    app.include_router(surface_router)
    app.include_router(misc_router)

    if dev_mode:
        # Development: CORS for Vite dev server (port 1420 is Tauri default)
        # Also allow localhost variants for flexibility
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:1420",
                "http://127.0.0.1:1420",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Production: Still enable CORS for localhost (common in dev/prod hybrid setups)
        # This allows frontend dev server to work even without --dev flag
        import os
        if os.getenv("SUNWELL_ENABLE_CORS", "").lower() in ("1", "true", "yes"):
            app.add_middleware(
                CORSMiddleware,
                allow_origins=[
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                ],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        # Production: Serve Svelte static build
        if static_dir and static_dir.exists():
            _mount_static(app, static_dir)

    return app


def _mount_static(app: FastAPI, static_dir: Path) -> None:
    """Mount static files for production mode."""

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    # Mount static assets
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
