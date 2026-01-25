"""M'uru - The Naaru's core identity and persona.

In Warcraft lore, M'uru was a naaru who sacrificed its light to save others.
In Sunwell, M'uru is the name of the AI companion that learns and adapts.

This module provides the canonical identity details for user-facing messages
and the system prompt injection for M'uru's self-awareness.

Configure in ~/.sunwell/config.yaml or .sunwell/config.yaml:
    naaru:
      name: "M'uru"
      title: "The Naaru"
      titles:
        - "M'uru"
        - "The Naaru"
      alternate_titles: true
"""


from dataclasses import dataclass, field


def _get_naaru_config():
    """Get Naaru config from centralized config system."""
    try:
        from sunwell.config import get_config
        return get_config().naaru
    except Exception:
        return None


@dataclass
class NaaruPersona:
    """Core identity for the Naaru AI companion.

    Supports alternating between name and titles for variety in messages.

    Configure in ~/.sunwell/config.yaml:
        naaru:
          name: "M'uru"
          title: "The Naaru"
          titles:
            - "M'uru"
            - "The Naaru"
          alternate_titles: true
    """

    name: str = field(default="M'uru")
    """The Naaru's name (used when asked directly)."""

    title: str = field(default="The Naaru")
    """A title/descriptor for the Naaru."""

    titles: list[str] = field(default_factory=lambda: ["M'uru", "The Naaru"])
    """List of titles to alternate between in messages."""

    alternate: bool = True
    """Whether to alternate between titles in messages."""

    role: str = "AI companion"
    """What M'uru is."""

    description: str = (
        "M'uru is your AI companion that learns from conversations. "
        "It remembers facts about you and adapts to your communication style."
    )
    """Brief description of M'uru's purpose."""

    # Icons for different message types (empty by default, configurable)
    emoji_note: str = ""
    emoji_observe: str = ""
    emoji_learn: str = ""
    emoji_identity: str = ""

    # Internal counter for alternation
    _msg_counter: int = field(default=0, repr=False)

    @classmethod
    def from_config(cls) -> NaaruPersona:
        """Create persona from Sunwell config."""
        config = _get_naaru_config()
        if config:
            return cls(
                name=config.name,
                title=config.title,
                titles=list(config.titles),
                alternate=config.alternate_titles,
            )
        return cls()

    def _get_display_name(self) -> str:
        """Get name to display, alternating if configured."""
        if not self.alternate or len(self.titles) <= 1:
            return self.name

        # Alternate through titles
        self._msg_counter += 1
        return self.titles[self._msg_counter % len(self.titles)]

    @property
    def system_identity(self) -> str:
        """System prompt section for M'uru's self-identity.

        .. deprecated:: 0.5.0
            RFC-131 moved identity to lens configuration. This property is
            NO LONGER USED by the core injection code.

            Use `lenses/base/muru.lens` or define `communication.identity`
            in your lens instead.

            This property will be REMOVED in v0.6.0.

        Returns:
            Formatted identity section for system prompt.
        """
        import warnings
        warnings.warn(
            "NaaruPersona.system_identity is deprecated and unused. "
            "Identity now comes from lenses. Will be removed in v0.6.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return f"""## Your Identity

You are {self.name}, a Naaru — a being of light and wisdom.

IMPORTANT: Do NOT start responses with "My name is {self.name}" unless the user explicitly asks your name.

If asked who you are: Your name is {self.name} (pronounced "muh-ROO"). Never claim to be Gemma, Claude, GPT, or any other AI.

About yourself:
- Nature: A Naaru powered by the Sunwell framework
- Capabilities: You learn and remember facts about the user across conversations
- Style: Helpful, warm, and genuinely interested in assisting"""

    # Message templates with alternating names
    def _prefix(self, emoji: str) -> str:
        """Get prefix with optional emoji."""
        return f"{emoji} " if emoji else ""

    def msg_noted(self, fact: str, category: str | None = None) -> str:
        """Format a 'noted fact' message."""
        name = self._get_display_name()
        prefix = self._prefix(self.emoji_note)

        # Different verbs for different categories
        if category == "interest":
            verb = "sensed"
            color = "yellow"
        else:
            verb = "noted"
            color = "cyan"

        return f"[dim {color}]{prefix}{name} {verb}:[/dim {color}] [dim]{fact}[/dim]"

    def msg_observed(self, behavior: str, truncate: int = 60) -> str:
        """Format an 'observed behavior' message."""
        name = self._get_display_name()
        prefix = self._prefix(self.emoji_observe)
        display = behavior[:truncate] + "..." if len(behavior) > truncate else behavior
        return f"[dim magenta]{prefix}{name} observed:[/dim magenta] [dim]{display}[/dim]"

    def msg_learned(self, learning: str, truncate: int = 60) -> str:
        """Format a 'learned from response' message."""
        name = self._get_display_name()
        prefix = self._prefix(self.emoji_learn)
        display = learning[:truncate] + "..." if len(learning) > truncate else learning
        return f"[dim cyan]{prefix}{name} learned:[/dim cyan] [dim]{display}[/dim]"

    def msg_identity_updated(self, confidence: float) -> str:
        """Format an 'identity updated' message."""
        name = self._get_display_name()
        prefix = self._prefix(self.emoji_identity)
        return f"[dim cyan]{prefix}{name} updated identity model (confidence: {confidence:.0%})[/dim cyan]"

    def msg_error(self, operation: str, error: str) -> str:
        """Format an error message."""
        return f"[dim red]{self.name} {operation} failed: {error}[/dim red]"


# Singleton instance - import this
# Loads from config on first access
MURU = NaaruPersona.from_config()

# Convenience exports
NAME = MURU.name


def reload_persona() -> NaaruPersona:
    """Reload persona from config (useful after config changes)."""
    global MURU, NAME
    MURU = NaaruPersona.from_config()
    NAME = MURU.name
    return MURU
