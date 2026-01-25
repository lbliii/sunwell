"""Base RegionWorker class for Naaru workers."""


import asyncio
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from sunwell.naaru.core.bus import MessageBus, MessageType, NaaruMessage, NaaruRegion


class RegionWorker(ABC):
    """Base class for Naaru region workers."""

    def __init__(
        self,
        region: NaaruRegion,
        bus: MessageBus,
        workspace: Path,
        worker_id: int = 0,
    ):
        self.region = region
        self.bus = bus
        self.workspace = workspace
        self.worker_id = worker_id
        self._stop_event = asyncio.Event()
        self.stats = {"tasks_completed": 0, "messages_sent": 0}

    @abstractmethod
    async def process(self) -> None:
        """Main processing loop for this region."""
        pass

    def stop(self) -> None:
        """Signal this worker to stop."""
        self._stop_event.set()

    async def send_message(
        self,
        msg_type: MessageType,
        target: NaaruRegion | None,
        payload: dict,
        priority: int = 5,
    ) -> None:
        """Send a message through the bus."""
        msg = NaaruMessage(
            id=f"{self.region.value}_{uuid.uuid4().hex[:8]}",
            type=msg_type,
            source=self.region,
            target=target,
            payload=payload,
            priority=priority,
        )
        await self.bus.send(msg)
        self.stats["messages_sent"] += 1
