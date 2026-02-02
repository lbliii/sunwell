"""Time trinket - injects current timestamp.

Priority 0 (first), notification placement.
Not cacheable - always shows current time.
"""

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
)
from sunwell.foundation.utils.timestamps import absolute_timestamp_full


class TimeTrinket(BaseTrinket):
    """Injects current timestamp with absolute formatting.

    Uses first-person voice and absolute timestamps to avoid
    relative time references that become stale.

    Example output:
        Current time: On Feb 2 at 3:45 PM
    """

    def get_section_name(self) -> str:
        """Return unique identifier."""
        return "time"

    async def generate(self, context: TrinketContext) -> TrinketSection:
        """Generate time section.

        Always returns content (never None) since time is always relevant.
        """
        return TrinketSection(
            name="time",
            content=f"Current time: {absolute_timestamp_full()}",
            placement=TrinketPlacement.NOTIFICATION,
            priority=0,  # First in notification
            cacheable=False,  # Always refresh
        )
