"""Background task execution system.

Enables long-running tasks to execute asynchronously while the user
continues working, with notifications on completion.

Usage:
    from sunwell.agent.background import BackgroundSession, BackgroundManager
    
    manager = BackgroundManager(workspace)
    session = await manager.spawn(goal, model, tool_executor)
    
    # Later, check status
    status = manager.get_session(session.session_id)
"""

from sunwell.agent.background.manager import BackgroundManager
from sunwell.agent.background.session import (
    BackgroundSession,
    SessionStatus,
)

__all__ = [
    "BackgroundManager",
    "BackgroundSession",
    "SessionStatus",
]
