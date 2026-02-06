"""MCP delegation tools for Sunwell.

Provides tools for smart model delegation and routing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sunwell.mcp.formatting import mcp_json, omit_empty

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_delegation_tools(mcp: FastMCP) -> None:
    """Register delegation-related tools.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool()
    def sunwell_delegate(
        task: str,
        constraints: str | None = None,
    ) -> str:
        """
        Get smart model delegation advice for a task.

        Uses Sunwell's model registry and routing intelligence to recommend
        the optimal model for a given task. Considers task complexity/type,
        model capabilities/cost, and available models.

        Args:
            task: Description of the task to delegate
            constraints: Optional constraints (e.g., "fast", "cheap", "accurate")

        Returns:
            JSON with recommended model, reasoning, and alternatives
        """
        try:
            from sunwell.models.registry.registry import get_registry

            registry = get_registry()
            registered = registry.list_registered()

            task_lower = task.lower()

            # Simple heuristic-based routing
            needs_intelligence = any(
                kw in task_lower
                for kw in [
                    "complex", "architect", "design", "reason", "analyze",
                    "refactor", "plan", "strategy", "debug", "investigate",
                ]
            )
            needs_speed = any(
                kw in task_lower
                for kw in [
                    "simple", "quick", "format", "rename", "trivial",
                    "lint", "fix typo", "minor",
                ]
            )

            if constraints:
                constraints_lower = constraints.lower()
                if "fast" in constraints_lower or "cheap" in constraints_lower:
                    needs_speed = True
                    needs_intelligence = False
                elif "accurate" in constraints_lower or "smart" in constraints_lower:
                    needs_intelligence = True
                    needs_speed = False

            if needs_intelligence and not needs_speed:
                tier = "smart"
                aliases_to_try = ["anthropic-smart", "openai-smart", "ollama-smart"]
                reasoning = "Task requires high intelligence - recommending capable model"
            elif needs_speed and not needs_intelligence:
                tier = "fast"
                aliases_to_try = ["anthropic-cheap", "openai-cheap", "ollama-cheap"]
                reasoning = "Task is straightforward - recommending fast/cheap model"
            else:
                tier = "balanced"
                aliases_to_try = ["default", "anthropic-smart", "openai-smart"]
                reasoning = "Task has mixed requirements - recommending balanced model"

            recommended = None
            for alias in aliases_to_try:
                model = registry.get(alias, auto_create=False)
                if model:
                    recommended = alias
                    break

            alternatives = [
                name for name in registered[:5] if name != recommended
            ]

            return mcp_json(omit_empty({
                "task": task,
                "constraints": constraints,
                "recommendation": {
                    "model": recommended or "default",
                    "tier": tier,
                    "reasoning": reasoning,
                },
                "alternatives": alternatives,
                "registered_models": registered,
            }), "compact")
        except Exception as e:
            return mcp_json({"error": str(e), "task": task}, "compact")
