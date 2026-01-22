"""Action Classification for Autonomy Guardrails (RFC-048, RFC-077).

Classifies actions by risk level using pattern matching and trust zones.
RFC-077 adds FastClassifier fallback for edge cases that patterns miss.
"""


from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.guardrails.types import (
    Action,
    ActionClassification,
    ActionRisk,
    TrustLevel,
    TrustZone,
)

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

# =============================================================================
# Default Trust Zones
# =============================================================================

DEFAULT_TRUST_ZONES: tuple[TrustZone, ...] = (
    # Safe zones (can be modified autonomously)
    TrustZone(
        pattern="tests/**",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Test files are safe to modify",
    ),
    TrustZone(
        pattern="test_*.py",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Test files are safe to modify",
    ),
    TrustZone(
        pattern="*_test.py",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Test files are safe to modify",
    ),
    TrustZone(
        pattern="docs/**",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Documentation is safe to modify",
    ),
    TrustZone(
        pattern="**/__pycache__/**",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Cache files can be regenerated",
    ),
    TrustZone(
        pattern="*.md",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Markdown files are documentation",
    ),
    # Protected zones (require approval)
    TrustZone(
        pattern="**/auth/**",
        risk_override=ActionRisk.DANGEROUS,
        allowed_in_autonomous=False,
        reason="Authentication code is security-critical",
    ),
    TrustZone(
        pattern="**/security/**",
        risk_override=ActionRisk.DANGEROUS,
        allowed_in_autonomous=False,
        reason="Security code is critical",
    ),
    TrustZone(
        pattern="**/migrations/**",
        risk_override=ActionRisk.DANGEROUS,
        allowed_in_autonomous=False,
        reason="Database migrations can cause data loss",
    ),
    TrustZone(
        pattern="**/secrets/**",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Secrets directory is forbidden",
    ),
    # Forbidden zones (never touch)
    TrustZone(
        pattern=".env",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Environment files contain secrets",
    ),
    TrustZone(
        pattern=".env.*",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Environment files contain secrets",
    ),
    TrustZone(
        pattern="**/.git/**",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Git internals should not be modified",
    ),
    TrustZone(
        pattern="*.key",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Key files are security-critical",
    ),
    TrustZone(
        pattern="*.pem",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Certificate files are security-critical",
    ),
)


# Hard-coded forbidden patterns that can NEVER be overridden
# Design decision: FORBIDDEN is truly hard-coded with NO escape hatch.
#
# Rationale:
# 1. These patterns protect against catastrophic failures
# 2. If you need to modify .env, do it manually (10 seconds)
# 3. An escape hatch would undermine the entire safety model
# 4. "Trust but verify" fails when the failure mode is catastrophic
FORBIDDEN_PATTERNS: tuple[str, ...] = (
    # Secrets
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*secret*",
    "*credential*",
    # System paths
    "/etc/*",
    "/usr/*",
    "/var/*",
    "~/.ssh/*",
)

FORBIDDEN_COMMANDS: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf /*",
    ":(){ :|:& };:",
    "sudo rm",
    "> /dev/sda",
    "mkfs.",
    "dd if=/dev/zero",
)


# =============================================================================
# Action Taxonomy
# =============================================================================


class ActionTaxonomy:
    """Taxonomy of actions with default risk levels."""

    # File operations
    FILE_READ = ("file_read", ActionRisk.SAFE)
    FILE_WRITE_TEST = ("file_write_test", ActionRisk.SAFE)
    FILE_WRITE_DOCS = ("file_write_docs", ActionRisk.SAFE)
    FILE_WRITE_SOURCE = ("file_write_source", ActionRisk.MODERATE)
    FILE_WRITE_CONFIG = ("file_write_config", ActionRisk.DANGEROUS)
    FILE_WRITE_SECRETS = ("file_write_secrets", ActionRisk.FORBIDDEN)
    FILE_DELETE = ("file_delete", ActionRisk.DANGEROUS)

    # Shell operations
    SHELL_TEST = ("shell_test", ActionRisk.SAFE)
    SHELL_BUILD = ("shell_build", ActionRisk.MODERATE)
    SHELL_DANGEROUS = ("shell_dangerous", ActionRisk.DANGEROUS)
    SHELL_NETWORK = ("shell_network", ActionRisk.FORBIDDEN)

    # Database operations
    DB_READ = ("db_read", ActionRisk.SAFE)
    DB_WRITE = ("db_write", ActionRisk.MODERATE)
    DB_SCHEMA = ("db_schema", ActionRisk.DANGEROUS)
    DB_DROP = ("db_drop", ActionRisk.FORBIDDEN)

    @classmethod
    def get_default_risk(cls, action_type: str) -> ActionRisk:
        """Get default risk for an action type."""
        for name in dir(cls):
            if name.startswith("_"):
                continue
            value = getattr(cls, name)
            if isinstance(value, tuple) and len(value) == 2 and value[0] == action_type:
                return value[1]
        return ActionRisk.MODERATE  # Default for unknown


# =============================================================================
# Action Classifier
# =============================================================================


class ActionClassifier:
    """Classify actions by risk level.

    Classification strategy:
    1. Check for hard-coded forbidden patterns (cannot be overridden)
    2. Match path against trust zones
    3. Classify action type based on patterns
    4. Default to MODERATE for unknown actions
    """

    def __init__(
        self,
        trust_level: TrustLevel = TrustLevel.GUARDED,
        trust_zones: tuple[TrustZone, ...] | None = None,
        custom_forbidden_patterns: tuple[str, ...] = (),
    ):
        """Initialize classifier.

        Args:
            trust_level: Overall trust level for this session
            trust_zones: Custom trust zones (extends defaults)
            custom_forbidden_patterns: Additional forbidden patterns
        """
        self.trust_level = trust_level
        self.trust_zones = (trust_zones or ()) + DEFAULT_TRUST_ZONES
        self.forbidden_patterns = FORBIDDEN_PATTERNS + custom_forbidden_patterns

    def classify(self, action: Action) -> ActionClassification:
        """Classify a single action.

        Args:
            action: The action to classify

        Returns:
            ActionClassification with risk level and details
        """
        # 1. Check forbidden patterns first (hard-coded protection)
        if self._is_forbidden(action):
            return ActionClassification(
                action_type=action.action_type,
                risk=ActionRisk.FORBIDDEN,
                path=action.path,
                reason="Matches forbidden pattern",
                escalation_required=True,
                blocking_rule="forbidden_pattern",
            )

        # 2. Check trust zones for path-based overrides
        if action.path:
            zone_result = self._check_trust_zones(action.path)
            if zone_result:
                return ActionClassification(
                    action_type=action.action_type,
                    risk=zone_result.risk_override or ActionRisk.MODERATE,
                    path=action.path,
                    reason=zone_result.reason,
                    escalation_required=self._needs_escalation(
                        zone_result.risk_override or ActionRisk.MODERATE
                    ),
                    blocking_rule="trust_zone" if zone_result.risk_override else None,
                )

        # 3. Classify by action type
        action_type, risk = self._classify_action_type(action)

        # 4. Return classification
        return ActionClassification(
            action_type=action_type,
            risk=risk,
            path=action.path,
            reason=self._get_reason(action_type, risk),
            escalation_required=self._needs_escalation(risk),
            blocking_rule=None,
        )

    def classify_all(self, actions: list[Action]) -> list[ActionClassification]:
        """Classify multiple actions.

        Args:
            actions: List of actions to classify

        Returns:
            List of classifications
        """
        return [self.classify(action) for action in actions]

    def _is_forbidden(self, action: Action) -> bool:
        """Check if action matches forbidden patterns.

        This is truly hard-coded with NO escape hatch.
        """
        # Check path patterns
        if action.path:
            for pattern in self.forbidden_patterns:
                if fnmatch(action.path, pattern):
                    return True
                # Also check basename for patterns like ".env"
                if fnmatch(Path(action.path).name, pattern):
                    return True

        # Check command patterns
        if action.command:
            for pattern in FORBIDDEN_COMMANDS:
                if pattern in action.command:
                    return True

        return False

    def _check_trust_zones(self, path: str) -> TrustZone | None:
        """Check if path matches any trust zone.

        Returns the first matching zone, or None.
        Zones are checked in order, so more specific zones should come first.
        """
        for zone in self.trust_zones:
            if fnmatch(path, zone.pattern):
                return zone
            # Also try with ** prefix for nested matching
            if fnmatch(path, f"**/{zone.pattern}"):
                return zone
        return None

    def _classify_action_type(
        self, action: Action
    ) -> tuple[str, ActionRisk]:
        """Classify action by type and patterns."""
        # File operations
        if action.action_type.startswith("file_"):
            return self._classify_file_action(action)

        # Shell operations
        if action.action_type.startswith("shell_"):
            return self._classify_shell_action(action)

        # Database operations
        if action.action_type.startswith("db_"):
            return self._classify_db_action(action)

        # Default: return original type with default risk
        default_risk = ActionTaxonomy.get_default_risk(action.action_type)
        return action.action_type, default_risk

    def _classify_file_action(self, action: Action) -> tuple[str, ActionRisk]:
        """Classify file operations."""
        if action.action_type == "file_read":
            return "file_read", ActionRisk.SAFE

        if action.action_type == "file_delete":
            return "file_delete", ActionRisk.DANGEROUS

        if action.action_type in ("file_write", "file_create", "file_modify"):
            path = action.path or ""

            # Test files
            if self._is_test_path(path):
                return "file_write_test", ActionRisk.SAFE

            # Documentation
            if self._is_docs_path(path):
                return "file_write_docs", ActionRisk.SAFE

            # Config files
            if self._is_config_path(path):
                return "file_write_config", ActionRisk.DANGEROUS

            # Source files
            return "file_write_source", ActionRisk.MODERATE

        return action.action_type, ActionRisk.MODERATE

    def _classify_shell_action(self, action: Action) -> tuple[str, ActionRisk]:
        """Classify shell operations."""
        command = action.command or ""

        # Safe: test commands
        safe_patterns = ("pytest", "ruff check", "ty ", "mypy", "uv run pytest")
        for pattern in safe_patterns:
            if command.startswith(pattern):
                return "shell_test", ActionRisk.SAFE

        # Moderate: build commands
        moderate_patterns = ("pip install", "uv sync", "make", "uv pip")
        for pattern in moderate_patterns:
            if command.startswith(pattern):
                return "shell_build", ActionRisk.MODERATE

        # Dangerous: destructive commands
        dangerous_patterns = ("rm ", "git push", "git reset --hard", "docker")
        for pattern in dangerous_patterns:
            if pattern in command:
                return "shell_dangerous", ActionRisk.DANGEROUS

        # Forbidden: network commands
        network_patterns = ("curl ", "wget ", "ssh ", "scp ")
        for pattern in network_patterns:
            if command.startswith(pattern):
                return "shell_network", ActionRisk.FORBIDDEN

        return "shell_exec", ActionRisk.MODERATE

    def _classify_db_action(self, action: Action) -> tuple[str, ActionRisk]:
        """Classify database operations."""
        match action.action_type:
            case "db_read" | "db_select":
                return "db_read", ActionRisk.SAFE
            case "db_write" | "db_insert" | "db_update":
                return "db_write", ActionRisk.MODERATE
            case "db_schema" | "db_migrate" | "db_alter":
                return "db_schema", ActionRisk.DANGEROUS
            case "db_drop" | "db_truncate":
                return "db_drop", ActionRisk.FORBIDDEN
            case _:
                return action.action_type, ActionRisk.MODERATE

    def _is_test_path(self, path: str) -> bool:
        """Check if path is a test file."""
        patterns = ("tests/**", "test_*.py", "*_test.py", "**/*_test.py", "**/test_*.py")
        return any(fnmatch(path, p) for p in patterns)

    def _is_docs_path(self, path: str) -> bool:
        """Check if path is documentation."""
        patterns = ("docs/**", "*.md", "*.rst", "README*", "CHANGELOG*")
        return any(fnmatch(path, p) for p in patterns)

    def _is_config_path(self, path: str) -> bool:
        """Check if path is a configuration file."""
        patterns = (
            "*.json",
            "*.yaml",
            "*.yml",
            "*.toml",
            "pyproject.toml",
            "*.ini",
            "*.cfg",
        )
        return any(fnmatch(path, p) for p in patterns)

    def _needs_escalation(self, risk: ActionRisk) -> bool:
        """Determine if risk level needs escalation based on trust level."""
        match self.trust_level:
            case TrustLevel.CONSERVATIVE:
                # Everything escalates
                return True
            case TrustLevel.GUARDED:
                # MODERATE and above escalate
                return risk in (
                    ActionRisk.MODERATE,
                    ActionRisk.DANGEROUS,
                    ActionRisk.FORBIDDEN,
                )
            case TrustLevel.SUPERVISED:
                # Only DANGEROUS and FORBIDDEN escalate
                return risk in (ActionRisk.DANGEROUS, ActionRisk.FORBIDDEN)
            case TrustLevel.FULL:
                # Only FORBIDDEN escalates (always)
                return risk == ActionRisk.FORBIDDEN

    def _get_reason(self, action_type: str, risk: ActionRisk) -> str:
        """Get explanation for classification."""
        reasons = {
            "file_read": "Reading files is safe",
            "file_write_test": "Test files are safe to modify",
            "file_write_docs": "Documentation is safe to modify",
            "file_write_source": "Source code modifications require review",
            "file_write_config": "Configuration changes can affect behavior",
            "file_delete": "Deleting files is destructive",
            "shell_test": "Test commands are safe",
            "shell_build": "Build commands can have side effects",
            "shell_dangerous": "Potentially destructive shell command",
            "db_read": "Database reads are safe",
            "db_write": "Database writes modify data",
            "db_schema": "Schema changes can cause data loss",
        }
        return reasons.get(action_type, f"Default classification for {action_type}")


# =============================================================================
# LLM-Enhanced Classifier (RFC-077)
# =============================================================================


class SmartActionClassifier(ActionClassifier):
    """Action classifier with LLM fallback for edge cases (RFC-077).

    Uses FastClassifier to handle cases that pattern matching misses:
    - Novel action types not in taxonomy
    - Ambiguous paths that don't match trust zones
    - Context-dependent risk assessment

    Example:
        classifier = SmartActionClassifier(model=small_model)

        # Pattern match first, LLM fallback for unknowns
        classification = await classifier.classify_smart(action)
    """

    def __init__(
        self,
        model: ModelProtocol | None = None,
        trust_level: TrustLevel = TrustLevel.GUARDED,
        trust_zones: tuple[TrustZone, ...] | None = None,
        custom_forbidden_patterns: tuple[str, ...] = (),
    ):
        """Initialize smart classifier.

        Args:
            model: Small model for LLM fallback (llama3.2:3b recommended)
            trust_level: Overall trust level for this session
            trust_zones: Custom trust zones (extends defaults)
            custom_forbidden_patterns: Additional forbidden patterns
        """
        super().__init__(trust_level, trust_zones, custom_forbidden_patterns)
        self._model = model
        self._classifier: Any = None

    async def _get_classifier(self) -> Any:
        """Lazy-load FastClassifier."""
        if self._classifier is None and self._model is not None:
            from sunwell.reasoning import FastClassifier

            self._classifier = FastClassifier(model=self._model)
        return self._classifier

    async def classify_smart(self, action: Action) -> ActionClassification:
        """Classify with LLM fallback for edge cases.

        Strategy:
        1. Check forbidden patterns (always hard-coded)
        2. Check trust zones (pattern-based)
        3. Classify by action type (pattern-based)
        4. If result is MODERATE and no clear pattern, use LLM

        Args:
            action: The action to classify

        Returns:
            ActionClassification with risk level
        """
        # First: standard pattern-based classification
        classification = self.classify(action)

        # If we got a clear answer from patterns, use it
        if classification.blocking_rule is not None:
            return classification

        # If risk is clearly SAFE or FORBIDDEN, use pattern result
        if classification.risk in (ActionRisk.SAFE, ActionRisk.FORBIDDEN):
            return classification

        # For MODERATE/DANGEROUS without clear pattern, try LLM
        classifier = await self._get_classifier()
        if classifier is None:
            return classification  # No model, use pattern result

        try:
            # Build context for LLM
            context = self._build_action_context(action, classification)
            risk_str = await classifier.risk(
                action=action.action_type,
                file_path=action.path or "unknown",
                change_description=context,
            )

            # Map LLM result to ActionRisk
            risk_map = {
                "safe": ActionRisk.SAFE,
                "moderate": ActionRisk.MODERATE,
                "dangerous": ActionRisk.DANGEROUS,
                "forbidden": ActionRisk.FORBIDDEN,
            }
            llm_risk = risk_map.get(risk_str.lower(), ActionRisk.MODERATE)

            # Return LLM-enhanced classification
            return ActionClassification(
                action_type=classification.action_type,
                risk=llm_risk,
                path=action.path,
                reason=f"LLM: {risk_str} (pattern: {classification.risk.value})",
                escalation_required=self._needs_escalation(llm_risk),
                blocking_rule=None,
            )

        except Exception:
            # LLM failed, fall back to pattern result
            return classification

    def _build_action_context(
        self, action: Action, classification: ActionClassification
    ) -> str:
        """Build context string for LLM risk assessment."""
        parts = [
            f"Action: {action.action_type}",
        ]

        if action.path:
            parts.append(f"Path: {action.path}")

        if action.command:
            parts.append(f"Command: {action.command[:100]}")

        if action.content:
            parts.append(f"Content preview: {action.content[:200]}")

        parts.append(f"Pattern classification: {classification.risk.value}")
        parts.append(f"Pattern reason: {classification.reason}")

        return "\n".join(parts)

    async def classify_all_smart(
        self, actions: list[Action]
    ) -> list[ActionClassification]:
        """Classify multiple actions with LLM fallback.

        Args:
            actions: List of actions to classify

        Returns:
            List of classifications
        """
        results = []
        for action in actions:
            results.append(await self.classify_smart(action))
        return results
