"""Action Classification for Autonomy Guardrails (RFC-048, RFC-077).

Classifies actions by risk level using pattern matching and trust zones.
RFC-077 adds FastClassifier fallback for edge cases that patterns miss.
"""

import dataclasses
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.quality.guardrails.types import (
    Action,
    ActionClassification,
    ActionRisk,
    EvolutionType,
    GuardEvolution,
    GuardViolation,
    TrustLevel,
    TrustZone,
    ViolationOutcome,
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
        return _ACTION_RISK_MAP.get(action_type, ActionRisk.MODERATE)


# Pre-built lookup map for O(1) action risk lookups
_ACTION_RISK_MAP: dict[str, ActionRisk] = {
    v[0]: v[1]
    for name in dir(ActionTaxonomy)
    if not name.startswith("_")
    and isinstance((v := getattr(ActionTaxonomy, name)), tuple)
    and len(v) == 2
}


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
    """Action classifier with LLM fallback for edge cases (RFC-077, RFC-130).

    Uses FastClassifier to handle cases that pattern matching misses:
    - Novel action types not in taxonomy
    - Ambiguous paths that don't match trust zones
    - Context-dependent risk assessment

    RFC-130 adds adaptive learning:
    - Track violations to identify false positive patterns
    - Suggest guard evolutions based on user feedback
    - Learn from override patterns to reduce friction

    Example:
        classifier = SmartActionClassifier(model=small_model, enable_learning=True)

        # Pattern match first, LLM fallback for unknowns
        classification = await classifier.classify_smart(action)

        # Record user feedback
        if user_overrode:
            classifier.record_violation(GuardViolation(
                action_type="file_write",
                path="src/utils/helpers.py",
                blocking_rule="trust_zone",
                outcome=ViolationOutcome.OVERRIDDEN,
                user_comment="This is a utility file, not auth code",
            ))

        # Get evolution suggestions
        evolutions = await classifier.suggest_evolutions()
    """

    def __init__(
        self,
        model: ModelProtocol | None = None,
        trust_level: TrustLevel = TrustLevel.GUARDED,
        trust_zones: tuple[TrustZone, ...] | None = None,
        custom_forbidden_patterns: tuple[str, ...] = (),
        enable_learning: bool = False,
        violation_store_path: Path | None = None,
    ):
        """Initialize smart classifier.

        Args:
            model: Small model for LLM fallback (llama3.2:3b recommended)
            trust_level: Overall trust level for this session
            trust_zones: Custom trust zones (extends defaults)
            custom_forbidden_patterns: Additional forbidden patterns
            enable_learning: Enable RFC-130 adaptive learning
            violation_store_path: Path to store violations (default: .sunwell/guard-violations/)
        """
        super().__init__(trust_level, trust_zones, custom_forbidden_patterns)
        self._model = model
        self._classifier: Any = None

        # RFC-130: Adaptive learning
        self._enable_learning = enable_learning
        self._violation_store_path = violation_store_path or Path(".sunwell/guard-violations")
        self._violations: list[GuardViolation] = []
        self._loaded_violations = False

    async def _get_classifier(self) -> Any:
        """Lazy-load FastClassifier."""
        if self._classifier is None and self._model is not None:
            from sunwell.planning.reasoning import FastClassifier

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

    # =========================================================================
    # RFC-130: Adaptive Learning
    # =========================================================================

    def record_violation(self, violation: GuardViolation) -> None:
        """Record a guardrail violation for learning.

        RFC-130: Violations are tracked to enable adaptive rule evolution.
        After enough false positives, the system suggests refinements.

        Args:
            violation: The violation to record
        """
        if not self._enable_learning:
            return

        # Compute similarity hash for grouping (violation is frozen, use replace)
        similarity_hash = self._compute_similarity_hash(violation)
        violation = dataclasses.replace(violation, similarity_hash=similarity_hash)

        self._violations.append(violation)

        # Persist to disk
        self._persist_violations()

    def record_user_feedback(
        self,
        action: Action,
        classification: ActionClassification,
        approved: bool,
        is_false_positive: bool = False,
        comment: str | None = None,
    ) -> None:
        """Record user feedback on a classification decision.

        RFC-130: Simplified API for recording feedback after escalation.

        Args:
            action: The action that was classified
            classification: The classification result
            approved: Whether the user approved the action
            is_false_positive: Whether user marked this as false positive
            comment: Optional user comment
        """
        if not self._enable_learning:
            return

        outcome = ViolationOutcome.FALSE_POSITIVE if is_false_positive else (
            ViolationOutcome.OVERRIDDEN if approved else ViolationOutcome.BLOCKED
        )

        violation = GuardViolation(
            action_type=action.action_type,
            path=action.path,
            blocking_rule=classification.blocking_rule or "unknown",
            outcome=outcome,
            user_comment=comment,
            context=(
                ("classification_risk", classification.risk.value),
                ("classification_reason", classification.reason),
            ),
        )

        self.record_violation(violation)

    async def suggest_evolutions(self) -> list[GuardEvolution]:
        """Suggest guard evolutions based on accumulated violations.

        RFC-130: Analyzes violation patterns to suggest rule refinements
        that reduce false positives while maintaining security.

        Returns:
            List of suggested evolutions, sorted by confidence
        """
        if not self._enable_learning:
            return []

        self._load_violations()

        # Group violations by similarity
        groups = self._group_violations_by_pattern()

        evolutions: list[GuardEvolution] = []

        for rule_id, violations in groups.items():
            # Count outcomes
            false_positives = sum(
                1 for v in violations if v.outcome == ViolationOutcome.FALSE_POSITIVE
            )
            overrides = sum(
                1 for v in violations if v.outcome == ViolationOutcome.OVERRIDDEN
            )
            total = len(violations)

            # Check thresholds for suggestions
            if false_positives >= 3:
                evolutions.append(self._suggest_exception_pattern(rule_id, violations))

            if overrides >= 5:
                evolutions.append(self._suggest_trust_elevation(rule_id, violations))

            if total >= 10 and (false_positives + overrides) / total > 0.7:
                evolutions.append(self._suggest_pattern_refinement(rule_id, violations))

        # Sort by confidence
        evolutions.sort(key=lambda e: e.confidence, reverse=True)

        return evolutions

    def _compute_similarity_hash(self, violation: GuardViolation) -> str:
        """Compute hash for grouping similar violations."""
        import hashlib

        parts = [
            violation.action_type,
            violation.blocking_rule,
        ]

        # Group by path pattern (e.g., "src/utils/*.py")
        if violation.path:
            path = Path(violation.path)
            # Use parent + extension as grouping key
            parts.append(str(path.parent))
            parts.append(path.suffix)

        key = "|".join(parts)
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _group_violations_by_pattern(self) -> dict[str, list[GuardViolation]]:
        """Group violations by blocking rule."""
        groups: dict[str, list[GuardViolation]] = {}

        for violation in self._violations:
            key = violation.blocking_rule
            if key not in groups:
                groups[key] = []
            groups[key].append(violation)

        return groups

    def _suggest_exception_pattern(
        self, rule_id: str, violations: list[GuardViolation]
    ) -> GuardEvolution:
        """Suggest adding an exception pattern."""
        # Find common path patterns in violations
        paths = [v.path for v in violations if v.path]
        common_pattern = self._find_common_pattern(paths)

        return GuardEvolution(
            rule_id=rule_id,
            evolution_type=EvolutionType.ADD_EXCEPTION,
            description=f"Add exception for {common_pattern}",
            reason=f"{len(violations)} false positives for similar paths",
            confidence=min(0.9, 0.5 + (len(violations) * 0.1)),
            supporting_violations=len(violations),
            new_pattern=common_pattern,
        )

    def _suggest_trust_elevation(
        self, rule_id: str, violations: list[GuardViolation]
    ) -> GuardEvolution:
        """Suggest elevating trust for this zone."""
        return GuardEvolution(
            rule_id=rule_id,
            evolution_type=EvolutionType.ELEVATE_TRUST,
            description=f"Elevate trust level for {rule_id}",
            reason=f"{len(violations)} user overrides indicate trustworthy zone",
            confidence=min(0.85, 0.4 + (len(violations) * 0.05)),
            supporting_violations=len(violations),
            new_trust_level=ActionRisk.MODERATE,
        )

    def _suggest_pattern_refinement(
        self, rule_id: str, violations: list[GuardViolation]
    ) -> GuardEvolution:
        """Suggest refining the pattern to be more specific."""
        paths = [v.path for v in violations if v.path]
        refined_pattern = self._find_specific_pattern(paths)

        return GuardEvolution(
            rule_id=rule_id,
            evolution_type=EvolutionType.REFINE_PATTERN,
            description=f"Refine pattern to {refined_pattern}",
            reason="High override rate suggests pattern is too broad",
            confidence=0.7,
            supporting_violations=len(violations),
            new_pattern=refined_pattern,
        )

    def _find_common_pattern(self, paths: list[str | None]) -> str:
        """Find common glob pattern across paths."""
        valid_paths = [p for p in paths if p]
        if not valid_paths:
            return "**/*"

        # Find common directory
        path_objects = [Path(p) for p in valid_paths]
        parents = [p.parent for p in path_objects]

        if parents:
            common_parent = parents[0]
            for p in parents[1:]:
                while common_parent != p and common_parent.parts:
                    common_parent = common_parent.parent
                    if str(p).startswith(str(common_parent)):
                        break

            # Find common extension
            extensions = {p.suffix for p in path_objects if p.suffix}
            if len(extensions) == 1:
                return f"{common_parent}/*{extensions.pop()}"
            return f"{common_parent}/**"

        return "**/*"

    def _find_specific_pattern(self, paths: list[str | None]) -> str:
        """Find a more specific pattern to reduce false positives."""
        valid_paths = [p for p in paths if p]
        if not valid_paths:
            return "**/*"

        # Use the most common directory as the specific pattern
        directories = [str(Path(p).parent) for p in valid_paths]
        if directories:
            most_common = Counter(directories).most_common(1)
            if most_common:
                return f"{most_common[0][0]}/*"

        return "**/*"

    def _persist_violations(self) -> None:
        """Persist violations to disk."""
        import json

        self._violation_store_path.mkdir(parents=True, exist_ok=True)
        violations_file = self._violation_store_path / "violations.jsonl"

        with open(violations_file, "a") as f:
            # Append only the latest violation
            if self._violations:
                f.write(json.dumps(self._violations[-1].to_dict()) + "\n")

    def _load_violations(self) -> None:
        """Load violations from disk."""
        import json

        if self._loaded_violations:
            return

        violations_file = self._violation_store_path / "violations.jsonl"
        if violations_file.exists():
            with open(violations_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        violation = GuardViolation.from_dict(data)
                        if violation not in self._violations:
                            self._violations.append(violation)

        self._loaded_violations = True

    def get_violation_stats(self) -> dict[str, Any]:
        """Get statistics about accumulated violations.

        Returns:
            Dict with violation counts, rule breakdown, and learning progress
        """
        self._load_violations()

        stats: dict[str, Any] = {
            "total_violations": len(self._violations),
            "by_outcome": {},
            "by_rule": {},
            "learning_enabled": self._enable_learning,
        }

        for outcome in ViolationOutcome:
            stats["by_outcome"][outcome.value] = sum(
                1 for v in self._violations if v.outcome == outcome
            )

        for violation in self._violations:
            rule = violation.blocking_rule
            if rule not in stats["by_rule"]:
                stats["by_rule"][rule] = 0
            stats["by_rule"][rule] += 1

        return stats
