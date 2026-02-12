"""Helper for spawning background tasks from synchronous Chirp handlers.

Chirp handlers are synchronous, but BackgroundManager.spawn() is async.
This module provides utilities to properly spawn background tasks without
blocking the request handler.
"""

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.background.manager import BackgroundManager
    from sunwell.agent.background.session import BackgroundSession
    from sunwell.memory import PersistentMemory
    from sunwell.models import ModelProtocol
    from sunwell.tools.execution import ToolExecutor


# Global event loop for background tasks
_background_loop: asyncio.AbstractEventLoop | None = None
_background_thread: threading.Thread | None = None
_loop_lock = threading.Lock()


def _start_background_loop() -> asyncio.AbstractEventLoop:
    """Start a persistent event loop in a background thread.

    Returns:
        The running event loop
    """
    global _background_loop, _background_thread

    with _loop_lock:
        if _background_loop is not None:
            return _background_loop

        # Create new event loop
        loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        # Start thread
        thread = threading.Thread(target=run_loop, daemon=True, name="chirp-background")
        thread.start()

        _background_loop = loop
        _background_thread = thread

        return loop


def get_background_loop() -> asyncio.AbstractEventLoop:
    """Get the background event loop, creating it if needed.

    Returns:
        The background event loop
    """
    if _background_loop is None:
        return _start_background_loop()
    return _background_loop


def spawn_background_session(
    manager: "BackgroundManager",
    goal: str,
    model: "ModelProtocol",
    tool_executor: "ToolExecutor",
    memory: "PersistentMemory | None" = None,
) -> "BackgroundSession":
    """Spawn a background agent session from a synchronous context.

    This function properly handles the async spawning by scheduling it
    on a persistent background event loop.

    Args:
        manager: BackgroundManager instance
        goal: Goal description for the agent
        model: Model to use for generation
        tool_executor: Tool executor for file operations
        memory: Optional persistent memory

    Returns:
        BackgroundSession that will run in the background
    """
    loop = get_background_loop()

    # Schedule spawn on background loop and wait for session object
    future = asyncio.run_coroutine_threadsafe(
        manager.spawn(
            goal=goal,
            model=model,
            tool_executor=tool_executor,
            memory=memory,
        ),
        loop,
    )

    # Wait for spawn to return the session object (this is fast)
    # The actual execution happens asynchronously in the background
    session = future.result(timeout=5.0)

    return session
