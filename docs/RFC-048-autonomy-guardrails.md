# RFC-048: Autonomy Guardrails — Safe Unsupervised Operation

**Status**: Draft (Revised)  
**Created**: 2026-01-19  
**Last Updated**: 2026-01-19  
**Authors**: Sunwell Team  
**Depends on**: RFC-042 (Adaptive Agent), RFC-046 (Autonomous Backlog), RFC-047 (Deep Verification)  
**Enables**: Phase 3 Autonomous Agent

---

## Summary

Autonomy Guardrails define what Sunwell can do unsupervised and what requires human approval. The system classifies every action by risk level, enforces hard limits on autonomous scope, and provides clear escalation paths when guardrails are triggered.

**Core insight**: Autonomy is a spectrum, not binary. A file fix in `tests/` is safe; deleting `.env` is not. Guardrails encode this spectrum with graduated trust levels that users can configure.

**Design approach**: Multi-layer guardrails (action classification + scope limits + verification gates) was selected over simpler allowlist/blocklist or heavier container sandboxing. See "Design Alternatives Considered" for full comparison.

**One-liner**: Sunwell works overnight — but only on tasks it can't break.

---

## Motivation

### The Autonomy Dilemma

RFC-046 (Autonomous Backlog) enables Sunwell to generate and execute goals without explicit commands. But "autonomous" without "guardrails" is dangerous:

```
User: sunwell backlog --autonomous
[overnight...]
Sunwell: I noticed the API seemed slow, so I:
  ✅ Optimized database queries
  ✅ Added caching layer  
  ❌ Dropped unused tables (oops, that was production data)
  ❌ Rotated API keys (oops, broke all clients)
```

Without guardrails, autonomous mode is a footgun.

### What "Safe Autonomous" Means

| Autonomous = Dangerous | Autonomous + Guardrails |
|------------------------|------------------------|
| Can do anything | Can only do pre-approved action classes |
| Unbounded scope | Scoped to safe paths |
| No checkpoints | Git commits at each step (revertible) |
| Silent failures | Loud escalations on uncertainty |
| One big change | Small atomic changes |
| Trust everything | Verify before applying |

### Current State

RFC-046 introduces `auto_approvable` on goals:

```python
# Current: Simple category + complexity check
auto_approve_categories: frozenset[str] = frozenset({"fix", "test"})
auto_approve_complexity: frozenset[str] = frozenset({"trivial", "simple"})
```

This is insufficient because:
1. **Scope is unbounded** — A "fix" goal could touch critical files
2. **No action classification** — `rm -rf /` and `pytest` are treated equally
3. **No verification** — Assumed correct if no error raised
4. **No recovery** — If it breaks, manual cleanup required
5. **No escalation** — Blocked goals just wait forever

---

## Goals and Non-Goals

### Goals

1. **Action classification** — Categorize every action by risk level
2. **Path-based trust zones** — Safe paths (tests) vs protected paths (.env)
3. **Hard scope limits** — Bounded file count, line changes, duration
4. **Automatic recovery** — Git commits enable instant revert
5. **Clear escalation** — When guardrails trigger, explain why and how to proceed
6. **User-configurable levels** — Conservative default, power users can relax
7. **Integration with verification** — RFC-047 confidence feeds into approval

### Non-Goals

1. **Security auditing** — Not a security tool, just operational safety
2. **Multi-user permissions** — Single-user focus (enterprise is future RFC)
3. **Remote execution** — Local machine only
4. **Sandboxing** — Relies on git for recovery, not containers
5. **Formal verification** — Heuristic guardrails, not mathematical proofs

---

## Design Alternatives Considered

### Option A: Simple Allowlist/Blocklist (Rejected)

```python
# Simple approach: just list safe and dangerous paths
safe_paths = ["tests/**", "docs/**"]
blocked_paths = [".env*", "**/auth/**"]

def can_auto_approve(path: str) -> bool:
    if any(fnmatch(path, p) for p in blocked_paths):
        return False
    return any(fnmatch(path, p) for p in safe_paths)
```

**Pros**:
- Simple to implement (~50 lines)
- Easy to understand and configure
- Fast execution (no ML/verification overhead)

**Cons**:
- ❌ No scope limits — "add docstrings to 10,000 files" would auto-approve
- ❌ Binary decision — no graduated risk levels
- ❌ No verification integration — can't use RFC-047 confidence
- ❌ No recovery — if something breaks, manual cleanup required
- ❌ Action-blind — `rm tests/foo.py` and `echo "test" > tests/foo.py` treated equally

**Verdict**: Too simplistic. Safe paths can still have dangerous operations.

### Option B: Container Sandbox (Future Work)

```python
# Run all autonomous operations in isolated container
async def execute_sandboxed(goal: Goal) -> Result:
    container = await create_ephemeral_container(
        base_image="sunwell-sandbox:latest",
        mounts=[("/workspace", project_path, "rw")],
    )
    result = await container.run(goal)
    if result.success:
        await container.commit_to_host()  # Copy changes out
    return result
```

**Pros**:
- True isolation — cannot damage host system
- Atomic — either all changes apply or none
- Can allow more dangerous operations safely

**Cons**:
- ❌ Heavy infrastructure — requires Docker/Podman
- ❌ Slow startup — container creation adds 2-5s per goal
- ❌ Complex file sync — managing workspace mounts is error-prone
- ❌ Platform limitations — Docker not available everywhere
- ❌ Overkill for most operations — "fix typo in README" doesn't need a container

**Verdict**: Good for high-risk operations but too heavy for default. Consider as future enhancement for DANGEROUS actions only.

### Option C: Multi-Layer Guardrails (Selected) ✅

The approach described in this RFC:

```
Layer 1: Action Classification → Know what's risky
Layer 2: Scope Limits         → Bound blast radius  
Layer 3: Verification Gate    → Ensure correctness
Layer 4: Recovery System      → Enable rollback
```

**Pros**:
- ✅ Graduated risk — SAFE/MODERATE/DANGEROUS/FORBIDDEN levels
- ✅ Defense in depth — multiple independent checks
- ✅ Integrates with RFC-047 — confidence-based decisions
- ✅ Lightweight — no container overhead
- ✅ Recoverable — git checkpoints enable instant rollback
- ✅ Configurable — users can adjust trust levels

**Cons**:
- More complex than Option A (~500 lines vs ~50)
- Classification can have false positives/negatives
- Git recovery requires clean state at start

**Verdict**: Best balance of safety, flexibility, and performance. Classification errors are mitigated by scope limits and verification gates.

### Decision Matrix

| Criteria | Allowlist | Container | Multi-Layer |
|----------|-----------|-----------|-------------|
| Implementation complexity | Low | High | Medium |
| Runtime overhead | None | High (2-5s) | Low (~100ms) |
| Safety guarantee | Weak | Strong | Moderate |
| Recovery mechanism | None | Atomic | Git-based |
| Verification integration | No | Yes | Yes |
| Scope limiting | No | Yes | Yes |
| User configurability | Low | Low | High |
| **Overall** | ❌ | Future | ✅ Selected |

---

## Design Overview

### The Trust Pyramid

```
                         ┌─────────────────────┐
                         │   FULL AUTONOMY     │ ← Future (human-in-the-loop verified)
                         │   (no limits)       │
                         ├─────────────────────┤
                         │   SUPERVISED        │ ← Prompt before dangerous actions
                         │   (ask for some)    │
                         ├─────────────────────┤
                         │   GUARDED           │ ← DEFAULT: Auto-approve within limits
                         │   (bounded scope)   │
                         ├─────────────────────┤
                         │   CONSERVATIVE      │ ← Propose only, never execute
                         │   (read-only mode)  │
                         └─────────────────────┘
```

Users choose their trust level. Each level inherits restrictions from below.

### The Three Guardrail Layers

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          GUARDRAIL LAYERS                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 1: ACTION CLASSIFICATION                                        │  │
│  │  Every action categorized: SAFE / MODERATE / DANGEROUS / FORBIDDEN     │  │
│  │  Dangerous actions require approval at any trust level                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 2: SCOPE LIMITS                                                 │  │
│  │  Hard caps: files touched, lines changed, duration, complexity         │  │
│  │  Exceeding limits triggers escalation (even for SAFE actions)          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 3: VERIFICATION GATE                                            │  │
│  │  RFC-047 Deep Verification confidence check                            │  │
│  │  Low confidence → escalate even if action is SAFE                      │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  All three layers must pass for autonomous execution.                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Action Classification

### Risk Levels

```python
class ActionRisk(Enum):
    """Risk classification for actions."""
    
    SAFE = "safe"
    """Can be executed autonomously within scope limits.
    
    Examples:
    - Write/modify test files
    - Add docstrings
    - Fix lint errors
    - Add type hints
    """
    
    MODERATE = "moderate"
    """Requires verification but can be auto-approved if confident.
    
    Examples:
    - Modify source files (non-critical paths)
    - Add new files
    - Modify configuration (non-secrets)
    - Run build commands
    """
    
    DANGEROUS = "dangerous"
    """Always requires human approval, even in FULL_AUTONOMY mode.
    
    Examples:
    - Delete files
    - Modify auth/security code
    - Change database schemas
    - Modify CI/CD configuration
    - Publish/deploy operations
    """
    
    FORBIDDEN = "forbidden"
    """Never executed, period. Hard-coded protection.
    
    Examples:
    - Access to credentials/secrets
    - Network operations to external hosts
    - System file modifications
    - Package publishing
    """
```

### Action Taxonomy

```yaml
# File Operations
file_read:
  risk: SAFE
  description: "Read file contents"
  
file_write_test:
  risk: SAFE
  description: "Write to tests/ directory"
  patterns: ["tests/**", "**/*_test.py", "**/test_*.py"]
  
file_write_docs:
  risk: SAFE
  description: "Write to docs/ or docstrings"
  patterns: ["docs/**", "**/*.md", "README*"]
  
file_write_source:
  risk: MODERATE
  description: "Write to source files"
  patterns: ["src/**", "**/*.py"]
  excludes: ["**/auth/**", "**/security/**", "**/config/**"]
  
file_write_config:
  risk: DANGEROUS
  description: "Write configuration files"
  patterns: ["*.json", "*.yaml", "*.toml", "pyproject.toml"]
  excludes: [".env*", "*secret*", "*credentials*"]
  
file_write_secrets:
  risk: FORBIDDEN
  description: "Write to secret files"
  patterns: [".env*", "*secret*", "*credential*", "*.pem", "*.key"]
  
file_delete:
  risk: DANGEROUS
  description: "Delete any file"
  
# Shell Operations
shell_test:
  risk: SAFE
  description: "Run test commands"
  patterns: ["pytest*", "ruff check*", "ty*", "mypy*"]
  
shell_build:
  risk: MODERATE
  description: "Run build commands"
  patterns: ["pip install*", "uv sync*", "make*"]
  
shell_dangerous:
  risk: DANGEROUS
  description: "Potentially destructive shell commands"
  patterns: ["rm *", "git push*", "git reset --hard*", "docker*"]
  
shell_network:
  risk: FORBIDDEN
  description: "Network operations"
  patterns: ["curl*", "wget*", "ssh*", "scp*"]

# Database Operations
db_read:
  risk: SAFE
  description: "Read from database"
  
db_write:
  risk: MODERATE
  description: "Write to database (non-schema)"
  
db_schema:
  risk: DANGEROUS
  description: "Modify database schema"
  
db_drop:
  risk: FORBIDDEN
  description: "Drop tables or databases"
```

### Classification Logic

```python
@dataclass(frozen=True, slots=True)
class ActionClassification:
    """Classification result for an action."""
    
    action_type: str
    """e.g., 'file_write_source'"""
    
    risk: ActionRisk
    """Classified risk level."""
    
    path: str | None
    """File path if applicable."""
    
    reason: str
    """Why this classification."""
    
    escalation_required: bool
    """Whether this needs human approval."""
    
    blocking_rule: str | None
    """Which rule triggered escalation (if any)."""


class ActionClassifier:
    """Classify actions by risk level.
    
    Classification strategy:
    1. Match action against known patterns
    2. Check path against trust zones
    3. Check for explicit forbidden patterns
    4. Default to MODERATE for unknown actions
    """
    
    def __init__(self, config: GuardrailConfig):
        self.config = config
        self._load_taxonomy()
    
    def classify(self, action: Action) -> ActionClassification:
        """Classify a single action.
        
        Args:
            action: The action to classify
        
        Returns:
            ActionClassification with risk level and details
        """
        # 1. Check forbidden patterns first (hard-coded protection)
        if self._is_forbidden(action):
            return ActionClassification(
                action_type=action.action_type,
                risk=ActionRisk.FORBIDDEN,
                path=action.path,
                reason="Matches forbidden pattern",
                escalation_required=True,
                blocking_rule="forbidden_pattern",
            )
        
        # 2. Check dangerous patterns
        if self._is_dangerous(action):
            return ActionClassification(
                action_type=action.action_type,
                risk=ActionRisk.DANGEROUS,
                path=action.path,
                reason=self._get_dangerous_reason(action),
                escalation_required=True,
                blocking_rule="dangerous_pattern",
            )
        
        # 3. Check safe patterns (trust zones)
        if self._is_safe(action):
            return ActionClassification(
                action_type=action.action_type,
                risk=ActionRisk.SAFE,
                path=action.path,
                reason="Matches safe pattern",
                escalation_required=False,
                blocking_rule=None,
            )
        
        # 4. Default to moderate
        return ActionClassification(
            action_type=action.action_type,
            risk=ActionRisk.MODERATE,
            path=action.path,
            reason="Default classification",
            escalation_required=self.config.trust_level < TrustLevel.SUPERVISED,
            blocking_rule=None,
        )
    
    def _is_forbidden(self, action: Action) -> bool:
        """Check if action matches forbidden patterns.
        
        Design decision: FORBIDDEN is truly hard-coded with NO escape hatch.
        
        Rationale:
        1. These patterns protect against catastrophic failures
        2. If you need to modify .env, do it manually (10 seconds)
        3. An escape hatch would undermine the entire safety model
        4. "Trust but verify" fails when the failure mode is catastrophic
        
        If a legitimate use case emerges, it should be addressed via
        a new RFC that carefully considers the security implications.
        """
        # Hard-coded, cannot be overridden
        forbidden_patterns = [
            # Secrets
            ".env", ".env.*", "*.key", "*.pem", "*secret*", "*credential*",
            # System
            "/etc/*", "/usr/*", "/var/*", "~/.ssh/*",
            # Dangerous commands
            "rm -rf /", ":(){ :|:& };:", "sudo rm",
        ]
        
        if action.path:
            for pattern in forbidden_patterns:
                if fnmatch(action.path, pattern):
                    return True
        
        if action.command:
            for pattern in forbidden_patterns:
                if pattern in action.command:
                    return True
        
        return False
```

---

## Scope Limits

Hard caps that cannot be exceeded even for SAFE actions.

### Scope Configuration

```python
@dataclass
class ScopeLimits:
    """Hard limits on autonomous operation scope.
    
    These limits exist because even SAFE actions can become
    dangerous at scale. "Add docstrings" is safe; "add docstrings
    to 10,000 files" is a footgun.
    """
    
    # Per-goal limits
    max_files_per_goal: int = 10
    """Maximum files touched by a single goal."""
    
    max_lines_changed_per_goal: int = 500
    """Maximum lines added/removed by a single goal."""
    
    max_duration_per_goal_minutes: int = 30
    """Maximum execution time for a single goal."""
    
    # Session limits
    max_goals_per_session: int = 20
    """Maximum goals executed in one autonomous session."""
    
    max_files_per_session: int = 50
    """Maximum total files touched in one session."""
    
    max_lines_per_session: int = 2000
    """Maximum total lines changed in one session."""
    
    max_duration_per_session_hours: int = 8
    """Maximum duration of autonomous session."""
    
    # Safety margins
    require_tests_for_source_changes: bool = True
    """If changing src/, must also add/modify tests/."""
    
    require_git_clean_start: bool = True
    """Refuse to start autonomous mode with uncommitted changes."""
    
    commit_after_each_goal: bool = True
    """Create git commit after each goal completes."""


class ScopeTracker:
    """Track scope usage and enforce limits."""
    
    def __init__(self, limits: ScopeLimits):
        self.limits = limits
        self.session_files: set[Path] = set()
        self.session_lines_changed: int = 0
        self.session_goals_completed: int = 0
        self.session_start: datetime = datetime.now()
    
    def check_goal(self, goal: Goal, planned_changes: list[FileChange]) -> ScopeCheckResult:
        """Check if a goal fits within limits.
        
        Returns:
            ScopeCheckResult indicating pass/fail and reason
        """
        # Check per-goal limits
        files_count = len(planned_changes)
        lines_count = sum(c.lines_added + c.lines_removed for c in planned_changes)
        
        if files_count > self.limits.max_files_per_goal:
            return ScopeCheckResult(
                passed=False,
                reason=f"Goal touches {files_count} files (limit: {self.limits.max_files_per_goal})",
                limit_type="files_per_goal",
            )
        
        if lines_count > self.limits.max_lines_changed_per_goal:
            return ScopeCheckResult(
                passed=False,
                reason=f"Goal changes {lines_count} lines (limit: {self.limits.max_lines_changed_per_goal})",
                limit_type="lines_per_goal",
            )
        
        # Check session limits
        new_session_files = len(self.session_files | {c.path for c in planned_changes})
        if new_session_files > self.limits.max_files_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session would touch {new_session_files} files (limit: {self.limits.max_files_per_session})",
                limit_type="files_per_session",
            )
        
        new_session_lines = self.session_lines_changed + lines_count
        if new_session_lines > self.limits.max_lines_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session would change {new_session_lines} lines (limit: {self.limits.max_lines_per_session})",
                limit_type="lines_per_session",
            )
        
        if self.session_goals_completed >= self.limits.max_goals_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session completed {self.session_goals_completed} goals (limit: {self.limits.max_goals_per_session})",
                limit_type="goals_per_session",
            )
        
        # Check duration
        elapsed = datetime.now() - self.session_start
        if elapsed.total_seconds() > self.limits.max_duration_per_session_hours * 3600:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session duration exceeded {self.limits.max_duration_per_session_hours}h",
                limit_type="duration_per_session",
            )
        
        # Check source+test requirement
        if self.limits.require_tests_for_source_changes:
            source_files = [c for c in planned_changes if self._is_source_file(c.path)]
            test_files = [c for c in planned_changes if self._is_test_file(c.path)]
            
            if source_files and not test_files:
                return ScopeCheckResult(
                    passed=False,
                    reason="Source changes require corresponding test changes",
                    limit_type="require_tests",
                )
        
        return ScopeCheckResult(passed=True, reason="Within limits")
    
    def record_goal_completion(self, changes: list[FileChange]) -> None:
        """Record completed goal for session tracking."""
        self.session_files.update(c.path for c in changes)
        self.session_lines_changed += sum(c.lines_added + c.lines_removed for c in changes)
        self.session_goals_completed += 1
```

---

## Trust Zones

Path-based trust configuration.

```python
@dataclass
class TrustZone:
    """A path pattern with associated trust level."""
    
    pattern: str
    """Glob pattern for matching paths."""
    
    risk_override: ActionRisk | None = None
    """Override default risk for this zone."""
    
    allowed_in_autonomous: bool = True
    """Whether autonomous mode can touch this zone."""
    
    reason: str = ""
    """Why this zone has special treatment."""


DEFAULT_TRUST_ZONES = [
    # Safe zones (can be modified autonomously)
    TrustZone(
        pattern="tests/**",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Test files are safe to modify",
    ),
    TrustZone(
        pattern="docs/**",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Documentation is safe to modify",
    ),
    TrustZone(
        pattern="**/__pycache__/**",
        risk_override=ActionRisk.SAFE,
        allowed_in_autonomous=True,
        reason="Cache files can be regenerated",
    ),
    
    # Protected zones (require approval)
    TrustZone(
        pattern="**/auth/**",
        risk_override=ActionRisk.DANGEROUS,
        allowed_in_autonomous=False,
        reason="Authentication code is security-critical",
    ),
    TrustZone(
        pattern="**/security/**",
        risk_override=ActionRisk.DANGEROUS,
        allowed_in_autonomous=False,
        reason="Security code is critical",
    ),
    TrustZone(
        pattern="**/migrations/**",
        risk_override=ActionRisk.DANGEROUS,
        allowed_in_autonomous=False,
        reason="Database migrations can cause data loss",
    ),
    
    # Forbidden zones (never touch)
    TrustZone(
        pattern=".env*",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Environment files contain secrets",
    ),
    TrustZone(
        pattern="**/.git/**",
        risk_override=ActionRisk.FORBIDDEN,
        allowed_in_autonomous=False,
        reason="Git internals should not be modified",
    ),
]
```

---

## Verification Integration

RFC-047 Deep Verification provides semantic confidence. Guardrails use this.

```python
class VerificationGate:
    """Gate that requires verification before approval.
    
    Integration with RFC-047:
    - DeepVerifier produces confidence score (0-1)
    - Guardrails use confidence to decide approval
    """
    
    def __init__(
        self,
        verifier: DeepVerifier,
        thresholds: VerificationThresholds,
    ):
        self.verifier = verifier
        self.thresholds = thresholds
    
    async def check(
        self,
        artifact: ArtifactSpec,
        content: str,
        goal: Goal,
    ) -> VerificationGateResult:
        """Check if artifact passes verification gate.
        
        Decision matrix:
        
        | Risk | Confidence | Result |
        |------|------------|--------|
        | SAFE | >= 0.7 | Auto-approve |
        | SAFE | < 0.7 | Escalate |
        | MODERATE | >= 0.85 | Auto-approve |
        | MODERATE | < 0.85 | Escalate |
        | DANGEROUS | any | Always escalate |
        """
        # Get action classification
        classification = self.classifier.classify_goal(goal)
        
        # FORBIDDEN never proceeds
        if classification.risk == ActionRisk.FORBIDDEN:
            return VerificationGateResult(
                passed=False,
                auto_approvable=False,
                reason="Action is forbidden",
                confidence=0.0,
            )
        
        # DANGEROUS always escalates
        if classification.risk == ActionRisk.DANGEROUS:
            return VerificationGateResult(
                passed=True,  # Can proceed with approval
                auto_approvable=False,
                reason="Dangerous action requires approval",
                confidence=None,  # Skip verification
            )
        
        # Run deep verification
        result = None
        async for event in self.verifier.verify(artifact, content):
            if event.stage == "complete":
                result = event.data["result"]
        
        if result is None:
            return VerificationGateResult(
                passed=False,
                auto_approvable=False,
                reason="Verification failed to complete",
                confidence=0.0,
            )
        
        # Apply threshold based on risk
        threshold = self._get_threshold(classification.risk)
        
        if result.confidence >= threshold:
            return VerificationGateResult(
                passed=True,
                auto_approvable=True,
                reason=f"Confidence {result.confidence:.0%} >= {threshold:.0%}",
                confidence=result.confidence,
                verification_result=result,
            )
        else:
            return VerificationGateResult(
                passed=True,  # Can proceed with approval
                auto_approvable=False,
                reason=f"Confidence {result.confidence:.0%} < {threshold:.0%}",
                confidence=result.confidence,
                verification_result=result,
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


@dataclass
class VerificationThresholds:
    """Confidence thresholds for auto-approval.
    
    Threshold Rationale (based on RFC-047 confidence semantics):
    
    - 0.70 (SAFE): At 70%, verification has "moderate" confidence.
      SAFE actions (tests, docs) have low blast radius, so moderate
      confidence is acceptable. False positives just trigger review.
      
    - 0.85 (MODERATE): At 85%, verification has "high" confidence.
      MODERATE actions (source changes) need stronger assurance.
      This threshold matches RFC-047's "high confidence" boundary.
      
    These defaults align with RFC-047 ConfidenceTriangulator:
    - >= 0.9: "high" confidence
    - >= 0.7: "moderate" confidence  
    - >= 0.5: "low" confidence
    - < 0.5: "uncertain"
    
    Users can adjust via config if their risk tolerance differs.
    """
    
    safe_threshold: float = 0.70
    """Threshold for SAFE actions (RFC-047 "moderate" confidence)."""
    
    moderate_threshold: float = 0.85
    """Threshold for MODERATE actions (RFC-047 "high" confidence)."""
```

---

## Escalation System

When guardrails trigger, the system must clearly communicate why and offer options.

```python
@dataclass(frozen=True, slots=True)
class Escalation:
    """An escalation event requiring human decision."""
    
    id: str
    goal_id: str
    
    reason: EscalationReason
    """Why escalation was triggered."""
    
    details: str
    """Human-readable explanation."""
    
    blocking_rule: str
    """Which guardrail triggered this."""
    
    action_classification: ActionClassification | None
    """Classification if action-related."""
    
    scope_check: ScopeCheckResult | None
    """Scope check if limit-related."""
    
    verification_result: DeepVerificationResult | None
    """Verification if confidence-related."""
    
    options: tuple[EscalationOption, ...]
    """Available options for the user."""
    
    recommended_option: str
    """ID of recommended option."""
    
    timestamp: datetime
    
    @property
    def severity(self) -> Literal["info", "warning", "critical"]:
        """Severity based on blocking rule."""
        match self.reason:
            case EscalationReason.FORBIDDEN_ACTION:
                return "critical"
            case EscalationReason.DANGEROUS_ACTION:
                return "warning"
            case _:
                return "info"


class EscalationReason(Enum):
    """Reasons for escalation."""
    
    # Action-related
    FORBIDDEN_ACTION = "forbidden_action"
    DANGEROUS_ACTION = "dangerous_action"
    UNKNOWN_ACTION = "unknown_action"
    
    # Scope-related
    SCOPE_EXCEEDED = "scope_exceeded"
    DURATION_EXCEEDED = "duration_exceeded"
    FILES_LIMIT = "files_limit"
    
    # Verification-related
    LOW_CONFIDENCE = "low_confidence"
    VERIFICATION_FAILED = "verification_failed"
    
    # Policy-related
    PROTECTED_PATH = "protected_path"
    MISSING_TESTS = "missing_tests"


@dataclass(frozen=True, slots=True)
class EscalationOption:
    """An option presented to the user during escalation."""
    
    id: str
    label: str
    description: str
    
    action: Literal[
        "approve",      # Proceed with the action
        "approve_once", # Approve this once, keep guardrail
        "skip",         # Skip this goal, continue session
        "modify",       # Let user modify the goal
        "abort",        # Abort entire session
        "relax",        # Relax the guardrail for session
    ]
    
    risk_acknowledgment: str | None = None
    """Warning user must acknowledge if risky."""


class EscalationHandler:
    """Handle escalations with clear user communication."""
    
    def __init__(self, ui: UIProtocol):
        self.ui = ui
        self._pending: dict[str, Escalation] = {}
    
    async def escalate(self, escalation: Escalation) -> EscalationResolution:
        """Present escalation to user and await resolution."""
        
        # Store pending
        self._pending[escalation.id] = escalation
        
        # Format message
        message = self._format_escalation(escalation)
        
        # Present to user
        await self.ui.show_escalation(
            severity=escalation.severity,
            message=message,
            options=[self._format_option(o) for o in escalation.options],
            recommended=escalation.recommended_option,
        )
        
        # Await response
        response = await self.ui.await_escalation_response(escalation.id)
        
        # Process response
        return self._process_response(escalation, response)
    
    def _format_escalation(self, esc: Escalation) -> str:
        """Format escalation for display."""
        
        lines = [
            f"⚠️ **Guardrail Triggered**: {esc.blocking_rule}",
            f"",
            f"**Goal**: {esc.goal_id}",
            f"**Reason**: {esc.reason.value}",
            f"",
            f"{esc.details}",
        ]
        
        if esc.action_classification:
            ac = esc.action_classification
            lines.extend([
                f"",
                f"**Action**: {ac.action_type}",
                f"**Risk Level**: {ac.risk.value.upper()}",
                f"**Path**: {ac.path or 'N/A'}",
            ])
        
        if esc.scope_check and not esc.scope_check.passed:
            lines.extend([
                f"",
                f"**Scope Issue**: {esc.scope_check.reason}",
            ])
        
        if esc.verification_result:
            vr = esc.verification_result
            lines.extend([
                f"",
                f"**Verification Confidence**: {vr.confidence:.0%}",
                f"**Issues Found**: {len(vr.issues)}",
            ])
        
        return "\n".join(lines)
```

### Escalation UI Examples

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⚠️  GUARDRAIL: dangerous_action                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Goal: Update database schema for users table                                │
│  Reason: DANGEROUS_ACTION                                                    │
│                                                                              │
│  This goal involves modifying database schema (migrations/).                 │
│  Schema changes can cause data loss if not carefully reviewed.               │
│                                                                              │
│  Action: db_schema                                                           │
│  Risk Level: DANGEROUS                                                       │
│  Path: migrations/0023_add_user_roles.py                                     │
│                                                                              │
│  ──────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Options:                                                                    │
│                                                                              │
│  [1] Approve (recommended)                                                   │
│      Review the migration and proceed if it looks correct.                   │
│                                                                              │
│  [2] Skip this goal                                                          │
│      Skip this goal and continue with other work.                            │
│                                                                              │
│  [3] Abort session                                                           │
│      Stop autonomous mode entirely.                                          │
│                                                                              │
│  [4] Show diff                                                               │
│      Display the planned changes before deciding.                            │
│                                                                              │
│  ⚠️  Note: Database migrations can cause irreversible data changes.          │
│      Please review carefully before approving.                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

> Enter option [1-4]: 
```

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ℹ️  GUARDRAIL: scope_exceeded                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Goal: Add type hints to all modules                                         │
│  Reason: SCOPE_EXCEEDED                                                      │
│                                                                              │
│  This goal would modify 47 files, exceeding the limit of 10 files           │
│  per goal.                                                                   │
│                                                                              │
│  Scope Issue: Goal touches 47 files (limit: 10)                             │
│                                                                              │
│  ──────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Options:                                                                    │
│                                                                              │
│  [1] Split goal (recommended)                                                │
│      Break into smaller goals (~5 files each).                               │
│                                                                              │
│  [2] Approve anyway                                                          │
│      Proceed despite exceeding limit (requires confirmation).                │
│                                                                              │
│  [3] Skip this goal                                                          │
│      Skip and continue with other work.                                      │
│                                                                              │
│  [4] Relax limit for session                                                 │
│      Temporarily increase file limit for this session.                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Recovery System

Git-based recovery ensures every change is revertible.

### Relationship to Existing Rollback Systems

Sunwell already has rollback in `mirror/proposals.py` for individual proposals:

```python
# Existing: Proposal-scoped rollback (mirror/proposals.py)
proposal = proposal_manager.apply_proposal(proposal_id, rollback_data)
rollback_data = proposal_manager.rollback_proposal(proposal_id)  # Single proposal
```

**Key differences from guardrail recovery**:

| Aspect | Proposal Rollback | Guardrail Recovery |
|--------|-------------------|-------------------|
| Scope | Single proposal | Entire session (multiple goals) |
| Trigger | User request | Guardrail violation or user abort |
| Mechanism | Stored rollback data | Git commits/tags |
| Granularity | Per-proposal | Per-goal + full session |
| Use case | Interactive editing | Autonomous execution |

**Integration approach**:
- Guardrail recovery **complements** proposal rollback, doesn't replace it
- Interactive mode continues using proposal rollback
- Autonomous mode uses git-based session recovery
- Both can coexist — git recovery doesn't interfere with proposal state

```python
class RecoveryManager:
    """Manage recovery points and rollbacks.
    
    Strategy:
    1. Commit before each goal (checkpoint)
    2. Tag session start point
    3. On failure/abort, offer revert options
    """
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.session_tag: str | None = None
        self.goal_commits: list[str] = []
    
    async def start_session(self) -> SessionStart:
        """Mark session start for potential rollback."""
        
        # Ensure clean state
        if await self._has_uncommitted_changes():
            raise GuardrailError(
                "Cannot start autonomous session with uncommitted changes. "
                "Please commit or stash your changes first."
            )
        
        # Create session tag
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_tag = f"sunwell-session-{session_id}"
        
        await self._run_git(["tag", self.session_tag])
        
        return SessionStart(
            session_id=session_id,
            tag=self.session_tag,
            start_commit=await self._get_head(),
        )
    
    async def checkpoint_goal(self, goal: Goal, changes: list[FileChange]) -> str:
        """Create checkpoint commit after goal completion."""
        
        # Stage changes
        for change in changes:
            await self._run_git(["add", str(change.path)])
        
        # Commit with metadata
        message = f"[sunwell] {goal.title}\n\nGoal ID: {goal.id}\nCategory: {goal.category}"
        await self._run_git(["commit", "-m", message])
        
        commit_hash = await self._get_head()
        self.goal_commits.append(commit_hash)
        
        return commit_hash
    
    async def rollback_goal(self, goal_id: str) -> RollbackResult:
        """Rollback a specific goal's changes."""
        
        # Find the commit for this goal
        commit_idx = self._find_goal_commit(goal_id)
        if commit_idx is None:
            return RollbackResult(success=False, reason="Goal commit not found")
        
        # Revert the commit
        commit = self.goal_commits[commit_idx]
        await self._run_git(["revert", "--no-commit", commit])
        await self._run_git(["commit", "-m", f"[sunwell] Revert: {goal_id}"])
        
        return RollbackResult(success=True, reverted_commit=commit)
    
    async def rollback_session(self) -> RollbackResult:
        """Rollback entire session to starting point."""
        
        if not self.session_tag:
            return RollbackResult(success=False, reason="No session tag found")
        
        # Hard reset to session start
        await self._run_git(["reset", "--hard", self.session_tag])
        
        # Clean untracked files
        await self._run_git(["clean", "-fd"])
        
        return RollbackResult(
            success=True,
            reverted_commit=self.session_tag,
            goals_reverted=len(self.goal_commits),
        )
    
    async def show_recovery_options(self) -> list[RecoveryOption]:
        """Show available recovery options."""
        
        options = []
        
        # Per-goal reverts
        for i, commit in enumerate(reversed(self.goal_commits)):
            goal_id = await self._get_goal_id_from_commit(commit)
            options.append(RecoveryOption(
                id=f"revert_{i}",
                description=f"Revert goal: {goal_id}",
                action="revert_goal",
                target=goal_id,
            ))
        
        # Full session rollback
        if self.session_tag:
            options.append(RecoveryOption(
                id="rollback_session",
                description=f"Rollback entire session ({len(self.goal_commits)} goals)",
                action="rollback_session",
                target=self.session_tag,
            ))
        
        return options
```

---

## Configuration

```yaml
# sunwell.yaml or pyproject.toml [tool.sunwell.guardrails]

guardrails:
  # Trust level: conservative | guarded | supervised | full
  trust_level: guarded
  
  # Scope limits
  scope:
    max_files_per_goal: 10
    max_lines_per_goal: 500
    max_duration_per_goal_minutes: 30
    max_goals_per_session: 20
    max_files_per_session: 50
    max_lines_per_session: 2000
    max_duration_per_session_hours: 8
  
  # Verification thresholds
  verification:
    safe_threshold: 0.70
    moderate_threshold: 0.85
    require_tests_for_source: true
  
  # Trust zones (extend defaults)
  trust_zones:
    - pattern: "src/utils/**"
      risk_override: safe
      reason: "Utility code is low-risk"
    
    - pattern: "src/billing/**"
      risk_override: dangerous
      allowed_in_autonomous: false
      reason: "Billing code is business-critical"
  
  # Auto-approve categories (for guarded mode)
  auto_approve:
    categories:
      - fix
      - test
      - document
    complexity:
      - trivial
      - simple
  
  # Recovery
  recovery:
    require_clean_start: true
    commit_after_each_goal: true
    auto_tag_sessions: true
```

---

## CLI Integration

```bash
# Start autonomous mode with guardrails (default: guarded)
sunwell backlog --autonomous

# Start with specific trust level
sunwell backlog --autonomous --trust guarded
sunwell backlog --autonomous --trust supervised
sunwell backlog --autonomous --trust conservative  # propose-only

# Override scope limits for session
sunwell backlog --autonomous --max-files 20 --max-lines 1000

# Dry run to see what would happen
sunwell backlog --autonomous --dry-run

# Show current guardrail configuration
sunwell guardrails show

# Validate goals against guardrails without executing
sunwell guardrails check

# Review session history and recovery options
sunwell guardrails history
sunwell guardrails rollback <session-id>
sunwell guardrails rollback-goal <goal-id>
```

### Example Session

```
$ sunwell backlog --autonomous

🛡️ Guardrails: GUARDED mode
   Trust zones: 3 safe, 2 protected, 2 forbidden
   Scope limits: 10 files/goal, 500 lines/goal, 20 goals/session
   Verification: 70% (safe), 85% (moderate)

📋 Backlog: 7 goals found
   ✅ 5 auto-approvable (safe + simple)
   ⚠️ 2 require approval (complex or protected paths)

🏷️ Session tagged: sunwell-session-20260119_143022

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1/7] Fix failing test in auth_test.py
      Category: fix | Complexity: simple | Risk: SAFE
      Files: 1 | Lines: ~15

      ✅ Verification: 94% confidence
      ✅ Auto-approved (safe + high confidence)
      
      Executing... ████████████████████████████████ 100%
      ✅ Committed: a3f2b1c

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[2/7] Add docstrings to models/user.py
      Category: document | Complexity: trivial | Risk: SAFE
      Files: 1 | Lines: ~30

      ✅ Verification: 89% confidence
      ✅ Auto-approved (safe + high confidence)
      
      Executing... ████████████████████████████████ 100%
      ✅ Committed: b4e3c2d

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[3/7] Update API authentication flow
      Category: fix | Complexity: moderate | Risk: DANGEROUS
      Files: 3 | Lines: ~120
      ⚠️ Path: src/auth/oauth.py (protected zone)

      ⚠️ ESCALATION: Protected path requires approval

      This goal modifies authentication code (src/auth/).
      Auth changes are marked DANGEROUS by default.

      Options:
        [1] Approve and continue
        [2] Skip this goal
        [3] Show planned changes
        [4] Abort session

      > 1

      Executing... ████████████████████████████████ 100%
      ✅ Committed: c5f4d3e

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

... (4 more goals)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Session Complete

   Goals: 7/7 completed
   Files: 12 modified
   Lines: +347 / -89
   Duration: 4m 23s
   Commits: 7

   ✅ All changes committed and recoverable
   
   To rollback entire session:
     sunwell guardrails rollback sunwell-session-20260119_143022
```

---

## Integration with Existing Systems

### With RFC-042 (Adaptive Agent)

Guardrails wrap agent execution:

```python
async def execute_with_guardrails(
    agent: AdaptiveAgent,
    goal: Goal,
    guardrails: GuardrailSystem,
) -> ExecutionResult:
    """Execute goal with guardrail protection."""
    
    # 1. Pre-check: Classify actions
    planned_actions = await agent.plan(goal)
    classifications = guardrails.classify_all(planned_actions)
    
    # 2. Check for forbidden actions
    forbidden = [c for c in classifications if c.risk == ActionRisk.FORBIDDEN]
    if forbidden:
        raise GuardrailError(f"Forbidden action: {forbidden[0].reason}")
    
    # 3. Check scope limits
    scope_check = guardrails.scope_tracker.check_goal(goal, planned_actions)
    if not scope_check.passed:
        return await guardrails.escalate(
            EscalationReason.SCOPE_EXCEEDED,
            goal=goal,
            scope_check=scope_check,
        )
    
    # 4. Execute with checkpoints
    result = await agent.execute(goal)
    
    # 5. Verify result
    if guardrails.config.verification_required:
        verification = await guardrails.verify(result)
        if not verification.passed:
            return await guardrails.escalate(
                EscalationReason.VERIFICATION_FAILED,
                goal=goal,
                verification=verification,
            )
    
    # 6. Checkpoint
    await guardrails.recovery.checkpoint_goal(goal, result.changes)
    
    return result
```

### With RFC-046 (Autonomous Backlog)

Guardrails determine auto-approval:

```python
# In AutonomousLoop.run()

async def run(self, mode: Literal["propose", "supervised", "autonomous"]):
    for goal in backlog:
        if mode == "autonomous":
            # Use guardrails for approval decision
            can_auto = await self.guardrails.can_auto_approve(goal)
            
            if can_auto:
                result = await self.execute_with_guardrails(goal)
            else:
                # Escalate for approval
                resolution = await self.guardrails.escalate(goal)
                if resolution.action == "approve":
                    result = await self.execute_with_guardrails(goal)
                elif resolution.action == "skip":
                    continue
                elif resolution.action == "abort":
                    break
```

### With RFC-047 (Deep Verification)

Confidence feeds into auto-approval:

```python
async def can_auto_approve(self, goal: Goal) -> bool:
    """Determine if goal can be auto-approved."""
    
    # 1. Check action classification
    classification = self.classifier.classify_goal(goal)
    if classification.risk in (ActionRisk.FORBIDDEN, ActionRisk.DANGEROUS):
        return False
    
    # 2. Check scope limits
    scope = self.scope_tracker.check_goal(goal, goal.planned_changes)
    if not scope.passed:
        return False
    
    # 3. Check verification confidence (RFC-047)
    if self.config.require_verification:
        verification = await self.verifier.verify(goal.artifact, goal.content)
        threshold = self._get_threshold(classification.risk)
        if verification.confidence < threshold:
            return False
    
    # 4. Check category/complexity policy
    if goal.category not in self.config.auto_approve_categories:
        return False
    if goal.estimated_complexity not in self.config.auto_approve_complexity:
        return False
    
    return True
```

---

## Risks and Mitigations

### Risk 1: Over-Restriction

**Problem**: Guardrails too strict, everything escalates.

**Mitigation**:
- Conservative defaults with easy relaxation
- Trust level tiers (conservative → guarded → supervised)
- User can whitelist specific paths/patterns
- Learning from approvals (future: auto-adjust thresholds)

### Risk 2: Under-Restriction

**Problem**: Guardrails miss dangerous actions.

**Mitigation**:
- Hard-coded FORBIDDEN patterns (cannot be overridden)
- Default to MODERATE for unknown actions
- Scope limits cap damage even for misclassified actions
- Git recovery ensures revertibility

### Risk 3: Classification Errors

**Problem**: Action wrongly classified as safe.

**Mitigation**:
- Multi-layer defense (action + scope + verification)
- Path-based trust zones override action classification
- Verification confidence adds second check
- Scope limits bound blast radius

### Risk 4: Recovery Failures

**Problem**: Git commits fail or corrupt state.

**Mitigation**:
- Require clean state before session
- Validate git operations
- Keep session tag for full rollback
- Test recovery paths in CI

### Risk 5: User Fatigue

**Problem**: Too many escalations, user approves blindly.

**Mitigation**:
- Batch similar escalations
- "Approve all of type X" option
- Smart defaults reduce escalation frequency
- Track escalation patterns, suggest config changes

---

## Testing Strategy

### Unit Tests

```python
# tests/test_guardrails/test_classifier.py
class TestActionClassifier:
    """Test action classification logic."""
    
    def test_forbidden_patterns_cannot_be_overridden(self):
        """Ensure .env files are always FORBIDDEN."""
        classifier = ActionClassifier(GuardrailConfig(trust_level=TrustLevel.FULL))
        result = classifier.classify(Action(path=".env.production"))
        assert result.risk == ActionRisk.FORBIDDEN
    
    def test_safe_zone_override(self):
        """Tests in tests/ are SAFE."""
        classifier = ActionClassifier(GuardrailConfig())
        result = classifier.classify(Action(path="tests/test_foo.py", action_type="file_write"))
        assert result.risk == ActionRisk.SAFE
    
    def test_dangerous_paths_escalate(self):
        """Auth paths require approval."""
        classifier = ActionClassifier(GuardrailConfig())
        result = classifier.classify(Action(path="src/auth/oauth.py", action_type="file_write"))
        assert result.risk == ActionRisk.DANGEROUS
        assert result.escalation_required is True


# tests/test_guardrails/test_scope.py
class TestScopeTracker:
    """Test scope limit enforcement."""
    
    def test_per_goal_file_limit(self):
        """Reject goals exceeding file limit."""
        tracker = ScopeTracker(ScopeLimits(max_files_per_goal=5))
        changes = [FileChange(path=f"file{i}.py") for i in range(10)]
        result = tracker.check_goal(goal, changes)
        assert not result.passed
        assert "10 files" in result.reason
    
    def test_session_accumulation(self):
        """Track cumulative session usage."""
        tracker = ScopeTracker(ScopeLimits(max_files_per_session=20))
        # Complete 3 goals touching 5 files each
        for _ in range(3):
            tracker.record_goal_completion([FileChange(path=f"f{i}.py") for i in range(5)])
        # 4th goal should fail (15 + 10 > 20)
        result = tracker.check_goal(goal, [FileChange(path=f"f{i}.py") for i in range(10)])
        assert not result.passed


# tests/test_guardrails/test_recovery.py
class TestRecoveryManager:
    """Test git-based recovery."""
    
    async def test_session_tag_created(self, tmp_git_repo):
        """Session start creates tag."""
        manager = RecoveryManager(tmp_git_repo)
        session = await manager.start_session()
        assert session.tag.startswith("sunwell-session-")
        # Verify tag exists in git
        tags = await manager._run_git(["tag", "-l", session.tag])
        assert session.tag in tags
    
    async def test_goal_checkpoint_creates_commit(self, tmp_git_repo):
        """Each goal creates a commit."""
        manager = RecoveryManager(tmp_git_repo)
        await manager.start_session()
        commit = await manager.checkpoint_goal(
            Goal(id="g1", title="Test goal"),
            [FileChange(path="test.py", lines_added=10)]
        )
        assert len(commit) == 40  # SHA length
    
    async def test_session_rollback_restores_state(self, tmp_git_repo):
        """Full session rollback works."""
        manager = RecoveryManager(tmp_git_repo)
        await manager.start_session()
        # Make changes
        (tmp_git_repo / "new_file.py").write_text("content")
        await manager.checkpoint_goal(goal, [FileChange(path="new_file.py")])
        # Rollback
        result = await manager.rollback_session()
        assert result.success
        assert not (tmp_git_repo / "new_file.py").exists()
```

### Integration Tests

```python
# tests/test_guardrails/test_integration.py
class TestGuardrailIntegration:
    """End-to-end guardrail tests with autonomous loop."""
    
    async def test_safe_goal_auto_approves(self, test_project):
        """SAFE goals with high confidence auto-approve."""
        guardrails = GuardrailSystem(GuardrailConfig(trust_level=TrustLevel.GUARDED))
        goal = Goal(
            id="test-1",
            title="Add test for utils",
            category="test",
            estimated_complexity="simple",
            planned_changes=[FileChange(path="tests/test_utils.py", lines_added=20)],
        )
        
        can_auto = await guardrails.can_auto_approve(goal)
        assert can_auto is True
    
    async def test_dangerous_goal_escalates(self, test_project):
        """DANGEROUS goals always escalate."""
        guardrails = GuardrailSystem(GuardrailConfig(trust_level=TrustLevel.GUARDED))
        goal = Goal(
            id="auth-1",
            title="Update OAuth flow",
            category="fix",
            estimated_complexity="simple",
            planned_changes=[FileChange(path="src/auth/oauth.py", lines_added=50)],
        )
        
        can_auto = await guardrails.can_auto_approve(goal)
        assert can_auto is False
    
    async def test_scope_exceeded_escalates(self, test_project):
        """Goals exceeding scope limits escalate."""
        guardrails = GuardrailSystem(GuardrailConfig(
            scope=ScopeLimits(max_files_per_goal=5)
        ))
        goal = Goal(
            id="bulk-1",
            title="Add type hints everywhere",
            category="fix",
            estimated_complexity="simple",
            planned_changes=[FileChange(path=f"src/mod{i}.py") for i in range(20)],
        )
        
        can_auto = await guardrails.can_auto_approve(goal)
        assert can_auto is False


class TestEscalationFlow:
    """Test escalation handling."""
    
    async def test_escalation_offers_correct_options(self, mock_ui):
        """Escalation presents appropriate options."""
        handler = EscalationHandler(mock_ui)
        escalation = Escalation(
            id="esc-1",
            goal_id="g-1",
            reason=EscalationReason.DANGEROUS_ACTION,
            details="Modifies auth code",
            blocking_rule="dangerous_pattern",
            options=(
                EscalationOption(id="approve", label="Approve", action="approve"),
                EscalationOption(id="skip", label="Skip", action="skip"),
            ),
            recommended_option="approve",
        )
        
        await handler.escalate(escalation)
        
        # Verify UI was called correctly
        mock_ui.show_escalation.assert_called_once()
        call_args = mock_ui.show_escalation.call_args
        assert call_args.kwargs["severity"] == "warning"
        assert len(call_args.kwargs["options"]) == 2
```

### Test Coverage Targets

| Component | Target | Notes |
|-----------|--------|-------|
| `ActionClassifier` | 95% | Critical for safety |
| `ScopeTracker` | 90% | Boundary conditions important |
| `RecoveryManager` | 85% | Git operations can be flaky |
| `EscalationHandler` | 80% | UI integration tested separately |
| `VerificationGate` | 90% | RFC-047 integration critical |

---

## Implementation Plan

### Phase 1: Action Classification (Week 1)

- [ ] `ActionClassifier` with taxonomy
- [ ] `ActionRisk` enum and classifications
- [ ] Pattern matching for file/shell operations
- [ ] Trust zone evaluation
- [ ] CLI: `sunwell guardrails classify <action>`

### Phase 2: Scope Limits (Week 2)

- [ ] `ScopeLimits` configuration
- [ ] `ScopeTracker` for session tracking
- [ ] Per-goal and per-session limit enforcement
- [ ] CLI: `sunwell guardrails check`

### Phase 3: Recovery System (Week 3)

- [ ] `RecoveryManager` with git operations
- [ ] Session tagging
- [ ] Goal checkpoints
- [ ] Rollback commands
- [ ] CLI: `sunwell guardrails rollback`

### Phase 4: Escalation System (Week 4)

- [ ] `Escalation` types
- [ ] `EscalationHandler` with UI
- [ ] Resolution processing
- [ ] Integration with autonomous loop

### Phase 5: Verification Integration (Week 5)

- [ ] Connect RFC-047 Deep Verification
- [ ] Confidence-based thresholds
- [ ] Verification gate in approval flow
- [ ] End-to-end testing

### Phase 6: Polish (Week 6)

- [ ] Configuration file support
- [ ] Trust level presets
- [ ] Session history and audit log
- [ ] Documentation

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| False escalations | < 20% | Safe actions escalated unnecessarily |
| Missed dangerous | 0% | Dangerous actions auto-approved |
| Recovery success | 100% | Rollbacks work correctly |
| User satisfaction | > 80% | Users accept guardrail decisions |
| Session completion | > 90% | Autonomous sessions complete without abort |

---

## Future Work

1. **Learning from approvals** — Adjust thresholds based on user decisions
2. **Team policies** — Shared guardrail configurations (RFC-052)
3. **External integration** — CI/CD guardrails (RFC-049)
4. **Sandbox execution** — Container isolation for dangerous actions
5. **Approval delegation** — Allow trusted paths to auto-approve higher risk

---

## Summary

Autonomy Guardrails enable safe unsupervised operation through:

| Layer | Purpose | Mechanism |
|-------|---------|-----------|
| **Action Classification** | Know what's risky | Taxonomy + trust zones |
| **Scope Limits** | Bound blast radius | Hard caps on changes |
| **Verification Gate** | Ensure correctness | RFC-047 confidence |
| **Recovery System** | Enable rollback | Git checkpoints |
| **Escalation System** | Human-in-the-loop | Clear options |

### The Trust Spectrum

```
CONSERVATIVE → GUARDED → SUPERVISED → FULL
    │              │           │         │
    │              │           │         └─ Only verified safe
    │              │           └─ Ask for dangerous
    │              └─ Auto-approve safe within limits
    └─ Propose only, never execute
```

### Integration Points

- **RFC-042**: Wraps agent execution with guardrail checks
- **RFC-046**: Determines which goals can auto-approve
- **RFC-047**: Confidence feeds into verification gate

**The result**: Sunwell that works while you sleep — but only on tasks it can't break.

---

## References

### RFCs

- RFC-042: Adaptive Agent — `src/sunwell/adaptive/`
- RFC-046: Autonomous Backlog — `src/sunwell/backlog/`
- RFC-047: Deep Verification — `src/sunwell/verification/` (to be created)

### Implementation Files (to be created)

```
src/sunwell/guardrails/
├── __init__.py
├── types.py           # ActionRisk, ActionClassification, Escalation, etc.
├── classifier.py      # ActionClassifier
├── scope.py           # ScopeLimits, ScopeTracker
├── trust.py           # TrustZone, TrustZoneEvaluator
├── recovery.py        # RecoveryManager
├── escalation.py      # EscalationHandler
├── verification.py    # VerificationGate (RFC-047 integration)
├── config.py          # GuardrailConfig loading
└── system.py          # GuardrailSystem orchestrator
```

### Related Existing Files

```
src/sunwell/backlog/
├── goals.py           # Goal.auto_approvable (enhance with guardrails)
└── loop.py            # AutonomousLoop (integrate guardrails)

src/sunwell/adaptive/
└── agent.py           # AdaptiveAgent (wrap with guardrails)
```

---

*Last updated: 2026-01-19*  
*Revision: Added design alternatives, threshold rationale, recovery system comparison, and testing strategy*
