"""HTTP server command for Studio UI (RFC-113).

Migration Complete: Pure Chirp + Pounce stack (FastAPI/uvicorn/Node.js removed).

Usage:
    sunwell serve              # Start on localhost:8080
    sunwell serve --open       # Start and open browser
    sunwell serve --port 3000  # Custom port
"""

import webbrowser

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", default=8080, help="Port to listen on")
@click.option("--host", default="127.0.0.1", help="Host to bind to (127.0.0.1 for local only)")
@click.option("--open", "open_browser", is_flag=True, help="Open browser automatically")
def serve(port: int, host: str, open_browser: bool) -> None:
    """Start the Sunwell Studio HTTP server.

    Serves Chirp pages with server-side rendering (SSR) using Pounce ASGI server.
    No FastAPI, no uvicorn, no Node.js - pure Python stack.

    \b
    Examples:
        sunwell serve              # Start on localhost:8080
        sunwell serve --open       # Start and open browser
        sunwell serve --port 3000  # Custom port
    """
    from sunwell.interface.chirp import create_app

    # Create Chirp app (uses Pounce internally via app.run())
    app = create_app()

    url = f"http://{host}:{port}"

    console.print()
    console.print("[bold green]🌐 Sunwell Studio[/bold green]")
    console.print(f"   URL: {url}")
    console.print("   Server: [cyan]Pounce[/cyan] (Chirp's ASGI server)")
    console.print("   Stack: [cyan]Python-only[/cyan] (Chirp + Kida + htmx)")
    console.print("   Mode: [green]Development[/green] (auto-reload enabled)")

    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    if open_browser:
        webbrowser.open(url)

    # Chirp's app.run() uses Pounce internally
    app.run(host=host, port=port)
