"""Type definitions for Autonomy Guardrails (RFC-048).

Core types for safe unsupervised operation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

# =============================================================================
# Risk Classification
# =============================================================================


class ActionRisk(Enum):
    """Risk classification for actions."""

    SAFE = "safe"
    """Can be executed autonomously within scope limits.

    Examples:
    - Write/modify test files
    - Add docstrings
    - Fix lint errors
    - Add type hints
    """

    MODERATE = "moderate"
    """Requires verification but can be auto-approved if confident.

    Examples:
    - Modify source files (non-critical paths)
    - Add new files
    - Modify configuration (non-secrets)
    - Run build commands
    """

    DANGEROUS = "dangerous"
    """Always requires human approval, even in FULL_AUTONOMY mode.

    Examples:
    - Delete files
    - Modify auth/security code
    - Change database schemas
    - Modify CI/CD configuration
    - Publish/deploy operations
    """

    FORBIDDEN = "forbidden"
    """Never executed, period. Hard-coded protection.

    Examples:
    - Access to credentials/secrets
    - Network operations to external hosts
    - System file modifications
    - Package publishing
    """


class TrustLevel(Enum):
    """Trust levels for autonomous operation."""

    CONSERVATIVE = "conservative"
    """Propose only, never execute."""

    GUARDED = "guarded"
    """Auto-approve within limits. DEFAULT."""

    SUPERVISED = "supervised"
    """Ask for dangerous actions only."""

    FULL = "full"
    """Only verified safe actions restricted."""


# =============================================================================
# Action Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class Action:
    """An action to be classified."""

    action_type: str
    """Type of action (file_write, shell_exec, etc.)."""

    path: str | None = None
    """File path if applicable."""

    command: str | None = None
    """Shell command if applicable."""

    content: str | None = None
    """Content being written (for analysis)."""

    metadata: dict = field(default_factory=dict)
    """Additional metadata."""


@dataclass(frozen=True, slots=True)
class ActionClassification:
    """Classification result for an action."""

    action_type: str
    """e.g., 'file_write_source'"""

    risk: ActionRisk
    """Classified risk level."""

    path: str | None
    """File path if applicable."""

    reason: str
    """Why this classification."""

    escalation_required: bool
    """Whether this needs human approval."""

    blocking_rule: str | None
    """Which rule triggered escalation (if any)."""


# =============================================================================
# Scope Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class FileChange:
    """A file change for scope tracking."""

    path: Path
    """Path to the file."""

    lines_added: int = 0
    """Lines added."""

    lines_removed: int = 0
    """Lines removed."""

    is_new: bool = False
    """Whether this is a new file."""

    is_deleted: bool = False
    """Whether this file is being deleted."""


@dataclass
class ScopeLimits:
    """Hard limits on autonomous operation scope.

    These limits exist because even SAFE actions can become
    dangerous at scale. "Add docstrings" is safe; "add docstrings
    to 10,000 files" is a footgun.
    """

    # Per-goal limits
    max_files_per_goal: int = 10
    """Maximum files touched by a single goal."""

    max_lines_changed_per_goal: int = 500
    """Maximum lines added/removed by a single goal."""

    max_duration_per_goal_minutes: int = 30
    """Maximum execution time for a single goal."""

    # Session limits
    max_goals_per_session: int = 20
    """Maximum goals executed in one autonomous session."""

    max_files_per_session: int = 50
    """Maximum total files touched in one session."""

    max_lines_per_session: int = 2000
    """Maximum total lines changed in one session."""

    max_duration_per_session_hours: int = 8
    """Maximum duration of autonomous session."""

    # Safety margins
    require_tests_for_source_changes: bool = True
    """If changing src/, must also add/modify tests/."""

    require_git_clean_start: bool = True
    """Refuse to start autonomous mode with uncommitted changes."""

    commit_after_each_goal: bool = True
    """Create git commit after each goal completes."""


@dataclass(frozen=True, slots=True)
class ScopeCheckResult:
    """Result of a scope limit check."""

    passed: bool
    """Whether the check passed."""

    reason: str
    """Explanation of result."""

    limit_type: str | None = None
    """Which limit was exceeded (if any)."""


# =============================================================================
# Trust Zone Types
# =============================================================================


@dataclass(slots=True)
class TrustZone:
    """A path pattern with associated trust level.

    RFC-130: Now supports adaptive learning from violations.
    """

    pattern: str
    """Glob pattern for matching paths."""

    risk_override: ActionRisk | None = None
    """Override default risk for this zone."""

    allowed_in_autonomous: bool = True
    """Whether autonomous mode can touch this zone."""

    reason: str = ""
    """Why this zone has special treatment."""

    # RFC-130: Adaptive learning fields
    learn_from_violations: bool = False
    """Whether to learn from violations to reduce false positives.

    When enabled, the system tracks violations in this zone and
    suggests rule refinements after reaching thresholds.
    """

    violation_history_path: str | None = None
    """Path to store violation history for learning (default: .sunwell/guard-violations/).

    If None, violations are not persisted. Set to enable cross-session learning.
    """

    false_positive_threshold: int = 3
    """Number of false positives before suggesting rule refinement.

    When users override a block this many times for similar patterns,
    suggest an evolution to reduce friction.
    """

    override_threshold: int = 5
    """Number of user overrides before auto-relaxing in this zone.

    After this many approvals for similar patterns, the system may
    suggest permanently allowing the pattern.
    """


# =============================================================================
# Escalation Types
# =============================================================================


class EscalationReason(Enum):
    """Reasons for escalation."""

    # Action-related
    FORBIDDEN_ACTION = "forbidden_action"
    DANGEROUS_ACTION = "dangerous_action"
    UNKNOWN_ACTION = "unknown_action"

    # Scope-related
    SCOPE_EXCEEDED = "scope_exceeded"
    DURATION_EXCEEDED = "duration_exceeded"
    FILES_LIMIT = "files_limit"

    # Verification-related
    LOW_CONFIDENCE = "low_confidence"
    VERIFICATION_FAILED = "verification_failed"

    # Policy-related
    PROTECTED_PATH = "protected_path"
    MISSING_TESTS = "missing_tests"


@dataclass(frozen=True, slots=True)
class EscalationOption:
    """An option presented to the user during escalation."""

    id: str
    label: str
    description: str

    action: Literal[
        "approve",  # Proceed with the action
        "approve_once",  # Approve this once, keep guardrail
        "skip",  # Skip this goal, continue session
        "modify",  # Let user modify the goal
        "abort",  # Abort entire session
        "relax",  # Relax the guardrail for session
        "split",  # Split into smaller goals
    ]

    risk_acknowledgment: str | None = None
    """Warning user must acknowledge if risky."""


@dataclass(frozen=True, slots=True)
class Escalation:
    """An escalation event requiring human decision."""

    id: str
    goal_id: str

    reason: EscalationReason
    """Why escalation was triggered."""

    details: str
    """Human-readable explanation."""

    blocking_rule: str
    """Which guardrail triggered this."""

    action_classification: ActionClassification | None = None
    """Classification if action-related."""

    scope_check: ScopeCheckResult | None = None
    """Scope check if limit-related."""

    verification_confidence: float | None = None
    """Verification confidence if confidence-related."""

    options: tuple[EscalationOption, ...] = ()
    """Available options for the user."""

    recommended_option: str = ""
    """ID of recommended option."""

    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def severity(self) -> Literal["info", "warning", "critical"]:
        """Severity based on blocking rule."""
        match self.reason:
            case EscalationReason.FORBIDDEN_ACTION:
                return "critical"
            case EscalationReason.DANGEROUS_ACTION:
                return "warning"
            case _:
                return "info"


@dataclass
class EscalationResolution:
    """Resolution of an escalation."""

    escalation_id: str
    option_id: str
    action: str
    acknowledged: bool = False
    modified_goal: str | None = None


# =============================================================================
# Recovery Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class SessionStart:
    """Session start information."""

    session_id: str
    tag: str
    start_commit: str


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    reason: str = ""
    reverted_commit: str | None = None
    goals_reverted: int = 0


@dataclass(frozen=True, slots=True)
class RecoveryOption:
    """A recovery option for rollback."""

    id: str
    description: str
    action: Literal["revert_goal", "rollback_session"]
    target: str


# =============================================================================
# Verification Gate Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class VerificationThresholds:
    """Confidence thresholds for auto-approval.

    Threshold Rationale (based on RFC-047 confidence semantics):

    - 0.70 (SAFE): At 70%, verification has "moderate" confidence.
      SAFE actions (tests, docs) have low blast radius, so moderate
      confidence is acceptable. False positives just trigger review.

    - 0.85 (MODERATE): At 85%, verification has "high" confidence.
      MODERATE actions (source changes) need stronger assurance.
      This threshold matches RFC-047's "high confidence" boundary.

    These defaults align with RFC-047 ConfidenceTriangulator:
    - >= 0.9: "high" confidence
    - >= 0.7: "moderate" confidence
    - >= 0.5: "low" confidence
    - < 0.5: "uncertain"

    Users can adjust via config if their risk tolerance differs.
    """

    safe_threshold: float = 0.70
    """Threshold for SAFE actions (RFC-047 "moderate" confidence)."""

    moderate_threshold: float = 0.85
    """Threshold for MODERATE actions (RFC-047 "high" confidence)."""


@dataclass(frozen=True, slots=True)
class VerificationGateResult:
    """Result from verification gate."""

    passed: bool
    """Whether verification passed."""

    auto_approvable: bool
    """Whether this can be auto-approved."""

    reason: str
    """Explanation."""

    confidence: float | None = None
    """Confidence score if verification ran."""


# =============================================================================
# RFC-130: Adaptive Guards Types
# =============================================================================


class ViolationOutcome(Enum):
    """Outcome of a guardrail violation."""

    BLOCKED = "blocked"
    """Action was blocked and user agreed."""

    OVERRIDDEN = "overridden"
    """Action was blocked but user overrode."""

    FALSE_POSITIVE = "false_positive"
    """User marked as false positive (shouldn't have blocked)."""


class EvolutionType(Enum):
    """Types of guard evolution suggestions."""

    ADD_EXCEPTION = "add_exception"
    """Add an exception pattern to allow specific cases."""

    REFINE_PATTERN = "refine_pattern"
    """Make pattern more specific to reduce false positives."""

    ELEVATE_TRUST = "elevate_trust"
    """Elevate trust level for this zone (user has proven trustworthy)."""

    REDUCE_SENSITIVITY = "reduce_sensitivity"
    """Reduce sensitivity for this rule type."""

    DEPRECATE_RULE = "deprecate_rule"
    """Suggest deprecating/removing the rule (too many overrides)."""


@dataclass(slots=True)
class GuardViolation:
    """Record of a guardrail violation for learning.

    RFC-130: Violations are tracked to enable adaptive learning.
    After enough false positives or overrides, the system can
    suggest rule refinements.

    Example:
        >>> violation = GuardViolation(
        ...     action_type="file_write",
        ...     path="tests/conftest.py",
        ...     blocking_rule="protected_path:tests/**",
        ...     outcome=ViolationOutcome.OVERRIDDEN,
        ...     user_comment="This is a test file, should be allowed",
        ... )
        >>> classifier.record_violation(violation)
    """

    action_type: str
    """Type of action that was blocked."""

    path: str | None
    """File path if applicable."""

    blocking_rule: str
    """Which rule blocked the action."""

    outcome: ViolationOutcome
    """How the violation was resolved."""

    user_comment: str | None = None
    """Optional user comment explaining why they overrode."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the violation occurred."""

    context: dict = field(default_factory=dict)
    """Additional context (goal, action details, etc.)."""

    similarity_hash: str | None = None
    """Hash for grouping similar violations."""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "action_type": self.action_type,
            "path": self.path,
            "blocking_rule": self.blocking_rule,
            "outcome": self.outcome.value,
            "user_comment": self.user_comment,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "similarity_hash": self.similarity_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GuardViolation":
        """Create from dict."""
        return cls(
            action_type=data["action_type"],
            path=data.get("path"),
            blocking_rule=data["blocking_rule"],
            outcome=ViolationOutcome(data["outcome"]),
            user_comment=data.get("user_comment"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            context=data.get("context", {}),
            similarity_hash=data.get("similarity_hash"),
        )


@dataclass(frozen=True, slots=True)
class GuardEvolution:
    """A suggested evolution to a guardrail rule.

    RFC-130: Generated by SmartActionClassifier.suggest_evolutions()
    based on accumulated violation patterns.

    Example:
        >>> evolutions = classifier.suggest_evolutions()
        >>> for evo in evolutions:
        ...     if evo.confidence > 0.8:
        ...         print(f"High-confidence suggestion: {evo.description}")
    """

    rule_id: str
    """ID of the rule to evolve."""

    evolution_type: EvolutionType
    """Type of evolution suggested."""

    description: str
    """Human-readable description of the change."""

    reason: str
    """Why this evolution is suggested (evidence summary)."""

    confidence: float
    """Confidence in this suggestion (0.0-1.0)."""

    supporting_violations: int
    """Number of violations supporting this evolution."""

    new_pattern: str | None = None
    """New pattern if evolution_type is REFINE_PATTERN or ADD_EXCEPTION."""

    new_trust_level: ActionRisk | None = None
    """New trust level if evolution_type is ELEVATE_TRUST."""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "rule_id": self.rule_id,
            "evolution_type": self.evolution_type.value,
            "description": self.description,
            "reason": self.reason,
            "confidence": self.confidence,
            "supporting_violations": self.supporting_violations,
            "new_pattern": self.new_pattern,
            "new_trust_level": self.new_trust_level.value if self.new_trust_level else None,
        }
