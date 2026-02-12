"""Test tool call endpoint - Trigger tool calls for testing."""

from chirp import Request, Response
import json


async def post(request: Request) -> Response:
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
        # Access the tool registry after app is frozen
        if not app._frozen:
            app._freeze()

        result = await app._tool_registry.call_tool(tool_name, {})

        return Response(
            body=json.dumps({"success": True, "tool": tool_name, "result": str(result)[:200]}),
            content_type="application/json",
        )
    except Exception as e:
        return Response(
            body=json.dumps({"success": False, "tool": tool_name, "error": str(e)}),
            status=500,
            content_type="application/json",
        )
