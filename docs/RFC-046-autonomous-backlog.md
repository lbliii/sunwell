# RFC-046: Autonomous Backlog — Self-Directed Goal Generation

**Status**: Draft  
**Created**: 2026-01-19  
**Authors**: Sunwell Team  
**Depends on**: RFC-036 (Artifact-First Planning), RFC-042 (Adaptive Agent)  
**Enhanced by** (optional): RFC-044 (Puzzle Planning), RFC-045 (Project Intelligence)

---

## Summary

Autonomous Backlog enables Sunwell to generate, prioritize, and pursue goals without explicit user commands. Instead of waiting for "Build X", Sunwell continuously observes project state and identifies what *should* exist but doesn't — applying the same artifact-first decomposition to the meta-problem of goal selection.

**Core insight**: The Artifact-First model (RFC-036) asks "what must exist?" for a given goal. Autonomous Backlog asks the same question at the *project level*: "What should exist in this project that doesn't yet?"

**One-liner**: Sunwell doesn't wait to be told what to do. It sees what's missing and proposes to fix it.

---

## Motivation

### The Waiting Problem

Current AI assistants are reactive:

```
Human: "Build forum app"
AI: [builds forum app]
Human: "Add tests"
AI: [adds tests]
Human: "Fix the bug in auth"
AI: [fixes bug]
```

The AI has all the information to know tests are needed and bugs exist — but it waits to be told.

### What a Senior Engineer Does

A senior engineer on a team doesn't wait for explicit tasks:

1. **Sees failing tests** → Fixes them without being asked
2. **Notices missing tests** → Adds coverage for critical paths
3. **Spots TODOs** → Addresses them when context is fresh
4. **Identifies tech debt** → Proposes refactoring
5. **Reviews recent changes** → Catches issues early
6. **Anticipates needs** → Prepares for upcoming features

### The Opportunity

Sunwell already has (verified implementations):
- **Artifact-First Planning** (RFC-036): Can decompose any goal into artifacts  
  → `src/sunwell/naaru/artifacts.py`, `src/sunwell/naaru/planners/artifact.py`
- **Adaptive Agent** (RFC-042): Can execute with appropriate techniques  
  → `src/sunwell/adaptive/agent.py`, `src/sunwell/adaptive/signals.py`
- **Validation Gates** (RFC-042): Signal extraction for syntax, lint, type, runtime errors  
  → `src/sunwell/adaptive/gates.py`, `src/sunwell/adaptive/validation.py`

Sunwell has partial implementations (can enhance backlog):
- **Project Intelligence** (RFC-045): Decision memory, failure memory, pattern learning  
  → `src/sunwell/intelligence/` — `DecisionMemory`, `FailureMemory`, `ProjectContext` exist
- **Puzzle Planning** (RFC-044): Understands project structure (edges/middle/center)  
  → RFC status: Draft — integration is optional enhancement

What's missing: **Goal generation** — deciding *what* to work on, not just *how*.

---

## Goals and Non-Goals

### Goals

1. **Autonomous goal discovery** — Identify what should exist but doesn't
2. **Priority-aware execution** — Work on highest-value items first
3. **Context-sensitive proposals** — Goals reflect project state, not generic best practices
4. **Human-compatible backlog** — Output tasks a human could also pick up
5. **Graceful handoff** — Human can review, reprioritize, or veto at any point
6. **Integration with existing planning** — Reuse RFC-036/044 for decomposition

### Non-Goals

1. **Fully unsupervised operation** — Human approval still required (see future RFC-048)
2. **External issue tracker sync** — GitHub/Linear integration is future work (RFC-049)
3. **Multi-agent coordination** — Single instance focus (RFC-051)
4. **Production monitoring** — Observing deployed systems is future work (RFC-049)
5. **Unbounded execution** — Goals must be scoped; no "rewrite everything"

---

## Design Overview

### The Meta-Artifact Model

RFC-036 (Artifact-First) asks: *"Given a goal, what artifacts must exist?"*

Autonomous Backlog inverts this: *"Given the current state, what goals would produce missing artifacts?"*

```
RFC-036 (Forward):
  Goal "Build forum" → [UserModel, PostModel, Routes, Tests, ...]

RFC-046 (Backward):
  Current State → [Missing: Tests, Stale: Config, Broken: Auth] → Goals
```

### The Backlog as an Artifact Graph

The backlog itself is an artifact graph where:
- **Artifacts** = Goals (things that should be done)
- **Dependencies** = Sequencing (fix tests before refactoring)
- **Leaves** = Quick wins (no blockers)
- **Root** = Strategic objectives (the "center" in Puzzle terms)

```
┌────────────────────────────────────────────────────────────────────┐
│                       PROJECT BACKLOG GRAPH                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  LEAVES (Quick Wins)           MIDDLE (Dependencies)    ROOT       │
│  ─────────────────────         ──────────────────────   ──────     │
│                                                                    │
│  ┌─────────────┐                                                   │
│  │ Fix typo    │──┐                                                │
│  │ in README   │  │                                                │
│  └─────────────┘  │                                                │
│                   │     ┌──────────────────┐                       │
│  ┌─────────────┐  │     │ Improve test     │                       │
│  │ Add missing │──┼────▶│ coverage to 80%  │                       │
│  │ docstring   │  │     └────────┬─────────┘                       │
│  └─────────────┘  │              │                                 │
│                   │              │     ┌───────────────────┐       │
│  ┌─────────────┐  │              │     │   Ship v2.0       │       │
│  │ Fix failing │──┼──────────────┼────▶│   (strategic)     │       │
│  │ test        │  │              │     └───────────────────┘       │
│  └─────────────┘  │              │              ▲                  │
│                   │     ┌────────┴───────┐      │                  │
│  ┌─────────────┐  │     │ Refactor auth  │      │                  │
│  │ Update deps │──┼────▶│ module         │──────┘                  │
│  │ (security)  │  │     └────────────────┘                         │
│  └─────────────┘  │                                                │
│                                                                    │
│  ◀─── Priority: LEFT to RIGHT ───▶                                 │
│  (Quick wins first, strategic goals emerge from completed work)    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Design Options

### Option A: Observable-Only Mode (Recommended for Phase 1)

Start with deterministic signals only. No LLM required for goal generation.

**Pros**:
- Works today — no RFC-045/044 dependency
- Deterministic, reproducible goals
- Zero token cost for goal discovery
- Fast implementation (Week 1-4 only)

**Cons**:
- Misses intelligence-derived goals (deferred decisions, recurring failures)
- No context-aware prioritization
- No puzzle-based decomposition for complex goals

**Implementation**: Phases 1-4 of the plan below.

### Option B: Intelligence-Enhanced Mode (Phase 5+)

Add RFC-045 Project Intelligence for context-aware goal generation.

**Pros**:
- Surfaces deferred decisions when relevant
- Detects recurring failure patterns
- Learns from past sessions
- Context-aware priority scoring

**Cons**:
- Requires RFC-045 partial implementation (exists but incomplete)
- Adds LLM calls for intelligence analysis
- More complex testing

**Implementation**: Phase 5 as optional enhancement.

### Option C: Full Integration (Future)

Full RFC-044 Puzzle Planning + RFC-045 Intelligence.

**Pros**:
- Strategic goal decomposition via puzzle model
- Complete context awareness
- Maximum intelligence

**Cons**:
- RFC-044 not yet implemented
- Highest complexity
- Longest time to value

**Decision**: Start with **Option A** (Observable-Only), add **Option B** in Phase 5. Option C deferred to future RFC.

---

### Three Sources of Goals

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GOAL SOURCES                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐ │
│  │  1. OBSERVABLES  │     │  2. INTELLIGENCE │     │ 3. EXPLICIT │ │
│  │  (code signals)  │     │  (RFC-045 memory)│     │ (user input)│ │
│  └────────┬─────────┘     └────────┬─────────┘     └──────┬──────┘ │
│           │                        │                      │        │
│  • Failing tests           • Past TODOs mentioned  • "Fix auth"    │
│  • TODO comments           • Deferred decisions    • Issue tracker │
│  • Type errors             • Known tech debt       • Feature reqs  │
│  • Missing coverage        • Failure patterns      • "Improve X"   │
│  • Stale dependencies      • Unfinished work       • Roadmap items │
│  • Lint warnings           • Superseded decisions                  │
│           │                        │                      │        │
│           └────────────────────────┼──────────────────────┘        │
│                                    ▼                               │
│                         ┌──────────────────┐                       │
│                         │  GOAL GENERATOR  │                       │
│                         │  (prioritize &   │                       │
│                         │   deduplicate)   │                       │
│                         └────────┬─────────┘                       │
│                                  │                                 │
│                                  ▼                                 │
│                         ┌──────────────────┐                       │
│                         │    BACKLOG       │                       │
│                         │  (artifact DAG)  │                       │
│                         └──────────────────┘                       │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Signal → Goal → Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS BACKLOG FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌─────────────────────────────────────────────────────┐   │
│  │  START   │    │                SIGNAL EXTRACTION                    │   │
│  └────┬─────┘    │  (Tier 1: Observable-Only, no LLM needed)           │   │
│       │          └─────────────────────────────────────────────────────┘   │
│       ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  SignalExtractor.extract_all(root)                               │      │
│  │    ├─ pytest --collect-only → failing_test signals               │      │
│  │    ├─ grep TODO/FIXME → todo_comment signals                     │      │
│  │    ├─ ty/mypy → type_error signals                               │      │
│  │    ├─ ruff check → lint_warning signals                          │      │
│  │    └─ coverage report → missing_test signals                     │      │
│  └────────────────────────────┬─────────────────────────────────────┘      │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  IntelligenceAnalyzer.analyze()  [Tier 2: Optional]              │      │
│  │    ├─ DecisionMemory._decisions → low_confidence, stale          │      │
│  │    └─ FailureMemory._failures → recurring_failure clusters       │      │
│  └────────────────────────────┬─────────────────────────────────────┘      │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  GoalGenerator.generate(observable_signals, intelligence_signals)│      │
│  │    ├─ Convert signals → candidate goals                          │      │
│  │    ├─ Deduplicate (same root cause = one goal)                   │      │
│  │    ├─ Infer dependencies (topological sort)                      │      │
│  │    └─ Prioritize (security > fix > test > improve > document)    │      │
│  └────────────────────────────┬─────────────────────────────────────┘      │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  BacklogManager.refresh() → Backlog (goal DAG)                   │      │
│  │    ├─ Merge with existing (preserve completed)                   │      │
│  │    └─ backlog.next_goal() → highest priority unblocked goal      │      │
│  └────────────────────────────┬─────────────────────────────────────┘      │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  AutonomousLoop.run(mode)                                        │      │
│  │    ├─ mode=propose: Show backlog, don't execute                  │      │
│  │    ├─ mode=supervised: Await approval per goal                   │      │
│  │    └─ mode=autonomous: Execute auto_approvable without asking    │      │
│  └────────────────────────────┬─────────────────────────────────────┘      │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  For each approved goal:                                         │      │
│  │    ├─ ArtifactPlanner.discover_graph(goal.description)           │      │
│  │    │    └─ src/sunwell/naaru/planners/artifact.py:116            │      │
│  │    ├─ AdaptiveAgent.execute(artifact_graph)                      │      │
│  │    │    └─ src/sunwell/adaptive/agent.py:88                      │      │
│  │    ├─ Validate result                                            │      │
│  │    └─ BacklogManager.complete_goal() or block_goal()             │      │
│  └────────────────────────────┬─────────────────────────────────────┘      │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────┐                                                              │
│  │  REPEAT  │ ← Refresh backlog, get next goal                             │
│  └──────────┘                                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Observable Signals

Signals extracted directly from code state, requiring no LLM.

> **Integration point**: Builds on existing validation infrastructure:
> - `src/sunwell/adaptive/gates.py` — GateType enum (SYNTAX, LINT, TYPE, IMPORT, TEST)
> - `src/sunwell/adaptive/validation.py` — ValidationRunner
> - `src/sunwell/adaptive/signals.py` — ErrorSignals, classify_error()

```python
@dataclass(frozen=True, slots=True)
class ObservableSignal:
    """A signal extracted from code without LLM."""
    
    signal_type: Literal[
        "failing_test",
        "todo_comment", 
        "fixme_comment",
        "type_error",
        "lint_warning",
        "missing_test",
        "stale_dependency",
        "large_file",
        "high_complexity",
        "missing_docstring",
        "dead_code",
    ]
    location: CodeLocation
    severity: Literal["critical", "high", "medium", "low"]
    message: str
    auto_fixable: bool
    """Can this be fixed without human decision-making?"""


class SignalExtractor:
    """Extract observable signals from codebase."""
    
    async def extract_all(self, root: Path) -> list[ObservableSignal]:
        """Run all extractors and deduplicate."""
        signals = []
        signals.extend(await self._extract_test_failures(root))
        signals.extend(await self._extract_todos(root))
        signals.extend(await self._extract_type_errors(root))
        signals.extend(await self._extract_lint_warnings(root))
        signals.extend(await self._extract_coverage_gaps(root))
        signals.extend(await self._extract_stale_deps(root))
        return self._deduplicate(signals)
    
    async def _extract_test_failures(self, root: Path) -> list[ObservableSignal]:
        """Run pytest --collect-only, then pytest on collected."""
        ...
    
    async def _extract_todos(self, root: Path) -> list[ObservableSignal]:
        """Grep for TODO, FIXME, XXX, HACK comments."""
        ...
    
    async def _extract_type_errors(self, root: Path) -> list[ObservableSignal]:
        """Run mypy/pyright and parse output."""
        ...
    
    async def _extract_coverage_gaps(self, root: Path) -> list[ObservableSignal]:
        """Run coverage and find uncovered critical paths."""
        ...
```

**Key insight**: These signals are **deterministic** — no LLM needed, reproducible, cheap.

---

### 2. Intelligence Signals (Phase 5 Enhancement)

> **Note**: This component requires RFC-045 Project Intelligence. It is optional for Phase 1-4.
> The design below uses actual RFC-045 API from `src/sunwell/intelligence/`.

Signals from Project Intelligence (RFC-045) that require context:

```python
@dataclass(frozen=True, slots=True)
class IntelligenceSignal:
    """A signal derived from Project Intelligence."""
    
    signal_type: Literal[
        "low_confidence_decision", # Decision.confidence < threshold
        "superseded_decision",     # Decision.supersedes is set
        "recurring_failure",       # Multiple FailedApproach with same root_cause
        "stale_decision",          # Decision.timestamp > 90 days ago
        "similar_failure_cluster", # FailedApproach.similar_to has entries
    ]
    source: str
    """Session/decision ID where this was identified."""
    
    description: str
    relevance_score: float
    """0-1, how relevant is this to current work."""
    
    suggested_goal: str
    """What goal would address this signal."""


class IntelligenceAnalyzer:
    """Extract goal signals from Project Intelligence.
    
    Uses actual RFC-045 API:
    - DecisionMemory: src/sunwell/intelligence/decisions.py
    - FailureMemory: src/sunwell/intelligence/failures.py
    - ProjectContext: src/sunwell/intelligence/context.py
    """
    
    def __init__(self, context: ProjectContext):
        self.context = context
    
    async def analyze(self) -> list[IntelligenceSignal]:
        """Scan intelligence stores for actionable signals.
        
        Uses existing DecisionMemory/FailureMemory API:
        - Iterates _decisions dict directly (no get_deferred needed)
        - Checks Decision.confidence for low-confidence decisions
        - Groups FailedApproach by similar_to for recurring patterns
        """
        signals = []
        
        # Low-confidence decisions that may need revisiting
        # API: DecisionMemory._decisions is dict[str, Decision]
        for decision in self.context.decisions._decisions.values():
            if decision.confidence < 0.7:
                signals.append(IntelligenceSignal(
                    signal_type="low_confidence_decision",
                    source=decision.session_id,
                    description=f"Low confidence ({decision.confidence:.0%}): {decision.question}",
                    relevance_score=1.0 - decision.confidence,
                    suggested_goal=f"Revisit decision: {decision.question}",
                ))
            
            # Stale decisions (> 90 days old)
            age_days = (datetime.now() - decision.timestamp).days
            if age_days > 90 and decision.confidence < 0.9:
                signals.append(IntelligenceSignal(
                    signal_type="stale_decision",
                    source=decision.id,
                    description=f"Decision from {age_days} days ago: {decision.question}",
                    relevance_score=min(age_days / 180, 1.0),
                    suggested_goal=f"Review stale decision: {decision.choice}",
                ))
        
        # Recurring failures - group by similar_to
        # API: FailureMemory._failures is dict[str, FailedApproach]
        # FailedApproach.similar_to: list[str] links related failures
        failure_clusters: dict[str, list[FailedApproach]] = {}
        for failure in self.context.failures._failures.values():
            if failure.similar_to:
                cluster_key = failure.similar_to[0]  # Group by first similar
                failure_clusters.setdefault(cluster_key, []).append(failure)
        
        for cluster_key, failures in failure_clusters.items():
            if len(failures) >= 2:  # Recurring pattern
                root_causes = {f.root_cause for f in failures if f.root_cause}
                signals.append(IntelligenceSignal(
                    signal_type="recurring_failure",
                    source=cluster_key,
                    description=f"Failed {len(failures)}x: {failures[0].description[:50]}",
                    relevance_score=min(len(failures) / 5, 1.0),
                    suggested_goal=f"Fix root cause: {root_causes.pop() if root_causes else failures[0].description}",
                ))
        
        return signals
```

---

### 3. Goal Generator

Converts signals into prioritized goals:

```python
@dataclass(frozen=True, slots=True)
class Goal:
    """A generated goal ready for execution."""
    
    id: str
    title: str
    description: str
    
    source_signals: tuple[str, ...]
    """IDs of signals that generated this goal."""
    
    priority: float
    """0-1, higher = more urgent."""
    
    estimated_complexity: Literal["trivial", "simple", "moderate", "complex"]
    
    requires: frozenset[str]
    """Goal IDs this depends on."""
    
    category: Literal[
        "fix",          # Something broken
        "improve",      # Something suboptimal
        "add",          # Something missing
        "refactor",     # Structural improvement
        "document",     # Documentation gap
        "test",         # Test coverage
        "security",     # Security-related
        "performance",  # Performance-related
    ]
    
    auto_approvable: bool
    """Can this be executed without human approval?"""
    
    scope: GoalScope
    """Bounded scope for safety."""


@dataclass(frozen=True, slots=True)
class GoalScope:
    """Bounded scope to prevent unbounded changes."""
    
    max_files: int = 5
    """Maximum files this goal should touch."""
    
    max_lines_changed: int = 500
    """Maximum lines added/removed."""
    
    allowed_paths: frozenset[Path] = frozenset()
    """If set, restrict changes to these paths."""
    
    forbidden_paths: frozenset[Path] = frozenset()
    """Never touch these paths."""


class GoalGenerator:
    """Generate and prioritize goals from signals."""
    
    def __init__(
        self,
        context: ProjectContext,
        policy: GoalPolicy,
    ):
        self.context = context
        self.policy = policy
    
    async def generate(
        self,
        observable_signals: list[ObservableSignal],
        intelligence_signals: list[IntelligenceSignal],
        explicit_goals: list[str] | None = None,
    ) -> list[Goal]:
        """Generate prioritized goal list."""
        
        # 1. Convert signals to candidate goals
        candidates = []
        candidates.extend(self._goals_from_observable(observable_signals))
        candidates.extend(self._goals_from_intelligence(intelligence_signals))
        if explicit_goals:
            candidates.extend(self._goals_from_explicit(explicit_goals))
        
        # 2. Deduplicate (same root cause = one goal)
        deduplicated = self._deduplicate_goals(candidates)
        
        # 3. Build dependency graph
        with_deps = await self._infer_dependencies(deduplicated)
        
        # 4. Score and prioritize
        prioritized = self._prioritize(with_deps)
        
        # 5. Apply policy limits
        filtered = self._apply_policy(prioritized)
        
        return filtered
    
    def _prioritize(self, goals: list[Goal]) -> list[Goal]:
        """Score goals by priority.
        
        Priority factors:
        - Severity: critical > high > medium > low
        - Category: security > fix > test > improve > refactor > document
        - Complexity: trivial > simple > moderate > complex (quick wins first)
        - Dependencies: leaves before roots (unblock others)
        - Recency: recently introduced issues > old tech debt
        - User signal: explicit requests > inferred needs
        """
        ...
    
    def _goals_from_observable(
        self,
        signals: list[ObservableSignal],
    ) -> list[Goal]:
        """Convert observable signals to goals."""
        goals = []
        
        for signal in signals:
            if signal.signal_type == "failing_test":
                goals.append(Goal(
                    id=f"fix-test-{hash(signal.location)}",
                    title=f"Fix failing test: {signal.location.symbol}",
                    description=signal.message,
                    source_signals=(signal.location.file.as_posix(),),
                    priority=0.95 if signal.severity == "critical" else 0.8,
                    estimated_complexity="simple",
                    requires=frozenset(),
                    category="fix",
                    auto_approvable=True,  # Tests are safe to fix
                    scope=GoalScope(max_files=2, max_lines_changed=100),
                ))
            
            elif signal.signal_type == "todo_comment":
                goals.append(Goal(
                    id=f"todo-{hash(signal.location)}",
                    title=f"Address TODO: {signal.message[:50]}",
                    description=signal.message,
                    source_signals=(signal.location.file.as_posix(),),
                    priority=0.4,  # Lower priority than broken things
                    estimated_complexity="moderate",
                    requires=frozenset(),
                    category="improve",
                    auto_approvable=False,  # TODOs need human judgment
                    scope=GoalScope(max_files=3, max_lines_changed=200),
                ))
            
            # ... other signal types
        
        return goals
```

---

### 4. Backlog Manager

Maintains the goal DAG and coordinates execution:

```python
@dataclass
class Backlog:
    """The prioritized backlog as an artifact DAG."""
    
    goals: dict[str, Goal]
    """All known goals."""
    
    completed: set[str]
    """Goal IDs that are done."""
    
    in_progress: str | None
    """Currently executing goal, if any."""
    
    blocked: dict[str, str]
    """Goal ID → reason blocked."""
    
    def execution_order(self) -> list[Goal]:
        """Return goals in optimal execution order.
        
        Uses same wave algorithm as ArtifactGraph (RFC-036):
        - Leaves first (no dependencies)
        - Higher priority within each wave
        - Quick wins before complex tasks
        """
        ...
    
    def next_goal(self) -> Goal | None:
        """Get the next goal to work on."""
        for goal in self.execution_order():
            if goal.id not in self.completed:
                if goal.id not in self.blocked:
                    if all(dep in self.completed for dep in goal.requires):
                        return goal
        return None
    
    def to_mermaid(self) -> str:
        """Export backlog as Mermaid diagram."""
        ...


class BacklogManager:
    """Manages the autonomous backlog lifecycle."""
    
    def __init__(
        self,
        context: ProjectContext,
        signal_extractor: SignalExtractor,
        intelligence_analyzer: IntelligenceAnalyzer,
        goal_generator: GoalGenerator,
    ):
        self.context = context
        self.signal_extractor = signal_extractor
        self.intelligence_analyzer = intelligence_analyzer
        self.goal_generator = goal_generator
        self.backlog = Backlog(goals={}, completed=set(), in_progress=None, blocked={})
    
    async def refresh(self) -> Backlog:
        """Refresh backlog from current project state.
        
        Called:
        - On session start
        - After completing a goal
        - After external changes (git pull, etc.)
        """
        # 1. Extract fresh signals
        observable = await self.signal_extractor.extract_all(self.context.root)
        intelligence = await self.intelligence_analyzer.analyze()
        
        # 2. Generate goals
        goals = await self.goal_generator.generate(
            observable_signals=observable,
            intelligence_signals=intelligence,
        )
        
        # 3. Merge with existing backlog (preserve completed, update priorities)
        self.backlog = self._merge_backlog(self.backlog, goals)
        
        return self.backlog
    
    async def complete_goal(self, goal_id: str, result: GoalResult) -> None:
        """Mark a goal as completed and refresh."""
        self.backlog.completed.add(goal_id)
        self.backlog.in_progress = None
        
        # Record in intelligence for future reference
        await self.context.decisions.record_goal_completion(goal_id, result)
        
        # Refresh to find newly unblocked goals
        await self.refresh()
    
    async def block_goal(self, goal_id: str, reason: str) -> None:
        """Mark a goal as blocked."""
        self.backlog.blocked[goal_id] = reason
        self.backlog.in_progress = None
```

---

### 5. Autonomous Loop

The main execution loop for autonomous operation:

```python
class AutonomousLoop:
    """Main loop for autonomous backlog execution."""
    
    def __init__(
        self,
        backlog_manager: BacklogManager,
        planner: ArtifactPlanner,  # RFC-036
        agent: AdaptiveAgent,       # RFC-042
        policy: AutonomyPolicy,
    ):
        self.backlog_manager = backlog_manager
        self.planner = planner
        self.agent = agent
        self.policy = policy
    
    async def run(
        self,
        mode: Literal["propose", "supervised", "autonomous"],
    ) -> AsyncIterator[LoopEvent]:
        """Run the autonomous loop.
        
        Modes:
        - propose: Generate backlog and show to user, don't execute
        - supervised: Execute with human approval per goal
        - autonomous: Execute auto-approvable goals without asking
        """
        # Initial refresh
        backlog = await self.backlog_manager.refresh()
        yield BacklogRefreshed(backlog=backlog)
        
        while True:
            # Get next goal
            goal = backlog.next_goal()
            
            if goal is None:
                yield BacklogEmpty()
                if mode == "autonomous":
                    # Wait for external changes, then refresh
                    await self._wait_for_changes()
                    backlog = await self.backlog_manager.refresh()
                    continue
                else:
                    break
            
            # Check approval
            if mode == "propose":
                yield GoalProposed(goal=goal)
                continue
            
            if mode == "supervised" or not goal.auto_approvable:
                yield GoalAwaitingApproval(goal=goal)
                approval = await self._await_approval(goal)
                if not approval.approved:
                    if approval.skip:
                        await self.backlog_manager.block_goal(goal.id, "User skipped")
                    continue
            
            # Execute goal
            yield GoalStarted(goal=goal)
            self.backlog_manager.backlog.in_progress = goal.id
            
            try:
                # Decompose goal into artifacts (RFC-036)
                artifact_graph = await self.planner.plan(goal.description)
                yield GoalPlanned(goal=goal, artifacts=artifact_graph)
                
                # Execute with adaptive agent (RFC-042)
                async for event in self.agent.execute(artifact_graph):
                    yield ExecutionEvent(goal=goal, event=event)
                
                # Validate
                result = await self._validate_goal(goal)
                
                if result.success:
                    await self.backlog_manager.complete_goal(goal.id, result)
                    yield GoalCompleted(goal=goal, result=result)
                else:
                    await self.backlog_manager.block_goal(goal.id, result.failure_reason)
                    yield GoalFailed(goal=goal, result=result)
                
            except Exception as e:
                await self.backlog_manager.block_goal(goal.id, str(e))
                yield GoalFailed(goal=goal, error=e)
            
            # Refresh backlog after each goal (new signals may have appeared)
            backlog = await self.backlog_manager.refresh()
            yield BacklogRefreshed(backlog=backlog)
```

---

## Integration with Existing Systems

### With RFC-036 (Artifact-First Planning)

Goals decompose into artifact graphs:

```python
# Goal: "Fix failing test in auth_test.py"
#   ↓ ArtifactPlanner
# ArtifactGraph:
#   - Artifact: "Read test file" (leaf)
#   - Artifact: "Identify failure cause" (depends on read)
#   - Artifact: "Fix source code" (depends on identify)
#   - Artifact: "Verify test passes" (depends on fix)
```

### With RFC-044 (Puzzle Planning) — Optional Enhancement

> **Note**: RFC-044 is in Draft status. This integration is **optional** and deferred to Phase 6+.

Strategic goals *can* use puzzle decomposition when RFC-044 is implemented:

```python
# Goal: "Refactor auth module" (complex, strategic)
#   ↓ PuzzlePlanner (when available)
# CENTER: "Auth protocol that supports multiple providers"
# MIDDLE: "Provider implementations, middleware, session handling"
# EDGES: "OAuth, JWT, Session storage protocols"

# Without RFC-044: Falls back to RFC-036 ArtifactPlanner
#   ↓ ArtifactPlanner.discover_graph()
# Standard artifact decomposition without puzzle semantics
```

### With RFC-045 (Project Intelligence)

Intelligence informs goal generation:

```python
# Intelligence signals:
# - Decision from 2 weeks ago: "Defer async auth until v2"
# - v2 milestone is now active
#   ↓
# Generated goal: "Implement async auth (deferred decision now relevant)"
```

### With RFC-042 (Adaptive Agent)

Goal complexity determines execution strategy:

```python
match goal.estimated_complexity:
    case "trivial":
        # Single-shot, no validation
        strategy = ExecutionStrategy.FAST
    case "simple":
        # Validation gates, no harmonic
        strategy = ExecutionStrategy.STANDARD
    case "moderate":
        # Harmonic candidates, compound eye on failure
        strategy = ExecutionStrategy.ADAPTIVE
    case "complex":
        # Full vortex, multi-candidate, human review
        strategy = ExecutionStrategy.FULL
```

---

## Execution Modes

### Mode 1: Propose (Default)

Sunwell generates and displays the backlog without executing:

```
$ sunwell backlog

📋 Project Backlog (7 goals identified)

QUICK WINS (auto-approvable):
  1. [FIX] Failing test: test_auth_flow ─── auth_test.py:45
     Priority: 0.95 │ Complexity: simple │ Est: 5 min
  
  2. [FIX] Type error in user model ─── models/user.py:23
     Priority: 0.85 │ Complexity: trivial │ Est: 2 min

NEEDS REVIEW:
  3. [IMPROVE] Address TODO: "Handle rate limiting" ─── api/routes.py:89
     Priority: 0.60 │ Complexity: moderate │ Est: 30 min
     
  4. [REFACTOR] Reduce complexity in payment module
     Priority: 0.45 │ Complexity: complex │ Est: 2 hr
     Source: Cyclomatic complexity = 24 (threshold: 10)

DEFERRED (from past sessions):
  5. [ADD] Async auth support (deferred 2 weeks ago)
     Priority: 0.50 │ Complexity: complex │ Est: 4 hr
     Reason deferred: "Wait for v2 milestone"
     Now relevant: v2 milestone is active

Run `sunwell backlog --execute` to start, or `sunwell backlog --approve 1,2` to approve specific goals.
```

### Mode 2: Supervised

Execute with human approval per goal:

```
$ sunwell backlog --execute

📋 Starting supervised execution...

Goal 1/7: Fix failing test: test_auth_flow
  File: auth_test.py:45
  Est: 5 min

Approve? [Y/n/skip/details] y

Executing...
  ├─ Reading test file... ✓
  ├─ Identifying failure cause... ✓
  │   → Missing mock for db connection
  ├─ Applying fix... ✓
  └─ Verifying... ✓

✓ Goal completed in 3 min 24 sec

Goal 2/7: Type error in user model
  File: models/user.py:23
  Est: 2 min

Approve? [Y/n/skip/details] _
```

### Mode 3: Autonomous (Future RFC-048)

Execute auto-approvable goals without asking:

```
$ sunwell backlog --autonomous

🤖 Autonomous mode enabled
   Auto-approvable: 2 goals
   Needs review: 5 goals (will pause)

Executing Goal 1: Fix failing test...
  [streaming progress]
  ✓ Complete

Executing Goal 2: Fix type error...
  [streaming progress]
  ✓ Complete

⏸ Paused: Goal 3 requires approval
  [IMPROVE] Address TODO: "Handle rate limiting"
  
  Approve? [Y/n/skip] _
```

---

## Goal Policy

Configurable policy for goal generation:

```yaml
# .sunwell/config.yaml
backlog:
  enabled: true
  
  # What signals to look for
  signals:
    failing_tests: true
    todo_comments: true
    type_errors: true
    lint_warnings: true
    coverage_gaps: true
    stale_dependencies: true
    
  # Priority weights
  priorities:
    security: 1.0      # Highest
    fix: 0.9
    test: 0.7
    improve: 0.5
    refactor: 0.4
    document: 0.3      # Lowest
    
  # Scope limits
  limits:
    max_goals: 20
    max_files_per_goal: 10
    max_lines_per_goal: 1000
    
  # Auto-approval rules
  auto_approve:
    - category: fix
      complexity: [trivial, simple]
      scope_files_max: 3
    - category: test
      complexity: [trivial, simple, moderate]
      
  # Exclusions
  exclude:
    paths:
      - "vendor/"
      - "generated/"
    patterns:
      - "TODO(someday)"  # Explicit deferral marker
```

---

## Storage

```
.sunwell/
├── intelligence/          # RFC-045
│   └── ...
├── backlog/
│   ├── goals.jsonl        # Goal history (append-only)
│   ├── current.json       # Current backlog state
│   └── completed.jsonl    # Completed goals with results
└── config.yaml
```

---

## Risks and Mitigations

### Risk 1: Goal Explosion

**Problem**: Too many low-value goals clutter the backlog.

**Mitigation**:
- Configurable `max_goals` limit
- Priority threshold (drop goals below 0.2)
- Category-based filtering
- "Quick win" bias (simple goals first, complex deferred)

### Risk 2: Unbounded Changes

**Problem**: A goal leads to rewriting half the codebase.

**Mitigation**:
- `GoalScope` enforces hard limits
- Abort if scope exceeded
- Human approval for complex goals
- Puzzle decomposition creates natural boundaries

### Risk 3: Stale Goals

**Problem**: Goals become irrelevant after code changes.

**Mitigation**:
- Refresh backlog after each goal completion
- Refresh on external changes (git events)
- Goals include `source_signals` — if signal disappears, goal is removed

### Risk 4: Conflicting Goals

**Problem**: Two goals want to modify the same code differently.

**Mitigation**:
- Dependency inference detects overlaps
- Serialize conflicting goals (one at a time)
- Surface conflicts to user for prioritization

### Risk 5: Gaming Auto-Approval

**Problem**: A goal looks simple but has large impact.

**Mitigation**:
- `auto_approvable` based on category + complexity + scope
- Post-execution validation (revert if tests fail)
- Conservative defaults (most goals require approval)

---

## Graceful Degradation

Autonomous Backlog is designed to work with varying levels of infrastructure:

### Tier 1: Observable-Only (Minimum Viable)

**Requires**: RFC-036, RFC-042 only (both implemented)

```yaml
available:
  - SignalExtractor (deterministic signals)
  - GoalGenerator (from observable signals)
  - BacklogManager (goal DAG)
  - AutonomousLoop (execution)
  
unavailable:
  - IntelligenceAnalyzer (needs RFC-045)
  - PuzzlePlanner integration (needs RFC-044)
  
behavior:
  - Goals generated from: failing tests, TODOs, type errors, lint warnings
  - Goal priority: severity + category + complexity
  - Decomposition: ArtifactPlanner only
```

### Tier 2: Intelligence-Enhanced

**Requires**: RFC-036, RFC-042, RFC-045 (partially implemented)

```yaml
available:
  - All Tier 1 features
  - IntelligenceAnalyzer (low-confidence decisions, recurring failures)
  - Context-aware priority scoring
  
unavailable:
  - PuzzlePlanner integration (needs RFC-044)
  
behavior:
  - Goals generated from: observables + intelligence signals
  - Goal priority: severity + category + complexity + relevance score
  - Decomposition: ArtifactPlanner only
```

### Tier 3: Full Integration (Future)

**Requires**: RFC-036, RFC-042, RFC-044, RFC-045

```yaml
available:
  - All Tier 2 features
  - PuzzlePlanner for complex/strategic goals
  - Full puzzle-based decomposition
  
behavior:
  - Strategic goals use puzzle model (center/middle/edges)
  - Complexity-based planner selection
```

### Capability Detection

```python
class CapabilityDetector:
    """Detect available capabilities at runtime."""
    
    def detect_tier(self, context: ProjectContext | None) -> Tier:
        """Determine operational tier based on available components."""
        
        # Check for RFC-045 Intelligence
        has_intelligence = (
            context is not None
            and hasattr(context, 'decisions')
            and hasattr(context, 'failures')
        )
        
        # Check for RFC-044 Puzzle Planning (future)
        has_puzzle = False  # Not yet implemented
        
        if has_puzzle and has_intelligence:
            return Tier.FULL
        elif has_intelligence:
            return Tier.INTELLIGENCE_ENHANCED
        else:
            return Tier.OBSERVABLE_ONLY
```

---

## CLI Commands

```bash
# View backlog
sunwell backlog                      # Show prioritized backlog
sunwell backlog --json               # Machine-readable output
sunwell backlog --mermaid            # Dependency graph visualization

# Execute
sunwell backlog --execute            # Supervised mode
sunwell backlog --execute --approve 1,2,3  # Pre-approve specific goals
sunwell backlog --autonomous         # Auto-execute safe goals (future)

# Management
sunwell backlog refresh              # Force refresh from signals
sunwell backlog add "Fix the auth bug"  # Add explicit goal
sunwell backlog skip 3               # Skip a goal
sunwell backlog block 4 "Waiting for API"  # Block with reason
sunwell backlog history              # View completed goals
```

---

## Testing Strategy

### Unit Tests

```python
class TestSignalExtractor:
    async def test_extracts_failing_tests(self, project_with_failing_test):
        extractor = SignalExtractor()
        signals = await extractor.extract_all(project_with_failing_test)
        
        failing = [s for s in signals if s.signal_type == "failing_test"]
        assert len(failing) == 1
        assert failing[0].severity == "high"
    
    async def test_extracts_todos(self, project_with_todos):
        extractor = SignalExtractor()
        signals = await extractor.extract_all(project_with_todos)
        
        todos = [s for s in signals if s.signal_type == "todo_comment"]
        assert len(todos) == 3


class TestGoalGenerator:
    async def test_deduplicates_similar_goals(self):
        # Two failing tests in same file → one "fix tests" goal
        ...
    
    async def test_infers_dependencies(self):
        # "Refactor auth" depends on "fix auth tests"
        ...
    
    async def test_respects_priority_order(self):
        # Security > fix > improve > document
        ...
```

### Integration Tests

```python
class TestAutonomousLoop:
    async def test_propose_mode_doesnt_execute(self):
        """Propose mode only shows backlog."""
        ...
    
    async def test_supervised_mode_awaits_approval(self):
        """Each goal requires approval."""
        ...
    
    async def test_completes_dependency_chain(self):
        """Goals execute in dependency order."""
        ...
    
    async def test_refreshes_after_completion(self):
        """Backlog updates after each goal."""
        ...
```

---

## Implementation Plan

### Tier 1: Observable-Only Mode (Weeks 1-4)

> **Goal**: Functional backlog with zero RFC-045/044 dependency

#### Phase 1: Signal Extraction (Week 1)

- [ ] Implement `SignalExtractor` with test/todo/type error extractors
- [ ] Integrate with existing `GateType` from `src/sunwell/adaptive/gates.py`
- [ ] Reuse `classify_error()` from `src/sunwell/adaptive/signals.py`
- [ ] CLI: `sunwell signals` to view raw signals
- [ ] Tests for signal extraction

#### Phase 2: Goal Generation (Week 2)

- [ ] Implement `Goal` and `GoalGenerator`
- [ ] Priority scoring algorithm (severity × category × complexity)
- [ ] Dependency inference via topological sort
- [ ] CLI: `sunwell backlog` to view goals

#### Phase 3: Backlog Management (Week 3)

- [ ] Implement `Backlog` and `BacklogManager`
- [ ] Persistence (goals.jsonl, current.json)
- [ ] Refresh logic (on completion, on git events)
- [ ] CLI: `sunwell backlog add/skip/block`

#### Phase 4: Execution Loop (Week 4)

- [ ] Implement `AutonomousLoop` with propose/supervised modes
- [ ] Integration with `ArtifactPlanner` from `src/sunwell/naaru/planners/artifact.py`
- [ ] Integration with `AdaptiveAgent` from `src/sunwell/adaptive/agent.py`
- [ ] CLI: `sunwell backlog --execute`
- [ ] **Milestone**: Tier 1 complete, ship as v0.1

### Tier 2: Intelligence-Enhanced (Week 5)

> **Goal**: Add RFC-045 intelligence signals (optional enhancement)

#### Phase 5: Intelligence Integration (Week 5)

- [ ] Implement `IntelligenceAnalyzer` using actual RFC-045 API:
  - `DecisionMemory._decisions` for low-confidence/stale decisions
  - `FailureMemory._failures` for recurring failure clusters
- [ ] Add `CapabilityDetector` for runtime tier detection
- [ ] Context-aware priority scoring with relevance
- [ ] **Milestone**: Tier 2 complete, ship as v0.2

### Tier 3: Full Integration (Future — Depends on RFC-044)

#### Phase 6: Polish + Puzzle Integration

- [ ] Goal policy configuration
- [ ] Mermaid visualization export
- [ ] History/audit trail
- [ ] Documentation
- [ ] (Future) PuzzlePlanner integration when RFC-044 ships

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Signal accuracy | > 95% | Manual review of extracted signals |
| Goal relevance | > 80% | User accepts/executes generated goals |
| Priority accuracy | > 70% | User agrees with suggested order |
| Execution success | > 90% | Goals complete without manual intervention |
| Time to value | < 30s | From `sunwell backlog` to seeing prioritized goals |

---

## Future Work

1. **RFC-047: Deep Verification** — Semantic correctness beyond syntax
2. **RFC-048: Autonomy Guardrails** — Safe unsupervised operation
3. **RFC-049: External Integration** — CI/CD, issue trackers, production metrics
4. **RFC-050: Meta-Loop** — Sunwell improving itself
5. **RFC-051: Multi-Instance** — Parallel autonomous agents

---

## Summary

Autonomous Backlog transforms Sunwell from reactive to proactive by:

1. **Observing** — Extract signals from code state (tests, todos, types, lint)
2. **Generating** — Convert signals to prioritized goals with dependency inference
3. **Decomposing** — Apply artifact-first planning to each goal (RFC-036)
4. **Executing** — Use adaptive agent with appropriate techniques (RFC-042)
5. **Learning** — Record completions back into Project Intelligence (RFC-045, optional)

### Tiered Implementation

| Tier | Dependencies | Features | Time to Ship |
|------|--------------|----------|--------------|
| **Tier 1** | RFC-036, RFC-042 | Observable signals only, no LLM for goal discovery | Week 4 |
| **Tier 2** | + RFC-045 | Intelligence signals, context-aware priority | Week 5 |
| **Tier 3** | + RFC-044 | Puzzle decomposition for strategic goals | Future |

**The result**: Sunwell sees what's wrong, proposes how to fix it, and (with approval) does the work — like a senior engineer who doesn't need to be told what to do.

### Key Design Decisions

1. **Observable-first**: Tier 1 works with zero LLM calls for goal discovery
2. **Graceful degradation**: Features enhance progressively based on available components
3. **Bounded scope**: `GoalScope` prevents unbounded changes
4. **Human-in-loop**: Default is supervised mode; autonomous mode is opt-in

---

## References

### RFCs

- RFC-036: Artifact-First Planning — **Implemented**
- RFC-042: Adaptive Agent — **Implemented**
- RFC-044: Puzzle Planning — Draft (optional enhancement)
- RFC-045: Project Intelligence — **Partially Implemented**

### Implementation Files (Verified)

```
# RFC-036 Artifact-First Planning
src/sunwell/naaru/artifacts.py           # ArtifactSpec, ArtifactGraph
src/sunwell/naaru/planners/artifact.py   # ArtifactPlanner.discover_graph()

# RFC-042 Adaptive Agent
src/sunwell/adaptive/agent.py            # AdaptiveAgent
src/sunwell/adaptive/signals.py          # TaskSignals, ErrorSignals, classify_error()
src/sunwell/adaptive/gates.py            # GateType, ValidationGate
src/sunwell/adaptive/validation.py       # ValidationRunner

# RFC-045 Project Intelligence (partial)
src/sunwell/intelligence/__init__.py     # Module exports
src/sunwell/intelligence/context.py      # ProjectContext
src/sunwell/intelligence/decisions.py    # Decision, DecisionMemory
src/sunwell/intelligence/failures.py     # FailedApproach, FailureMemory
src/sunwell/intelligence/patterns.py     # PatternProfile, PatternLearner
src/sunwell/intelligence/codebase.py     # CodebaseGraph, CodebaseAnalyzer
```
