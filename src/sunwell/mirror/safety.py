"""Safety checks for RFC-015 Mirror Neuron operations.

Implements guardrails to prevent dangerous self-modifications:
- Core module immutability
- Trust escalation prevention
- Rate limiting on modifications
- Mandatory proposal workflow

These safety constraints cannot be modified by the mirror system itself.
"""


from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.mirror.proposals import Proposal


# Modules that cannot be modified (hardcoded safety)
IMMUTABLE_MODULES: frozenset[str] = frozenset({
    "sunwell/core",
    "sunwell/mirror/safety",
    "sunwell/tools/types",  # Trust level definitions
})

# Settings that cannot be modified via proposals
BLOCKED_MODIFICATION_TARGETS: frozenset[str] = frozenset({
    "trust_level",
    "safety_policy",
    "blocked_patterns",
    "immutable_modules",
    "rate_limits",
    "BLOCKED_MODIFICATION_TARGETS",  # Can't modify this list
    "IMMUTABLE_MODULES",  # Can't modify this list
})

# Patterns in diffs that indicate dangerous modifications
DANGEROUS_PATTERNS: frozenset[str] = frozenset({
    "trust_level =",
    "TrustLevel.",
    "BLOCKED_",
    "IMMUTABLE_",
    "safety_policy",
    "eval(",
    "exec(",
    "__import__",
    "subprocess.call",
    "os.system",
})


@dataclass(slots=True)
class SafetyPolicy:
    """Safety policy for mirror neuron operations.

    This class defines the safety constraints that cannot be
    bypassed by the mirror system.
    """

    # Maximum proposals per hour
    max_proposals_per_hour: int = 10

    # Maximum applications per day
    max_applications_per_day: int = 5

    # Require user confirmation for these operations
    require_confirmation: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "apply_proposal",
            "rollback_proposal",
            "approve_proposal",
        })
    )

    # Operations that are always blocked
    blocked_operations: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "modify_safety_policy",
            "escalate_trust",
            "modify_core",
        })
    )


@dataclass(slots=True)
class SafetyChecker:
    """Validates mirror operations against safety constraints.

    This checker enforces:
    1. Core module immutability
    2. Blocked modification targets
    3. Dangerous pattern detection
    4. Rate limiting

    RFC-085: Renamed sunwell_root to workspace to clarify semantics.
    """

    policy: SafetyPolicy = field(default_factory=SafetyPolicy)
    workspace: Path | None = None  # User's workspace, not Sunwell source

    # Rate limiting state
    _proposal_times: list[datetime] = field(default_factory=list, init=False)
    _application_times: list[datetime] = field(default_factory=list, init=False)

    def validate_proposal(self, proposal: Proposal) -> tuple[bool, str]:
        """Validate that a proposal doesn't violate safety constraints.

        Args:
            proposal: The proposal to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        diff_lower = proposal.diff.lower()

        # Check for blocked modification targets
        for blocked in BLOCKED_MODIFICATION_TARGETS:
            if blocked.lower() in diff_lower:
                return False, f"Cannot modify safety-critical setting: {blocked}"

        # Check for immutable module modifications
        for module in IMMUTABLE_MODULES:
            if module in proposal.diff:
                return False, f"Cannot modify immutable module: {module}"

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in diff_lower:
                return False, f"Dangerous pattern detected: {pattern}"

        # Check rate limits for proposal creation
        if not self._check_proposal_rate():
            return False, "Proposal rate limit exceeded. Wait before creating more proposals."

        return True, "OK"

    def validate_application(self, proposal: Proposal) -> tuple[bool, str]:
        """Validate that a proposal can be applied.

        Additional checks beyond validate_proposal for the actual
        application step.

        Args:
            proposal: The proposal to apply

        Returns:
            Tuple of (is_valid, reason)
        """
        # First run standard proposal validation
        is_valid, reason = self.validate_proposal(proposal)
        if not is_valid:
            return is_valid, reason

        # Check application rate limit
        if not self._check_application_rate():
            return False, "Application rate limit exceeded. Wait before applying more proposals."

        # Verify the proposal was properly approved
        from sunwell.mirror.proposals import ProposalStatus
        if proposal.status != ProposalStatus.APPROVED:
            return False, f"Proposal must be APPROVED before application. Current: {proposal.status.value}"

        return True, "OK"

    def requires_confirmation(self, operation: str) -> bool:
        """Check if an operation requires user confirmation.

        Args:
            operation: The operation name

        Returns:
            True if confirmation is required
        """
        return operation in self.policy.require_confirmation

    def is_operation_blocked(self, operation: str) -> bool:
        """Check if an operation is blocked.

        Args:
            operation: The operation name

        Returns:
            True if the operation is blocked
        """
        return operation in self.policy.blocked_operations

    def _check_proposal_rate(self) -> bool:
        """Check if we're within proposal rate limits."""
        self._prune_old_times(self._proposal_times, hours=1)

        if len(self._proposal_times) >= self.policy.max_proposals_per_hour:
            return False

        self._proposal_times.append(datetime.now())
        return True

    def _check_application_rate(self) -> bool:
        """Check if we're within application rate limits."""
        self._prune_old_times(self._application_times, hours=24)

        if len(self._application_times) >= self.policy.max_applications_per_day:
            return False

        self._application_times.append(datetime.now())
        return True

    def _prune_old_times(self, times: list[datetime], hours: int) -> None:
        """Remove entries older than the specified hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        times[:] = [t for t in times if t > cutoff]

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status.

        Returns:
            Dict with proposal and application limits/usage
        """
        self._prune_old_times(self._proposal_times, hours=1)
        self._prune_old_times(self._application_times, hours=24)

        return {
            "proposals": {
                "used": len(self._proposal_times),
                "limit": self.policy.max_proposals_per_hour,
                "remaining": max(0, self.policy.max_proposals_per_hour - len(self._proposal_times)),
                "window": "1 hour",
            },
            "applications": {
                "used": len(self._application_times),
                "limit": self.policy.max_applications_per_day,
                "remaining": max(0, self.policy.max_applications_per_day - len(self._application_times)),
                "window": "24 hours",
            },
        }


def validate_diff_safety(diff: str) -> tuple[bool, str]:
    """Quick validation of a diff string for safety issues.

    Args:
        diff: The diff content to validate

    Returns:
        Tuple of (is_safe, reason)
    """
    diff_lower = diff.lower()

    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in diff_lower:
            return False, f"Dangerous pattern: {pattern}"

    for blocked in BLOCKED_MODIFICATION_TARGETS:
        if blocked.lower() in diff_lower:
            return False, f"Blocked target: {blocked}"

    return True, "OK"
