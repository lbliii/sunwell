"""Server-Sent Events (SSE) infrastructure for real-time updates.

Replaces WebSocket connections with SSE for simpler architecture:
- Automatic reconnection (browser built-in)
- Event replay via Last-Event-ID header
- HTTP/2 multiplexing
- Firewall friendly
"""

import asyncio
import json
from typing import AsyncGenerator, Any

from chirp import EventStream


class EventBatcher:
    """Batch multiple events into single SSE message to reduce overhead.

    For high-frequency event streams (150+ event types), batching reduces
    network overhead and improves client-side rendering performance.
    """

    def __init__(self, batch_size: int = 10, flush_interval: float = 0.1):
        self.batch: list[dict[str, Any]] = []
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._last_flush = asyncio.get_event_loop().time()

    async def add_event(self, event: dict[str, Any]) -> str | None:
        """Add event to batch. Returns SSE message if batch is full."""
        self.batch.append(event)

        current_time = asyncio.get_event_loop().time()
        should_flush_size = len(self.batch) >= self.batch_size
        should_flush_time = (current_time - self._last_flush) >= self.flush_interval

        if should_flush_size or should_flush_time:
            return self.flush()

        return None

    def flush(self) -> str | None:
        """Flush current batch and return as SSE message."""
        if not self.batch:
            return None

        batch_msg = f"data: {json.dumps(self.batch)}\n\n"
        self.batch = []
        self._last_flush = asyncio.get_event_loop().time()
        return batch_msg


async def create_run_event_stream(
    run_id: str,
    last_event_id: str | None = None,
    batch_events: bool = True,
) -> EventStream:
    """Create SSE stream for agent run events.

    Args:
        run_id: The run identifier to stream events for
        last_event_id: Last received event ID (for reconnection replay)
        batch_events: Whether to batch high-frequency events

    Returns:
        EventStream that yields run events in SSE format

    SSE Format:
        event: <event_type>
        id: <sequence_number>
        data: <json_payload>

    Example:
        @app.route("/events/run/{run_id}")
        async def run_events(request, run_id: str):
            last_id = request.headers.get("Last-Event-ID")
            return await create_run_event_stream(run_id, last_event_id=last_id)
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE-formatted events."""
        start_seq = 0
        if last_event_id:
            try:
                start_seq = int(last_event_id) + 1
            except (ValueError, TypeError):
                pass

        batcher = EventBatcher() if batch_events else None

        # Send connection confirmation
        yield f"event: connected\nid: 0\ndata: {json.dumps({'run_id': run_id, 'replay_from': start_seq})}\n\n"

        # TODO: Integrate with actual run manager
        # This is where we would:
        # 1. Get run from run_manager.get_run(run_id)
        # 2. Replay buffered events from start_seq
        # 3. Subscribe to live events
        # 4. Handle run completion

        # from sunwell.agent.background.manager import get_background_manager
        # manager = get_background_manager()
        # session = manager.get_session(run_id)
        #
        # if not session:
        #     yield f"event: error\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
        #     return
        #
        # # Replay buffered events
        # for event in session.get_events_since(start_seq):
        #     if batcher:
        #         msg = await batcher.add_event(event.to_dict())
        #         if msg:
        #             yield msg
        #     else:
        #         yield f"event: {event.type}\nid: {event.seq}\ndata: {json.dumps(event.data)}\n\n"
        #
        # # Stream live events
        # async for event in session.subscribe_events():
        #     if batcher:
        #         msg = await batcher.add_event(event.to_dict())
        #         if msg:
        #             yield msg
        #     else:
        #         yield f"event: {event.type}\nid: {event.seq}\ndata: {json.dumps(event.data)}\n\n"
        #
        #     if event.type in ("run_complete", "run_failed", "run_cancelled"):
        #         break
        #
        # # Flush any remaining batched events
        # if batcher:
        #     final = batcher.flush()
        #     if final:
        #         yield final

        # Placeholder: emit sample events for development
        sample_events = [
            ("task_start", {"task_id": "t1", "description": "Reading files"}),
            ("model_thinking", {"content": "Analyzing structure..."}),
            ("task_complete", {"task_id": "t1", "status": "done"}),
        ]

        for seq, (event_type, data) in enumerate(sample_events, start=1):
            yield f"event: {event_type}\nid: {seq}\ndata: {json.dumps(data)}\n\n"
            await asyncio.sleep(1.0)

        # Keep connection alive with heartbeat
        while True:
            await asyncio.sleep(30)
            yield ": heartbeat\n\n"

    return EventStream(event_generator())
