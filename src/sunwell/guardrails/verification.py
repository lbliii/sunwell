"""Verification Gate for Autonomy Guardrails (RFC-048).

Integrates RFC-047 Deep Verification with guardrails.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.guardrails.types import (
    ActionRisk,
    VerificationGateResult,
    VerificationThresholds,
)

if TYPE_CHECKING:
    from sunwell.naaru.types import ArtifactSpec
    from sunwell.verification import DeepVerificationResult, DeepVerifier


@dataclass
class VerificationGate:
    """Gate that requires verification before approval.

    Integration with RFC-047:
    - DeepVerifier produces confidence score (0-1)
    - Guardrails use confidence to decide approval

    Decision matrix:

    | Risk | Confidence | Result |
    |------|------------|--------|
    | SAFE | >= 0.7 | Auto-approve |
    | SAFE | < 0.7 | Escalate |
    | MODERATE | >= 0.85 | Auto-approve |
    | MODERATE | < 0.85 | Escalate |
    | DANGEROUS | any | Always escalate |
    | FORBIDDEN | any | Never approve |
    """

    thresholds: VerificationThresholds | None = None
    """Confidence thresholds for auto-approval."""

    verifier: DeepVerifier | None = None
    """RFC-047 Deep Verifier instance."""

    def __post_init__(self):
        if self.thresholds is None:
            self.thresholds = VerificationThresholds()

    async def check(
        self,
        risk: ActionRisk,
        artifact_spec: ArtifactSpec | None = None,
        content: str | None = None,
    ) -> VerificationGateResult:
        """Check if artifact passes verification gate.

        Args:
            risk: Action risk classification
            artifact_spec: Artifact specification (for verification)
            content: Content to verify

        Returns:
            VerificationGateResult with pass/fail and auto-approve status
        """
        # FORBIDDEN never proceeds
        if risk == ActionRisk.FORBIDDEN:
            return VerificationGateResult(
                passed=False,
                auto_approvable=False,
                reason="Action is forbidden",
                confidence=0.0,
            )

        # DANGEROUS always escalates (but can proceed with approval)
        if risk == ActionRisk.DANGEROUS:
            return VerificationGateResult(
                passed=True,  # Can proceed with approval
                auto_approvable=False,
                reason="Dangerous action requires approval",
                confidence=None,  # Skip verification
            )

        # For SAFE and MODERATE, run verification if available
        if self.verifier and artifact_spec and content:
            result = await self._run_verification(artifact_spec, content)
            threshold = self._get_threshold(risk)

            if result.confidence >= threshold:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=True,
                    reason=f"Confidence {result.confidence:.0%} >= {threshold:.0%}",
                    confidence=result.confidence,
                )
            else:
                return VerificationGateResult(
                    passed=True,  # Can proceed with approval
                    auto_approvable=False,
                    reason=f"Confidence {result.confidence:.0%} < {threshold:.0%}",
                    confidence=result.confidence,
                )

        # No verifier available - use risk-based decision
        match risk:
            case ActionRisk.SAFE:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=True,
                    reason="SAFE action (no verifier configured)",
                    confidence=None,
                )
            case ActionRisk.MODERATE:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=False,
                    reason="MODERATE action requires verification",
                    confidence=None,
                )
            case _:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=False,
                    reason="Unknown risk level",
                    confidence=None,
                )

    async def check_quick(self, risk: ActionRisk) -> VerificationGateResult:
        """Quick check without running verification.

        Useful for pre-filtering before investing in verification.

        Args:
            risk: Action risk classification

        Returns:
            VerificationGateResult based on risk only
        """
        match risk:
            case ActionRisk.FORBIDDEN:
                return VerificationGateResult(
                    passed=False,
                    auto_approvable=False,
                    reason="Action is forbidden",
                )
            case ActionRisk.DANGEROUS:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=False,
                    reason="Dangerous action requires approval",
                )
            case ActionRisk.SAFE:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=True,
                    reason="SAFE action",
                )
            case ActionRisk.MODERATE:
                return VerificationGateResult(
                    passed=True,
                    auto_approvable=False,
                    reason="MODERATE action needs verification",
                )

    def _get_threshold(self, risk: ActionRisk) -> float:
        """Get confidence threshold for risk level."""
        match risk:
            case ActionRisk.SAFE:
                return self.thresholds.safe_threshold  # 0.70
            case ActionRisk.MODERATE:
                return self.thresholds.moderate_threshold  # 0.85
            case _:
                return 1.0  # Never auto-approve

    async def _run_verification(
        self,
        artifact_spec: ArtifactSpec,
        content: str,
    ) -> DeepVerificationResult:
        """Run RFC-047 deep verification.

        Args:
            artifact_spec: Artifact specification
            content: Content to verify

        Returns:
            DeepVerificationResult with confidence score
        """
        # Collect verification result from streaming API
        result = None
        async for event in self.verifier.verify(artifact_spec, content):
            if event.stage == "complete":
                result = event.data.get("result")

        if result is None:
            # Verification didn't complete - create minimal result
            from sunwell.verification.types import DeepVerificationResult

            result = DeepVerificationResult(
                passed=False,
                confidence=0.0,
                issues=(),
                generated_tests=(),
                test_results=None,
                perspective_results=(),
                recommendations=("Verification did not complete",),
                duration_ms=0,
            )

        return result


def create_verification_gate(
    model=None,
    cwd=None,
    thresholds: VerificationThresholds | None = None,
    level: str = "quick",
) -> VerificationGate:
    """Create a verification gate with optional verifier.

    Args:
        model: LLM model for verification (None = no verification)
        cwd: Working directory for verification
        thresholds: Confidence thresholds
        level: Verification level ("quick", "standard", "thorough")

    Returns:
        VerificationGate instance
    """
    verifier = None
    if model and cwd:
        try:
            from sunwell.verification import create_verifier

            verifier = create_verifier(model, cwd, level=level)
        except ImportError:
            pass  # Verification module not available

    return VerificationGate(
        thresholds=thresholds,
        verifier=verifier,
    )
