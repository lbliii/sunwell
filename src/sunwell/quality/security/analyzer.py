# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Permission analysis and risk assessment (RFC-089).

Analyzes skill DAGs for security permissions and computes risk assessments.
Uses a two-phase detection strategy:
1. Deterministic pattern matching (fast, reliable)
2. Optional LLM classification (for novel patterns)

Integrates with:
- guardrails.types.ActionRisk for risk classification
- skills.graph.SkillGraph for DAG analysis
"""


import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Literal

from sunwell.quality.guardrails.types import ActionRisk

if TYPE_CHECKING:
    from sunwell.planning.skills.graph import SkillGraph
    from sunwell.planning.skills.types import Skill


# =============================================================================
# PERMISSION TYPES
# =============================================================================


@dataclass(frozen=True, slots=True)
class PermissionScope:
    """Total permissions for a skill or DAG.

    Permissions use consistent pattern syntax:
    - Filesystem: Glob patterns (*, **, ~)
    - Shell: Prefix match for security
    - Network: host:port patterns
    - Environment: Exact or prefix match
    """

    filesystem_read: frozenset[str] = frozenset()
    """Paths the skill can read (glob patterns)."""

    filesystem_write: frozenset[str] = frozenset()
    """Paths the skill can write (glob patterns)."""

    network_allow: frozenset[str] = frozenset()
    """Hosts the skill can connect to (host:port patterns)."""

    network_deny: frozenset[str] = field(default_factory=lambda: frozenset(["*"]))
    """Hosts explicitly denied (default: deny all)."""

    shell_allow: frozenset[str] = frozenset()
    """Shell commands allowed (prefix match)."""

    shell_deny: frozenset[str] = frozenset()
    """Shell commands explicitly denied."""

    env_read: frozenset[str] = frozenset()
    """Environment variables the skill can read."""

    env_write: frozenset[str] = frozenset()
    """Environment variables the skill can write."""

    def merge_with(self, other: PermissionScope) -> PermissionScope:
        """Merge two permission scopes (union)."""
        return PermissionScope(
            filesystem_read=self.filesystem_read | other.filesystem_read,
            filesystem_write=self.filesystem_write | other.filesystem_write,
            network_allow=self.network_allow | other.network_allow,
            network_deny=self.network_deny & other.network_deny,  # Intersection for deny
            shell_allow=self.shell_allow | other.shell_allow,
            shell_deny=self.shell_deny | other.shell_deny,
            env_read=self.env_read | other.env_read,
            env_write=self.env_write | other.env_write,
        )

    def is_empty(self) -> bool:
        """Check if this scope has no permissions."""
        return (
            not self.filesystem_read
            and not self.filesystem_write
            and not self.network_allow
            and not self.shell_allow
            and not self.env_read
            and not self.env_write
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            "filesystem_read": sorted(self.filesystem_read),
            "filesystem_write": sorted(self.filesystem_write),
            "network_allow": sorted(self.network_allow),
            "network_deny": sorted(self.network_deny),
            "shell_allow": sorted(self.shell_allow),
            "shell_deny": sorted(self.shell_deny),
            "env_read": sorted(self.env_read),
            "env_write": sorted(self.env_write),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PermissionScope:
        """Deserialize from dictionary."""
        return cls(
            filesystem_read=frozenset(data.get("filesystem_read", [])),
            filesystem_write=frozenset(data.get("filesystem_write", [])),
            network_allow=frozenset(data.get("network_allow", [])),
            network_deny=frozenset(data.get("network_deny", ["*"])),
            shell_allow=frozenset(data.get("shell_allow", [])),
            shell_deny=frozenset(data.get("shell_deny", [])),
            env_read=frozenset(data.get("env_read", [])),
            env_write=frozenset(data.get("env_write", [])),
        )


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Security risk assessment for a permission scope.

    Maps to RFC-048 ActionRisk for integration with existing guardrails:
    - low → ActionRisk.SAFE
    - medium → ActionRisk.MODERATE
    - high → ActionRisk.DANGEROUS
    - critical → ActionRisk.FORBIDDEN
    """

    level: Literal["low", "medium", "high", "critical"]
    """Risk level classification."""

    score: float
    """Numeric risk score (0.0 - 1.0)."""

    flags: tuple[str, ...] = ()
    """Risk flags detected during analysis."""

    recommendations: tuple[str, ...] = ()
    """Recommendations for reducing risk."""

    def to_action_risk(self) -> ActionRisk:
        """Convert to RFC-048 ActionRisk for guardrails integration."""
        mapping = {
            "low": ActionRisk.SAFE,
            "medium": ActionRisk.MODERATE,
            "high": ActionRisk.DANGEROUS,
            "critical": ActionRisk.FORBIDDEN,
        }
        return mapping[self.level]

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            "level": self.level,
            "score": self.score,
            "flags": list(self.flags),
            "recommendations": list(self.recommendations),
        }


RiskContributionLevel = Literal["none", "low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class SkillPermissionBreakdown:
    """Per-skill permission info for transparency."""

    skill_name: str
    preset: str | None
    permissions: PermissionScope
    risk_contribution: RiskContributionLevel
    risk_reason: str | None


@dataclass(frozen=True, slots=True)
class DetailedSecurityAnalysis:
    """Full security analysis with per-skill breakdown."""

    aggregated_permissions: PermissionScope
    aggregated_risk: RiskAssessment
    skill_breakdown: tuple[SkillPermissionBreakdown, ...]
    highest_risk_skill: str | None


@dataclass(frozen=True, slots=True)
class RiskWeights:
    """Configurable risk scoring weights.

    Rationale for defaults (derived from MITRE ATT&CK technique severity):
    - filesystem_write (0.05): Low per-path risk, but accumulates
    - shell_allow (0.10): Commands can chain, 2× file risk
    - network_allow (0.10): Exfiltration vector, matches shell
    - credential_flag (0.30): Direct compromise vector
    - dangerous_flag (0.40): Highest single-action risk
    - external_flag (0.20): Data leakage risk
    """

    filesystem_write: float = 0.05
    """Weight per filesystem write permission."""

    shell_allow: float = 0.10
    """Weight per shell command allowed."""

    network_allow: float = 0.10
    """Weight per network host allowed."""

    credential_flag: float = 0.30
    """Weight per credential access flag."""

    dangerous_flag: float = 0.40
    """Weight per dangerous command flag."""

    external_flag: float = 0.20
    """Weight per external network flag."""


# =============================================================================
# PERMISSION ANALYZER
# =============================================================================


class PermissionAnalyzer:
    """Analyzes DAGs for security permissions.

    Uses a two-phase detection strategy:
    1. Deterministic pattern matching (fast, reliable)
    2. Optional LLM classification (for novel patterns)
    """

    # Deterministic credential patterns (regex)
    # These catch common secrets without LLM overhead
    CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("AWS_SECRET", re.compile(r"[A-Za-z0-9/+=]{40}")),
        ("GITHUB_TOKEN", re.compile(r"ghp_[A-Za-z0-9]{36}")),
        ("SLACK_TOKEN", re.compile(r"xox[baprs]-[0-9A-Za-z-]+")),
        (
            "PRIVATE_KEY",
            re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
        ),
        (
            "JWT",
            re.compile(r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*"),
        ),
        (
            "GENERIC_SECRET",
            re.compile(
                r"(?i)(password|secret|token|api_key)\s*[=:]\s*['\"][^'\"]{8,}"
            ),
        ),
    )

    # High-risk path patterns (glob syntax)
    SENSITIVE_PATHS: frozenset[str] = frozenset([
        "~/.ssh/*",
        "~/.aws/*",
        "~/.config/gcloud/*",
        "~/.kube/config",
        "/etc/passwd",
        "/etc/shadow",
        "**/credentials*",
        "**/*.pem",
        "**/*.key",
        "**/.env",
        "**/.env.*",
        "**/secrets.*",
    ])

    # Dangerous shell command patterns (prefix match)
    # Pattern syntax: prefix match with * as glob
    DANGEROUS_COMMANDS: frozenset[str] = frozenset([
        "rm -rf",  # Recursive delete
        "dd if=",  # Raw disk write
        "mkfs",  # Filesystem format
        ":(){ :|:& };:",  # Fork bomb
        "curl * | sh",  # Remote code exec
        "curl * | bash",
        "wget * | sh",
        "wget * | bash",
        "eval ",  # Arbitrary eval
        "ssh ",  # Remote access
        "scp ",  # Remote copy
        "rsync ",  # Remote sync
        "> /dev/sd",  # Direct disk write
        "chmod 777",  # Overly permissive
        "chown root",  # Privilege escalation
    ])

    def __init__(self, weights: RiskWeights | None = None):
        """Initialize the permission analyzer.

        Args:
            weights: Risk scoring weights (uses defaults if not provided)
        """
        self.weights = weights or RiskWeights()

    def analyze_dag(
        self, dag: SkillGraph
    ) -> tuple[PermissionScope, RiskAssessment]:
        """Compute total permissions and risk for entire DAG.

        Args:
            dag: The skill graph to analyze

        Returns:
            Tuple of (total_permissions, risk_assessment)
        """
        total_scope = PermissionScope()
        flags: list[str] = []

        for skill in dag.skills.values():
            skill_scope = self._extract_permissions(skill)
            total_scope = total_scope.merge_with(skill_scope)

            # Deterministic risk checks (Phase 1)
            flags.extend(self._check_risks_deterministic(skill, skill_scope))

        risk = self._compute_risk(total_scope, flags)
        return total_scope, risk

    def analyze_dag_detailed(self, dag: SkillGraph) -> DetailedSecurityAnalysis:
        """Compute total permissions and per-skill breakdown for a DAG."""
        total_scope = PermissionScope()
        all_flags: list[str] = []
        breakdown: list[SkillPermissionBreakdown] = []
        highest_risk: tuple[str | None, float] = (None, 0.0)

        for skill_name in dag.topological_order():
            skill = dag.get(skill_name)
            if not skill:
                continue
            skill_scope = self._extract_permissions(skill)
            skill_flags = self._check_risks_deterministic(skill, skill_scope)
            all_flags.extend(skill_flags)
            total_scope = total_scope.merge_with(skill_scope)

            skill_risk = self._compute_risk(skill_scope, skill_flags)
            risk_contribution = self._risk_contribution_level(skill_scope, skill_risk, skill_flags)
            risk_reason = self._primary_risk_reason(skill_scope, skill_flags)

            breakdown.append(
                SkillPermissionBreakdown(
                    skill_name=skill.name,
                    preset=skill.preset,
                    permissions=skill_scope,
                    risk_contribution=risk_contribution,
                    risk_reason=risk_reason,
                )
            )

            if skill_risk.score > highest_risk[1]:
                highest_risk = (skill.name, skill_risk.score)

        aggregated_risk = self._compute_risk(total_scope, all_flags)

        return DetailedSecurityAnalysis(
            aggregated_permissions=total_scope,
            aggregated_risk=aggregated_risk,
            skill_breakdown=tuple(breakdown),
            highest_risk_skill=highest_risk[0],
        )

    def analyze_skills_detailed(self, skills: list[Skill]) -> DetailedSecurityAnalysis:
        """Compute permissions and per-skill breakdown for ordered skills."""
        total_scope = PermissionScope()
        all_flags: list[str] = []
        breakdown: list[SkillPermissionBreakdown] = []
        highest_risk: tuple[str | None, float] = (None, 0.0)

        for skill in skills:
            skill_scope = self._extract_permissions(skill)
            skill_flags = self._check_risks_deterministic(skill, skill_scope)
            all_flags.extend(skill_flags)
            total_scope = total_scope.merge_with(skill_scope)

            skill_risk = self._compute_risk(skill_scope, skill_flags)
            risk_contribution = self._risk_contribution_level(skill_scope, skill_risk, skill_flags)
            risk_reason = self._primary_risk_reason(skill_scope, skill_flags)

            breakdown.append(
                SkillPermissionBreakdown(
                    skill_name=skill.name,
                    preset=skill.preset,
                    permissions=skill_scope,
                    risk_contribution=risk_contribution,
                    risk_reason=risk_reason,
                )
            )

            if skill_risk.score > highest_risk[1]:
                highest_risk = (skill.name, skill_risk.score)

        aggregated_risk = self._compute_risk(total_scope, all_flags)

        return DetailedSecurityAnalysis(
            aggregated_permissions=total_scope,
            aggregated_risk=aggregated_risk,
            skill_breakdown=tuple(breakdown),
            highest_risk_skill=highest_risk[0],
        )

    def analyze_skill(self, skill: Skill) -> tuple[PermissionScope, RiskAssessment]:
        """Compute permissions and risk for a single skill.

        Args:
            skill: The skill to analyze

        Returns:
            Tuple of (permissions, risk_assessment)
        """
        scope = self._extract_permissions(skill)
        flags = self._check_risks_deterministic(skill, scope)
        risk = self._compute_risk(scope, flags)
        return scope, risk

    def scan_for_credentials(self, content: str) -> list[tuple[str, str]]:
        """Deterministic credential scanning.

        Runs BEFORE any LLM classification for reliability.

        Args:
            content: Text content to scan

        Returns:
            List of (pattern_name, redacted_value) tuples
        """
        findings: list[tuple[str, str]] = []
        for name, pattern in self.CREDENTIAL_PATTERNS:
            for match in pattern.finditer(content):
                # Redact the actual value for safety
                matched = match.group()
                redacted = matched[:8] + "..." if len(matched) > 8 else "***"
                findings.append((name, redacted))
        return findings

    def _extract_permissions(self, skill: Skill) -> PermissionScope:
        """Extract permission scope from a skill's declaration.

        Args:
            skill: The skill to extract permissions from

        Returns:
            PermissionScope with declared permissions (or empty if none)
        """
        # Check if skill has permissions attribute (RFC-089 extension)
        permissions = getattr(skill, "permissions", None)
        if permissions is None:
            return PermissionScope()

        # Handle dict-based permission declaration
        if isinstance(permissions, dict):
            fs = permissions.get("filesystem", {})
            net = permissions.get("network", {})
            shell = permissions.get("shell", {})
            env = permissions.get("environment", {})

            return PermissionScope(
                filesystem_read=frozenset(fs.get("read", [])),
                filesystem_write=frozenset(fs.get("write", [])),
                network_allow=frozenset(net.get("allow", [])),
                network_deny=frozenset(net.get("deny", ["*"])),
                shell_allow=frozenset(shell.get("allow", [])),
                shell_deny=frozenset(shell.get("deny", [])),
                env_read=frozenset(env.get("read", [])),
                env_write=frozenset(env.get("write", [])),
            )

        # Handle PermissionScope directly
        if isinstance(permissions, PermissionScope):
            return permissions

        return PermissionScope()

    def _check_risks_deterministic(
        self, skill: Skill, scope: PermissionScope
    ) -> list[str]:
        """Deterministic security checks (no LLM needed).

        Args:
            skill: The skill being checked
            scope: The skill's permission scope

        Returns:
            List of risk flag strings
        """
        flags: list[str] = []

        # Credential path access
        for path in scope.filesystem_read:
            if any(fnmatch(path, pattern) for pattern in self.SENSITIVE_PATHS):
                flags.append(f"CREDENTIAL_ACCESS: {skill.name} reads {path}")

        # Dangerous commands (prefix match)
        for cmd in scope.shell_allow:
            cmd_lower = cmd.lower().strip()
            for danger in self.DANGEROUS_COMMANDS:
                # Handle patterns with wildcard
                danger_prefix = danger.replace(" *", "").lower()
                if cmd_lower.startswith(danger_prefix):
                    flags.append(f"DANGEROUS_COMMAND: {skill.name} allows '{cmd}'")
                    break

        # External network access
        for host in scope.network_allow:
            if not self._is_internal(host):
                flags.append(f"EXTERNAL_NETWORK: {skill.name} connects to {host}")

        return flags

    def _is_internal(self, host: str) -> bool:
        """Check if host is internal (not external network).

        Args:
            host: Host pattern to check (may include port)

        Returns:
            True if host is internal
        """
        # Extract hostname (strip port if present)
        hostname = host.rsplit(":", 1)[0] if ":" in host else host

        internal_patterns = [
            "localhost",
            "127.0.0.1",
            "::1",
            "*.internal",
            "*.local",
            "*.internal.*",
            "10.*",
            "172.16.*",
            "192.168.*",
        ]
        return any(fnmatch(hostname, p) for p in internal_patterns)

    def _compute_risk(
        self,
        scope: PermissionScope,
        flags: list[str],
    ) -> RiskAssessment:
        """Compute overall risk level using configurable weights.

        Args:
            scope: The permission scope to assess
            flags: Risk flags from deterministic checks

        Returns:
            RiskAssessment with level, score, flags, and recommendations
        """
        score = 0.0
        w = self.weights

        # Base risk from permission breadth
        score += len(scope.filesystem_write) * w.filesystem_write
        score += len(scope.shell_allow) * w.shell_allow
        score += len(scope.network_allow) * w.network_allow

        # High-risk flags
        credential_flags = [f for f in flags if "CREDENTIAL" in f]
        dangerous_flags = [f for f in flags if "DANGEROUS" in f]
        external_flags = [f for f in flags if "EXTERNAL" in f]

        score += len(credential_flags) * w.credential_flag
        score += len(dangerous_flags) * w.dangerous_flag
        score += len(external_flags) * w.external_flag

        # Clamp to 0-1
        score = min(1.0, score)

        # Level determination (credential/dangerous flags auto-escalate)
        if score >= 0.8 or credential_flags or dangerous_flags:
            level: Literal["low", "medium", "high", "critical"] = "critical"
        elif score >= 0.5 or external_flags:
            level = "high"
        elif score >= 0.2:
            level = "medium"
        else:
            level = "low"

        recommendations = self._generate_recommendations(flags)

        return RiskAssessment(
            level=level,
            score=score,
            flags=tuple(flags),
            recommendations=recommendations,
        )

    def _risk_contribution_level(
        self,
        scope: PermissionScope,
        risk: RiskAssessment,
        flags: list[str],
    ) -> RiskContributionLevel:
        """Classify per-skill risk contribution for UI display."""
        if scope.is_empty():
            return "none"

        if any("CREDENTIAL_ACCESS" in f for f in flags) or any(
            "DANGEROUS_COMMAND" in f for f in flags
        ):
            return "high"

        if risk.score >= 0.8:
            return "high"
        if risk.score >= 0.5:
            return "medium"
        if risk.score >= 0.1:
            return "low"
        return "low"

    def _primary_risk_reason(self, scope: PermissionScope, flags: list[str]) -> str | None:
        """Choose a concise reason for per-skill risk display."""
        if any("CREDENTIAL_ACCESS" in f for f in flags):
            return "credential access"
        if any("DANGEROUS_COMMAND" in f for f in flags):
            return "dangerous command"
        if any("EXTERNAL_NETWORK" in f for f in flags):
            return "external network"
        if scope.shell_allow:
            return "shell access"
        if scope.network_allow:
            return "network access"
        if scope.filesystem_write:
            return "filesystem write"
        if scope.filesystem_read:
            return "filesystem read"
        if scope.env_read or scope.env_write:
            return "environment access"
        return None

    def _generate_recommendations(self, flags: list[str]) -> tuple[str, ...]:
        """Generate recommendations based on detected flags.

        Args:
            flags: List of risk flags

        Returns:
            Tuple of recommendation strings
        """
        recommendations: list[str] = []

        for flag in flags:
            if "CREDENTIAL_ACCESS" in flag:
                if ".aws" in flag:
                    recommendations.append("Use IAM role instead of credentials file")
                elif ".ssh" in flag:
                    recommendations.append("Use SSH agent instead of reading key files")
                else:
                    recommendations.append(
                        "Avoid reading credential files directly"
                    )

            elif "DANGEROUS_COMMAND" in flag:
                if "rm -rf" in flag:
                    recommendations.append("Use targeted delete instead of rm -rf")
                elif "ssh " in flag or "scp " in flag:
                    recommendations.append("Consider read-only access or staging environment")
                else:
                    recommendations.append("Review command for safer alternatives")

            elif "EXTERNAL_NETWORK" in flag:
                recommendations.append(
                    "Restrict to internal hosts or use explicit allowlist"
                )

        return tuple(recommendations)
