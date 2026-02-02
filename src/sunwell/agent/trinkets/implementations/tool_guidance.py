"""Tool guidance trinket - injects tool hints and usage guidance.

Priority 50, system placement.
Not cacheable - changes with tool state.

Ported from tools/registry/context.py
"""

import logging
from typing import TYPE_CHECKING

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
    TurnResult,
)

if TYPE_CHECKING:
    from sunwell.tools.execution.executor import ToolExecutor
    from sunwell.tools.registry.dynamic import DynamicToolRegistry

logger = logging.getLogger(__name__)


class ToolGuidanceTrinket(BaseTrinket):
    """Injects tool hints and usage guidance.

    Combines:
    - Tool hints: What additional tools are available (auto-load on use)
    - Usage guidance: How to use active tools effectively

    Reacts to tool execution to potentially update guidance.

    Example output:
        <available_tools>
        Additional tools available (will auto-load on first use):
          - git_status: Show git repository status
          - search_files: Search file contents with ripgrep
        </available_tools>

        ## Tool Usage Tips

        **read_file**: Prefer reading specific line ranges for large files.
        **edit_file**: Always include enough context for unique matching.
    """

    def __init__(self, executor: ToolExecutor | None) -> None:
        """Initialize with tool executor.

        Args:
            executor: Tool executor with registry access.
        """
        self.executor = executor
        self._tools_executed: set[str] = set()

    def get_section_name(self) -> str:
        """Return unique identifier."""
        return "tool_guidance"

    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        """Generate tool guidance section.

        Returns None if no executor or no registry.
        """
        if not self.executor:
            return None

        registry = self._get_registry()
        if not registry:
            return None

        try:
            from sunwell.tools.registry.context import build_tool_context

            content = build_tool_context(registry)
            if not content:
                return None

            return TrinketSection(
                name="tool_guidance",
                content=content,
                placement=TrinketPlacement.SYSTEM,
                priority=50,  # After learnings, before memory context
                cacheable=False,  # Changes with tool state
            )

        except Exception as e:
            logger.warning("Tool guidance trinket failed: %s", e)
            return None

    def on_tool_executed(self, tool_name: str, success: bool) -> None:
        """Track executed tools.

        This could be used to adjust guidance based on what
        tools have been used.
        """
        self._tools_executed.add(tool_name)

    def on_turn_complete(self, result: TurnResult) -> None:
        """Track tools from completed turns."""
        for tool_name in result.tool_calls:
            self._tools_executed.add(tool_name)

    def _get_registry(self) -> DynamicToolRegistry | None:
        """Get the registry from the executor."""
        if not self.executor:
            return None

        # Access the internal registry
        return getattr(self.executor, "_registry", None)
