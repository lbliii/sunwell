"""SSE stream endpoint for real-time system updates.

Provides Server-Sent Events stream for:
- Background task progress
- System status changes
- Real-time notifications
"""

from chirp import EventStream, Request


async def get(request: Request) -> EventStream:
    """Stream system events via SSE.

    Args:
        request: HTTP request with optional Last-Event-ID header for replay

    Returns:
        EventStream that yields SSE-formatted events

    Usage:
        const events = new EventSource('/system/stream');
        events.addEventListener('task_update', (e) => {
            const data = JSON.parse(e.data);
            console.log('Task update:', data);
        });
    """
    from sunwell.interface.chirp.events import create_run_event_stream

    # Get Last-Event-ID for replay support
    last_event_id = request.headers.get("Last-Event-ID")

    # For now, stream general system events
    # In the future, could support filtering by query params:
    # - ?run_id=xxx - stream specific run
    # - ?type=tasks - only task events
    # - ?type=system - only system events

    run_id = request.query.get("run_id", "system")

    return await create_run_event_stream(
        run_id=run_id,
        last_event_id=last_event_id,
        batch_events=True,
    )
