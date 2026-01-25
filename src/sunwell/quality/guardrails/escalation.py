"""Escalation System for Autonomy Guardrails (RFC-048).

Handles escalations with clear user communication.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sunwell.quality.guardrails.types import (
    ActionClassification,
    Escalation,
    EscalationOption,
    EscalationReason,
    EscalationResolution,
    ScopeCheckResult,
)


class UIProtocol(Protocol):
    """Protocol for UI interactions during escalation."""

    async def show_escalation(
        self,
        severity: str,
        message: str,
        options: list[dict],
        recommended: str,
    ) -> None:
        """Show escalation to user."""
        ...

    async def await_escalation_response(self, escalation_id: str) -> dict:
        """Await user's response to escalation."""
        ...


@dataclass(slots=True)
class EscalationHandler:
    """Handle escalations with clear user communication.

    Escalations are the mechanism for getting human input when
    guardrails are triggered. They present clear options and
    explanations to help users make informed decisions.
    """

    ui: UIProtocol | None = None
    """UI for user interaction (None = use default)."""

    auto_response: str | None = None
    """Auto-response for testing (skip UI)."""

    on_escalate: Callable[[Escalation], None] | None = None
    """Callback when escalation is created."""

    _pending: dict = None

    def __post_init__(self):
        self._pending = {}

    async def escalate(self, escalation: Escalation) -> EscalationResolution:
        """Present escalation to user and await resolution.

        Args:
            escalation: The escalation to present

        Returns:
            EscalationResolution with user's decision
        """
        # Store pending
        self._pending[escalation.id] = escalation

        # Callback if registered
        if self.on_escalate:
            self.on_escalate(escalation)

        # Auto-response for testing
        if self.auto_response:
            return EscalationResolution(
                escalation_id=escalation.id,
                option_id=self.auto_response,
                action=self.auto_response,
                acknowledged=True,
            )

        # Format message
        message = self._format_escalation(escalation)

        # Present to user
        if self.ui:
            await self.ui.show_escalation(
                severity=escalation.severity,
                message=message,
                options=[self._format_option(o) for o in escalation.options],
                recommended=escalation.recommended_option,
            )

            # Await response
            response = await self.ui.await_escalation_response(escalation.id)
            return self._process_response(escalation, response)

        # No UI - default to skip
        return EscalationResolution(
            escalation_id=escalation.id,
            option_id="skip",
            action="skip",
            acknowledged=False,
        )

    def create_escalation(
        self,
        goal_id: str,
        reason: EscalationReason,
        details: str,
        blocking_rule: str,
        action_classification: ActionClassification | None = None,
        scope_check: ScopeCheckResult | None = None,
        verification_confidence: float | None = None,
    ) -> Escalation:
        """Create an escalation with appropriate options.

        Args:
            goal_id: ID of the goal being escalated
            reason: Why escalation was triggered
            details: Human-readable explanation
            blocking_rule: Which rule triggered this
            action_classification: Classification if action-related
            scope_check: Scope check if limit-related
            verification_confidence: Confidence if verification-related

        Returns:
            Escalation ready to present to user
        """
        escalation_id = f"esc-{uuid.uuid4().hex[:8]}"
        options = self._get_options_for_reason(reason)
        recommended = self._get_recommended_option(reason)

        return Escalation(
            id=escalation_id,
            goal_id=goal_id,
            reason=reason,
            details=details,
            blocking_rule=blocking_rule,
            action_classification=action_classification,
            scope_check=scope_check,
            verification_confidence=verification_confidence,
            options=options,
            recommended_option=recommended,
        )

    def get_pending(self, escalation_id: str) -> Escalation | None:
        """Get a pending escalation by ID."""
        return self._pending.get(escalation_id)

    def clear_pending(self, escalation_id: str) -> None:
        """Clear a pending escalation."""
        self._pending.pop(escalation_id, None)

    def _get_options_for_reason(
        self, reason: EscalationReason
    ) -> tuple[EscalationOption, ...]:
        """Get appropriate options for an escalation reason."""
        # Common options
        approve = EscalationOption(
            id="approve",
            label="Approve",
            description="Proceed with this action",
            action="approve",
        )
        approve_once = EscalationOption(
            id="approve_once",
            label="Approve once",
            description="Approve this instance only",
            action="approve_once",
        )
        skip = EscalationOption(
            id="skip",
            label="Skip",
            description="Skip this goal, continue with others",
            action="skip",
        )
        abort = EscalationOption(
            id="abort",
            label="Abort session",
            description="Stop autonomous mode entirely",
            action="abort",
        )

        match reason:
            case EscalationReason.FORBIDDEN_ACTION:
                # Cannot approve forbidden actions
                return (skip, abort)

            case EscalationReason.DANGEROUS_ACTION:
                return (
                    EscalationOption(
                        id="approve",
                        label="Approve",
                        description="Review and proceed if correct",
                        action="approve",
                        risk_acknowledgment="This is a dangerous action. Please review carefully.",
                    ),
                    skip,
                    abort,
                )

            case EscalationReason.SCOPE_EXCEEDED:
                return (
                    EscalationOption(
                        id="split",
                        label="Split goal",
                        description="Break into smaller goals",
                        action="split",
                    ),
                    EscalationOption(
                        id="approve",
                        label="Approve anyway",
                        description="Proceed despite exceeding limit",
                        action="approve",
                        risk_acknowledgment="This exceeds scope limits.",
                    ),
                    EscalationOption(
                        id="relax",
                        label="Relax limit",
                        description="Temporarily increase limit for this session",
                        action="relax",
                    ),
                    skip,
                )

            case EscalationReason.LOW_CONFIDENCE:
                return (
                    EscalationOption(
                        id="approve",
                        label="Approve",
                        description="Proceed despite low confidence",
                        action="approve",
                        risk_acknowledgment="Verification confidence is below threshold.",
                    ),
                    EscalationOption(
                        id="modify",
                        label="Modify goal",
                        description="Change the goal description",
                        action="modify",
                    ),
                    skip,
                    abort,
                )

            case EscalationReason.MISSING_TESTS:
                return (
                    approve,
                    EscalationOption(
                        id="relax",
                        label="Skip test requirement",
                        description="Proceed without adding tests",
                        action="relax",
                    ),
                    skip,
                )

            case _:
                return (approve, approve_once, skip, abort)

    def _get_recommended_option(self, reason: EscalationReason) -> str:
        """Get the recommended option for an escalation reason."""
        match reason:
            case EscalationReason.FORBIDDEN_ACTION:
                return "skip"
            case EscalationReason.DANGEROUS_ACTION:
                return "approve"  # Review and approve
            case EscalationReason.SCOPE_EXCEEDED:
                return "split"
            case EscalationReason.LOW_CONFIDENCE:
                return "skip"
            case EscalationReason.MISSING_TESTS:
                return "approve"
            case _:
                return "approve"

    def _format_escalation(self, esc: Escalation) -> str:
        """Format escalation for display."""
        lines = [
            f"⚠️ **Guardrail Triggered**: {esc.blocking_rule}",
            "",
            f"**Goal**: {esc.goal_id}",
            f"**Reason**: {esc.reason.value}",
            "",
            f"{esc.details}",
        ]

        if esc.action_classification:
            ac = esc.action_classification
            lines.extend([
                "",
                f"**Action**: {ac.action_type}",
                f"**Risk Level**: {ac.risk.value.upper()}",
                f"**Path**: {ac.path or 'N/A'}",
            ])

        if esc.scope_check and not esc.scope_check.passed:
            lines.extend([
                "",
                f"**Scope Issue**: {esc.scope_check.reason}",
            ])

        if esc.verification_confidence is not None:
            lines.extend([
                "",
                f"**Verification Confidence**: {esc.verification_confidence:.0%}",
            ])

        return "\n".join(lines)

    def _format_option(self, option: EscalationOption) -> dict:
        """Format option for UI."""
        return {
            "id": option.id,
            "label": option.label,
            "description": option.description,
            "action": option.action,
            "risk_acknowledgment": option.risk_acknowledgment,
        }

    def _process_response(
        self, escalation: Escalation, response: dict
    ) -> EscalationResolution:
        """Process user response to escalation."""
        option_id = response.get("option_id", "skip")
        acknowledged = response.get("acknowledged", False)
        modified_goal = response.get("modified_goal")

        # Find the action for this option
        action = "skip"
        for opt in escalation.options:
            if opt.id == option_id:
                action = opt.action
                break

        # Clear from pending
        self.clear_pending(escalation.id)

        return EscalationResolution(
            escalation_id=escalation.id,
            option_id=option_id,
            action=action,
            acknowledged=acknowledged,
            modified_goal=modified_goal,
        )
