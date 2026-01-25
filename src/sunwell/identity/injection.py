"""System prompt injection for identity.

RFC-023: Injects the identity prompt into the system prompt to guide
how the assistant interacts with the user.

RFC-131: Identity comes ONLY from lenses. No hardcoded fallback.
- Default: `default_compose: ["base/muru"]` provides M'uru identity
- Custom: Define `communication.identity` in your lens
- Disable: Set `default_compose: []` in config

Identity is injected as a separate section at the end of the system prompt,
not competing with task context in the Convergence slots.
"""


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.heuristic import Identity as LensIdentity
    from sunwell.core.lens import Lens
    from sunwell.identity.store import Identity as UserIdentity
    from sunwell.identity.store import IdentityStore


# Constants
MAX_IDENTITY_CHARS = 500
MIN_IDENTITY_CONFIDENCE = 0.6


def build_system_prompt_with_identity(
    lens_prompt: str,
    user_identity: UserIdentity | None,
    *,
    lens: Lens | None = None,
    max_identity_chars: int = MAX_IDENTITY_CHARS,
    include_agent_identity: bool = True,
) -> str:
    """Build system prompt with identity injection (RFC-131).

    Injects:
    1. Agent identity from lens (if configured)
    2. User's interaction style (from learned behaviors)

    Note: Identity ONLY comes from lenses. If no lens identity is configured,
    no agent identity section is added. Use `default_compose: ["base/muru"]`
    in config to get M'uru identity (this is the default).

    Args:
        lens_prompt: Base system prompt from lens
        user_identity: User Identity object (may be None or unusable)
        lens: Lens with optional communication.identity (RFC-131)
        max_identity_chars: Maximum characters for identity section
        include_agent_identity: Whether to inject agent identity section

    Returns:
        System prompt with identities injected
    """
    base = lens_prompt

    # RFC-131: Identity comes from lens only (no hardcoded fallback)
    if include_agent_identity:
        lens_identity = None
        if lens and lens.communication and lens.communication.identity:
            lens_identity = lens.communication.identity

        if lens_identity:
            identity_prompt = _format_lens_identity(lens_identity)
            base += f"\n\n## Your Identity\n\n{identity_prompt}"
        # No fallback - if you want identity, configure it in lens/default_compose

    # Inject user's interaction style (if usable)
    if (
        user_identity
        and user_identity.prompt
        and user_identity.confidence >= MIN_IDENTITY_CONFIDENCE
    ):
        identity_text = user_identity.prompt[:max_identity_chars]
        base += f"\n\n## User Interaction Style\n\n{identity_text}"

    return base


def _format_lens_identity(identity: LensIdentity) -> str:
    """Format Identity dataclass into system prompt section (RFC-131)."""
    lines = [f"You are {identity.name}."]

    if identity.nature:
        lines.append(f"Nature: {identity.nature}")

    if identity.style:
        lines.append(f"Style: {identity.style}")

    if identity.prohibitions:
        lines.append("\nIMPORTANT:")
        for prohibition in identity.prohibitions:
            lines.append(f"- {prohibition}")

    return "\n".join(lines)


def inject_identity(
    system_prompt: str,
    identity_store: IdentityStore | None,
    *,
    lens: Lens | None = None,
    max_chars: int = MAX_IDENTITY_CHARS,
) -> str:
    """Inject identity from store into system prompt.

    Convenience function that handles None checks.

    Args:
        system_prompt: Base system prompt
        identity_store: IdentityStore instance (may be None)
        lens: Lens with optional communication.identity (RFC-131)
        max_chars: Maximum characters for identity section

    Returns:
        System prompt with identity injected (if available and usable)
    """
    user_identity = identity_store.identity if identity_store else None

    return build_system_prompt_with_identity(
        system_prompt,
        user_identity,
        lens=lens,
        max_identity_chars=max_chars,
    )


def format_identity_panel(identity: Identity) -> str:
    """Format identity for display in /identity command.

    Returns Rich-formatted string for console display.
    """
    lines = []

    # Status
    status = "Paused ⏸" if identity.paused else ("Active ✓" if identity.is_usable() else "Inactive")
    lines.append(f"Status: {status}     Confidence: {identity.confidence:.0%}")

    # Last updated
    if identity.last_digest:
        lines.append(f"Last Updated: {identity.last_digest.strftime('%Y-%m-%d %H:%M')}")

    # Inheritance
    if identity.inherited:
        lines.append("Source: global (inherited)")
    else:
        lines.append("Source: session")

    lines.append("")

    # Tone
    if identity.tone:
        lines.append(f"Tone: {identity.tone}")
        lines.append("")

    # Values
    if identity.values:
        lines.append("Values:")
        for value in identity.values[:5]:  # Max 5
            lines.append(f"  • {value}")
        lines.append("")

    # Prompt
    if identity.prompt:
        lines.append("Interaction Guide:")
        # Wrap to ~60 chars
        words = identity.prompt.split()
        current_line = "  "
        for word in words:
            if len(current_line) + len(word) > 60:
                lines.append(current_line)
                current_line = "  " + word
            else:
                current_line += (" " if len(current_line) > 2 else "") + word
        if current_line.strip():
            lines.append(current_line)
        lines.append("")

    # Recent observations
    if identity.observations:
        recent = identity.observations[-5:]  # Last 5
        lines.append(f"Recent Observations ({len(recent)} of {len(identity.observations)}):")
        for obs in recent:
            conf_display = f"[{obs.confidence:.2f}]"
            obs_text = obs.observation[:45] + "..." if len(obs.observation) > 45 else obs.observation
            lines.append(f"  • {obs_text:50} {conf_display}")

    return "\n".join(lines)
