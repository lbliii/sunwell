"""Executive worker - coordination, prioritization, attention."""


import asyncio
from collections import deque
from collections.abc import Callable

from sunwell.planning.naaru.core.bus import MessageType, NaaruRegion
from sunwell.planning.naaru.core.worker import RegionWorker


class ExecutiveWorker(RegionWorker):
    """Executive region - coordination, prioritization, attention."""

    def __init__(self, *args, on_output: Callable = None, **kwargs):
        super().__init__(NaaruRegion.EXECUTIVE, *args, **kwargs)
        self.on_output = on_output
        # Bounded deque to prevent memory leak (keeps last 1000 proposals)
        self.completed_proposals: deque[dict] = deque(maxlen=1000)
        self.attention_focus: str | None = None

    async def process(self) -> None:
        """Coordinate other regions and track progress."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.VALIDATION_RESULT:
                result = msg.payload
                self.completed_proposals.append(result)

                if self.on_output:
                    status = "✅" if result["valid"] else "❌"
                    self.on_output(f"{status} {result.get('proposal_id', '?')}")

                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.ATTENTION_SHIFT:
                self.attention_focus = msg.payload.get("focus")

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)
