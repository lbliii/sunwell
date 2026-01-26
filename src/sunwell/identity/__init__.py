"""Identity module - Adaptive behavioral learning for personalized interaction.

RFC-023: Two-tier learning system that captures both facts and behaviors:
- Facts → Inject into context for recall
- Behaviors → Digest into evolving identity prompt that shapes interaction

Key components:
- extraction: Two-tier extraction (facts vs behaviors) from user messages
- store: Identity storage with session/global persistence
- synthesis: Behavior → Identity synthesis with adaptive frequency
- injection: System prompt integration
"""

# Core models
from sunwell.identity.core.models import Identity, Observation

# Extraction
from sunwell.identity.extraction import extract_behaviors, extract_with_categories

# Injection
from sunwell.identity.injection import build_system_prompt_with_identity

# Storage
from sunwell.identity.store import IdentityStore

# Synthesis
from sunwell.identity.synthesis import digest_identity

__all__ = [
    # Core
    "Identity",
    "IdentityStore",
    "Observation",
    # Extraction
    "extract_with_categories",
    "extract_behaviors",
    # Synthesis
    "digest_identity",
    # Injection
    "build_system_prompt_with_identity",
]
