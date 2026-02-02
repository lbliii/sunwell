"""Briefing trinket - injects session orientation.

Priority 10 (early), system placement.
Cacheable - briefing doesn't change mid-conversation.
"""

from typing import TYPE_CHECKING

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
)

if TYPE_CHECKING:
    from sunwell.memory.briefing.briefing import Briefing


class BriefingTrinket(BaseTrinket):
    """Injects briefing state for session orientation.

    The briefing provides instant orientation at session start:
    - Mission: What we're trying to accomplish
    - Status: Current state (in_progress, blocked, etc.)
    - Progress: Where we are
    - Last/Next action: Momentum indicators
    - Hazards: What to avoid
    - Focus files: Where to look

    Uses first-person voice for reduced epistemic distance.

    Example output:
        ## Where I Am (Briefing)

        **My Mission**: Implement user authentication
        **Status**: In Progress
        **Where I am**: I've completed the login endpoint.
        **What I just did**: I added JWT token validation.
        **What I'll do next**: I'll implement the logout endpoint.
    """

    def __init__(self, briefing: Briefing | None) -> None:
        """Initialize with optional briefing.

        Args:
            briefing: The briefing to inject, or None.
        """
        self.briefing = briefing

    def get_section_name(self) -> str:
        """Return unique identifier."""
        return "briefing"

    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        """Generate briefing section.

        Returns None if no briefing is available.
        """
        if not self.briefing:
            return None

        return TrinketSection(
            name="briefing",
            content=self.briefing.to_prompt(),
            placement=TrinketPlacement.SYSTEM,
            priority=10,  # Early - orientation first
            cacheable=True,  # Briefing doesn't change mid-conversation
        )

    def update_briefing(self, briefing: Briefing | None) -> None:
        """Update the briefing.

        Call this if the briefing changes during the session.

        Args:
            briefing: The new briefing, or None.
        """
        self.briefing = briefing
