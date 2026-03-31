"""Tool test form handler — returns a fragment loaded into modal via HTMX."""

from chirp import App, Fragment


def get(tool_name: str, app: App) -> Fragment:
    """Render tool test form as a modal fragment."""
    tools = app._tool_registry.list_tools()
    tool = next((t for t in tools if t["name"] == tool_name), None)

    if not tool:
        return Fragment(
            "tools/{tool_name}/test/page.html",
            "tool_test",
            tool_name=tool_name,
            description="Tool not found",
            parameters={},
            required=[],
        )

    schema = tool.get("inputSchema", {})
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    return Fragment(
        "tools/{tool_name}/test/page.html",
        "tool_test",
        tool_name=tool_name,
        description=tool.get("description", ""),
        parameters=properties,
        required=required,
    )
