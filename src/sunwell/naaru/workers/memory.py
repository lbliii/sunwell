"""Memory worker - simulacrum operations, learning persistence."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime

from sunwell.naaru.core.bus import MessageType, NaaruRegion
from sunwell.naaru.core.worker import RegionWorker


class MemoryWorker(RegionWorker):
    """Memory region - simulacrum operations, learning persistence."""

    def __init__(self, *args, **kwargs):
        super().__init__(NaaruRegion.MEMORY, *args, **kwargs)
        # Bounded deque to prevent memory leak (keeps last 5000 learnings)
        self.learnings: deque[dict] = deque(maxlen=5000)

    async def process(self) -> None:
        """Handle memory operations."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.MEMORIZE_REQUEST:
                learning = msg.payload
                self.learnings.append({
                    "content": learning,
                    "timestamp": datetime.now().isoformat(),
                    "source": msg.source.value,
                })
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.PATTERN_FOUND:
                self.learnings.append({
                    "type": "pattern",
                    "content": msg.payload,
                    "timestamp": datetime.now().isoformat(),
                })

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)
