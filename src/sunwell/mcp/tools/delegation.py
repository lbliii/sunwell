"""MCP delegation tools for Sunwell.

Provides tools for smart model delegation and routing.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

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

        Uses Sunwell's model registry and routing intelligence (RFC-137)
        to recommend the optimal model for a given task. Considers:
        - Task complexity and type
        - Model capabilities and cost
        - Available models in the registry

        Good for deciding between fast/cheap vs. smart/expensive models.

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

            # Classify the task to determine model needs
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

            # Determine recommendation
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

            # Find first available model
            recommended = None
            for alias in aliases_to_try:
                model = registry.get(alias, auto_create=False)
                if model:
                    recommended = alias
                    break

            # Build alternatives
            alternatives = []
            for name in registered[:5]:
                if name != recommended:
                    alternatives.append(name)

            return json.dumps(
                {
                    "task": task,
                    "constraints": constraints,
                    "recommendation": {
                        "model": recommended or "default",
                        "tier": tier,
                        "reasoning": reasoning,
                    },
                    "alternatives": alternatives,
                    "registered_models": registered,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "task": task}, indent=2)
