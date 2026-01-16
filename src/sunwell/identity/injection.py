"""System prompt injection for identity.

RFC-023: Injects the identity prompt into the system prompt to guide
how the assistant interacts with the user.

Identity is injected as a separate section at the end of the system prompt,
not competing with task context in the Convergence slots.

Also injects M'uru's self-identity so it knows its own name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.identity.store import Identity, IdentityStore


# Constants
MAX_IDENTITY_CHARS = 500
MIN_IDENTITY_CONFIDENCE = 0.6


def build_system_prompt_with_identity(
    lens_prompt: str,
    identity: "Identity | None",
    *,
    max_identity_chars: int = MAX_IDENTITY_CHARS,
    include_muru_identity: bool = True,
) -> str:
    """Build system prompt with identity injection.
    
    Injects both:
    1. M'uru's self-identity (so it knows its name)
    2. User's interaction style (from learned behaviors)
    
    Args:
        lens_prompt: Base system prompt from lens
        identity: Identity object (may be None or unusable)
        max_identity_chars: Maximum characters for identity section
        include_muru_identity: Whether to inject M'uru's self-identity
    
    Returns:
        System prompt with identities injected
    """
    from sunwell.naaru.persona import MURU
    
    base = lens_prompt
    
    # Inject M'uru's self-identity (so it knows its name)
    if include_muru_identity:
        base += f"\n\n{MURU.system_identity}"
    
    # Inject user's interaction style (if usable)
    if identity and identity.prompt and identity.confidence >= MIN_IDENTITY_CONFIDENCE:
        identity_text = identity.prompt[:max_identity_chars]
        base += f"\n\n## User Interaction Style\n\n{identity_text}"
    
    return base


def inject_identity(
    system_prompt: str,
    identity_store: "IdentityStore | None",
    *,
    max_chars: int = MAX_IDENTITY_CHARS,
) -> str:
    """Inject identity from store into system prompt.
    
    Convenience function that handles None checks.
    
    Args:
        system_prompt: Base system prompt
        identity_store: IdentityStore instance (may be None)
        max_chars: Maximum characters for identity section
    
    Returns:
        System prompt with identity injected (if available and usable)
    """
    if not identity_store:
        return system_prompt
    
    return build_system_prompt_with_identity(
        system_prompt,
        identity_store.identity,
        max_identity_chars=max_chars,
    )


def format_identity_panel(identity: "Identity") -> str:
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
