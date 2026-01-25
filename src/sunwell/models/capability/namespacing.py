"""Tool namespacing for multi-service environments.

Enables multiple tool registries (e.g., MCP servers) to coexist
by prefixing tool names with their service namespace.
"""

from dataclasses import dataclass

from sunwell.models.core.protocol import Tool, ToolCall


@dataclass(frozen=True, slots=True)
class NamespacedTool:
    """A tool with namespace information.

    Attributes:
        namespace: The namespace/service this tool belongs to.
        original_name: The tool's original name.
        namespaced_name: The full namespaced name.
        tool: The underlying Tool definition.
    """

    namespace: str
    """Namespace/service identifier."""

    original_name: str
    """Original tool name without namespace."""

    namespaced_name: str
    """Full namespaced name (namespace.original_name)."""

    tool: Tool
    """The underlying Tool definition."""


def namespace_tools(
    tools: tuple[Tool, ...],
    namespace: str,
    separator: str = ".",
) -> tuple[Tool, ...]:
    """Add namespace prefix to tool names.

    Args:
        tools: Tools to namespace
        namespace: Namespace to prepend
        separator: Separator between namespace and name

    Returns:
        Tools with namespaced names
    """
    return tuple(
        Tool(
            name=f"{namespace}{separator}{tool.name}",
            description=f"[{namespace}] {tool.description}",
            parameters=tool.parameters,
        )
        for tool in tools
    )


def parse_namespaced_name(
    namespaced_name: str,
    separator: str = ".",
) -> tuple[str | None, str]:
    """Parse a namespaced tool name.

    Args:
        namespaced_name: Full namespaced name
        separator: Separator between namespace and name

    Returns:
        Tuple of (namespace, original_name). Namespace is None if not namespaced.
    """
    if separator in namespaced_name:
        parts = namespaced_name.split(separator, 1)
        return parts[0], parts[1]
    return None, namespaced_name


def resolve_tool(
    namespaced_name: str,
    registries: dict[str, dict[str, Tool]],
    separator: str = ".",
) -> Tool | None:
    """Resolve a namespaced tool name to its definition.

    Args:
        namespaced_name: Full namespaced name
        registries: Dict of namespace to tool registry
        separator: Separator between namespace and name

    Returns:
        Tool definition, or None if not found
    """
    namespace, original_name = parse_namespaced_name(namespaced_name, separator)

    if namespace is None:
        # No namespace - search all registries
        for registry in registries.values():
            if original_name in registry:
                return registry[original_name]
        return None

    # Look in specific namespace
    registry = registries.get(namespace)
    if registry is None:
        return None

    return registry.get(original_name)


def denamespacify_tool_call(
    tool_call: ToolCall,
    separator: str = ".",
) -> tuple[str | None, ToolCall]:
    """Remove namespace from a tool call.

    Args:
        tool_call: Tool call with potentially namespaced name
        separator: Separator between namespace and name

    Returns:
        Tuple of (namespace, tool_call with original name)
    """
    namespace, original_name = parse_namespaced_name(tool_call.name, separator)

    if namespace is None:
        return None, tool_call

    return namespace, ToolCall(
        id=tool_call.id,
        name=original_name,
        arguments=tool_call.arguments,
    )


def merge_registries(
    registries: dict[str, dict[str, Tool]],
    separator: str = ".",
) -> dict[str, Tool]:
    """Merge multiple registries into a single namespaced registry.

    Args:
        registries: Dict of namespace to tool registry
        separator: Separator between namespace and name

    Returns:
        Single registry with all tools namespaced
    """
    merged: dict[str, Tool] = {}

    for namespace, registry in registries.items():
        for name, tool in registry.items():
            namespaced_name = f"{namespace}{separator}{name}"
            merged[namespaced_name] = Tool(
                name=namespaced_name,
                description=f"[{namespace}] {tool.description}",
                parameters=tool.parameters,
            )

    return merged
