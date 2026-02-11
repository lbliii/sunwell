"""Library page - Skills and Spells management."""

from chirp import Page
from sunwell.interface.chirp.services import SkillService


def get(skill_svc: SkillService) -> Page:
    """Render library page showing available skills and spells."""
    skills = skill_svc.list_skills()
    spells = skill_svc.list_spells()

    return Page(
        "library/page.html",
        "content",
        current_page="library",
        skills=skills,
        spells=spells,
        title="Library",
    )
