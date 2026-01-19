"""Identity module - Adaptive behavioral learning for personalized interaction.

RFC-023: Two-tier learning system that captures both facts and behaviors:
- Facts → Inject into context for recall
- Behaviors → Digest into evolving identity prompt that shapes interaction

Key components:
- extractor: Two-tier extraction (facts vs behaviors) from user messages
- store: Identity storage with session/global persistence
- digest: Behavior → Identity synthesis with adaptive frequency
- injection: System prompt integration
"""

from sunwell.identity.digest import digest_identity
from sunwell.identity.extractor import extract_behaviors, extract_with_categories
from sunwell.identity.injection import build_system_prompt_with_identity
from sunwell.identity.store import Identity, IdentityStore, Observation

__all__ = [
    "Identity",
    "IdentityStore",
    "Observation",
    "extract_with_categories",
    "extract_behaviors",
    "digest_identity",
    "build_system_prompt_with_identity",
]
