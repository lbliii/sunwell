"""SkillExecutor - wires skills into agent tool loop as callable tools."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.models import Tool, ToolCall
from sunwell.skills.protocol import SkillRegistry

if TYPE_CHECKING:
    from sunwell.memory import PersistentMemory
    from sunwell.tools.providers.web_search import WebSearchHandler

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Executes skill actions and provides Tool definitions for the agent."""

    def __init__(
        self,
        registry: SkillRegistry,
        workspace: Path,
        web_search_handler: WebSearchHandler | None = None,
        memory: PersistentMemory | None = None,
    ) -> None:
        self._registry = registry
        self._workspace = workspace
        self._web_search = web_search_handler
        self._memory = memory

    def get_tool_definitions(self) -> tuple[Tool, ...]:
        """Get Tool definitions for all registered skill actions."""
        return tuple(self._registry.get_all_tools())

    def get_tool_names(self) -> frozenset[str]:
        """Get set of tool names from skill actions."""
        return self._registry.get_tool_names()

    def is_skill_tool(self, name: str) -> bool:
        """Check if tool name is a skill action."""
        return name in self._registry.get_tool_names()

    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a skill action.

        Args:
            tool_call: Tool call with name and arguments

        Returns:
            Result string for the agent
        """
        name = tool_call.name
        args = tool_call.arguments or {}

        for skill in self._registry._skills.values():
            for action in skill.get_actions():
                if action.name == name:
                    method = getattr(skill, action.method_name)
                    try:
                        result = await method(**args)
                        return str(result)
                    except Exception as e:
                        logger.exception("Skill %s.%s failed", skill.name, name)
                        return f"Skill error: {e}"

        return f"Unknown skill action: {name}"
