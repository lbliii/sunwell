"""Analysis worker - reads code, finds patterns, introspection."""

from __future__ import annotations

import asyncio
import json

from sunwell.mirror import MirrorHandler
from sunwell.naaru.core.bus import MessageType, NaaruRegion
from sunwell.naaru.core.worker import RegionWorker


class AnalysisWorker(RegionWorker):
    """Analysis region - reads code, finds patterns, introspection."""

    def __init__(self, *args, **kwargs):
        super().__init__(NaaruRegion.ANALYSIS, *args, **kwargs)
        self.mirror = MirrorHandler(
            workspace=self.workspace,
            storage_path=self.workspace / ".sunwell" / "naaru" / f"analysis_{self.worker_id}",
        )

    async def process(self) -> None:
        """Analyze code and report findings."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.ANALYZE_REQUEST:
                target = msg.payload.get("target")
                result = await self._analyze(target)

                await self.send_message(
                    MessageType.ANALYSIS_COMPLETE,
                    NaaruRegion.SYNTHESIS,
                    {"target": target, "findings": result},
                )
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _analyze(self, target: str) -> dict:
        """Analyze a target module."""
        try:
            result = await self.mirror.handle("introspect_source", {"module": target})
            return json.loads(result)
        except Exception as e:
            return {"error": str(e)}
