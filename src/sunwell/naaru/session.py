"""Naaru Session Management (RFC-083).

Session-scoped Naaru instances with TTL eviction.
One Naaru instance per user session, not singleton.

Session-scoped benefits:
- Convergence persists across requests in a session
- Isolates users
- Allows stateful conversation
- Avoids singleton global state problems
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sunwell.types.naaru_api import NaaruEvent, ProcessInput


@dataclass
class NaaruSession:
    """Wraps Naaru with session lifecycle management.

    Each session has its own Naaru instance with isolated Convergence.
    Sessions expire after TTL of inactivity.
    """

    session_id: str
    """Unique session identifier."""

    naaru: Any  # NaaruCoordinator - lazy import to avoid circular
    """The Naaru instance for this session."""

    created_at: datetime = field(default_factory=datetime.now)
    """When this session was created."""

    last_accessed: datetime = field(default_factory=datetime.now)
    """Last time this session was used."""

    async def process(self, input: ProcessInput) -> AsyncIterator[NaaruEvent]:
        """Process input through this session's Naaru.

        Updates last_accessed timestamp for TTL tracking.

        Args:
            input: ProcessInput to process

        Yields:
            NaaruEvent stream
        """
        self.last_accessed = datetime.now()
        async for event in self.naaru.process(input):
            yield event

    def is_expired(self, ttl: timedelta) -> bool:
        """Check if this session has expired.

        Args:
            ttl: Time-to-live duration

        Returns:
            True if session hasn't been accessed within TTL
        """
        return datetime.now() - self.last_accessed > ttl


class NaaruSessionManager:
    """Manages session pool with TTL eviction.

    Thread-safe session management for multi-user scenarios.

    Example:
        manager = NaaruSessionManager(max_sessions=100, ttl_hours=4.0)
        session = manager.get_or_create("user-123")
        async for event in session.process(input):
            ...
    """

    def __init__(
        self,
        max_sessions: int = 100,
        ttl_hours: float = 4.0,
        naaru_factory: Any | None = None,
    ) -> None:
        """Initialize session manager.

        Args:
            max_sessions: Maximum concurrent sessions
            ttl_hours: Session TTL in hours
            naaru_factory: Optional factory function to create Naaru instances.
                          If None, uses default NaaruCoordinator creation.
        """
        self._sessions: dict[str, NaaruSession] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = timedelta(hours=ttl_hours)
        self._naaru_factory = naaru_factory

    def get_or_create(self, session_id: str) -> NaaruSession:
        """Get existing session or create new one.

        Thread-safe. Evicts expired sessions if at capacity.

        Args:
            session_id: Unique session identifier

        Returns:
            NaaruSession for this session_id
        """
        with self._lock:
            # Return existing session if found
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.last_accessed = datetime.now()
                return session

            # Evict expired sessions
            self._evict_expired()

            # Evict oldest if at capacity
            if len(self._sessions) >= self._max_sessions:
                self._evict_oldest()

            # Create new session
            naaru = self._create_naaru()
            session = NaaruSession(
                session_id=session_id,
                naaru=naaru,
            )
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> NaaruSession | None:
        """Get session if it exists.

        Args:
            session_id: Session identifier

        Returns:
            NaaruSession or None if not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_accessed = datetime.now()
            return session

    def remove(self, session_id: str) -> bool:
        """Remove a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was found and removed
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear_all(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared
        """
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def get_stats(self) -> dict[str, Any]:
        """Get session manager statistics.

        Returns:
            Dict with session counts and stats
        """
        with self._lock:
            now = datetime.now()
            ages = [(now - s.created_at).total_seconds() for s in self._sessions.values()]

            return {
                "active_sessions": len(self._sessions),
                "max_sessions": self._max_sessions,
                "ttl_hours": self._ttl.total_seconds() / 3600,
                "oldest_session_age_s": max(ages) if ages else 0,
                "newest_session_age_s": min(ages) if ages else 0,
            }

    def _evict_expired(self) -> int:
        """Remove all expired sessions. Must hold lock.

        Returns:
            Number of sessions evicted
        """
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired(self._ttl)
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def _evict_oldest(self) -> None:
        """Remove oldest session. Must hold lock."""
        if not self._sessions:
            return

        oldest_id = min(
            self._sessions.keys(),
            key=lambda k: self._sessions[k].last_accessed,
        )
        del self._sessions[oldest_id]

    def _create_naaru(self) -> Any:
        """Create a new Naaru instance.

        Uses factory if provided, otherwise creates default.
        """
        if self._naaru_factory:
            return self._naaru_factory()

        # Default creation - import here to avoid circular imports
        from pathlib import Path

        from sunwell.naaru.coordinator import Naaru
        from sunwell.types.config import NaaruConfig

        return Naaru(
            workspace=Path.cwd(),
            config=NaaruConfig(),
        )


# =============================================================================
# GLOBAL SESSION MANAGER (optional convenience)
# =============================================================================

_default_manager: NaaruSessionManager | None = None


def get_session_manager() -> NaaruSessionManager:
    """Get or create the default session manager.

    Thread-safe lazy initialization.

    Returns:
        Global NaaruSessionManager instance
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = NaaruSessionManager()
    return _default_manager


def get_session(session_id: str) -> NaaruSession:
    """Convenience function to get or create a session.

    Args:
        session_id: Unique session identifier

    Returns:
        NaaruSession for this session_id
    """
    return get_session_manager().get_or_create(session_id)


__all__ = [
    "NaaruSession",
    "NaaruSessionManager",
    "get_session_manager",
    "get_session",
]
