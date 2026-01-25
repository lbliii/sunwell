"""Quality domain - Verification, guardrails, security, confidence scoring.

Key components:
- GuardrailSystem: Multi-layer safety guardrails for autonomous operation (RFC-048)
- DeepVerifier: Semantic correctness verification (RFC-047)
- PermissionAnalyzer: Security analysis for skills (RFC-089)
- WeaknessAnalyzer: Technical debt detection (RFC-063)
- aggregate_confidence: Confidence scoring aggregation (RFC-100)

For advanced usage, import from subpackages directly:
    from sunwell.quality.guardrails import ScopeTracker, TrustZoneEvaluator
    from sunwell.quality.verification import TestGenerator, BehavioralExecutor
    from sunwell.quality.security import SecureSandbox, AuditLogManager

RFC-138: Module Architecture Consolidation
"""

# === Primary Entry Points ===

# Guardrails (RFC-048) - Safety system for autonomous operation
from sunwell.quality.guardrails import (
    GuardrailSystem,
    GuardrailConfig,
    execute_with_guardrails,
    TrustLevel,
    ActionRisk,
)

# Verification (RFC-047) - Deep semantic verification
from sunwell.quality.verification import (
    DeepVerifier,
    create_verifier,
    DeepVerificationResult,
    STANDARD_CONFIG,
)

# Security (RFC-089) - Permission analysis
from sunwell.quality.security import (
    PermissionAnalyzer,
    SecureSkillExecutor,
    create_secure_executor,
)

# Confidence (RFC-100) - Confidence scoring
from sunwell.quality.confidence import (
    ConfidenceLevel,
    aggregate_confidence,
    Evidence,
)

# Weakness (RFC-063) - Technical debt detection
from sunwell.quality.weakness import (
    WeaknessAnalyzer,
    WeaknessType,
    CascadeExecutor,
)

__all__ = [
    # === Guardrails ===
    "GuardrailSystem",
    "GuardrailConfig",
    "execute_with_guardrails",
    "TrustLevel",
    "ActionRisk",
    # === Verification ===
    "DeepVerifier",
    "create_verifier",
    "DeepVerificationResult",
    "STANDARD_CONFIG",
    # === Security ===
    "PermissionAnalyzer",
    "SecureSkillExecutor",
    "create_secure_executor",
    # === Confidence ===
    "ConfidenceLevel",
    "aggregate_confidence",
    "Evidence",
    # === Weakness ===
    "WeaknessAnalyzer",
    "WeaknessType",
    "CascadeExecutor",
]
