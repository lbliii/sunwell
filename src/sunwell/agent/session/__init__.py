"""Session management for cross-channel continuity.

Provides portable session state that can be exported and imported
across different channels (CLI, web, mobile).

Usage:
    from sunwell.agent.session import PortableSession
    
    # Export session
    session = PortableSession.from_chat_loop(loop)
    token = session.to_token()
    
    # Import session in another channel
    session = PortableSession.from_token(token)
    loop.restore_from_portable(session)
"""

from sunwell.agent.session.portable import (
    PortableSession,
    SessionToken,
)

__all__ = [
    "PortableSession",
    "SessionToken",
]
