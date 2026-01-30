"""Auto-approve configuration for adaptive trust.

Stores user decisions about which intent paths should be
automatically approved without confirmation checkpoints.

Storage: .sunwell/trust/auto-approve.yaml
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sunwell.agent.intent.dag import IntentNode, IntentPath

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AutoApproveRule:
    """A rule specifying an intent path that should be auto-approved.

    Attributes:
        intent_path: The DAG path to auto-approve, e.g., ("ACT", "WRITE", "CREATE")
        created_at: When the rule was created
        approval_count_at_creation: How many approvals triggered this rule
        enabled: Whether the rule is currently active
    """

    intent_path: tuple[str, ...]
    created_at: datetime
    approval_count_at_creation: int
    enabled: bool = True

    def to_dict(self) -> dict:
        """Serialize to dictionary for YAML storage."""
        return {
            "intent_path": list(self.intent_path),
            "created_at": self.created_at.isoformat(),
            "approval_count_at_creation": self.approval_count_at_creation,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AutoApproveRule":
        """Deserialize from dictionary."""
        return cls(
            intent_path=tuple(data["intent_path"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            approval_count_at_creation=data.get("approval_count_at_creation", 0),
            enabled=data.get("enabled", True),
        )


@dataclass
class AutoApproveConfig:
    """Configuration for auto-approved intent paths.

    Manages the set of intent paths that should skip confirmation
    checkpoints based on user decisions.

    Thread-safe for concurrent access.

    Example:
        >>> config = AutoApproveConfig(workspace)
        >>> config.add_rule(path, approval_count=15)
        >>> if config.should_auto_approve(path):
        ...     # Skip confirmation checkpoint
        ...     pass
    """

    workspace: Path
    """Workspace root directory."""

    _rules: dict[tuple[str, ...], AutoApproveRule] = field(
        default_factory=dict, init=False
    )
    """In-memory rule cache."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Thread safety lock."""

    _loaded: bool = field(default=False, init=False)
    """Whether rules have been loaded from disk."""

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace)

    @property
    def _config_path(self) -> Path:
        """Path to auto-approve configuration file."""
        return self.workspace / ".sunwell" / "trust" / "auto-approve.yaml"

    def _ensure_loaded(self) -> None:
        """Load rules from disk if not already loaded."""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            if self._config_path.exists():
                try:
                    with open(self._config_path) as f:
                        data = yaml.safe_load(f) or {}

                    rules_data = data.get("rules", [])
                    for rule_data in rules_data:
                        rule = AutoApproveRule.from_dict(rule_data)
                        self._rules[rule.intent_path] = rule

                    logger.debug(
                        "Loaded %d auto-approve rules from %s",
                        len(self._rules),
                        self._config_path,
                    )
                except Exception as e:
                    logger.warning("Failed to load auto-approve config: %s", e)

            self._loaded = True

    def _save(self) -> None:
        """Save all rules to disk."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "rules": [rule.to_dict() for rule in self._rules.values()],
            }

            with open(self._config_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        except Exception as e:
            logger.warning("Failed to save auto-approve config: %s", e)

    def _path_to_key(self, path: IntentPath) -> tuple[str, ...]:
        """Convert IntentPath to storage key (tuple of node values)."""
        return tuple(node.value for node in path)

    def add_rule(
        self,
        path: IntentPath,
        approval_count: int = 0,
    ) -> AutoApproveRule:
        """Add an auto-approve rule for a path.

        Args:
            path: The intent DAG path to auto-approve
            approval_count: Number of approvals at time of rule creation

        Returns:
            The created AutoApproveRule
        """
        self._ensure_loaded()
        key = self._path_to_key(path)

        rule = AutoApproveRule(
            intent_path=key,
            created_at=datetime.now(timezone.utc),
            approval_count_at_creation=approval_count,
            enabled=True,
        )

        with self._lock:
            self._rules[key] = rule
            self._save()

        logger.info("Added auto-approve rule for path: %s", key)
        return rule

    def remove_rule(self, path: IntentPath) -> bool:
        """Remove an auto-approve rule.

        Args:
            path: The intent DAG path to remove

        Returns:
            True if rule was removed, False if it didn't exist
        """
        self._ensure_loaded()
        key = self._path_to_key(path)

        with self._lock:
            if key in self._rules:
                del self._rules[key]
                self._save()
                logger.info("Removed auto-approve rule for path: %s", key)
                return True

        return False

    def disable_rule(self, path: IntentPath) -> bool:
        """Disable an auto-approve rule without removing it.

        Args:
            path: The intent DAG path to disable

        Returns:
            True if rule was disabled, False if it didn't exist
        """
        self._ensure_loaded()
        key = self._path_to_key(path)

        with self._lock:
            if key in self._rules:
                old_rule = self._rules[key]
                # Create new rule with enabled=False (frozen dataclass)
                self._rules[key] = AutoApproveRule(
                    intent_path=old_rule.intent_path,
                    created_at=old_rule.created_at,
                    approval_count_at_creation=old_rule.approval_count_at_creation,
                    enabled=False,
                )
                self._save()
                logger.info("Disabled auto-approve rule for path: %s", key)
                return True

        return False

    def enable_rule(self, path: IntentPath) -> bool:
        """Re-enable a disabled auto-approve rule.

        Args:
            path: The intent DAG path to enable

        Returns:
            True if rule was enabled, False if it didn't exist
        """
        self._ensure_loaded()
        key = self._path_to_key(path)

        with self._lock:
            if key in self._rules:
                old_rule = self._rules[key]
                self._rules[key] = AutoApproveRule(
                    intent_path=old_rule.intent_path,
                    created_at=old_rule.created_at,
                    approval_count_at_creation=old_rule.approval_count_at_creation,
                    enabled=True,
                )
                self._save()
                logger.info("Enabled auto-approve rule for path: %s", key)
                return True

        return False

    def should_auto_approve(self, path: IntentPath) -> bool:
        """Check if a path should be auto-approved.

        Args:
            path: The intent DAG path to check

        Returns:
            True if path has an enabled auto-approve rule
        """
        self._ensure_loaded()
        key = self._path_to_key(path)

        with self._lock:
            rule = self._rules.get(key)
            return rule is not None and rule.enabled

    def get_rule(self, path: IntentPath) -> AutoApproveRule | None:
        """Get the auto-approve rule for a path.

        Args:
            path: The intent DAG path to look up

        Returns:
            AutoApproveRule if found, None otherwise
        """
        self._ensure_loaded()
        key = self._path_to_key(path)
        return self._rules.get(key)

    def list_rules(self, enabled_only: bool = False) -> list[AutoApproveRule]:
        """List all auto-approve rules.

        Args:
            enabled_only: If True, only return enabled rules

        Returns:
            List of AutoApproveRule instances
        """
        self._ensure_loaded()

        with self._lock:
            rules = list(self._rules.values())

        if enabled_only:
            rules = [r for r in rules if r.enabled]

        # Sort by creation date
        rules.sort(key=lambda r: r.created_at)
        return rules

    def has_rule(self, path: IntentPath) -> bool:
        """Check if a rule exists for a path (enabled or disabled).

        Args:
            path: The intent DAG path to check

        Returns:
            True if any rule exists for this path
        """
        self._ensure_loaded()
        key = self._path_to_key(path)
        return key in self._rules

    def clear(self) -> None:
        """Clear all auto-approve rules (for testing)."""
        with self._lock:
            self._rules.clear()
            if self._config_path.exists():
                self._config_path.unlink()
            self._loaded = True
