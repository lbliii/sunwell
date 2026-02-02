"""Base tool class and metadata for self-registering tools.

This module provides the foundation for the dynamic tool registry:
- ToolMetadata: Frozen dataclass with tool properties
- ToolContext: Rich context injected into tools at enable time
- BaseTool: Abstract base class combining definition + implementation
- tool_metadata: Decorator to attach metadata to tool classes
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.models import Tool
from sunwell.tools.core.types import ToolTrust

if TYPE_CHECKING:
    from sunwell.knowledge.project import Project
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.tools.registry.dynamic import DynamicToolRegistry


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    """Metadata for self-registering tools.

    Attributes:
        name: Unique tool name (matches JSON tool_call name)
        simple_description: One-line description for tool hints
        trust_level: Minimum trust level required to use this tool
        dependencies: Other tools that must be enabled first
        essential: If True, tool is always active (never disabled)
        usage_guidance: Tips injected into system prompt when tool is active
    """

    name: str
    simple_description: str
    trust_level: ToolTrust = ToolTrust.WORKSPACE
    dependencies: tuple[str, ...] = ()
    essential: bool = False
    usage_guidance: str | None = None


@dataclass(slots=True)
class ToolContext:
    """Rich context injected into tools when enabled.

    Provides tools with access to project, registry, memory, and LLM.
    This is richer than MIRA's project-only injection.

    Attributes:
        project: The current project (workspace root, trust level, etc.)
        registry: Reference to the registry for loading other tools
        memory_store: Optional access to conversation memory
        llm_provider: Optional access to LLM for tool-initiated calls
    """

    project: Project
    registry: DynamicToolRegistry
    memory_store: SimulacrumStore | None = None
    llm_provider: Any | None = None


class BaseTool(ABC):
    """Base class for self-registering tools.

    Combines tool definition (parameters, description) and implementation
    (execute method) in a single class. This replaces the previous split
    between definitions/builtins.py and handlers/base.py.

    Subclasses must:
    1. Use @tool_metadata decorator to set metadata
    2. Define `parameters` class attribute with JSON Schema
    3. Implement async `execute()` method

    Example:
        >>> @tool_metadata(
        ...     name="read_file",
        ...     simple_description="Read file contents",
        ...     trust_level=ToolTrust.READ_ONLY,
        ... )
        >>> class ReadFileTool(BaseTool):
        ...     parameters = {
        ...         "type": "object",
        ...         "properties": {
        ...             "path": {"type": "string", "description": "File path"},
        ...         },
        ...         "required": ["path"],
        ...     }
        ...
        ...     async def execute(self, arguments: dict) -> str:
        ...         path = self.resolve_path(arguments["path"])
        ...         return path.read_text()
    """

    # Set by @tool_metadata decorator
    metadata: ToolMetadata

    # Set by subclass - JSON Schema for parameters
    parameters: dict[str, Any]

    # Injected by registry when tool is enabled
    ctx: ToolContext | None = None

    @property
    def project(self) -> Project:
        """Convenience accessor for project context.

        Raises:
            RuntimeError: If tool not initialized with context
        """
        if not self.ctx:
            raise RuntimeError("Tool not initialized with context")
        return self.ctx.project

    @property
    def registry(self) -> DynamicToolRegistry:
        """Access registry to load other tools dynamically.

        Raises:
            RuntimeError: If tool not initialized with context
        """
        if not self.ctx:
            raise RuntimeError("Tool not initialized with context")
        return self.ctx.registry

    @property
    def memory_store(self) -> SimulacrumStore | None:
        """Access memory store if available."""
        return self.ctx.memory_store if self.ctx else None

    @property
    def llm_provider(self) -> Any | None:
        """Access LLM provider if available."""
        return self.ctx.llm_provider if self.ctx else None

    def to_tool(self) -> Tool:
        """Convert to Tool dataclass for LLM consumption.

        Returns:
            Tool object with name, description, and parameters
        """
        return Tool(
            name=self.metadata.name,
            description=self.__doc__ or self.metadata.simple_description,
            parameters=self.parameters,
        )

    def resolve_path(self, relative: str) -> Path:
        """Resolve path relative to workspace with security enforcement.

        Args:
            relative: Path relative to workspace root

        Returns:
            Absolute path within workspace

        Raises:
            RuntimeError: If tool not initialized with context
        """
        return self.project.root / relative

    @abstractmethod
    async def execute(self, arguments: dict) -> str:
        """Execute the tool with given arguments.

        Args:
            arguments: Parsed arguments from tool call

        Returns:
            String result to return to LLM
        """

    def is_available(self) -> bool:
        """Check if tool is available for use.

        Override in subclasses for gated tools that self-determine
        availability based on context (e.g., git tools only in repos).

        Returns:
            True if tool can be used, False otherwise
        """
        return True


def tool_metadata(
    name: str,
    simple_description: str,
    trust_level: ToolTrust = ToolTrust.WORKSPACE,
    dependencies: tuple[str, ...] = (),
    essential: bool = False,
    usage_guidance: str | None = None,
) -> type[BaseTool]:
    """Decorator to attach metadata to tool classes.

    Args:
        name: Unique tool name
        simple_description: One-line description for hints
        trust_level: Minimum trust level required
        dependencies: Tools that must be enabled first
        essential: If True, always active
        usage_guidance: Tips for system prompt when active

    Returns:
        Decorated class with metadata attached

    Example:
        >>> @tool_metadata(
        ...     name="edit_file",
        ...     simple_description="Make surgical edits to a file",
        ...     trust_level=ToolTrust.WORKSPACE,
        ...     usage_guidance="Prefer edit_file over write_file for existing files.",
        ... )
        >>> class EditFileTool(BaseTool):
        ...     ...
    """

    def decorator(cls: type[BaseTool]) -> type[BaseTool]:
        cls.metadata = ToolMetadata(
            name=name,
            simple_description=simple_description,
            trust_level=trust_level,
            dependencies=dependencies,
            essential=essential,
            usage_guidance=usage_guidance,
        )
        return cls

    return decorator
