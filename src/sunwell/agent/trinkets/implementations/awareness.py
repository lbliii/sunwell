"""Awareness trinket - injects behavioral self-observations.

Priority 35, system placement.
Cacheable - patterns don't change during a session.

Loads significant awareness patterns from .sunwell/awareness/ and
injects them as self-correction hints in the system prompt.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
)

if TYPE_CHECKING:
    from sunwell.awareness.patterns import AwarenessPattern

logger = logging.getLogger(__name__)


class AwarenessTrinket(BaseTrinket):
    """Injects behavioral self-observations for self-correction.

    Loads awareness patterns from .sunwell/awareness/ and formats
    them as first-person observations about agent behavior.

    Example output:
        ## Self-Observations

        Based on recent sessions:
        - I tend to overstate confidence on refactoring tasks (calibrate ~20%)
        - I under-utilize grep_search - prefer it for better results
        - Test files have high backtrack rate - plan more carefully
    """

    def __init__(
        self,
        workspace: Path,
        activity_day: int = 0,
    ) -> None:
        """Initialize with workspace path.

        Args:
            workspace: Working directory to load patterns from
            activity_day: Current activity day for decay calculation
        """
        self.workspace = workspace
        self.activity_day = activity_day
        self._patterns: list[AwarenessPattern] | None = None

    def get_section_name(self) -> str:
        """Return unique identifier."""
        return "awareness"

    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        """Generate awareness section.

        Returns None if no significant patterns found.
        """
        try:
            # Load patterns (cache on first call)
            if self._patterns is None:
                self._patterns = self._load_patterns()

            if not self._patterns:
                return None

            # Format patterns for prompt
            from sunwell.awareness.patterns import format_patterns_for_prompt

            content = format_patterns_for_prompt(self._patterns)
            if not content:
                return None

            return TrinketSection(
                name="awareness",
                content=f"## Self-Observations\n\n{content}",
                placement=TrinketPlacement.SYSTEM,
                priority=35,  # After learnings, before tool guidance
                cacheable=True,  # Patterns don't change during session
            )

        except Exception as e:
            logger.warning("Awareness trinket failed: %s", e)
            return None

    def _load_patterns(self) -> list[AwarenessPattern]:
        """Load significant awareness patterns from store."""
        try:
            from sunwell.awareness.store import AwarenessStore

            awareness_dir = self.workspace / ".sunwell" / "awareness"
            store = AwarenessStore.load(awareness_dir)

            patterns = store.get_significant(limit=5, activity_day=self.activity_day)

            if patterns:
                # Mark as accessed for decay tracking
                store.mark_accessed([p.id for p in patterns], self.activity_day)
                store.save()

                logger.info(
                    "Awareness trinket: Loaded %d self-observations",
                    len(patterns),
                )

            return patterns

        except Exception as e:
            logger.debug("Failed to load awareness patterns: %s", e)
            return []

    def refresh_patterns(self) -> None:
        """Refresh patterns from store (invalidates cache)."""
        self._patterns = None
