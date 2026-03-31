"""Tool execution handler."""

import json

from chirp import App, Request, Response


async def post(tool_name: str, request: Request, app: App) -> Response:
    """Execute a tool with provided arguments."""
    # Parse form data
    form = await request.form()
    arguments = {}
    for key, value in form.items():
        if value:  # Only include non-empty values
            # Try to convert to appropriate type
            if "," in value:
                # Array (comma-separated)
                arguments[key] = [v.strip() for v in value.split(",")]
            elif value.isdigit():
                # Integer
                arguments[key] = int(value)
            else:
                # String
                arguments[key] = value

    # Execute tool
    try:
        result = await app._tool_registry.call_tool(tool_name, arguments)

        # Format result - tool returns dict directly
        result_data = result if isinstance(result, dict) else {"result": str(result)}
        result_html = f"""
        <div class="chirpui-alert chirpui-alert--success">
            <h4>Success</h4>
            <pre class="chirpui-font-mono chirpui-ui-sm"><code>{json.dumps(result_data, indent=2)}</code></pre>
        </div>
        """

        return Response(
            body=result_html,
            content_type="text/html",
        )
    except Exception as e:
        error_html = f"""
        <div class="chirpui-alert chirpui-alert--error">
            <h4>Error</h4>
            <pre class="chirpui-font-mono chirpui-ui-sm"><code>{str(e)}</code></pre>
        </div>
        """

        return Response(
            body=error_html,
            status=500,
            content_type="text/html",
        )
