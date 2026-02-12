"""Activity Monitor page - Real-time tool call monitoring."""

import json
import time
from chirp import Page, EventStream, Fragment, Request


def get() -> Page:
    """Render activity monitor page."""
    return Page("activity/page.html")


async def feed() -> EventStream:
    """Stream tool call events via SSE.

    This subscribes to app.tool_events and streams each tool call
    as an HTML fragment that gets appended to the activity feed.
    """

    async def generate(request: Request):
        # Get the app instance to access tool_events
        app = request.app

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

            yield Fragment(
                "activity/_event.html",
                "event_row",
                tool_name=tool_name,
                category=category,
                timestamp=timestamp,
                args=args_str,
                result=event.result if not has_error else None,
                error=event.error if has_error else None,
            )

    return EventStream(generate)


async def post_test_call(request: Request) -> dict:
    """Trigger a test tool call to demonstrate activity monitoring.

    This manually calls one of the registered tools and lets the
    tool event system broadcast it to any connected activity monitors.
    """
    form = await request.form()
    tool_name = form.get("tool", "sunwell_list_lenses")

    # Get the app to access the tool registry
    app = request.app

    # Call the tool (this will emit an event automatically)
    try:
        result = await app.tools.call_tool(tool_name, {})
        return {"success": True, "tool": tool_name, "result": result}
    except Exception as e:
        return {"success": False, "tool": tool_name, "error": str(e)}
