"""SSE endpoint for run events."""

from chirp import EventStream, Request

from sunwell.interface.chirp.events import create_run_event_stream


async def get(request: Request, run_id: str) -> EventStream:
    """Stream events for a specific run via SSE.

    Args:
        request: HTTP request (used to get Last-Event-ID header)
        run_id: Run identifier

    Returns:
        SSE EventStream with run events

    Example:
        GET /events/run/abc123
        Last-Event-ID: 42

        event: task_start
        id: 43
        data: {"task_id": "t1", "description": "Analyzing..."}
    """
    # Check for Last-Event-ID header (reconnection)
    last_event_id = request.headers.get("Last-Event-ID")

    # Create SSE stream with optional replay
    return await create_run_event_stream(
        run_id=run_id,
        last_event_id=last_event_id,
        batch_events=True,  # Enable batching for high-frequency events
    )
