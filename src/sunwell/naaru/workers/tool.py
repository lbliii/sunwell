"""Tool region worker - executes tools on behalf of other regions (RFC-032)."""


import asyncio
import uuid
from collections import deque
from datetime import datetime

from sunwell.naaru.core.bus import MessageType, NaaruRegion
from sunwell.naaru.core.worker import RegionWorker


class ToolRegionWorker(RegionWorker):
    """Executes tools on behalf of other regions (RFC-032).

    This is the bridge between Naaru's cognitive architecture and
    the outside world. All file I/O, commands, and web access
    flow through here.

    Message Types Handled:
    - TOOL_REQUEST: Execute a tool and return result
    - TOOL_BATCH: Execute multiple tools (parallel when possible)
    """

    def __init__(
        self,
        *args,
        tool_executor=None,
        **kwargs,
    ):
        super().__init__(NaaruRegion.TOOLS, *args, **kwargs)
        self.tool_executor = tool_executor
        # Bounded deque to prevent memory leak (keeps last 1000 executions)
        self.execution_log: deque[dict] = deque(maxlen=1000)

    async def process(self) -> None:
        """Process tool execution requests."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.TOOL_REQUEST:
                from sunwell.models.protocol import ToolCall

                tool_call = ToolCall(
                    id=msg.id,
                    name=msg.payload["tool"],
                    arguments=msg.payload["arguments"],
                )

                result = await self.tool_executor.execute(tool_call)

                # Log execution
                self.execution_log.append({
                    "request_id": msg.id,
                    "tool": msg.payload["tool"],
                    "success": result.success,
                    "timestamp": datetime.now().isoformat(),
                })

                await self.send_message(
                    MessageType.TOOL_RESULT,
                    msg.source,  # Reply to requester
                    {
                        "request_id": msg.id,
                        "success": result.success,
                        "output": result.output,
                        "artifacts": [str(p) for p in result.artifacts],
                    },
                )
                self.stats["tools_executed"] = self.stats.get("tools_executed", 0) + 1

            elif msg and msg.type == MessageType.TOOL_BATCH:
                # Execute multiple tools, parallel where possible
                results = await self._execute_batch(msg.payload["tools"])

                await self.send_message(
                    MessageType.TOOL_BATCH_RESULT,
                    msg.source,
                    {"results": results},
                )

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _execute_batch(self, tool_specs: list[dict]) -> list[dict]:
        """Execute multiple tools, parallelizing independent ones."""
        from sunwell.models.protocol import ToolCall

        # For now, execute sequentially (safe default)
        results = []
        for spec in tool_specs:
            tool_call = ToolCall(
                id=spec.get("id", str(uuid.uuid4())),
                name=spec["tool"],
                arguments=spec["arguments"],
            )
            result = await self.tool_executor.execute(tool_call)
            results.append({
                "tool": spec["tool"],
                "success": result.success,
                "output": result.output,
            })
        return results
