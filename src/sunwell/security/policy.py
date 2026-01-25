# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Policy-as-code for security enforcement (RFC-089).

Provides declarative security policies that can be version-controlled
and applied consistently across teams and environments.

Policy files support:
- Environment-specific rules (dev, staging, prod)
- Deny lists for dangerous patterns
- Approval requirements
- Custom risk thresholds
- Audit configuration
"""


import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# POLICY SCHEMA
# =============================================================================


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Individual policy rule within a policy."""

    name: str
    """Rule identifier."""

    environments: frozenset[str] = frozenset()
    """Environments this rule applies to (empty = all)."""

    # Deny lists
    deny_filesystem: frozenset[str] = frozenset()
    """Filesystem patterns to deny."""

    deny_network: frozenset[str] = frozenset()
    """Network hosts to deny."""

    deny_shell: frozenset[str] = frozenset()
    """Shell commands to deny."""

    deny_env: frozenset[str] = frozenset()
    """Environment variables to deny reading."""

    # Approval requirements
    require_approval: bool = False
    """Whether this rule requires approval."""

    require_approval_for_risk_above: float | None = None
    """Risk threshold for requiring approval."""

    # Recommendations
    recommend: str | None = None
    """Recommendation message when rule triggers."""

    def applies_to_environment(self, env: str | None) -> bool:
        """Check if rule applies to the given environment.

        Args:
            env: Current environment (None = default)

        Returns:
            True if rule applies
        """
        if not self.environments:
            return True
        if env is None:
            return "default" in self.environments or not self.environments
        return env in self.environments

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "name": self.name,
            "environments": list(self.environments) if self.environments else [],
            "deny": {
                "filesystem": list(self.deny_filesystem),
                "network": list(self.deny_network),
                "shell": list(self.deny_shell),
                "env": list(self.deny_env),
            },
            "require_approval": self.require_approval,
            "require_approval_for_risk_above": self.require_approval_for_risk_above,
            "recommend": self.recommend,
        }


@dataclass(slots=True)
class SecurityPolicyConfig:
    """Complete security policy configuration.

    Loaded from security-policy.yaml files with support for:
    - Multiple named policies
    - Environment-specific rules
    - Inheritance between policies
    """

    version: str = "1"
    """Policy schema version."""

    name: str = "default"
    """Policy name."""

    description: str = ""
    """Policy description."""

    # Global settings
    default_enforcement: Literal["strict", "warn", "audit"] = "strict"
    """Default enforcement mode."""

    require_permissions_declared: bool = True
    """Whether skills must declare permissions."""

    audit_enabled: bool = True
    """Whether to audit all executions."""

    audit_path: str | None = None
    """Custom audit log path."""

    # Risk thresholds
    auto_approve_risk_below: float = 0.3
    """Auto-approve if risk below this threshold."""

    require_approval_risk_above: float = 0.5
    """Require approval if risk above this threshold."""

    block_risk_above: float = 0.9
    """Block execution if risk above this threshold."""

    # Rules
    rules: list[PolicyRule] = field(default_factory=list)
    """Policy rules."""

    # Inheritance
    extends: str | None = None
    """Parent policy to extend."""

    @classmethod
    def from_yaml(cls, path: Path) -> SecurityPolicyConfig:
        """Load policy from YAML file.

        Args:
            path: Path to security-policy.yaml

        Returns:
            SecurityPolicyConfig instance

        Raises:
            ValueError: If policy is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls._from_dict(data, path.parent)

    @classmethod
    def _from_dict(cls, data: dict, base_path: Path) -> SecurityPolicyConfig:
        """Create config from dictionary.

        Args:
            data: Policy data
            base_path: Base path for resolving extends

        Returns:
            SecurityPolicyConfig instance
        """
        # Handle inheritance
        parent: SecurityPolicyConfig | None = None
        if data.get("extends"):
            parent_path = base_path / data["extends"]
            if parent_path.exists():
                parent = cls.from_yaml(parent_path)
            else:
                logger.warning(f"Parent policy not found: {parent_path}")

        # Parse rules
        rules = []
        for rule_data in data.get("policies", data.get("rules", [])):
            deny = rule_data.get("deny", {})
            rules.append(
                PolicyRule(
                    name=rule_data.get("name", "unnamed"),
                    environments=frozenset(rule_data.get("environments", [])),
                    deny_filesystem=frozenset(deny.get("filesystem", [])),
                    deny_network=frozenset(deny.get("network", [])),
                    deny_shell=frozenset(deny.get("shell", [])),
                    deny_env=frozenset(deny.get("env", [])),
                    require_approval=rule_data.get("require_approval", False),
                    require_approval_for_risk_above=rule_data.get(
                        "require_approval_for_risk_above"
                    ),
                    recommend=rule_data.get("recommend"),
                )
            )

        # Create config
        config = cls(
            version=str(data.get("version", "1")),
            name=data.get("name", "default"),
            description=data.get("description", ""),
            default_enforcement=data.get("default_enforcement", "strict"),
            require_permissions_declared=data.get("require_permissions_declared", True),
            audit_enabled=data.get("audit_enabled", True),
            audit_path=data.get("audit_path"),
            auto_approve_risk_below=data.get("auto_approve_risk_below", 0.3),
            require_approval_risk_above=data.get("require_approval_risk_above", 0.5),
            block_risk_above=data.get("block_risk_above", 0.9),
            rules=rules,
            extends=data.get("extends"),
        )

        # Merge with parent if extending
        if parent:
            config = config.merge_with_parent(parent)

        return config

    def merge_with_parent(self, parent: SecurityPolicyConfig) -> SecurityPolicyConfig:
        """Merge this config with a parent config.

        Args:
            parent: Parent policy to inherit from

        Returns:
            Merged config
        """
        # Child settings override parent, rules are combined
        merged_rules = list(parent.rules) + self.rules

        return SecurityPolicyConfig(
            version=self.version,
            name=self.name,
            description=self.description or parent.description,
            default_enforcement=self.default_enforcement,
            require_permissions_declared=self.require_permissions_declared,
            audit_enabled=self.audit_enabled,
            audit_path=self.audit_path or parent.audit_path,
            auto_approve_risk_below=self.auto_approve_risk_below,
            require_approval_risk_above=self.require_approval_risk_above,
            block_risk_above=self.block_risk_above,
            rules=merged_rules,
            extends=self.extends,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "default_enforcement": self.default_enforcement,
            "require_permissions_declared": self.require_permissions_declared,
            "audit_enabled": self.audit_enabled,
            "audit_path": self.audit_path,
            "auto_approve_risk_below": self.auto_approve_risk_below,
            "require_approval_risk_above": self.require_approval_risk_above,
            "block_risk_above": self.block_risk_above,
            "policies": [r.to_dict() for r in self.rules],
            "extends": self.extends,
        }

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)


# =============================================================================
# POLICY VALIDATOR
# =============================================================================


@dataclass(frozen=True, slots=True)
class PolicyValidationError:
    """A policy validation error."""

    field: str
    """Field with the error."""

    message: str
    """Error message."""

    severity: Literal["error", "warning"] = "error"
    """Error severity."""


class PolicyValidator:
    """Validates security policy configurations."""

    REQUIRED_FIELDS = ["version"]
    VALID_ENFORCEMENTS = ["strict", "warn", "audit"]
    MAX_RISK_THRESHOLD = 1.0
    MIN_RISK_THRESHOLD = 0.0

    def validate(self, config: SecurityPolicyConfig) -> list[PolicyValidationError]:
        """Validate a policy configuration.

        Args:
            config: Policy to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[PolicyValidationError] = []

        # Version check
        if not config.version:
            errors.append(
                PolicyValidationError("version", "Missing required field 'version'")
            )

        # Enforcement mode check
        if config.default_enforcement not in self.VALID_ENFORCEMENTS:
            errors.append(
                PolicyValidationError(
                    "default_enforcement",
                    f"Invalid enforcement mode. Must be one of: {self.VALID_ENFORCEMENTS}",
                )
            )

        # Risk threshold checks
        thresholds = [
            ("auto_approve_risk_below", config.auto_approve_risk_below),
            ("require_approval_risk_above", config.require_approval_risk_above),
            ("block_risk_above", config.block_risk_above),
        ]

        for name, value in thresholds:
            if not self.MIN_RISK_THRESHOLD <= value <= self.MAX_RISK_THRESHOLD:
                errors.append(
                    PolicyValidationError(
                        name,
                        f"Risk threshold must be between {self.MIN_RISK_THRESHOLD} and {self.MAX_RISK_THRESHOLD}",
                    )
                )

        # Threshold ordering
        if config.auto_approve_risk_below > config.require_approval_risk_above:
            errors.append(
                PolicyValidationError(
                    "risk_thresholds",
                    "auto_approve_risk_below must be <= require_approval_risk_above",
                    severity="warning",
                )
            )

        if config.require_approval_risk_above > config.block_risk_above:
            errors.append(
                PolicyValidationError(
                    "risk_thresholds",
                    "require_approval_risk_above must be <= block_risk_above",
                    severity="warning",
                )
            )

        # Rule validation
        for i, rule in enumerate(config.rules):
            if not rule.name:
                errors.append(
                    PolicyValidationError(
                        f"rules[{i}].name",
                        "Rule must have a name",
                    )
                )

            # Check for overly broad deny patterns
            for pattern in rule.deny_filesystem:
                if pattern in ("*", "**", "/"):
                    errors.append(
                        PolicyValidationError(
                            f"rules[{i}].deny.filesystem",
                            f"Overly broad filesystem deny pattern: {pattern}",
                            severity="warning",
                        )
                    )

        return errors


# =============================================================================
# POLICY ENFORCEMENT
# =============================================================================


class PolicyEnforcer:
    """Enforces security policies during skill execution."""

    def __init__(
        self,
        config: SecurityPolicyConfig,
        environment: str | None = None,
    ):
        """Initialize policy enforcer.

        Args:
            config: Policy configuration
            environment: Current environment name
        """
        self.config = config
        self.environment = environment
        self._applicable_rules = [
            r for r in config.rules if r.applies_to_environment(environment)
        ]

    def check_permissions(
        self,
        permissions: Any,  # PermissionScope
    ) -> tuple[bool, list[str]]:
        """Check if permissions are allowed by policy.

        Args:
            permissions: Requested permissions

        Returns:
            Tuple of (allowed, list of violation messages)
        """
        violations: list[str] = []

        for rule in self._applicable_rules:
            # Check filesystem
            for path in getattr(permissions, "filesystem_read", []):
                if self._matches_any(path, rule.deny_filesystem):
                    violations.append(
                        f"[{rule.name}] Filesystem read denied: {path}"
                    )
                    if rule.recommend:
                        violations.append(f"  Recommendation: {rule.recommend}")

            for path in getattr(permissions, "filesystem_write", []):
                if self._matches_any(path, rule.deny_filesystem):
                    violations.append(
                        f"[{rule.name}] Filesystem write denied: {path}"
                    )

            # Check network
            for host in getattr(permissions, "network_allow", []):
                if self._matches_any(host, rule.deny_network):
                    violations.append(
                        f"[{rule.name}] Network access denied: {host}"
                    )

            # Check shell
            for cmd in getattr(permissions, "shell_allow", []):
                if self._matches_any(cmd, rule.deny_shell):
                    violations.append(
                        f"[{rule.name}] Shell command denied: {cmd}"
                    )

            # Check env
            for var in getattr(permissions, "env_read", []):
                if self._matches_any(var, rule.deny_env):
                    violations.append(
                        f"[{rule.name}] Environment variable access denied: {var}"
                    )

        allowed = len(violations) == 0
        return allowed, violations

    def _matches_any(self, value: str, patterns: frozenset[str]) -> bool:
        """Check if value matches any pattern.

        Args:
            value: Value to check
            patterns: Patterns to match against

        Returns:
            True if any pattern matches
        """
        from fnmatch import fnmatch

        return any(fnmatch(value, p) for p in patterns)

    def requires_approval(self, risk_score: float) -> bool:
        """Check if execution requires approval based on risk.

        Args:
            risk_score: Computed risk score

        Returns:
            True if approval required
        """
        # Check per-rule approval requirements
        for rule in self._applicable_rules:
            if rule.require_approval:
                return True
            if rule.require_approval_for_risk_above is not None:
                if risk_score > rule.require_approval_for_risk_above:
                    return True

        # Check global threshold
        return risk_score > self.config.require_approval_risk_above

    def should_block(self, risk_score: float) -> bool:
        """Check if execution should be blocked based on risk.

        Args:
            risk_score: Computed risk score

        Returns:
            True if execution should be blocked
        """
        return risk_score > self.config.block_risk_above


# =============================================================================
# EXAMPLE POLICY
# =============================================================================


EXAMPLE_POLICY = """# Security Policy (RFC-089)
# Place in .sunwell/security-policy.yaml or ~/.sunwell/security-policy.yaml

version: "1"
name: production
description: "Production security policy for enterprise deployments"

# Global settings
default_enforcement: strict
require_permissions_declared: true
audit_enabled: true

# Risk thresholds
auto_approve_risk_below: 0.3
require_approval_risk_above: 0.5
block_risk_above: 0.9

policies:
  # Block credential file access in production
  - name: no-credential-files
    environments: [production, staging]
    deny:
      filesystem:
        - "~/.ssh/*"
        - "~/.aws/*"
        - "~/.config/gcloud/*"
        - "**/credentials*"
        - "**/.env*"
    recommend: "Use IAM roles or secret managers instead of credential files"

  # Block external network in production
  - name: no-external-network
    environments: [production]
    deny:
      network:
        - "*"
    require_approval: true
    recommend: "Use internal services or get approval for external access"

  # Block dangerous shell commands everywhere
  - name: no-dangerous-commands
    deny:
      shell:
        - "rm -rf *"
        - "dd if=*"
        - "mkfs*"
        - "> /dev/sd*"
        - "chmod 777*"

  # Require approval for moderate risk in staging
  - name: staging-approval
    environments: [staging]
    require_approval_for_risk_above: 0.4
"""


def create_example_policy(path: Path) -> None:
    """Create an example security policy file.

    Args:
        path: Path to write the example policy
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXAMPLE_POLICY)
    logger.info(f"Created example security policy at {path}")
