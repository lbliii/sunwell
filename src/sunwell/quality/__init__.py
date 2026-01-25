"""Quality domain — Verification, guardrails, security, confidence scoring, weakness detection.

This domain consolidates all quality assurance modules for safe, verified code generation.

RFC-138: Module Architecture Consolidation

Key components:
- Verification: Deep semantic correctness verification (RFC-047)
- Guardrails: Multi-layer safety guardrails for autonomous operation (RFC-048)
- Security: Permission-aware execution and audit logging (RFC-089)
- Confidence: Confidence scoring and calibration (RFC-100)
- Weakness: Technical debt detection and cascade execution (RFC-063, RFC-069)

Example:
    >>> from sunwell.quality import DeepVerifier, GuardrailSystem, PermissionAnalyzer
    >>> from sunwell.quality import WeaknessAnalyzer, aggregate_confidence
    >>>
    >>> # Deep verification
    >>> verifier = create_verifier(model, cwd, level="standard")
    >>> result = await verifier.verify_quick(artifact_spec, content)
    >>>
    >>> # Guardrails for autonomous operation
    >>> guardrails = GuardrailSystem(repo_path=Path.cwd())
    >>> session = await guardrails.start_session()
    >>> if await guardrails.can_auto_approve(goal):
    ...     result = await execute(goal)
    >>>
    >>> # Security analysis
    >>> analyzer = PermissionAnalyzer()
    >>> analysis = analyzer.analyze_skill(skill_graph)
    >>>
    >>> # Weakness detection
    >>> analyzer = WeaknessAnalyzer()
    >>> weaknesses = analyzer.analyze_codebase(workspace_path)
"""

# Verification (RFC-047)
from sunwell.quality.verification.analyzer import MultiPerspectiveAnalyzer
from sunwell.quality.verification.executor import BehavioralExecutor
from sunwell.quality.verification.extractor import SpecificationExtractor
from sunwell.quality.verification.generator import TestGenerator
from sunwell.quality.verification.triangulator import ConfidenceTriangulator
from sunwell.quality.verification.types import (
    QUICK_CONFIG,
    STANDARD_CONFIG,
    THOROUGH_CONFIG,
    BehavioralExecutionResult,
    DeepVerificationConfig,
    DeepVerificationResult,
    GeneratedTest,
    InputSpec,
    OutputSpec,
    PerspectiveResult,
    SemanticIssue,
    Specification,
    TestExecutionResult,
    VerificationEvent,
)
from sunwell.quality.verification.verifier import DeepVerifier, create_verifier

# Guardrails (RFC-048)
from sunwell.quality.guardrails.classifier import (
    ActionClassifier,
    ActionTaxonomy,
    SmartActionClassifier,
)
from sunwell.quality.guardrails.config import GuardrailConfig, load_config, save_config
from sunwell.quality.guardrails.escalation import EscalationHandler
from sunwell.quality.guardrails.recovery import GuardrailError, RecoveryManager
from sunwell.quality.guardrails.scope import ScopeTracker
from sunwell.quality.guardrails.system import GuardrailSystem, execute_with_guardrails
from sunwell.quality.guardrails.trust import TrustZoneEvaluator, TrustZoneMatch
from sunwell.quality.guardrails.types import (
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
from sunwell.quality.guardrails.verification import (
    VerificationGate,
    create_verification_gate,
)

# Security (RFC-089)
from sunwell.quality.security.analyzer import (
    DetailedSecurityAnalysis,
    PermissionAnalyzer,
    PermissionScope,
    RiskAssessment,
    RiskWeights,
    SkillPermissionBreakdown,
)
from sunwell.quality.security.approval_cache import (
    ApprovalCacheConfig,
    ApprovalCacheManager,
    ApprovalRecord,
    FileApprovalCache,
    SQLiteApprovalCache,
)
from sunwell.quality.security.audit import (
    AuditBackend,
    AuditEntry,
    AuditLogManager,
    LocalAuditLog,
    S3ObjectLockBackend,
)
from sunwell.quality.security.benchmark import (
    BenchmarkResult,
    BenchmarkSuite,
    run_benchmark_suite,
)
from sunwell.quality.security.diff import (
    ChangeType,
    PermissionChange,
    PermissionDiff,
    PermissionDiffCalculator,
    diff_lens_permissions,
    diff_skill_by_name,
)
from sunwell.quality.security.executor import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalResponse,
    SecureSkillExecutor,
    SecurityPolicy,
    create_secure_executor,
)
from sunwell.quality.security.monitor import (
    SecurityClassification,
    SecurityMonitor,
    SecurityViolation,
)
from sunwell.quality.security.policy import (
    POLICY_MAX_RISK_THRESHOLD,
    POLICY_MIN_RISK_THRESHOLD,
    POLICY_REQUIRED_FIELDS,
    POLICY_VALID_ENFORCEMENTS,
    PolicyEnforcer,
    PolicyRule,
    PolicyValidationError,
    SecurityPolicyConfig,
    create_example_policy,
    validate_policy,
)
from sunwell.quality.security.sandbox import (
    PermissionAwareSandboxConfig,
    PermissionDeniedError,
    SecureSandbox,
    SecurityAudit,
)
from sunwell.quality.security.siem import (
    CEFFormatter,
    DatadogFormatter,
    ECSFormatter,
    JSONLinesFormatter,
    LEEFFormatter,
    SIEMFormatter,
    SplunkHECFormatter,
    SyslogFormatter,
    export_to_siem,
    get_formatter,
    list_formats,
)

# Confidence (RFC-100)
from sunwell.quality.confidence.aggregation import (
    ConfidenceLevel,
    Evidence,
    ModelNode,
    aggregate_confidence,
    score_to_band,
)
from sunwell.quality.confidence.calibration import (
    CalibrationTracker,
    ConfidenceFeedback,
)

# Weakness (RFC-063, RFC-069)
from sunwell.quality.weakness.analyzer import SmartWeaknessAnalyzer, WeaknessAnalyzer
from sunwell.quality.weakness.cascade import (
    CascadeEngine,
    CascadeExecution,
    CascadePreview,
)
from sunwell.quality.weakness.executor import (
    CascadeArtifactBuilder,
    CascadeExecutor,
    WaveResult,
    create_cascade_executor,
)
from sunwell.quality.weakness.types import (
    CascadeRisk,
    DeltaPreview,
    ExtractedContract,
    WaveConfidence,
    WeaknessScore,
    WeaknessSignal,
    WeaknessType,
)
from sunwell.quality.weakness.verification import run_mypy, run_pytest, run_ruff

__all__ = [
    # Verification (RFC-047)
    "DeepVerifier",
    "create_verifier",
    "SpecificationExtractor",
    "TestGenerator",
    "BehavioralExecutor",
    "MultiPerspectiveAnalyzer",
    "ConfidenceTriangulator",
    "DeepVerificationResult",
    "VerificationEvent",
    "BehavioralExecutionResult",
    "TestExecutionResult",
    "PerspectiveResult",
    "SemanticIssue",
    "Specification",
    "InputSpec",
    "OutputSpec",
    "GeneratedTest",
    "DeepVerificationConfig",
    "QUICK_CONFIG",
    "STANDARD_CONFIG",
    "THOROUGH_CONFIG",
    # Guardrails (RFC-048)
    "GuardrailSystem",
    "execute_with_guardrails",
    "GuardrailConfig",
    "load_config",
    "save_config",
    "ActionClassifier",
    "ActionTaxonomy",
    "SmartActionClassifier",
    "ScopeTracker",
    "ScopeLimits",
    "TrustZoneEvaluator",
    "TrustZoneMatch",
    "RecoveryManager",
    "GuardrailError",
    "EscalationHandler",
    "VerificationGate",
    "create_verification_gate",
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
    # Security (RFC-089)
    "PermissionScope",
    "RiskAssessment",
    "RiskWeights",
    "PermissionAnalyzer",
    "SkillPermissionBreakdown",
    "DetailedSecurityAnalysis",
    "PermissionAwareSandboxConfig",
    "SecureSandbox",
    "SecurityAudit",
    "PermissionDeniedError",
    "SecurityClassification",
    "SecurityMonitor",
    "SecurityViolation",
    "AuditEntry",
    "AuditBackend",
    "AuditLogManager",
    "LocalAuditLog",
    "S3ObjectLockBackend",
    "SecurityPolicy",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalManager",
    "SecureSkillExecutor",
    "create_secure_executor",
    "SecurityPolicyConfig",
    "PolicyRule",
    "PolicyValidationError",
    "PolicyEnforcer",
    "create_example_policy",
    "validate_policy",
    "POLICY_REQUIRED_FIELDS",
    "POLICY_VALID_ENFORCEMENTS",
    "POLICY_MAX_RISK_THRESHOLD",
    "POLICY_MIN_RISK_THRESHOLD",
    "SIEMFormatter",
    "CEFFormatter",
    "LEEFFormatter",
    "SyslogFormatter",
    "JSONLinesFormatter",
    "ECSFormatter",
    "DatadogFormatter",
    "SplunkHECFormatter",
    "get_formatter",
    "export_to_siem",
    "list_formats",
    "ApprovalRecord",
    "ApprovalCacheConfig",
    "ApprovalCacheManager",
    "FileApprovalCache",
    "SQLiteApprovalCache",
    "ChangeType",
    "PermissionChange",
    "PermissionDiff",
    "PermissionDiffCalculator",
    "diff_lens_permissions",
    "diff_skill_by_name",
    "BenchmarkResult",
    "BenchmarkSuite",
    "run_benchmark_suite",
    # Confidence (RFC-100)
    "ConfidenceLevel",
    "Evidence",
    "ModelNode",
    "aggregate_confidence",
    "score_to_band",
    "ConfidenceFeedback",
    "CalibrationTracker",
    # Weakness (RFC-063, RFC-069)
    "WeaknessType",
    "WeaknessSignal",
    "WeaknessScore",
    "ExtractedContract",
    "WaveConfidence",
    "DeltaPreview",
    "CascadeRisk",
    "WaveResult",
    "WeaknessAnalyzer",
    "SmartWeaknessAnalyzer",
    "CascadeEngine",
    "CascadeExecution",
    "CascadePreview",
    "CascadeArtifactBuilder",
    "CascadeExecutor",
    "create_cascade_executor",
    "run_pytest",
    "run_mypy",
    "run_ruff",
]
