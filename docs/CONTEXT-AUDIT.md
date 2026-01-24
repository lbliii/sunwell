# Sunwell Context Flow Audit

**573 Python files. 41+ context/state/session/memory classes. Zero unified flow.**

---

## 0. MODULE VALUE ANALYSIS

### What Each System Is TRYING To Do

This section documents the **intended value** of each module based on RFCs and docstrings, with an assessment of integration status.

---

### 🧠 MEMORY SYSTEMS (The Persistent Brain)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **Simulacrum** | RFC-013/014 | Model-agnostic conversation memory. Switch models mid-conversation. Smart retrieval keeps context in window. Learnings persist forever. | ⚠️ PARTIAL: Used in planning, discarded before task execution |
| **Briefing** | RFC-071 | "Twitter for LLMs" - 300-token rolling handoff note. Instant orientation. Dispatch signals for prefetch. Hazards prevent mistakes. | ⚠️ PARTIAL: Prefetch works, hazards never reach tasks |
| **LearningStore** | RFC-042/122 | Extract patterns from code/fixes. Propagate within session and cross-session via Simulacrum. Categories: type, api, pattern, fix, dead_end. | ✅ WORKING: Flows to planning AND execution |
| **DecisionMemory** | RFC-045 | Architectural decisions persist forever. Records "why X over Y" with rationale. Prevents re-arguing same decisions. | ❌ ORPHANED: Never loaded by Agent |
| **FailureMemory** | RFC-045 | Remember what didn't work and why. Root cause analysis. Pattern detection for similar failures. | ❌ ORPHANED: Never loaded by Agent |
| **TeamKnowledge** | RFC-052 | Git-based shared knowledge across team. Decisions, failures, patterns sync via repo. Zero infrastructure. | ❌ ORPHANED: Never integrated |
| **SessionTracker** | RFC-120 | Track activity within session. Goal summaries. File metrics. Session-level aggregation. | ❌ ORPHANED: Agent doesn't use it |

**Total Intended Value**: Agent that NEVER forgets what worked, what didn't, why decisions were made.
**Actual Value Delivered**: ~30% (only LearningStore fully works)

---

### 🎯 INTELLIGENCE SYSTEMS (Understanding the Project)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **ProjectContext** | RFC-045 | Unified context: Simulacrum + Project Intelligence + Team Intelligence. The "main interface for all project intelligence." | ❌ ORPHANED: Never instantiated by Agent |
| **CodebaseGraph** | RFC-045 | Semantic understanding of code structure. Know what depends on what. | ❌ ORPHANED: Built but unused |
| **PatternProfile** | RFC-045 | Learned user/project style preferences. Code conventions. Naming patterns. | ❌ ORPHANED: Built but unused |
| **BootstrapOrchestrator** | RFC-050 | Day-1 intelligence from git history, code patterns, docs, config. Immediate value on first run. | ⚠️ PARTIAL: Can bootstrap, but results not consumed |

**Total Intended Value**: Agent that understands YOUR project from day 1.
**Actual Value Delivered**: ~10% (bootstrap works but feeds orphaned systems)

---

### 🔧 EXECUTION SYSTEMS (Getting Things Done)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **Agent** | RFC-110 | THE execution method. All roads lead here. Signal → Lens → Plan → Execute → Validate → Fix → Learn. | ✅ WORKING: Primary entry point |
| **Naaru** | RFC-016/019 | Coordinated intelligence for local models. Parallel workers, convergence memory, harmonic synthesis. | ⚠️ PARTIAL: Used internally by Agent, direct path broken |
| **ConvergenceLoop** | RFC-123 | Self-stabilizing code gen. After writes, run lint/types/tests. Fix until stable or escalate. | ✅ WORKING: Wired to Agent |
| **Vortex** | RFC-N/A | Multi-model coordination through primitive composition. Islands prevent premature convergence. | ⚠️ PARTIAL: Used by Fixer, not primary path |
| **ExecutionManager** | RFC-094 | Single entry point for backlog-driven goal execution. | ❌ ORPHANED: Exists but not used |

**Total Intended Value**: Parallel, self-correcting, multi-model execution.
**Actual Value Delivered**: ~60% (Agent+Convergence work, Naaru/Vortex underutilized)

---

### 🛡️ SAFETY SYSTEMS (Not Breaking Things)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **GuardrailSystem** | RFC-048 | Multi-layer safety: classify actions, bound scope, verify, rollback, escalate. Safe unsupervised operation. | ⚠️ PARTIAL: Components exist, not wired to main flow |
| **RecoveryManager** | RFC-125 | When auto-fix fails, preserve progress. Review interface like GitHub merge conflicts. | ✅ WORKING: CLI command works |
| **IntegrationVerifier** | RFC-067 | Detect orphan code. Verify artifacts are wired. Prevent "building without connecting". | ⚠️ PARTIAL: Can verify, not auto-invoked |

**Total Intended Value**: Agent that can't accidentally break your project.
**Actual Value Delivered**: ~40% (Recovery works, guardrails not automatic)

---

### 🧭 ROUTING/PLANNING SYSTEMS (Deciding What To Do)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **HarmonicPlanner** | RFC-032/034 | Multi-persona planning. Uses Simulacrum for memory. Generates candidates, scores, selects. | ✅ WORKING: Primary planner |
| **AgentPlanner** | RFC-032 | LLM-based planning for arbitrary goals. Contract-aware fields. | ✅ WORKING: Used when HarmonicPlanner fails |
| **ArtifactPlanner** | RFC-N/A | Generate artifact content. | ❌ BROKEN: Doesn't check workspace_context |
| **UnifiedRouter** | RFC-030 | Single tiny model handles ALL routing decisions in one inference call. | ⚠️ PARTIAL: Exists, not default |
| **CognitiveRouter** | RFC-020 | Intent-aware routing with tiny LLMs. (DEPRECATED) | ❌ DEPRECATED: Use UnifiedRouter |
| **TieredAttunement** | RFC-022 | Enhanced routing with DORI techniques. (DEPRECATED) | ❌ DEPRECATED: Use UnifiedRouter |

**Total Intended Value**: Smart routing that picks the right approach instantly.
**Actual Value Delivered**: ~50% (planners work, routing underused)

---

### 🎭 EXPERTISE SYSTEMS (Knowing How)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **Lens** | RFC-070/101 | Expertise injection. Heuristics, validators, personas. "Capable Lenses" execute AND evaluate. | ✅ WORKING: Auto-selection works |
| **Skills** | RFC-011/087/111 | Action capabilities: instructions, scripts, templates. Dependency tracking. Self-learning skills. | ⚠️ PARTIAL: Defined but rarely invoked |
| **Fount** | RFC-N/A | Lens distribution and sharing. Cloud lens library. | ✅ WORKING: Downloads work |

**Total Intended Value**: Agent with domain expertise in anything.
**Actual Value Delivered**: ~70% (Lenses work, Skills underused)

---

### 📊 ANALYSIS SYSTEMS (Understanding What Exists)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **StateDag** | RFC-100 | Scan existing project → show "what exists and its health". Enable brownfield workflows (~95% of real work). | ⚠️ PARTIAL: CLI scan works, not auto-used |
| **Workspace** | RFC-103 | Workspace-aware scanning. Auto-detect related repos. Cross-reference validation. | ⚠️ PARTIAL: Detection works, not wired |
| **SourceContext** | RFC-103 | Symbol extraction from code. Know what's exported/imported. | ✅ WORKING: Used by analysis |

**Total Intended Value**: Agent that understands existing codebases.
**Actual Value Delivered**: ~40% (tools exist, not automatic)

---

### 🔍 INTROSPECTION SYSTEMS (Understanding Itself)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **Mirror** | RFC-015 | Self-introspection toolkit. Examine own code, detect patterns, propose improvements, learn. Model-aware routing. | ⚠️ PARTIAL: Tools exist, rarely invoked |
| **Self** | RFC-085 | Singleton for self-knowledge. Source introspection, analysis, proposals. Thread-safe. | ⚠️ PARTIAL: Exists, not automatic |

**Total Intended Value**: Agent that improves itself over time.
**Actual Value Delivered**: ~20% (tools exist, never auto-triggered)

---

### 📈 AUTONOMOUS SYSTEMS (Working Without Prompting)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **BacklogManager** | RFC-046/115 | Self-directed goal generation. Extract signals (tests, TODOs, type errors). Prioritize. Execute. | ❌ ORPHANED: Exists but not auto-run |
| **AutonomousLoop** | RFC-046 | Execute goals from backlog using Agent. | ❌ ORPHANED: Never triggered |
| **EpicDecomposer** | RFC-115 | Decompose ambitious goals into milestones. Track progress. | ❌ ORPHANED: Never triggered |

**Total Intended Value**: Agent that finds and fixes issues without being asked.
**Actual Value Delivered**: ~5% (infrastructure exists, never runs)

---

### 📜 LINEAGE SYSTEMS (Tracking Changes)

| Module | RFC | Intended Value | Integration Status |
|--------|-----|----------------|-------------------|
| **LineageStore** | RFC-121 | Track complete lineage: which goal spawned artifact, which model wrote it, edits made, relationships. | ⚠️ PARTIAL: Server routes, not Agent |
| **HumanEditDetector** | RFC-121 | Detect when humans edited AI-generated files. | ✅ WORKING: Detection works |

**Total Intended Value**: Full audit trail of everything.
**Actual Value Delivered**: ~30% (exists but not wired to Agent)

---

### SUMMARY: INTENDED vs DELIVERED VALUE

| Category | Intended Value | Delivered | Gap |
|----------|---------------|-----------|-----|
| Memory | Never forget anything | ~30% | Simulacrum/Briefing partial, rest orphaned |
| Intelligence | Understand YOUR project | ~10% | Bootstrap works but feeds orphans |
| Execution | Parallel, self-correcting | ~60% | Agent+Convergence work |
| Safety | Can't break things | ~40% | Recovery works, guardrails manual |
| Routing | Smart instant decisions | ~50% | Planners work, routing underused |
| Expertise | Domain knowledge | ~70% | Lenses work, Skills underused |
| Analysis | Understand codebases | ~40% | Tools exist, not automatic |
| Introspection | Self-improvement | ~20% | Tools exist, never triggered |
| Autonomous | Works without prompting | ~5% | Infrastructure exists, never runs |
| Lineage | Full audit trail | ~30% | Server only, not Agent |

**OVERALL: ~35% of intended value is actually delivered.**

The remaining 65% is built, documented, tested — but not wired together.

---

## 1. ENTRY POINTS (How Users Get In)

| Entry | File | Context Built | Passed To | BROKEN? |
|-------|------|---------------|-----------|---------|
| `sunwell "goal"` | `cli/main.py:_run_agent()` | `build_workspace_context()` → `RunRequest.context` | `Agent.run()` | ⚠️ Partial |
| `sunwell chat` | `cli/chat.py:chat()` | `_build_smart_workspace_context()` → system prompt | Chat loop | ✅ Works |
| `sunwell agent run` | `cli/agent/run.py` | Only `{"cwd": ...}` | `Naaru.run()` | ❌ BROKEN |
| `sunwell -s shortcut` | `cli/shortcuts.py` | `exec_context` dict | `SkillExecutor` | ⚠️ Partial |
| HTTP API | `server/main.py` | None | ??? | ❌ Unknown |

**KEY FINDING**: 4 different entry points build context 4 different ways.

---

## 2. EXECUTION ENGINES

### Agent (cli/main.py path)
```
RunRequest.context["workspace_context"]
    ↓
Agent._workspace_context (field I added)
    ↓
_plan_with_signals() → planning_context dict
    ↓
HarmonicPlanner._format_context() → checks specific keys
    ↓
_execute_task_streaming() → includes in prompt
```

### Naaru (cli/agent/run.py path)
```
run_context = {"cwd": str(project.root)}
    ↓
Naaru.run(goal, context=run_context)
    ↓
Worker execution
    ↓
Task prompts → NO WORKSPACE CONTEXT
```

**KEY FINDING**: Agent and Naaru are PARALLEL systems, not hierarchical. Context doesn't flow between them.

---

## 3. MEMORY SYSTEMS (What Gets Remembered)

| System | Location | Produces | Consumed By | Persists? |
|--------|----------|----------|-------------|-----------|
| **LearningStore** | `agent/learning.py` | `format_for_prompt()` | Task execution | Runtime only |
| **Simulacrum** | `simulacrum/core/store.py` | `PlanningContext` | HarmonicPlanner | ✅ Disk |
| **Briefing** | `memory/briefing.py` | `to_prompt()` | Agent planning | ✅ Disk |
| **TeamKnowledge** | `team/unified.py` | `TeamKnowledgeContext` | ??? | ✅ Disk |
| **SessionTracker** | `session/tracker.py` | Session ID | ??? | Runtime |
| **DecisionMemory** | `intelligence/decisions.py` | Past decisions | ??? | ✅ Disk |
| **FailureMemory** | `intelligence/failures.py` | Failure patterns | ??? | ✅ Disk |

**KEY FINDING**: 7+ separate memory systems. They don't share a common interface.

### What Memory Produces vs What Tasks Consume

```
SimulacrumStore.retrieve_for_planning()
    → PlanningContext(facts, constraints, dead_ends, templates, heuristics, patterns)
    → HarmonicPlanner receives this
    → Gets converted to Convergence slots
    → Used during PLANNING only
    
BUT: Task execution only sees:
    - self._workspace_context (if set)
    - learnings_context from LearningStore
    
WHERE IS: facts, constraints, dead_ends, templates from Simulacrum?
ANSWER: DISCARDED after planning. Never reaches task execution.
```

---

## 4. CONTEXT CLASSES (The Fragmentation)

### Workspace/Project Context
| Class | File | Purpose | Used By |
|-------|------|---------|---------|
| `WorkspaceContext` (dict) | `cli/helpers.py` | Project type, files, tree | main.py only |
| `ProjectContext` | `intelligence/context.py` | Project analysis | intelligence module |
| `IDEContext` | `context/ide.py` | IDE state | ??? |
| `ResolvedContext` | `context/reference.py` | @ reference resolution | context resolver |
| `ExternalContext` | `external/context.py` | External tools | external module |
| `DagContext` | `execution/manager.py` | DAG execution | execution module |
| `BacklogContext` | `execution/context.py` | Backlog state | backlog module |
| `WriterContext` | `workflow/engine.py` | Workflow state | workflow module |

**KEY FINDING**: 8 different "context" concepts. None share a base class.

### Session/State
| Class | File | Purpose |
|-------|------|---------|
| `ChatState` | `cli/chat.py` | Chat session state |
| `RunState` | `server/runs.py` | HTTP run state |
| `WorkflowState` | `workflow/state.py` | Workflow execution |
| `RecoveryState` | `recovery/types.py` | Error recovery |
| `HandoffState` | `runtime/handoff.py` | Agent handoff |
| `IndexState` | `indexing/service.py` | Index build state |
| `ValidationState` | `surface/types.py` | Validation state |

---

## 5. WHAT FLOWS WHERE (The Actual Data Path)

### Goal → Response (Current Broken Flow)

```
USER: sunwell "what is this project?"
       │
       ▼
main.py: GoalFirstGroup.parse_args()
       │ ctx.obj["_goal"] = goal
       ▼
main.py: _run_goal()
       │
       ▼
main.py: _run_agent()
       │
       ├─── build_workspace_context(workspace) ✅ BUILT
       │         → {path, name, type, framework, key_files, tree}
       │
       ├─── format_workspace_context() ✅ FORMATTED
       │         → markdown string
       │
       ├─── RunRequest(context={"workspace_context": prompt, ...}) ✅ PASSED
       │
       ▼
Agent.run(request)
       │
       ├─── self._workspace_context = request.context.get("workspace_context") ✅ STORED
       │
       ├─── _load_memory(request)
       │         ├─── _load_briefing() → Briefing from disk
       │         └─── Simulacrum session (if configured)
       │
       ├─── extract_signals(goal) → complexity, needs_tools, etc.
       │
       ├─── _plan_with_signals(goal, signals, request.context)
       │         │
       │         ├─── planning_context = dict(context)
       │         │         → includes workspace_context ✅
       │         │
       │         ├─── Add learnings_context ✅
       │         ├─── Add lens_context (if lens) ✅
       │         ├─── Add briefing (if loaded) ✅
       │         ├─── Add prefetched_files ✅
       │         │
       │         ▼
       │    HarmonicPlanner.plan_with_metrics(goal, planning_context)
       │         │
       │         ├─── SimulacrumStore.retrieve_for_planning(goal)
       │         │         → PlanningContext(facts, constraints, dead_ends...)
       │         │         → USED FOR CANDIDATE GENERATION ONLY
       │         │         → THEN DISCARDED ❌
       │         │
       │         ├─── _generate_candidates()
       │         │         └─── ArtifactPlanner._format_context()
       │         │                   → Only checks: cwd, files, description
       │         │                   → workspace_context KEY NOT CHECKED ❌
       │         │
       │         └─── Returns: task list
       │
       ├─── _execute_with_gates()
       │         │
       │         ▼
       │    _execute_task_streaming(task)
       │         │
       │         ├─── learnings_context = self._learning_store.format_for_prompt()
       │         │
       │         ├─── if self._workspace_context: ✅ CHECKED
       │         │         context_sections.append(workspace_context)
       │         │
       │         ├─── Build prompt with context_block
       │         │
       │         └─── model.generate(prompt) → RESPONSE
       │
       └─── Return response

WHERE IT BREAKS:
1. ArtifactPlanner._format_context() doesn't check "workspace_context" key
2. Planner generates tasks WITHOUT workspace awareness
3. Task descriptions are generic ("Complete this task: what is this project?")
4. Model sees workspace context but task description doesn't reference it
```

---

## 6. WHAT'S WASTED (Built but Never Used)

| Data | Built In | Used By | WASTED? |
|------|----------|---------|---------|
| `PlanningContext.facts` | Simulacrum | HarmonicPlanner | ❌ Only during planning, not execution |
| `PlanningContext.templates` | Simulacrum | HarmonicPlanner | ❌ Only during planning |
| `Briefing.hazards` | memory/briefing.py | ??? | ❌ Never injected into tasks |
| `Briefing.hot_files` | memory/briefing.py | Prefetch | ✅ Used |
| `TeamKnowledgeContext` | team/unified.py | ??? | ❌ No integration found |
| `DecisionMemory` | intelligence/decisions.py | ??? | ❌ No integration found |
| `FailureMemory` | intelligence/failures.py | ??? | ❌ No integration found |
| `workspace_context["tree"]` | helpers.py | Prompt | ✅ Used |
| `workspace_context["entry_points"]` | helpers.py | ??? | ⚠️ In prompt, unclear if model uses |

---

## 7. PARALLEL UNIVERSES (Systems That Don't Talk)

### Universe A: Agent System
- `Agent` (agent/core.py)
- `LearningStore` (agent/learning.py)
- `Briefing` (memory/briefing.py)
- `ValidationRunner` (agent/validation.py)

### Universe B: Naaru System
- `Naaru` (naaru/coordinator.py)
- `NaaruWorker` (naaru/shards.py)
- `Convergence` (convergence/loop.py)
- `MessageBus` (naaru/core/bus.py)

### Universe C: Planning System
- `HarmonicPlanner` (naaru/planners/harmonic.py)
- `ArtifactPlanner` (naaru/planners/artifact.py)
- `AgentPlanner` (naaru/planners/agent.py)
- `GoalPlanner` (agent/planner.py)

### Universe D: Memory System
- `SimulacrumStore` (simulacrum/core/store.py)
- `ConversationDAG` (simulacrum/core/core.py)
- `SessionIndex` (simulacrum/identity.py)

### Universe E: Intelligence System
- `ProjectContext` (intelligence/context.py)
- `DecisionMemory` (intelligence/decisions.py)
- `FailureMemory` (intelligence/failures.py)

**NO UNIFIED BUS CONNECTING THESE UNIVERSES.**

---

## 8. THE FIX: Unified Context Architecture

### Required: Single Context Object

```python
@dataclass
class UnifiedContext:
    """THE context that flows through EVERYTHING."""
    
    # Workspace (where we are)
    workspace: WorkspaceInfo
    cwd: Path
    project_name: str
    project_type: str
    key_files: list[str]
    directory_tree: str
    
    # Memory (what we remember)
    learnings: list[Learning]
    facts: list[str]
    constraints: list[str]
    dead_ends: list[str]
    
    # Session (current state)
    goal: str
    task_graph: TaskGraph | None
    artifacts_created: list[str]
    
    # Briefing (continuity)
    briefing: Briefing | None
    
    def to_planning_prompt(self) -> str: ...
    def to_task_prompt(self, task: Task) -> str: ...
    def to_memory_update(self) -> dict: ...
```

### Required: Single Entry Point

```python
async def execute(goal: str, workspace: Path) -> Result:
    """THE entry point. Everything flows from here."""
    
    # 1. Build context ONCE
    ctx = UnifiedContext.build(workspace, goal)
    
    # 2. Load memory INTO context
    ctx.load_memory()
    
    # 3. Plan WITH context
    tasks = await plan(goal, ctx)
    
    # 4. Execute WITH context (context flows to each task)
    for task in tasks:
        result = await execute_task(task, ctx)
        ctx.update(result)  # Context evolves
    
    # 5. Save memory FROM context
    ctx.save_memory()
    
    return Result(ctx)
```

---

## 9. IMMEDIATE ACTIONS

1. **Create `UnifiedContext`** - Single source of truth
2. **Refactor entry points** - All flow through one path
3. **Pass context explicitly** - No hidden state
4. **Remove duplicate systems** - One memory, one planner
5. **Connect universes** - Agent, Naaru, Memory must share context

---

## 10. FILES TO MODIFY

| File | Action |
|------|--------|
| `agent/core.py` | Use UnifiedContext instead of scattered fields |
| `naaru/coordinator.py` | Receive context from Agent, don't build own |
| `naaru/planners/*.py` | Receive context, use it in prompts |
| `cli/main.py` | Build UnifiedContext, pass everywhere |
| `cli/agent/run.py` | DELETE or redirect to main.py |
| `memory/briefing.py` | Integrate into UnifiedContext |
| `simulacrum/core/store.py` | Integrate into UnifiedContext |
| `agent/learning.py` | Integrate into UnifiedContext |

---

## 11. SERVER ENTRY POINT ANALYSIS

### server/routes/agent.py - ANOTHER PARALLEL UNIVERSE

```python
# _execute_agent() builds RunRequest with MINIMAL context:
request = AgentRunRequest(
    goal=run.goal,
    context={"cwd": str(workspace)},  # ← ONLY cwd, no workspace_context!
    cwd=workspace,
    options=RunOptions(trust=run.trust, timeout_seconds=run.timeout),
)
```

**This is the Studio/API entry point - it's BROKEN the same way CLI was before our fix.**

### Context Created But Discarded:
| Data | Location | Fate |
|------|----------|------|
| `run.workspace` | `RunState` | Used to resolve Path |
| `run.project_id` | `RunState` | Passed to `resolve_project()` |
| `project.root` | After resolution | Used as workspace |
| Workspace context | **NEVER BUILT** | ❌ Missing |

**FIX NEEDED**: `server/routes/agent.py:_execute_agent()` must call `build_workspace_context()` and include it in the request.

---

## 12. NAARU INTERNAL ARCHITECTURE

### Naaru is NOT a separate entry point

Per RFC-110, Naaru is internal coordination used BY Agent:
```
Agent.run()
    └── _init_naaru()
            └── Naaru(workspace=self.cwd, synthesis_model=self.model, ...)
```

But there's ALSO a direct CLI:
```
sunwell agent run "goal"
    └── cli/agent/run.py
            └── Naaru.run(goal, context={"cwd": str(project.root)})  # ← BYPASSES Agent
```

**This creates two execution universes:**

| Path | Agent Involved? | Context Rich? | Memory Loaded? |
|------|-----------------|---------------|----------------|
| `sunwell "goal"` | ✅ Yes | ✅ Yes | ✅ Yes |
| `sunwell agent run` | ❌ No | ❌ No | ❌ No |

**RECOMMENDATION**: Delete `cli/agent/run.py` or make it call through Agent.

---

## 13. PLANNERS - THE CONTEXT SINK

### Three Planners, Three Formats

| Planner | File | Context Format |
|---------|------|----------------|
| `AgentPlanner` | `naaru/planners/agent.py` | `_format_context()` - checks workspace_context ✅ |
| `ArtifactPlanner` | `naaru/planners/artifact.py` | `_format_context()` - only checks cwd, files ❌ |
| `HarmonicPlanner` | `naaru/planners/harmonic.py` | Uses Simulacrum + Convergence |

### ArtifactPlanner._format_context() - THE GAP

```python
def _format_context(self, context: dict[str, Any] | None) -> str:
    if not context:
        return "No additional context."
    
    lines = []
    if "cwd" in context:
        lines.append(f"Working directory: {context['cwd']}")
    if "files" in context:
        lines.append(f"Relevant files: {', '.join(context['files'])}")
    if "description" in context:
        lines.append(f"Context: {context['description']}")
    
    # workspace_context is NEVER checked!
    return "\n".join(lines) or "No additional context."
```

**FIX NEEDED**: Add workspace_context handling to ArtifactPlanner.

---

## 14. MEMORY RETRIEVAL → TASK EXECUTION GAP

### HarmonicPlanner retrieves rich memory:

```python
# naaru/planners/harmonic.py:_plan_iteration()
planning_memory = self.simulacrum.retrieve_for_planning(goal)
# → PlanningContext with: facts, constraints, dead_ends, templates, heuristics, patterns
```

### But this memory is used ONLY for candidate generation:

```python
# The PlanningContext is used to:
# 1. Provide context for candidate tasks
# 2. Score candidates
# 3. Select best candidate

# After selection, PlanningContext is DISCARDED
# The winning Task has only: id, description, mode, tools, target_path
```

### Task execution never sees:
- `planning_memory.facts`
- `planning_memory.constraints`
- `planning_memory.dead_ends`
- `planning_memory.templates`
- `planning_memory.patterns`

**RESULT**: Model makes same mistakes because constraints/dead_ends aren't in task prompts.

---

## 15. BRIEFING - UNDERUTILIZED

### Briefing contains rich continuity data:

```python
@dataclass
class Briefing:
    mission: str              # What we're doing
    status: BriefingStatus    # Current state
    progress: str             # Where we are
    last_action: str          # What just happened
    next_action: str | None   # What should happen
    hazards: tuple[str, ...]  # What NOT to do (max 3)
    blockers: tuple[str, ...] # What's blocking
    hot_files: tuple[str, ...] # Files to look at
    predicted_skills: tuple[str, ...] # Skills needed
    suggested_lens: str | None # Best lens
```

### But it's only used for:
1. **Prefetch dispatch** - hot_files trigger file preloading
2. **Planning prompt** - `briefing.to_prompt()` added to planning_context

### NOT used for:
- Task execution prompts (hazards not injected)
- Skill selection (predicted_skills ignored)
- Lens auto-selection (suggested_lens sometimes checked)

---

## 16. FULL MODULE INVENTORY

### Core Execution (what actually runs things)
| Module | Files | Purpose | Context Aware? |
|--------|-------|---------|----------------|
| `agent/` | 17 | Primary execution engine | ⚠️ Partial |
| `naaru/` | 60 | Parallel coordination | ❌ Minimal |
| `execution/` | 4 | DAG execution | ❌ None |
| `workflow/` | 5 | Workflow engine | ❌ None |

### Memory/Intelligence (what's remembered)
| Module | Files | Purpose | Integrated? |
|--------|-------|---------|-------------|
| `simulacrum/` | 41 | Conversation memory | ⚠️ Planning only |
| `memory/` | 2 | Briefing | ⚠️ Prefetch only |
| `intelligence/` | 7 | Project intelligence | ❌ Orphaned |
| `team/` | 9 | Team knowledge | ❌ Orphaned |
| `session/` | 3 | Session tracking | ❌ Orphaned |

### Analysis/Context (what's detected)
| Module | Files | Purpose | Integrated? |
|--------|-------|---------|-------------|
| `analysis/` | 7 | Workspace analysis | ❌ Orphaned |
| `context/` | 5 | @ reference resolution | ✅ Used |
| `workspace/` | 4 | Workspace detection | ⚠️ CLI only |
| `environment/` | 6 | Environment analysis | ❌ Orphaned |

### Routing/Planning (what decides what)
| Module | Files | Purpose | Context Aware? |
|--------|-------|---------|----------------|
| `routing/` | 5 | Cognitive routing | ⚠️ Partial |
| `reasoning/` | 5 | LLM reasoning | ❌ None |
| `backlog/` | 7 | Goal decomposition | ❌ None |

### Support Systems
| Module | Files | Purpose |
|--------|-------|---------|
| `tools/` | 17 | Tool execution |
| `skills/` | 9 | Skill system |
| `lens/` | 5 | Expertise injection |
| `providers/` | 13 | Model providers |
| `security/` | 11 | Security/approval |

### Likely Orphaned (no clear integration point)
| Module | Files | Evidence |
|--------|-------|----------|
| `vortex/` | 6 | No imports found in core |
| `spectrum/` | 1 | Single file, unclear purpose |
| `fount/` | 4 | No references in agent/ |
| `lineage/` | 7 | Server routes only |
| `mirror/` | 9 | Self-improvement, unclear use |
| `self/` | 5 | Proposals, unclear use |

---

## 17. THE FUNDAMENTAL PROBLEM

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER GOAL                                 │
│                    "what is this project?"                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ENTRY POINT                                  │
│        (one of 4+ ways in, each builds different context)        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    Agent      │   │    Naaru      │   │    Server     │
│ (has context) │   │ (no context)  │   │ (no context)  │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Planner     │   │   Workers     │   │   ???         │
│ (loses some)  │   │ (sees cwd)    │   │               │
└───────┬───────┘   └───────────────┘   └───────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                         TASK EXECUTION                            │
│     (sees workspace_context + learnings, but NOT:                 │
│      - Simulacrum facts/constraints/dead_ends                     │
│      - Briefing hazards                                           │
│      - Team knowledge                                             │
│      - Project intelligence)                                      │
└───────────────────────────────────────────────────────────────────┘
```

**THE FIX**: Single context object, single entry path, context flows to ALL stages.

---

## 18. DUPLICATE IMPLEMENTATIONS

### Workspace Context Building (SAME LOGIC, 3 PLACES)

| Location | Function | Keys Produced |
|----------|----------|---------------|
| `cli/helpers.py` | `build_workspace_context()` | path, name, type, framework, key_files, entry_points, tree |
| `cli/chat.py` | `_build_smart_workspace_context()` | path, name, type, framework, key_files, entry_points, tree |
| `cli/chat.py` | `_build_workspace_context()` | Calls `_build_smart_workspace_context()` |

**These are IDENTICAL implementations. One calls the other, but both exist.**

### Project Detection (SAME PATTERNS, 2 PLACES)

| Location | Function |
|----------|----------|
| `cli/helpers.py` | `_detect_project_type()` |
| `cli/chat.py` | `_detect_project_type()` |

Both check for: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, etc.

### Directory Tree Building (SAME LOGIC, 2 PLACES)

| Location | Function |
|----------|----------|
| `cli/helpers.py` | `_build_directory_tree()` |
| `cli/chat.py` | `_build_directory_tree()` |

### CONSOLIDATION NEEDED:
1. Keep ONE implementation in `cli/helpers.py`
2. Delete duplicates from `cli/chat.py`
3. Import from `helpers` everywhere

---

## 19. CROSS-CUTTING CONCERNS

### Trust Level
Passed around everywhere but not part of any context object:
- `RunRequest.options.trust`
- `ChatState.trust_level`
- `ToolPolicy.trust_level`
- `RunState.trust`

### Working Directory
Multiple names for the same thing:
- `cwd` (in RunRequest, Agent)
- `workspace` (in Naaru, ToolExecutor)
- `project.root` (in Project)
- `workspace_root` (in ContextResolver)

### Model Reference
Different ways to pass the model:
- `Agent.model`
- `Naaru.synthesis_model`
- `ToolExecutor` (no model)
- `HarmonicPlanner.model`
- `ChatState.model`

---

## 20. RECOMMENDED ARCHITECTURE

### Phase 1: Create SessionContext (Immediate)

```python
@dataclass
class SessionContext:
    """Single source of truth for all execution context."""
    
    # Identity
    session_id: str
    cwd: Path
    project: Project | None
    
    # Workspace (auto-detected)
    project_name: str
    project_type: str
    framework: str | None
    key_files: list[tuple[str, str]]
    entry_points: list[str]
    directory_tree: str
    
    # Memory (loaded on init)
    briefing: Briefing | None
    learnings: list[Learning]
    facts: list[str]
    constraints: list[str]
    dead_ends: list[str]
    
    # Execution state
    goal: str
    tasks: list[Task]
    artifacts_created: list[str]
    
    # Options
    trust: str
    model_name: str
    lens: Lens | None
    
    @classmethod
    def build(cls, cwd: Path, goal: str, trust: str = "workspace") -> SessionContext:
        """Build complete context from workspace and goal."""
        ...
    
    def to_planning_prompt(self) -> str:
        """Format for planner consumption."""
        ...
    
    def to_task_prompt(self, task: Task) -> str:
        """Format for task execution."""
        ...
    
    def update_from_result(self, task: Task, result: TaskResult) -> None:
        """Update state after task completion."""
        ...
```

### Phase 2: Single Entry Point

```python
# cli/main.py
async def execute(goal: str, options: ExecuteOptions) -> None:
    """THE entry point. Period."""
    
    ctx = SessionContext.build(
        cwd=options.cwd or Path.cwd(),
        goal=goal,
        trust=options.trust,
    )
    
    agent = Agent(ctx)
    async for event in agent.run():
        emit(event)
```

### Phase 3: Delete Redundant Paths

1. `cli/agent/run.py` → DELETE (direct Naaru access)
2. `cli/chat.py:_build_smart_workspace_context()` → IMPORT from helpers
3. `server/routes/agent.py:_execute_agent()` → USE SessionContext

### Phase 4: Wire Memory Through

```python
# In Agent.run()
# 1. Memory loads INTO SessionContext
ctx.load_memory()

# 2. Planner receives SessionContext (not dict)
tasks = await plan(ctx)

# 3. Task execution receives SessionContext
for task in tasks:
    result = await execute_task(task, ctx)
    ctx.update_from_result(task, result)

# 4. Memory saves FROM SessionContext  
ctx.save_memory()
```

---

## 21. SUMMARY: WHAT'S BROKEN

| Issue | Impact | Fix |
|-------|--------|-----|
| **4 entry points** | Inconsistent behavior | Single entry |
| **3 context builders** | Code duplication | Single builder |
| **Memory not flowing** | Model repeats mistakes | Wire through |
| **Orphaned modules** | Wasted code | Remove or integrate |
| **Server has no context** | Studio is broken | Same fix as CLI |
| **Planners lose context** | Poor task descriptions | Pass SessionContext |

---

## 22. FILES REQUIRING IMMEDIATE ACTION

### High Priority (Context Flow)
| File | Action |
|------|--------|
| `agent/request.py` | Add SessionContext integration |
| `agent/core.py` | Replace scattered fields with SessionContext |
| `naaru/planners/artifact.py` | Add workspace_context handling |
| `server/routes/agent.py` | Call build_workspace_context() |

### Medium Priority (Deduplication)
| File | Action |
|------|--------|
| `cli/chat.py:240-330` | Delete duplicate context functions |
| `cli/agent/run.py` | DELETE or redirect to main.py |

### Low Priority (Cleanup)
| File | Action |
|------|--------|
| `spectrum/` | Investigate/delete if orphaned |
| `cli/chat/command.py` | Fix import of deleted spectrum |

---

## 23. SESSION TRACKING - ANOTHER ORPHAN

### SessionTracker exists but Agent doesn't use it

```python
# session/tracker.py exists with:
class SessionTracker:
    def record_goal_complete(...) -> GoalSummary
    def get_summary() -> SessionSummary
```

### Used only by:
- `server/routes/memory.py` - HTTP endpoint
- `cli/session.py` - Session CLI commands
- `lineage/human_detection.py` - Human activity detection

### NOT used by:
- `Agent` - doesn't track sessions
- `Naaru` - no session awareness
- `main.py` - doesn't create session

**RESULT**: Session tracking exists but the core execution path doesn't use it.

---

## 24. COMPLETE CONTEXT MAP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                         │
│                     "sunwell 'what is this project?'"                        │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                          ENTRY POINTS                                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ main.py     │ │ chat.py     │ │ agent/run.py│ │ server/     │            │
│  │ _run_goal() │ │ chat()      │ │ run_cmd()   │ │ routes/     │            │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘            │
│         │ ✅            │ ✅            │ ❌            │ ❌                 │
│    builds ctx     builds ctx      NO ctx         NO ctx                     │
└─────────┼───────────────┼───────────────┼───────────────┼───────────────────┘
          │               │               │               │
          ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXECUTION                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                             │
│  │   Agent     │ │ Chat Loop   │ │   Naaru     │                             │
│  │ (run())     │ │ (generate())│ │ (run())     │                             │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                             │
│         │ ✅            │ ✅            │ ❌                                  │
│    has ctx         has ctx         NO ctx                                    │
└─────────┼───────────────┼───────────────┼───────────────────────────────────┘
          │               │               │
          ▼               │               │
┌─────────────────────────┼───────────────┼───────────────────────────────────┐
│                   MEMORY SYSTEMS        │                                    │
│  ┌─────────────────────┐│               │                                    │
│  │ Simulacrum          ││               │                                    │
│  │ - PlanningContext   ││               │     NOT CONNECTED                  │
│  │ - facts, constraints│◀───────────────┼─────────────────────               │
│  │ - dead_ends         ││               │                                    │
│  │ - templates         ││               │                                    │
│  └──────────┬──────────┘│               │                                    │
│             │           │               │                                    │
│  ┌──────────▼──────────┐│               │                                    │
│  │ Briefing            ││               │                                    │
│  │ - hazards           ││               │   ❌ NOT USED in task execution    │
│  │ - hot_files         ├┘               │                                    │
│  │ - predicted_skills  │                │                                    │
│  └─────────────────────┘                │                                    │
│                                         │                                    │
│  ┌─────────────────────┐                │                                    │
│  │ LearningStore       │                │                                    │
│  │ - learnings         │◀───────────────┘   ✅ USED (partially)              │
│  └─────────────────────┘                                                     │
│                                                                              │
│  ┌─────────────────────┐                                                     │
│  │ Team/Intelligence   │                    ❌ ORPHANED                       │
│  │ - DecisionMemory    │                                                     │
│  │ - FailureMemory     │                                                     │
│  │ - TeamKnowledge     │                                                     │
│  └─────────────────────┘                                                     │
│                                                                              │
│  ┌─────────────────────┐                                                     │
│  │ SessionTracker      │                    ❌ ORPHANED from Agent            │
│  │ - goal history      │                                                     │
│  │ - metrics           │                                                     │
│  └─────────────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PLANNING                                          │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐     │
│  │ HarmonicPlanner     │ │ AgentPlanner        │ │ ArtifactPlanner     │     │
│  │ (harmonic.py)       │ │ (agent.py)          │ │ (artifact.py)       │     │
│  └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘     │
│             │ ⚠️                    │ ✅                    │ ❌              │
│     uses Simulacrum          checks ws_ctx          NO ws_ctx check          │
│     DISCARDS after                                                           │
└─────────────┼───────────────────────┼───────────────────────┼───────────────┘
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TASK EXECUTION                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ _execute_task_streaming()                                             │   │
│  │                                                                       │   │
│  │ Context available:                                                    │   │
│  │ ✅ workspace_context (if set in Agent._workspace_context)             │   │
│  │ ✅ learnings_context (from LearningStore)                             │   │
│  │                                                                       │   │
│  │ Context NOT available:                                                │   │
│  │ ❌ Simulacrum facts/constraints/dead_ends                             │   │
│  │ ❌ Briefing hazards/predicted_skills                                  │   │
│  │ ❌ Team knowledge                                                     │   │
│  │ ❌ Decision memory                                                    │   │
│  │ ❌ Failure memory                                                     │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                          │
│                      Model generates response                                │
│                    with partial context awareness                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 25. NEXT STEPS (PRIORITIZED)

### P0: Make It Work (Day 1)
1. **`server/routes/agent.py`**: Add `build_workspace_context()` call - Studio is broken
2. **`naaru/planners/artifact.py`**: Add workspace_context handling - tasks are blind

### P1: Stop Duplicating (Week 1)
3. **`cli/chat.py`**: Delete duplicate context functions, import from `helpers.py`
4. **`cli/agent/run.py`**: Redirect to main.py or delete

### P2: Wire Memory (Week 2)
5. **Create `SessionContext`**: Single context class
6. **Flow Simulacrum to execution**: facts/constraints/dead_ends in task prompts
7. **Flow Briefing hazards**: Include in task prompts

### P3: Consolidate (Month 1)
8. **Integrate intelligence/team**: Wire DecisionMemory, FailureMemory
9. **Add SessionTracker to Agent**: Track goal completion
10. **Remove orphaned modules**: Clean up unused code
