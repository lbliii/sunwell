"""Executable skill protocol: Skill base class, @skill_action, SkillRegistry.

Skills are Python modules that expose callable actions as agent tools.
Each @skill_action becomes a tool the agent can invoke.
"""

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_type_hints

from sunwell.models import Tool

logger = logging.getLogger(__name__)


def _action_to_json_schema(method: Callable[..., Any]) -> dict[str, Any]:
    """Build JSON Schema for a skill action from its signature."""
    sig = inspect.signature(method)
    params: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        hint = get_type_hints(method).get(name, str)
        if hasattr(hint, "__origin__"):
            # Handle Optional, Union
            pass

        prop: dict[str, Any] = {"type": "string"}
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
            params["properties"][name] = prop
        else:
            params["properties"][name] = prop
            params["required"].append(name)

    return params


def skill_action(method: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator marking a skill method as an invokable action (agent tool)."""
    method._skill_action = True
    return method


def is_skill_action(method: Callable[..., Any]) -> bool:
    """Check if method is marked as a skill action."""
    return getattr(method, "_skill_action", False)


@dataclass(frozen=True, slots=True)
class SkillActionDef:
    """Definition of a skill action (tool)."""

    name: str
    description: str
    method_name: str
    parameters_schema: dict[str, Any]


class Skill:
    """Base class for executable skills.

    Subclasses define name, description, tools_required, and @skill_action methods.
    Each skill action becomes a callable tool for the agent.
    """

    name: str = ""
    description: str = ""
    tools_required: tuple[str, ...] = ()

    def __init__(
        self,
        workspace: Path | None = None,
        tools: Any = None,
        memory: Any = None,
    ) -> None:
        self.workspace = workspace or Path.cwd()
        self._tools = tools
        self._memory = memory

    def get_actions(self) -> list[SkillActionDef]:
        """Return action definitions for this skill."""
        actions: list[SkillActionDef] = []
        for attr_name in dir(type(self)):
            if attr_name.startswith("_"):
                continue
            attr = getattr(type(self), attr_name)
            if callable(attr) and is_skill_action(attr):
                schema = _action_to_json_schema(attr)
                doc = (attr.__doc__ or "").strip().split("\n")[0]
                actions.append(
                    SkillActionDef(
                        name=attr_name,
                        description=doc or f"Execute {attr_name}",
                        method_name=attr_name,
                        parameters_schema=schema,
                    )
                )
        return actions

    def to_tools(self) -> list[Tool]:
        """Convert skill actions to Tool definitions for the agent."""
        tools: list[Tool] = []
        for action in self.get_actions():
            tools.append(
                Tool(
                    name=action.name,
                    description=action.description,
                    parameters=action.parameters_schema,
                )
            )
        return tools


class SkillRegistry:
    """Registry of executable skills."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill instance."""
        name = skill.name or skill.__class__.__name__
        self._skills[name] = skill
        logger.debug("Registered skill: %s", name)

    def get(self, name: str) -> Skill | None:
        """Get skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """List registered skill names."""
        return list(self._skills)

    def get_all_tools(self) -> list[Tool]:
        """Get all Tool definitions from all skills."""
        tools: list[Tool] = []
        for skill in self._skills.values():
            tools.extend(skill.to_tools())
        return tools

    def get_tool_names(self) -> frozenset[str]:
        """Get set of all tool names from skill actions."""
        names: set[str] = set()
        for skill in self._skills.values():
            for action in skill.get_actions():
                names.add(action.name)
        return frozenset(names)
