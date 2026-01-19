# RFC-042: Adaptive Agent — Signal-Driven Execution

**Status**: Draft (Revised)  
**Author**: Sunwell Team  
**Created**: 2026-01-19  
**Last Updated**: 2026-01-19

## Summary

Make all advanced features (Vortex, Compound Eye, Harmonic, Resonance) automatic by default. The agent uses cheap signals to decide when to apply expensive techniques. Users just say what they want; the infrastructure figures out how.

**Key additions:**
- Live streaming progress (no polling)
- Cost analysis with acceleration opportunities  
- Automatic technique selection via signals

## Motivation

Currently, users must opt-in to advanced features:

```bash
sunwell "Build forum app" --harmonic --candidates 5 --refine 2
```

This is backwards. The system has all the signals it needs to decide:
- Is this complex? → Use harmonic planning
- Is the model uncertain? → Use vortex
- Did something break? → Use compound eye + resonance

**Users shouldn't need to know about internal mechanisms.**

---

## Goals and Non-Goals

### Goals

1. **Automatic technique selection** — System decides when to use Vortex, Compound Eye, Harmonic, Resonance
2. **Zero-config default** — Simple `sunwell "goal"` works optimally without flags
3. **Live progress streaming** — Users see what's happening, reducing perceived wait time
4. **Fail-fast validation** — Catch errors early via gates, don't waste tokens on dependent work
5. **Graceful degradation** — Budget-aware downgrade from expensive to cheap techniques

### Non-Goals

1. **Automatic model selection** — Model choice remains user-configured (out of scope)
2. **Learning from history** — No persistent learning across sessions (future RFC)
3. **Multi-language parity** — Python-first; other languages are future work
4. **Distributed execution** — Single-machine execution only (no remote workers)
5. **Custom signal definitions** — Signal vocabulary is fixed; extensibility is future work

---

## Cost Analysis

> **Note**: Cost estimates below are based on representative workloads.
> Actual costs vary by model, task complexity, and content length.
> Numbers marked with `~` are estimates pending benchmark validation.

### Overhead Budget

| Component | Token Cost | Time | When |
|-----------|------------|------|------|
| Signal extraction | ~40 tokens | ~0.5s | Once per goal |
| Per-task signals | ~20 tokens | ~0.2s | Each task (batched) |
| Syntax check | **0** | ~10ms | Always |
| Import check | **0** | ~100ms | If syntax passes |
| Runtime check | **0** | ~3s | If imports pass |
| Compound Eye | ~5x base | ~10s | Only if errors |
| Vortex | ~15x base | ~30s | Only if low confidence |

### Real-World Example: Forum App (13 tasks)

> **⚠️ Estimates**: These numbers are projections based on component costs.
> Benchmark validation required before finalizing.

| Mode | Tokens | Time | Outcome |
|------|--------|------|---------|
| Current (single-shot) | ~8,000 | ~158s | Broken (SQLite error) |
| Current + human debug | ~8,000 | ~158s + 5min | Works |
| **Adaptive** | ~10,300 | ~195s | **Works automatically** |

**Hypothesis**: The overhead pays for itself by eliminating debug time.
**Validation needed**: Run benchmark comparing single-shot vs. adaptive on forum app task.

### When Overhead is Zero

Simple tasks skip expensive techniques entirely:

```
Signal: complexity=NO, needs_tools=NO
→ Skip harmonic, skip vortex, skip validation level 3
→ Result: Same cost as current, with safety net ready
```

---

## Acceleration Opportunities

The adaptive system can be **faster** than the current approach:

### 1. Streaming Validation (Hidden Latency)

```
CURRENT (Sequential):
┌──────────────────────────────────────────────────────┐
│ Task1 ──► Task2 ──► Task3 ──► ... ──► Validate All  │
│ ████████████████████████████████████████░░░░░░░░░░  │
│                                        ^ validation │
└──────────────────────────────────────────────────────┘

ADAPTIVE (Streaming):
┌──────────────────────────────────────────────────────┐
│ Task1 ──► Task2 ──► Task3 ──► ...                   │
│   └─✓       └─✓       └─✓     (validated in parallel)│
│ ████████████████████████████████████████            │
│ Validation hidden behind GPU latency                │
└──────────────────────────────────────────────────────┘

Savings: 5-10 seconds (validation runs while model generates)
```

### 2. Confidence-Based Shortcuts

```python
for task in tasks:
    if task.confidence > 0.85:
        # Fast path: single call
        result = await model.generate(task)          # 1 call
    elif task.confidence > 0.6:
        # Medium path: quick check
        result = await interference(task, n=3)       # 3 calls
    else:
        # Slow path: full exploration
        result = await vortex.solve(task)            # 15+ calls

# Most tasks are high-confidence → most skip expensive path
# Net effect: FEWER calls than always running vortex
```

### 3. Targeted Fixes (Not Whole-File Regeneration)

```
CURRENT:
  Error in posts.py → Regenerate entire file (500 tokens)

ADAPTIVE:
  Compound Eye finds: posts.py:8-20 is the hotspot
  → Fix only that region (100 tokens)
  
Savings: 5x fewer tokens for fixes
```

### 4. Speculative Execution (Free Parallelism)

```
While GPU generates Task N:
  CPU: Validate Task N-1           # Free (CPU idle anyway)
  CPU: Pre-extract signals N+1     # Free
  CPU: Compound Eye on errors      # Free
  
Result: CPU work completely hidden behind GPU latency
```

### 5. Early Termination

```
Signal: is_dangerous=YES
→ Stop immediately, ask user
→ Don't waste tokens on dangerous operations

Signal: confidence < 0.3
→ Ask for clarification instead of generating garbage
→ Saves 100% of wasted tokens
```

### Net Impact

| Scenario | Without Adaptive | With Adaptive |
|----------|------------------|---------------|
| Simple task, works | 10s | 11s (+10%) |
| Medium task, works | 60s | **52s (-13%)** via shortcuts |
| Complex task, works | 180s | **165s (-8%)** via shortcuts |
| **Any task, fails** | Time + debug | **Auto-fixed** |

---

## Validation Gates in Task Decomposition

**Key insight:** Don't validate at the end — build validation checkpoints INTO the task graph.

### Current: Validate After Everything

```
[Task 1] → [Task 2] → ... → [Task 13] → Validate All
                                              ↓
                                         ❌ Error in Task 7
                                         (but we already did 8-13)
```

Wasted work: Tasks 8-13 might depend on broken Task 7.

### Proposed: Validation Gates at Runnable Milestones

```
┌─────────────────────────────────────────────────────────────────┐
│                    TASK GRAPH WITH GATES                        │
│                                                                 │
│  [UserProtocol] ──┐                                             │
│  [PostProtocol] ──┼──► GATE 1: Import all protocols             │
│  [CommentProtocol]┘         │                                   │
│                             ▼                                   │
│                        ✅ Pass → continue                       │
│                        ❌ Fail → FIX before proceeding          │
│                             │                                   │
│                             ▼                                   │
│  [UserModel] ─────┐                                             │
│  [PostModel] ─────┼──► GATE 2: Create DB, run migrations        │
│  [CommentModel] ──┘         │                                   │
│                             ▼                                   │
│                        ✅ Pass → continue                       │
│                        ❌ Fail → FIX before proceeding          │
│                             │                                   │
│                             ▼                                   │
│  [UserRoutes] ────┐                                             │
│  [PostRoutes] ────┼──► GATE 3: Start server, test endpoints     │
│  [CommentRoutes] ─┘         │                                   │
│                             ▼                                   │
│                        ❌ FAIL: SQLite threading error          │
│                        ┌─────────────────────────────┐          │
│                        │ FIX before continuing       │          │
│                        │ (didn't waste tokens on     │          │
│                        │  AppFactory yet!)           │          │
│                        └─────────────────────────────┘          │
│                             │                                   │
│                             ▼ (after fix)                       │
│  [AppFactory] ────────► GATE 4: Full integration test           │
│                             │                                   │
│                             ▼                                   │
│                          ✅ DONE                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Benefits

| Benefit | Impact |
|---------|--------|
| **Early error detection** | Catch issues before wasting tokens on dependent tasks |
| **Incremental confidence** | Each gate pass = checkpoint save |
| **Smaller fix scope** | Only fix what's broken, not rebuild everything |
| **Resume from gate** | If interrupted, restart from last passed gate |
| **Parallel within gates** | Tasks before a gate can parallelize |

### Gate Types

The planner identifies natural validation boundaries:

```python
class GateType(Enum):
    """Types of validation gates in task decomposition."""
    
    # Static analysis (instant, free)
    SYNTAX = "syntax"          # Can we parse it? (py_compile)
    LINT = "lint"              # Does it pass ruff? (ruff check --fix)
    TYPE = "type"              # Does it pass type checking? (ty/mypy)
    
    # Import/instantiation (fast)
    IMPORT = "import"          # Can we import it?
    INSTANTIATE = "instantiate" # Can we create instances?
    
    # Runtime (slower but comprehensive)
    SCHEMA = "schema"          # Can we create DB schema?
    SERVE = "serve"            # Can we start the server?
    ENDPOINT = "endpoint"      # Do endpoints respond?
    INTEGRATION = "integration" # Does everything work together?


@dataclass(frozen=True, slots=True)
class ValidationGate:
    """A checkpoint in the task graph where we validate."""
    
    id: str
    gate_type: GateType
    depends_on: tuple[str, ...]  # Task IDs that must complete
    validation: str              # What to check
    blocks: tuple[str, ...]      # Task IDs blocked until gate passes
    
    # Auto-detected by planner
    is_runnable_milestone: bool = True  # Can we actually run something?


# Example gates for forum app
FORUM_APP_GATES = [
    ValidationGate(
        id="gate_protocols",
        gate_type=GateType.IMPORT,
        depends_on=("UserProtocol", "PostProtocol", "CommentProtocol"),
        validation="import src.protocols.*",
        blocks=("UserModel", "PostModel", "CommentModel"),
    ),
    ValidationGate(
        id="gate_models",
        gate_type=GateType.SCHEMA,
        depends_on=("UserModel", "PostModel", "CommentModel"),
        validation="Base.metadata.create_all(engine)",
        blocks=("UserRoutes", "PostRoutes", "CommentRoutes"),
    ),
    ValidationGate(
        id="gate_routes",
        gate_type=GateType.ENDPOINT,
        depends_on=("UserRoutes", "PostRoutes", "CommentRoutes"),
        validation="curl http://localhost:5000/health",
        blocks=("AppFactory",),
    ),
    ValidationGate(
        id="gate_integration",
        gate_type=GateType.INTEGRATION,
        depends_on=("AppFactory",),
        validation="pytest tests/integration/",
        blocks=(),
    ),
]
```

### Static Analysis at Every Gate (Language-Agnostic)

The gate system is designed to work with **any language**. Each language plugs in its own toolchain:

| Language | Lint | Type Check | Format |
|----------|------|------------|--------|
| **Python** | ruff | ty / mypy | ruff format |
| TypeScript | eslint | tsc | prettier |
| Rust | clippy | cargo check | rustfmt |
| Go | golint | go vet | gofmt |
| *Custom* | *configurable* | *configurable* | *configurable* |

```python
@dataclass(frozen=True, slots=True)
class LanguageToolchain:
    """Toolchain for a specific language."""
    
    language: str
    
    # Static analysis commands
    syntax_cmd: tuple[str, ...] | None = None
    lint_cmd: tuple[str, ...] | None = None
    lint_fix_cmd: tuple[str, ...] | None = None
    type_cmd: tuple[str, ...] | None = None
    format_cmd: tuple[str, ...] | None = None
    
    # File patterns
    file_glob: str = "*"


# Built-in toolchains
PYTHON_TOOLCHAIN = LanguageToolchain(
    language="python",
    syntax_cmd=("python", "-m", "py_compile"),
    lint_cmd=("ruff", "check", "--output-format=json"),
    lint_fix_cmd=("ruff", "check", "--fix"),
    type_cmd=("ty", "check"),  # or mypy
    format_cmd=("ruff", "format"),
    file_glob="*.py",
)

TYPESCRIPT_TOOLCHAIN = LanguageToolchain(
    language="typescript",
    lint_cmd=("eslint", "--format=json"),
    lint_fix_cmd=("eslint", "--fix"),
    type_cmd=("tsc", "--noEmit"),
    format_cmd=("prettier", "--write"),
    file_glob="*.ts",
)

# Auto-detect from project files
def detect_toolchain(project_path: Path) -> LanguageToolchain:
    if (project_path / "pyproject.toml").exists():
        return PYTHON_TOOLCHAIN
    if (project_path / "package.json").exists():
        return TYPESCRIPT_TOOLCHAIN
    if (project_path / "Cargo.toml").exists():
        return RUST_TOOLCHAIN
    # ... etc
```

**For now, we start with Python (ruff + ty). Other languages can be added as needed.**

Every gate runs a fast static analysis cascade FIRST:

```
┌─────────────────────────────────────────────────────────────────┐
│                    GATE VALIDATION CASCADE                      │
│                                                                 │
│  Step 1: SYNTAX (py_compile)                    ~10ms, free     │
│          └─ Can Python parse it?                                │
│                    │                                            │
│                    ▼                                            │
│  Step 2: LINT (ruff check)                      ~50ms, free     │
│          └─ Style, imports, common bugs                         │
│          └─ Auto-fix: ruff check --fix                          │
│                    │                                            │
│                    ▼                                            │
│  Step 3: TYPE (ty / mypy)                       ~500ms, free    │
│          └─ Type errors, missing annotations                    │
│          └─ Catches: wrong arg types, None checks, etc.         │
│                    │                                            │
│                    ▼                                            │
│  Step 4: GATE-SPECIFIC CHECK                    varies          │
│          └─ Import, schema, endpoint, etc.                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why this catches bugs early:**

```python
# Generated code with type error:
def get_user(user_id: str) -> User:
    return db.query(User).filter(User.id == user_id).first()
    #                                    ↑ User.id is int, not str!

# ty/mypy catches this BEFORE we try to run:
# error: Argument of type "str" cannot be assigned to parameter of type "int"

# Fix prompt to model:
"The type checker found: User.id is int but you're comparing to str.
 Fix get_user() to accept int, or convert the parameter."
```

**Ruff auto-fix handles style automatically:**

```python
# Generated:
from typing import List, Dict, Optional
import os
import sys
from flask import Flask
import json

# After ruff --fix:
import json
import os
import sys
from typing import Optional  # List, Dict removed (use builtins)

from flask import Flask
```

### Lint/Type Fix Strategy

```python
class StaticAnalysisFixer:
    """Fixes lint and type errors at gates."""
    
    async def fix_at_gate(self, artifacts: list[Artifact]) -> FixResult:
        # Step 1: Ruff auto-fix (deterministic, no LLM needed)
        for artifact in artifacts:
            subprocess.run(["ruff", "check", "--fix", artifact.path])
        
        # Step 2: Check for remaining lint errors
        lint_result = subprocess.run(
            ["ruff", "check", "--output-format=json", *paths],
            capture_output=True,
        )
        lint_errors = json.loads(lint_result.stdout)
        
        # Step 3: Type check
        type_result = subprocess.run(
            ["ty", "check", *paths],  # or mypy
            capture_output=True,
        )
        type_errors = parse_type_errors(type_result.stdout)
        
        # Step 4: If errors remain, ask model to fix
        if lint_errors or type_errors:
            return await self._llm_fix(artifacts, lint_errors, type_errors)
        
        return FixResult(success=True)
    
    async def _llm_fix(
        self,
        artifacts: list[Artifact],
        lint_errors: list[LintError],
        type_errors: list[TypeError],
    ) -> FixResult:
        """Use LLM to fix errors that ruff --fix couldn't handle."""
        
        # Build targeted fix prompt
        prompt = f"""Fix these errors in the code:

Lint errors (ruff):
{self._format_lint_errors(lint_errors)}

Type errors (ty):
{self._format_type_errors(type_errors)}

Rules:
- Use Python 3.14 syntax (list[str] not List[str])
- Use X | None not Optional[X]
- All public functions need type annotations
- Follow ruff rules: {RUFF_RULES}
"""
        
        # Targeted fix (only the error regions, not whole files)
        for error in lint_errors + type_errors:
            region = self._get_error_region(error)
            fix = await self.model.generate(
                f"{prompt}\n\nFix this specific region:\n```\n{region}\n```"
            )
            self._apply_targeted_fix(error.file, error.line, fix)
        
        return FixResult(success=True)
```

### Planner Gate Detection

The planner automatically identifies gates by looking for:

```python
class GateDetector:
    """Detects natural validation boundaries in task graph."""
    
    def detect_gates(self, tasks: list[Task]) -> list[ValidationGate]:
        """Find runnable milestones in task graph."""
        gates = []
        
        # Pattern 1: Protocol/Interface completion
        protocols = [t for t in tasks if "protocol" in t.artifact_type.lower()]
        if protocols:
            gates.append(self._make_import_gate(protocols))
        
        # Pattern 2: Model/Schema completion
        models = [t for t in tasks if "model" in t.artifact_type.lower()]
        if models:
            gates.append(self._make_schema_gate(models))
        
        # Pattern 3: Route/Endpoint completion
        routes = [t for t in tasks if "route" in t.artifact_type.lower()]
        if routes:
            gates.append(self._make_endpoint_gate(routes))
        
        # Pattern 4: App factory / main entry point
        entry_points = [t for t in tasks if t.is_entry_point]
        if entry_points:
            gates.append(self._make_integration_gate(entry_points))
        
        # Pattern 5: Explicit test tasks
        tests = [t for t in tasks if "test" in t.artifact_type.lower()]
        for test_task in tests:
            gates.append(self._make_test_gate(test_task))
        
        return gates
    
    def _is_runnable_milestone(self, tasks: list[Task]) -> bool:
        """Check if completing these tasks gives us something we can run."""
        # Heuristic: If tasks produce importable modules, we can validate
        return all(t.produces_module for t in tasks)
```

### Streaming UX with Gates

```
$ sunwell "Build forum app"

🎯 Understanding goal...
   └─ route: CONTRACT_FIRST with 4 validation gates

📋 Plan:
   Gate 1: Protocols (lint + type + import)
   Gate 2: Models (lint + type + schema)  
   Gate 3: Routes (lint + type + endpoints)
   Gate 4: Integration (full test)

⚡ Executing...

   ═══════════════════════════════════════════
   GATE 1: Protocols
   ═══════════════════════════════════════════
   
   [1-3/13] Protocols (parallel)
            ████████████████████ ✓✓✓
   
   🔍 Gate validation:
      ├─ syntax   ✅ (3/3 files parse)
      ├─ lint     ⚠️ 2 issues → ruff --fix → ✅
      ├─ type     ✅ (ty: no errors)
      └─ import   ✅ (all importable)
   
   ═══════════════════════════════════════════
   GATE 2: Models  
   ═══════════════════════════════════════════
   
   [4-6/13] Models (parallel)
            ████████████████████ ✓✓✓
   
   🔍 Gate validation:
      ├─ syntax   ✅
      ├─ lint     ✅
      ├─ type     ⚠️ 1 error: User.id expects int, got str
      │           └─ 🔧 Fixed: user_id: str → user_id: int
      └─ schema   ✅ (tables created)
   
   ═══════════════════════════════════════════
   GATE 3: Routes
   ═══════════════════════════════════════════
   
   [7-9/13] Routes (parallel)
            ████████████████████ ✓✓✓
   
   🔍 Gate validation:
      ├─ syntax   ✅
      ├─ lint     ⚠️ import order → ruff --fix → ✅
      ├─ type     ✅
      └─ endpoint ❌ POST /posts → 500
                  sqlite3.ProgrammingError: threading...
   
   🔧 Fixing before continuing...
      ├─ Compound Eye: hotspot at posts.py:8-20
      ├─ Fix applied: per-request connections
      └─ Re-checking gate...
      └─ endpoint ✅ POST /posts → 201 Created
   
   ═══════════════════════════════════════════
   GATE 4: Integration
   ═══════════════════════════════════════════
   
   [10-13/13] App + tests
            ████████████████████ ✓✓✓✓
   
   🔍 Gate validation:
      ├─ syntax   ✅
      ├─ lint     ✅
      ├─ type     ✅
      └─ tests    ✅ (pytest: 12 passed)

✨ Complete: 4/4 gates passed (195s)
   ├─ Auto-fixed: 3 lint issues (ruff --fix)
   ├─ Auto-fixed: 1 type error (User.id type)
   └─ Auto-fixed: 1 runtime error (SQLite threading)
```

### Incremental Re-runs with Gates

Gates enable smart re-runs:

```bash
# First run fails at Gate 3
sunwell "Build forum app"
# ... fails, user Ctrl+C's ...

# Second run: resume from last passed gate
sunwell "Build forum app" --resume
# Skips Gate 1, 2 (already validated)
# Starts from Gate 3

# Or force full rebuild
sunwell "Build forum app" --force
```

### Gate Metadata for Debugging

```python
@dataclass
class GateResult:
    """Result of passing through a validation gate."""
    
    gate: ValidationGate
    passed: bool
    duration_ms: int
    validation_output: str
    
    # For resume capability
    checkpoint_hash: str  # Hash of all artifacts at this point
    artifacts_snapshot: dict[str, str]  # path → content hash
    
    # For debugging
    commands_run: list[str]
    errors: list[str]
```

---

## Simulacrum Integration — Persistent Memory

The adaptive agent wires into Simulacrum for persistent, cross-session memory. This enables:
- Multi-day autonomous tasks
- Learning from past attempts
- Avoiding known dead ends
- Remembering code style preferences

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 SIMULACRUM + ADAPTIVE AGENT                     │
│                                                                 │
│  Session Start:                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Load Simulacrum                                          │  │
│  │  ├─ Learnings: "User.id is int, not str"                  │  │
│  │  ├─ Dead Ends: "sync wrappers block event loop"           │  │
│  │  ├─ Identity: "prefers explicit > implicit"               │  │
│  │  └─ Context: "working on auth module refactor"            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  Planning Phase:                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Inject learnings into prompts                            │  │
│  │  Filter out approaches that hit dead ends                 │  │
│  │  Apply identity preferences (code style, etc.)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  Gate Execution:                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  After each gate:                                         │  │
│  │  ├─ Extract new learnings from generated code             │  │
│  │  ├─ Record dead ends if fix failed                        │  │
│  │  ├─ Checkpoint Simulacrum to disk                         │  │
│  │  └─ Memory survives crashes, Ctrl+C, power loss           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  Session End:                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Persist all learnings                                    │  │
│  │  Update identity with observed preferences                │  │
│  │  Ready for next session (tomorrow, next week, whenever)   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
@dataclass
class AdaptiveAgent:
    """Adaptive agent with Simulacrum integration."""
    
    model: ModelProtocol
    simulacrum: SimulacrumStore | None = None
    
    async def run(
        self,
        goal: str,
        session: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute goal with persistent memory."""
        
        # Load Simulacrum if session provided
        if session:
            yield AgentEvent(EventType.MEMORY_LOAD, {"session": session})
            self.simulacrum = SimulacrumStore(Path(".sunwell/memory"))
            
            try:
                self.simulacrum.load_session(session)
                yield AgentEvent(EventType.MEMORY_LOADED, {
                    "learnings": len(self.simulacrum.dag.learnings),
                    "dead_ends": len(self.simulacrum.dag.dead_ends),
                    "turns": len(self.simulacrum.dag.turns),
                })
            except FileNotFoundError:
                self.simulacrum.new_session(session)
                yield AgentEvent(EventType.MEMORY_NEW, {"session": session})
        
        # Extract signals with memory context
        signals = await self._extract_signals_with_memory(goal)
        
        # Plan with learnings injected
        plan = await self._plan_with_memory(goal, signals)
        
        # Execute with gate checkpoints
        async for event in self._execute_with_checkpoints(plan):
            yield event
        
        # Persist on completion
        if self.simulacrum:
            self.simulacrum.save_session()
            yield AgentEvent(EventType.MEMORY_SAVED, {
                "learnings": len(self.simulacrum.dag.learnings),
            })
    
    async def _extract_signals_with_memory(self, goal: str) -> SignalVector:
        """Extract signals, informed by past learnings."""
        
        # Base signal extraction
        signals = await extract_signals(goal, self.model)
        
        # Boost confidence if we have relevant learnings
        if self.simulacrum:
            relevant = self.simulacrum.dag.get_learnings_for(goal)
            if relevant:
                signals = signals.with_memory_boost(len(relevant))
        
        return signals
    
    async def _plan_with_memory(
        self,
        goal: str,
        signals: SignalVector,
    ) -> TaskGraph:
        """Plan with learnings and dead ends considered."""
        
        # Build context from memory
        memory_context = ""
        if self.simulacrum:
            # Inject relevant learnings
            learnings = self.simulacrum.dag.get_learnings_for(goal)
            if learnings:
                memory_context += "Known facts from previous work:\n"
                for l in learnings[:10]:  # Top 10 most relevant
                    memory_context += f"- {l.fact}\n"
            
            # Warn about dead ends
            dead_ends = self.simulacrum.dag.get_dead_ends_for(goal)
            if dead_ends:
                memory_context += "\nApproaches that didn't work:\n"
                for de in dead_ends[:5]:
                    memory_context += f"- {de.approach}: {de.reason}\n"
            
            # Apply identity preferences
            if self.simulacrum.identity.code_style:
                memory_context += f"\nCode style: {self.simulacrum.identity.code_style}\n"
        
        # Plan with memory context
        return await self.planner.plan(
            goal=goal,
            signals=signals,
            context=memory_context,
        )
    
    async def _checkpoint_at_gate(self, gate: ValidationGate, result: GateResult):
        """Checkpoint memory after each gate."""
        
        if not self.simulacrum:
            return
        
        # Extract learnings from generated code
        for artifact in result.artifacts:
            learnings = await self._extract_learnings(artifact)
            for learning in learnings:
                self.simulacrum.dag.add_learning(learning)
        
        # Record dead ends if fix failed
        if not result.passed and result.fix_attempts >= 3:
            self.simulacrum.dag.add_dead_end(DeadEnd(
                approach=result.failed_approach,
                reason=result.failure_reason,
                gate=gate.id,
            ))
        
        # Checkpoint to disk (survives crashes)
        self.simulacrum.save_session()
```

### Multi-Day Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-DAY EXAMPLE                            │
│                                                                 │
│  Monday:                                                        │
│  $ sunwell "Refactor backend to async" --session async-refactor │
│                                                                 │
│    📋 Planning: 47 tasks, 8 gates                               │
│    ⚡ Executing...                                              │
│       GATE 1: Interfaces ✅                                     │
│       GATE 2: Core models ✅                                    │
│       GATE 3: Database layer ❌ (connection pool issues)        │
│          └─ Tried: sync wrappers → blocked event loop           │
│          └─ Dead end recorded                                   │
│    💾 Session saved (12 learnings, 1 dead end)                  │
│    [User goes home]                                             │
│                                                                 │
│  Tuesday:                                                       │
│  $ sunwell --resume --session async-refactor                    │
│                                                                 │
│    📂 Loaded session: 12 learnings, 1 dead end                  │
│    ⚡ Resuming from GATE 3...                                   │
│       └─ Avoiding: sync wrappers (known dead end)               │
│       └─ Trying: proper async connection pool                   │
│       GATE 3: Database layer ✅                                 │
│       GATE 4: Services ✅                                       │
│    💾 Session saved (18 learnings)                              │
│    [User goes home]                                             │
│                                                                 │
│  Wednesday:                                                     │
│  $ sunwell chat --session async-refactor                        │
│                                                                 │
│    You: "What did we learn about async patterns?"               │
│                                                                 │
│    Sunwell: "From our refactoring work, I learned:              │
│     - SQLAlchemy async requires create_async_engine             │
│     - Don't use sync wrappers (blocks event loop)               │
│     - Connection pools need async context managers              │
│     - ..."                                                      │
│                                                                 │
│  A year later:                                                  │
│  $ sunwell "Add new async endpoint" --session async-refactor    │
│                                                                 │
│    📂 Loaded session: 18 learnings                              │
│    └─ Applies everything learned last year                      │
│    └─ Avoids the same mistakes                                  │
│    └─ Consistent with established patterns                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Memory-Aware Streaming UX

```
$ sunwell "Build user dashboard" --session dashboard-v2

📂 Loading session: dashboard-v2
   ├─ 7 learnings from previous work
   ├─ 2 dead ends to avoid
   └─ Identity: "prefers functional components, TypeScript strict"

🎯 Understanding goal...
   ├─ complexity: YES
   ├─ memory_boost: +15% confidence (relevant learnings found)
   └─ route: HARMONIC_PLANNING

📋 Planning...
   ├─ Injecting learnings: "User model uses UUID, not int"
   ├─ Avoiding dead end: "Redux for local state (too complex)"
   └─ Applying style: functional components, TypeScript strict

⚡ Executing...

   ═══════════════════════════════════════════
   GATE 1: Types & Interfaces
   ═══════════════════════════════════════════
   
   [1-3/12] Types (parallel)
            ████████████████████ ✓✓✓
   
   🔍 Gate validation: ✅
   📚 New learning: "Dashboard uses DashboardConfig type"
   💾 Checkpoint saved

   ... (continues) ...

✨ Complete: 4/4 gates passed
   ├─ Learnings: 7 → 11 (+4 new)
   ├─ Dead ends: 2 (none added)
   └─ Session saved for future use
```

### CLI Integration

```bash
# Start new session
sunwell "Build feature" --session my-feature

# Resume existing session
sunwell --resume --session my-feature

# Continue from specific gate
sunwell --resume --session my-feature --from-gate 3

# Chat with session memory
sunwell chat --session my-feature

# List sessions
sunwell sessions list
# my-feature     12 learnings, Gate 4/4, last active 2 hours ago
# async-refactor 18 learnings, Gate 8/8, last active 3 days ago
# auth-module    5 learnings, Gate 2/5, last active 1 week ago

# Export session learnings
sunwell sessions export my-feature --format markdown
```

### Learning Extraction

The agent extracts learnings from generated code and fix attempts:

```python
class LearningExtractor:
    """Extracts learnings from agent work."""
    
    async def extract_from_artifact(
        self,
        artifact: Artifact,
        model: ModelProtocol,
    ) -> list[Learning]:
        """Extract learnings from generated code."""
        
        # Pattern-based extraction (fast, no LLM)
        learnings = []
        
        # Type definitions
        for type_def in self._find_type_definitions(artifact.content):
            learnings.append(Learning(
                fact=f"{type_def.name} has fields: {type_def.fields}",
                category="type",
                confidence=0.9,
            ))
        
        # API patterns
        for endpoint in self._find_endpoints(artifact.content):
            learnings.append(Learning(
                fact=f"Endpoint {endpoint.method} {endpoint.path} exists",
                category="api",
                confidence=0.9,
            ))
        
        # LLM extraction for deeper insights (optional, more expensive)
        if artifact.is_complex:
            llm_learnings = await self._llm_extract(artifact, model)
            learnings.extend(llm_learnings)
        
        return learnings
    
    async def extract_from_fix(
        self,
        error: ValidationError,
        fix: str,
        success: bool,
    ) -> Learning | DeadEnd:
        """Extract learning or dead end from fix attempt."""
        
        if success:
            return Learning(
                fact=f"Fixed '{error.type}' by: {self._summarize_fix(fix)}",
                category="fix_pattern",
                confidence=0.85,
            )
        else:
            return DeadEnd(
                approach=self._summarize_fix(fix),
                reason=error.message,
                context=error.context,
            )
```

---

## Live Streaming UX

**Critical insight:** Users accept longer times if they see progress. Silent waiting is anxiety-inducing.

### Current UX (Bad)

```
$ sunwell "Build forum app"
[nothing for 2 minutes]
✨ Complete
```

User thinks: "Is it stuck? Should I Ctrl+C?"

### Adaptive UX (Good)

```
$ sunwell "Build forum app"

🎯 Understanding goal...
   ├─ complexity: YES (multi-component)
   ├─ needs_tools: YES
   └─ route: HARMONIC_PLANNING

📋 Planning... (3 candidates)
   ├─ Protocol-first ████████████ 0.85
   ├─ Model-first    ████████░░░░ 0.72  
   └─ Route-first    ███████░░░░░ 0.68
   Winner: Protocol-first

⚡ Executing 13 tasks...
   
   [1/13] UserProtocol
          confidence: 0.92 → single-shot
          ████████████████████ ✓ 2.1s
   
   [2-3/13] PostProtocol, UserModel (parallel)
          ████████████████████ ✓✓ 3.4s
   
   [4-8/13] 5 tasks in parallel
          ████████████████░░░░ 72%
          ├─ CommentModel ✓
          ├─ UpvoteModel ✓
          ├─ UserRoutes (vortex: low confidence)
          │    └─ discovery ███░░ 3/6 signals
          ├─ UpvoteProtocol ✓
          └─ CommentProtocol ✓

🔍 Validating...
   ├─ Syntax   ✓ (13/13 files)
   ├─ Imports  ✓ (13/13 modules)  
   └─ Runtime  ⚠ testing endpoints...
               POST /posts → 500 Internal Server Error
               
   ❌ sqlite3.ProgrammingError: SQLite objects created 
      in a thread can only be used in that same thread

🔧 Auto-fixing...
   ├─ Compound Eye: scanning error region
   │    └─ Hotspot: src/routes/posts.py:8-20
   ├─ Signal: threading_issue=YES → VORTEX
   ├─ Vortex discovery: 4 candidates
   │    ├─ "per-request connection" 0.89 ←
   │    ├─ "connection pool" 0.76
   │    ├─ "check_same_thread=False" 0.54
   │    └─ "async wrapper" 0.41
   └─ Applying fix...

🔍 Re-validating...
   └─ Runtime  ✓ POST /posts → 201 Created

✨ Complete: 13/13 tasks (195s)
   └─ Auto-fixed 1 issue
```

### Implementation: Event Stream

```python
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator

class EventType(Enum):
    # Memory events
    MEMORY_LOAD = "memory_load"
    MEMORY_LOADED = "memory_loaded"
    MEMORY_NEW = "memory_new"
    MEMORY_LEARNING = "memory_learning"
    MEMORY_DEAD_END = "memory_dead_end"
    MEMORY_CHECKPOINT = "memory_checkpoint"
    MEMORY_SAVED = "memory_saved"
    
    # Signal events
    SIGNAL = "signal"
    
    # Planning events
    PLAN_START = "plan_start"
    PLAN_CANDIDATE = "plan_candidate"
    PLAN_WINNER = "plan_winner"
    
    # Execution events
    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    
    # Validation events
    VALIDATE_START = "validate_start"
    VALIDATE_LEVEL = "validate_level"
    VALIDATE_ERROR = "validate_error"
    
    # Fix events
    FIX_START = "fix_start"
    FIX_PROGRESS = "fix_progress"
    FIX_COMPLETE = "fix_complete"
    
    # Completion
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class AgentEvent:
    """A single event in the agent stream."""
    type: EventType
    data: dict
    timestamp: float


class AdaptiveAgent:
    """Agent that streams events as it works."""
    
    async def run(self, goal: str) -> AsyncIterator[AgentEvent]:
        """Execute goal, yielding events as they happen."""
        
        # Signal extraction
        yield AgentEvent(EventType.SIGNAL, {"status": "extracting"}, time())
        signals = await self._extract_signals(goal)
        yield AgentEvent(EventType.SIGNAL, {"signals": signals.to_dict()}, time())
        
        # Planning
        yield AgentEvent(EventType.PLAN_START, {"technique": signals.planning_route}, time())
        async for event in self._plan_with_events(goal, signals):
            yield event
        
        # Execution
        async for event in self._execute_with_events(self.plan):
            yield event
        
        # Validation (streaming)
        async for event in self._validate_with_events(self.artifacts):
            yield event
            
            # If error, auto-fix
            if event.type == EventType.VALIDATE_ERROR:
                async for fix_event in self._fix_with_events(event.data["errors"]):
                    yield fix_event
        
        yield AgentEvent(EventType.COMPLETE, {"success": True}, time())
```

### CLI Renderer

```python
from rich.live import Live
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

class StreamingRenderer:
    """Renders agent events to terminal in real-time."""
    
    def __init__(self):
        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
    
    async def render(self, events: AsyncIterator[AgentEvent]):
        """Render events as they stream in."""
        
        with Live(self.progress, console=self.console, refresh_per_second=10):
            async for event in events:
                self._handle_event(event)
    
    def _handle_event(self, event: AgentEvent):
        match event.type:
            case EventType.SIGNAL:
                self._render_signals(event.data)
            case EventType.TASK_START:
                self._add_task_progress(event.data)
            case EventType.TASK_PROGRESS:
                self._update_task_progress(event.data)
            case EventType.VALIDATE_ERROR:
                self._render_error(event.data)
            # ... etc
```

### Quiet Mode (for CI/scripts)

```bash
# Full streaming (default, interactive)
sunwell "Build app"

# Quiet mode (CI/scripts)
sunwell "Build app" --quiet
# Only outputs: final status, errors, file list

# JSON mode (programmatic)
sunwell "Build app" --json
# Outputs: newline-delimited JSON events
```

---

## Design Alternatives

Three approaches were considered for adaptive technique selection:

### Option A: Rule-Based Routing (Recommended)

**Description**: Static rules map signals to techniques. Signal extraction uses cheap LLM call (~40 tokens), then deterministic routing table selects technique.

```python
# Example routing rules
if signals.complexity == "YES":
    planner = HarmonicPlanner(candidates=5)
elif signals.complexity == "NO":
    planner = SingleShotPlanner()

if task.confidence < 0.6:
    executor = VortexExecutor()
else:
    executor = DirectExecutor()
```

| Pros | Cons |
|------|------|
| Predictable, debuggable | May miss edge cases |
| Zero learning overhead | Requires manual tuning |
| Fast routing (~0.5s) | Rules may become stale |

### Option B: Learned Router

**Description**: Train a small classifier on historical (task, technique, outcome) triples to predict optimal technique.

| Pros | Cons |
|------|------|
| Adapts to actual usage | Requires training data |
| Catches edge cases | Black box decisions |
| Improves over time | Cold start problem |

**Why not chosen**: Requires significant data collection infrastructure and introduces debugging complexity. Future RFC could add this as an enhancement.

### Option C: Always-On Expensive

**Description**: Run all techniques (Harmonic + Vortex + Compound Eye) for every task, select best result.

| Pros | Cons |
|------|------|
| Maximum quality | 15-20x cost increase |
| No routing errors | Unacceptable latency |
| Simple implementation | Wasteful for simple tasks |

**Why not chosen**: Cost prohibitive. Violates the goal of making adaptive the default.

### Decision: Option A (Rule-Based Routing)

Rule-based routing provides the best balance of:
- **Debuggability**: Clear signal → technique mapping
- **Performance**: Minimal overhead for simple tasks
- **Extensibility**: Rules can be tuned based on observed patterns

The routing table in this RFC (see Signal-Based Routing Table) implements Option A.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Signal extraction is wrong** | Medium | High | Fallback to single-shot if confidence < 0.3; allow `--force-technique` override |
| **Gates add too much latency** | Low | Medium | Run static analysis (syntax/lint/type) in parallel; skip gates with `--no-gates` |
| **Fix loop doesn't converge** | Medium | High | Hard limit of 3 fix attempts; escalate to user after limit |
| **Budget exhausted mid-task** | Low | Medium | Reserve 20% budget for fixes; graceful degradation to cheaper techniques |
| **Streaming overwhelms terminal** | Low | Low | Rate-limit events to 10/sec; `--quiet` mode for CI |
| **Compound Eye misidentifies hotspot** | Medium | Medium | Show top-3 hotspots, not just top-1; user can override with `--fix-file` |

### Failure Modes

1. **Signal extraction timeout**: Default to `complexity=YES, needs_tools=YES` (conservative)
2. **Gate validation hangs**: 30s timeout per gate; skip to next gate on timeout
3. **Model unavailable mid-execution**: Save checkpoint, allow `--resume` from last gate

---

## Design

### The Adaptive Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADAPTIVE AGENT                              │
│                                                                 │
│  User: "Build a Flask forum app"                                │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              1. SIGNAL EXTRACTION                        │   │
│  │                                                          │   │
│  │  complexity:    YES (multi-component app)                │   │
│  │  needs_tools:   YES (file operations)                    │   │
│  │  is_ambiguous:  MAYBE (forum could mean many things)     │   │
│  │  is_dangerous:  NO                                       │   │
│  │                                                          │   │
│  │  → Route: HARMONIC_PLANNING + CONTRACT_EXECUTION         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              2. ADAPTIVE PLANNING                        │   │
│  │                                                          │   │
│  │  complexity=YES → Generate 3-5 plan candidates           │   │
│  │  is_ambiguous=MAYBE → Use dialectic to resolve           │   │
│  │  Agreement > 0.8 → Pick winner                           │   │
│  │  Agreement < 0.5 → Request clarification                 │   │
│  │                                                          │   │
│  │  → Output: Task graph with confidence scores             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              3. ADAPTIVE EXECUTION                       │   │
│  │                                                          │   │
│  │  For each task:                                          │   │
│  │    Extract task-level signals                            │   │
│  │    confidence > 0.8 → Single-shot generation             │   │
│  │    confidence < 0.6 → Vortex pipeline for this task      │   │
│  │    is_critical=YES → Extra verification                  │   │
│  │                                                          │   │
│  │  → Output: Generated artifacts                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              4. STREAMING VALIDATION                     │   │
│  │                                                          │   │
│  │  Runs IN PARALLEL with execution (hidden latency)        │   │
│  │                                                          │   │
│  │  Level 1: Syntax (py_compile) ─────────────────┐        │   │
│  │  Level 2: Import (try import) ─────────────────┤        │   │
│  │  Level 3: Runtime (start, curl) ───────────────┤        │   │
│  │                                         │      │        │   │
│  │  Any failures? ─────────────────────────┼──────┘        │   │
│  │         │                               │               │   │
│  │         ▼                               ▼               │   │
│  │    Go to FIX               All pass → DONE              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              5. ADAPTIVE FIX (if needed)                 │   │
│  │                                                          │   │
│  │  Compound Eye: Scan error regions                        │   │
│  │    - Lateral inhibition: Where does signal change?       │   │
│  │    - Temporal diff: What's unstable?                     │   │
│  │    - Hotspots: Edges + Unstable = priority               │   │
│  │                                                          │   │
│  │  Signal the error type:                                  │   │
│  │    syntax_error → Direct fix (high confidence)           │   │
│  │    import_error → Dependency resolution                  │   │
│  │    runtime_error → Vortex for fix candidates             │   │
│  │    test_failure → Dialectic (why vs how to fix)          │   │
│  │                                                          │   │
│  │  Resonance: Loop until validation passes                 │   │
│  │    max_attempts=3                                        │   │
│  │    escalate if stuck                                     │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│                       DONE                                      │
│                       (events streamed throughout)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Signal-Based Routing Table

| Signal | Value | Action |
|--------|-------|--------|
| `complexity` | NO | Single-shot planning |
| `complexity` | YES | Harmonic planning (3-5 candidates) |
| `is_ambiguous` | YES | Dialectic before execution |
| `confidence` | > 0.85 | Single-shot (fast path) |
| `confidence` | 0.6-0.85 | Interference only (medium path) |
| `confidence` | < 0.6 | Vortex (slow path) |
| `confidence` | < 0.3 | Request clarification |
| `error_type` | syntax | Direct fix (cheap) |
| `error_type` | runtime | Compound Eye → Vortex → Resonance |
| `hotspot_count` | > 3 | Escalate to larger model |
| `is_dangerous` | YES | Stop, ask user |

### Cost Awareness

```python
@dataclass
class AdaptiveBudget:
    """Token budget with automatic economization."""
    
    total_budget: int = 50_000
    spent: int = 0
    
    # Cost multipliers
    single_shot: float = 1.0
    interference: float = 3.0
    harmonic_3: float = 3.5
    harmonic_5: float = 6.0  
    vortex: float = 15.0
    compound_eye: float = 5.0
    resonance_per_loop: float = 2.0
    
    def route_for_budget(self, ideal: str, base_cost: int) -> str:
        """Downgrade technique if budget is tight."""
        if self._can_afford(ideal, base_cost):
            return ideal
        
        # Downgrade path
        downgrades = {
            "vortex": "interference",
            "harmonic_5": "harmonic_3",
            "harmonic_3": "single_shot",
            "interference": "single_shot",
            "compound_eye": "lateral_only",
        }
        
        fallback = downgrades.get(ideal, "single_shot")
        if self._can_afford(fallback, base_cost):
            return fallback
        return "single_shot"
```

---

## Comparison with Other Agent Tools

### Feature Comparison

| Capability | Sunwell Adaptive | Aider | Cursor | Devin | CrewAI |
|----|----|----|----|----|----|
| **Multi-day tasks** | ✅ Simulacrum | ❌ | ❌ | ✅ | ❌ |
| **Cross-session memory** | ✅ Learnings + dead ends | ❌ | ❌ | Partial | ❌ |
| **Self-healing fixes** | ✅ Compound Eye + Vortex | Partial | ❌ | ✅ | ❌ |
| **Streaming UX** | ✅ Rich events | ✅ | ✅ | ✅ | ❌ |
| **Validation gates** | ✅ Per-milestone | ❌ | ❌ | ❌ | ❌ |
| **Adaptive routing** | ✅ Signal-driven | ❌ | ❌ | Unknown | ❌ |
| **Multi-model synthesis** | ✅ Vortex + Harmonic | ❌ | ❌ | Unknown | ✅ |
| **Budget-aware** | ✅ Auto-downgrade | ✅ | ✅ | ❌ | ❌ |
| **Chat about code** | ✅ With memory | ✅ | ✅ | ✅ | ❌ |
| **Local-first** | ✅ Ollama | ❌* | ❌ | ❌ | ✅ |
| **Resume from crash** | ✅ Gate checkpoints | ❌ | ❌ | ✅ | ❌ |
| **Learn from mistakes** | ✅ Dead ends | ❌ | ❌ | Partial | ❌ |

*Aider supports local models but experience is degraded

### Key Differentiators

**1. Simulacrum (Persistent Memory)**

No other tool remembers learnings across sessions:
- Start Monday, stop mid-task, resume Wednesday
- Mistakes from January inform work in March
- "Chat about code" includes full project history
- Identity preferences persist (code style, testing approach)

```
Other tools: Each session starts fresh
Sunwell:     Each session builds on all previous ones
```

**2. Adaptive Routing (Signal-Driven)**

No other tool automatically selects techniques:
- Simple change? Single-shot (fast, cheap)
- Complex change? Harmonic planning (multi-candidate)
- Runtime error? Vortex → Compound Eye → Resonance

```
Other tools: Fixed pipeline, same cost for all tasks
Sunwell:     Variable pipeline, cost matches complexity
```

**3. Validation Gates**

No other tool validates at milestones:
- Types wrong? Stop before writing routes
- API contract broken? Stop before integration
- Catches errors early, saves tokens

```
Other tools: Generate everything, validate at end, fix everything
Sunwell:     Validate incrementally, fix targeted errors
```

**4. Multi-Model Synthesis (Vortex + Harmonic)**

Most tools: Single model, single attempt, hope for the best.

Sunwell: Multiple models (or temps), discover options, synthesize best.

```
Other tools: 1 attempt, then manual fix
Sunwell:     N candidates, automatic selection, consensus-driven
```

### Positioning Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT LANDSCAPE                           │
│                                                                 │
│  Chat/Completion ────────────────────────────────▶ Autonomous   │
│        │                                                │       │
│        │  Cursor, Copilot                               │       │
│        │    └─ Good at edits                            │       │
│        │    └─ No memory                                │       │
│        │    └─ Single-shot                              │       │
│        │                                                │       │
│        │          Aider                                 │       │
│        │            └─ Good at git workflow             │       │
│        │            └─ No persistence                   │       │
│        │            └─ Single model                     │       │
│        │                                                │       │
│        │                    CrewAI                      │       │
│        │                      └─ Multi-agent            │       │
│        │                      └─ No code focus          │       │
│        │                      └─ No memory              │       │
│        │                                                │       │
│        │                              Devin             │       │
│        │                                └─ Autonomous   │       │
│        │                                └─ Cloud-only   │       │
│        │                                └─ Black box    │       │
│        │                                                │       │
│        │                                    SUNWELL     │       │
│        │                                      └─ Multi-day       │
│        │                                      └─ Learns          │
│        │                                      └─ Local-first     │
│        │                                      └─ Adaptive        │
│        │                                      └─ Transparent     │
│        │                                                │       │
│  Single-turn ────────────────────────────────▶ Multi-day        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Sunwell's Unique Value Proposition

**"The agent that gets better over time."**

- Other agents: Reset to zero every session
- Sunwell: Accumulates knowledge, avoids past mistakes, remembers preferences

**"The agent that knows when to try harder."**

- Other agents: Fixed effort for every task
- Sunwell: Adapts technique to task complexity

**"The agent you can walk away from."**

- Other agents: Need babysitting, no resume
- Sunwell: Checkpoint at gates, resume after crash/sleep/weekend

**"The agent you can run locally."**

- Other agents: Cloud-dependent, privacy concerns, usage limits
- Sunwell: Local LLMs via Ollama, your data stays yours

---

## Implementation Plan

### Phase 1: Event Streaming Infrastructure
- [ ] Define `AgentEvent` types
- [ ] Create `AsyncIterator[AgentEvent]` interface
- [ ] Implement `StreamingRenderer` with Rich
- [ ] Add `--quiet` and `--json` modes

### Phase 2: Validation Gates
- [ ] Add `ValidationGate` and `GateType` types
- [ ] Implement `GateDetector` for automatic gate identification
- [ ] Patterns: protocols → models → routes → integration
- [ ] Gate result checkpointing for resume capability

### Phase 3: Gate-Aware Execution
- [ ] Execute tasks up to gate, then validate
- [ ] Block dependent tasks until gate passes
- [ ] Fix-before-continue at failed gates
- [ ] `--resume` flag to start from last passed gate

### Phase 4: Streaming Validation (within gates)
- [ ] Add `ValidationStage` that yields events
- [ ] Run validation in parallel with execution
- [ ] Level 1-2-3 cascade with early exit

### Phase 5: Fix Stage  
- [ ] Add `FixStage` that yields events
- [ ] Wire Compound Eye for error analysis
- [ ] Fix routing based on error signals
- [ ] Targeted fixes (region, not whole file)

### Phase 6: Adaptive Planning
- [ ] Extract signals before planning
- [ ] Route to harmonic vs single-shot
- [ ] Auto-detect gates during planning
- [ ] Stream plan candidates as they're generated

### Phase 7: Adaptive Execution
- [ ] Per-task confidence scoring
- [ ] Route low-confidence tasks to vortex
- [ ] Budget tracking with auto-downgrade

### Phase 8: Simulacrum Integration
- [ ] Load Simulacrum at session start (`--session` flag)
- [ ] Inject learnings into planning prompts
- [ ] Filter out approaches matching dead ends
- [ ] Extract learnings from generated artifacts
- [ ] Record dead ends from failed fix attempts
- [ ] Checkpoint Simulacrum at each gate
- [ ] `--resume --session` to continue from last gate
- [ ] `sunwell chat --session` for memory-aware conversations
- [ ] `sunwell sessions list/export` commands

### Phase 9: Full Integration
- [ ] Make adaptive the default
- [ ] Make Simulacrum default (auto-create session from goal hash)
- [ ] Remove explicit technique flags
- [ ] Comprehensive event coverage

---

## Metrics

| Metric | Current | Target | How |
|--------|---------|--------|-----|
| First-pass success | ~70% | 90%+ | Auto-fix at gates |
| Wasted tokens on failures | High | Near-zero | Gates stop before dependent work |
| Time to working code | Variable | Predictable | Streaming shows progress |
| Resume capability | None | Full | Checkpoint at each gate |
| Human interventions | Common | Rare | Adaptive fixing |
| Perceived wait time | High | Low | Live updates |
| Token efficiency | Baseline | -30% | Shortcuts for simple tasks |
| Cross-session learning | None | Active | Simulacrum persists learnings |
| Mistake repetition | Common | Rare | Dead ends prevent re-trying failures |
| Multi-day task completion | Unsupported | Supported | Session resume + memory |
| Onboarding time (repeat users) | Same | Decreasing | Identity remembers preferences |

---

## CLI Interface

```bash
# Default: full adaptive with streaming
sunwell "Build a Flask forum app"

# Quiet mode (CI/scripts)
sunwell "Build app" --quiet

# JSON events (programmatic)
sunwell "Build app" --json

# Budget control
sunwell "Build app" --budget 100000    # More quality
sunwell "Build app" --economize        # Prefer cheap

# Debugging
sunwell "Build app" --verbose          # Show routing decisions
sunwell "Build app" --dry-run          # Plan only, show what would happen
```

---

## Decisions (Resolved Questions)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Event granularity** | Every state change + heartbeat every 500ms | Balances responsiveness with terminal performance |
| **Offline/batch mode** | `--quiet` mode with JSON summary at end | CI/CD needs machine-readable output |
| **Partial results** | Keep broken code, mark with `# FIXME: [error]` comments | Users can manually fix; better than losing all progress |
| **Escalation UX** | Pause stream, show prompt, wait for input, resume | Blocking is acceptable for dangerous/ambiguous cases |
| **Gate timeout** | 30s per gate, skip on timeout | Prevents hangs; timeout indicates environmental issue |
| **Max fix attempts** | 3 attempts per error, then escalate to user | Prevents infinite loops; 3 gives diverse approaches |

---

## Open Questions (Require Discussion)

1. **Should adaptive be opt-out or opt-in initially?**
   - Option A: Default on (`--no-adaptive` to disable) — Bold, but may surprise users
   - Option B: Default off (`--adaptive` to enable) — Safe, but delays adoption
   - **Leaning**: Option A after Phase 9 is complete and battle-tested

2. **How should gates interact with existing `--incremental` flag?**
   - Gates provide finer checkpoints than RFC-040's plan-level persistence
   - Need to reconcile checkpoint formats

3. **Should Simulacrum sessions be auto-created?**
   - Option A: Always create session from goal hash (zero friction)
   - Option B: Require explicit `--session name` (user controls naming)
   - Option C: Prompt once "Save this session for later?" (best UX, more complexity)
   - **Leaning**: Option A with optional `--session name` override

4. **How to handle conflicting learnings across sessions?**
   - User worked on project A (uses int IDs) and project B (uses UUIDs)
   - Option A: Session-scoped learnings only
   - Option B: Global learnings with project tagging
   - **Leaning**: Option A (simpler, less confusion)

---

## References

### Internal RFCs
- RFC-019: Naaru Architecture (Shards, Convergence, Resonance)
- RFC-034: Contract-Aware Planning
- RFC-038: Harmonic Planning
- RFC-040: Plan Persistence (incremental builds)

### Existing Implementations
- `src/sunwell/experiments/compound.py`: Compound Eye (lateral inhibition, temporal diff, hotspots)
- `src/sunwell/vortex/`: Vortex pipeline (signals, discovery, convergence)
- `src/sunwell/vortex/signals.py`: Signal dataclass and parsing
- `src/sunwell/naaru/planners/harmonic.py`: HarmonicPlanner with candidate scoring
- `src/sunwell/naaru/resonance.py`: Resonance feedback loops
- `src/sunwell/experiments/resonance_amp.py`: Resonance amplification experiments
- `src/sunwell/simulacrum/`: Persistent memory system (DAG, learnings, dead ends, identity)
- `src/sunwell/simulacrum/dag.py`: Memory DAG with turns, branches, learnings
- `src/sunwell/simulacrum/store.py`: Session persistence and loading
- `src/sunwell/spectrum/identity/`: Identity extraction and management

### External
- Rich library: https://rich.readthedocs.io/en/latest/live.html

---

## Appendix: Validation Checklist

Before moving to `plan/evaluated/`:

- [ ] Benchmark: single-shot vs. adaptive on forum app (cost + time + success)
- [ ] Verify cost multipliers with actual token counts
- [ ] Test gate detection on 3+ different project types
- [ ] Prototype `StreamingRenderer` with Rich to validate UX
- [ ] Review with team: rule-based routing vs. learned router decision
