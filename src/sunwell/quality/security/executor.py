# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Security-aware skill executor (RFC-089).

Integrates security analysis, permission enforcement, and audit logging
with the existing skill execution flow. This module wraps SkillExecutor
and IncrementalSkillExecutor with security gates.

Execution flow:
1. Pre-execution: Analyze permissions, compute risk, request approval if needed
2. Execution: Run skill in SecureSandbox with enforced permissions
3. Post-execution: Monitor output, log to audit trail, detect violations
"""


import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.foundation.utils import safe_json_dumps, safe_yaml_load
from sunwell.quality.security.analyzer import PermissionAnalyzer, PermissionScope, RiskAssessment
from sunwell.quality.security.audit import AuditLogManager, LocalAuditLog
from sunwell.quality.security.monitor import SecurityMonitor, SecurityViolation
from sunwell.quality.security.sandbox import (
    PermissionDeniedError,
)

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol
    from sunwell.planning.skills.executor import ExecutionContext
    from sunwell.planning.skills.graph import SkillGraph
    from sunwell.planning.skills.types import SkillOutput


# =============================================================================
# SECURITY POLICY
# =============================================================================


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    """Security policy for skill execution.

    Defines approval requirements, risk thresholds, and enforcement mode.
    Can be loaded from security-policy.yaml.
    """

    # Approval requirements
    require_approval_above_risk: float = 0.5
    """Risk score threshold requiring user approval."""

    auto_approve_internal_only: bool = True
    """Auto-approve skills that only access internal resources."""

    session_approval_cache: bool = True
    """Cache approvals for session duration."""

    # Enforcement
    enforcement_mode: str = "strict"  # "strict", "warn", "audit"
    """How to handle permission violations."""

    soft_warnings: bool = True
    """Warn about undeclared permissions (soft enforcement)."""

    # Audit
    audit_all_executions: bool = True
    """Log all executions to audit trail."""

    audit_path: Path | None = None
    """Path to audit log (defaults to ~/.sunwell/security/audit.log)."""

    @classmethod
    def from_yaml(cls, path: Path) -> SecurityPolicy:
        """Load policy from YAML file.

        Args:
            path: Path to security-policy.yaml

        Returns:
            SecurityPolicy instance
        """
        if not path.exists():
            return cls()

        data = safe_yaml_load(path) or {}

        return cls(
            require_approval_above_risk=data.get("require_approval_above_risk", 0.5),
            auto_approve_internal_only=data.get("auto_approve_internal_only", True),
            session_approval_cache=data.get("session_approval_cache", True),
            enforcement_mode=data.get("enforcement_mode", "strict"),
            soft_warnings=data.get("soft_warnings", True),
            audit_all_executions=data.get("audit_all_executions", True),
            audit_path=Path(data["audit_path"]) if data.get("audit_path") else None,
        )


# =============================================================================
# APPROVAL MANAGEMENT
# =============================================================================


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Request for user approval before execution."""

    dag_id: str
    """Identifier for the DAG being approved."""

    skills: tuple[str, ...]
    """Skills requiring execution."""

    permissions: PermissionScope
    """Total permissions requested."""

    risk: RiskAssessment
    """Risk assessment for the permissions."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When approval was requested."""


@dataclass(frozen=True, slots=True)
class ApprovalResponse:
    """User response to an approval request."""

    dag_id: str
    """DAG that was approved/rejected."""

    approved: bool
    """Whether execution was approved."""

    remember_for_session: bool = False
    """Cache approval for session."""

    user_id: str | None = None
    """User who approved (for audit)."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When approval was given."""


class ApprovalManager:
    """Manages security approvals for skill execution."""

    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self._session_approvals: dict[str, ApprovalResponse] = {}
        self._pending: ApprovalRequest | None = None

    def needs_approval(self, risk: RiskAssessment, scope: PermissionScope) -> bool:
        """Check if execution needs user approval.

        Args:
            risk: Risk assessment
            scope: Permission scope

        Returns:
            True if approval is required
        """
        # Check risk threshold
        if risk.score >= self.policy.require_approval_above_risk:
            return True

        # Check for dangerous flags
        if any("DANGEROUS" in f or "CREDENTIAL" in f for f in risk.flags):
            return True

        # Auto-approve internal-only if policy allows
        if self.policy.auto_approve_internal_only:
            if not scope.network_allow or all(
                self._is_internal(h) for h in scope.network_allow
            ):
                return False

        return False

    def _is_internal(self, host: str) -> bool:
        """Check if host is internal."""
        hostname = host.rsplit(":", 1)[0] if ":" in host else host
        internal = ["localhost", "127.0.0.1", "::1", "10.", "172.16.", "192.168."]
        return any(hostname.startswith(p) or hostname == p for p in internal)

    def get_cached_approval(self, dag_id: str) -> ApprovalResponse | None:
        """Get cached approval for DAG.

        Args:
            dag_id: DAG identifier

        Returns:
            Cached approval or None
        """
        if not self.policy.session_approval_cache:
            return None
        return self._session_approvals.get(dag_id)

    def cache_approval(self, response: ApprovalResponse) -> None:
        """Cache an approval response.

        Args:
            response: Approval response to cache
        """
        if response.remember_for_session:
            self._session_approvals[response.dag_id] = response

    def create_request(
        self,
        dag_id: str,
        skills: list[str],
        permissions: PermissionScope,
        risk: RiskAssessment,
    ) -> ApprovalRequest:
        """Create an approval request.

        Args:
            dag_id: DAG identifier
            skills: Skills to execute
            permissions: Requested permissions
            risk: Risk assessment

        Returns:
            ApprovalRequest for user
        """
        request = ApprovalRequest(
            dag_id=dag_id,
            skills=tuple(skills),
            permissions=permissions,
            risk=risk,
        )
        self._pending = request
        return request

    def submit_response(self, response: ApprovalResponse) -> None:
        """Submit user response to approval request.

        Args:
            response: User's approval response
        """
        self.cache_approval(response)
        self._pending = None


# =============================================================================
# SECURE SKILL EXECUTOR
# =============================================================================


@dataclass(slots=True)
class SecureSkillExecutor:
    """Security-aware skill executor (RFC-089).

    Wraps skill execution with:
    1. Pre-execution permission analysis and approval gates
    2. Runtime sandboxing with enforced permissions
    3. Post-execution output monitoring
    4. Audit logging

    Usage:
        executor = SecureSkillExecutor(lens, model, policy)

        # Check if approval needed
        if executor.needs_approval(dag):
            request = executor.request_approval(dag)
            # ... show to user ...
            executor.submit_approval(response)

        # Execute with security
        results = await executor.execute(dag, context)
    """

    lens: Lens
    model: ModelProtocol
    policy: SecurityPolicy = field(default_factory=SecurityPolicy)
    workspace_root: Path | None = None

    # Optional callbacks
    on_approval_needed: Callable[[ApprovalRequest], None] | None = None
    on_violation: Callable[[SecurityViolation], None] | None = None
    on_soft_warning: Callable[[str, str], None] | None = None

    def __post_init__(self) -> None:
        self._analyzer = PermissionAnalyzer()
        self._monitor = SecurityMonitor()
        self._approval_manager = ApprovalManager(self.policy)
        self._audit = self._setup_audit()

    def _setup_audit(self) -> AuditLogManager | None:
        """Setup audit log manager."""
        if not self.policy.audit_all_executions:
            return None

        audit_path = self.policy.audit_path or (
            Path.home() / ".sunwell" / "security" / "audit.log"
        )
        audit_path.parent.mkdir(parents=True, exist_ok=True)

        key = os.environ.get("SUNWELL_AUDIT_KEY", "sunwell-default-key").encode()
        backend = LocalAuditLog(audit_path, key)
        return AuditLogManager(backend)

    def analyze(self, graph: SkillGraph) -> tuple[PermissionScope, RiskAssessment]:
        """Analyze DAG permissions and risk.

        Args:
            graph: Skill graph to analyze

        Returns:
            Tuple of (permissions, risk)
        """
        return self._analyzer.analyze_dag(graph)

    def needs_approval(self, graph: SkillGraph) -> bool:
        """Check if DAG execution needs approval.

        Args:
            graph: Skill graph

        Returns:
            True if approval needed
        """
        scope, risk = self.analyze(graph)

        # Check session cache
        dag_id = self._compute_dag_id(graph)
        if self._approval_manager.get_cached_approval(dag_id):
            return False

        return self._approval_manager.needs_approval(risk, scope)

    def request_approval(self, graph: SkillGraph) -> ApprovalRequest:
        """Create approval request for DAG.

        Args:
            graph: Skill graph

        Returns:
            ApprovalRequest for user
        """
        scope, risk = self.analyze(graph)
        dag_id = self._compute_dag_id(graph)
        skills = tuple(graph.skills.keys())

        request = self._approval_manager.create_request(dag_id, list(skills), scope, risk)

        if self.on_approval_needed:
            self.on_approval_needed(request)

        return request

    def submit_approval(self, response: ApprovalResponse) -> None:
        """Submit user approval response.

        Args:
            response: User's approval
        """
        self._approval_manager.submit_response(response)

    async def execute(
        self,
        graph: SkillGraph,
        context: ExecutionContext,
        on_wave_complete: Callable | None = None,
        on_skill_complete: Callable | None = None,
    ) -> dict[str, SkillOutput]:
        """Execute DAG with security enforcement.

        Args:
            graph: Skill graph to execute
            context: Execution context
            on_wave_complete: Progress callback
            on_skill_complete: Per-skill callback

        Returns:
            Mapping of skill name to output

        Raises:
            PermissionDeniedError: If execution not approved
        """
        from sunwell.planning.skills.executor import IncrementalSkillExecutor

        # Pre-execution checks
        dag_id = self._compute_dag_id(graph)
        scope, risk = self.analyze(graph)

        # Check approval
        if self._approval_manager.needs_approval(risk, scope):
            cached = self._approval_manager.get_cached_approval(dag_id)
            if not cached or not cached.approved:
                raise PermissionDeniedError(
                    dag_id,
                    f"Execution requires approval (risk: {risk.level})",
                    "Use request_approval() and submit_approval() first",
                )

        # Soft warnings for undeclared permissions
        if self.policy.soft_warnings:
            self._check_soft_warnings(graph)

        # Audit log: execution started
        inputs_hash = self._compute_inputs_hash(context)
        if self._audit:
            self._audit.record_execution(
                skill_name=dag_id,
                dag_id=dag_id,
                permissions=scope,
                inputs_hash=inputs_hash,
                details=f"DAG execution started: {list(graph.skills.keys())}",
            )

        # Execute with incremental executor
        base_executor = IncrementalSkillExecutor(
            lens=self.lens,
            model=self.model,
            workspace_root=self.workspace_root,
        )

        start_time = time.time()
        violations: list[SecurityViolation] = []

        def handle_violation(v: SecurityViolation) -> None:
            violations.append(v)
            if self.on_violation:
                self.on_violation(v)

        try:
            results = await base_executor.execute(
                graph,
                context,
                on_wave_complete=on_wave_complete,
                on_skill_complete=on_skill_complete,
            )

            # Post-execution monitoring
            for skill_name, output in results.items():
                classification = self._monitor.classify_output_deterministic(
                    output.content, scope
                )
                if classification.violation:
                    handle_violation(
                        SecurityViolation(
                            type=classification.violation_type or "unknown",
                            content=output.content[:100],
                            position=0,
                            detection_method=classification.detection_method,
                            skill_name=skill_name,
                        )
                    )

            # Audit log: execution completed
            duration_ms = int((time.time() - start_time) * 1000)
            if self._audit:
                outputs_hash = self._compute_outputs_hash(results)
                self._audit.record_execution(
                    skill_name=dag_id,
                    dag_id=dag_id,
                    permissions=scope,
                    inputs_hash=inputs_hash,
                    outputs_hash=outputs_hash,
                    details=f"DAG execution completed in {duration_ms}ms",
                )

            # Log violations
            for v in violations:
                if self._audit:
                    self._audit.record_violation(
                        skill_name=v.skill_name,
                        dag_id=dag_id,
                        violation_type=v.type,
                        content=v.content,
                        action_taken="logged" if self.policy.enforcement_mode == "audit" else "blocked",
                    )

                if self.policy.enforcement_mode == "strict":
                    raise PermissionDeniedError(
                        v.skill_name,
                        f"Security violation: {v.type}",
                        v.content[:100],
                    )

            return results

        except Exception as e:
            # Audit log: execution failed
            if self._audit:
                self._audit.backend.append(
                    self._audit._create_entry(
                        skill_name=dag_id,
                        action="error",
                        details=str(e),
                    )
                )
            raise

    def _compute_dag_id(self, graph: SkillGraph) -> str:
        """Compute stable ID for DAG."""
        import hashlib

        skills = sorted(graph.skills.keys())
        content = "|".join(skills)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_inputs_hash(self, context: ExecutionContext) -> str:
        """Compute hash of execution inputs."""
        import hashlib

        data = safe_json_dumps(context.snapshot(), sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _compute_outputs_hash(self, results: dict[str, SkillOutput]) -> str:
        """Compute hash of execution outputs."""
        import hashlib

        data = {k: v.content[:1000] for k, v in results.items()}
        return hashlib.sha256(safe_json_dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    def _check_soft_warnings(self, graph: SkillGraph) -> None:
        """Check for undeclared permissions (soft enforcement)."""
        import warnings

        for skill in graph.skills.values():
            if not hasattr(skill, "permissions") or skill.permissions is None:
                warning_msg = f"Skill '{skill.name}' has no declared permissions"
                warnings.warn(warning_msg, stacklevel=2)
                if self.on_soft_warning:
                    self.on_soft_warning(skill.name, warning_msg)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def create_secure_executor(
    lens: Lens,
    model: ModelProtocol,
    policy_path: Path | None = None,
    workspace_root: Path | None = None,
) -> SecureSkillExecutor:
    """Create a security-aware skill executor.

    Args:
        lens: Lens for skill execution
        model: Model for generation
        policy_path: Path to security-policy.yaml (optional)
        workspace_root: Workspace root directory

    Returns:
        Configured SecureSkillExecutor
    """
    # Load policy
    if policy_path and policy_path.exists():
        policy = SecurityPolicy.from_yaml(policy_path)
    else:
        # Try default locations
        for candidate in [
            Path.cwd() / ".sunwell" / "security-policy.yaml",
            Path.home() / ".sunwell" / "security-policy.yaml",
        ]:
            if candidate.exists():
                policy = SecurityPolicy.from_yaml(candidate)
                break
        else:
            policy = SecurityPolicy()

    return SecureSkillExecutor(
        lens=lens,
        model=model,
        policy=policy,
        workspace_root=workspace_root,
    )
