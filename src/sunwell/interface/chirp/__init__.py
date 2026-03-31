"""Chirp web interface for Sunwell Studio.

HTML-over-the-wire interface using Chirp framework, Kida templates, htmx, and SSE.
Replaces the previous Svelte + FastAPI dual-stack architecture.

Uses page convention routing: filesystem structure mirrors URL paths.
"""

from chirp import App

__all__ = ["create_app"]


def create_app() -> App:
    """Create and configure the Chirp application."""
    from .main import create_app as _create_app

    return _create_app()
