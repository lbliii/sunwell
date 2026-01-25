"""HTTP/WebSocket server for Studio UI (RFC-113).

This replaces the Rust/Tauri bridge with direct Python-to-browser communication.

Usage:
    sunwell serve --open

Architecture:
    Browser (Svelte) ←WebSocket→ Python (FastAPI) → Agent

Benefits:
    - Single source of truth for events (Python only)
    - No subprocess spawning, no stdout parsing
    - Auto-reconnect with event replay
    - 12,932 fewer lines of code
"""

from sunwell.interface.generative.server.main import create_app
from sunwell.interface.generative.server.workspace_manager import WorkspaceManager, get_workspace_manager

__all__ = ["create_app", "WorkspaceManager", "get_workspace_manager"]
