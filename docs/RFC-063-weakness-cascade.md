# RFC-063: DAG-Powered Weakness Cascade — Smart Technical Debt Liquidation

**Status**: Draft  
**Created**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 88% 🟢  
**Depends on**: RFC-040 (Incremental Build), RFC-046 (Backlog), RFC-056 (Live DAG)
**Alternatives**: Evaluated 4 options; see "Alternatives Considered" section

---

## Summary

Use the DAG to identify weak parts of a codebase (low coverage, high complexity, staleness), compute the full cascade of dependents that would be impacted, and orchestrate the agent to regenerate everything atomically — fixing technical debt with guaranteed consistency.

**The insight**: The DAG gives us **blast radius prediction**. Before touching a weak module, we know exactly what else must be updated. This transforms refactoring from "hope nothing breaks" to "planned atomic regeneration."

**Key capabilities:**
- **Weakness detection** — Automated analysis of test coverage, complexity, lint errors, staleness
- **Cascade preview** — Show full impact graph before any changes
- **Contract extraction** — Extract interfaces before regeneration to guarantee compatibility
- **Wave-by-wave execution** — Approve each wave with confidence scoring and delta preview
- **Atomic regeneration** — Agent rebuilds weak node + all dependents in topological order
- **Verification** — Ensure no regressions after cascade completes

**The deeper insight**: This is **Make/Bazel for code semantics** — not just "rebuild if source changed" but "rebuild if *meaning* changed." The DAG tracks semantic dependencies, and the agent understands how to propagate changes. This generalizes to API evolution, migrations, and security fixes.

---

## Goals

1. **Identify weakness** — Automated detection of technical debt hotspots
2. **Predict impact** — Show exactly what would be affected before changes
3. **Atomic regeneration** — Fix weak code + all dependents in one operation
4. **No regressions** — Verification ensures cascade didn't break anything
5. **Full visibility** — Studio shows weakness scores and cascade previews

## Non-Goals

1. **Auto-fix everything** — Human approves cascade before execution
2. **Perfect metrics** — Some heuristics are approximate; that's acceptable
3. **Replace code review** — Agent proposes, human reviews
4. **Real-time analysis** — Weakness scan runs on-demand, not continuously

## Tool Requirements

Optional tools for enhanced weakness detection (graceful degradation if missing):

| Tool | Purpose | Install | Minimum Version |
|------|---------|---------|-----------------|
| `coverage` | Test coverage analysis | `pip install coverage` | 7.0+ |
| `radon` | Cyclomatic complexity | `pip install radon` | 6.0+ |
| `ruff` | Lint error detection | `pip install ruff` | 0.1+ |
| `mypy` | Type error detection | `pip install mypy` | 1.0+ |

Note: `ruff` and `mypy` are already Sunwell dependencies; `coverage` and `radon` are optional.

---

## Motivation

### The Technical Debt Problem

Every codebase accumulates weak spots:
- Files with 30% test coverage that 15 other files depend on
- Complex functions (cyclomatic complexity > 15) at the core of the system
- Stale code that hasn't been touched in a year but has high fan-out
- Modules with unresolved lint warnings that get copy-pasted

Traditional approaches fail:
- **Manual refactoring**: You fix one file, something else breaks, cycle repeats
- **Big-bang rewrite**: High risk, often abandoned halfway
- **Ignore it**: Debt compounds until the codebase is unmaintainable

### The DAG Advantage

We already track dependencies for incremental builds. The same graph tells us:

```
auth/session.py (weak: 30% coverage)
    ├── api/auth_handler.py (depends on session)
    │   ├── api/routes.py (depends on auth_handler)
    │   └── services/login.py (depends on auth_handler)
    ├── services/token_service.py (depends on session)
    │   └── api/refresh.py (depends on token_service)
    └── middleware/auth_middleware.py (depends on session)
        └── api/protected_routes.py (depends on auth_middleware)
```

If we regenerate `auth/session.py`, we **must** also update everything in that tree. The DAG makes this explicit and automatable.

### Alternatives Considered

**Option A: Manual Refactoring Assistance (Rejected)**
- Show weakness scores but let humans decide what to fix
- *Why rejected*: Humans can't track cascade impact across 50+ files; the DAG advantage is lost

**Option B: LLM-Based Weakness Detection (Rejected)**
- Use LLM to analyze code quality instead of static tools
- *Why rejected*: Non-deterministic, expensive, slower than `ruff`/`radon`; static tools are sufficient for measurable metrics

**Option C: Continuous Background Analysis (Deferred)**
- Analyze weaknesses on every file save
- *Why deferred*: Adds complexity; on-demand scanning is simpler and sufficient for v1

**Option D: Separate Analysis and Fix Phases (Rejected)**
- Two-step: first run analysis tool, then separately run fix tool
- *Why rejected*: Loses the atomic guarantee; cascade state could change between phases

**Chosen: Integrated DAG Cascade (This RFC)**
- Static tool detection → DAG cascade preview → atomic agent regeneration
- *Why chosen*: Leverages existing `find_invalidated()`, provides blast radius prediction, maintains atomicity

### The Cascade Regeneration Vision

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CASCADE REGENERATION FLOW                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ANALYZE              PREVIEW              EXECUTE                  │
│   ───────              ───────              ───────                  │
│                                                                      │
│   [Weakness Scan]      [Cascade Graph]      [Agent Regeneration]     │
│        │                    │                    │                   │
│        ▼                    ▼                    ▼                   │
│   • Test coverage      • Direct deps        Wave 1: Weak node       │
│   • Complexity         • Transitive deps    Wave 2: Direct deps     │
│   • Lint errors        • Total impact       Wave 3: Transitive      │
│   • Staleness          • Est. effort        Wave N: Verification    │
│   • Failure history    • Risk assessment                            │
│                                                                      │
│   HUMAN APPROVAL GATE ──────────────────────────────────────────────│
│   "This will regenerate 12 files. Proceed?"                         │
│                                                                      │
│   VERIFY               COMMIT               REPORT                   │
│   ──────               ──────               ──────                   │
│                                                                      │
│   • Run tests          • Atomic commit      • Before/after metrics  │
│   • Type check         • Or rollback        • Debt reduction score  │
│   • Lint clean                              • Coverage improvement   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### The Deeper Opportunity: Semantic Change Propagation

The weakness cascade is a specific instance of a more general capability: **semantic change propagation**. Traditional build systems (Make, Bazel) track file-level dependencies — "if X.c changed, recompile Y.o." But they can't reason about *what* changed semantically.

The DAG + agent combination enables:

| Use Case | Trigger | Cascade Effect |
|----------|---------|----------------|
| **Technical debt** | Low coverage, high complexity | Regenerate weak code + update dependents |
| **API evolution** | Interface signature change | Update all implementations + call sites |
| **Dependency upgrade** | Package version bump | Fix compatibility issues across codebase |
| **Security fix** | Vulnerable pattern detected | Replace pattern everywhere it appears |
| **Deprecation** | Function marked deprecated | Migrate all callers to new API |

The common pattern:
1. **Detect** — Something needs to change (weakness, breaking change, security issue)
2. **Compute cascade** — Use DAG to find everything affected
3. **Extract contracts** — Capture interfaces before touching anything
4. **Propagate change** — Agent updates each node preserving contracts
5. **Verify** — Tests prove nothing broke

This RFC focuses on the first use case (technical debt) but the infrastructure supports all of them.

---

## Detailed Design

### Part 1: Python Backend — Weakness Detection & Cascade Engine

#### 1.1 Weakness Signal Types

```python
# src/sunwell/weakness/types.py

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class WeaknessType(str, Enum):
    """Categories of code weakness."""
    
    LOW_COVERAGE = "low_coverage"          # < 50% test coverage
    HIGH_COMPLEXITY = "high_complexity"    # Cyclomatic complexity > 10
    LINT_ERRORS = "lint_errors"            # Unresolved linter issues  
    STALE_CODE = "stale_code"              # No commits in 6mo + high fan_out
    FAILURE_PRONE = "failure_prone"        # Failed in recent executions
    MISSING_TYPES = "missing_types"        # Any in mypy output
    BROKEN_CONTRACT = "broken_contract"    # Interface doesn't match impl


@dataclass(frozen=True, slots=True)
class WeaknessSignal:
    """A detected weakness in the codebase."""
    
    artifact_id: str
    file_path: Path
    weakness_type: WeaknessType
    severity: float  # 0.0 - 1.0
    evidence: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_critical(self) -> bool:
        """Severity > 0.8 is critical."""
        return self.severity > 0.8


@dataclass(frozen=True, slots=True)
class WeaknessScore:
    """Aggregated weakness score for an artifact."""
    
    artifact_id: str
    file_path: Path
    signals: tuple[WeaknessSignal, ...]
    fan_out: int  # How many depend on this
    depth: int    # Position in dependency chain
    
    @property
    def total_severity(self) -> float:
        """Weighted severity including impact multiplier."""
        base = sum(s.severity for s in self.signals) / max(len(self.signals), 1)
        # Higher fan_out = more impact if weak
        impact_multiplier = 1 + (self.fan_out * 0.05)
        return min(1.0, base * impact_multiplier)
    
    @property
    def cascade_risk(self) -> Literal["low", "medium", "high", "critical"]:
        """Risk level based on weakness + fan_out."""
        score = self.total_severity * (1 + self.fan_out / 10)
        if score > 2.0:
            return "critical"
        if score > 1.0:
            return "high"
        if score > 0.5:
            return "medium"
        return "low"


@dataclass(frozen=True, slots=True)
class ExtractedContract:
    """Interface contract extracted from code before regeneration.
    
    Captures the public API so regeneration can verify compatibility.
    """
    
    artifact_id: str
    file_path: Path
    
    # Public interface elements
    functions: tuple[str, ...]      # Function signatures
    classes: tuple[str, ...]        # Class definitions with public methods
    exports: tuple[str, ...]        # __all__ or equivalent
    type_signatures: tuple[str, ...]  # Key type annotations
    
    # Checksum for quick equality check
    interface_hash: str
    
    def is_compatible_with(self, other: ExtractedContract) -> bool:
        """Check if another contract is backward-compatible."""
        # All functions in self must exist in other (additions OK)
        # Signatures can be more permissive but not more restrictive
        return set(self.functions) <= set(other.functions)


@dataclass(frozen=True, slots=True)
class WaveConfidence:
    """Confidence score for a completed wave."""
    
    wave_num: int
    artifacts_completed: tuple[str, ...]
    
    # Scoring components
    tests_passed: bool
    types_clean: bool
    lint_clean: bool
    contracts_preserved: bool
    
    # Aggregate score 0.0-1.0
    confidence: float
    
    # Reasons for any deductions
    deductions: tuple[str, ...] = ()
    
    @classmethod
    def compute(
        cls,
        wave_num: int,
        artifacts: tuple[str, ...],
        test_result: bool,
        type_result: bool,
        lint_result: bool,
        contract_result: bool,
    ) -> WaveConfidence:
        """Compute confidence from verification results."""
        deductions = []
        score = 1.0
        
        if not test_result:
            score -= 0.4
            deductions.append("Tests failed")
        if not type_result:
            score -= 0.2
            deductions.append("Type errors introduced")
        if not lint_result:
            score -= 0.1
            deductions.append("Lint errors introduced")
        if not contract_result:
            score -= 0.3
            deductions.append("Contract compatibility broken")
        
        return cls(
            wave_num=wave_num,
            artifacts_completed=artifacts,
            tests_passed=test_result,
            types_clean=type_result,
            lint_clean=lint_result,
            contracts_preserved=contract_result,
            confidence=max(0.0, score),
            deductions=tuple(deductions),
        )
    
    @property
    def should_continue(self) -> bool:
        """Whether cascade should proceed to next wave."""
        return self.confidence >= 0.7  # Configurable threshold


@dataclass(frozen=True, slots=True)
class DeltaPreview:
    """Preview of changes the agent would make to a file."""
    
    artifact_id: str
    file_path: Path
    
    # Diff information
    additions: int
    deletions: int
    hunks: tuple[str, ...]  # Summary of each change hunk
    
    # Full unified diff (can be large)
    unified_diff: str | None = None
```

#### 1.2 Weakness Analyzer

```python
# src/sunwell/weakness/analyzer.py

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import json

from sunwell.naaru.artifacts import ArtifactGraph
from sunwell.weakness.types import WeaknessSignal, WeaknessScore, WeaknessType


@dataclass
class WeaknessAnalyzer:
    """Analyzes codebase for weak points using DAG structure."""
    
    graph: ArtifactGraph
    project_root: Path
    
    # Thresholds
    coverage_threshold: float = 0.5
    complexity_threshold: int = 10
    staleness_months: int = 6
    
    async def scan(self) -> list[WeaknessScore]:
        """Scan codebase for weaknesses, returning scored artifacts."""
        # Run analysis tools in parallel
        coverage_map = await self._analyze_coverage()
        complexity_map = await self._analyze_complexity()
        lint_map = await self._analyze_lint()
        staleness_map = await self._analyze_staleness()
        type_errors = await self._analyze_types()
        
        scores = []
        for artifact_id in self.graph:
            artifact = self.graph[artifact_id]
            
            # Skip artifacts without output files (e.g., config-only, virtual)
            # These can still be dependencies but aren't directly analyzable
            if not artifact.produces_file:
                continue
            
            # Skip non-Python files for now (extend later for JS/TS)
            file_path = Path(artifact.produces_file)
            if file_path.suffix not in (".py", ".pyi"):
                continue
            signals = []
            
            # Check coverage
            if artifact_id in coverage_map:
                cov = coverage_map[artifact_id]
                if cov < self.coverage_threshold:
                    signals.append(WeaknessSignal(
                        artifact_id=artifact_id,
                        file_path=file_path,
                        weakness_type=WeaknessType.LOW_COVERAGE,
                        severity=(self.coverage_threshold - cov) / self.coverage_threshold,
                        evidence={"coverage": cov, "threshold": self.coverage_threshold},
                    ))
            
            # Check complexity
            if artifact_id in complexity_map:
                complexity = complexity_map[artifact_id]
                if complexity > self.complexity_threshold:
                    signals.append(WeaknessSignal(
                        artifact_id=artifact_id,
                        file_path=file_path,
                        weakness_type=WeaknessType.HIGH_COMPLEXITY,
                        severity=min(1.0, (complexity - self.complexity_threshold) / 10),
                        evidence={"complexity": complexity, "threshold": self.complexity_threshold},
                    ))
            
            # Check lint errors
            if artifact_id in lint_map and lint_map[artifact_id] > 0:
                signals.append(WeaknessSignal(
                    artifact_id=artifact_id,
                    file_path=file_path,
                    weakness_type=WeaknessType.LINT_ERRORS,
                    severity=min(1.0, lint_map[artifact_id] / 10),
                    evidence={"error_count": lint_map[artifact_id]},
                ))
            
            # Check staleness (old + low coverage + high fan_out = risky)
            # Note: Stable code isn't necessarily weak — require all three signals
            if artifact_id in staleness_map:
                months_stale = staleness_map[artifact_id]
                fan_out = self.graph.fan_out(artifact_id)
                coverage = coverage_map.get(artifact_id, 1.0)  # Assume covered if unknown
                is_stale = months_stale > self.staleness_months
                is_low_coverage = coverage < self.coverage_threshold
                is_high_fanout = fan_out > 3
                if is_stale and is_low_coverage and is_high_fanout:
                    signals.append(WeaknessSignal(
                        artifact_id=artifact_id,
                        file_path=file_path,
                        weakness_type=WeaknessType.STALE_CODE,
                        severity=min(1.0, (months_stale / 12) * (fan_out / 10)),
                        evidence={
                            "months_stale": months_stale,
                            "fan_out": fan_out,
                            "coverage": coverage,
                        },
                    ))
            
            # Check type errors
            if artifact_id in type_errors:
                signals.append(WeaknessSignal(
                    artifact_id=artifact_id,
                    file_path=file_path,
                    weakness_type=WeaknessType.MISSING_TYPES,
                    severity=min(1.0, type_errors[artifact_id] / 5),
                    evidence={"type_errors": type_errors[artifact_id]},
                ))
            
            if signals:
                scores.append(WeaknessScore(
                    artifact_id=artifact_id,
                    file_path=file_path,
                    signals=tuple(signals),
                    fan_out=self.graph.fan_out(artifact_id),
                    depth=self.graph.depth(artifact_id),
                ))
        
        # Sort by total severity (highest first)
        return sorted(scores, key=lambda s: s.total_severity, reverse=True)
    
    async def _analyze_coverage(self) -> dict[str, float]:
        """Get test coverage per file."""
        try:
            result = subprocess.run(
                ["coverage", "json", "-o", "-"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    self._file_to_artifact(f): info["summary"]["percent_covered"] / 100
                    for f, info in data.get("files", {}).items()
                }
        except Exception:
            pass
        return {}
    
    async def _analyze_complexity(self) -> dict[str, int]:
        """Get cyclomatic complexity per file."""
        try:
            result = subprocess.run(
                ["radon", "cc", "-j", str(self.project_root / "src")],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                complexity_map = {}
                for file_path, funcs in data.items():
                    max_complexity = max((f["complexity"] for f in funcs), default=0)
                    complexity_map[self._file_to_artifact(file_path)] = max_complexity
                return complexity_map
        except Exception:
            pass
        return {}
    
    async def _analyze_lint(self) -> dict[str, int]:
        """Get lint error count per file."""
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", str(self.project_root / "src")],
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout) if result.stdout else []
            error_counts: dict[str, int] = {}
            for error in data:
                file_path = error.get("filename", "")
                artifact_id = self._file_to_artifact(file_path)
                error_counts[artifact_id] = error_counts.get(artifact_id, 0) + 1
            return error_counts
        except Exception:
            pass
        return {}
    
    async def _analyze_staleness(self) -> dict[str, int]:
        """Get months since last commit per file."""
        # Uses git log to determine file age
        # Implementation detail: parse git log --format=%at for each file
        return {}  # TODO: implement
    
    async def _analyze_types(self) -> dict[str, int]:
        """Get type error count per file from mypy.
        
        Uses standard mypy output format (file:line: error: message).
        """
        try:
            result = subprocess.run(
                [
                    "mypy",
                    "--no-error-summary",
                    "--show-error-codes",
                    str(self.project_root / "src"),
                ],
                capture_output=True,
                text=True,
            )
            # Parse mypy output: "path/file.py:10: error: Message [code]"
            error_counts: dict[str, int] = {}
            for line in result.stdout.splitlines():
                if ": error:" in line:
                    file_path = line.split(":")[0]
                    artifact_id = self._file_to_artifact(file_path)
                    error_counts[artifact_id] = error_counts.get(artifact_id, 0) + 1
            return error_counts
        except Exception:
            pass
        return {}
    
    def _file_to_artifact(self, file_path: str) -> str:
        """Convert file path to artifact ID."""
        # Normalize path relative to project root
        try:
            rel = Path(file_path).relative_to(self.project_root)
            return str(rel)
        except ValueError:
            return file_path
```

#### 1.3 Cascade Engine

```python
# src/sunwell/weakness/cascade.py

from dataclasses import dataclass, field
from typing import Any

from sunwell.naaru.artifacts import ArtifactGraph
from sunwell.naaru.incremental import find_invalidated
from sunwell.weakness.types import WeaknessScore


@dataclass(frozen=True, slots=True)
class CascadePreview:
    """Preview of what a cascade regeneration would affect."""
    
    weak_node: str
    weakness_score: WeaknessScore
    direct_dependents: frozenset[str]
    transitive_dependents: frozenset[str]
    total_impacted: int
    estimated_effort: str  # small, medium, large, epic
    files_touched: tuple[str, ...]
    waves: tuple[tuple[str, ...], ...]  # Topological order
    risk_assessment: str
    
    # NEW: Contract and delta information
    extracted_contracts: dict[str, ExtractedContract] = field(default_factory=dict)
    delta_previews: dict[str, DeltaPreview] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "weak_node": self.weak_node,
            "weakness_type": [s.weakness_type.value for s in self.weakness_score.signals],
            "severity": self.weakness_score.total_severity,
            "cascade_risk": self.weakness_score.cascade_risk,
            "direct_dependents": list(self.direct_dependents),
            "transitive_dependents": list(self.transitive_dependents),
            "total_impacted": self.total_impacted,
            "estimated_effort": self.estimated_effort,
            "files_touched": list(self.files_touched),
            "waves": [list(w) for w in self.waves],
            "risk_assessment": self.risk_assessment,
            "has_contracts": len(self.extracted_contracts) > 0,
            "has_deltas": len(self.delta_previews) > 0,
        }


@dataclass
class CascadeExecution:
    """State of an in-progress cascade execution with wave-by-wave approval."""
    
    preview: CascadePreview
    current_wave: int = 0
    wave_confidences: list[WaveConfidence] = field(default_factory=list)
    
    # Execution mode
    auto_approve: bool = False  # If True, continue automatically if confidence > threshold
    confidence_threshold: float = 0.7
    
    # Escalation: if N consecutive waves have low confidence, escalate to human review
    max_consecutive_low_confidence: int = 2
    consecutive_low_confidence_count: int = 0
    escalated_to_human: bool = False
    
    # State
    paused_for_approval: bool = False
    completed: bool = False
    aborted: bool = False
    abort_reason: str | None = None
    
    @property
    def overall_confidence(self) -> float:
        """Average confidence across completed waves."""
        if not self.wave_confidences:
            return 1.0
        return sum(w.confidence for w in self.wave_confidences) / len(self.wave_confidences)
    
    def approve_wave(self) -> None:
        """Approve current wave and proceed to next."""
        self.paused_for_approval = False
    
    def abort(self, reason: str) -> None:
        """Abort cascade execution."""
        self.aborted = True
        self.abort_reason = reason
    
    def record_wave_completion(self, confidence: WaveConfidence) -> None:
        """Record completion of a wave and determine next action."""
        self.wave_confidences.append(confidence)
        
        # Track consecutive low-confidence waves for escalation
        if confidence.confidence < self.confidence_threshold:
            self.consecutive_low_confidence_count += 1
            
            # Escalate to human review if too many consecutive low-confidence waves
            if self.consecutive_low_confidence_count >= self.max_consecutive_low_confidence:
                self.escalated_to_human = True
                self.paused_for_approval = True
                # Force manual review even in auto mode
                self.auto_approve = False
            elif self.auto_approve:
                # Auto mode but confidence too low - pause for human review
                self.paused_for_approval = True
            else:
                self.paused_for_approval = True
        else:
            # Reset counter on successful wave
            self.consecutive_low_confidence_count = 0
            if not self.auto_approve:
                # Manual mode - always pause for approval
                self.paused_for_approval = True
        
        # Check if we're done
        if self.current_wave >= len(self.preview.waves) - 1:
            self.completed = True


@dataclass
class CascadeEngine:
    """Computes and executes cascade regenerations."""
    
    graph: ArtifactGraph
    max_cascade_depth: int = 5
    max_cascade_size: int = 50
    
    def preview(self, weakness: WeaknessScore) -> CascadePreview:
        """Preview what regenerating a weak node would affect."""
        weak_id = weakness.artifact_id
        
        # Get direct dependents
        direct = self.graph.get_dependents(weak_id)
        
        # Get full cascade (transitive)
        all_impacted = find_invalidated(self.graph, {weak_id})
        all_impacted.discard(weak_id)  # Don't count the weak node itself
        transitive = all_impacted - direct
        
        # Compute topological order (waves)
        waves = self._compute_waves(weak_id, all_impacted)
        
        # Gather file paths
        files = [weak_id]
        for aid in all_impacted:
            if aid in self.graph:
                artifact = self.graph[aid]
                if artifact.produces_file:
                    files.append(artifact.produces_file)
        
        # Estimate effort
        total = len(all_impacted) + 1
        if total <= 3:
            effort = "small"
        elif total <= 10:
            effort = "medium"
        elif total <= 25:
            effort = "large"
        else:
            effort = "epic"
        
        # Risk assessment
        risk = self._assess_risk(weakness, all_impacted)
        
        return CascadePreview(
            weak_node=weak_id,
            weakness_score=weakness,
            direct_dependents=frozenset(direct),
            transitive_dependents=frozenset(transitive),
            total_impacted=total,
            estimated_effort=effort,
            files_touched=tuple(files),
            waves=waves,
            risk_assessment=risk,
        )
    
    def _compute_waves(
        self,
        weak_id: str,
        impacted: set[str],
    ) -> tuple[tuple[str, ...], ...]:
        """Compute execution waves in topological order."""
        waves = []
        remaining = impacted | {weak_id}
        completed: set[str] = set()
        
        # Wave 0: the weak node itself
        waves.append((weak_id,))
        completed.add(weak_id)
        remaining.discard(weak_id)
        
        # Subsequent waves: nodes whose deps are all completed
        while remaining:
            wave = []
            for aid in remaining:
                if aid in self.graph:
                    artifact = self.graph[aid]
                    deps_in_cascade = set(artifact.requires) & (impacted | {weak_id})
                    if deps_in_cascade <= completed:
                        wave.append(aid)
            
            if not wave:
                # Circular dependency or unreachable - add remaining
                waves.append(tuple(remaining))
                break
            
            waves.append(tuple(wave))
            completed.update(wave)
            remaining -= set(wave)
        
        return tuple(waves)
    
    def _assess_risk(
        self,
        weakness: WeaknessScore,
        impacted: set[str],
    ) -> str:
        """Generate human-readable risk assessment."""
        risk_factors = []
        
        if len(impacted) > 20:
            risk_factors.append(f"Large cascade ({len(impacted)} files)")
        
        if weakness.fan_out > 10:
            risk_factors.append(f"High fan-out ({weakness.fan_out} dependents)")
        
        critical_signals = [s for s in weakness.signals if s.is_critical]
        if critical_signals:
            types = ", ".join(s.weakness_type.value for s in critical_signals)
            risk_factors.append(f"Critical weaknesses: {types}")
        
        if not risk_factors:
            return "Low risk: Small, isolated change"
        
        return " | ".join(risk_factors)
    
    def compute_regeneration_tasks(
        self,
        preview: CascadePreview,
    ) -> list[dict[str, Any]]:
        """Convert preview into executable task list for agent."""
        tasks = []
        
        for wave_num, wave in enumerate(preview.waves):
            for artifact_id in wave:
                task = {
                    "id": f"cascade-{artifact_id}",
                    "description": self._generate_task_description(
                        artifact_id,
                        wave_num,
                        preview,
                    ),
                    "mode": "modify" if wave_num > 0 else "regenerate",
                    "target_path": artifact_id,
                    "depends_on": self._get_wave_dependencies(
                        artifact_id,
                        wave_num,
                        preview,
                    ),
                    "verification": "ruff check && mypy && pytest",
                    "wave": wave_num,
                }
                tasks.append(task)
        
        # Final verification task
        tasks.append({
            "id": "cascade-verify",
            "description": "Run full test suite to verify cascade didn't break anything",
            "mode": "verify",
            "depends_on": [f"cascade-{aid}" for aid in preview.waves[-1]],
            "verification_command": "pytest --tb=short",
        })
        
        return tasks
    
    def _generate_task_description(
        self,
        artifact_id: str,
        wave_num: int,
        preview: CascadePreview,
    ) -> str:
        """Generate descriptive task for agent."""
        if wave_num == 0:
            weakness_types = ", ".join(
                s.weakness_type.value for s in preview.weakness_score.signals
            )
            return (
                f"Regenerate {artifact_id} to fix: {weakness_types}. "
                f"Maintain all existing public interfaces."
            )
        else:
            return (
                f"Update {artifact_id} to be compatible with regenerated "
                f"{preview.weak_node}. Preserve existing behavior."
            )
    
    def _get_wave_dependencies(
        self,
        artifact_id: str,
        wave_num: int,
        preview: CascadePreview,
    ) -> list[str]:
        """Get task dependencies from previous waves."""
        if wave_num == 0:
            return []
        
        # Depend on all tasks from previous wave
        prev_wave = preview.waves[wave_num - 1]
        return [f"cascade-{aid}" for aid in prev_wave]
    
    async def extract_contract(self, artifact_id: str) -> ExtractedContract:
        """Extract public interface contract from a file before regeneration.
        
        This ensures we can verify the regenerated code is backward-compatible.
        Uses AST analysis to extract:
        - Function signatures (name, params, return type)
        - Class definitions with public methods
        - Module exports (__all__)
        - Key type annotations
        """
        import ast
        import hashlib
        
        artifact = self.graph[artifact_id]
        file_path = Path(artifact.produces_file)
        
        with open(file_path) as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        functions = []
        classes = []
        exports = []
        type_sigs = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions
                if not node.name.startswith('_'):
                    sig = f"def {node.name}({ast.unparse(node.args)})"
                    if node.returns:
                        sig += f" -> {ast.unparse(node.returns)}"
                    functions.append(sig)
            
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith('_'):
                    methods = [
                        f.name for f in node.body 
                        if isinstance(f, ast.FunctionDef) and not f.name.startswith('_')
                    ]
                    classes.append(f"class {node.name}: {', '.join(methods)}")
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, ast.List):
                            exports = [
                                elt.s for elt in node.value.elts 
                                if isinstance(elt, ast.Constant)
                            ]
        
        # Create hash of interface for quick comparison
        interface_str = "\n".join(sorted(functions + classes + exports))
        interface_hash = hashlib.sha256(interface_str.encode()).hexdigest()[:16]
        
        return ExtractedContract(
            artifact_id=artifact_id,
            file_path=file_path,
            functions=tuple(functions),
            classes=tuple(classes),
            exports=tuple(exports),
            type_signatures=tuple(type_sigs),
            interface_hash=interface_hash,
        )
    
    async def preview_with_contracts(
        self,
        weakness: WeaknessScore,
        include_deltas: bool = False,
    ) -> CascadePreview:
        """Enhanced preview that extracts contracts and optionally generates delta previews.
        
        Args:
            weakness: The weakness to preview cascade for
            include_deltas: If True, use agent to generate delta previews (expensive)
        
        Returns:
            CascadePreview with contracts and optionally deltas populated
        """
        # Get basic preview
        preview = self.preview(weakness)
        
        # Extract contracts for all affected files
        contracts = {}
        for artifact_id in [preview.weak_node] + list(preview.direct_dependents):
            if artifact_id in self.graph:
                try:
                    contract = await self.extract_contract(artifact_id)
                    contracts[artifact_id] = contract
                except Exception:
                    pass  # Some files may not be parseable
        
        # Optionally generate delta previews (expensive - requires agent calls)
        deltas = {}
        if include_deltas:
            # This would call the agent to generate proposed changes
            # and return diffs without actually writing them
            pass  # TODO: implement with agent dry-run mode
        
        # Return enhanced preview
        return CascadePreview(
            weak_node=preview.weak_node,
            weakness_score=preview.weakness_score,
            direct_dependents=preview.direct_dependents,
            transitive_dependents=preview.transitive_dependents,
            total_impacted=preview.total_impacted,
            estimated_effort=preview.estimated_effort,
            files_touched=preview.files_touched,
            waves=preview.waves,
            risk_assessment=preview.risk_assessment,
            extracted_contracts=contracts,
            delta_previews=deltas,
        )
    
    async def execute_wave_by_wave(
        self,
        preview: CascadePreview,
        auto_approve: bool = False,
        on_wave_complete: Callable[[WaveConfidence], Awaitable[bool]] | None = None,
    ) -> CascadeExecution:
        """Execute cascade with wave-by-wave approval.
        
        Args:
            preview: The cascade preview to execute
            auto_approve: If True, continue automatically if confidence > threshold
            on_wave_complete: Callback after each wave; return False to abort
        
        Returns:
            CascadeExecution with final state
        """
        execution = CascadeExecution(
            preview=preview,
            auto_approve=auto_approve,
        )
        
        for wave_num, wave in enumerate(preview.waves):
            execution.current_wave = wave_num
            
            # Execute wave (would call agent here)
            # ... agent execution ...
            
            # Verify wave completion
            test_result = await self._run_tests()
            type_result = await self._run_type_check()
            lint_result = await self._run_lint()
            contract_result = await self._verify_contracts(
                preview.extracted_contracts,
                wave,
            )
            
            confidence = WaveConfidence.compute(
                wave_num=wave_num,
                artifacts=tuple(wave),
                test_result=test_result,
                type_result=type_result,
                lint_result=lint_result,
                contract_result=contract_result,
            )
            
            execution.record_wave_completion(confidence)
            
            # Callback for UI/CLI to handle
            if on_wave_complete:
                should_continue = await on_wave_complete(confidence)
                if not should_continue:
                    execution.abort("User cancelled")
                    break
            
            # Check if we should pause
            if execution.paused_for_approval and not auto_approve:
                # In a real implementation, this would yield control
                # For now, we model it as requiring explicit approval
                break
            
            if execution.aborted:
                break
        
        return execution
```

#### 1.4 CLI Integration

```python
# src/sunwell/cli/weakness_cmd.py

import click
from pathlib import Path


@click.group()
def weakness():
    """Analyze and fix code weaknesses using DAG cascade."""
    pass


@weakness.command()
@click.option("--min-severity", default=0.3, help="Minimum severity to report")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def scan(min_severity: float, as_json: bool):
    """Scan codebase for weaknesses."""
    # Implementation calls WeaknessAnalyzer.scan()
    pass


@weakness.command()
@click.argument("artifact_id")
@click.option("--max-depth", default=5, help="Maximum cascade depth")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def preview(artifact_id: str, max_depth: int, as_json: bool):
    """Preview cascade impact for a weak artifact."""
    # Implementation calls CascadeEngine.preview()
    pass


@weakness.command()
@click.argument("artifact_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--json", "as_json", is_flag=True, help="Output progress as JSON events")
@click.option("--wave-by-wave", is_flag=True, help="Approve each wave manually")
@click.option("--show-deltas", is_flag=True, help="Show diffs before executing")
@click.option("--confidence-threshold", default=0.7, help="Min confidence to auto-proceed")
def fix(
    artifact_id: str,
    yes: bool,
    dry_run: bool,
    as_json: bool,
    wave_by_wave: bool,
    show_deltas: bool,
    confidence_threshold: float,
):
    """Fix a weak artifact and all dependents.
    
    By default, executes all waves after initial approval.
    Use --wave-by-wave to approve each wave individually.
    Use --show-deltas to preview exact changes before executing.
    
    Confidence scoring (0.0-1.0) tracks:
    - Tests passed (+0.4)
    - Types clean (+0.2)
    - Lint clean (+0.1)
    - Contracts preserved (+0.3)
    
    If confidence drops below threshold, execution pauses for review.
    
    ESCALATION: If 2+ consecutive waves have low confidence, the cascade
    is escalated to full human review (auto-approve is disabled). This
    guards against semantic regressions that pass signature-level checks
    but may change behavior.
    """
    # Implementation calls CascadeEngine.preview_with_contracts()
    # Then CascadeEngine.execute_wave_by_wave() with callbacks
    pass


@weakness.command()
@click.argument("artifact_id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def extract_contract(artifact_id: str, as_json: bool):
    """Extract and display the public interface contract for a file.
    
    Shows:
    - Public function signatures
    - Public class definitions
    - Module exports (__all__)
    - Key type annotations
    
    Useful for understanding what must be preserved during regeneration.
    """
    # Implementation calls CascadeEngine.extract_contract()
    pass
```

---

### Part 2: Rust/Tauri Backend — Performance & Studio Bridge

#### 2.1 Weakness Types (Rust)

```rust
// studio/src-tauri/src/weakness.rs

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Weakness type enum matching Python
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum WeaknessType {
    LowCoverage,
    HighComplexity,
    LintErrors,
    StaleCode,
    FailureProne,
    MissingTypes,
    BrokenContract,
}

/// A weakness signal for a single artifact
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WeaknessSignal {
    pub artifact_id: String,
    pub file_path: String,
    pub weakness_type: WeaknessType,
    pub severity: f32,
    pub evidence: HashMap<String, serde_json::Value>,
}

/// Aggregated weakness score
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WeaknessScore {
    pub artifact_id: String,
    pub file_path: String,
    pub signals: Vec<WeaknessSignal>,
    pub fan_out: u32,
    pub depth: u32,
    pub total_severity: f32,
    pub cascade_risk: String, // low, medium, high, critical
}

/// Preview of cascade regeneration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CascadePreview {
    pub weak_node: String,
    pub weakness_types: Vec<String>,
    pub severity: f32,
    pub cascade_risk: String,
    pub direct_dependents: Vec<String>,
    pub transitive_dependents: Vec<String>,
    pub total_impacted: u32,
    pub estimated_effort: String,
    pub files_touched: Vec<String>,
    pub waves: Vec<Vec<String>>,
    pub risk_assessment: String,
}

/// Full weakness report for a project
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WeaknessReport {
    pub project_path: String,
    pub scan_time: String,
    pub weaknesses: Vec<WeaknessScore>,
    pub total_files_scanned: u32,
    pub critical_count: u32,
    pub high_count: u32,
    pub medium_count: u32,
    pub low_count: u32,
}

/// Confidence score for a completed wave
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WaveConfidence {
    pub wave_num: u32,
    pub artifacts_completed: Vec<String>,
    pub tests_passed: bool,
    pub types_clean: bool,
    pub lint_clean: bool,
    pub contracts_preserved: bool,
    pub confidence: f32,
    pub deductions: Vec<String>,
    pub should_continue: bool,
}

/// State of an in-progress cascade execution
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CascadeExecution {
    pub preview: CascadePreview,
    pub current_wave: u32,
    pub wave_confidences: Vec<WaveConfidence>,
    pub auto_approve: bool,
    pub confidence_threshold: f32,
    // Escalation: if N consecutive waves have low confidence, escalate to human
    pub max_consecutive_low_confidence: u32,
    pub consecutive_low_confidence_count: u32,
    pub escalated_to_human: bool,
    // State
    pub paused_for_approval: bool,
    pub completed: bool,
    pub aborted: bool,
    pub abort_reason: Option<String>,
    pub overall_confidence: f32,
}

/// Extracted interface contract for a file
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExtractedContract {
    pub artifact_id: String,
    pub file_path: String,
    pub functions: Vec<String>,
    pub classes: Vec<String>,
    pub exports: Vec<String>,
    pub interface_hash: String,
}

/// Delta preview showing proposed changes
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeltaPreview {
    pub artifact_id: String,
    pub file_path: String,
    pub additions: u32,
    pub deletions: u32,
    pub hunks: Vec<String>,
    pub unified_diff: Option<String>,
}
```

#### 2.2 Tauri Commands

```rust
// studio/src-tauri/src/weakness.rs (continued)

use std::path::PathBuf;
use std::process::Command;

/// Scan project for weaknesses
/// 
/// Calls Python CLI with --json flag for structured output.
/// The CLI/Tauri contract: all commands support --json for Studio integration.
#[tauri::command]
pub async fn scan_weaknesses(path: String) -> Result<WeaknessReport, String> {
    let project_path = PathBuf::from(&path);
    
    // Call Python CLI and parse JSON output
    let output = Command::new("sunwell")
        .args(["weakness", "scan", "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run weakness scan: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Weakness scan failed: {}", stderr));
    }
    
    let report: WeaknessReport = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse weakness report: {}", e))?;
    
    Ok(report)
}

/// Preview cascade for a specific weakness
#[tauri::command]
pub async fn preview_cascade(
    path: String,
    artifact_id: String,
) -> Result<CascadePreview, String> {
    let project_path = PathBuf::from(&path);
    
    let output = Command::new("sunwell")
        .args(["weakness", "preview", &artifact_id, "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to preview cascade: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Cascade preview failed: {}", stderr));
    }
    
    let preview: CascadePreview = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse cascade preview: {}", e))?;
    
    Ok(preview)
}

/// Execute cascade fix
#[tauri::command]
pub async fn execute_cascade_fix(
    app: tauri::AppHandle,
    state: tauri::State<'_, crate::commands::AppState>,
    path: String,
    artifact_id: String,
) -> Result<crate::commands::RunGoalResult, String> {
    let project_path = PathBuf::from(&path);
    
    // Get preview first
    let preview = preview_cascade(path.clone(), artifact_id.clone()).await?;
    
    // Create goal description for cascade
    let goal = format!(
        "Fix weakness in {} ({}) and update {} dependent files",
        artifact_id,
        preview.weakness_types.join(", "),
        preview.total_impacted - 1,
    );
    
    // Run through agent
    crate::commands::run_goal(app, state, goal, Some(path)).await
}

/// Get weakness overlay data for DAG visualization
#[tauri::command]
pub async fn get_weakness_overlay(path: String) -> Result<HashMap<String, WeaknessScore>, String> {
    let report = scan_weaknesses(path).await?;
    
    let mut overlay = HashMap::new();
    for weakness in report.weaknesses {
        overlay.insert(weakness.artifact_id.clone(), weakness);
    }
    
    Ok(overlay)
}

/// Start wave-by-wave cascade execution
#[tauri::command]
pub async fn start_cascade_execution(
    path: String,
    artifact_id: String,
    auto_approve: bool,
    confidence_threshold: f32,
) -> Result<CascadeExecution, String> {
    let project_path = PathBuf::from(&path);
    
    let output = Command::new("sunwell")
        .args([
            "weakness", "fix", &artifact_id,
            "--wave-by-wave",
            "--json",
            &format!("--confidence-threshold={}", confidence_threshold),
        ])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to start cascade: {}", e))?;
    
    // Parse initial execution state
    let execution: CascadeExecution = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse execution state: {}", e))?;
    
    Ok(execution)
}

/// Approve current wave and continue execution
#[tauri::command]
pub async fn approve_cascade_wave(
    path: String,
    execution_id: String,
) -> Result<CascadeExecution, String> {
    // Send approval signal to running cascade process
    // Returns updated execution state
    todo!("Implement IPC with cascade process")
}

/// Abort cascade execution
#[tauri::command]
pub async fn abort_cascade(
    path: String,
    execution_id: String,
    reason: String,
) -> Result<(), String> {
    // Send abort signal to running cascade process
    todo!("Implement IPC with cascade process")
}

/// Get delta preview for a specific artifact (expensive)
#[tauri::command]
pub async fn get_delta_preview(
    path: String,
    artifact_id: String,
) -> Result<DeltaPreview, String> {
    let project_path = PathBuf::from(&path);
    
    let output = Command::new("sunwell")
        .args(["weakness", "preview", &artifact_id, "--show-deltas", "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to get delta preview: {}", e))?;
    
    let delta: DeltaPreview = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse delta preview: {}", e))?;
    
    Ok(delta)
}

/// Extract contract for a file
#[tauri::command]
pub async fn extract_contract(
    path: String,
    artifact_id: String,
) -> Result<ExtractedContract, String> {
    let project_path = PathBuf::from(&path);
    
    let output = Command::new("sunwell")
        .args(["weakness", "extract-contract", &artifact_id, "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to extract contract: {}", e))?;
    
    let contract: ExtractedContract = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse contract: {}", e))?;
    
    Ok(contract)
}
```

#### 2.3 Register Commands

```rust
// studio/src-tauri/src/main.rs (additions)

mod weakness;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            // ... existing commands ...
            weakness::scan_weaknesses,
            weakness::preview_cascade,
            weakness::execute_cascade_fix,
            weakness::get_weakness_overlay,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

---

### Part 3: Svelte Frontend — Visualization & Interaction

#### 3.1 Weakness Types (TypeScript)

```typescript
// studio/src/lib/types/weakness.ts

export type WeaknessType =
  | 'low_coverage'
  | 'high_complexity'
  | 'lint_errors'
  | 'stale_code'
  | 'failure_prone'
  | 'missing_types'
  | 'broken_contract';

export type CascadeRisk = 'low' | 'medium' | 'high' | 'critical';

export interface WeaknessSignal {
  artifactId: string;
  filePath: string;
  weaknessType: WeaknessType;
  severity: number;
  evidence: Record<string, unknown>;
}

export interface WeaknessScore {
  artifactId: string;
  filePath: string;
  signals: WeaknessSignal[];
  fanOut: number;
  depth: number;
  totalSeverity: number;
  cascadeRisk: CascadeRisk;
}

export interface CascadePreview {
  weakNode: string;
  weaknessTypes: string[];
  severity: number;
  cascadeRisk: CascadeRisk;
  directDependents: string[];
  transitiveDependents: string[];
  totalImpacted: number;
  estimatedEffort: string;
  filesTouched: string[];
  waves: string[][];
  riskAssessment: string;
}

export interface WeaknessReport {
  projectPath: string;
  scanTime: string;
  weaknesses: WeaknessScore[];
  totalFilesScanned: number;
  criticalCount: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
}
```

#### 3.2 Weakness Store

```typescript
// studio/src/stores/weakness.svelte.ts

import { invoke } from '@tauri-apps/api/core';
import type { WeaknessReport, WeaknessScore, CascadePreview } from '$lib/types/weakness';

interface WeaknessState {
  report: WeaknessReport | null;
  selectedWeakness: WeaknessScore | null;
  cascadePreview: CascadePreview | null;
  isScanning: boolean;
  isPreviewing: boolean;
  error: string | null;
}

function createWeaknessStore() {
  let state = $state<WeaknessState>({
    report: null,
    selectedWeakness: null,
    cascadePreview: null,
    isScanning: false,
    isPreviewing: false,
    error: null,
  });

  return {
    get report() { return state.report; },
    get selectedWeakness() { return state.selectedWeakness; },
    get cascadePreview() { return state.cascadePreview; },
    get isScanning() { return state.isScanning; },
    get isPreviewing() { return state.isPreviewing; },
    get error() { return state.error; },
    
    // Derived: weakness scores by artifact ID for DAG overlay
    get weaknessMap(): Map<string, WeaknessScore> {
      const map = new Map();
      if (state.report) {
        for (const w of state.report.weaknesses) {
          map.set(w.artifactId, w);
        }
      }
      return map;
    },
    
    async scan(projectPath: string) {
      state.isScanning = true;
      state.error = null;
      try {
        const report = await invoke<WeaknessReport>('scan_weaknesses', { path: projectPath });
        state.report = report;
      } catch (e) {
        state.error = String(e);
      } finally {
        state.isScanning = false;
      }
    },
    
    async selectWeakness(weakness: WeaknessScore | null, projectPath: string) {
      state.selectedWeakness = weakness;
      state.cascadePreview = null;
      
      if (weakness) {
        state.isPreviewing = true;
        try {
          const preview = await invoke<CascadePreview>('preview_cascade', {
            path: projectPath,
            artifactId: weakness.artifactId,
          });
          state.cascadePreview = preview;
        } catch (e) {
          state.error = String(e);
        } finally {
          state.isPreviewing = false;
        }
      }
    },
    
    async executeFix(projectPath: string, artifactId: string) {
      try {
        await invoke('execute_cascade_fix', { path: projectPath, artifactId });
      } catch (e) {
        state.error = String(e);
      }
    },
    
    clear() {
      state.report = null;
      state.selectedWeakness = null;
      state.cascadePreview = null;
      state.error = null;
    },
  };
}

export const weakness = createWeaknessStore();
```

#### 3.3 DAG Node Enhancement (Weakness Overlay)

```svelte
<!-- studio/src/components/dag/DagNode.svelte (enhanced) -->
<script lang="ts">
  import type { DagNode as DagNodeType } from '$lib/types';
  import type { WeaknessScore } from '$lib/types/weakness';
  import { dag, hoverNode, selectNode } from '../../stores/dag.svelte';
  import { weakness } from '../../stores/weakness.svelte';
  
  interface Props {
    node: DagNodeType;
    isSelected?: boolean;
    isHovered?: boolean;
  }
  
  let { node, isSelected = false, isHovered = false }: Props = $props();
  
  // Existing derived state
  let isCritical = $derived(dag.criticalPath.has(node.id));
  let isBottleneck = $derived(dag.bottlenecks.has(node.id));
  let willUnblock = $derived(dag.wouldUnblock.some(n => n.id === node.id));
  
  // NEW: Weakness overlay
  let weaknessScore = $derived(weakness.weaknessMap.get(node.id));
  let isWeak = $derived(weaknessScore !== undefined);
  let isInCascade = $derived(
    weakness.cascadePreview?.directDependents.includes(node.id) ||
    weakness.cascadePreview?.transitiveDependents.includes(node.id)
  );
  let isWeakRoot = $derived(weakness.cascadePreview?.weakNode === node.id);
  
  let weaknessRingColor = $derived(() => {
    if (!weaknessScore) return 'transparent';
    switch (weaknessScore.cascadeRisk) {
      case 'critical': return 'var(--error)';
      case 'high': return 'var(--warning)';
      case 'medium': return 'var(--info)';
      default: return 'var(--text-tertiary)';
    }
  });
  
  // ... rest of existing code ...
</script>

<g 
  class="dag-node {statusClass}"
  class:selected={isSelected}
  class:hovered={isHovered}
  class:critical={isCritical}
  class:bottleneck={isBottleneck}
  class:will-unblock={willUnblock}
  class:weak={isWeak}
  class:in-cascade={isInCascade}
  class:weak-root={isWeakRoot}
  transform="translate({(node.x ?? 0) - (node.width ?? 180) / 2}, {(node.y ?? 0) - (node.height ?? 80) / 2})"
  {/* ... existing handlers ... */}
>
  <!-- Weakness indicator ring (behind main node) -->
  {#if isWeak}
    <rect 
      class="weakness-ring"
      x="-4" y="-4"
      width={(node.width ?? 180) + 8}
      height={(node.height ?? 80) + 8}
      rx="12" ry="12"
      fill="none"
      stroke={weaknessRingColor()}
      stroke-width="2"
      stroke-dasharray={isWeakRoot ? 'none' : '4 2'}
    />
  {/if}
  
  <!-- Cascade highlight (when previewing) -->
  {#if isInCascade}
    <rect 
      class="cascade-highlight"
      x="-2" y="-2"
      width={(node.width ?? 180) + 4}
      height={(node.height ?? 80) + 4}
      rx="10" ry="10"
      fill="none"
      stroke="var(--accent)"
      stroke-width="1.5"
      stroke-dasharray="6 3"
    />
  {/if}
  
  <!-- Existing node rendering -->
  <rect class="node-bg" width={node.width ?? 180} height={node.height ?? 80} rx="8" ry="8" />
  <!-- ... rest of existing markup ... -->
  
  <!-- Weakness badge -->
  {#if isWeak && weaknessScore}
    <g class="weakness-badge" transform="translate(-8, -8)">
      <circle r="12" fill={weaknessRingColor()} />
      <text x="0" y="4" text-anchor="middle" font-size="10" fill="white">
        {weaknessScore.signals.length}
      </text>
    </g>
  {/if}
</g>

<style>
  /* ... existing styles ... */
  
  /* Weakness styles */
  .dag-node.weak .node-bg {
    stroke: var(--warning);
    stroke-width: 1;
  }
  .dag-node.weak-root .node-bg {
    stroke: var(--error);
    stroke-width: 2;
  }
  .dag-node.in-cascade .node-bg {
    stroke: var(--accent);
    stroke-width: 1.5;
  }
  
  .weakness-ring {
    animation: pulse-ring 2s ease-in-out infinite;
  }
  @keyframes pulse-ring {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
  }
  
  .cascade-highlight {
    animation: cascade-flow 1s linear infinite;
  }
  @keyframes cascade-flow {
    0% { stroke-dashoffset: 0; }
    100% { stroke-dashoffset: 18; }
  }
  
  .weakness-badge {
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
  }
</style>
```

#### 3.4 Weakness Panel Component

```svelte
<!-- studio/src/components/weakness/WeaknessPanel.svelte -->
<script lang="ts">
  import { weakness } from '../../stores/weakness.svelte';
  import { project } from '../../stores/project.svelte';
  import Button from '../Button.svelte';
  import Panel from '../Panel.svelte';
  
  let isExpanded = $state(true);
  
  function handleScan() {
    if (project.path) {
      weakness.scan(project.path);
    }
  }
  
  function handleSelectWeakness(w: typeof weakness.report.weaknesses[0]) {
    if (project.path) {
      weakness.selectWeakness(w, project.path);
    }
  }
  
  function handleFix() {
    if (project.path && weakness.selectedWeakness) {
      weakness.executeFix(project.path, weakness.selectedWeakness.artifactId);
    }
  }
  
  function getSeverityColor(severity: number): string {
    if (severity > 0.8) return 'var(--error)';
    if (severity > 0.5) return 'var(--warning)';
    if (severity > 0.3) return 'var(--info)';
    return 'var(--text-tertiary)';
  }
  
  function getWeaknessIcon(type: string): string {
    switch (type) {
      case 'low_coverage': return '🧪';
      case 'high_complexity': return '🌀';
      case 'lint_errors': return '⚠️';
      case 'stale_code': return '🕸️';
      case 'failure_prone': return '💥';
      case 'missing_types': return '📝';
      case 'broken_contract': return '🔗';
      default: return '❓';
    }
  }
</script>

<Panel title="Code Health" {isExpanded} onToggle={() => isExpanded = !isExpanded}>
  <div class="weakness-panel">
    <!-- Scan button -->
    <div class="scan-controls">
      <Button 
        variant="secondary" 
        onclick={handleScan}
        disabled={weakness.isScanning}
      >
        {weakness.isScanning ? 'Scanning...' : '🔍 Scan for Weaknesses'}
      </Button>
    </div>
    
    <!-- Summary stats -->
    {#if weakness.report}
      <div class="stats-row">
        <div class="stat" style="--color: var(--error)">
          <span class="stat-value">{weakness.report.criticalCount}</span>
          <span class="stat-label">Critical</span>
        </div>
        <div class="stat" style="--color: var(--warning)">
          <span class="stat-value">{weakness.report.highCount}</span>
          <span class="stat-label">High</span>
        </div>
        <div class="stat" style="--color: var(--info)">
          <span class="stat-value">{weakness.report.mediumCount}</span>
          <span class="stat-label">Medium</span>
        </div>
        <div class="stat" style="--color: var(--text-tertiary)">
          <span class="stat-value">{weakness.report.lowCount}</span>
          <span class="stat-label">Low</span>
        </div>
      </div>
      
      <!-- Weakness list -->
      <div class="weakness-list">
        {#each weakness.report.weaknesses as w (w.artifactId)}
          <button
            class="weakness-item"
            class:selected={weakness.selectedWeakness?.artifactId === w.artifactId}
            onclick={() => handleSelectWeakness(w)}
          >
            <div class="weakness-header">
              <span class="weakness-icons">
                {#each w.signals as signal}
                  <span title={signal.weaknessType}>{getWeaknessIcon(signal.weaknessType)}</span>
                {/each}
              </span>
              <span class="weakness-file">{w.filePath}</span>
            </div>
            <div class="weakness-meta">
              <span 
                class="severity-badge"
                style="background: {getSeverityColor(w.totalSeverity)}"
              >
                {(w.totalSeverity * 100).toFixed(0)}%
              </span>
              <span class="fan-out" title="Files that depend on this">
                📤 {w.fanOut}
              </span>
            </div>
          </button>
        {/each}
      </div>
    {/if}
    
    <!-- Cascade preview -->
    {#if weakness.cascadePreview}
      <div class="cascade-preview">
        <h4>Cascade Impact</h4>
        <div class="cascade-stats">
          <div class="cascade-stat">
            <span class="label">Direct dependents</span>
            <span class="value">{weakness.cascadePreview.directDependents.length}</span>
          </div>
          <div class="cascade-stat">
            <span class="label">Transitive</span>
            <span class="value">{weakness.cascadePreview.transitiveDependents.length}</span>
          </div>
          <div class="cascade-stat">
            <span class="label">Total impacted</span>
            <span class="value">{weakness.cascadePreview.totalImpacted}</span>
          </div>
          <div class="cascade-stat">
            <span class="label">Effort</span>
            <span class="value">{weakness.cascadePreview.estimatedEffort}</span>
          </div>
        </div>
        
        <div class="risk-assessment">
          <span class="risk-label">Risk:</span>
          <span class="risk-value risk-{weakness.cascadePreview.cascadeRisk}">
            {weakness.cascadePreview.cascadeRisk.toUpperCase()}
          </span>
          <p class="risk-detail">{weakness.cascadePreview.riskAssessment}</p>
        </div>
        
        <!-- Execution waves preview -->
        <div class="waves-preview">
          <h5>Regeneration Waves</h5>
          {#each weakness.cascadePreview.waves as wave, i}
            <div class="wave">
              <span class="wave-num">Wave {i}</span>
              <span class="wave-files">{wave.join(', ')}</span>
            </div>
          {/each}
        </div>
        
        <div class="fix-controls">
          <Button variant="secondary" onclick={handleFixWaveByWave}>
            🎚️ Wave-by-Wave
          </Button>
          <Button variant="primary" onclick={handleFix}>
            ⚡ Fix All ({weakness.cascadePreview.totalImpacted} files)
          </Button>
        </div>
      </div>
    {:else if weakness.isPreviewing}
      <div class="loading">Computing cascade impact...</div>
    {/if}
    
    <!-- Wave-by-Wave Execution UI -->
    {#if weakness.execution && !weakness.execution.completed}
      <div class="execution-panel">
        <h4>Cascade Execution</h4>
        
        <!-- Wave progress -->
        <div class="wave-progress">
          {#each weakness.cascadePreview.waves as wave, i}
            <div 
              class="wave-marker"
              class:completed={i < weakness.execution.currentWave}
              class:current={i === weakness.execution.currentWave}
              class:pending={i > weakness.execution.currentWave}
            >
              <span class="wave-num">{i}</span>
              {#if weakness.execution.waveConfidences[i]}
                <span class="wave-confidence" style="color: {getConfidenceColor(weakness.execution.waveConfidences[i].confidence)}">
                  {(weakness.execution.waveConfidences[i].confidence * 100).toFixed(0)}%
                </span>
              {/if}
            </div>
          {/each}
        </div>
        
        <!-- Current wave details -->
        {#if weakness.execution.pausedForApproval}
          <div class="approval-prompt">
            <h5>Wave {weakness.execution.currentWave} Complete</h5>
            
            {#if weakness.execution.waveConfidences.length > 0}
              {@const conf = weakness.execution.waveConfidences.at(-1)}
              <div class="confidence-details">
                <div class="confidence-score" style="color: {getConfidenceColor(conf.confidence)}">
                  Confidence: {(conf.confidence * 100).toFixed(0)}%
                </div>
                <div class="checks">
                  <span class:pass={conf.testsPassed} class:fail={!conf.testsPassed}>
                    {conf.testsPassed ? '✓' : '✗'} Tests
                  </span>
                  <span class:pass={conf.typesClean} class:fail={!conf.typesClean}>
                    {conf.typesClean ? '✓' : '✗'} Types
                  </span>
                  <span class:pass={conf.lintClean} class:fail={!conf.lintClean}>
                    {conf.lintClean ? '✓' : '✗'} Lint
                  </span>
                  <span class:pass={conf.contractsPreserved} class:fail={!conf.contractsPreserved}>
                    {conf.contractsPreserved ? '✓' : '✗'} Contracts
                  </span>
                </div>
                {#if conf.deductions.length > 0}
                  <div class="deductions">
                    {#each conf.deductions as d}
                      <span class="deduction">⚠️ {d}</span>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
            
            <div class="approval-actions">
              <Button variant="secondary" onclick={handleAbort}>
                ✗ Abort
              </Button>
              <Button variant="primary" onclick={handleApproveWave}>
                ✓ Continue to Wave {weakness.execution.currentWave + 1}
              </Button>
            </div>
          </div>
        {:else}
          <div class="executing">
            <span class="spinner">⟳</span>
            Executing Wave {weakness.execution.currentWave}...
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Execution complete -->
    {#if weakness.execution?.completed}
      <div class="execution-complete">
        <h4>✅ Cascade Complete</h4>
        <div class="final-stats">
          <span>Overall Confidence: {(weakness.execution.overallConfidence * 100).toFixed(0)}%</span>
          <span>Waves: {weakness.execution.waveConfidences.length}</span>
        </div>
      </div>
    {/if}
  </div>
</Panel>

<style>
  .weakness-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .scan-controls {
    display: flex;
    justify-content: center;
  }
  
  .stats-row {
    display: flex;
    justify-content: space-around;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
  }
  
  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
  
  .stat-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--color);
  }
  
  .stat-label {
    font-size: 10px;
    color: var(--text-secondary);
    text-transform: uppercase;
  }
  
  .weakness-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 200px;
    overflow-y: auto;
  }
  
  .weakness-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
  }
  
  .weakness-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
  }
  
  .weakness-item.selected {
    border-color: var(--accent);
    background: var(--accent-muted);
  }
  
  .weakness-header {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  
  .weakness-icons {
    display: flex;
    gap: 2px;
  }
  
  .weakness-file {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .weakness-meta {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  
  .severity-badge {
    font-size: 10px;
    font-weight: 600;
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
  }
  
  .fan-out {
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .cascade-preview {
    padding: 12px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .cascade-preview h4 {
    margin: 0;
    font-size: 12px;
    text-transform: uppercase;
    color: var(--text-secondary);
  }
  
  .cascade-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  
  .cascade-stat {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
  }
  
  .cascade-stat .label {
    color: var(--text-secondary);
  }
  
  .cascade-stat .value {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .risk-assessment {
    padding: 8px;
    background: var(--bg-secondary);
    border-radius: 6px;
  }
  
  .risk-label {
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .risk-value {
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
  }
  
  .risk-low { background: var(--success); color: white; }
  .risk-medium { background: var(--info); color: white; }
  .risk-high { background: var(--warning); color: black; }
  .risk-critical { background: var(--error); color: white; }
  
  .risk-detail {
    margin: 4px 0 0;
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .waves-preview {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .waves-preview h5 {
    margin: 0;
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .wave {
    display: flex;
    gap: 8px;
    font-size: 10px;
    padding: 4px 8px;
    background: var(--bg-secondary);
    border-radius: 4px;
  }
  
  .wave-num {
    font-weight: 600;
    color: var(--accent);
  }
  
  .wave-files {
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .loading {
    text-align: center;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 16px;
  }
</style>
```

---

## Implementation Plan

### Phase 1: Python Core — Weakness Detection (Week 1)

| Task | Description | Effort |
|------|-------------|--------|
| P1.1 | Create `weakness/types.py` with signal types | S |
| P1.2 | Implement `WeaknessAnalyzer` basic structure | M |
| P1.3 | Add coverage analysis (via `coverage.py`) | S |
| P1.4 | Add complexity analysis (via `radon`) | S |
| P1.5 | Add lint error analysis (via `ruff`) | S |
| P1.6 | Add type error analysis (via `mypy`) | S |
| P1.7 | Implement `CascadeEngine.preview()` | M |
| P1.8 | Add CLI command `sunwell weakness scan` | S |
| P1.9 | Unit tests for weakness detection | M |

### Phase 2: Python Core — Cascade & Contracts (Week 2)

| Task | Description | Effort |
|------|-------------|--------|
| P2.1 | Implement `ExtractedContract` and `extract_contract()` | M |
| P2.2 | Implement `WaveConfidence` scoring system | M |
| P2.3 | Implement `CascadeExecution` state machine | M |
| P2.4 | Implement `execute_wave_by_wave()` with callbacks | L |
| P2.5 | Add CLI commands `preview`, `fix`, `extract-contract` | M |
| P2.6 | Implement `--wave-by-wave` and `--show-deltas` modes | M |
| P2.7 | Integration tests for cascade execution | L |

### Phase 3: Rust/Tauri Bridge (Week 3)

| Task | Description | Effort |
|------|-------------|--------|
| R3.1 | Create `weakness.rs` with all types matching Python | M |
| R3.2 | Implement `scan_weaknesses` command | S |
| R3.3 | Implement `preview_cascade` command | S |
| R3.4 | Implement `start_cascade_execution` command | M |
| R3.5 | Implement `approve_cascade_wave` with IPC | M |
| R3.6 | Implement `abort_cascade` command | S |
| R3.7 | Implement `get_delta_preview` and `extract_contract` | S |
| R3.8 | Implement `get_weakness_overlay` for DAG | S |
| R3.9 | Register all commands in `main.rs` | S |
| R3.10 | Add tests for Tauri commands | M |

### Phase 4: Svelte Frontend (Week 4)

| Task | Description | Effort |
|------|-------------|--------|
| S4.1 | Create `weakness.ts` types (all new types) | S |
| S4.2 | Create `weakness.svelte.ts` store with execution state | M |
| S4.3 | Enhance `DagNode.svelte` with weakness overlay | M |
| S4.4 | Create `WeaknessPanel.svelte` with scan UI | M |
| S4.5 | Add cascade preview section to panel | M |
| S4.6 | Add wave-by-wave execution UI | L |
| S4.7 | Add confidence visualization (gauges, checks) | M |
| S4.8 | Add cascade animation to DAG edges | M |
| S4.9 | Integrate panel into main layout | S |
| S4.10 | Add keyboard shortcuts (Ctrl+Shift+W for scan) | S |

### Phase 5: Polish & Integration (Week 5)

| Task | Description | Effort |
|------|-------------|--------|
| I5.1 | Add staleness detection (git history) | M |
| I5.2 | Failure history tracking (from execution logs) | M |
| I5.3 | Delta preview generation (agent dry-run mode) | L |
| I5.4 | Performance optimization (cache analysis results) | M |
| I5.5 | E2E tests for full workflow | L |
| I5.6 | Documentation and examples | M |
| I5.7 | Dogfood on Sunwell codebase itself | L |

---

## Success Criteria

1. **Weakness detection**: Scan identifies ≥80% of known technical debt hotspots
2. **Cascade accuracy**: Preview matches actual impacted files in 100% of cases
3. **Contract preservation**: Regenerated code passes contract compatibility check in ≥95% of cases
4. **Confidence calibration**: Wave confidence score correlates with actual success rate (±10%)
5. **Regeneration success**: Agent fixes weak node + dependents with no regressions
6. **UI responsiveness**: Scan completes in <10s for 500-file project
7. **User control**: Wave-by-wave mode allows pause/abort at any point
8. **Rollback capability**: Failed cascades can be reverted to pre-cascade state

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large cascades overwhelm agent | High | Max cascade depth limit (default: 5), size limit (default: 50 files) |
| False positive weaknesses | Medium | Configurable thresholds, ability to ignore specific files via `.sunwellignore` |
| Circular dependencies in cascade | Medium | Detection and warning in preview; break cycles at arbitrary point |
| Regeneration introduces bugs | High | Mandatory verification step; rollback on test failure |
| Tool dependencies (coverage, radon) | Low | Graceful degradation if tools missing; document requirements |
| External dependencies (npm, pip) | Low | Cascade only touches source files; package deps are frozen during cascade |
| Artifacts without `produces_file` | Low | Skip in analysis; they can still appear as dependencies in cascade graph |
| Agent reliability bounds | High | Contract checks are signature-level, not semantic — a function could preserve its signature but change behavior. If confidence < threshold for N consecutive waves, escalate to full human review rather than continuing |
| Stale code false positives | Medium | "No commits in 6mo" alone doesn't indicate weakness — stable code may just work. Gate staleness signal on additional factors: stale + low coverage + high fan-out (all three required) |

---

## Future Extensions

### Near-term (v1.1)

1. **Auto-prioritization**: Use weakness scores to prioritize backlog goals
2. **Technical debt dashboard**: Track weakness scores over time with trend analysis
   - Persist scores per scan in `.sunwell/weakness-history.jsonl`
   - Show improvement/regression graphs in Studio
   - Alert when weakness score increases significantly
3. **Smart suggestions**: "You just edited X; consider regenerating Y"
4. **Multi-language support**: Extend analyzers for TypeScript, Rust, Go

### Medium-term (v2.0) — Semantic Change Propagation

The cascade engine generalizes beyond weakness fixing:

| Feature | Description |
|---------|-------------|
| **API Evolution** | Change interface → cascade signature updates to all implementations |
| **Dependency Upgrade** | Bump package version → cascade compatibility fixes |
| **Security Patches** | Identify vulnerable pattern → cascade fix everywhere |
| **Deprecation Migration** | Mark function deprecated → cascade callers to new API |
| **Schema Migration** | Change data model → cascade all code touching that model |

Each use case follows the same pattern:
1. Detect trigger (weakness, breaking change, CVE, deprecation notice)
2. Compute affected files via DAG
3. Extract contracts to preserve compatibility
4. Propagate changes wave-by-wave with confidence scoring
5. Verify with tests + types + contracts

### Long-term Vision

**Continuous code health maintenance**: The system monitors code quality, automatically proposes cascade fixes when weakness scores exceed thresholds, and executes approved cascades during low-activity periods.

```yaml
# .sunwell/health.yaml
weakness_thresholds:
  critical_max: 0       # No critical weaknesses allowed
  high_max: 3           # Max 3 high-severity weaknesses
  coverage_min: 0.7     # Minimum 70% coverage

auto_fix:
  enabled: true
  require_approval: true  # Still needs human approval
  schedule: "weekdays 2am-4am"  # Execute during low activity
  max_cascade_size: 20  # Don't auto-fix huge cascades
```

---

## Related RFCs

- **RFC-040**: Incremental Build — provides `find_invalidated()` cascade logic
- **RFC-046**: Autonomous Backlog — weakness scores inform goal priority
- **RFC-056**: Live DAG Integration — visualization foundation
- **RFC-047**: Deep Verification — verification step after cascade

---

## Appendix A: Example Workflow

```bash
# 1. Scan for weaknesses
$ sunwell weakness scan
📊 Weakness Report
─────────────────────────────────────────────────────────
Files scanned: 127
Critical: 2 | High: 5 | Medium: 12 | Low: 23

Top weaknesses:
│ File                    │ Type              │ Severity │ Fan-Out │
├─────────────────────────┼───────────────────┼──────────┼─────────┤
│ src/auth/session.py     │ low_coverage      │ 0.92     │ 12      │
│ src/api/handlers.py     │ high_complexity   │ 0.78     │ 8       │
│ src/models/user.py      │ stale_code        │ 0.71     │ 15      │

# 2. Preview cascade for worst weakness
$ sunwell weakness preview src/auth/session.py
🔍 Cascade Preview: src/auth/session.py
─────────────────────────────────────────────────────────
Weakness: low_coverage (92% severity)
Risk: CRITICAL

Cascade Impact:
  Direct dependents: 4
  Transitive dependents: 8
  Total impacted: 13 files

Regeneration Waves:
  Wave 0: src/auth/session.py (regenerate with tests)
  Wave 1: src/api/auth_handler.py, src/services/token_service.py, ...
  Wave 2: src/api/routes.py, src/api/refresh.py, ...
  Wave 3: Verification (run full test suite)

Estimated effort: medium (~30 min)
Risk: Large cascade (13 files) | High fan-out (12 dependents)

Proceed with fix? [y/N]

# 3. Execute cascade fix (wave-by-wave mode)
$ sunwell weakness fix src/auth/session.py --wave-by-wave
⚡ Starting cascade fix (wave-by-wave mode)...

Wave 0/3: Regenerating src/auth/session.py
  ✓ Generated new implementation with 95% coverage
  ✓ Tests passing
  ✓ Types clean
  ✓ Lint clean
  ✓ Contract preserved
  
  📊 Wave 0 Confidence: 100%
  Continue to Wave 1? [Y/n] y

Wave 1/3: Updating direct dependents
  ✓ src/api/auth_handler.py updated
  ✓ src/services/token_service.py updated
  ✓ src/middleware/auth_middleware.py updated
  ✓ src/services/login.py updated
  
  Running verification...
  ✓ Tests passed (87/87)
  ⚠ Type errors: 2 (in auth_handler.py)
  ✓ Lint clean
  ✓ Contracts preserved
  
  📊 Wave 1 Confidence: 80% (deduction: type errors)
  ⚠ Below threshold (70%), pausing for review.
  
  Type errors:
    auth_handler.py:45: Argument 1 has incompatible type "str | None"; expected "str"
    auth_handler.py:78: Missing return statement
  
  Options:
    [c] Continue anyway
    [f] Fix and retry wave
    [a] Abort cascade
  Choice: f

  Retrying Wave 1 with fixes...
  ✓ Type errors resolved
  
  📊 Wave 1 Confidence: 100%
  Continue to Wave 2? [Y/n] y

Wave 2/3: Updating transitive dependents
  ✓ src/api/routes.py updated
  ✓ src/api/refresh.py updated
  ... (6 more files)
  
  📊 Wave 2 Confidence: 100%
  Continue to Wave 3? [Y/n] y

Wave 3/3: Final verification
  ✓ ruff check passed
  ✓ mypy passed
  ✓ pytest passed (127 tests)
  ✓ All contracts verified

✅ Cascade complete!
  Files regenerated: 13
  Overall confidence: 95%
  Test coverage: 47% → 68%
  Complexity reduced: 15 → 8
  
  Commit message: "fix(auth): regenerate session.py and 12 dependents"

# 4. Alternative: Show deltas before executing
$ sunwell weakness fix src/auth/session.py --show-deltas --dry-run
📄 Delta Preview for Wave 0:

src/auth/session.py (+127, -89):
  - Remove global state, use ContextVar
  - Add comprehensive test coverage
  - Fix complexity (CC: 15 → 6)
  
  --- a/src/auth/session.py
  +++ b/src/auth/session.py
  @@ -1,20 +1,35 @@
  -_session_cache: dict[str, Session] = {}  # ❌ Global mutable state
  +from contextvars import ContextVar
  +_session: ContextVar[Session | None] = ContextVar('session', default=None)
  ...

Execute this plan? [y/N]
```

---

## Appendix B: DAG Visualization Mockup

```
┌─────────────────────────────────────────────────────────────────────────┐
│ DAG View                                         [🔍 Scan Weaknesses]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│     ┌──────────────┐                                                    │
│     │ config.py    │                                                    │
│     │ ○ Pending    │                                                    │
│     └──────┬───────┘                                                    │
│            │                                                            │
│     ┌──────▼───────┐       ┌──────────────┐                            │
│     │ session.py   │◀──────│ token_svc.py │                            │
│     │ ⚠ WEAK (92%) │       │ ○ Pending    │                            │
│     │ 🧪 coverage  │       └──────────────┘                            │
│     └──────┬───────┘                 │                                  │
│            │                         │                                  │
│     ┌──────▼───────┐       ┌────────▼─────┐                            │
│     │ auth_handler │◀──────│ refresh.py   │  ◄── IN CASCADE            │
│     │ ○ Pending    │       │ ○ Pending    │      (dashed border)       │
│     └──────┬───────┘       └──────────────┘                            │
│            │                                                            │
│     ┌──────▼───────┐                                                    │
│     │ routes.py    │                                                    │
│     │ ○ Pending    │                                                    │
│     └──────────────┘                                                    │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Code Health                                                    [▼]     │
│ ─────────────────────────────────────────────────────────────────────  │
│  Critical: 2  │  High: 5  │  Medium: 12  │  Low: 23                    │
│                                                                         │
│  ▸ 🧪 src/auth/session.py .............. 92% ⚠  📤 12                 │
│  ▸ 🌀 src/api/handlers.py .............. 78% ⚠  📤 8                  │
│  ▸ 🕸️ src/models/user.py ............... 71%    📤 15                 │
│                                                                         │
│  ┌─ Cascade Preview ──────────────────────────────────────────────┐    │
│  │ session.py → 13 files impacted                                  │    │
│  │ Risk: CRITICAL | Effort: medium                                 │    │
│  │                                                                 │    │
│  │ Waves: 0→session.py  1→4 files  2→8 files  3→verify           │    │
│  │                                                                 │    │
│  │              [⚡ Fix Cascade (13 files)]                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```
