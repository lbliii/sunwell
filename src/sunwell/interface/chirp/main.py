"""Main Chirp application entry point - page convention routing."""

from __future__ import annotations

import os
from pathlib import Path

from chirp import App, AppConfig
from chirp.middleware.static import StaticFiles

def _use_chirp_ui(app: "App") -> None:
    """Register ChirpUI: filters, static files, OOB regions, page shell.
    Uses chirp.ext.chirp_ui when available; falls back to chirp_ui only when not.
    """
    try:
        from chirp.ext.chirp_ui import use_chirp_ui
        use_chirp_ui(app)
        return
    except (ImportError, AttributeError):
        pass
    # Fallback: PyPI chirp lacks ext; register filters + static only
    import chirp_ui

    chirp_ui.register_filters(app)
    app.add_middleware(StaticFiles(directory=str(chirp_ui.static_path()), prefix="/static"))


def _default_debug() -> bool:
    """Debug mode: False by default; True when SUNWELL_DEBUG=true/1/yes."""
    val = os.environ.get("SUNWELL_DEBUG", "false").lower()
    return val in ("true", "1", "yes")


def _check_chirp_compat() -> None:
    """Ensure chirp has features Sunwell needs (mount_pages, provide).
    PyPI bengal-chirp 0.1.0 lacks these; use a path source for development.
    """
    from chirp import App

    app = App()
    missing = []
    if not hasattr(app, "mount_pages"):
        missing.append("mount_pages")
    if not hasattr(app, "provide"):
        missing.append("provide")
    if missing:
        raise RuntimeError(
            f"Sunwell requires chirp with {', '.join(missing)}. "
            "PyPI bengal-chirp 0.1.0 does not include them. Use a path source:\n"
            '  [tool.uv.sources]\n  bengal-chirp = { path = "../b-stack/chirp", editable = true }'
        )


def create_app() -> App:
    """Create and configure the Chirp application.

    Uses filesystem-based page routing: the pages/ directory defines
    URL paths, layout nesting, and context inheritance.
    """
    _check_chirp_compat()

    pkg_dir = Path(__file__).parent
    pages_dir = pkg_dir / "pages"
    static_dir = pkg_dir / "static"

    # AppConfig: only pass kwargs supported by PyPI chirp 0.1.0
    # (view_transitions, delegation, alpine exist in local chirp only)
    config = AppConfig(
        template_dir=str(pages_dir),
        static_dir=str(static_dir),
        static_url="/static",
        debug=_default_debug(),
    )

    app = App(config=config)
    _use_chirp_ui(app)

    # Provide App for handlers that need tool_events, _tool_registry, etc.
    app.provide(App, lambda: app)

    # Template globals for ChirpUI app shell (sidebar, breadcrumbs)
    _SIDEBAR_LINKS: list[dict[str, str | bool]] = [
        {"id": "home", "label": "Home", "href": "/", "icon": "home"},
        {"id": "projects", "label": "Projects", "href": "/projects", "icon": "folder"},
        {"id": "observatory", "label": "Observatory", "href": "/observatory", "icon": "chart"},
        {"id": "activity", "label": "Activity", "href": "/activity", "icon": "activity"},
        {"id": "tools", "label": "Tools", "href": "/tools", "icon": "wrench"},
        {"id": "memory", "label": "Memory", "href": "/memory", "icon": "database"},
        {"id": "library", "label": "Library", "href": "/library", "icon": "book"},
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
    # Optional: requires chirp[markdown] (patitas) to be installed
    try:
        from chirp.markdown import register_markdown_filter
        register_markdown_filter(app)
    except Exception:
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
        MemoryService,
        ProjectService,
        SessionService,
        SkillService,
    )

    # Create service instances once (true singletons)
    # This prevents re-importing numpy in Python 3.14 free-threaded build
    _config_service = ConfigService()
    _project_service = ProjectService()
    _skill_service = SkillService()
    _memory_service = MemoryService()
    _session_service = SessionService()

    # Register service singletons
    app.provide(ConfigService, lambda: _config_service)
    app.provide(ProjectService, lambda: _project_service)
    app.provide(SkillService, lambda: _skill_service)
    app.provide(MemoryService, lambda: _memory_service)
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
