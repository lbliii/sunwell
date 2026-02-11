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
    static_dir = pages_dir / "static"

    config = AppConfig(
        template_dir=str(pages_dir),  # Templates live alongside routes in pages/
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

    # Register template filters (Task #9)
    register_filters(app)

    # Register service providers (Task #8)
    register_providers(app)

    # Serve static files (CSS, JS) - no-cache in debug mode
    cache_policy = "no-cache" if config.debug else "public, max-age=3600"
    app.add_middleware(
        StaticFiles(directory=static_dir, prefix="/static", cache_control=cache_policy)
    )

    # Mount filesystem-based page routes
    # This scans pages/ and creates routes based on file structure
    app.mount_pages(str(pages_dir))

    return app


def register_filters(app: App) -> None:
    """Register custom template filters for Sunwell domain."""
    import time

    @app.template_filter("format_duration")
    def format_duration(ms: float) -> str:
        """Format milliseconds to human-readable duration."""
        if ms < 1000:
            return f"{int(ms)}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        elif ms < 3600000:
            return f"{ms / 60000:.1f}m"
        else:
            return f"{ms / 3600000:.1f}h"

    @app.template_filter("format_tokens")
    def format_tokens(count: int) -> str:
        """Format token count with k/M suffixes."""
        if count < 1000:
            return str(count)
        elif count < 1_000_000:
            return f"{count / 1000:.1f}k"
        else:
            return f"{count / 1_000_000:.1f}M"

    @app.template_filter("format_filesize")
    def format_filesize(bytes: int) -> str:
        """Format bytes to human-readable file size."""
        if bytes < 1024:
            return f"{bytes}B"
        elif bytes < 1024**2:
            return f"{bytes / 1024:.1f}KB"
        elif bytes < 1024**3:
            return f"{bytes / 1024**2:.1f}MB"
        else:
            return f"{bytes / 1024**3:.1f}GB"

    @app.template_filter("excerpt")
    def excerpt(text: str, length: int = 100) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= length:
            return text
        return text[:length].rsplit(" ", 1)[0] + "..."

    @app.template_filter("relative_time")
    def relative_time(timestamp: float) -> str:
        """Format Unix timestamp as relative time (e.g., '2m ago')."""
        now = time.time()
        diff = now - timestamp
        if diff < 1:
            return "just now"
        elif diff < 60:
            return f"{int(diff)}s ago"
        elif diff < 3600:
            return f"{int(diff / 60)}m ago"
        elif diff < 86400:
            return f"{int(diff / 3600)}h ago"
        else:
            return f"{int(diff / 86400)}d ago"


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
