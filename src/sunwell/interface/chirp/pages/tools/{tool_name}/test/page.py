"""Tool test form handler."""

from chirp import Page, Request


async def get(tool_name: str, request: Request) -> Page:
    """Render tool test form."""
    app = request.app
    if not app._frozen:
        app._freeze()

    # Get tool schema
    tools = app._tool_registry.list_tools()
    tool = next((t for t in tools if t["name"] == tool_name), None)

    if not tool:
        return Page(
            "tools/{tool_name}/test/page.html",
            tool_name=tool_name,
            description="Tool not found",
            parameters={},
            required=[],
        )

    schema = tool.get("inputSchema", {})
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    return Page(
        "tools/{tool_name}/test/page.html",
        tool_name=tool_name,
        description=tool.get("description", ""),
        parameters=properties,
        required=required,
    )
