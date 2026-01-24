"""Team Configuration - RFC-052.

Configuration options for team intelligence features.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TeamSyncConfig:
    """Synchronization settings."""

    auto_commit: bool = True
    """Commit changes automatically."""

    auto_push: bool = False
    """Push requires explicit action."""

    pull_on_start: bool = True
    """Pull team knowledge on session start."""

    notify_new_knowledge: bool = True
    """Notify about new team knowledge."""


@dataclass
class TeamSharingConfig:
    """What knowledge is shared."""

    decisions: bool = True
    """Share architectural decisions."""

    failures: bool = True
    """Share failure patterns."""

    patterns: bool = True
    """Share code patterns."""

    ownership: bool = True
    """Share ownership mapping."""


@dataclass
class TeamPrivacyConfig:
    """Privacy boundaries."""

    share_session_history: bool = False
    """Never share conversations (RFC-013 stays local)."""

    share_personal_prefs: bool = False
    """Keep preferences local."""

    anonymize_failures: bool = False
    """Include author names in failures."""


@dataclass
class TeamConflictConfig:
    """Conflict handling settings."""

    auto_merge_compatible: bool = True
    """Auto-merge non-conflicting changes."""

    prefer_newer: bool = False
    """Don't auto-resolve by timestamp."""

    require_review: bool = True
    """Escalate true conflicts for human review."""


@dataclass
class TeamOnboardingConfig:
    """Onboarding settings."""

    show_summary_on_init: bool = True
    """Show team knowledge summary on init."""

    interactive_tour: bool = False
    """Skip interactive onboarding by default."""


@dataclass
class TeamEnforcementConfig:
    """Enforcement settings."""

    patterns: Literal["suggest", "warn", "enforce"] = "warn"
    """How strictly to apply team patterns."""

    decisions: Literal["suggest", "warn", "enforce"] = "warn"
    """How strictly to apply team decisions."""


@dataclass
class TeamConfig:
    """Complete team intelligence configuration.

    Example sunwell.yaml:

    ```yaml
    team:
      enabled: true
      sync:
        auto_commit: true
        auto_push: false
        pull_on_start: true
        notify_new_knowledge: true
      sharing:
        decisions: true
        failures: true
        patterns: true
        ownership: true
      privacy:
        share_session_history: false
        share_personal_prefs: false
        anonymize_failures: false
      conflicts:
        auto_merge_compatible: true
        prefer_newer: false
        require_review: true
      onboarding:
        show_summary_on_init: true
        interactive_tour: false
      enforcement:
        patterns: warn
        decisions: warn
    ```
    """

    enabled: bool = True
    """Whether team intelligence is enabled."""

    sync: TeamSyncConfig = field(default_factory=TeamSyncConfig)
    sharing: TeamSharingConfig = field(default_factory=TeamSharingConfig)
    privacy: TeamPrivacyConfig = field(default_factory=TeamPrivacyConfig)
    conflicts: TeamConflictConfig = field(default_factory=TeamConflictConfig)
    onboarding: TeamOnboardingConfig = field(default_factory=TeamOnboardingConfig)
    enforcement: TeamEnforcementConfig = field(default_factory=TeamEnforcementConfig)

    @classmethod
    def from_dict(cls, data: dict) -> TeamConfig:
        """Create TeamConfig from dictionary (e.g., from YAML).

        Args:
            data: Configuration dictionary

        Returns:
            TeamConfig instance
        """
        return cls(
            enabled=data.get("enabled", True),
            sync=TeamSyncConfig(**data.get("sync", {})),
            sharing=TeamSharingConfig(**data.get("sharing", {})),
            privacy=TeamPrivacyConfig(**data.get("privacy", {})),
            conflicts=TeamConflictConfig(**data.get("conflicts", {})),
            onboarding=TeamOnboardingConfig(**data.get("onboarding", {})),
            enforcement=TeamEnforcementConfig(**data.get("enforcement", {})),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization.

        Returns:
            Configuration dictionary
        """
        return {
            "enabled": self.enabled,
            "sync": {
                "auto_commit": self.sync.auto_commit,
                "auto_push": self.sync.auto_push,
                "pull_on_start": self.sync.pull_on_start,
                "notify_new_knowledge": self.sync.notify_new_knowledge,
            },
            "sharing": {
                "decisions": self.sharing.decisions,
                "failures": self.sharing.failures,
                "patterns": self.sharing.patterns,
                "ownership": self.sharing.ownership,
            },
            "privacy": {
                "share_session_history": self.privacy.share_session_history,
                "share_personal_prefs": self.privacy.share_personal_prefs,
                "anonymize_failures": self.privacy.anonymize_failures,
            },
            "conflicts": {
                "auto_merge_compatible": self.conflicts.auto_merge_compatible,
                "prefer_newer": self.conflicts.prefer_newer,
                "require_review": self.conflicts.require_review,
            },
            "onboarding": {
                "show_summary_on_init": self.onboarding.show_summary_on_init,
                "interactive_tour": self.onboarding.interactive_tour,
            },
            "enforcement": {
                "patterns": self.enforcement.patterns,
                "decisions": self.enforcement.decisions,
            },
        }
