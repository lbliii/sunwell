"""Guardrail System Orchestrator for Autonomy Guardrails (RFC-048).

Main orchestrator that ties all guardrail components together.
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.guardrails.classifier import ActionClassifier
from sunwell.guardrails.config import GuardrailConfig, load_config
from sunwell.guardrails.escalation import EscalationHandler
from sunwell.guardrails.recovery import RecoveryManager
from sunwell.guardrails.scope import ScopeTracker
from sunwell.guardrails.trust import TrustZoneEvaluator
from sunwell.guardrails.types import (
    Action,
    ActionClassification,
    ActionRisk,
    EscalationReason,
    EscalationResolution,
    FileChange,
    GuardViolation,
    ScopeCheckResult,
    SessionStart,
    ViolationOutcome,
)
from sunwell.guardrails.verification import VerificationGate, create_verification_gate

if TYPE_CHECKING:
    from sunwell.backlog.goals import Goal
    from sunwell.external.policy import ExternalGoalPolicy
    from sunwell.external.types import ExternalEvent


@dataclass(slots=True)
class GuardrailSystem:
    """Main guardrail system orchestrator.

    Coordinates all guardrail components:
    - ActionClassifier: Classifies actions by risk
    - ScopeTracker: Enforces scope limits
    - TrustZoneEvaluator: Evaluates paths against trust zones
    - VerificationGate: RFC-047 integration
    - RecoveryManager: Git-based recovery
    - EscalationHandler: User escalations

    Example:
        >>> guardrails = GuardrailSystem(repo_path=Path.cwd())
        >>> session = await guardrails.start_session()
        >>>
        >>> for goal in backlog:
        ...     if await guardrails.can_auto_approve(goal):
        ...         result = await execute(goal)
        ...         await guardrails.checkpoint_goal(goal, result.changes)
        ...     else:
        ...         resolution = await guardrails.escalate(goal)
        ...         if resolution.action == "approve":
        ...             result = await execute(goal)
    """

    repo_path: Path
    """Path to git repository."""

    config: GuardrailConfig | None = None
    """Guardrail configuration (loads from project if None)."""

    model: object = None
    """LLM model for verification (optional)."""

    # Components (initialized in __post_init__)
    classifier: ActionClassifier = field(init=False)
    scope_tracker: ScopeTracker = field(init=False)
    trust_evaluator: TrustZoneEvaluator = field(init=False)
    verification_gate: VerificationGate = field(init=False)
    recovery: RecoveryManager = field(init=False)
    escalation_handler: EscalationHandler = field(init=False)

    # Session state
    _session_started: bool = field(default=False, init=False)

    def __post_init__(self):
        """Initialize all components."""
        # Load config if not provided
        if self.config is None:
            self.config = load_config(self.repo_path)

        # Initialize components
        self.classifier = ActionClassifier(
            trust_level=self.config.trust_level,
            trust_zones=self.config.trust_zones,
        )

        self.scope_tracker = ScopeTracker(limits=self.config.scope)

        self.trust_evaluator = TrustZoneEvaluator(
            custom_zones=self.config.trust_zones,
            include_defaults=True,
        )

        self.verification_gate = create_verification_gate(
            model=self.model,
            cwd=self.repo_path,
            thresholds=self.config.verification,
        )

        self.recovery = RecoveryManager(self.repo_path)

        self.escalation_handler = EscalationHandler()

    async def start_session(self) -> SessionStart:
        """Start an autonomous session.

        Creates a git tag for potential rollback and initializes
        session tracking.

        Returns:
            SessionStart with session ID and tag

        Raises:
            GuardrailError: If there are uncommitted changes
        """
        if self.config.require_clean_start:
            session = await self.recovery.start_session()
        else:
            # Create session without git tag
            from datetime import datetime

            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            session = SessionStart(
                session_id=session_id,
                tag=f"sunwell-session-{session_id}",
                start_commit="",
            )

        self._session_started = True
        return session

    async def can_auto_approve(self, goal: Goal) -> bool:
        """Determine if goal can be auto-approved.

        Checks all guardrail layers:
        1. Action classification (risk level)
        2. Scope limits
        3. Category/complexity policy
        4. Verification confidence (if applicable)

        Args:
            goal: The goal to check

        Returns:
            True if goal can be auto-approved
        """
        # Check category and complexity policy
        if goal.category not in self.config.auto_approve_categories:
            return False
        if goal.estimated_complexity not in self.config.auto_approve_complexity:
            return False

        # Check scope limits
        changes = self._goal_to_changes(goal)
        scope_check = self.scope_tracker.check_goal(changes, goal.id)
        if not scope_check.passed:
            return False

        # Check action classification
        classification = self._classify_goal(goal)
        if classification.risk in (ActionRisk.FORBIDDEN, ActionRisk.DANGEROUS):
            return False

        # Check verification gate
        gate_result = await self.verification_gate.check_quick(classification.risk)
        return gate_result.auto_approvable

    async def check_goal(
        self, goal: Goal
    ) -> tuple[bool, str, ActionClassification | None, ScopeCheckResult | None]:
        """Check if a goal passes all guardrails.

        Args:
            goal: The goal to check

        Returns:
            Tuple of (passed, reason, classification, scope_check)
        """
        # Classify the goal
        classification = self._classify_goal(goal)

        # Check for forbidden
        if classification.risk == ActionRisk.FORBIDDEN:
            return (
                False,
                f"Forbidden action: {classification.reason}",
                classification,
                None,
            )

        # Check scope
        changes = self._goal_to_changes(goal)
        scope_check = self.scope_tracker.check_goal(changes, goal.id)
        if not scope_check.passed:
            return (
                False,
                f"Scope exceeded: {scope_check.reason}",
                classification,
                scope_check,
            )

        # Check verification gate
        gate_result = await self.verification_gate.check_quick(classification.risk)
        if not gate_result.passed:
            return (
                False,
                f"Verification failed: {gate_result.reason}",
                classification,
                scope_check,
            )

        return (True, "All checks passed", classification, scope_check)

    async def escalate_goal(self, goal: Goal) -> EscalationResolution:
        """Create and handle escalation for a goal.

        Args:
            goal: The goal that needs escalation

        Returns:
            EscalationResolution with user's decision
        """
        classification = self._classify_goal(goal)
        changes = self._goal_to_changes(goal)
        scope_check = self.scope_tracker.check_goal(changes, goal.id)

        # Determine reason
        reason = self._determine_escalation_reason(classification, scope_check)

        # Create escalation
        escalation = self.escalation_handler.create_escalation(
            goal_id=goal.id,
            reason=reason,
            details=self._get_escalation_details(goal, classification, scope_check),
            blocking_rule=self._get_blocking_rule(classification, scope_check),
            action_classification=classification,
            scope_check=scope_check if not scope_check.passed else None,
        )

        # Present to user
        return await self.escalation_handler.escalate(escalation)

    async def checkpoint_goal(
        self, goal: Goal, changes: list[FileChange]
    ) -> str:
        """Create checkpoint commit after goal completion.

        Args:
            goal: The completed goal
            changes: List of file changes

        Returns:
            Commit hash (empty if no changes)
        """
        if self.config.commit_after_each_goal:
            commit = await self.recovery.checkpoint_goal(
                goal_id=goal.id,
                goal_title=goal.title,
                changes=changes,
            )
        else:
            commit = ""

        # Record in scope tracker
        self.scope_tracker.record_goal_completion(changes)

        return commit

    async def rollback_goal(self, goal_id: str) -> bool:
        """Rollback a specific goal.

        Args:
            goal_id: ID of goal to rollback

        Returns:
            True if successful
        """
        result = await self.recovery.rollback_goal(goal_id)
        return result.success

    async def rollback_session(self) -> bool:
        """Rollback entire session.

        Returns:
            True if successful
        """
        result = await self.recovery.rollback_session()
        if result.success:
            self.scope_tracker.reset_session()
        return result.success

    async def cleanup_session(self) -> None:
        """Clean up session after successful completion."""
        await self.recovery.cleanup_session()
        self._session_started = False

    def can_continue(self) -> ScopeCheckResult:
        """Check if session can continue.

        Returns:
            ScopeCheckResult indicating if session can continue
        """
        return self.scope_tracker.can_continue()

    def get_session_stats(self) -> dict:
        """Get session statistics.

        Returns:
            Dictionary with session stats
        """
        return self.scope_tracker.get_session_stats()

    def classify_action(self, action: Action) -> ActionClassification:
        """Classify a single action.

        Args:
            action: The action to classify

        Returns:
            ActionClassification with risk and details
        """
        return self.classifier.classify(action)

    def classify_actions(self, actions: list[Action]) -> list[ActionClassification]:
        """Classify multiple actions.

        Args:
            actions: Actions to classify

        Returns:
            List of classifications
        """
        return self.classifier.classify_all(actions)

    # =========================================================================
    # RFC-130: Autonomous Action Checking
    # =========================================================================

    async def check_autonomous_action(
        self,
        action: Action,
        emit_event: callable | None = None,
    ) -> tuple[bool, str | None]:
        """Check if an action is allowed in autonomous mode.

        RFC-130: Pre-action check for autonomous operation.
        Uses SmartActionClassifier with LLM fallback for edge cases.

        Args:
            action: The action to check
            emit_event: Optional callback to emit events

        Returns:
            Tuple of (allowed, blocking_reason)
        """
        from sunwell.guardrails.classifier import SmartActionClassifier

        # Use smart classifier if model available
        if self.model is not None and isinstance(self.classifier, SmartActionClassifier):
            classification = await self.classifier.classify_smart(action)
        else:
            classification = self.classifier.classify(action)

        # Check if action is allowed
        if classification.risk == ActionRisk.FORBIDDEN:
            if emit_event:
                from sunwell.agent.events import autonomous_action_blocked_event
                event = autonomous_action_blocked_event(
                    action_type=action.action_type,
                    path=action.path,
                    reason="Action is forbidden",
                    blocking_rule=classification.blocking_rule or "forbidden",
                    risk_level="forbidden",
                )
                emit_event(event)
            return False, f"Forbidden: {classification.reason}"

        if classification.risk == ActionRisk.DANGEROUS:
            # Check if trust level allows dangerous actions
            if self.config.trust_level.value in ("conservative", "guarded"):
                if emit_event:
                    from sunwell.agent.events import autonomous_action_blocked_event
                    event = autonomous_action_blocked_event(
                        action_type=action.action_type,
                        path=action.path,
                        reason="Dangerous action requires approval",
                        blocking_rule=classification.blocking_rule or "dangerous",
                        risk_level="dangerous",
                    )
                    emit_event(event)
                return False, f"Dangerous (requires approval): {classification.reason}"

        # Check scope limits
        if action.path:
            from pathlib import Path as PathLib
            changes = [FileChange(
                path=PathLib(action.path),
                lines_added=len(action.content.splitlines()) if action.content else 10,
                lines_removed=0,
            )]
            scope_check = self.scope_tracker.check_goal(changes, "autonomous")
            if not scope_check.passed:
                if emit_event:
                    from sunwell.agent.events import autonomous_action_blocked_event
                    event = autonomous_action_blocked_event(
                        action_type=action.action_type,
                        path=action.path,
                        reason=scope_check.reason,
                        blocking_rule=f"scope:{scope_check.limit_type}",
                        risk_level="moderate",
                    )
                    emit_event(event)
                return False, f"Scope exceeded: {scope_check.reason}"

        return True, None

    def record_autonomous_violation(
        self,
        action: Action,
        classification: ActionClassification,
        user_approved: bool,
        is_false_positive: bool = False,
        comment: str | None = None,
    ) -> None:
        """Record a violation from autonomous mode.

        RFC-130: Records violations for adaptive learning.

        Args:
            action: The blocked action
            classification: The classification that blocked it
            user_approved: Whether user approved after escalation
            is_false_positive: Whether user marked as false positive
            comment: Optional user comment
        """
        from sunwell.guardrails.classifier import SmartActionClassifier

        if not isinstance(self.classifier, SmartActionClassifier):
            return

        self.classifier.record_user_feedback(
            action=action,
            classification=classification,
            approved=user_approved,
            is_false_positive=is_false_positive,
            comment=comment,
        )

    async def get_guard_evolutions(self) -> list:
        """Get suggested guard evolutions.

        RFC-130: Returns evolution suggestions based on violation patterns.

        Returns:
            List of GuardEvolution suggestions
        """
        from sunwell.guardrails.classifier import SmartActionClassifier

        if not isinstance(self.classifier, SmartActionClassifier):
            return []

        return await self.classifier.suggest_evolutions()

    def get_guard_stats(self) -> dict:
        """Get guardrail statistics including violations.

        Returns:
            Dict with stats including session stats and violation info
        """
        from sunwell.guardrails.classifier import SmartActionClassifier

        stats = self.get_session_stats()

        if isinstance(self.classifier, SmartActionClassifier):
            stats["violations"] = self.classifier.get_violation_stats()

        return stats

    async def can_auto_approve_external(
        self,
        goal: Goal,
        event: ExternalEvent,
        external_policy: ExternalGoalPolicy | None = None,
    ) -> bool:
        """Check if external-triggered goal can be auto-approved (RFC-049).

        External goals have ADDITIONAL scrutiny beyond normal guardrails:
        1. Source must be in trusted_external_sources
        2. Event type must allow auto-approval per policy
        3. All standard guardrail checks still apply

        Args:
            goal: The goal to check
            event: The external event that triggered the goal
            external_policy: Policy for external event auto-approval

        Returns:
            True if goal can be auto-approved
        """
        from sunwell.external.types import EventSource, EventType

        # 1. Check source trust
        trusted_sources = getattr(
            self.config, "trusted_external_sources",
            frozenset({EventSource.GITHUB, EventSource.GITLAB})
        )
        if event.source not in trusted_sources:
            return False

        # 2. Check event type allows auto-approve
        if external_policy is None:
            # No external policy - never auto-approve external
            return False

        match event.event_type:
            case EventType.CI_FAILURE:
                if not external_policy.auto_approve_ci_failures:
                    return False
            case EventType.ISSUE_OPENED:
                if not external_policy.auto_approve_issues:
                    return False
            case _:
                return False  # Unknown types never auto-approve

        # 3. Standard guardrail checks
        return await self.can_auto_approve(goal)

    def _classify_goal(self, goal: Goal) -> ActionClassification:
        """Classify a goal based on its properties.

        Converts goal to an Action and classifies it.
        """
        # Extract path from goal if available
        path = None
        if hasattr(goal, "scope") and goal.scope.allowed_paths:
            # Use first allowed path as representative
            path = str(next(iter(goal.scope.allowed_paths)))

        action = Action(
            action_type=f"goal_{goal.category}",
            path=path,
            content=goal.description,
        )

        return self.classifier.classify(action)

    def _goal_to_changes(self, goal: Goal) -> list[FileChange]:
        """Convert goal scope to file changes for scope checking."""
        changes: list[FileChange] = []

        if hasattr(goal, "scope"):
            scope = goal.scope
            # Estimate based on scope limits
            for path in scope.allowed_paths:
                changes.append(
                    FileChange(
                        path=path,
                        lines_added=scope.max_lines_changed // 2,
                        lines_removed=scope.max_lines_changed // 4,
                    )
                )

        # If no explicit scope, create estimate from goal
        if not changes:
            changes.append(
                FileChange(
                    path=Path("estimated.py"),
                    lines_added=100,
                    lines_removed=50,
                )
            )

        return changes

    def _determine_escalation_reason(
        self,
        classification: ActionClassification,
        scope_check: ScopeCheckResult,
    ) -> EscalationReason:
        """Determine the primary escalation reason."""
        if classification.risk == ActionRisk.FORBIDDEN:
            return EscalationReason.FORBIDDEN_ACTION
        if classification.risk == ActionRisk.DANGEROUS:
            return EscalationReason.DANGEROUS_ACTION
        if not scope_check.passed:
            if scope_check.limit_type == "require_tests":
                return EscalationReason.MISSING_TESTS
            return EscalationReason.SCOPE_EXCEEDED
        return EscalationReason.UNKNOWN_ACTION

    def _get_escalation_details(
        self,
        goal: Goal,
        classification: ActionClassification,
        scope_check: ScopeCheckResult,
    ) -> str:
        """Get detailed explanation for escalation."""
        lines = [
            f"Goal '{goal.title}' requires approval.",
            "",
            f"Category: {goal.category}",
            f"Complexity: {goal.estimated_complexity}",
        ]

        if classification.risk != ActionRisk.SAFE:
            lines.extend([
                "",
                f"Risk Level: {classification.risk.value.upper()}",
                f"Reason: {classification.reason}",
            ])

        if not scope_check.passed:
            lines.extend([
                "",
                f"Scope Issue: {scope_check.reason}",
            ])

        return "\n".join(lines)

    def _get_blocking_rule(
        self,
        classification: ActionClassification,
        scope_check: ScopeCheckResult,
    ) -> str:
        """Get the blocking rule name."""
        if classification.blocking_rule:
            return classification.blocking_rule
        if not scope_check.passed:
            return f"scope_{scope_check.limit_type}"
        return "unknown"


async def execute_with_guardrails(
    goal: Goal,
    guardrails: GuardrailSystem,
    execute_fn,
) -> dict:
    """Execute a goal with guardrail protection.

    High-level helper that wraps goal execution with all guardrail checks.

    Args:
        goal: The goal to execute
        guardrails: GuardrailSystem instance
        execute_fn: Async function to execute the goal

    Returns:
        Execution result dictionary
    """
    # 1. Check if auto-approvable
    can_auto = await guardrails.can_auto_approve(goal)

    if not can_auto:
        # 2. Escalate for approval
        resolution = await guardrails.escalate_goal(goal)

        if resolution.action == "skip":
            return {"status": "skipped", "goal_id": goal.id}
        elif resolution.action == "abort":
            return {"status": "aborted", "goal_id": goal.id}
        elif resolution.action != "approve":
            return {"status": "skipped", "goal_id": goal.id, "action": resolution.action}

    # 3. Execute the goal
    guardrails.scope_tracker.start_goal()
    result = await execute_fn(goal)

    # 4. Checkpoint if successful
    if result.get("success", False):
        changes = [
            FileChange(path=Path(f), lines_added=10, lines_removed=5)
            for f in result.get("files_changed", [])
        ]
        await guardrails.checkpoint_goal(goal, changes)

    return result
