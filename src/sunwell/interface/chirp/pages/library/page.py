"""Library page - Skills and Spells management - Using MCP tools."""

from chirp import App, Page
from sunwell.interface.chirp.services import SkillService


async def get(skill_svc: SkillService, app: App) -> Page:
    """Render library page showing available skills and spells.

    Now uses sunwell_list_lenses tool for lenses/expertise.
    """
    # Get traditional skills/spells from service
    skills = skill_svc.list_skills()
    spells = skill_svc.list_spells()

    # Get lenses from MCP tool
    if not app._frozen:
        app._freeze()

    lenses = []
    try:
        result = await app._tool_registry.call_tool("sunwell_list_lenses", {})
        # Tool returns dict directly (not string)
        data = result if isinstance(result, dict) else {}
        if "lenses" in data:
            lenses = data["lenses"]
    except Exception as e:
        print(f"Error calling sunwell_list_lenses tool: {e}")
        pass  # Fall back to empty list

    return Page(
        "library/page.html",
        "content",
        current_page="library",
        skills=skills,
        spells=spells,
        lenses=lenses,  # Add lenses from tool
        lens_count=len(lenses),
        title="Library",
    )
