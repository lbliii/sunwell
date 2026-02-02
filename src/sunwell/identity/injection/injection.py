"""System prompt injection for identity.

RFC-023: Injects the identity prompt into the system prompt to guide
how the assistant interacts with the user.

RFC-131: Identity comes ONLY from lenses. No hardcoded fallback.
- Default: `default_compose: ["base/muru"]` provides M'uru identity
- Custom: Define `communication.identity` in your lens
- Disable: Set `default_compose: []` in config

Identity is injected as a separate section at the end of the system prompt,
not competing with task context in the Convergence slots.

Awareness patterns (behavioral self-observations) are also injected here
as a "Self-Observations" section for self-correction hints.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.awareness.patterns import AwarenessPattern
    from sunwell.core.models.heuristic import Identity as LensIdentity
    from sunwell.foundation.core.lens import Lens
    from sunwell.identity.core.models import Identity as UserIdentity

from sunwell.identity.core.constants import (
    MAX_IDENTITY_PROMPT_LENGTH,
    MIN_IDENTITY_CONFIDENCE,
)


def build_system_prompt_with_identity(
    lens_prompt: str,
    user_identity: UserIdentity | None,
    *,
    lens: Lens | None = None,
    awareness_patterns: list[AwarenessPattern] | None = None,
    max_identity_chars: int = MAX_IDENTITY_PROMPT_LENGTH,
    include_agent_identity: bool = True,
) -> str:
    """Build system prompt with identity injection (RFC-131).

    Injects:
    1. Agent identity from lens (if configured)
    2. User's interaction style (from learned behaviors)
    3. Self-observations from awareness patterns (behavioral hints)

    Note: Identity ONLY comes from lenses. If no lens identity is configured,
    no agent identity section is added. Use `default_compose: ["base/muru"]`
    in config to get M'uru identity (this is the default).

    Args:
        lens_prompt: Base system prompt from lens
        user_identity: User Identity object (may be None or unusable)
        lens: Lens with optional communication.identity (RFC-131)
        awareness_patterns: Behavioral patterns for self-correction hints
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

    # Inject awareness patterns (self-observations)
    if awareness_patterns:
        awareness_text = _format_awareness_patterns(awareness_patterns)
        if awareness_text:
            base += f"\n\n## Self-Observations\n\n{awareness_text}"

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


def _format_awareness_patterns(patterns: list[AwarenessPattern]) -> str:
    """Format awareness patterns for system prompt injection.

    Args:
        patterns: Behavioral patterns to format

    Returns:
        Formatted string for system prompt, or empty if no significant patterns
    """
    from sunwell.awareness.patterns import format_patterns_for_prompt
    return format_patterns_for_prompt(patterns)


