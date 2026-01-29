"""Tool planner for plan-then-execute pattern.

This module implements a pre-selection planning step that asks the model
what tools it will need for a task BEFORE filtering. This dramatically
reduces tool count by focusing on explicitly planned tools.

Research backing:
- Plan-then-Execute pattern provides control-flow integrity
- Reduces harmful tool calls by ~65% (proactive guardrails research)
- Improves multi-step task completion

The planner generates a tool plan which becomes a hard filter signal
in MultiSignalToolSelector.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import Tool
    from sunwell.models.protocol import ModelProtocol

logger = logging.getLogger(__name__)

# Prompt template for tool planning
PLANNING_PROMPT = """You are a tool planning assistant. Given a user's request, determine which tools will be needed to complete the task.

Available tools:
{tool_list}

User request: {query}

Think step by step:
1. What is the user trying to accomplish?
2. What sequence of actions would achieve this?
3. Which tools from the list are needed for each action?

Respond with ONLY a JSON array of tool names needed, in order of use.
Example: ["list_files", "read_file", "edit_file"]

Tools needed:"""

# Simpler prompt for faster models
FAST_PLANNING_PROMPT = """Task: {query}

Available tools: {tool_names}

List ONLY the tool names needed (JSON array):"""


@dataclass(frozen=True, slots=True)
class ToolPlan:
    """Result of tool planning.

    Attributes:
        tools: Ordered list of planned tool names
        reasoning: Optional explanation of the plan
        confidence: Planning confidence (0.0-1.0)
    """

    tools: tuple[str, ...]
    reasoning: str = ""
    confidence: float = 1.0

    def __contains__(self, tool_name: str) -> bool:
        """Check if a tool is in the plan."""
        return tool_name in self.tools

    def __len__(self) -> int:
        return len(self.tools)

    def as_set(self) -> frozenset[str]:
        """Return tools as a frozenset for set operations."""
        return frozenset(self.tools)


@dataclass(slots=True)
class ToolPlanner:
    """Plans which tools are needed before selection.

    Uses the model to analyze the user's request and determine which
    tools will be needed, creating a focused tool set for the task.

    This implements the Plan-then-Execute pattern:
    1. User query → Planner → Tool plan
    2. Tool plan → Selector → Filtered tools
    3. Filtered tools → Model → Tool call

    Attributes:
        fast_mode: Use simpler prompt for faster planning
        max_tools: Maximum tools to include in plan
        fallback_to_all: If planning fails, include all tools
    """

    fast_mode: bool = True
    max_tools: int = 10
    fallback_to_all: bool = True

    # Cache for repeated queries
    _cache: dict[str, ToolPlan] = field(default_factory=dict, init=False)

    def _build_tool_list(self, tools: "tuple[Tool, ...]") -> str:
        """Build a formatted list of tools for the prompt.

        Args:
            tools: Available tool definitions

        Returns:
            Formatted string listing tools with descriptions
        """
        lines = []
        for tool in tools:
            desc = getattr(tool, "description", "") or ""
            # Truncate long descriptions
            if len(desc) > 100:
                desc = desc[:97] + "..."
            lines.append(f"- {tool.name}: {desc}")
        return "\n".join(lines)

    def _build_tool_names(self, tools: "tuple[Tool, ...]") -> str:
        """Build a comma-separated list of tool names.

        Args:
            tools: Available tool definitions

        Returns:
            Comma-separated tool names
        """
        return ", ".join(t.name for t in tools)

    def _parse_plan_response(
        self,
        response: str,
        available_names: frozenset[str],
    ) -> ToolPlan:
        """Parse the model's planning response.

        Args:
            response: Raw model response
            available_names: Set of valid tool names

        Returns:
            Parsed ToolPlan
        """
        # Try to extract JSON array
        # Look for [...] pattern
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            try:
                tools_list = json.loads(match.group())
                if isinstance(tools_list, list):
                    # Filter to valid tool names
                    valid_tools = [
                        t for t in tools_list
                        if isinstance(t, str) and t in available_names
                    ]
                    if valid_tools:
                        return ToolPlan(
                            tools=tuple(valid_tools[:self.max_tools]),
                            reasoning=response,
                            confidence=0.9,
                        )
            except json.JSONDecodeError:
                pass

        # Fallback: look for tool names mentioned in response
        mentioned = []
        response_lower = response.lower()
        for name in available_names:
            if name.lower() in response_lower:
                mentioned.append(name)

        if mentioned:
            return ToolPlan(
                tools=tuple(mentioned[:self.max_tools]),
                reasoning=response,
                confidence=0.6,  # Lower confidence for fallback parsing
            )

        # No tools found
        return ToolPlan(tools=(), reasoning=response, confidence=0.0)

    async def plan(
        self,
        query: str,
        available_tools: "tuple[Tool, ...]",
        model: "ModelProtocol",
    ) -> ToolPlan:
        """Generate a tool plan for the query.

        Args:
            query: User's request
            available_tools: All available tool definitions
            model: Model to use for planning

        Returns:
            ToolPlan with needed tools
        """
        # Check cache
        cache_key = f"{query}:{len(available_tools)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        available_names = frozenset(t.name for t in available_tools)

        # Build prompt
        if self.fast_mode:
            prompt = FAST_PLANNING_PROMPT.format(
                query=query,
                tool_names=self._build_tool_names(available_tools),
            )
        else:
            prompt = PLANNING_PROMPT.format(
                query=query,
                tool_list=self._build_tool_list(available_tools),
            )

        try:
            # Generate plan using model
            messages = [{"role": "user", "content": prompt}]
            response = await model.generate(messages)

            # Extract text from response
            if hasattr(response, "content"):
                response_text = response.content
            elif hasattr(response, "message"):
                response_text = response.message.content
            else:
                response_text = str(response)

            plan = self._parse_plan_response(response_text, available_names)

            # Cache result
            self._cache[cache_key] = plan

            logger.debug(
                "Tool plan for '%s': %s (confidence=%.2f)",
                query[:50],
                plan.tools,
                plan.confidence,
            )

            return plan

        except Exception as e:
            logger.warning("Tool planning failed: %s", e)

            # Fallback: return all tools or empty plan
            if self.fallback_to_all:
                return ToolPlan(
                    tools=tuple(t.name for t in available_tools[:self.max_tools]),
                    reasoning=f"Planning failed: {e}",
                    confidence=0.3,
                )
            return ToolPlan(tools=(), reasoning=f"Planning failed: {e}", confidence=0.0)

    def plan_sync(
        self,
        query: str,
        available_tools: "tuple[Tool, ...]",
        model: "ModelProtocol",
    ) -> ToolPlan:
        """Synchronous wrapper for plan().

        Args:
            query: User's request
            available_tools: All available tool definitions
            model: Model to use for planning

        Returns:
            ToolPlan with needed tools
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run sync in async context
                # Return empty plan (planning disabled)
                return ToolPlan(tools=(), confidence=0.0)
            return loop.run_until_complete(self.plan(query, available_tools, model))
        except RuntimeError:
            return asyncio.run(self.plan(query, available_tools, model))

    def clear_cache(self) -> None:
        """Clear the planning cache."""
        self._cache.clear()


# =============================================================================
# HEURISTIC PLANNER (NO MODEL REQUIRED)
# =============================================================================


# Keywords to tool mapping for heuristic planning
KEYWORD_TOOL_MAP: dict[str, tuple[str, ...]] = {
    # File operations
    "list": ("list_files",),
    "find": ("find_files", "search_files"),
    "search": ("search_files",),
    "read": ("read_file",),
    "view": ("read_file",),
    "show": ("read_file", "list_files"),
    "edit": ("edit_file",),
    "modify": ("edit_file",),
    "change": ("edit_file",),
    "fix": ("search_files", "read_file", "edit_file"),
    "write": ("write_file",),
    "create": ("write_file", "mkdir"),
    "delete": ("delete_file",),
    "remove": ("delete_file",),
    "rename": ("rename_file",),
    "copy": ("copy_file",),
    "undo": ("undo_file",),
    "restore": ("restore_file",),

    # Git operations
    "commit": ("git_add", "git_commit"),
    "stage": ("git_add",),
    "unstage": ("git_restore",),
    "diff": ("git_diff",),
    "status": ("git_status",),
    "log": ("git_log",),
    "blame": ("git_blame",),
    "branch": ("git_branch",),
    "checkout": ("git_checkout",),
    "merge": ("git_merge",),
    "stash": ("git_stash",),
    "reset": ("git_reset",),

    # Shell operations
    "run": ("run_command",),
    "execute": ("run_command",),
    "test": ("run_command",),
    "build": ("run_command",),
    "install": ("run_command",),

    # Web operations
    "google": ("web_search",),
    "lookup": ("web_search",),
    "fetch": ("web_fetch",),
    "download": ("web_fetch",),

    # Environment
    "env": ("list_env",),
    "environment": ("list_env",),
    "variable": ("list_env",),
}


def plan_heuristic(
    query: str,
    available_tools: "tuple[Tool, ...]",
    max_tools: int = 10,
) -> ToolPlan:
    """Plan tools using keyword heuristics (no model required).

    Fast fallback when model-based planning is unavailable or too slow.

    Args:
        query: User's request
        available_tools: All available tool definitions
        max_tools: Maximum tools to include

    Returns:
        ToolPlan based on keyword matching
    """
    available_names = frozenset(t.name for t in available_tools)
    query_lower = query.lower()

    # Collect matching tools
    matched: list[str] = []
    matched_set: set[str] = set()

    for keyword, tools in KEYWORD_TOOL_MAP.items():
        if keyword in query_lower:
            for tool in tools:
                if tool in available_names and tool not in matched_set:
                    matched.append(tool)
                    matched_set.add(tool)

    # If no matches, return common starting tools
    if not matched:
        defaults = ["list_files", "search_files", "read_file"]
        matched = [t for t in defaults if t in available_names]

    return ToolPlan(
        tools=tuple(matched[:max_tools]),
        reasoning=f"Heuristic plan from keywords in: {query[:50]}",
        confidence=0.7,
    )
