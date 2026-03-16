"""Tool Inspector page - Browse and test MCP tools."""

import json
from collections import defaultdict

from chirp import App


def get(app: App) -> dict:
    """Render tool inspector page."""
    tools = app._tool_registry.list_tools()

    tools_by_category: defaultdict[str, list[dict]] = defaultdict(list)
    for tool in tools:
        name = tool["name"]
        if name.startswith("sunwell_"):
            name_part = name.replace("sunwell_", "")
            if any(x in name_part for x in ["goal", "backlog", "suggest"]):
                category = "backlog"
            elif any(x in name_part for x in ["search", "ask", "codebase", "workspace"]):
                category = "knowledge"
            elif any(x in name_part for x in ["lens", "route", "list_lenses"]):
                category = "lens"
            elif any(x in name_part for x in ["briefing", "recall", "lineage", "session"]):
                category = "memory"
            else:
                category = "other"
        else:
            category = "other"

        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        enriched_tool = {
            "name": tool["name"],
            "description": tool.get("description", "No description"),
            "schema": schema,
            "schema_json": json.dumps(schema, indent=2),
            "required": required,
            "optional_count": len(properties) - len(required),
            "properties": properties,
        }

        tools_by_category[category].append(enriched_tool)

    category_icons = {
        "backlog": "📋",
        "knowledge": "🔍",
        "lens": "🔬",
        "memory": "🧠",
        "other": "🔹",
    }

    return {
        "page_title": "Tool Inspector - Sunwell Studio",
        "breadcrumb_label": "Tools",
        "total_tools": len(tools),
        "tools_by_category": dict(tools_by_category),
        "categories": list(tools_by_category.keys()),
        "category_icons": category_icons,
    }
