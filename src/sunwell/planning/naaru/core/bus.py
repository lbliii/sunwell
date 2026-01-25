"""Message Bus - Central communication system for Naaru regions.

Like the brain's corpus callosum, this allows different specialized
regions to communicate and coordinate.
"""


import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NaaruRegion(Enum):
    """Specialized regions of the Naaru architecture."""

    ANALYSIS = "analysis"      # Reading, pattern detection, introspection
    SYNTHESIS = "synthesis"    # Proposal generation, solution creation
    VALIDATION = "validation"  # Safety checks, testing, quality gates
    MEMORY = "memory"          # Simulacrum operations, learning
    EXECUTIVE = "executive"    # Coordination, prioritization
    ROUTING = "routing"        # RFC-020: Intent-aware routing
    TOOLS = "tools"            # RFC-032: Tool execution for agent mode


class MessageType(Enum):
    """Types of messages on the message bus."""

    # Discoveries
    PATTERN_FOUND = "pattern_found"
    OPPORTUNITY_FOUND = "opportunity_found"

    # Requests
    ANALYZE_REQUEST = "analyze_request"
    VALIDATE_REQUEST = "validate_request"
    MEMORIZE_REQUEST = "memorize_request"
    REFINE_REQUEST = "refine_request"  # Resonance: rejected → refine
    ROUTE_REQUEST = "route_request"    # RFC-020: Intent classification request

    # Responses
    ANALYSIS_COMPLETE = "analysis_complete"
    PROPOSAL_READY = "proposal_ready"
    VALIDATION_RESULT = "validation_result"
    ROUTE_COMPLETE = "route_complete"  # RFC-020: Routing decision ready

    # RFC-032: Tool execution messages
    TOOL_REQUEST = "tool_request"           # Execute a tool
    TOOL_RESULT = "tool_result"             # Tool execution result
    TOOL_BATCH = "tool_batch"               # Execute multiple tools
    TOOL_BATCH_RESULT = "tool_batch_result" # Batch execution results
    TASK_READY = "task_ready"               # Task ready for execution
    TASK_COMPLETE = "task_complete"         # Task completed
    TASK_FAILED = "task_failed"             # Task execution failed

    # Control
    ATTENTION_SHIFT = "attention_shift"
    PRIORITY_CHANGE = "priority_change"
    SHUTDOWN = "shutdown"


@dataclass
class NaaruMessage:
    """Message passed through the Naaru message bus."""

    id: str
    type: MessageType
    source: NaaruRegion
    target: NaaruRegion | None  # None = broadcast
    payload: dict[str, Any]
    priority: int = 5  # 1-10, higher = more urgent
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source.value,
            "target": self.target.value if self.target else None,
            "payload": self.payload,
            "priority": self.priority,
        }


class MessageBus:
    """Central communication bus connecting Naaru regions.

    Like the brain's corpus callosum, this allows different specialized
    regions to communicate and coordinate.
    """

    def __init__(self, max_message_log: int = 10000, max_queue_size: int = 1000):
        """Initialize message bus with bounded memory.

        Args:
            max_message_log: Maximum number of messages to keep in log (default: 10000)
            max_queue_size: Maximum size per region queue (default: 1000)
        """
        self._queues: dict[NaaruRegion, asyncio.Queue] = {
            region: asyncio.Queue(maxsize=max_queue_size) for region in NaaruRegion
        }
        # Use deque with maxlen for automatic bounded growth
        self._message_log: deque[NaaruMessage] = deque(maxlen=max_message_log)
        self._lock = asyncio.Lock()

    async def send(self, message: NaaruMessage) -> None:
        """Send a message to a specific region or broadcast.
        
        Raises:
            asyncio.QueueFull: If target queue is full (backpressure)
        """
        async with self._lock:
            # deque with maxlen automatically drops oldest when full
            self._message_log.append(message)

        if message.target:
            await self._queues[message.target].put(message)
        else:
            # Broadcast to all
            for region_queue in self._queues.values():
                await region_queue.put(message)

    async def receive(self, region: NaaruRegion, timeout: float = 0.1) -> NaaruMessage | None:
        """Receive a message for a specific region."""
        try:
            return await asyncio.wait_for(
                self._queues[region].get(),
                timeout=timeout,
            )
        except TimeoutError:
            return None

    def get_stats(self) -> dict:
        """Get communication statistics."""
        by_type = {}
        for msg in self._message_log:
            by_type[msg.type.value] = by_type.get(msg.type.value, 0) + 1

        return {
            "total_messages": len(self._message_log),
            "by_type": by_type,
            "queue_sizes": {
                region.value: self._queues[region].qsize()
                for region in NaaruRegion
            },
        }
