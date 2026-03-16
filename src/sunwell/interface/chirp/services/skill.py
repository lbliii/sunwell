"""Skill and spell management service for Chirp interface."""

from pathlib import Path

from sunwell.skills.protocol import SkillRegistry
from sunwell.skills.research import ResearchSkill


def _build_registry() -> SkillRegistry:
    """Build registry with built-in executable skills."""
    registry = SkillRegistry()
    skill = ResearchSkill(workspace=Path.cwd(), tools=None, memory=None)
    registry.register(skill)
    return registry


class SkillService:
    """Service for skill/spell management."""

    def __init__(self) -> None:
        self._registry = _build_registry()

    def list_skills(self) -> list[dict]:
        """List all available executable skills.

        Returns:
            List of skill dicts with id, name, category, description, actions
        """
        result: list[dict] = []
        for skill in self._registry._skills.values():
            actions = [a.name for a in skill.get_actions()]
            result.append(
                {
                    "id": skill.name or skill.__class__.__name__.lower(),
                    "name": (skill.name or skill.__class__.__name__).replace("_", " ").title(),
                    "category": "executable",
                    "description": skill.description or "",
                    "actions": actions,
                }
            )
        return result

    def list_spells(self) -> list[dict]:
        """List all available spells.

        Returns:
            List of spell dicts with id, name, category, description
        """
        # TODO: Integrate with actual spell registry
        return [
            {
                "id": "quick-fix",
                "name": "Quick Fix",
                "category": "bug",
                "tags": ["bug", "fix"],
                "description": "Quick bug fix workflow",
            },
            {
                "id": "feature-add",
                "name": "Add Feature",
                "category": "feature",
                "tags": ["feature", "development"],
                "description": "Full feature implementation workflow",
            },
        ]
