"""Base types for the trinket composition system.

Trinkets are self-contained components that contribute sections to the
system prompt. They provide:
- Modularity: Each trinket owns its domain (time, learnings, briefing, etc.)
- Priority ordering: Explicit control over section order
- Graceful degradation: One failing trinket doesn't crash composition
- Native async: Full async support for database lookups, etc.

Inspired by MIRA's trinket pattern but with explicit priority ordering,
native async support, and no EventBus complexity.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.tools.core.types import Tool


class TrinketPlacement(Enum):
    """Where a trinket's content should be placed."""

    SYSTEM = "system"
    """Goes in the system prompt (cached or non-cached)."""

    CONTEXT = "context"
    """Goes in the user context section."""

    NOTIFICATION = "notification"
    """Goes in a sliding notification window (time, alerts)."""


@dataclass(frozen=True, slots=True)
class TrinketSection:
    """A section contributed by a trinket.

    Attributes:
        name: Unique identifier for this section.
        content: The actual content to inject.
        placement: Where this content should go.
        priority: Lower = earlier in prompt. Default 50.
        cacheable: Whether this can be cached across turns.
    """

    name: str
    """Unique identifier for this section."""

    content: str
    """The actual content to inject into the prompt."""

    placement: TrinketPlacement
    """Where this content should be placed."""

    priority: int = 50
    """Lower priority = appears earlier in the prompt."""

    cacheable: bool = False
    """Whether this section can be cached across turns."""


@dataclass(frozen=True, slots=True)
class TrinketContext:
    """Context provided to trinkets during generation.

    Contains all information a trinket might need to generate
    its section.
    """

    task: str
    """The current task description."""

    workspace: Path
    """The workspace root path."""

    turn: int = 0
    """Current turn number (0 for initial composition)."""

    tools: tuple[Any, ...] = ()
    """Available tools (Tool objects)."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Additional context for specialized trinkets."""


@dataclass(frozen=True, slots=True)
class TurnResult:
    """Result of a completed turn, for trinket notifications.

    Trinkets can use this to update their state based on
    what happened during the turn.
    """

    turn: int
    """The turn number that completed."""

    tool_calls: tuple[str, ...] = ()
    """Names of tools that were called."""

    success: bool = True
    """Whether the turn completed successfully."""

    error: str | None = None
    """Error message if turn failed."""


class BaseTrinket(ABC):
    """Base class for prompt-contributing trinkets.

    Subclasses must implement:
    - get_section_name(): Return unique identifier
    - generate(): Return TrinketSection or None

    Optionally override:
    - on_turn_complete(): React to turn completion
    - on_tool_executed(): React to tool execution

    Example:
        class TimeTrinket(BaseTrinket):
            def get_section_name(self) -> str:
                return "time"

            async def generate(self, context: TrinketContext) -> TrinketSection:
                return TrinketSection(
                    name="time",
                    content=f"Current time: {datetime.now()}",
                    placement=TrinketPlacement.NOTIFICATION,
                    priority=0,
                )
    """

    @abstractmethod
    def get_section_name(self) -> str:
        """Return unique identifier for this trinket's section.

        This is used for caching and logging.
        """
        ...

    @abstractmethod
    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        """Generate this trinket's section.

        Args:
            context: Information about the current task, turn, etc.

        Returns:
            TrinketSection with content, or None if nothing to contribute.
        """
        ...

    def on_turn_complete(self, result: TurnResult) -> None:
        """React to turn completion (optional).

        Override this to update internal state based on what
        happened during the turn.

        Args:
            result: Information about the completed turn.
        """
        pass

    def on_tool_executed(self, tool_name: str, success: bool) -> None:
        """React to tool execution (optional).

        Override this to update internal state based on
        tool execution.

        Args:
            tool_name: Name of the tool that was executed.
            success: Whether the tool execution succeeded.
        """
        pass
