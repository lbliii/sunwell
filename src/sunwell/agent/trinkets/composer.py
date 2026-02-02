"""Trinket composer - collects and assembles trinket sections into prompts.

The TrinketComposer is the central coordinator for the trinket system.
It maintains a registry of trinkets and composes their contributions
into a final prompt structure.

Key features:
- Graceful degradation: One failing trinket doesn't crash composition
- Caching: Cacheable sections are stored and reused
- Priority ordering: Sections sorted by priority within each placement
- Turn notifications: Trinkets can react to turn completion
"""

import logging
from dataclasses import dataclass, field

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
    TurnResult,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ComposedPrompt:
    """Result of trinket composition.

    Contains the assembled content for each placement type.
    """

    system: str
    """Content for the system prompt."""

    context: str
    """Content for the user context section."""

    notification: str
    """Content for the notification/sliding window."""

    @property
    def has_system(self) -> bool:
        """Whether there's system content to inject."""
        return bool(self.system.strip())

    @property
    def has_context(self) -> bool:
        """Whether there's context content to inject."""
        return bool(self.context.strip())

    @property
    def has_notification(self) -> bool:
        """Whether there's notification content to inject."""
        return bool(self.notification.strip())


@dataclass(slots=True)
class TrinketComposer:
    """Registry and composer for trinkets.

    Manages trinket registration, composition, and turn notifications.

    Example:
        composer = TrinketComposer()
        composer.register(TimeTrinket())
        composer.register(BriefingTrinket(briefing))

        # Compose prompt
        ctx = TrinketContext(task="Build API", workspace=Path("."))
        composed = await composer.compose(ctx)

        # Use composed prompt
        if composed.has_system:
            messages.append(Message(role="system", content=composed.system))

        # Notify after turn
        composer.notify_turn_complete(TurnResult(turn=1, success=True))
    """

    trinkets: list[BaseTrinket] = field(default_factory=list)
    """Registered trinkets."""

    _cache: dict[str, TrinketSection] = field(default_factory=dict, repr=False)
    """Cache for cacheable sections."""

    def register(self, trinket: BaseTrinket) -> None:
        """Register a trinket for composition.

        Args:
            trinket: The trinket to register.
        """
        self.trinkets.append(trinket)
        logger.debug("Registered trinket: %s", trinket.get_section_name())

    def unregister(self, name: str) -> bool:
        """Unregister a trinket by name.

        Args:
            name: The section name of the trinket to remove.

        Returns:
            True if a trinket was removed, False if not found.
        """
        for i, trinket in enumerate(self.trinkets):
            if trinket.get_section_name() == name:
                self.trinkets.pop(i)
                self._cache.pop(name, None)
                logger.debug("Unregistered trinket: %s", name)
                return True
        return False

    def clear_cache(self) -> None:
        """Clear the section cache."""
        self._cache.clear()

    async def compose(self, context: TrinketContext) -> ComposedPrompt:
        """Compose all trinkets into final prompt sections.

        Args:
            context: Context for trinket generation.

        Returns:
            ComposedPrompt with assembled content for each placement.
        """
        sections: list[TrinketSection] = []

        for trinket in self.trinkets:
            section_name = trinket.get_section_name()
            try:
                # Check cache first for cacheable sections
                if section_name in self._cache:
                    sections.append(self._cache[section_name])
                    continue

                # Generate new section
                section = await trinket.generate(context)

                if section and section.content:
                    sections.append(section)

                    # Cache if cacheable
                    if section.cacheable:
                        self._cache[section_name] = section
                        logger.debug("Cached trinket section: %s", section_name)

            except Exception as e:
                # Graceful degradation: log but don't crash
                logger.warning(
                    "Trinket %s failed during composition: %s",
                    section_name,
                    e,
                )

        # Sort by priority (lower = earlier)
        sections.sort(key=lambda s: s.priority)

        return ComposedPrompt(
            system=self._join_by_placement(sections, TrinketPlacement.SYSTEM),
            context=self._join_by_placement(sections, TrinketPlacement.CONTEXT),
            notification=self._join_by_placement(sections, TrinketPlacement.NOTIFICATION),
        )

    def notify_turn_complete(self, result: TurnResult) -> None:
        """Notify all trinkets of turn completion.

        Args:
            result: Information about the completed turn.
        """
        for trinket in self.trinkets:
            try:
                trinket.on_turn_complete(result)
            except Exception as e:
                logger.warning(
                    "Trinket %s failed during turn notification: %s",
                    trinket.get_section_name(),
                    e,
                )

    def notify_tool_executed(self, tool_name: str, success: bool) -> None:
        """Notify all trinkets of tool execution.

        Args:
            tool_name: Name of the tool that was executed.
            success: Whether the tool execution succeeded.
        """
        for trinket in self.trinkets:
            try:
                trinket.on_tool_executed(tool_name, success)
            except Exception as e:
                logger.warning(
                    "Trinket %s failed during tool notification: %s",
                    trinket.get_section_name(),
                    e,
                )

    def _join_by_placement(
        self,
        sections: list[TrinketSection],
        placement: TrinketPlacement,
    ) -> str:
        """Join sections for a specific placement.

        Args:
            sections: All collected sections.
            placement: The placement to filter by.

        Returns:
            Joined content string.
        """
        matching = [s for s in sections if s.placement == placement]
        if not matching:
            return ""

        return "\n\n".join(s.content for s in matching)

    @property
    def registered_names(self) -> list[str]:
        """Get names of all registered trinkets."""
        return [t.get_section_name() for t in self.trinkets]

    @property
    def cached_names(self) -> list[str]:
        """Get names of cached sections."""
        return list(self._cache.keys())
