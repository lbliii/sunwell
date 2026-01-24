# RFC-110: Unified Execution Engine — Clean Architecture

**Status**: 🚧 Draft  
**Author**: AI Assistant  
**Created**: 2026-01-23  
**Breaking**: YES — Deletes 15+ modules, renames core components  
**Priority**: P0 — Mission Critical

---

## Summary

Sunwell has accumulated **30 executor/engine classes** across **5+ execution paths** with two competing "unified" entry points (AdaptiveAgent and Naaru). This creates confusion, inconsistent behavior, and duplicated code.

This RFC:
1. Establishes a **layered architecture** where each layer adds distinct value
2. Renames `AdaptiveAgent` → `Agent` and moves to `agent/` (it's THE agent, not "an adaptive one")
3. Clarifies Naaru as an **internal coordination layer**, not an entry point
4. Deletes all redundant executors and entry points
5. Removes ~50 files and ~10,000 lines of code

**Principle: If a component doesn't transform, enrich, or decide — delete it.**

---

## Problem Statement

### Current State: Two "Unified" Systems

```
AdaptiveAgent claims: "THE ONE agent for Sunwell" (RFC-042)
Naaru claims:         "THE unified entry point" (RFC-083)
```

Both are right — they operate at different layers. But the naming is confusing and there are redundant entry points.

### Current Entry Points (Chaos)

```
sunwell "goal"              → AdaptiveAgent
sunwell -s a-2 file         → SkillExecutor  
sunwell do ::a-2 file       → SkillExecutor
sunwell ask "question"      → RuntimeEngine
sunwell naaru process       → Naaru.process()  ← redundant entry point
sunwell naaru run           → Naaru.run()      ← redundant entry point
sunwell interface process   → IntentAnalyzer   ← domain handler, not executor
sunwell chat + message      → model.generate() (DIRECT, bypasses everything!)
sunwell workflow run        → WorkflowEngine
```

**8 entry points. 5 execution engines. 30 executor classes.**

### The Executor Graveyard

| Class | File | Verdict |
|-------|------|---------|
| AdaptiveAgent | `adaptive/agent.py` | **RENAME** → `Agent` in `agent/core.py` |
| RuntimeEngine | `runtime/engine.py` | DELETE (Agent does this) |
| SkillExecutor | `skills/executor.py` | DELETE (Agent does this) |
| IncrementalSkillExecutor | `skills/executor.py` | DELETE (Agent does this) |
| SecureSkillExecutor | `security/executor.py` | DELETE (becomes Agent hook) |
| WorkflowEngine | `workflow/engine.py` | DELETE (Agent task graph) |
| CascadeExecutor | `weakness/executor.py` | DELETE (Agent task graph) |
| IncrementalExecutor | `incremental/executor.py` | DELETE (Agent cache) |
| ActionExecutor | `interface/executor.py` | DELETE (becomes tools) |
| ArtifactExecutor | `naaru/executor.py` | MERGE into Agent |
| Naaru.process() | `naaru/coordinator.py` | DELETE entry point |
| Naaru.run() | `naaru/coordinator.py` | KEEP (called by Agent) |

---

## Solution: Layered Architecture

### Principle: Every Layer Adds Distinct Value

| Layer | Value Added | If Missing, You Lose... |
|-------|-------------|-------------------------|
| **CLI** | Human interface — args, env, rendering | Ability to use from terminal |
| **Agent** | Intelligence — signals, planning, validation, learning | Adaptive behavior |
| **Naaru** | Parallelism — shards, convergence, wave execution | Performance on local models |
| **Tools** | Side effects — file I/O, shell, external APIs | Ability to change the world |

**Test for every component**: "If I delete this, what intelligence/optimization/capability is lost?"

- Delete CLI → Lose human interface ❌ Keep
- Delete Agent → Lose adaptive behavior ❌ Keep
- Delete Naaru → Lose parallelism optimization ❌ Keep
- Delete Tools → Lose ability to affect the world ❌ Keep
- Delete RuntimeEngine → Lose... nothing (Agent does it) ✅ **DELETE**
- Delete `naaru process` → Lose... nothing (redundant entry) ✅ **DELETE**

---

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                              CLI                                     │
│                                                                      │
│   sunwell "goal"                                                    │
│   sunwell -s shortcut [target]                                      │
│   sunwell chat                                                       │
│                                                                      │
│   Value: Parse arguments, setup environment, render output          │
│   Transform: Text commands → RunRequest → AgentEvent → Rich output  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                             AGENT                                    │
│                         (sunwell/agent/)                             │
│                                                                      │
│   Agent.run(request: RunRequest) → AsyncIterator[AgentEvent]        │
│                                                                      │
│   Value: Intelligence — understands goals, makes decisions          │
│                                                                      │
│   1. SIGNAL    → Analyze: What kind of task? How complex?           │
│   2. LENS      → Select expertise injection                         │
│   3. PLAN      → Decompose into task graph with dependencies        │
│   4. EXECUTE   → Run tasks (delegates parallelism to Naaru)         │
│   5. VALIDATE  → Check gates, detect failures                       │
│   6. FIX       → Auto-fix errors (Compound Eye)                     │
│   7. LEARN     → Persist patterns to Simulacrum                     │
│                                                                      │
│   This is THE brain. Makes all the decisions.                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ uses internally
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                             NAARU                                    │
│                         (sunwell/naaru/)                             │
│                                                                      │
│   Value: Parallelism — maximizes throughput from local models       │
│                                                                      │
│   • Convergence: 7±2 slot working memory (context caching)          │
│   • Shards: CPU prefetches while GPU generates                      │
│   • Harmonic: Multiple personas generate in parallel                │
│   • Waves: Execute independent tasks concurrently                   │
│                                                                      │
│   NOT an entry point. Used BY Agent for task execution.             │
│   Agent says WHAT. Naaru figures out HOW to do it fast.             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                             TOOLS                                    │
│                         (sunwell/tools/)                             │
│                                                                      │
│   Value: Side effects — actually changes files, runs commands       │
│                                                                      │
│   Pure functions with real-world effects:                           │
│   • write_file(path, content) → writes to disk                      │
│   • run_command(cmd) → executes shell command                       │
│   • search_codebase(query) → finds code                             │
│   • create_calendar_event(...) → provider actions                   │
│                                                                      │
│   No intelligence. No coordination. Does what it's told.            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Naming Changes

### Why Rename?

| Current | Problem | New |
|---------|---------|-----|
| `AdaptiveAgent` | "Adaptive" is implementation detail, not identity | `Agent` |
| `adaptive/` | Directory named after adjective | `agent/` |
| `Naaru.process()` | Implies it's an entry point (it shouldn't be) | DELETE |
| `sunwell naaru process` | Redundant CLI command | DELETE |
| `interface/executor.py` | Not an executor, it's provider tools | `tools/providers.py` |

### Rename Map

```
BEFORE                              AFTER
─────────────────────────────────────────────────────────────
adaptive/agent.py → AdaptiveAgent   agent/core.py → Agent
adaptive/signals.py                 agent/signals.py
adaptive/gates.py                   agent/gates.py
adaptive/fixer.py                   agent/fixer.py
adaptive/events.py                  agent/events.py
adaptive/budget.py                  agent/budget.py
adaptive/learning.py                agent/learning.py
adaptive/lens_resolver.py           agent/lens.py

interface/executor.py               tools/providers.py
interface/analyzer.py               KEEP (domain-specific)
```

---

## The Request Object

```python
# agent/request.py

@dataclass(frozen=True, slots=True)
class RunRequest:
    """Input to Agent.run() — everything needed to execute a goal."""
    
    goal: str
    """Natural language goal (shortcuts already expanded)."""
    
    context: dict[str, Any] = field(default_factory=dict)
    """Injected context: target files, workspace state, user preferences."""
    
    lens: Lens | None = None
    """Explicit lens or None for auto-selection."""
    
    options: RunOptions = field(default_factory=RunOptions)
    """Execution options (trust, timeout, etc.)."""


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Execution configuration."""
    
    trust: ToolTrust = ToolTrust.WORKSPACE
    timeout_seconds: int = 300
    max_tokens: int = 50_000
    streaming: bool = True
    validate: bool = True
    persist_learnings: bool = True
```

---

## CLI: The Human Interface

The CLI transforms human text into structured requests and renders events as output.

```python
# cli/main.py

@click.command()
@click.argument("goal", required=False)
@click.option("-s", "--shortcut", help="Skill shortcut (a, a-2, p, etc.)")
@click.option("-t", "--target", help="Target file/directory for shortcut")
@click.option("-c", "--context", help="Additional context string")
# ... other options
async def main(goal: str | None, shortcut: str | None, target: str | None, ...):
    """Sunwell — AI agent for software development."""
    
    # Build the goal
    if shortcut:
        # Shortcuts expand directly to goals — no intermediate layer
        goal = SHORTCUT_TEMPLATES[shortcut].format(
            target=target or ".",
            context=context or "",
        )
        request_context = await gather_context(target)
    elif goal:
        request_context = {}
    else:
        # Interactive mode
        return await run_chat(options)
    
    # Create request
    request = RunRequest(
        goal=goal,
        context=request_context,
        lens=lens,
        options=options,
    )
    
    # Execute through Agent
    agent = Agent(model=model, tool_executor=tools)
    
    async for event in agent.run(request):
        renderer.render(event)


# Shortcut templates — goal transformation, not a "handler"
SHORTCUT_TEMPLATES = {
    "a": "Perform a quick documentation audit on {target}",
    "a-2": "Perform a deep documentation audit with triangulation on {target}. {context}",
    "p": "Polish and improve the documentation in {target}. {context}",
    "health": "Check the health of the documentation in {target}",
    "drift": "Detect documentation drift from source code in {target}",
}
```

### Chat: A REPL, Not a Separate Path

```python
# cli/chat.py

async def run_chat(options: RunOptions):
    """Interactive chat — a REPL that calls Agent for each turn."""
    
    agent = Agent(model=model, tool_executor=tools)
    session_context = SessionContext()
    
    while True:
        user_input = await get_input()
        
        # Shortcuts expand to goals
        if user_input.startswith("::"):
            shortcut, *args = user_input[2:].split(maxsplit=1)
            goal = SHORTCUT_TEMPLATES[shortcut].format(
                target=args[0] if args else ".",
                context="",
            )
        else:
            goal = user_input
        
        # Every message goes through Agent
        request = RunRequest(
            goal=goal,
            context=session_context.to_dict(),
            options=options,
        )
        
        async for event in agent.run(request):
            renderer.render(event)
        
        session_context.add_turn(user_input, event.result)
```

---

## Agent: The Brain

The Agent is the intelligence layer. It analyzes, plans, executes, validates, and learns.

```python
# agent/core.py

@dataclass
class Agent:
    """THE execution engine for Sunwell.
    
    This is the single point of intelligence. All entry points
    (CLI, chat, Studio) call Agent.run().
    
    Agent uses Naaru internally for parallel task execution,
    but Naaru is an implementation detail — not an entry point.
    """
    
    model: ModelProtocol
    tool_executor: ToolExecutor
    cwd: Path = field(default_factory=Path.cwd)
    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    
    # Internal coordination (Naaru)
    _naaru: Naaru = field(init=False)
    
    def __post_init__(self):
        # Naaru is internal — Agent creates and owns it
        self._naaru = Naaru(
            workspace=self.cwd,
            synthesis_model=self.model,
            tool_executor=self.tool_executor,
        )
    
    async def run(self, request: RunRequest) -> AsyncIterator[AgentEvent]:
        """Execute a goal through the unified pipeline.
        
        This is THE execution method. All roads lead here.
        
        Pipeline:
        1. SIGNAL    → Analyze goal complexity and domain
        2. LENS      → Select or validate expertise injection
        3. PLAN      → Decompose into task graph
        4. EXECUTE   → Run tasks (Naaru handles parallelism)
        5. VALIDATE  → Check gates at checkpoints
        6. FIX       → Auto-fix failures (Compound Eye)
        7. LEARN     → Persist patterns to Simulacrum
        """
        
        # 1. Signal extraction — understand what we're dealing with
        signals = await extract_signals(request.goal, request.context)
        yield SignalEvent(signals)
        
        # 2. Lens selection — inject expertise
        lens = request.lens or await self._select_lens(signals)
        yield LensEvent(lens)
        
        # 3. Planning — decompose into task graph
        plan = await self._plan(request.goal, signals, lens)
        yield PlanEvent(plan)
        
        # 4. Execute with validation gates
        async for event in self._execute_plan(plan, lens):
            yield event
        
        # 7. Learn from this execution
        if request.options.persist_learnings:
            await self._persist_learnings(request, plan)
        
        yield CompleteEvent(plan.summary())
    
    async def _execute_plan(self, plan: TaskGraph, lens: Lens):
        """Execute task graph with validation gates.
        
        Naaru handles the parallelism. Agent handles the intelligence.
        """
        while plan.has_pending_tasks():
            # Get ready tasks (dependencies satisfied)
            ready = plan.get_ready_tasks()
            
            # Execute via Naaru (parallel if independent)
            results = await self._naaru.execute_tasks(ready)
            
            for task, result in zip(ready, results, strict=True):
                yield TaskCompleteEvent(task, result)
                plan.mark_complete(task)
                
                # Check validation gate after task?
                if gate := plan.gate_after(task):
                    validation = await self._validate(gate, result)
                    yield ValidationEvent(validation)
                    
                    if not validation.passed:
                        # 6. Auto-fix
                        fix = await self._auto_fix(validation)
                        yield FixEvent(fix)
```

---

## Naaru: The Optimizer

Naaru is the coordination layer. It maximizes throughput from local models through parallelism and caching.

**Naaru is NOT an entry point.** It's used internally by Agent.

```python
# naaru/coordinator.py

@dataclass
class Naaru:
    """Parallel task coordination for local models.
    
    This is NOT an entry point. Agent creates and uses Naaru internally.
    
    Naaru's job is to execute tasks efficiently:
    - Convergence: 7±2 slot working memory
    - Shards: CPU prefetches while GPU generates
    - Harmonic: Multi-persona parallel generation
    - Waves: Execute independent tasks concurrently
    """
    
    workspace: Path
    synthesis_model: ModelProtocol
    tool_executor: ToolExecutor
    config: NaaruConfig = field(default_factory=NaaruConfig)
    
    # Components
    convergence: Convergence = field(init=False)
    shard_pool: ShardPool = field(init=False)
    
    async def execute_tasks(self, tasks: list[Task]) -> list[TaskResult]:
        """Execute tasks with optimal parallelism.
        
        This is what Naaru is FOR — efficient task execution.
        Agent calls this, Naaru figures out HOW.
        """
        # Prefetch context via shards
        await self.shard_pool.prepare_for_tasks(tasks)
        
        # Execute in parallel waves
        results = []
        for wave in self._compute_waves(tasks):
            wave_results = await asyncio.gather(*[
                self._execute_single(task) for task in wave
            ])
            results.extend(wave_results)
        
        return results
    
    # DELETE: process() — this was a redundant entry point
    # DELETE: run() entry point — Agent.run() is THE entry point
```

### What Gets Deleted from Naaru

```python
# These entry points are DELETED — they're redundant with Agent.run()

# BEFORE (naaru/coordinator.py)
async def process(self, input: ProcessInput) -> AsyncIterator[NaaruEvent]:
    """THE unified entry point. All roads lead here."""  # ← LIE, delete it
    
async def run(self, goal: str, ...) -> AgentResult:
    """Execute an arbitrary user task."""  # ← Agent.run() does this
```

### What Stays in Naaru

```python
# These are valuable and KEPT — they add parallelism value

convergence.py     # Working memory (7±2 slots)
shards.py          # Parallel CPU helpers
planners/          # Planning strategies (harmonic, artifact)
workers/           # Region workers for parallel execution
```

---

## Studio Integration

Studio currently calls:
- `sunwell naaru process --json "goal"` → DELETE this path
- `sunwell --json "goal"` → KEEP (calls Agent.run())

### Migration for Studio

```rust
// BEFORE: studio/src-tauri/src/naaru.rs
let output = Command::new("sunwell")
    .args(["naaru", "process", &input.content, "--json"])  // ❌ Delete
    .output();

// AFTER: studio/src-tauri/src/naaru.rs  
let output = Command::new("sunwell")
    .args([&input.content, "--json"])  // ✅ Direct to Agent
    .output();
```

Same JSON event format. Same behavior. Cleaner path.

---

## What Gets Deleted

### Executors/Engines (All Redundant)

```
src/sunwell/runtime/engine.py           # RuntimeEngine → Agent
src/sunwell/skills/executor.py          # SkillExecutor → Agent
src/sunwell/workflow/engine.py          # WorkflowEngine → Agent task graph
src/sunwell/security/executor.py        # SecureSkillExecutor → Agent hooks
src/sunwell/weakness/executor.py        # CascadeExecutor → Agent task graph
src/sunwell/incremental/executor.py     # IncrementalExecutor → Agent cache
src/sunwell/interface/executor.py       # ActionExecutor → tools/providers.py
src/sunwell/eval/executors.py           # Simplify to benchmark.py
src/sunwell/naaru/executor.py           # ArtifactExecutor → merge into Agent
```

### CLI Commands (Redundant Entry Points)

```
src/sunwell/cli/ask.py                  # → sunwell "question"
src/sunwell/cli/apply.py                # → sunwell -s shortcut
src/sunwell/cli/do_cmd.py               # → sunwell -s shortcut
src/sunwell/cli/skill.py                # → sunwell -s shortcut
src/sunwell/cli/naaru_cmd.py            # → sunwell "goal" (no separate naaru)
src/sunwell/cli/interface_cmd.py        # → sunwell providers (rename)
```

### Runtime (Duplicates Agent Functionality)

```
src/sunwell/runtime/engine.py           # RuntimeEngine
src/sunwell/runtime/classifier.py       # → agent/signals.py
src/sunwell/runtime/injector.py         # → agent context gathering
src/sunwell/runtime/retriever.py        # → agent/lens.py
src/sunwell/runtime/commands.py         # → SHORTCUT_TEMPLATES
```

### Naaru Entry Points (Keep Coordination, Delete Entry)

```
# DELETE from naaru/coordinator.py:
- Naaru.process()                       # Redundant entry point
- Naaru.run() as entry point            # Agent.run() is THE entry

# KEEP in naaru/:
+ convergence.py                        # Working memory
+ shards.py                             # Parallel helpers
+ planners/                             # Planning strategies
+ workers/                              # Region workers
+ Naaru.execute_tasks()                 # Internal method for Agent
```

---

## New Directory Structure

```
src/sunwell/
├── agent/                      # NEW: renamed from adaptive/
│   ├── __init__.py
│   ├── core.py                 # Agent class (renamed from AdaptiveAgent)
│   ├── request.py              # RunRequest, RunOptions
│   ├── signals.py              # Signal extraction
│   ├── gates.py                # Validation gates
│   ├── fixer.py                # Auto-fix (Compound Eye)
│   ├── events.py               # AgentEvent types
│   ├── learning.py             # Simulacrum integration
│   ├── lens.py                 # Lens selection (from lens_resolver.py)
│   └── budget.py               # Token budget
│
├── naaru/                      # KEEP: internal coordination
│   ├── coordinator.py          # Naaru class (no process/run entry points)
│   ├── convergence.py          # Working memory
│   ├── shards.py               # Parallel helpers
│   ├── planners/               # Planning strategies
│   │   ├── harmonic.py
│   │   ├── artifact.py
│   │   └── agent.py
│   └── workers/                # Region workers
│
├── tools/                      # Tool execution
│   ├── executor.py             # ToolExecutor
│   ├── providers.py            # NEW: calendar, lists, notes (from interface/)
│   └── ...
│
├── cli/                        # Simplified CLI
│   ├── main.py                 # THE entry point
│   ├── chat.py                 # Interactive mode
│   └── providers.py            # sunwell providers subcommand
│
└── ... (models, memory, etc.)
```

---

## Impact Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Entry points | 8 | **2** (main, chat) | -6 |
| Executor classes | 30 | **1** (Agent) | -29 |
| "Unified" systems | 2 (Agent, Naaru) | **1** (Agent) | -1 |
| Files in agent/ | 16 | 10 | -6 |
| Files deleted | 0 | ~50 | -50 |
| Lines deleted | 0 | ~10,000 | -10K |
| Lines created | 0 | ~500 | +500 |
| **Net reduction** | — | **~9,500 lines** | |

---

## Implementation Plan

### Phase 1: Rename and Reorganize (Day 1)

1. **Create `agent/` directory**
2. **Move and rename files**:
   - `adaptive/agent.py` → `agent/core.py` (rename class to `Agent`)
   - `adaptive/signals.py` → `agent/signals.py`
   - `adaptive/gates.py` → `agent/gates.py`
   - `adaptive/fixer.py` → `agent/fixer.py`
   - `adaptive/events.py` → `agent/events.py`
   - `adaptive/lens_resolver.py` → `agent/lens.py`
   - `adaptive/budget.py` → `agent/budget.py`
   - `adaptive/learning.py` → `agent/learning.py`
3. **Create `agent/request.py`** with RunRequest, RunOptions
4. **Update Agent.run()** to accept RunRequest
5. **Add `GateType.CHECKPOINT`** to gates.py
6. **Update all imports** (use search-replace across codebase)

### Phase 2: Remove Naaru Entry Points (Day 1-2)

1. **Delete `Naaru.process()`** method
2. **Delete `Naaru.run()`** as entry point
3. **Keep `Naaru.execute_tasks()`** as internal method
4. **Update Agent** to use `self._naaru.execute_tasks()`
5. **Delete `cli/naaru_cmd.py`**

### Phase 3: Consolidate CLI (Day 2)

1. **Update `cli/main.py`** to call Agent directly
2. **Move shortcut templates** into main.py (no separate module)
3. **Delete deprecated commands**:
   - `cli/ask.py`
   - `cli/apply.py`
   - `cli/do_cmd.py`
   - `cli/skill.py`
4. **Rename `cli/interface_cmd.py`** → `cli/providers.py`
5. **Update chat** to use Agent for every message

### Phase 4: Delete Executors (Day 2-3)

1. **Delete `runtime/engine.py`** (RuntimeEngine)
2. **Delete `skills/executor.py`** (SkillExecutor)
3. **Delete `workflow/engine.py`** (WorkflowEngine)
4. **Delete `security/executor.py`** (SecureSkillExecutor)
5. **Delete `weakness/executor.py`** (CascadeExecutor)
6. **Delete `incremental/executor.py`** (IncrementalExecutor)
7. **Move `interface/executor.py`** functionality to `tools/providers.py`
8. **Simplify `eval/executors.py`** → `eval/benchmark.py`

### Phase 5: Delete Runtime Duplicates (Day 3)

1. **Delete `runtime/classifier.py`** (→ agent/signals.py)
2. **Delete `runtime/injector.py`** (→ Agent context)
3. **Delete `runtime/retriever.py`** (→ agent/lens.py)
4. **Delete `runtime/commands.py`** (→ SHORTCUT_TEMPLATES)
5. **Delete `adaptive/` directory** (now empty)

### Phase 6: Studio Update (Day 3)

1. **Update Studio Tauri commands** to call `sunwell "goal" --json`
2. **Remove `naaru process` path**
3. **Verify event format unchanged**
4. **Test full integration**

---

## Migration Guide

### For CLI Users

```bash
# BEFORE (deprecated)          # AFTER
sunwell ask "question"         sunwell "question"
sunwell do ::a-2 file.md       sunwell -s a-2 file.md
sunwell apply my-lens          sunwell -l my-lens "goal"
sunwell naaru process "goal"   sunwell "goal"
sunwell naaru run "goal"       sunwell "goal"

# UNCHANGED
sunwell "build an app"         sunwell "build an app"
sunwell -s a-2 docs/           sunwell -s a-2 docs/
sunwell chat                   sunwell chat
```

### For Code Using Internal APIs

```python
# BEFORE
from sunwell.adaptive.agent import AdaptiveAgent
agent = AdaptiveAgent(model=model)
async for event in agent.run(goal):
    ...

# AFTER
from sunwell.agent import Agent, RunRequest
agent = Agent(model=model, tool_executor=tools)
request = RunRequest(goal=goal)
async for event in agent.run(request):
    ...
```

### For Studio

```rust
// BEFORE
Command::new("sunwell").args(["naaru", "process", &goal, "--json"])

// AFTER
Command::new("sunwell").args([&goal, "--json"])
```

---

## Success Criteria

1. **One entry point**: `sunwell "goal"` (and `-s` for shortcuts)
2. **One Agent class**: `Agent` in `agent/core.py`
3. **Naaru is internal**: No public entry points, used by Agent
4. **All tests pass**: Adapted to new imports
5. **Studio works**: Same JSON format, cleaner path
6. **~50 files deleted**: No redundant executors
7. **~9,500 lines removed**: Significant code reduction

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking Studio | Update Tauri commands before removing old paths |
| Import errors | Automated search-replace for all imports |
| Test failures | Update tests alongside code changes |
| Feature loss | Audit each deleted file for unique functionality |
| Naaru features lost | Keep all coordination code, only remove entry points |

---

## Non-Goals

1. **NOT adding new features** — Pure consolidation and cleanup
2. **NOT changing behavior** — Same capabilities, cleaner architecture
3. **NOT backwards compatibility** — Delete old code, no deprecated shims
4. **NOT touching models** — Model layer unchanged
5. **NOT renaming Naaru** — Keep the name, clarify it's internal

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 4 hours | Agent renamed and reorganized |
| Phase 2 | 2 hours | Naaru entry points removed |
| Phase 3 | 4 hours | CLI consolidated |
| Phase 4 | 4 hours | Executors deleted |
| Phase 5 | 2 hours | Runtime duplicates deleted |
| Phase 6 | 2 hours | Studio updated and tested |
| **Total** | **~2.5 days** | Clean architecture |

---

## Appendix: Files to Delete

```
# Executors (DELETE)
src/sunwell/runtime/engine.py
src/sunwell/skills/executor.py
src/sunwell/workflow/engine.py
src/sunwell/security/executor.py
src/sunwell/weakness/executor.py
src/sunwell/incremental/executor.py
src/sunwell/interface/executor.py
src/sunwell/eval/executors.py
src/sunwell/naaru/executor.py

# CLI Commands (DELETE)
src/sunwell/cli/ask.py
src/sunwell/cli/apply.py
src/sunwell/cli/do_cmd.py
src/sunwell/cli/skill.py
src/sunwell/cli/naaru_cmd.py

# Runtime (DELETE)
src/sunwell/runtime/engine.py
src/sunwell/runtime/classifier.py
src/sunwell/runtime/injector.py
src/sunwell/runtime/retriever.py
src/sunwell/runtime/commands.py

# Directory (DELETE after move)
src/sunwell/adaptive/
```

---

## Appendix: Final Agent Implementation

```python
# agent/core.py

@dataclass
class Agent:
    """THE execution engine for Sunwell.
    
    Single point of intelligence. All entry points call Agent.run().
    Uses Naaru internally for parallel task execution.
    """
    
    model: ModelProtocol
    tool_executor: ToolExecutor
    cwd: Path = field(default_factory=Path.cwd)
    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    
    # Optional
    lens: Lens | None = None
    auto_lens: bool = True
    session: str | None = None
    simulacrum: SimulacrumStore | None = None
    
    # Internal
    _naaru: Naaru = field(init=False)
    
    def __post_init__(self):
        self._naaru = Naaru(
            workspace=self.cwd,
            synthesis_model=self.model,
            tool_executor=self.tool_executor,
        )
    
    async def run(self, request: RunRequest) -> AsyncIterator[AgentEvent]:
        """Execute a goal. THE entry point for all Sunwell operations."""
        
        # 1. Signal extraction
        signals = await extract_signals(request.goal, request.context)
        yield SignalEvent(signals)
        
        # 2. Lens selection
        lens = request.lens or (await self._select_lens(signals) if self.auto_lens else None)
        if lens:
            yield LensEvent(lens)
        
        # 3. Planning
        plan = await self._plan(request.goal, signals, lens)
        yield PlanEvent(plan)
        
        # 4-6. Execute with validation and auto-fix
        async for event in self._execute_with_gates(plan, lens):
            yield event
        
        # 7. Learning
        if request.options.persist_learnings and self.simulacrum:
            await self._persist_learnings(request, plan)
        
        yield CompleteEvent(plan.summary())
    
    async def _execute_with_gates(self, plan: TaskGraph, lens: Lens | None):
        """Execute plan with validation gates and auto-fix."""
        
        while plan.has_pending_tasks():
            ready = plan.get_ready_tasks()
            
            # Naaru handles parallel execution
            results = await self._naaru.execute_tasks(ready)
            
            for task, result in zip(ready, results, strict=True):
                yield TaskCompleteEvent(task, result)
                plan.mark_complete(task)
                
                # Validation gate?
                if gate := plan.gate_after(task):
                    validation = await self._validate(gate, result)
                    yield ValidationEvent(validation)
                    
                    if not validation.passed:
                        fix = await self._auto_fix(validation, task, lens)
                        yield FixEvent(fix)
```

---

**Ready to implement?**
