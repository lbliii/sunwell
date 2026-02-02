"""Self-registering tool implementations.

Each module in this package contains a BaseTool subclass that:
1. Uses @tool_metadata decorator for registration
2. Defines JSON Schema parameters
3. Implements async execute() method

Tools are discovered automatically by DynamicToolRegistry.discover().

Example tool structure:
    # implementations/my_tool.py
    from sunwell.tools.registry import BaseTool, tool_metadata
    from sunwell.tools.core.types import ToolTrust

    @tool_metadata(
        name="my_tool",
        simple_description="Do something useful",
        trust_level=ToolTrust.WORKSPACE,
    )
    class MyTool(BaseTool):
        parameters = {
            "type": "object",
            "properties": {...},
            "required": [...],
        }

        async def execute(self, arguments: dict) -> str:
            return "result"
"""

# Tools are discovered via pkgutil.iter_modules, no explicit imports needed
