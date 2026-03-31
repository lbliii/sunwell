"""Executable skills - Python modules as agent tools."""

from pathlib import Path

from sunwell.skills.protocol import Skill, SkillRegistry, skill_action
from sunwell.skills.research import ResearchSkill
from sunwell.skills.runtime import (
    SkillCatalogSummary,
    SkillExecutor,
    SkillToolSummary,
)

__all__ = [
    "Skill",
    "SkillCatalogSummary",
    "SkillExecutor",
    "SkillToolSummary",
    "SkillRegistry",
    "ResearchSkill",
    "create_default_skill_executor",
    "skill_action",
]


def create_default_skill_executor(
    workspace: Path | str,
    web_search_handler=None,  # WebSearchHandler | None
    memory=None,  # PersistentMemory | None
) -> SkillExecutor | None:
    """Create SkillExecutor with built-in skills (ResearchSkill).

    Returns None if no web search handler (ResearchSkill requires it).
    """
    if not web_search_handler:
        return None

    ws = Path(workspace) if isinstance(workspace, str) else workspace
    registry = SkillRegistry()
    skill = ResearchSkill(workspace=ws, tools=web_search_handler, memory=memory)
    registry.register(skill)

    return SkillExecutor(
        registry=registry,
        workspace=ws,
        web_search_handler=web_search_handler,
        memory=memory,
    )
