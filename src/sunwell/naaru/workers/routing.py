"""Routing worker - RFC-030 UnifiedRouter for all routing decisions."""


import asyncio
from collections import deque
from datetime import datetime
from typing import Any

from sunwell.naaru.core.bus import MessageType, NaaruRegion
from sunwell.naaru.core.worker import RegionWorker


class CognitiveRoutingWorker(RegionWorker):
    """Routing region - RFC-030 UnifiedRouter for all routing decisions.

    RFC-030: Uses UnifiedRouter for ALL routing decisions in a single inference:
    - intent: What kind of task is this?
    - complexity: How complex is the task?
    - lens: Which lens should handle it?
    - tools: What tools might be needed?
    - mood: User's emotional state
    - expertise: User's skill level
    - confidence: How certain is the routing?
    """

    def __init__(
        self,
        *args,
        router_model=None,
        available_lenses: list[str] | None = None,
        cache_size: int = 1000,
        **kwargs,
    ):
        super().__init__(NaaruRegion.ROUTING, *args, **kwargs)
        self.router_model = router_model
        self.available_lenses = available_lenses or []
        self.cache_size = cache_size
        self._router = None
        # Bounded deque to prevent memory leak (keeps last 5000 routing decisions)
        self._routing_history: deque[dict] = deque(maxlen=5000)

    async def _ensure_router(self) -> None:
        """Lazily initialize the UnifiedRouter."""
        if self._router is None and self.router_model is not None:
            from sunwell.routing import UnifiedRouter

            self._router = UnifiedRouter(
                model=self.router_model,
                cache_size=self.cache_size,
                available_lenses=self.available_lenses,
            )

    async def process(self) -> None:
        """Process routing requests."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.ROUTE_REQUEST:
                task = msg.payload.get("task", "")
                context = msg.payload.get("context")

                routing = await self._route_task(task, context)

                await self.send_message(
                    MessageType.ROUTE_COMPLETE,
                    msg.source,  # Reply to sender
                    {
                        "task": task,
                        "routing": routing,
                    },
                )
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _route_task(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Route a task and return the routing decision.

        RFC-030: Uses UnifiedRouter, falling back to heuristics if unavailable.
        Output format is backward-compatible with legacy consumers.
        """
        await self._ensure_router()

        if self._router is None:
            # Fallback: heuristic routing without LLM
            return self._heuristic_route(task)

        try:
            decision = await self._router.route(task, context)
            result = decision.to_dict()
            # top_k and threshold are now included via to_dict()

            self._routing_history.append({
                "task": task[:100],
                "decision": result,
                "timestamp": datetime.now().isoformat(),
            })
            return result
        except Exception as e:
            return {
                "error": str(e),
                "fallback": self._heuristic_route(task),
            }

    def _heuristic_route(self, task: str) -> dict[str, Any]:
        """Fallback heuristic routing without LLM."""
        task_lower = task.lower()

        # Simple keyword matching
        if any(kw in task_lower for kw in ["security", "vulnerability", "injection"]):
            return {
                "intent": "review",
                "lens": "code-reviewer",
                "focus": ["security", "vulnerability"],
                "top_k": 5,
                "threshold": 0.3,
                "confidence": 0.3,
            }
        elif any(kw in task_lower for kw in ["test", "coverage", "unittest"]):
            return {
                "intent": "code",
                "lens": "team-qa",
                "focus": ["testing", "edge cases"],
                "top_k": 5,
                "threshold": 0.3,
                "confidence": 0.3,
            }
        elif any(kw in task_lower for kw in ["document", "readme", "explain"]):
            return {
                "intent": "explain",
                "lens": "tech-writer",
                "focus": ["clarity", "examples"],
                "top_k": 5,
                "threshold": 0.3,
                "confidence": 0.3,
            }
        else:
            return {
                "intent": "code",
                "lens": "helper",
                "focus": [],
                "top_k": 5,
                "threshold": 0.3,
                "confidence": 0.1,
            }

    async def route_sync(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Synchronous routing for direct use (not via message bus)."""
        return await self._route_task(task, context)
