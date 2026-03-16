"""Activity feed - SSE stream of tool call events."""

import time
from chirp import App, EventStream, Fragment


async def get(app: App) -> EventStream:
    """Stream tool call events via SSE.

    This subscribes to app.tool_events and streams each tool call
    as an HTML fragment that gets appended to the activity feed.
    """

    async def generate():
        # Subscribe to tool events
        async for event in app.tool_events.subscribe():
            # Determine category from tool name
            tool_name = event.tool_name
            category = "unknown"
            if "backlog" in tool_name or "goal" in tool_name:
                category = "backlog"
            elif "search" in tool_name or "ask" in tool_name or "codebase" in tool_name:
                category = "knowledge"
            elif "recall" in tool_name or "briefing" in tool_name or "lineage" in tool_name:
                category = "memory"
            elif "lens" in tool_name or "route" in tool_name:
                category = "lens"

            # Format timestamp
            timestamp = time.strftime("%H:%M:%S", time.localtime(event.started_at))

            # Format arguments
            args_str = ", ".join(
                f"{k}={repr(v)[:50]}" for k, v in event.arguments.items()
            )

            # Check if error
            has_error = hasattr(event, "error") and event.error

            # Format result
            if has_error:
                result_str = None
                error_str = str(event.error)
            else:
                result_str = str(event.result)[:200] if event.result else "Success"
                error_str = None

            yield Fragment(
                "activity/_event.html",
                "event_row",
                tool_name=tool_name,
                category=category,
                timestamp=timestamp,
                args=args_str,
                result=result_str,
                error=error_str,
            )

    return EventStream(generate())
