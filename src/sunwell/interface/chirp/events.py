"""Server-Sent Events (SSE) infrastructure for real-time updates.

Deprecated: No callers; create_run_event_stream was used by removed system/stream
and events/run endpoints. Kept for future run-specific SSE (POST→fragment pattern).

Replaces WebSocket connections with SSE for simpler architecture:
- Automatic reconnection (browser built-in)
- Event replay via Last-Event-ID header
- HTTP/2 multiplexing
- Firewall friendly
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any

from chirp import EventStream

from sunwell.planning.naaru.session_store import SessionStore


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

    async def event_generator() -> AsyncGenerator[str]:
        """Generate SSE-formatted events."""
        start_seq = 0
        if last_event_id:
            with suppress(ValueError, TypeError):
                start_seq = int(last_event_id) + 1

        batcher = EventBatcher() if batch_events else None

        # Send connection confirmation
        connected = json.dumps({"run_id": run_id, "replay_from": start_seq})
        yield f"event: connected\nid: 0\ndata: {connected}\n\n"

        store = SessionStore()
        session = store.load(run_id)
        if session is None:
            yield (
                "event: error\nid: 1\n"
                f"data: {json.dumps({'error': 'session_not_found', 'run_id': run_id})}\n\n"
            )
            return

        summary = {
            "session_id": session.session_id,
            "status": session.status.value,
            "goals": list(session.config.goals),
            "started_at": session.started_at.isoformat(),
            "stop_reason": session.stop_reason,
        }
        payload = {"session": summary}
        if batcher:
            msg = await batcher.add_event({"type": "session_snapshot", "data": payload})
            if msg:
                yield msg
            final = batcher.flush()
            if final:
                yield final
        else:
            yield f"event: session_snapshot\nid: 1\ndata: {json.dumps(payload)}\n\n"

        yield ": heartbeat\n\n"

    return EventStream(event_generator())
