"""Main Chirp application entry point - page convention routing."""

import os
from pathlib import Path

from chirp import App, AppConfig
from chirp.markdown import register_markdown_filter
from chirp.middleware.static import StaticFiles

try:
    from chirp import use_chirp_ui
except ImportError:
    from chirp.ext.chirp_ui import use_chirp_ui


def _default_debug() -> bool:
    """Debug mode: False by default; True when SUNWELL_DEBUG=true/1/yes."""
    val = os.environ.get("SUNWELL_DEBUG", "false").lower()
    return val in ("true", "1", "yes")


def create_app() -> App:
    """Create and configure the Chirp application.

    Uses filesystem-based page routing: the pages/ directory defines
    URL paths, layout nesting, and context inheritance.
    """
    pkg_dir = Path(__file__).parent
    pages_dir = pkg_dir / "pages"
    static_dir = pkg_dir / "static"

    config = AppConfig(
        template_dir=str(pages_dir),
        static_dir=str(static_dir),
        static_url="/static",
        debug=_default_debug(),
        view_transitions=True,
        delegation=True,
        alpine=True,
    )

    app = App(config=config)
    use_chirp_ui(app)

    # Template globals for ChirpUI app shell (sidebar, breadcrumbs)
    _SIDEBAR_LINKS: list[dict[str, str | bool]] = [
        {"id": "home", "label": "Home", "href": "/", "icon": "home"},
        {"id": "projects", "label": "Projects", "href": "/projects", "icon": "folder"},
        {"id": "observatory", "label": "Observatory", "href": "/observatory", "icon": "chart"},
        {"id": "dag", "label": "DAG", "href": "/dag", "icon": "git-branch"},
        {"id": "writer", "label": "Writer", "href": "/writer", "icon": "edit"},
        {"id": "backlog", "label": "Backlog", "href": "/backlog", "icon": "list"},
        {"id": "activity", "label": "Activity", "href": "/activity", "icon": "activity"},
        {"id": "tools", "label": "Tools", "href": "/tools", "icon": "wrench"},
        {"id": "settings", "label": "Settings", "href": "/settings", "icon": "settings"},
    ]

    def _sunwell_sidebar_groups(current_path: str) -> list[dict]:
        cp = current_path or "/"
        items = [
            {**link, "active": cp == link["href"] or (link["href"] != "/" and cp.startswith(link["href"]))}
            for link in _SIDEBAR_LINKS
        ]
        return [{"id": "nav", "title": "Navigation", "cls": "sunwell-sidebar-group", "links": items}]

    def _sunwell_breadcrumb_items(
        breadcrumb_prefix: list,
        breadcrumb_label: str | None,
        current_path: str,
    ) -> list[dict]:
        parts: list[dict] = list(breadcrumb_prefix or [])
        if breadcrumb_label:
            parts.append({"label": breadcrumb_label, "href": current_path or "/"})
        if parts:
            return parts
        # Fallback: derive from path
        path = (current_path or "/").strip("/") or "home"
        segs = path.split("/")
        if not segs or segs[0] == "home":
            return [{"label": "Home", "href": "/"}]
        items = [{"label": "Home", "href": "/"}]
        acc = ""
        for i, seg in enumerate(segs):
            acc += "/" + seg
            label = seg.replace("-", " ").replace("_", " ").title()
            items.append({"label": label, "href": acc})
        return items

    app.template_global("sunwell_sidebar_groups")(_sunwell_sidebar_groups)
    app.template_global("sunwell_breadcrumb_items")(_sunwell_breadcrumb_items)

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

    # Create service instances once (true singletons)
    # This prevents re-importing numpy in Python 3.14 free-threaded build
    _config_service = ConfigService()
    _project_service = ProjectService()
    _skill_service = SkillService()
    _backlog_service = BacklogService()
    _writer_service = WriterService()
    _memory_service = MemoryService()
    _coordinator_service = CoordinatorService()
    _session_service = SessionService()

    # Register service singletons
    app.provide(ConfigService, lambda: _config_service)
    app.provide(ProjectService, lambda: _project_service)
    app.provide(SkillService, lambda: _skill_service)
    app.provide(BacklogService, lambda: _backlog_service)
    app.provide(WriterService, lambda: _writer_service)
    app.provide(MemoryService, lambda: _memory_service)
    app.provide(CoordinatorService, lambda: _coordinator_service)
    app.provide(SessionService, lambda: _session_service)


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
