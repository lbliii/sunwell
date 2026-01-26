"""HTTP server command for Studio UI (RFC-113).

Usage:
    sunwell serve              # Start on localhost:8080
    sunwell serve --open       # Start and open browser
    sunwell serve --dev        # API only, for Vite dev server
"""

import webbrowser
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", default=8080, help="Port to listen on")
@click.option("--host", default="127.0.0.1", help="Host to bind to (127.0.0.1 for local only)")
@click.option("--open", "open_browser", is_flag=True, help="Open browser automatically")
@click.option("--dev", is_flag=True, help="Development mode (CORS enabled for Vite on :5173)")
def serve(port: int, host: str, open_browser: bool, dev: bool) -> None:
    """Start the Sunwell Studio HTTP server.

    In production mode (default), serves the Svelte UI from the same origin.
    In development mode (--dev), enables CORS for Vite dev server on :5173.

    \b
    Examples:
        sunwell serve              # Start on localhost:8080
        sunwell serve --open       # Start and open browser
        sunwell serve --dev        # API only, for Vite dev server
        sunwell serve --port 3000  # Custom port
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error: uvicorn not installed[/red]")
        console.print("Run: uv sync")
        raise SystemExit(1) from None

    from sunwell.interface.server import create_app

    # Find static directory (Svelte build)
    static_dir = _find_static_dir()

    if not dev and not static_dir:
        console.print("[yellow]Warning: No static files found[/yellow]")
        console.print("Run 'cd studio && npm run build' first, or use --dev mode")
        dev = True  # Fall back to dev mode

    app = create_app(dev_mode=dev, static_dir=static_dir)

    url = f"http://{host}:{port}"

    console.print()
    console.print("[bold green]🌐 Sunwell Studio[/bold green]")
    console.print(f"   URL: {url}")

    if dev:
        console.print("   Mode: [yellow]Development[/yellow] (CORS enabled)")
        console.print("   Vite: http://localhost:5173 (run: cd studio && npm run dev)")
    else:
        console.print("   Mode: [green]Production[/green] (serving static UI)")

    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    if open_browser and not dev:
        webbrowser.open(url)

    uvicorn.run(app, host=host, port=port, log_level="info")


def _find_static_dir() -> Path | None:
    """Find the Svelte build directory.

    Checks several possible locations:
    1. ./studio/dist (Vite default)
    2. ./studio/build (legacy)
    3. ~/.sunwell/studio (installed)
    4. Package resources (pip installed)
    """
    # Development: relative to cwd (Vite outputs to dist/)
    dev_path = Path.cwd() / "studio" / "dist"
    if dev_path.exists() and (dev_path / "index.html").exists():
        return dev_path

    # Legacy: build folder
    build_path = Path.cwd() / "studio" / "build"
    if build_path.exists() and (build_path / "index.html").exists():
        return build_path

    # Check relative to this file (source tree)
    src_path = Path(__file__).parent.parent.parent.parent.parent / "studio" / "dist"
    if src_path.exists() and (src_path / "index.html").exists():
        return src_path

    # Installed: ~/.sunwell/studio
    home_path = Path.home() / ".sunwell" / "studio"
    if home_path.exists() and (home_path / "index.html").exists():
        return home_path

    return None
