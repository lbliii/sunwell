"""Main Chirp application entry point - page convention routing."""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from chirp import App, AppConfig

if TYPE_CHECKING:
    from sunwell.channels import ChannelManager, ChannelRouter
    from sunwell.interface.chirp.services import ConfigService
from chirp.middleware.static import StaticFiles


def _use_chirp_ui(app: App) -> None:
    """Register ChirpUI: filters, static files, OOB regions, page shell."""
    try:
        from chirp import use_chirp_ui
    except ImportError:
        from chirp.ext.chirp_ui import use_chirp_ui

    use_chirp_ui(app, strict=True)


def _default_debug() -> bool:
    """Debug mode: False by default; True when SUNWELL_DEBUG=true/1/yes."""
    val = os.environ.get("SUNWELL_DEBUG", "false").lower()
    return val in ("true", "1", "yes")


def _check_chirp_compat() -> None:
    """Ensure chirp has mount_pages and provide (bengal-chirp >= 0.1.9)."""
    from chirp import App

    app = App()
    missing = []
    if not hasattr(app, "mount_pages"):
        missing.append("mount_pages")
    if not hasattr(app, "provide"):
        missing.append("provide")
    if missing:
        raise RuntimeError(f"Sunwell requires bengal-chirp >= 0.1.9 with {', '.join(missing)}.")


def create_app() -> App:
    """Create and configure the Chirp application.

    Uses filesystem-based page routing: the pages/ directory defines
    URL paths, layout nesting, and context inheritance.
    """
    _check_chirp_compat()

    pkg_dir = Path(__file__).parent
    pages_dir = pkg_dir / "pages"
    static_dir = pkg_dir / "static"

    config = AppConfig(
        template_dir=str(pages_dir),
        debug=_default_debug(),
        alpine=True,
        delegation=True,
    )

    app = App(config=config)
    _use_chirp_ui(app)

    # Provide App for handlers that need tool_events, _tool_registry, etc.
    app.provide(App, lambda: app)

    # Template globals for ChirpUI app shell (sidebar, breadcrumbs)
    _SIDEBAR_LINKS: list[dict[str, str | bool]] = [
        {"id": "home", "label": "Home", "href": "/", "icon": "home"},
        {"id": "chat", "label": "Chat", "href": "/chat", "icon": "chat"},
        {"id": "projects", "label": "Projects", "href": "/projects", "icon": "grid"},
        {"id": "observatory", "label": "Observatory", "href": "/observatory", "icon": "chart"},
        {"id": "activity", "label": "Activity", "href": "/activity", "icon": "run"},
        {"id": "tools", "label": "Tools", "href": "/tools", "icon": "gear"},
        {"id": "memory", "label": "Memory", "href": "/memory", "icon": "cloud"},
        {"id": "library", "label": "Library", "href": "/library", "icon": "list"},
        {"id": "settings", "label": "Settings", "href": "/settings", "icon": "settings"},
    ]

    def _sunwell_sidebar_groups(current_path: str) -> list[dict]:
        cp = current_path or "/"
        items = [
            {
                **link,
                "active": cp == link["href"]
                or (link["href"] != "/" and cp.startswith(link["href"])),
            }
            for link in _SIDEBAR_LINKS
        ]
        return [
            {"id": "nav", "title": "Navigation", "cls": "sunwell-sidebar-group", "links": items}
        ]

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

    # Chat session cookie - set sunwell_chat_session on /chat GET responses
    from sunwell.interface.chirp.middleware.chat_session_cookie import (
        chat_session_cookie_middleware,
    )

    app.add_middleware(chat_session_cookie_middleware)

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
        def get(project_svc: ProjectService) -> dict:
            ...
    """
    from sunwell.channels import ChannelManager, ChannelRouter, make_router_handle
    from sunwell.interface.chirp.services import (
        ChatService,
        ConfigService,
        MemoryService,
        ProjectService,
        SessionService,
        SkillService,
    )

    # Create service instances once (true singletons)
    # This prevents re-importing numpy in Python 3.14 free-threaded build
    _config_service = ConfigService()
    _chat_service = ChatService()
    _project_service = ProjectService()
    _skill_service = SkillService()
    _memory_service = MemoryService()
    _session_service = SessionService()

    _channel_manager = ChannelManager()
    _channel_router = ChannelRouter(
        make_router_handle(_chat_service, _channel_manager),
    )

    # Register service singletons
    app.provide(ConfigService, lambda: _config_service)
    app.provide(ChatService, lambda: _chat_service)
    app.provide(ProjectService, lambda: _project_service)
    app.provide(SkillService, lambda: _skill_service)
    app.provide(MemoryService, lambda: _memory_service)
    app.provide(SessionService, lambda: _session_service)
    app.provide(ChannelManager, lambda: _channel_manager)
    app.provide(ChannelRouter, lambda: _channel_router)

    register_channel_lifecycle(app, _channel_manager, _config_service, _channel_router)


def register_channel_lifecycle(
    app: App,
    channel_manager: ChannelManager,
    config_service: ConfigService,
    channel_router: ChannelRouter,
) -> None:
    """Register app startup/shutdown hooks for ChannelManager."""

    @app.on_startup
    async def _channel_startup() -> None:
        token = config_service.get_telegram_token_for_runtime()
        if token:
            try:
                from sunwell.channels.telegram import TelegramPlugin

                plugin = TelegramPlugin(token=token, router=channel_router)
                channel_manager.register(plugin)
                await channel_manager.start_all(["telegram"])
            except ImportError as e:
                import logging

                logging.getLogger(__name__).warning(
                    "Telegram channel skipped (install sunwell[channels]): %s",
                    e,
                )

    @app.on_shutdown
    async def _channel_shutdown() -> None:
        await channel_manager.stop_all()


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
