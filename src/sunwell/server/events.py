"""Global event bus for unified CLI/Studio visibility (RFC-119).

Routes events from all sources (CLI, Studio, API) to connected WebSocket
subscribers. Enables Studio Observatory to see CLI-triggered runs.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import WebSocket


@dataclass(frozen=True, slots=True)
class BusEvent:
    """Event wrapper with routing metadata.

    All events flowing through the bus carry:
    - Schema version for future compatibility
    - Source tracking (cli/studio/api)
    - Project filtering support
    """

    v: int  # Schema version (currently 1)
    run_id: str
    type: str
    data: dict[str, Any]
    timestamp: datetime
    source: str  # "cli" | "studio" | "api"
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for WebSocket transmission."""
        return {
            "v": self.v,
            "run_id": self.run_id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "project_id": self.project_id,
        }


@dataclass(slots=True)
class Subscriber:
    """WebSocket subscriber with optional project filter."""

    websocket: WebSocket
    project_filter: str | None = None


class EventBus:
    """Global event bus for all connected clients.

    Thread-safe broadcasting to WebSocket subscribers with:
    - Project-based filtering
    - Connection limits (prevents resource exhaustion)
    - Backpressure handling (slow consumers dropped)

    Usage:
        bus = EventBus()

        # Subscribe (in WebSocket handler)
        await bus.subscribe(websocket, project_filter="proj-123")

        # Broadcast (from run execution)
        await bus.broadcast(BusEvent(...))

        # Cleanup
        await bus.unsubscribe(websocket)
    """

    MAX_SUBSCRIBERS = 100
    SEND_TIMEOUT = 1.0  # Seconds before dropping slow consumer

    def __init__(self) -> None:
        self._subscribers: dict[WebSocket, Subscriber] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        ws: WebSocket,
        project_filter: str | None = None,
    ) -> bool:
        """Add subscriber.

        Args:
            ws: WebSocket connection
            project_filter: Optional project ID to filter events

        Returns:
            True if subscribed, False if at capacity
        """
        async with self._lock:
            if len(self._subscribers) >= self.MAX_SUBSCRIBERS:
                return False
            self._subscribers[ws] = Subscriber(ws, project_filter)
            return True

    async def unsubscribe(self, ws: WebSocket) -> None:
        """Remove subscriber."""
        async with self._lock:
            self._subscribers.pop(ws, None)

    async def broadcast(self, event: BusEvent) -> None:
        """Send event to all matching subscribers.

        Events are filtered by project_id if subscriber has a filter set.
        Slow consumers (>1s to accept) are dropped to prevent backpressure.
        """
        async with self._lock:
            to_remove: list[WebSocket] = []

            for ws, sub in self._subscribers.items():
                # Skip if project filter doesn't match
                if sub.project_filter and event.project_id != sub.project_filter:
                    continue

                try:
                    await asyncio.wait_for(
                        ws.send_json(event.to_dict()),
                        timeout=self.SEND_TIMEOUT,
                    )
                except TimeoutError:
                    to_remove.append(ws)
                except Exception:
                    to_remove.append(ws)

            # Drop slow/dead consumers
            for ws in to_remove:
                self._subscribers.pop(ws, None)

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)
