"""Team Intelligence - RFC-052: Shared Knowledge Across Developers.

Team Intelligence enables multiple developers to share Sunwell's accumulated
knowledge — decisions, patterns, failures, and codebase understanding — across
a team. Instead of each developer's Sunwell instance learning independently,
teams benefit from collective intelligence.

Design: Git-based synchronization. Shared intelligence is stored in the
repository (`.sunwell/team/`), while personal preferences remain local.
This leverages existing workflows (PR review, branch merging) and requires
zero infrastructure.

Components:
- TeamKnowledgeStore: Git-tracked storage for decisions, failures, patterns
- ConflictResolver: Handle merge conflicts in team knowledge
- KnowledgePropagator: Promote personal knowledge to team
- UnifiedIntelligence: Combine team + personal + project knowledge
- TeamOnboarding: Welcome new members with accumulated wisdom

See: RFC-052-team-intelligence.md
"""

from sunwell.team.config import TeamConfig
from sunwell.team.conflicts import ConflictResolver, KnowledgeConflict
from sunwell.team.gitignore_template import (
    SUNWELL_GITIGNORE,
    create_sunwell_gitignore,
    ensure_sunwell_structure,
)
from sunwell.team.onboarding import OnboardingSummary, TeamOnboarding
from sunwell.team.propagation import KnowledgePropagator
from sunwell.team.store import SyncResult, TeamKnowledgeStore
from sunwell.team.types import (
    Embeddable,
    KnowledgeScope,
    RejectedOption,
    Serializable,
    TeamDecision,
    TeamFailure,
    TeamKnowledgeContext,
    TeamKnowledgeUpdate,
    TeamOwnership,
    TeamPatterns,
)
from sunwell.team.unified import ApproachCheck, ApproachWarning, FileContext, UnifiedIntelligence

__all__ = [
    # Protocols
    "Serializable",
    "Embeddable",
    # Types
    "KnowledgeScope",
    "RejectedOption",
    "TeamDecision",
    "TeamFailure",
    "TeamPatterns",
    "TeamOwnership",
    "TeamKnowledgeContext",
    "TeamKnowledgeUpdate",
    # Store
    "TeamKnowledgeStore",
    "SyncResult",
    # Conflicts
    "ConflictResolver",
    "KnowledgeConflict",
    # Propagation
    "KnowledgePropagator",
    # Unified
    "UnifiedIntelligence",
    "ApproachCheck",
    "ApproachWarning",
    "FileContext",
    # Onboarding
    "TeamOnboarding",
    "OnboardingSummary",
    # Config
    "TeamConfig",
    # Gitignore
    "SUNWELL_GITIGNORE",
    "create_sunwell_gitignore",
    "ensure_sunwell_structure",
]
