"""Routing worker - RFC-030 UnifiedRouter for all routing decisions."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime

from sunwell.naaru.core.bus import MessageType, NaaruRegion
from sunwell.naaru.core.worker import RegionWorker


class CognitiveRoutingWorker(RegionWorker):
    """Routing region - RFC-030 UnifiedRouter for all routing decisions.

    RFC-030 MIGRATION: Now uses UnifiedRouter instead of CognitiveRouter.
    The UnifiedRouter handles ALL routing decisions in a single inference:
    - intent: What kind of task is this?
    - complexity: How complex is the task?
    - lens: Which lens should handle it?
    - tools: What tools might be needed?
    - mood: User's emotional state
    - expertise: User's skill level
    - confidence: How certain is the routing?

    Backward Compatibility:
        The output format is compatible with legacy consumers via
        LegacyRoutingAdapter. Existing code using the routing dict
        will continue to work.
    """

    def __init__(
        self,
        *args,
        router_model=None,
        available_lenses: list[str] | None = None,
        use_unified_router: bool = True,  # RFC-030: Default to new router
        cache_size: int = 1000,
        **kwargs,
    ):
        super().__init__(NaaruRegion.ROUTING, *args, **kwargs)
        self.router_model = router_model
        self.available_lenses = available_lenses or []
        self.use_unified_router = use_unified_router
        self.cache_size = cache_size
        self._router = None
        self._legacy_adapter = None
        # Bounded deque to prevent memory leak (keeps last 5000 routing decisions)
        self._routing_history: deque[dict] = deque(maxlen=5000)

    async def _ensure_router(self):
        """Lazily initialize the router (UnifiedRouter or CognitiveRouter)."""
        if self._router is None and self.router_model is not None:
            if self.use_unified_router:
                # RFC-030: Use UnifiedRouter
                from sunwell.routing import LegacyRoutingAdapter, UnifiedRouter
                self._router = UnifiedRouter(
                    model=self.router_model,
                    cache_size=self.cache_size,
                    available_lenses=self.available_lenses,
                )
                self._legacy_adapter = LegacyRoutingAdapter(self._router)
            else:
                # Legacy: Use CognitiveRouter (deprecated)
                from sunwell.routing import CognitiveRouter
                self._router = CognitiveRouter(
                    router_model=self.router_model,
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

    async def _route_task(self, task: str, context: dict | None = None) -> dict:
        """Route a task and return the routing decision.

        RFC-030: Uses UnifiedRouter by default, falling back to heuristics.
        Output format is backward-compatible with legacy consumers.
        """
        await self._ensure_router()

        if self._router is None:
            # Fallback: heuristic routing without LLM
            return self._heuristic_route(task)

        try:
            if self.use_unified_router and self._legacy_adapter:
                # RFC-030: Use UnifiedRouter with legacy adapter
                decision = await self._router.route(task, context)
                # Include both unified and legacy format
                result = decision.to_dict()
                # Add legacy-compatible fields
                legacy = await self._legacy_adapter.to_cognitive_router_decision(task, context)
                result.update({
                    "top_k": legacy["top_k"],
                    "threshold": legacy["threshold"],
                })
            else:
                # Legacy CognitiveRouter path
                decision = await self._router.route(task, context)
                result = decision.to_dict()

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

    def _heuristic_route(self, task: str) -> dict:
        """Fallback heuristic routing without LLM."""
        task_lower = task.lower()

        # Simple keyword matching
        if any(kw in task_lower for kw in ["security", "vulnerability", "injection"]):
            return {
                "intent": "code_review",
                "lens": "code-reviewer",
                "focus": ["security", "vulnerability"],
                "top_k": 5,
                "confidence": 0.3,
            }
        elif any(kw in task_lower for kw in ["test", "coverage", "unittest"]):
            return {
                "intent": "testing",
                "lens": "team-qa",
                "focus": ["testing", "edge cases"],
                "top_k": 5,
                "confidence": 0.3,
            }
        elif any(kw in task_lower for kw in ["document", "readme", "explain"]):
            return {
                "intent": "documentation",
                "lens": "tech-writer",
                "focus": ["clarity", "examples"],
                "top_k": 5,
                "confidence": 0.3,
            }
        else:
            return {
                "intent": "unknown",
                "lens": "helper",
                "focus": [],
                "top_k": 5,
                "confidence": 0.1,
            }

    async def route_sync(self, task: str, context: dict | None = None) -> dict:
        """Synchronous routing for direct use (not via message bus)."""
        return await self._route_task(task, context)
