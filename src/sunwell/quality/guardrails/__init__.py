"""Autonomy Guardrails Module (RFC-048).

Safe unsupervised operation through multi-layer guardrails:

1. **Action Classification**: Know what's risky
2. **Scope Limits**: Bound blast radius
3. **Verification Gate**: Ensure correctness (RFC-047)
4. **Recovery System**: Enable rollback
5. **Escalation System**: Human-in-the-loop

Example:
    >>> from sunwell.guardrails import GuardrailSystem, GuardrailConfig
    >>>
    >>> # Create guardrail system
    >>> guardrails = GuardrailSystem(repo_path=Path.cwd())
    >>>
    >>> # Start autonomous session
    >>> session = await guardrails.start_session()
    >>>
    >>> # Process goals
    >>> for goal in backlog:
    ...     if await guardrails.can_auto_approve(goal):
    ...         result = await execute(goal)
    ...         await guardrails.checkpoint_goal(goal, result.changes)
    ...     else:
    ...         resolution = await guardrails.escalate_goal(goal)
    ...         if resolution.action == "approve":
    ...             result = await execute(goal)
    ...             await guardrails.checkpoint_goal(goal, result.changes)

Trust Levels:
    - CONSERVATIVE: Propose only, never execute
    - GUARDED: Auto-approve within limits (default)
    - SUPERVISED: Ask for dangerous actions only
    - FULL: Only verified safe actions restricted

Integration:
    - RFC-042 (Adaptive Agent): Wraps agent execution
    - RFC-046 (Autonomous Backlog): Determines auto-approval
    - RFC-047 (Deep Verification): Confidence-based decisions
"""

# Types
# Components
from sunwell.guardrails.classifier import (
    ActionClassifier,
    ActionTaxonomy,
    SmartActionClassifier,
)
from sunwell.guardrails.config import GuardrailConfig, load_config, save_config
from sunwell.guardrails.escalation import EscalationHandler
from sunwell.guardrails.recovery import GuardrailError, RecoveryManager
from sunwell.guardrails.scope import ScopeTracker
from sunwell.guardrails.system import GuardrailSystem, execute_with_guardrails
from sunwell.guardrails.trust import TrustZoneEvaluator, TrustZoneMatch
from sunwell.guardrails.types import (
    Action,
    ActionClassification,
    ActionRisk,
    Escalation,
    EscalationOption,
    EscalationReason,
    EscalationResolution,
    FileChange,
    RecoveryOption,
    RollbackResult,
    ScopeCheckResult,
    ScopeLimits,
    SessionStart,
    TrustLevel,
    TrustZone,
    VerificationGateResult,
    VerificationThresholds,
)
from sunwell.guardrails.verification import VerificationGate, create_verification_gate

__all__ = [
    # Main system
    "GuardrailSystem",
    "execute_with_guardrails",
    # Configuration
    "GuardrailConfig",
    "load_config",
    "save_config",
    # Classification
    "ActionClassifier",
    "ActionTaxonomy",
    "SmartActionClassifier",  # RFC-077: LLM fallback
    # Scope
    "ScopeTracker",
    "ScopeLimits",
    # Trust
    "TrustZoneEvaluator",
    "TrustZoneMatch",
    # Recovery
    "RecoveryManager",
    "GuardrailError",
    # Escalation
    "EscalationHandler",
    # Verification
    "VerificationGate",
    "create_verification_gate",
    # Types
    "Action",
    "ActionClassification",
    "ActionRisk",
    "TrustLevel",
    "TrustZone",
    "FileChange",
    "ScopeCheckResult",
    "Escalation",
    "EscalationReason",
    "EscalationOption",
    "EscalationResolution",
    "SessionStart",
    "RollbackResult",
    "RecoveryOption",
    "VerificationThresholds",
    "VerificationGateResult",
]
