# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Security-First Skill Execution (RFC-089).

This module provides declarative permission graphs for AI coding assistants,
enabling enterprise-grade security without sacrificing capability.

Components:
- analyzer: Permission scope analysis and risk assessment
- sandbox: Permission-aware sandboxed execution
- monitor: Real-time security violation detection
- audit: Immutable audit logging with provenance

Integration:
- Extends guardrails.types.ActionRisk for risk classification
- Extends skills.sandbox.ScriptSandbox for execution
- Integrates with skills.graph.SkillGraph for DAG analysis
"""

from sunwell.security.analyzer import (
    DetailedSecurityAnalysis,
    PermissionAnalyzer,
    PermissionScope,
    RiskAssessment,
    RiskWeights,
    SkillPermissionBreakdown,
)
from sunwell.security.approval_cache import (
    ApprovalCacheConfig,
    ApprovalCacheManager,
    ApprovalRecord,
    FileApprovalCache,
    SQLiteApprovalCache,
)
from sunwell.security.audit import (
    AuditBackend,
    AuditEntry,
    AuditLogManager,
    LocalAuditLog,
    S3ObjectLockBackend,
)
from sunwell.security.benchmark import (
    BenchmarkResult,
    BenchmarkSuite,
    run_benchmark_suite,
)
from sunwell.security.diff import (
    ChangeType,
    PermissionChange,
    PermissionDiff,
    PermissionDiffCalculator,
    diff_lens_permissions,
    diff_skill_by_name,
)
from sunwell.security.executor import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalResponse,
    SecureSkillExecutor,
    SecurityPolicy,
    create_secure_executor,
)
from sunwell.security.monitor import (
    SecurityClassification,
    SecurityMonitor,
    SecurityViolation,
)
from sunwell.security.policy import (
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
from sunwell.security.sandbox import (
    PermissionAwareSandboxConfig,
    PermissionDeniedError,
    SecureSandbox,
    SecurityAudit,
)
from sunwell.security.siem import (
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

__all__ = [
    # Analyzer
    "PermissionScope",
    "RiskAssessment",
    "RiskWeights",
    "PermissionAnalyzer",
    "SkillPermissionBreakdown",
    "DetailedSecurityAnalysis",
    # Sandbox
    "PermissionAwareSandboxConfig",
    "SecureSandbox",
    "SecurityAudit",
    "PermissionDeniedError",
    # Monitor
    "SecurityClassification",
    "SecurityMonitor",
    "SecurityViolation",
    # Audit
    "AuditEntry",
    "AuditBackend",
    "AuditLogManager",
    "LocalAuditLog",
    "S3ObjectLockBackend",
    # Executor
    "SecurityPolicy",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalManager",
    "SecureSkillExecutor",
    "create_secure_executor",
    # Policy
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
    # SIEM
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
    # Approval Cache
    "ApprovalRecord",
    "ApprovalCacheConfig",
    "ApprovalCacheManager",
    "FileApprovalCache",
    "SQLiteApprovalCache",
    # Diff
    "ChangeType",
    "PermissionChange",
    "PermissionDiff",
    "PermissionDiffCalculator",
    "diff_lens_permissions",
    "diff_skill_by_name",
    # Benchmark
    "BenchmarkResult",
    "BenchmarkSuite",
    "run_benchmark_suite",
]
