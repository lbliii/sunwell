"""Main Chirp application entry point - page convention routing."""

from pathlib import Path

from chirp import App, AppConfig
from chirp.markdown import register_markdown_filter
from chirp.middleware.static import StaticFiles


def create_app() -> App:
    """Create and configure the Chirp application.

    Uses filesystem-based page routing: the pages/ directory defines
    URL paths, layout nesting, and context inheritance.
    """
    # Resolve paths relative to this file
    pkg_dir = Path(__file__).parent
    pages_dir = pkg_dir / "pages"
    components_dir = pkg_dir / "components"
    static_dir = pkg_dir / "static"

    config = AppConfig(
        template_dir=str(pages_dir),  # Pages for routing
        component_dirs=(str(components_dir),),  # Component library (separate directory)
        static_dir=str(static_dir),
        static_url="/static",
        debug=True,  # Enable debug mode during development
        view_transitions=True,  # Enable View Transitions API for smooth navigation
    )

    app = App(config=config)

    # Register markdown filter - enables {{ content | markdown }} in templates
    # Optional: requires chirp[markdown] to be installed
    try:
        register_markdown_filter(app)
    except Exception:
        # Markdown support not available (missing patitas dependency)
        pass

    # Register custom template filters from lib/
    from sunwell.interface.chirp.lib.filters import register_all_filters
    register_all_filters(app)

    # Register service providers
    register_providers(app)

    # Register MCP tools - exposes Sunwell capabilities via /mcp endpoint
    register_mcp_tools(app)

    # Serve static files (CSS, JS) - no-cache in debug mode
    cache_policy = "no-cache" if config.debug else "public, max-age=3600"
    app.add_middleware(
        StaticFiles(directory=static_dir, prefix="/static", cache_control=cache_policy)
    )

    # Mount filesystem-based page routes
    # This scans pages/ and creates routes based on file structure
    app.mount_pages(str(pages_dir))

    return app


def register_providers(app: App) -> None:
    """Register service providers for dependency injection.

    Handlers can request services via type annotations:
        def get(project_svc: ProjectService) -> Page:
            ...
    """
    from sunwell.interface.chirp.services import (
        ConfigService,
        ProjectService,
        SkillService,
        BacklogService,
        WriterService,
        MemoryService,
        CoordinatorService,
        SessionService,
    )

    # Register service singletons
    app.provide(ConfigService, lambda: ConfigService())
    app.provide(ProjectService, lambda: ProjectService())
    app.provide(SkillService, lambda: SkillService())
    app.provide(BacklogService, lambda: BacklogService())
    app.provide(WriterService, lambda: WriterService())
    app.provide(MemoryService, lambda: MemoryService())
    app.provide(CoordinatorService, lambda: CoordinatorService())
    app.provide(SessionService, lambda: SessionService())


def register_mcp_tools(app: App) -> None:
    """Register MCP tools with Chirp's built-in MCP server.

    This exposes Sunwell capabilities via the /mcp endpoint, enabling:
    - AI agents to call tools via JSON-RPC (Model Context Protocol)
    - Web UI to call the same functions (unified interface)
    - Real-time activity monitoring via app.tool_events

    Tools are registered using @app.tool() decorator, which:
    - Automatically generates JSON Schema from type annotations
    - Routes JSON-RPC calls to Python functions
    - Emits ToolCallEvent for monitoring

    See: docs/chirp-mcp-integration.md for architecture details
    """
    from sunwell.interface.chirp.tools import register_all_tools

    register_all_tools(app)
