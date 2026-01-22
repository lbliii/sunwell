# RFC-089: Security-First Skill Execution

**Status:** Implemented  
**Author:** AI Assistant  
**Created:** 2026-01-22  
**Updated:** 2026-01-22  
**Related:** RFC-087 (Skill-Lens DAG), RFC-048 (Autonomy Guardrails)

## Integration with Existing Infrastructure

This RFC **extends** existing Sunwell security infrastructure rather than replacing it:

| Existing Component | Location | How RFC-089 Extends It |
|--------------------|----------|------------------------|
| `ActionRisk` enum | `guardrails/types.py:17-59` | Maps to `RiskAssessment.level` |
| `ScriptSandbox` | `skills/sandbox.py:33-59` | Adds permission-aware configuration |
| `TrustLevel` | `skills/types.py:67-76` | Complements with fine-grained permissions |
| `ScopeTracker` | `guardrails/scope.py` | Integrates scope limits with permission checks |
| `SkillGraph` | `skills/graph.py` | Adds permission aggregation across DAG |

**Key principle**: Security checks compose — RFC-048's action classification runs first, then RFC-089's permission enforcement.

---

## Executive Summary

AI coding assistants with ambient authority (shell, network, filesystem) represent **infrastructural risk** — not just to local machines, but as lateral movement vectors to other hosts. Current solutions either:

1. **Trust blindly** — Agent has full access, hope it doesn't misuse it
2. **Block everything** — Sandbox so restrictive the agent can't do real work
3. **Prompt for each action** — Death by a thousand confirmations

Sunwell's DAG architecture enables a fourth option: **Declarative Permission Graphs**. Each skill declares its exact permissions. Before execution, users see the complete permission scope. Runtime sandboxes enforce boundaries. Monitors detect violations. Provenance tracks everything.

**This is enterprise-grade AI security without sacrificing capability.**

---

## The Problem

### Ambient Authority Is Dangerous

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT AI AGENTS                            │
│                                                                  │
│  User: "Deploy my app"                                          │
│           ↓                                                      │
│  Agent: [Has ambient authority]                                  │
│         - Shell access ✓                                         │
│         - Network access ✓                                       │
│         - Filesystem access ✓                                    │
│         - Can install packages ✓                                 │
│         - Can SSH to other hosts ✓                               │
│           ↓                                                      │
│  Agent executes... something. User hopes it's correct.           │
│                                                                  │
│  RISKS:                                                          │
│  - Credential exfiltration (reads ~/.ssh/*, ~/.aws/*)           │
│  - Lateral movement (SSH to production)                          │
│  - Supply chain attack (installs malicious package)              │
│  - Data exfiltration (uploads codebase to unknown host)          │
│  - Cryptominer installation (background process)                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Real-World Attack Vectors

| Vector | How It Happens | Impact |
|--------|----------------|--------|
| **Credential theft** | Agent reads `~/.aws/credentials` "to help with deployment" | AWS account compromise |
| **Lateral movement** | Agent SSHs to production "to check logs" | Production breach |
| **Supply chain** | Agent installs `python-dateutils` (typosquat) | Malware execution |
| **Data exfil** | Agent "backs up" code to attacker-controlled S3 | IP theft |
| **Persistence** | Agent adds cron job "for monitoring" | Persistent access |

### Why Current Solutions Fail

| Approach | Problem |
|----------|---------|
| **Full trust** | One mistake = full compromise |
| **Full sandbox** | Agent can't actually help with real tasks |
| **Per-action prompts** | User fatigue → blind approval |
| **Capability lists** | Static, can't adapt to task requirements |

---

## Solution: Declarative Permission Graphs

### Core Insight

Sunwell's DAG architecture (RFC-087) already requires skills to declare:
- `depends_on` — what skills must run first
- `produces` — what outputs it creates
- `requires` — what inputs it needs

**Extend this to permissions:**

```yaml
- name: deploy_kubernetes
  depends_on: [build_image, run_tests]
  produces: ["deployment_status"]
  requires: ["docker_image", "test_results"]
  
  # NEW: Explicit permission declaration
  permissions:
    filesystem:
      read: ["/app/k8s/*.yaml", "/app/.env"]
      write: ["/tmp/deploy-*"]
    network:
      allow: ["*.internal.cluster.local:443"]
      deny: ["*"]  # Default deny
    shell:
      allow: ["kubectl apply -f *", "kubectl rollout status *"]
      deny: ["kubectl delete *", "kubectl exec *"]
    environment:
      read: ["KUBECONFIG", "DEPLOY_ENV"]
      write: []
```

### The Permission Graph

Before execution, Sunwell computes the **total permission scope** of the entire DAG:

```
┌─────────────────────────────────────────────────────────────────┐
│                   PERMISSION GRAPH ANALYSIS                      │
│                                                                  │
│  Pipeline: deploy_app                                            │
│  Skills: 4 (build_image → run_tests → deploy_kubernetes → notify)│
│                                                                  │
│  TOTAL PERMISSIONS REQUESTED:                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Filesystem                                                   │ │
│  │   Read:  /app/src/*, /app/k8s/*.yaml, /app/.env            │ │
│  │   Write: /tmp/build-*, /tmp/deploy-*                        │ │
│  ├─────────────────────────────────────────────────────────────┤ │
│  │ Network                                                      │ │
│  │   Allow: registry.internal:5000, *.internal.cluster.local   │ │
│  │   Deny:  * (default)                                        │ │
│  ├─────────────────────────────────────────────────────────────┤ │
│  │ Shell                                                        │ │
│  │   Allow: docker build, docker push, kubectl apply/rollout   │ │
│  │   Deny:  kubectl delete/exec, docker run (blocked)          │ │
│  ├─────────────────────────────────────────────────────────────┤ │
│  │ Environment                                                  │ │
│  │   Read:  KUBECONFIG, DEPLOY_ENV, REGISTRY_URL               │ │
│  │   Write: (none)                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  RISK ASSESSMENT: LOW                                            │
│  - No access to credentials directories                          │
│  - No external network access                                    │
│  - No destructive kubectl commands                               │
│  - No shell escape vectors                                       │
│                                                                  │
│  [Approve] [Reject] [Modify Permissions]                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY-FIRST EXECUTION                      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Permission  │    │   Runtime    │    │   Security   │
│   Analyzer   │    │   Sandbox    │    │   Monitor    │
├──────────────┤    ├──────────────┤    ├──────────────┤
│ Static DAG   │    │ Enforce at   │    │ Detect       │
│ analysis     │    │ execution    │    │ violations   │
│              │    │              │    │              │
│ Compute total│    │ seccomp/bpf  │    │ Real-time    │
│ permissions  │    │ namespaces   │    │ classification│
│              │    │ network policy│   │              │
│ Risk scoring │    │ fs isolation │    │ Provenance   │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌──────────────┐
                    │  Audit Log   │
                    │  (Immutable) │
                    └──────────────┘
```

### 1. Permission Analyzer

```python
# src/sunwell/security/analyzer.py

import re
from fnmatch import fnmatch

from sunwell.guardrails.types import ActionRisk  # RFC-048 integration


@dataclass(frozen=True, slots=True)
class PermissionScope:
    """Total permissions for a skill or DAG."""
    
    filesystem_read: frozenset[str] = frozenset()
    filesystem_write: frozenset[str] = frozenset()
    network_allow: frozenset[str] = frozenset()
    network_deny: frozenset[str] = frozenset(["*"])  # Default deny
    shell_allow: frozenset[str] = frozenset()
    shell_deny: frozenset[str] = frozenset()
    env_read: frozenset[str] = frozenset()
    env_write: frozenset[str] = frozenset()


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
    score: float  # 0.0 - 1.0
    flags: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    
    def to_action_risk(self) -> ActionRisk:
        """Convert to RFC-048 ActionRisk for guardrails integration."""
        return {
            "low": ActionRisk.SAFE,
            "medium": ActionRisk.MODERATE,
            "high": ActionRisk.DANGEROUS,
            "critical": ActionRisk.FORBIDDEN,
        }[self.level]


@dataclass(frozen=True, slots=True)
class RiskWeights:
    """Configurable risk scoring weights.
    
    Rationale for defaults:
    - filesystem_write (0.05): Low per-path risk, but accumulates
    - shell_allow (0.10): Commands can chain, 2× file risk
    - network_allow (0.10): Exfiltration vector, matches shell
    - credential_flag (0.30): Direct compromise vector
    - dangerous_flag (0.40): Highest single-action risk
    - external_flag (0.20): Data leakage risk
    
    These weights are derived from MITRE ATT&CK technique severity
    and can be overridden per-deployment via security policy.
    """
    
    filesystem_write: float = 0.05
    shell_allow: float = 0.10
    network_allow: float = 0.10
    credential_flag: float = 0.30
    dangerous_flag: float = 0.40
    external_flag: float = 0.20


class PermissionAnalyzer:
    """Analyzes DAGs for security permissions.
    
    Uses a two-phase detection strategy:
    1. Deterministic pattern matching (fast, reliable)
    2. Optional LLM classification (for novel patterns)
    """
    
    # Deterministic credential patterns (regex)
    # These catch common secrets without LLM overhead
    CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
        ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("AWS_SECRET", re.compile(r"[A-Za-z0-9/+=]{40}")),
        ("GITHUB_TOKEN", re.compile(r"ghp_[A-Za-z0-9]{36}")),
        ("SLACK_TOKEN", re.compile(r"xox[baprs]-[0-9A-Za-z-]+")),
        ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")),
        ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*")),
        ("GENERIC_SECRET", re.compile(r"(?i)(password|secret|token|api_key)\s*[=:]\s*['\"][^'\"]{8,}")),
    )
    
    # High-risk path patterns (glob syntax)
    SENSITIVE_PATHS: frozenset[str] = frozenset([
        "~/.ssh/*", "~/.aws/*", "~/.config/gcloud/*",
        "~/.kube/config", "/etc/passwd", "/etc/shadow",
        "**/credentials*", "**/*.pem", "**/*.key",
        "**/.env", "**/.env.*", "**/secrets.*",
    ])
    
    # Dangerous shell command patterns (prefix match)
    # Pattern syntax: prefix match with * as glob
    DANGEROUS_COMMANDS: frozenset[str] = frozenset([
        "rm -rf",        # Recursive delete
        "dd if=",        # Raw disk write
        "mkfs",          # Filesystem format
        ":(){ :|:& };:", # Fork bomb
        "curl * | sh",   # Remote code exec
        "curl * | bash",
        "wget * | sh",
        "wget * | bash",
        "eval ",         # Arbitrary eval
        "ssh ",          # Remote access
        "scp ",          # Remote copy
        "rsync ",        # Remote sync
        "> /dev/sd",     # Direct disk write
        "chmod 777",     # Overly permissive
        "chown root",    # Privilege escalation
    ])
    
    def __init__(self, weights: RiskWeights | None = None):
        self.weights = weights or RiskWeights()
    
    def analyze_dag(self, dag: SkillGraph) -> tuple[PermissionScope, RiskAssessment]:
        """Compute total permissions and risk for entire DAG."""
        
        total_scope = PermissionScope()
        flags: list[str] = []
        
        for skill in dag.skills.values():
            skill_scope = self._extract_permissions(skill)
            total_scope = self._merge_scopes(total_scope, skill_scope)
            
            # Deterministic risk checks (Phase 1)
            flags.extend(self._check_risks_deterministic(skill, skill_scope))
        
        risk = self._compute_risk(total_scope, flags)
        
        return total_scope, risk
    
    def scan_for_credentials(self, content: str) -> list[tuple[str, str]]:
        """Deterministic credential scanning.
        
        Returns list of (pattern_name, matched_value) tuples.
        This runs BEFORE any LLM classification for reliability.
        """
        findings = []
        for name, pattern in self.CREDENTIAL_PATTERNS:
            for match in pattern.finditer(content):
                # Redact the actual value for safety
                redacted = match.group()[:8] + "..." if len(match.group()) > 8 else "***"
                findings.append((name, redacted))
        return findings
    
    def _check_risks_deterministic(self, skill: Skill, scope: PermissionScope) -> list[str]:
        """Deterministic security checks (no LLM needed)."""
        flags = []
        
        # Credential path access
        for path in scope.filesystem_read:
            if any(fnmatch(path, pattern) for pattern in self.SENSITIVE_PATHS):
                flags.append(f"CREDENTIAL_ACCESS: {skill.name} reads {path}")
        
        # Dangerous commands (prefix match)
        for cmd in scope.shell_allow:
            cmd_lower = cmd.lower().strip()
            for danger in self.DANGEROUS_COMMANDS:
                if cmd_lower.startswith(danger.replace(" *", "").lower()):
                    flags.append(f"DANGEROUS_COMMAND: {skill.name} allows '{cmd}'")
                    break
        
        # External network access
        for host in scope.network_allow:
            if not self._is_internal(host):
                flags.append(f"EXTERNAL_NETWORK: {skill.name} connects to {host}")
        
        return flags
    
    def _is_internal(self, host: str) -> bool:
        """Check if host is internal (not external network)."""
        internal_patterns = [
            "localhost", "127.0.0.1", "::1",
            "*.internal", "*.local", "*.internal.*",
            "10.*", "172.16.*", "192.168.*",
        ]
        return any(fnmatch(host, p) for p in internal_patterns)
    
    def _compute_risk(
        self, 
        scope: PermissionScope, 
        flags: list[str]
    ) -> RiskAssessment:
        """Compute overall risk level using configurable weights."""
        
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
        
        # Clamp and categorize
        score = min(1.0, score)
        
        # Level determination (credential/dangerous flags auto-escalate)
        if score >= 0.8 or credential_flags or dangerous_flags:
            level = "critical"
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
```

### 2. Runtime Sandbox

**Extends existing `skills/sandbox.py:33-59` with permission-aware configuration.**

#### Platform Support Matrix

| Platform | Isolation Method | Filesystem | Network | Notes |
|----------|------------------|------------|---------|-------|
| **Linux** | seccomp + namespaces | bind mounts | netns | Full support |
| **macOS** | sandbox-exec | symlinks | PF rules | Partial (no netns) |
| **Windows** | Job Objects | Junction points | WFP | Partial (no seccomp) |
| **Container** | Docker/Podman | volumes | network policy | Recommended for CI |

**Fallback strategy**: If platform-specific isolation unavailable, use process-level restrictions + aggressive auditing.

```python
# src/sunwell/security/sandbox.py
# EXTENDS: skills/sandbox.py:ScriptSandbox

import platform
from sunwell.skills.sandbox import ScriptSandbox, TrustLevel


@dataclass
class PermissionAwareSandboxConfig:
    """Configuration for permission-aware skill execution.
    
    Extends ScriptSandbox with declarative permissions from RFC-089.
    """
    
    permissions: PermissionScope
    
    # Inherit base sandbox settings
    base_trust: TrustLevel = TrustLevel.SANDBOXED
    
    # Platform-specific isolation (auto-detected if None)
    isolation_backend: Literal["seccomp", "sandbox-exec", "container", "process"] | None = None
    
    # Resource limits (inherited from ScriptSandbox, can override)
    max_memory_mb: int = 512
    max_cpu_seconds: int = 60
    max_file_size_mb: int = 100
    max_processes: int = 10
    
    # Network policy
    allowed_hosts: frozenset[str] = frozenset()
    
    def __post_init__(self):
        if self.isolation_backend is None:
            self.isolation_backend = self._detect_backend()
    
    def _detect_backend(self) -> str:
        """Auto-detect best isolation backend for current platform."""
        system = platform.system()
        if system == "Linux":
            # Check if seccomp available
            try:
                import prctl
                return "seccomp"
            except ImportError:
                return "process"
        elif system == "Darwin":
            return "sandbox-exec"
        elif system == "Windows":
            return "process"  # Job Objects via subprocess
        return "process"


class SecureSandbox:
    """Execute skills in isolated sandbox with enforced permissions.
    
    Composes with existing ScriptSandbox rather than replacing it.
    The base ScriptSandbox handles script execution; this class adds
    permission enforcement and security auditing.
    """
    
    def __init__(self, config: PermissionAwareSandboxConfig):
        self.config = config
        self._base_sandbox = ScriptSandbox(
            trust=config.base_trust,
            read_paths=tuple(Path(p) for p in config.permissions.filesystem_read),
            write_paths=tuple(Path(p) for p in config.permissions.filesystem_write),
            allow_network=bool(config.allowed_hosts),
            timeout_seconds=config.max_cpu_seconds,
        )
        self._setup_isolation()
    
    def _setup_isolation(self):
        """Configure platform-specific isolation."""
        backend = self.config.isolation_backend
        
        if backend == "seccomp":
            self._setup_seccomp_filter()
        elif backend == "sandbox-exec":
            self._setup_macos_sandbox()
        elif backend == "container":
            self._setup_container_policy()
        # "process" backend uses base ScriptSandbox restrictions only
    
    async def execute(
        self, 
        skill: Skill, 
        context: ExecutionContext
    ) -> tuple[SkillOutput, SecurityAudit]:
        """Execute skill in sandbox, return output and audit log."""
        
        audit = SecurityAudit(skill_name=skill.name)
        
        # Pre-execution validation
        if not self._validate_permissions(skill, context):
            raise PermissionDeniedError(
                f"Skill {skill.name} requested permissions not in scope"
            )
        
        # Execute using base sandbox with our config
        try:
            # For script-based skills, delegate to base sandbox
            if skill.scripts:
                for script in skill.scripts:
                    result = await self._base_sandbox.execute(script)
                    if result.exit_code != 0:
                        audit.record_error(Exception(result.stderr))
                        raise SkillExecutionError(skill.name, "execute", result.stderr)
            
            # For instruction-based skills, execute with monitoring
            output = await self._execute_with_monitoring(skill, context)
            audit.record_success(output)
            
        except PermissionError as e:
            audit.record_violation(e)
            raise
        
        except Exception as e:
            audit.record_error(e)
            raise
        
        return output, audit
    
    def _setup_seccomp_filter(self):
        """Configure seccomp to block dangerous syscalls (Linux only)."""
        
        blocked_syscalls = [
            "ptrace",      # No debugging other processes
            "mount",       # No mounting filesystems
            "umount",      # No unmounting
            "pivot_root",  # No changing root
            "reboot",      # No rebooting
            "init_module", # No loading kernel modules
            "delete_module",
            "kexec_load",  # No loading new kernels
        ]
        
        # Allow but audit
        audited_syscalls = [
            "execve",      # Log all process execution
            "connect",     # Log all network connections
            "open",        # Log file access
            "openat",
        ]
        
        self.seccomp_filter = SeccompFilter(
            default_action="allow",
            blocked=blocked_syscalls,
            audited=audited_syscalls,
        )
    
    def _setup_macos_sandbox(self):
        """Configure sandbox-exec profile (macOS only)."""
        # Generate sandbox-exec profile from permissions
        profile = self._generate_sandbox_profile()
        self._sandbox_profile_path = Path(tempfile.mktemp(suffix=".sb"))
        self._sandbox_profile_path.write_text(profile)
    
    def _generate_sandbox_profile(self) -> str:
        """Generate macOS sandbox-exec profile from PermissionScope."""
        lines = ["(version 1)", "(deny default)"]
        
        # Allow read paths
        for path in self.config.permissions.filesystem_read:
            expanded = os.path.expanduser(path)
            lines.append(f'(allow file-read* (subpath "{expanded}"))')
        
        # Allow write paths
        for path in self.config.permissions.filesystem_write:
            expanded = os.path.expanduser(path)
            lines.append(f'(allow file-write* (subpath "{expanded}"))')
        
        # Network rules
        if self.config.allowed_hosts:
            lines.append("(allow network-outbound")
            for host in self.config.allowed_hosts:
                # Parse host:port
                if ":" in host:
                    h, p = host.rsplit(":", 1)
                    lines.append(f'  (remote tcp "{h}" (port {p}))')
            lines.append(")")
        
        return "\n".join(lines)
```

### Pattern Syntax Reference

Permission declarations use consistent pattern syntax across all permission types:

#### Filesystem Patterns (Glob)

```yaml
filesystem:
  read:
    - "/app/src/*"           # All files in src/
    - "/app/src/**"          # All files recursively
    - "/app/config/*.yaml"   # Only YAML files
    - "~/.config/myapp/*"    # User home expansion
  write:
    - "/tmp/myapp-*"         # Prefix match in temp
```

| Pattern | Meaning | Example Match |
|---------|---------|---------------|
| `*` | Any characters in filename | `/app/*.py` → `/app/main.py` |
| `**` | Recursive directory match | `/app/**` → `/app/a/b/c.py` |
| `~` | User home directory | `~/.ssh` → `/home/user/.ssh` |
| `?` | Single character | `/tmp/?.log` → `/tmp/a.log` |

#### Shell Command Patterns (Prefix Match)

Shell patterns use **prefix matching** for security (commands must START with allowed pattern):

```yaml
shell:
  allow:
    - "kubectl apply -f"     # Allows: kubectl apply -f foo.yaml
                             # Blocks: kubectl apply -f /etc/passwd (path check separate)
    - "docker build"         # Allows: docker build -t myimage .
    - "npm run"              # Allows: npm run test, npm run build
  deny:
    - "kubectl delete"       # Blocks ALL delete commands
    - "rm -rf"               # Blocks recursive delete
```

**Why prefix match?** Glob patterns like `kubectl *` would allow `kubectl delete --all` which is dangerous. Prefix matching ensures only intended command forms are allowed.

**Argument validation**: For commands with path arguments, the paths are validated against `filesystem` permissions separately.

#### Network Patterns (Host:Port)

```yaml
network:
  allow:
    - "registry.internal:5000"      # Exact host:port
    - "*.internal.cluster.local:*"  # Wildcard subdomain, any port
    - "10.0.0.0/8:443"              # CIDR range, specific port
  deny:
    - "*"                           # Default deny all external
```

| Pattern | Meaning |
|---------|---------|
| `host:port` | Exact match |
| `*.domain:port` | Any subdomain |
| `host:*` | Any port on host |
| `CIDR:port` | IP range match |

#### Environment Patterns (Exact or Prefix)

```yaml
environment:
  read:
    - "KUBECONFIG"          # Exact variable
    - "AWS_*"               # All AWS_ prefixed vars
  write: []                 # Never allow env mutation
```

---

### 3. Security Monitor

```python
# src/sunwell/security/monitor.py

import re
from dataclasses import dataclass
from typing import AsyncIterator, Callable

from sunwell.security.analyzer import PermissionAnalyzer


SECURITY_CLASSIFICATIONS = [
    "safe",
    "credential_leak",
    "path_traversal", 
    "shell_injection",
    "network_exfil",
    "pii_exposure",
    "permission_escalation",
]


@dataclass(frozen=True, slots=True)
class SecurityClassification:
    """Result of security classification."""
    
    classification: str
    violation: bool
    violation_type: str | None = None
    evidence: str | None = None
    confidence: float = 1.0
    detection_method: str = "deterministic"  # or "llm"


class SecurityMonitor:
    """Real-time monitoring of skill execution for security violations.
    
    Uses a two-phase detection strategy:
    1. Deterministic pattern matching (fast, reliable, no false negatives)
    2. LLM classification (catches novel patterns, may have false positives)
    
    Deterministic checks ALWAYS run. LLM is optional and runs only if
    deterministic checks pass but paranoid_mode is enabled.
    """
    
    # Deterministic patterns for common violations
    PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.\/|\.\.\\|%2e%2e|%252e")
    SHELL_INJECTION_PATTERNS = [
        re.compile(r"`[^`]+`"),           # Backtick execution
        re.compile(r"\$\([^)]+\)"),        # $() subshell
        re.compile(r";\s*\w+"),            # Command chaining
        re.compile(r"\|\s*\w+"),           # Pipe to command
        re.compile(r"&&\s*\w+"),           # AND chaining
        re.compile(r"\|\|\s*\w+"),         # OR chaining
    ]
    PII_PATTERNS = [
        ("EMAIL", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
        ("PHONE", re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")),
        ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        ("CREDIT_CARD", re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")),
    ]
    
    def __init__(
        self, 
        classifier_model: ModelProtocol | None = None,
        paranoid_mode: bool = False,
    ):
        """Initialize security monitor.
        
        Args:
            classifier_model: Optional LLM for Phase 2 classification
            paranoid_mode: If True, run LLM classification even when
                          deterministic checks pass (slower, more thorough)
        """
        self.classifier = classifier_model
        self.paranoid_mode = paranoid_mode
        self._analyzer = PermissionAnalyzer()
    
    def classify_output_deterministic(
        self, 
        output: str, 
        declared_permissions: PermissionScope
    ) -> SecurityClassification:
        """Phase 1: Deterministic security classification.
        
        Fast, reliable, no false negatives for known patterns.
        Returns immediately if violation found.
        """
        # 1. Credential leak (uses PermissionAnalyzer patterns)
        credential_findings = self._analyzer.scan_for_credentials(output)
        if credential_findings:
            return SecurityClassification(
                classification="credential_leak",
                violation=True,
                violation_type="credential_leak",
                evidence=f"Found: {credential_findings[0][0]}",
                detection_method="deterministic",
            )
        
        # 2. Path traversal
        if self.PATH_TRAVERSAL_PATTERN.search(output):
            return SecurityClassification(
                classification="path_traversal",
                violation=True,
                violation_type="path_traversal",
                evidence="Path traversal sequence detected",
                detection_method="deterministic",
            )
        
        # 3. Shell injection
        for pattern in self.SHELL_INJECTION_PATTERNS:
            match = pattern.search(output)
            if match:
                return SecurityClassification(
                    classification="shell_injection",
                    violation=True,
                    violation_type="shell_injection",
                    evidence=f"Shell metacharacter: {match.group()[:20]}",
                    detection_method="deterministic",
                )
        
        # 4. PII exposure (check against permissions)
        for pii_name, pattern in self.PII_PATTERNS:
            if pattern.search(output):
                # Only flag if PII handling not explicitly permitted
                if "pii" not in str(declared_permissions.env_read).lower():
                    return SecurityClassification(
                        classification="pii_exposure",
                        violation=True,
                        violation_type="pii_exposure",
                        evidence=f"Potential {pii_name} detected",
                        detection_method="deterministic",
                    )
        
        # No deterministic violations found
        return SecurityClassification(
            classification="safe",
            violation=False,
            detection_method="deterministic",
        )
    
    async def classify_output(
        self, 
        output: str, 
        declared_permissions: PermissionScope
    ) -> SecurityClassification:
        """Full security classification (Phase 1 + optional Phase 2).
        
        Runs deterministic checks first. If clean and paranoid_mode
        is enabled (and classifier available), runs LLM classification.
        """
        # Phase 1: Deterministic (always runs)
        result = self.classify_output_deterministic(output, declared_permissions)
        if result.violation:
            return result
        
        # Phase 2: LLM classification (optional)
        if self.paranoid_mode and self.classifier:
            llm_result = await self._classify_with_llm(output, declared_permissions)
            if llm_result.violation:
                # Mark as LLM-detected (lower confidence)
                return SecurityClassification(
                    classification=llm_result.classification,
                    violation=True,
                    violation_type=llm_result.violation_type,
                    evidence=llm_result.evidence,
                    confidence=0.7,  # LLM classifications have lower confidence
                    detection_method="llm",
                )
        
        return result
    
    async def _classify_with_llm(
        self, 
        output: str, 
        declared_permissions: PermissionScope
    ) -> SecurityClassification:
        """Phase 2: LLM-based classification for novel patterns."""
        
        prompt = f"""Analyze this AI agent output for security issues.

Declared permissions:
- Filesystem read: {declared_permissions.filesystem_read}
- Filesystem write: {declared_permissions.filesystem_write}
- Network: {declared_permissions.network_allow}
- Shell: {declared_permissions.shell_allow}

Output to analyze:
---
{output[:2000]}
---

Check for:
1. credential_leak: Contains API keys, passwords, tokens, private keys
2. path_traversal: Accesses files outside declared scope (../, /etc/, ~/)
3. shell_injection: Embedded commands, backticks, $() constructs
4. network_exfil: Contacts hosts not in declared network permissions
5. pii_exposure: Contains emails, phone numbers, SSNs, addresses
6. permission_escalation: Attempts to gain more access than declared

Respond with JSON: {{"classification": "safe|<type>", "evidence": "brief explanation"}}
"""
        
        response = await self.classifier.generate(
            prompt=(Message(role="user", content=prompt),)
        )
        
        return self._parse_classification(response.content)
    
    async def monitor_stream(
        self,
        stream: AsyncIterator[str],
        permissions: PermissionScope,
        on_violation: Callable[[SecurityViolation], None],
    ) -> AsyncIterator[str]:
        """Monitor streaming output for security violations.
        
        Runs deterministic checks synchronously on each chunk.
        LLM classification (if enabled) runs periodically.
        """
        buffer: list[str] = []
        
        async for chunk in stream:
            buffer.append(chunk)
            yield chunk
            
            # Deterministic check on every chunk (fast)
            text = "".join(buffer)
            result = self.classify_output_deterministic(text, permissions)
            
            if result.violation:
                on_violation(SecurityViolation(
                    type=result.violation_type,
                    content=text[-200:],  # Last 200 chars for context
                    position=len(text),
                    detection_method=result.detection_method,
                ))
            
            # LLM check periodically (slow, optional)
            if self.paranoid_mode and self.classifier and len(text) > 500:
                llm_result = await self._classify_with_llm(text, permissions)
                if llm_result.violation:
                    on_violation(SecurityViolation(
                        type=llm_result.violation_type,
                        content=text[-200:],
                        position=len(text),
                        detection_method="llm",
                    ))
                buffer = buffer[-5:]  # Keep some context
```

### 4. Audit Log

#### Immutability Requirements

**Problem**: File-based append-only logs can still be truncated, deleted, or modified via direct disk access.

**Solution**: Use defense-in-depth with multiple storage backends:

| Backend | Immutability Level | Use Case |
|---------|-------------------|----------|
| **Local file** | Low (append-only mode) | Development, debugging |
| **Local + checksum chain** | Medium (tamper-evident) | Single-user production |
| **Database + triggers** | Medium-High (audit triggers) | Team production |
| **S3 Object Lock** | High (WORM compliance) | Enterprise/regulated |
| **Blockchain/ledger** | Very High (cryptographic) | Maximum assurance |

**Recommended**: Local file + checksum chain for most deployments, with S3 Object Lock for compliance-sensitive environments.

```python
# src/sunwell/security/audit.py

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal, Protocol


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable audit log entry."""
    
    timestamp: datetime
    skill_name: str
    dag_id: str
    user_id: str
    
    # What was requested
    requested_permissions: PermissionScope
    
    # What happened
    action: Literal["execute", "violation", "denied", "error"]
    details: str
    
    # Provenance
    inputs_hash: str
    outputs_hash: str | None
    
    # Integrity chain (each entry references previous)
    previous_hash: str
    entry_hash: str
    
    # Signature for integrity (HMAC-SHA256)
    signature: str


class AuditBackend(Protocol):
    """Protocol for audit storage backends."""
    
    def append(self, entry: AuditEntry) -> None:
        """Append entry (must be atomic)."""
        ...
    
    def query(self, **filters) -> Iterator[AuditEntry]:
        """Query entries with filters."""
        ...
    
    def verify_integrity(self) -> tuple[bool, str]:
        """Verify chain integrity. Returns (valid, reason)."""
        ...


class LocalAuditLog:
    """Local file audit log with checksum chain.
    
    Provides tamper-evidence (not tamper-proof):
    - Each entry includes hash of previous entry
    - HMAC signature prevents modification without key
    - Integrity verification detects tampering
    
    For true immutability, use S3ObjectLockBackend.
    """
    
    def __init__(self, storage_path: Path, signing_key: bytes):
        self.storage = storage_path
        self.key = signing_key
        self._last_hash = self._get_last_hash()
    
    def append(self, entry_data: dict) -> AuditEntry:
        """Append entry to log with integrity chain."""
        
        # Compute entry hash (includes previous hash)
        entry_hash = self._compute_hash({**entry_data, "previous_hash": self._last_hash})
        
        # Sign the entry
        signature = hmac.new(
            self.key, 
            entry_hash.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        entry = AuditEntry(
            **entry_data,
            previous_hash=self._last_hash,
            entry_hash=entry_hash,
            signature=signature,
        )
        
        # Atomic append (write to temp, rename)
        temp_path = self.storage.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
        
        # Append to main log
        with open(self.storage, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
        
        temp_path.unlink()
        self._last_hash = entry_hash
        
        return entry
    
    def verify_integrity(self) -> tuple[bool, str]:
        """Verify the entire chain is intact."""
        
        previous_hash = ""
        line_num = 0
        
        with open(self.storage) as f:
            for line in f:
                line_num += 1
                entry = AuditEntry(**json.loads(line))
                
                # Check chain linkage
                if entry.previous_hash != previous_hash:
                    return False, f"Chain broken at line {line_num}"
                
                # Verify signature
                expected_sig = hmac.new(
                    self.key,
                    entry.entry_hash.encode(),
                    hashlib.sha256
                ).hexdigest()
                
                if entry.signature != expected_sig:
                    return False, f"Invalid signature at line {line_num}"
                
                previous_hash = entry.entry_hash
        
        return True, f"Verified {line_num} entries"
    
    def _compute_hash(self, data: dict) -> str:
        """Compute SHA-256 hash of entry data."""
        # Deterministic serialization
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _get_last_hash(self) -> str:
        """Get hash of last entry (or empty for new log)."""
        if not self.storage.exists():
            return ""
        
        last_line = ""
        with open(self.storage) as f:
            for line in f:
                last_line = line
        
        if not last_line:
            return ""
        
        entry = json.loads(last_line)
        return entry.get("entry_hash", "")
    
    def query(
        self,
        skill_name: str | None = None,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
    ) -> Iterator[AuditEntry]:
        """Query audit log with filters."""
        
        with open(self.storage) as f:
            for line in f:
                entry = AuditEntry(**json.loads(line))
                
                if skill_name and entry.skill_name != skill_name:
                    continue
                if user_id and entry.user_id != user_id:
                    continue
                if action and entry.action != action:
                    continue
                if since and entry.timestamp < since:
                    continue
                
                yield entry


class S3ObjectLockBackend:
    """S3 backend with Object Lock for true WORM immutability.
    
    Requires S3 bucket with Object Lock enabled (Governance or Compliance mode).
    Each entry is a separate object with a retention period.
    
    This provides regulatory-grade immutability (SOC 2, HIPAA, etc.).
    """
    
    def __init__(
        self, 
        bucket: str, 
        prefix: str = "audit/",
        retention_days: int = 365,
        mode: Literal["GOVERNANCE", "COMPLIANCE"] = "GOVERNANCE",
    ):
        self.bucket = bucket
        self.prefix = prefix
        self.retention_days = retention_days
        self.mode = mode
        # boto3 client initialization...
    
    def append(self, entry: AuditEntry) -> None:
        """Write entry as locked S3 object."""
        key = f"{self.prefix}{entry.timestamp.isoformat()}_{entry.entry_hash[:8]}.json"
        
        retention_date = datetime.now() + timedelta(days=self.retention_days)
        
        self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(asdict(entry)),
            ObjectLockMode=self.mode,
            ObjectLockRetainUntilDate=retention_date,
        )
    
    def export_for_compliance(
        self,
        format: Literal["json", "csv", "siem"],
    ) -> str:
        """Export audit log for compliance/SIEM integration."""
        # Implementation for each format...
        ...
```

---

## User Experience

### CLI Workflow

```bash
$ sunwell run deploy-app --goal "Deploy the user service to staging"

📋 Pipeline Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Skills: build_image → run_tests → deploy_kubernetes → notify_slack

🔒 Permission Scope
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Filesystem Read:   /app/src/*, /app/k8s/*.yaml, /app/.env
Filesystem Write:  /tmp/build-*, /tmp/deploy-*
Network:           registry.internal:5000, k8s.internal:443
Shell Commands:    docker build/push, kubectl apply/rollout
Environment:       KUBECONFIG, REGISTRY_URL

⚠️  Risk Assessment: LOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ No credential access
✓ No external network
✓ No destructive commands
✓ Limited filesystem scope

Approve execution? [Y/n/modify]: y

🚀 Executing in secure sandbox...
  ✓ build_image (sandbox: docker-only)
  ✓ run_tests (sandbox: no-network)
  ✓ deploy_kubernetes (sandbox: k8s-internal)
  ✓ notify_slack (sandbox: slack-webhook-only)

✅ Pipeline complete. Audit log: ~/.sunwell/audit/2026-01-22-deploy-app.log
```

### High-Risk Scenario

```bash
$ sunwell run risky-task --goal "Debug the production database"

📋 Pipeline Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Skills: connect_db → query_data → export_results

🔒 Permission Scope
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Filesystem Read:   ~/.aws/credentials, /app/.env
Filesystem Write:  /tmp/export-*
Network:           db.production.internal:5432
Shell Commands:    psql *, pg_dump *

🚨 Risk Assessment: CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✗ CREDENTIAL_ACCESS: connect_db reads ~/.aws/credentials
✗ PRODUCTION_DATABASE: connect_db accesses db.production.internal
✗ DATA_EXPORT: export_results can write unbounded data

Recommendations:
• Use IAM role instead of credentials file
• Consider read-only replica instead of production
• Add row limit to query_data skill

Approve execution? [y/N/modify]: n
Execution cancelled.
```

---

## Integration with Existing Sunwell

### Skill Definition Extension (RFC-087)

```yaml
# skills/deploy.skill.yaml
skills:
  - name: deploy_kubernetes
    depends_on: [build_image]
    produces: ["deployment_status"]
    
    # RFC-089: Security permissions
    permissions:
      filesystem:
        read: ["/app/k8s/*.yaml"]
        write: ["/tmp/deploy-*"]
      network:
        allow: ["*.internal.cluster.local:443"]
      shell:
        allow: ["kubectl apply -f *", "kubectl rollout status *"]
        deny: ["kubectl delete *", "kubectl exec *"]
      
    # RFC-089: Security metadata
    security:
      data_classification: internal
      requires_approval: false
      audit_level: standard
```

### Lens Security Policy

```yaml
# lenses/devops.lens
lens:
  metadata:
    name: devops
    
  # RFC-089: Lens-level security policy
  security_policy:
    max_risk_level: medium  # Block high/critical by default
    require_approval_for:
      - credential_access
      - production_database
      - external_network
    
    blocked_patterns:
      - "rm -rf"
      - "curl * | sh"
      - "~/.ssh/*"
    
    audit_retention_days: 90
```

---

## Compliance & Enterprise Features

### SOC 2 / ISO 27001 Alignment

| Control | How Sunwell Addresses It |
|---------|-------------------------|
| **Access Control** | Declarative permissions, least privilege |
| **Audit Logging** | Immutable append-only log, signed entries |
| **Change Management** | DAG approval before execution |
| **Risk Assessment** | Automatic scoring, flag high-risk patterns |
| **Incident Response** | Full provenance, traceable to inputs |

### SIEM Integration

```python
# Export to Splunk, Datadog, etc.
audit_log.export_for_compliance(
    format="siem",
    destination="splunk://security.company.com:8088",
    token=os.environ["SPLUNK_TOKEN"],
)
```

### Policy as Code

```yaml
# .sunwell/security-policy.yaml
version: 1
policies:
  - name: no-production-access
    environments: [development, staging]
    deny:
      network: ["*.production.*"]
      
  - name: no-credential-files
    deny:
      filesystem_read: ["~/.aws/*", "~/.ssh/*", "~/.config/gcloud/*"]
    recommend: "Use IAM roles or environment variables instead"
    
  - name: require-approval-for-external
    require_approval:
      network: ["!*.internal.*"]  # Anything not internal
```

---

## Migration Path

### Phase 1: Permission Declaration (Non-Breaking)

1. Add optional `permissions` field to Skill
2. If not declared, assume "ambient" (legacy behavior)
3. Add permission analyzer for DAGs with declarations

### Phase 2: Soft Enforcement

1. Warn when permissions aren't declared
2. Show permission scope before execution
3. Log all permission usage for audit

### Phase 3: Hard Enforcement

1. Require permissions for new skills
2. Sandbox enforcement for skills with declarations
3. Block execution if permissions violated

### Phase 4: Enterprise Features

1. Policy as code
2. SIEM integration
3. Compliance reporting
4. Role-based approval workflows

### Phase 5: CLI Enhancements

1. Add `sunwell security analyze <dag>` — analyze permissions before execution
2. Add `sunwell security approve` — interactive approval flow
3. Add `sunwell security audit` — query audit log
4. Add `sunwell security verify` — verify audit log integrity
5. Add `--trust-all` flag with explicit warning (escape hatch)

### Phase 6: Platform Isolation

1. Implement seccomp sandbox (Linux)
2. Implement sandbox-exec profile generation (macOS)
3. Add container-based isolation option
4. Add benchmark suite for sandbox overhead
5. Document platform-specific limitations

### Phase 7: Studio Integration

See [Cross-Language Integration](#cross-language-integration) section for details.

1. TypeScript types (`security-types.ts`)
2. Rust types (`security.rs`)
3. Tauri commands for permission analysis and approval
4. Agent events for security workflow
5. Svelte store (`security.svelte.ts`)
6. UI components (`SecurityApprovalModal.svelte`, `AuditLogPanel.svelte`)

---

## Competitive Advantage

| Feature | Cursor/Copilot | Sunwell |
|---------|---------------|---------|
| **Permission model** | Ambient (trust all) | Declarative (least privilege) |
| **Pre-execution review** | None | Full permission scope |
| **Runtime enforcement** | None | Sandbox with seccomp |
| **Audit trail** | Minimal | Immutable, signed, exportable |
| **Risk assessment** | None | Automatic scoring |
| **Compliance** | Manual | Built-in SOC 2 alignment |
| **Policy as code** | None | Declarative security policies |

**This is the security model enterprises need to adopt AI coding assistants.**

---

## Success Metrics

1. **Adoption**: % of skills with declared permissions
2. **Violation rate**: Security violations caught per 1000 executions
3. **Risk reduction**: Average risk score before/after adoption
4. **Compliance**: Time to generate SOC 2 evidence
5. **User trust**: Survey on confidence in AI assistant security

---

## Cross-Language Integration

This RFC spans three codebases: **Python** (core security logic), **Rust** (Tauri backend), and **Svelte** (Studio UI). All must be updated for full functionality.

### Type Synchronization

| Language | Location | Primary Types |
|----------|----------|---------------|
| **Python** | `src/sunwell/security/` | `PermissionScope`, `RiskAssessment`, `SecurityClassification`, `AuditEntry` |
| **TypeScript** | `studio/src/lib/security-types.ts` | `PermissionScope`, `RiskAssessment`, `SecurityApproval` |
| **Rust** | `studio/src-tauri/src/security.rs` | `PermissionScope`, `RiskAssessment`, `SecurityApproval` |

**Synchronization mechanism**: JSON schema generated from Python types (`scripts/generate_security_types.py`), validated in CI.

### TypeScript Types (Studio)

```typescript
// studio/src/lib/security-types.ts — NEW FILE

/** Permission scope for a skill or DAG. */
export interface PermissionScope {
  filesystemRead: string[];
  filesystemWrite: string[];
  networkAllow: string[];
  networkDeny: string[];
  shellAllow: string[];
  shellDeny: string[];
  envRead: string[];
  envWrite: string[];
}

/** Risk assessment result. */
export interface RiskAssessment {
  level: 'low' | 'medium' | 'high' | 'critical';
  score: number;  // 0.0 - 1.0
  flags: string[];
  recommendations: string[];
}

/** Security approval request shown to user. */
export interface SecurityApproval {
  dagId: string;
  dagName: string;
  skillCount: number;
  permissions: PermissionScope;
  risk: RiskAssessment;
  timestamp: string;
}

/** User's response to security approval. */
export interface SecurityApprovalResponse {
  dagId: string;
  approved: boolean;
  modifiedPermissions?: PermissionScope;
  rememberForSession: boolean;
  acknowledgedRisks: string[];
}

/** Security violation detected during execution. */
export interface SecurityViolation {
  skillName: string;
  violationType: string;
  evidence: string;
  position: number;
  detectionMethod: 'deterministic' | 'llm';
  timestamp: string;
}

/** Audit log entry for UI display. */
export interface AuditEntryDisplay {
  timestamp: string;
  skillName: string;
  action: 'execute' | 'violation' | 'denied' | 'error';
  details: string;
  riskLevel: string;
}
```

### Rust Types (Tauri Backend)

```rust
// studio/src-tauri/src/security.rs — NEW FILE

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionScope {
    #[serde(rename = "filesystemRead")]
    pub filesystem_read: Vec<String>,
    #[serde(rename = "filesystemWrite")]
    pub filesystem_write: Vec<String>,
    #[serde(rename = "networkAllow")]
    pub network_allow: Vec<String>,
    #[serde(rename = "networkDeny")]
    pub network_deny: Vec<String>,
    #[serde(rename = "shellAllow")]
    pub shell_allow: Vec<String>,
    #[serde(rename = "shellDeny")]
    pub shell_deny: Vec<String>,
    #[serde(rename = "envRead")]
    pub env_read: Vec<String>,
    #[serde(rename = "envWrite")]
    pub env_write: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskAssessment {
    pub level: String,  // "low" | "medium" | "high" | "critical"
    pub score: f32,
    pub flags: Vec<String>,
    pub recommendations: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityApproval {
    #[serde(rename = "dagId")]
    pub dag_id: String,
    #[serde(rename = "dagName")]
    pub dag_name: String,
    #[serde(rename = "skillCount")]
    pub skill_count: u32,
    pub permissions: PermissionScope,
    pub risk: RiskAssessment,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityApprovalResponse {
    #[serde(rename = "dagId")]
    pub dag_id: String,
    pub approved: bool,
    #[serde(skip_serializing_if = "Option::is_none", rename = "modifiedPermissions")]
    pub modified_permissions: Option<PermissionScope>,
    #[serde(rename = "rememberForSession")]
    pub remember_for_session: bool,
    #[serde(rename = "acknowledgedRisks")]
    pub acknowledged_risks: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityViolation {
    #[serde(rename = "skillName")]
    pub skill_name: String,
    #[serde(rename = "violationType")]
    pub violation_type: String,
    pub evidence: String,
    pub position: u64,
    #[serde(rename = "detectionMethod")]
    pub detection_method: String,
    pub timestamp: String,
}
```

### New Tauri Commands

```rust
// studio/src-tauri/src/security.rs — ADD these commands

/// Analyze DAG permissions before execution.
#[tauri::command]
pub async fn analyze_dag_permissions(dag_id: String) -> Result<SecurityApproval, String> {
    sunwell_command()
        .args(["security", "analyze", &dag_id, "--json"])
        .output()
        .map_err(|e| format!("Failed to analyze permissions: {}", e))
        .and_then(|out| {
            if out.status.success() {
                serde_json::from_slice(&out.stdout)
                    .map_err(|e| format!("Failed to parse analysis: {}", e))
            } else {
                Err(String::from_utf8_lossy(&out.stderr).to_string())
            }
        })
}

/// Submit user's approval response.
#[tauri::command]
pub async fn submit_security_approval(response: SecurityApprovalResponse) -> Result<bool, String> {
    let json = serde_json::to_string(&response)
        .map_err(|e| format!("Failed to serialize response: {}", e))?;
    
    sunwell_command()
        .args(["security", "approve", "--json"])
        .stdin_string(json)
        .output()
        .map_err(|e| format!("Failed to submit approval: {}", e))
        .map(|out| out.status.success())
}

/// Get recent audit log entries for display.
#[tauri::command]
pub async fn get_audit_log(
    since: Option<String>,
    limit: Option<u32>,
) -> Result<Vec<AuditEntryDisplay>, String> {
    let mut cmd = sunwell_command();
    cmd.args(["security", "audit", "--json"]);
    
    if let Some(s) = since {
        cmd.args(["--since", &s]);
    }
    if let Some(l) = limit {
        cmd.args(["--limit", &l.to_string()]);
    }
    
    cmd.output()
        .map_err(|e| format!("Failed to get audit log: {}", e))
        .and_then(|out| {
            if out.status.success() {
                serde_json::from_slice(&out.stdout)
                    .map_err(|e| format!("Failed to parse audit log: {}", e))
            } else {
                Err(String::from_utf8_lossy(&out.stderr).to_string())
            }
        })
}

/// Verify audit log integrity.
#[tauri::command]
pub async fn verify_audit_integrity() -> Result<(bool, String), String> {
    sunwell_command()
        .args(["security", "audit", "--verify", "--json"])
        .output()
        .map_err(|e| format!("Failed to verify audit: {}", e))
        .and_then(|out| {
            if out.status.success() {
                serde_json::from_slice(&out.stdout)
                    .map_err(|e| format!("Failed to parse result: {}", e))
            } else {
                Err(String::from_utf8_lossy(&out.stderr).to_string())
            }
        })
}

// Register in main.rs:
// security::analyze_dag_permissions,
// security::submit_security_approval,
// security::get_audit_log,
// security::verify_audit_integrity,
```

### Agent Events

New events for security-first execution:

```typescript
// schemas/agent-events.schema.json — ADD these event types

interface SecurityApprovalRequestedEvent {
  type: 'security_approval_requested';
  data: {
    dag_id: string;
    dag_name: string;
    skill_count: number;
    risk_level: string;
    risk_score: number;
    flags: string[];
  };
}

interface SecurityApprovalReceivedEvent {
  type: 'security_approval_received';
  data: {
    dag_id: string;
    approved: boolean;
    modified: boolean;
    remembered: boolean;
  };
}

interface SecurityViolationEvent {
  type: 'security_violation';
  data: {
    skill_name: string;
    violation_type: string;
    evidence: string;
    detection_method: string;
    action_taken: 'logged' | 'paused' | 'aborted';
  };
}

interface SecurityScanCompleteEvent {
  type: 'security_scan_complete';
  data: {
    output_length: number;
    violations_found: number;
    scan_duration_ms: number;
    method: 'deterministic' | 'llm' | 'both';
  };
}

interface AuditLogEntryEvent {
  type: 'audit_log_entry';
  data: {
    skill_name: string;
    action: string;
    risk_level: string;
    timestamp: string;
  };
}
```

### Event Handling in Studio

```typescript
// studio/src/stores/agent.svelte.ts — ADD to handleAgentEvent()

case 'security_approval_requested': {
  const dagId = (data.dag_id as string) ?? '';
  const riskLevel = (data.risk_level as string) ?? 'low';
  const flags = (data.flags as string[]) ?? [];
  
  // Show approval modal
  showSecurityApprovalModal({
    dagId,
    riskLevel,
    flags,
    onApprove: (response) => submitSecurityApproval(response),
    onReject: () => submitSecurityApproval({ dagId, approved: false }),
  });
  
  _state = {
    ..._state,
    learnings: [
      ..._state.learnings,
      `🔒 Security review: ${riskLevel.toUpperCase()} risk (${flags.length} flags)`,
    ],
  };
  break;
}

case 'security_violation': {
  const skillName = (data.skill_name as string) ?? '';
  const violationType = (data.violation_type as string) ?? '';
  const actionTaken = (data.action_taken as string) ?? 'logged';
  
  const icon = actionTaken === 'aborted' ? '🛑' : '⚠️';
  
  _state = {
    ..._state,
    learnings: [
      ..._state.learnings,
      `${icon} Security: ${violationType} in ${skillName} (${actionTaken})`,
    ],
  };
  
  // Add to security violations store
  addSecurityViolation(data as SecurityViolation);
  break;
}

case 'security_scan_complete': {
  const violations = (data.violations_found as number) ?? 0;
  const icon = violations > 0 ? '⚠️' : '✅';
  
  _state = {
    ..._state,
    learnings: [
      ..._state.learnings,
      `${icon} Security scan: ${violations} violations found`,
    ],
  };
  break;
}
```

### Studio UI Components

#### SecurityApprovalModal.svelte (New)

```svelte
<!--
  SecurityApprovalModal.svelte — Permission approval dialog
  
  Shows permission scope and risk assessment before DAG execution.
  User can approve, reject, or modify permissions.
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/tauri';
  import type { SecurityApproval, SecurityApprovalResponse, PermissionScope } from '$lib/security-types';
  
  export let approval: SecurityApproval;
  export let onClose: () => void;
  
  let rememberForSession = false;
  let acknowledgedRisks: string[] = [];
  
  const riskColors = {
    low: 'text-green-500',
    medium: 'text-yellow-500',
    high: 'text-orange-500',
    critical: 'text-red-500',
  };
  
  async function handleApprove() {
    const response: SecurityApprovalResponse = {
      dagId: approval.dagId,
      approved: true,
      rememberForSession,
      acknowledgedRisks,
    };
    
    await invoke('submit_security_approval', { response });
    onClose();
  }
  
  async function handleReject() {
    const response: SecurityApprovalResponse = {
      dagId: approval.dagId,
      approved: false,
      rememberForSession: false,
      acknowledgedRisks: [],
    };
    
    await invoke('submit_security_approval', { response });
    onClose();
  }
</script>

<div class="modal-overlay">
  <div class="modal-content">
    <div class="header">
      <span class="title">🔒 Security Review Required</span>
      <span class="risk-badge {riskColors[approval.risk.level]}">
        {approval.risk.level.toUpperCase()} RISK
      </span>
    </div>
    
    <div class="dag-info">
      <span class="dag-name">{approval.dagName}</span>
      <span class="skill-count">{approval.skillCount} skills</span>
    </div>
    
    <div class="permissions-section">
      <h4>Permissions Requested</h4>
      
      {#if approval.permissions.filesystemRead.length > 0}
        <div class="permission-group">
          <span class="label">📁 Filesystem Read:</span>
          <ul>
            {#each approval.permissions.filesystemRead as path}
              <li><code>{path}</code></li>
            {/each}
          </ul>
        </div>
      {/if}
      
      {#if approval.permissions.filesystemWrite.length > 0}
        <div class="permission-group">
          <span class="label">✏️ Filesystem Write:</span>
          <ul>
            {#each approval.permissions.filesystemWrite as path}
              <li><code>{path}</code></li>
            {/each}
          </ul>
        </div>
      {/if}
      
      {#if approval.permissions.networkAllow.length > 0}
        <div class="permission-group">
          <span class="label">🌐 Network:</span>
          <ul>
            {#each approval.permissions.networkAllow as host}
              <li><code>{host}</code></li>
            {/each}
          </ul>
        </div>
      {/if}
      
      {#if approval.permissions.shellAllow.length > 0}
        <div class="permission-group">
          <span class="label">💻 Shell Commands:</span>
          <ul>
            {#each approval.permissions.shellAllow as cmd}
              <li><code>{cmd}</code></li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
    
    {#if approval.risk.flags.length > 0}
      <div class="flags-section">
        <h4>⚠️ Risk Flags</h4>
        <ul>
          {#each approval.risk.flags as flag}
            <li class="flag-item">
              <input 
                type="checkbox" 
                bind:group={acknowledgedRisks} 
                value={flag}
              />
              <span>{flag}</span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
    
    {#if approval.risk.recommendations.length > 0}
      <div class="recommendations">
        <h4>💡 Recommendations</h4>
        <ul>
          {#each approval.risk.recommendations as rec}
            <li>{rec}</li>
          {/each}
        </ul>
      </div>
    {/if}
    
    <div class="actions">
      <label class="remember-option">
        <input type="checkbox" bind:checked={rememberForSession} />
        Remember for this session
      </label>
      
      <div class="buttons">
        <button class="reject-btn" onclick={handleReject}>
          Reject
        </button>
        <button 
          class="approve-btn" 
          onclick={handleApprove}
          disabled={approval.risk.flags.length > 0 && acknowledgedRisks.length < approval.risk.flags.length}
        >
          {#if approval.risk.level === 'critical'}
            Approve Anyway
          {:else}
            Approve
          {/if}
        </button>
      </div>
    </div>
  </div>
</div>
```

#### AuditLogPanel.svelte (New)

```svelte
<!--
  AuditLogPanel.svelte — Security audit log viewer
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/tauri';
  import type { AuditEntryDisplay } from '$lib/security-types';
  
  let entries: AuditEntryDisplay[] = [];
  let integrityStatus: { valid: boolean; message: string } | null = null;
  
  const actionIcons = {
    execute: '✅',
    violation: '🛑',
    denied: '🚫',
    error: '❌',
  };
  
  onMount(async () => {
    entries = await invoke('get_audit_log', { limit: 50 });
    integrityStatus = await invoke('verify_audit_integrity');
  });
  
  async function refresh() {
    entries = await invoke('get_audit_log', { limit: 50 });
  }
</script>

<div class="audit-panel">
  <div class="header">
    <h3>🔐 Security Audit Log</h3>
    <div class="integrity-status">
      {#if integrityStatus}
        {#if integrityStatus.valid}
          <span class="valid">✓ Integrity verified</span>
        {:else}
          <span class="invalid">⚠️ {integrityStatus.message}</span>
        {/if}
      {/if}
    </div>
    <button onclick={refresh}>↻ Refresh</button>
  </div>
  
  <div class="entries">
    {#each entries as entry}
      <div class="entry" class:violation={entry.action === 'violation'}>
        <span class="icon">{actionIcons[entry.action]}</span>
        <span class="timestamp">{entry.timestamp}</span>
        <span class="skill">{entry.skillName}</span>
        <span class="details">{entry.details}</span>
        <span class="risk-badge {entry.riskLevel}">{entry.riskLevel}</span>
      </div>
    {/each}
  </div>
</div>
```

### New Svelte Store

```typescript
// studio/src/stores/security.svelte.ts — NEW FILE

import type { 
  SecurityApproval, 
  SecurityViolation, 
  PermissionScope,
  AuditEntryDisplay 
} from '$lib/security-types';

interface SecurityState {
  pendingApproval: SecurityApproval | null;
  violations: SecurityViolation[];
  sessionApprovals: Map<string, PermissionScope>;  // dagId → approved scope
  auditEntries: AuditEntryDisplay[];
}

const initialState: SecurityState = {
  pendingApproval: null,
  violations: [],
  sessionApprovals: new Map(),
  auditEntries: [],
};

let _state = $state<SecurityState>({ ...initialState });

export const securityState = {
  get pendingApproval() { return _state.pendingApproval; },
  get violations() { return _state.violations; },
  get sessionApprovals() { return _state.sessionApprovals; },
  get auditEntries() { return _state.auditEntries; },
  
  get hasUnacknowledgedViolations() {
    return _state.violations.some(v => !v.acknowledged);
  },
  
  get violationCount() {
    return _state.violations.length;
  },
};

export function setPendingApproval(approval: SecurityApproval | null): void {
  _state = { ..._state, pendingApproval: approval };
}

export function addSecurityViolation(violation: SecurityViolation): void {
  _state = { 
    ..._state, 
    violations: [..._state.violations, violation] 
  };
}

export function rememberApprovalForSession(dagId: string, scope: PermissionScope): void {
  const newApprovals = new Map(_state.sessionApprovals);
  newApprovals.set(dagId, scope);
  _state = { ..._state, sessionApprovals: newApprovals };
}

export function isApprovedForSession(dagId: string): boolean {
  return _state.sessionApprovals.has(dagId);
}

export function getSessionApproval(dagId: string): PermissionScope | undefined {
  return _state.sessionApprovals.get(dagId);
}

export function setAuditEntries(entries: AuditEntryDisplay[]): void {
  _state = { ..._state, auditEntries: entries };
}

export function clearViolations(): void {
  _state = { ..._state, violations: [] };
}

export function resetSecurityState(): void {
  _state = { ...initialState };
}
```

**Risk**: Medium — requires coordination across three languages. Mitigated by JSON schema validation and shared test fixtures.

---

## Open Questions

### Resolved in This RFC

| Question | Resolution |
|----------|------------|
| **How to integrate with existing guardrails?** | Maps to `ActionRisk` enum, composes with RFC-048 |
| **What's the pattern syntax?** | Glob for filesystem, prefix for shell, host:port for network |
| **How to make audit logs truly immutable?** | Multiple backends with increasing guarantees |
| **LLM classification reliability?** | Deterministic checks first, LLM optional |

### Still Open

1. **Granularity trade-off**: Fine-grained permissions (per-file) vs coarse (per-directory)?
   - *Proposal*: Start coarse (directory-level), add fine-grained as opt-in

2. **Legacy skill defaults**: What permissions for skills without declarations?
   - *Proposal*: `trust: sandboxed` skills get default `PermissionScope()` (empty = nothing allowed)
   - *Alternative*: Infer from `TrustLevel` — `FULL` → ambient, `SANDBOXED` → prompt for each

3. **Performance budget**: What's acceptable sandbox overhead?
   - *Target*: < 50ms setup per skill, < 5% runtime overhead
   - *Measurement*: Add benchmarks in Phase 2

4. **Approval fatigue UX**: How to minimize prompts?
   - *Proposal*: "Remember for session" option, risk-based auto-approve thresholds
   - *Research*: Study Cursor/VS Code permission prompts for patterns

5. **Escape hatch**: When can users bypass security?
   - *Proposal*: `--trust-all` CLI flag with explicit warning, logged to audit
   - *Policy*: Enterprises can disable via `security_policy.yaml`

6. **Container vs native sandbox**: When to prefer which?
   - *Proposal*: Native for low-latency (< 100ms), container for strong isolation (CI/CD)
   - *Decision*: Make configurable per-skill or per-lens

---

## References

### Internal RFCs & Code

- **RFC-087**: Skill-Lens DAG — Foundation for skill dependencies
- **RFC-048**: Autonomy Guardrails — Risk classification, scope tracking
- `src/sunwell/skills/types.py:67-76` — `TrustLevel` enum
- `src/sunwell/skills/sandbox.py:33-59` — `ScriptSandbox` base class
- `src/sunwell/skills/graph.py` — `SkillGraph` DAG implementation
- `src/sunwell/guardrails/types.py:17-59` — `ActionRisk` enum
- `src/sunwell/guardrails/scope.py` — `ScopeTracker` implementation

### External References

- [Principle of Least Privilege](https://en.wikipedia.org/wiki/Principle_of_least_privilege)
- [seccomp](https://man7.org/linux/man-pages/man2/seccomp.2.html) — Linux syscall filtering
- [Linux Namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html) — Process isolation
- [macOS sandbox-exec](https://reverse.put.as/wp-content/uploads/2011/09/Apple-Sandbox-Guide-v1.0.pdf) — macOS sandboxing
- [SOC 2 Compliance](https://www.aicpa.org/soc2) — Security compliance framework
- [MITRE ATT&CK](https://attack.mitre.org/) — Threat modeling (informed risk weights)
- [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) — WORM storage
