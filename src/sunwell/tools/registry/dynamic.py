"""Dynamic tool registry with runtime enable/disable and synthetic loading.

This module implements the core registry that:
- Discovers tools by scanning implementations/ package
- Manages active vs inactive tool sets
- Provides synthetic loading (auto-enable on first call)
- Generates tool hints for inactive tools
- Generates usage guidance for active tools
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.models import Tool
from sunwell.tools.registry.base import BaseTool, ToolContext

if TYPE_CHECKING:
    from sunwell.knowledge.project import Project
    from sunwell.memory.simulacrum.core.store import SimulacrumStore


@dataclass(slots=True)
class DynamicToolRegistry:
    """Self-registering tool registry with runtime enable/disable.

    Replaces:
    - Static CORE_TOOLS dict in definitions/builtins.py
    - Manual tool registration in execution/executor.py

    Key features beyond MIRA:
    - Synthetic loading (auto-enable on first call)
    - Tool guidance injection
    - Richer context (memory, LLM provider, not just project)

    Attributes:
        tool_classes: Discovered tool classes (name -> class)
        active_tools: Currently active tool instances (name -> instance)
        project: Project context for path resolution
        memory_store: Optional memory store for tools
        llm_provider: Optional LLM provider for tools

    Example:
        >>> registry = DynamicToolRegistry(project=my_project)
        >>> registry.discover()
        >>> registry.enable("read_file")
        >>> result = await registry.execute("read_file", {"path": "foo.py"})
    """

    # Discovered tool classes (name -> class)
    tool_classes: dict[str, type[BaseTool]] = field(default_factory=dict)

    # Currently active tools (name -> instance)
    active_tools: dict[str, BaseTool] = field(default_factory=dict)

    # Rich context for tool injection
    project: Project | None = None
    memory_store: SimulacrumStore | None = None
    llm_provider: Any | None = None

    def discover(self, package: str = "sunwell.tools.implementations") -> None:
        """Scan package for BaseTool subclasses and register them.

        Scans all modules in the specified package, finding classes that:
        1. Subclass BaseTool
        2. Have metadata attached via @tool_metadata

        Args:
            package: Package path to scan (default: sunwell.tools.implementations)
        """
        try:
            pkg = importlib.import_module(package)
        except ModuleNotFoundError:
            # Package doesn't exist yet (during migration)
            return

        if not hasattr(pkg, "__path__"):
            return

        for module_info in pkgutil.iter_modules(pkg.__path__, package + "."):
            try:
                module = importlib.import_module(module_info.name)
            except Exception:
                # Skip modules that fail to import
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseTool)
                    and attr is not BaseTool
                    and hasattr(attr, "metadata")
                ):
                    self.tool_classes[attr.metadata.name] = attr

        # Auto-enable essential tools
        for name, cls in self.tool_classes.items():
            if cls.metadata.essential:
                self.enable(name)

    def discover_for_domain(self, domain: Any) -> None:
        """Discover tools for a specific domain (RFC-DOMAINS).

        Discovers tools from:
        1. Domain's tools_package (domain-specific tools)
        2. Universal tools (always available)

        Args:
            domain: Domain instance with tools_package property
        """
        from sunwell.domains.protocol import Domain

        # Type check the domain
        if not isinstance(domain, Domain) and not hasattr(domain, "tools_package"):
            return

        # Discover domain-specific tools
        if domain.tools_package:
            self.discover(domain.tools_package)

        # Always include universal tools (core file operations)
        # These are in the base implementations package
        self.discover("sunwell.tools.implementations")

    def enable(self, name: str) -> bool:
        """Enable tool for LLM use.

        Instantiates the tool class and injects rich context.
        Also enables any dependencies first.

        Args:
            name: Tool name to enable

        Returns:
            True if newly enabled, False if already active or not found
        """
        if name in self.active_tools:
            return False
        if name not in self.tool_classes:
            return False

        cls = self.tool_classes[name]

        # Enable dependencies first
        for dep in cls.metadata.dependencies:
            self.enable(dep)

        # Instantiate and inject rich context
        instance = cls()
        if self.project:
            instance.ctx = ToolContext(
                project=self.project,
                registry=self,
                memory_store=self.memory_store,
                llm_provider=self.llm_provider,
            )
        self.active_tools[name] = instance
        return True

    def disable(self, name: str) -> bool:
        """Disable tool (removes from LLM context).

        Essential tools cannot be disabled.

        Args:
            name: Tool name to disable

        Returns:
            True if disabled, False if not active or essential
        """
        if name not in self.active_tools:
            return False
        # Don't disable essential tools
        if self.tool_classes[name].metadata.essential:
            return False
        del self.active_tools[name]
        return True

    def get_active_schemas(self) -> tuple[Tool, ...]:
        """Get Tool definitions for only active tools.

        Returns:
            Tuple of Tool objects for LLM tool calling
        """
        return tuple(tool.to_tool() for tool in self.active_tools.values())

    def get_hints(self) -> dict[str, str]:
        """Get name -> simple_description for inactive tools.

        Used to show the LLM what additional tools are available
        without including their full schemas.

        Returns:
            Dict mapping tool names to one-line descriptions
        """
        return {
            name: cls.metadata.simple_description
            for name, cls in self.tool_classes.items()
            if name not in self.active_tools
        }

    def get_active_guidance(self) -> str:
        """Get usage guidance for all active tools.

        Collects usage_guidance from all active tools with guidance
        and formats them for system prompt injection.

        Returns:
            Formatted guidance string or empty string if no guidance
        """
        guidance_parts = []
        for tool in self.active_tools.values():
            if tool.metadata.usage_guidance:
                guidance_parts.append(
                    f"**{tool.metadata.name}**: {tool.metadata.usage_guidance}"
                )
        if not guidance_parts:
            return ""
        return "<tool_guidance>\n" + "\n".join(guidance_parts) + "\n</tool_guidance>"

    def get_tool(self, name: str) -> BaseTool | None:
        """Get an active tool instance by name.

        Args:
            name: Tool name

        Returns:
            Tool instance if active, None otherwise
        """
        return self.active_tools.get(name)

    def is_known(self, name: str) -> bool:
        """Check if a tool name is known (discovered).

        Args:
            name: Tool name

        Returns:
            True if tool was discovered, False otherwise
        """
        return name in self.tool_classes

    def is_active(self, name: str) -> bool:
        """Check if a tool is currently active.

        Args:
            name: Tool name

        Returns:
            True if tool is active, False otherwise
        """
        return name in self.active_tools

    async def execute(
        self,
        name: str,
        arguments: dict,
        auto_enable: bool = True,
    ) -> str:
        """Execute a tool by name.

        With auto_enable=True (default), implements synthetic loading:
        if the tool is known but not active, it's automatically enabled
        before execution. This is better than MIRA's approach which
        requires the LLM to explicitly call invokeother_tool.

        Args:
            name: Tool name to execute
            arguments: Arguments to pass to tool
            auto_enable: If True, auto-enable inactive but known tools

        Returns:
            Tool execution result string

        Raises:
            KeyError: If tool is not known or couldn't be enabled
        """
        if name not in self.active_tools:
            if auto_enable and name in self.tool_classes:
                # Synthetic loading: auto-enable the tool transparently
                self.enable(name)
            else:
                raise KeyError(f"Tool '{name}' is not available.")

        tool = self.active_tools[name]

        # Check gated availability
        if not tool.is_available():
            raise KeyError(f"Tool '{name}' is not available in current context.")

        return await tool.execute(arguments)

    def list_all_tools(self) -> list[str]:
        """Get list of all known tool names.

        Returns:
            List of all discovered tool names
        """
        return list(self.tool_classes.keys())

    def list_active_tools(self) -> list[str]:
        """Get list of currently active tool names.

        Returns:
            List of active tool names
        """
        return list(self.active_tools.keys())

    def enable_all_essential(self) -> None:
        """Enable all essential tools.

        Call this after discover() to ensure essential tools are active.
        This is also called automatically at the end of discover().
        """
        for name, cls in self.tool_classes.items():
            if cls.metadata.essential and name not in self.active_tools:
                self.enable(name)
