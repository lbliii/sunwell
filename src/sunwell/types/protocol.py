"""Protocol definitions for dependency injection and testing.

RFC-025: Protocol Layer - Enables dependency injection and testability.

These protocols define abstract interfaces for major subsystems,
allowing implementations to be swapped for testing or alternative backends.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Protocol, TypeVar, runtime_checkable

from sunwell.models.protocol import Tool, ToolCall
from sunwell.tools.types import ToolResult

T = TypeVar("T")
R = TypeVar("R")


@runtime_checkable
class ConsoleProtocol(Protocol):
    """Abstract console interface for I/O operations.

    Enables swapping Rich Console for test doubles (NullConsole, MockConsole).
    """

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print a message to console.

        Args:
            *args: Positional arguments (message, style, etc.)
            **kwargs: Keyword arguments (end, style, etc.)
        """
        ...

    def input(self, prompt: str = "") -> str:
        """Get input from user.

        Args:
            prompt: Prompt string to display

        Returns:
            User input string
        """
        ...


@runtime_checkable
class ChatSessionProtocol(Protocol):
    """Abstract chat session interface.

    Separates CLI interface from core chat logic for testability.
    """

    async def process_message(self, message: str) -> str:
        """Process a user message and return assistant response.

        Args:
            message: User message text

        Returns:
            Assistant response text
        """
        ...

    async def handle_command(self, command: str) -> str | None:
        """Handle a chat command (e.g., /switch, /learn).

        Args:
            command: Command string (with or without leading /)

        Returns:
            Command output string, or None if command not recognized
        """
        ...


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Unified memory store interface.

    Abstracts over SimulacrumStore, SimulacrumManager, and other
    memory implementations for testing and alternative backends.
    """

    async def store(self, key: str, value: Any) -> None:
        """Store a value in memory.

        Args:
            key: Storage key/identifier
            value: Value to store (Turn, Learning, etc.)
        """
        ...

    async def retrieve(self, query: str, limit: int = 10) -> list[Any]:
        """Retrieve items by text query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of retrieved items
        """
        ...

    async def search(self, embedding: list[float], limit: int = 10) -> list[Any]:
        """Search by embedding vector.

        Args:
            embedding: Embedding vector
            limit: Maximum number of results

        Returns:
            List of retrieved items
        """
        ...


@runtime_checkable
class ToolExecutorProtocol(Protocol):
    """Abstract tool execution interface.

    Enables swapping ToolExecutor for test doubles or alternative implementations.
    """

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call.

        Args:
            tool_call: Tool call to execute

        Returns:
            Tool execution result
        """
        ...

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool name strings
        """
        ...

    def available_tools(self) -> list[Tool]:
        """Get list of available Tool definitions.

        Returns:
            List of Tool objects
        """
        ...


@runtime_checkable
class ParallelExecutorProtocol(Protocol):
    """Unified parallel execution interface.

    Abstracts over ThreadPoolExecutor, asyncio.gather, and other
    parallel execution mechanisms for testability.
    """

    async def map(self, fn: Callable[[T], R], items: list[T]) -> list[R]:
        """Apply function to items in parallel.

        Args:
            fn: Function to apply
            items: List of items to process

        Returns:
            List of results
        """
        ...

    async def gather(self, *coros: Coroutine[Any, Any, R]) -> list[R]:
        """Run coroutines in parallel and gather results.

        Args:
            *coros: Coroutines to run

        Returns:
            List of results in order
        """
        ...
