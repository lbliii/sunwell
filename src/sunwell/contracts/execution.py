"""Execution and runtime protocols.

Extracted from sunwell.foundation.types.protocol per the Contracts Layer plan.
This module imports ONLY from stdlib + sibling contracts modules.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar, runtime_checkable

from sunwell.contracts.model import Tool, ToolCall

T = TypeVar("T")
R = TypeVar("R")


# =============================================================================
# Tool Result (moved from sunwell.tools.core.types)
# =============================================================================


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result from executing a tool."""

    tool_call_id: str
    success: bool
    output: str
    artifacts: tuple[str, ...] = ()  # Files created/modified
    execution_time_ms: int = 0


# =============================================================================
# Console Protocol
# =============================================================================


@runtime_checkable
class ConsoleProtocol(Protocol):
    """Abstract console interface for I/O operations.

    Enables swapping Rich Console for test doubles (NullConsole, MockConsole).
    """

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print a message to console."""
        ...

    def input(self, prompt: str = "") -> str:
        """Get input from user."""
        ...


# =============================================================================
# Chat Session Protocol
# =============================================================================


@runtime_checkable
class ChatSessionProtocol(Protocol):
    """Abstract chat session interface.

    Separates CLI interface from core chat logic for testability.
    """

    async def process_message(self, message: str) -> str:
        """Process a user message and return assistant response."""
        ...

    async def handle_command(self, command: str) -> str | None:
        """Handle a chat command (e.g., /switch, /learn)."""
        ...


# =============================================================================
# Memory Store Protocol
# =============================================================================


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Unified memory store interface.

    Abstracts over SimulacrumStore, SimulacrumManager, and other
    memory implementations for testing and alternative backends.
    """

    async def store(self, key: str, value: Any) -> None:
        """Store a value in memory."""
        ...

    async def retrieve(self, query: str, limit: int = 10) -> list[Any]:
        """Retrieve items by text query."""
        ...

    async def search(self, embedding: list[float], limit: int = 10) -> list[Any]:
        """Search by embedding vector."""
        ...


# =============================================================================
# Tool Executor Protocol
# =============================================================================


@runtime_checkable
class ToolExecutorProtocol(Protocol):
    """Abstract tool execution interface.

    Enables swapping ToolExecutor for test doubles or alternative implementations.
    """

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        ...

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names."""
        ...

    def available_tools(self) -> list[Tool]:
        """Get list of available Tool definitions."""
        ...


# =============================================================================
# Parallel Executor Protocol
# =============================================================================


@runtime_checkable
class ParallelExecutorProtocol(Protocol):
    """Unified parallel execution interface.

    Abstracts over ThreadPoolExecutor, asyncio.gather, and other
    parallel execution mechanisms for testability.
    """

    async def map(self, fn: Callable[[T], R], items: list[T]) -> list[R]:
        """Apply function to items in parallel."""
        ...

    async def gather(self, *coros: Coroutine[Any, Any, R]) -> list[R]:
        """Run coroutines in parallel and gather results."""
        ...


# =============================================================================
# Worker Protocol
# =============================================================================


@runtime_checkable
class WorkerProtocol(Protocol):
    """Protocol for Naaru region workers.

    Enables dependency injection and testing of worker implementations.
    All workers in naaru/workers/ implement this protocol.

    Note: ``region`` and ``bus`` are typed as ``Any`` here to avoid
    importing planning types into the contracts layer. Concrete
    implementations use the proper NaaruRegion and MessageBus types.
    """

    region: Any
    """The region this worker handles (NaaruRegion)."""

    bus: Any
    """Message bus for inter-region communication (MessageBus)."""

    workspace: Path
    """Workspace root path."""

    worker_id: int
    """Unique identifier for this worker instance."""

    stats: dict[str, int]
    """Worker statistics."""

    async def process(self) -> None:
        """Main processing loop for this region."""
        ...

    def stop(self) -> None:
        """Signal this worker to stop."""
        ...
