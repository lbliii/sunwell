# Sunwell Architecture: Memory Facade & Unified Entry Points

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-24

## Executive Summary

This RFC proposes a **Memory Facade** (`PersistentMemory`) that unifies existing memory stores and a **Session Context** (`SessionContext`) that consolidates fragmented context-building code. The core insight: we have good components that aren't wired together.

---

## The Core Insight

Sunwell has **two distinct concerns** that are currently conflated:

1. **Session State** — What's happening RIGHT NOW (goal, tasks, progress, files changed)
2. **Persistent Memory** — What we remember ACROSS sessions (decisions, failures, patterns, team knowledge)

The Agent loop doesn't need something "beside" it — it needs:
- **Input**: Rich context flowing INTO the loop
- **Access**: Persistent memory available DURING the loop
- **Output**: Updated memory flowing OUT of the loop

**And the UI needs access to ALL of this** — both for display and for triggering actions.

---

## Current State Inventory

### ✅ Components That Already Exist

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| `DecisionMemory` | `intelligence/decisions.py:154` | ✅ Complete | Records architectural decisions, has semantic search |
| `FailureMemory` | `intelligence/failures.py:97` | ✅ Complete | Tracks failed approaches with pattern detection |
| `PatternProfile` | `intelligence/patterns.py:24` | ✅ Complete | Learns user preferences, has bootstrap support |
| `SimulacrumStore` | `simulacrum/core/store.py:252` | ✅ Complete | Session persistence, learnings, conversation DAG |
| `TeamKnowledgeStore` | `team/store.py:57` | ✅ Complete | Shared team knowledge with sync |
| `Briefing` | `memory/briefing.py` | ✅ Complete | Session continuity, prefetch hints |
| `build_workspace_context()` | `cli/helpers.py:23` | ✅ Complete | Project detection, key files, tree |

### ⚠️ Problems With Current Wiring

| Problem | Evidence | Impact |
|---------|----------|--------|
| **4+ context-building implementations** | `cli/main.py:483`, `cli/agent/run.py:523`, `cli/chat.py:1011`, `cli/chat/command.py` | Inconsistent context across entry points |
| **Memory loaded inside Agent** | `agent/core.py:483-550` (`_load_memory`) | Hard to test, memory not available for planning |
| **DecisionMemory not queried during planning** | No calls to `find_relevant_decisions()` in planners | Agent repeats rejected approaches |
| **FailureMemory not queried during planning** | No calls to `check_similar_failures()` in planners | Agent repeats failed approaches |
| **cli/agent/run.py bypasses Agent** | Direct Naaru calls | No memory, no briefing, no learnings |

### 🎯 What This RFC Creates

| Component | Purpose |
|-----------|---------|
| `SessionContext` | All session state in one object — goal, workspace, briefing, lens, options |
| `PersistentMemory` | Unified access to all memory stores — decisions, failures, patterns, learnings |
| `MemoryContext` | Query result from memory — constraints, dead ends, patterns |
| `WorkspaceManager` | Server-side memory cache — loaded once, used by all requests |

### 🗑️ What This RFC Deletes

| Component | Reason |
|-----------|--------|
| `RunRequest` | Replaced by `SessionContext` |
| `cli/agent/run.py` | Bypassed Agent, violated architecture |
| `Agent._load_memory()` | Logic moved to `PersistentMemory.load()` |
| `Agent._load_briefing()` | Logic moved to `SessionContext.build()` |
| Scattered `build_workspace_context()` calls | Unified in `SessionContext.build()` |

---

## The Four-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LAYER 1: ENTRY                                     │
│                                                                              │
│   CLI / Server / Studio / API → ALL create the same SessionContext          │
│                                                                              │
│   SessionContext.build(workspace, goal, options)                            │
│       ├── Detect project (type, framework, key files)                       │
│       ├── Load briefing (if exists)                                         │
│       └── Return: SessionContext with workspace + goal + options            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LAYER 2: MEMORY                                     │
│                                                                              │
│   PersistentMemory.load(workspace)                                          │
│       ├── SimulacrumStore (conversation history, learnings)                 │
│       ├── DecisionMemory (architectural decisions)                          │
│       ├── FailureMemory (what didn't work)                                  │
│       ├── TeamKnowledge (shared team intelligence)                          │
│       └── PatternProfile (user/project preferences)                         │
│                                                                              │
│   This is a SINGLETON per workspace — loaded ONCE, available ALWAYS         │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LAYER 3: EXECUTION                                  │
│                                                                              │
│   Agent.run(session_ctx, memory)                                            │
│       │                                                                      │
│       ├── PLAN: memory.get_relevant(goal) → constraints, dead_ends          │
│       │         session_ctx.workspace_info → project context                 │
│       │         → Generate task graph                                        │
│       │                                                                      │
│       ├── EXECUTE: For each task:                                           │
│       │         memory.get_constraints(task) → "don't do X"                 │
│       │         session_ctx.briefing.hazards → "avoid Y"                    │
│       │         → Execute with full context                                  │
│       │         → Update session_ctx.artifacts_created                       │
│       │                                                                      │
│       ├── VALIDATE: Convergence loop until stable                           │
│       │         → memory.record_failure() if failed                         │
│       │                                                                      │
│       └── LEARN: Extract from execution                                      │
│                 → memory.add_learning()                                      │
│                 → memory.add_decision() if architectural                     │
│                 → session_ctx.save_briefing()                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Two Core Objects

### 1. SessionContext (All Session State)

```python
@dataclass
class SessionContext:
    """Everything about THIS execution.
    
    Consolidates:
    - Project detection (from cli/helpers.py, inlined)
    - Briefing loading (from Agent._load_briefing, moved)
    - Goal and execution state
    - Prompt formatting
    """
    
    # === IDENTITY ===
    session_id: str
    cwd: Path
    goal: str
    
    # === WORKSPACE (from build_workspace_context) ===
    project_name: str
    project_type: str          # python, node, rust, etc.
    framework: str | None      # fastapi, react, etc.
    key_files: list[tuple[str, str]]  # (path, preview)
    entry_points: list[str]
    directory_tree: str
    
    # === BRIEFING (from previous session) ===
    briefing: Briefing | None
    
    # === OPTIONS ===
    trust: str
    timeout: int
    model_name: str
    lens: Lens | None
    
    # === EXECUTION STATE (updated during run) ===
    tasks: list[Task] = field(default_factory=list)
    current_task: Task | None = None
    artifacts_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    
    # === BUILD ===
    @classmethod
    def build(cls, cwd: Path, goal: str, options: RunOptions) -> SessionContext:
        """Build session context from workspace.
        
        Inlines logic from cli/helpers.py:build_workspace_context():
        - Detects project type and framework
        - Finds key files with previews
        - Builds directory tree
        - Loads briefing from previous session
        """
        from sunwell.memory.briefing import Briefing
        
        # Inline project detection (moved from cli/helpers.py)
        project_type, framework = _detect_project_type(cwd)
        key_files = _find_key_files(cwd)
        entry_points = _find_entry_points(cwd, project_type)
        directory_tree = _build_directory_tree(cwd)
        
        # Load briefing from previous session
        briefing = Briefing.load(cwd)
        
        return cls(
            session_id=_generate_session_id(),
            cwd=cwd,
            goal=goal,
            project_name=cwd.name,
            project_type=project_type,
            framework=framework,
            key_files=key_files,
            entry_points=entry_points,
            directory_tree=directory_tree,
            briefing=briefing,
            trust=options.trust,
            timeout=options.timeout_seconds,
            model_name=options.model or "default",
            lens=options.lens,
        )
    
    # === PROMPTS ===
    def to_planning_prompt(self) -> str:
        """Format for planner."""
        ...
    
    def to_task_prompt(self, task: Task) -> str:
        """Format for task execution."""
        ...
    
    # === BRIEFING ===
    def save_briefing(self) -> None:
        """Save updated briefing for next session."""
        ...
```

### 2. PersistentMemory (Unified Memory Access)

```python
@dataclass
class PersistentMemory:
    """Unified access to all memory stores.
    
    Owns and coordinates:
    - SimulacrumStore — conversation history, learnings
    - DecisionMemory — architectural decisions
    - FailureMemory — failed approaches
    - PatternProfile — user preferences
    - TeamKnowledgeStore — shared team knowledge (optional)
    """
    
    workspace: Path
    
    # === OWNED STORES ===
    simulacrum: SimulacrumStore
    decisions: DecisionMemory
    failures: FailureMemory
    patterns: PatternProfile
    team: TeamKnowledgeStore | None
    
    # === LOAD ===
    @classmethod
    def load(cls, workspace: Path) -> PersistentMemory:
        """Load all memory for workspace.
        
        Each store loads independently — failure in one doesn't block others.
        """
        intel_path = workspace / ".sunwell" / "intelligence"
        
        return cls(
            workspace=workspace,
            simulacrum=SimulacrumStore(workspace / ".sunwell" / "memory"),
            decisions=DecisionMemory(intel_path),
            failures=FailureMemory(intel_path),
            patterns=PatternProfile.load(intel_path),
            team=_load_team_if_configured(workspace / ".sunwell" / "team"),
        )
    
    @classmethod
    def empty(cls, workspace: Path) -> PersistentMemory:
        """Create empty memory for testing."""
        intel_path = workspace / ".sunwell" / "intelligence"
        return cls(
            workspace=workspace,
            simulacrum=SimulacrumStore(workspace / ".sunwell" / "memory"),
            decisions=DecisionMemory(intel_path),
            failures=FailureMemory(intel_path),
            patterns=PatternProfile(),
            team=None,
        )
    
    # === QUERY (for planning) ===
    async def get_relevant(self, goal: str) -> MemoryContext:
        """Get all relevant memory for a goal.
        
        Queries each store and aggregates results.
        """
        relevant_decisions = await self.decisions.find_relevant_decisions(goal, top_k=5)
        similar_failures = await self.failures.check_similar_failures(goal, top_k=3)
        
        # Extract constraints from decisions (what was rejected)
        constraints = []
        for d in relevant_decisions:
            for rejected in d.rejected:
                constraints.append(f"{rejected.option}: {rejected.reason}")
        
        # Extract dead ends from failures
        dead_ends = [f.description for f in similar_failures]
        
        # Get team decisions if available
        team_decisions = []
        if self.team:
            team_ctx = await self.team.get_relevant_context(goal)
            team_decisions = team_ctx.decisions if team_ctx else []
        
        return MemoryContext(
            learnings=self.simulacrum.get_relevant_learnings(goal) if self.simulacrum else (),
            facts=(),  # TODO: Add fact extraction
            constraints=tuple(constraints),
            dead_ends=tuple(dead_ends),
            team_decisions=tuple(team_decisions),
            patterns=self._get_relevant_patterns(goal),
        )
    
    # === QUERY (for task execution) ===
    def get_task_context(self, task: Task) -> TaskMemoryContext:
        """Get memory relevant to a specific task."""
        return TaskMemoryContext(
            constraints=self.decisions.get_for_path(task.target_path),
            hazards=self.failures.get_for_path(task.target_path),
            patterns=self.patterns.get_for_type(task.mode),
        )
    
    # === RECORD (during/after execution) ===
    def add_learning(self, learning: Learning) -> None:
        """Record a new learning."""
        self.simulacrum.add_learning(learning)
    
    def add_decision(self, decision: Decision) -> None:
        """Record an architectural decision."""
        self.decisions.add(decision)
    
    def add_failure(self, failure: FailedApproach) -> None:
        """Record what didn't work."""
        self.failures.add(failure)
    
    # === SYNC ===
    def sync(self) -> None:
        """Persist all changes to disk."""
        self.simulacrum.sync()
        self.decisions.sync()
        self.failures.sync()
        if self.team:
            self.team.sync()
        self.patterns.sync()
```

---

## Supporting Types

### MemoryContext (What Memory Provides for Planning)

```python
@dataclass(frozen=True, slots=True)
class MemoryContext:
    """All memory relevant to a goal — used during planning."""
    
    # From SimulacrumStore
    learnings: tuple[Learning, ...]
    """Facts learned from past executions."""
    
    facts: tuple[str, ...]
    """Extracted facts about the codebase."""
    
    # From DecisionMemory
    constraints: tuple[str, ...]
    """Things we decided NOT to do: "Don't use Redis - too complex for our scale"."""
    
    # From FailureMemory
    dead_ends: tuple[str, ...]
    """Approaches that failed before: "Async SQLAlchemy caused connection pool issues"."""
    
    # From TeamKnowledgeStore
    team_decisions: tuple[str, ...]
    """Team-level decisions: "Team uses Pydantic v2 for all models"."""
    
    # From PatternProfile
    patterns: tuple[str, ...]
    """Style preferences: "Use snake_case for functions"."""
    
    def to_prompt(self) -> str:
        """Format for inclusion in planning prompt."""
        sections = []
        
        if self.constraints:
            sections.append("## Constraints (DO NOT violate)")
            for c in self.constraints:
                sections.append(f"- {c}")
        
        if self.dead_ends:
            sections.append("\n## Known Dead Ends (DO NOT repeat)")
            for d in self.dead_ends:
                sections.append(f"- {d}")
        
        if self.team_decisions:
            sections.append("\n## Team Decisions (follow these)")
            for t in self.team_decisions:
                sections.append(f"- {t}")
        
        if self.learnings:
            sections.append("\n## Known Facts")
            for l in self.learnings[:10]:  # Limit to top 10
                sections.append(f"- [{l.category}] {l.fact}")
        
        return "\n".join(sections) if sections else ""
```

### TaskMemoryContext (What Memory Provides for Task Execution)

```python
@dataclass(frozen=True, slots=True)
class TaskMemoryContext:
    """Memory relevant to a specific task — used during execution."""
    
    constraints: tuple[str, ...]
    """Constraints for this file/path."""
    
    hazards: tuple[str, ...]
    """Past failures involving this path."""
    
    patterns: tuple[str, ...]
    """Style patterns for this type of task."""
    
    def to_prompt(self) -> str:
        """Format for inclusion in task prompt."""
        sections = []
        
        if self.constraints:
            sections.append("CONSTRAINTS for this task:")
            for c in self.constraints:
                sections.append(f"  - {c}")
        
        if self.hazards:
            sections.append("HAZARDS (past failures with similar tasks):")
            for h in self.hazards:
                sections.append(f"  - {h}")
        
        if self.patterns:
            sections.append("PATTERNS to follow:")
            for p in self.patterns:
                sections.append(f"  - {p}")
        
        return "\n".join(sections) if sections else ""
```

### Event Types

```python
class EventType(str, Enum):
    """All events emitted during agent execution."""
    
    # Existing events
    SIGNAL = "signal"
    PLAN_START = "plan_start"
    PLAN_COMPLETE = "plan_complete"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    VALIDATION_START = "validation_start"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    COMPLETE = "complete"
    ERROR = "error"
    
    # NEW: Memory-aware events
    ORIENT = "orient"                    # Memory loaded, constraints identified
    LEARNING_ADDED = "learning_added"    # New learning extracted
    DECISION_MADE = "decision_made"      # Architectural decision recorded
    FAILURE_RECORDED = "failure_recorded" # Failed approach recorded
    BRIEFING_UPDATED = "briefing_updated" # Briefing saved for next session
```

### Workspace Identification

```python
def workspace_id(path: Path) -> str:
    """Generate stable workspace ID from path.
    
    Uses blake2b hash of resolved path for:
    - Stability (same path = same ID)
    - Privacy (ID doesn't leak path)
    - Uniqueness (no collisions)
    """
    import hashlib
    resolved = str(path.resolve())
    return hashlib.blake2b(resolved.encode(), digest_size=8).hexdigest()

# Examples:
# /Users/me/myproject → "a1b2c3d4e5f6g7h8"
# /home/user/work/api → "x9y8z7w6v5u4t3s2"
```

---

## The Agent Loop (Simplified)

```python
class Agent:
    """THE execution engine."""
    
    async def run(
        self,
        session: SessionContext,
        memory: PersistentMemory,
    ) -> AsyncIterator[AgentEvent]:
        """Execute goal with full context and memory."""
        
        # ─── PHASE 1: ORIENT ───
        # What do we know? What should we avoid?
        memory_ctx = memory.get_relevant(session.goal)
        
        yield AgentEvent(ORIENT, {
            "learnings": len(memory_ctx.learnings),
            "constraints": len(memory_ctx.constraints),
            "dead_ends": len(memory_ctx.dead_ends),
        })
        
        # ─── PHASE 2: PLAN ───
        # Decompose goal into tasks, informed by memory
        planning_prompt = session.to_planning_prompt()
        planning_prompt += memory_ctx.to_prompt()  # Include constraints!
        
        tasks = await self.planner.plan(session.goal, planning_prompt)
        session.tasks = tasks
        
        yield AgentEvent(PLAN_COMPLETE, {"tasks": len(tasks)})
        
        # ─── PHASE 3: EXECUTE ───
        for task in tasks:
            session.current_task = task
            
            # Get task-specific memory
            task_memory = memory.get_task_context(task)
            
            # Build prompt with FULL context
            task_prompt = session.to_task_prompt(task)
            task_prompt += task_memory.to_prompt()  # "Don't do X because..."
            
            # Execute
            result = await self._execute_task(task, task_prompt)
            
            # Record
            if result.success:
                session.artifacts_created.extend(result.files)
                memory.add_learning(result.learnings)
            else:
                memory.add_failure(result.to_failure())
            
            yield AgentEvent(TASK_COMPLETE, result.to_dict())
        
        # ─── PHASE 4: VALIDATE ───
        async for event in self._convergence_loop(session.artifacts_created):
            if event.type == VALIDATION_FAILED:
                memory.add_failure(event.to_failure())
            yield event
        
        # ─── PHASE 5: LEARN ───
        # Extract decisions if architectural
        if self._is_architectural(session.goal):
            decision = await self._extract_decision(session)
            memory.add_decision(decision)
        
        # Save briefing for next session
        session.save_briefing()
        
        # Sync memory to disk
        memory.sync()
        
        yield AgentEvent(COMPLETE, session.summary())
```

---

## What Changes

### Before (Current)
```
Entry Point → Builds context differently
    ↓
Agent.run() → Loads some memory, discards most
    ↓
Planning → Uses partial context
    ↓
Execution → Different context again
    ↓
End → Some learnings saved, most lost
```

### After (Proposed)
```
Entry Point → SessionContext.build()  [SAME everywhere]
    ↓
PersistentMemory.load()  [ONCE per workspace]
    ↓
Agent.run(session, memory)
    ↓
Planning → memory.get_relevant() + session.workspace
    ↓
Execution → memory.get_task_context() + session.briefing
    ↓
End → memory.sync() + session.save_briefing()
```

---

## The Key Principles

### 1. Separation of Concerns
- **SessionContext**: What's happening NOW (disposable after run)
- **PersistentMemory**: What we remember FOREVER (survives sessions)

### 2. Single Entry Point
- ALL paths (CLI, Server, Chat, API) create `SessionContext.build()`
- No more 4 different context-building implementations

### 3. Memory Flows Through, Not Around
- Memory is passed to Agent, not loaded internally
- Agent queries memory at each stage (plan, execute, validate)
- Agent writes to memory throughout

### 4. Context Is Explicit, Not Implicit
- No hidden fields scattered across Agent class
- Everything needed is in SessionContext or PersistentMemory
- Easy to trace what data goes where

### 5. Nothing Is Orphaned
- Every memory system (Simulacrum, Decisions, Failures, Team) is loaded by PersistentMemory
- Every system contributes to planning AND execution
- No more "built but not wired"

---

## Layer 4: The UI Layer (Studio)

The UI needs access to **everything** — not just events during execution, but all the context and memory that informs what the agent does.

### What the UI Needs to Show

| View | Data Source | Updates |
|------|-------------|---------|
| **Project Overview** | `SessionContext.workspace_info` | On workspace change |
| **Current Goal** | `SessionContext.goal` | On run start |
| **Task Progress** | `SessionContext.tasks` + events | Real-time via WebSocket |
| **Decisions Made** | `PersistentMemory.decisions` | After each run |
| **Past Failures** | `PersistentMemory.failures` | After each run |
| **Team Knowledge** | `PersistentMemory.team` | After sync |
| **Learnings** | `PersistentMemory.simulacrum.learnings` | Real-time + historical |
| **Briefing** | `SessionContext.briefing` | On session load |
| **Run History** | `SessionTracker` | After each run |
| **Lineage** | `LineageStore` | After file changes |

### The Server as State Holder

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SERVER                                          │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     WorkspaceManager                                 │   │
│   │                                                                      │   │
│   │   workspace_id → (SessionContext, PersistentMemory, ActiveRun?)     │   │
│   │                                                                      │   │
│   │   - Caches loaded memory (expensive to reload)                       │   │
│   │   - Tracks active runs per workspace                                 │   │
│   │   - Provides unified access for all routes                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐       │
│   │ /api/run          │  │ /api/memory       │  │ /api/project      │       │
│   │                   │  │                   │  │                   │       │
│   │ POST: Start run   │  │ GET: All memory   │  │ GET: Context      │       │
│   │ WS: Stream events │  │ GET: Decisions    │  │ GET: Workspace    │       │
│   │ DELETE: Cancel    │  │ GET: Failures     │  │ GET: Briefing     │       │
│   │                   │  │ GET: Learnings    │  │                   │       │
│   └───────────────────┘  └───────────────────┘  └───────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STUDIO UI                                       │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        State Store (Svelte)                          │   │
│   │                                                                      │   │
│   │   workspace: { path, name, type, framework, keyFiles, tree }         │   │
│   │   memory: { decisions, failures, learnings, team }                   │   │
│   │   briefing: { mission, status, hazards, hotFiles }                   │   │
│   │   activeRun: { id, goal, tasks, events[], status }                   │   │
│   │   history: { runs[], sessions[] }                                    │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│   │ Observatory │  │ Memory View │  │ Decisions   │  │ Lineage     │        │
│   │ (runs)      │  │ (learnings) │  │ (history)   │  │ (artifacts) │        │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### API Design for UI

```yaml
# ═══════════════════════════════════════════════════════════════
# WORKSPACE CONTEXT
# ═══════════════════════════════════════════════════════════════

GET /api/workspace/{workspace_id}/context
  → SessionContext (without active goal)
  → { path, name, type, framework, keyFiles, entryPoints, tree }

GET /api/workspace/{workspace_id}/briefing
  → Briefing | null
  → { mission, status, progress, hazards, hotFiles, predictedSkills }

# ═══════════════════════════════════════════════════════════════
# PERSISTENT MEMORY
# ═══════════════════════════════════════════════════════════════

GET /api/workspace/{workspace_id}/memory
  → PersistentMemory summary
  → { learningCount, decisionCount, failureCount, teamDecisionCount }

GET /api/workspace/{workspace_id}/memory/decisions
  → Decision[]
  → [{ id, category, question, choice, rationale, rejected[], timestamp }]

GET /api/workspace/{workspace_id}/memory/decisions/{decision_id}
  → Decision with full context

GET /api/workspace/{workspace_id}/memory/failures
  → FailedApproach[]
  → [{ id, description, errorType, rootCause, context, timestamp }]

GET /api/workspace/{workspace_id}/memory/learnings
  → Learning[]
  → [{ id, fact, category, confidence, source }]

GET /api/workspace/{workspace_id}/memory/team
  → TeamKnowledgeContext | null
  → { decisions[], failures[], patterns[] }

# ═══════════════════════════════════════════════════════════════
# EXECUTION (existing, enhanced)
# ═══════════════════════════════════════════════════════════════

POST /api/workspace/{workspace_id}/run
  body: { goal, trust?, model?, lens? }
  → { runId }
  
  # Server internally:
  # 1. Gets cached (session, memory) from WorkspaceManager
  # 2. Updates session.goal
  # 3. Calls Agent.run(session, memory)
  # 4. Streams events via WebSocket

WS /api/workspace/{workspace_id}/run/{run_id}/events
  → Event stream (existing)
  
  # NEW: Events now include memory updates
  → { type: "learning_added", data: Learning }
  → { type: "decision_made", data: Decision }
  → { type: "failure_recorded", data: FailedApproach }

GET /api/workspace/{workspace_id}/runs
  → RunHistory[]
  → [{ runId, goal, status, startedAt, completedAt, tasksCompleted }]

# ═══════════════════════════════════════════════════════════════
# LINEAGE
# ═══════════════════════════════════════════════════════════════

GET /api/workspace/{workspace_id}/lineage
  → ArtifactLineage[]
  → [{ artifactId, path, createdBy, goalId, model, edits[] }]

GET /api/workspace/{workspace_id}/lineage/{path}
  → Full lineage for specific file
```

### UI Components and Their Data

```svelte
<!-- Observatory: Watch runs in real-time -->
<Observatory>
  <!-- Needs: activeRun, events stream -->
  <RunProgress tasks={$activeRun.tasks} />
  <EventStream events={$activeRun.events} />
  <MemoryUpdates learnings={$recentLearnings} />
</Observatory>

<!-- Memory Explorer: Browse what Sunwell remembers -->
<MemoryExplorer>
  <!-- Needs: PersistentMemory.* -->
  <DecisionTimeline decisions={$memory.decisions} />
  <FailurePatterns failures={$memory.failures} />
  <LearningGraph learnings={$memory.learnings} />
</MemoryExplorer>

<!-- Project Context: Understand the workspace -->
<ProjectContext>
  <!-- Needs: SessionContext.workspace_info -->
  <ProjectType type={$workspace.type} framework={$workspace.framework} />
  <KeyFiles files={$workspace.keyFiles} />
  <DirectoryTree tree={$workspace.tree} />
</ProjectContext>

<!-- Briefing Panel: Session continuity -->
<BriefingPanel>
  <!-- Needs: SessionContext.briefing -->
  <Mission text={$briefing.mission} status={$briefing.status} />
  <Hazards items={$briefing.hazards} />
  <HotFiles files={$briefing.hotFiles} />
  <NextAction action={$briefing.nextAction} />
</BriefingPanel>

<!-- History: Past runs and outcomes -->
<History>
  <!-- Needs: SessionTracker, RunHistory -->
  <RunList runs={$history.runs} />
  <SessionSummary session={$history.currentSession} />
</History>
```

### Real-Time Updates

```typescript
// Studio subscribes to workspace updates
const ws = new WebSocket(`/api/workspace/${workspaceId}/events`);

ws.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  
  switch (type) {
    // Run events
    case 'run_started':
      activeRun.set({ id: data.runId, goal: data.goal, tasks: [], events: [] });
      break;
    case 'task_complete':
      activeRun.update(r => ({ ...r, tasks: [...r.tasks, data.task] }));
      break;
    case 'run_complete':
      activeRun.update(r => ({ ...r, status: 'complete' }));
      refreshMemory();  // Reload memory after run
      break;
      
    // Memory events (NEW)
    case 'learning_added':
      memory.update(m => ({ 
        ...m, 
        learnings: [...m.learnings, data] 
      }));
      break;
    case 'decision_made':
      memory.update(m => ({ 
        ...m, 
        decisions: [...m.decisions, data] 
      }));
      break;
    case 'failure_recorded':
      memory.update(m => ({ 
        ...m, 
        failures: [...m.failures, data] 
      }));
      break;
      
    // Briefing updates
    case 'briefing_updated':
      briefing.set(data);
      break;
  }
};
```

### Key Design Decisions

1. **Server caches memory per workspace**
   - Loading `PersistentMemory` is expensive (disk I/O, parsing)
   - Cache it in `WorkspaceManager`, invalidate on sync
   - Multiple UI clients share the same memory instance

2. **Events include memory updates**
   - UI doesn't poll for memory changes
   - Agent emits events when memory is modified
   - UI updates in real-time

3. **Workspace-scoped everything**
   - All routes are `/api/workspace/{workspace_id}/...`
   - Clean separation between projects
   - Easy to support multiple workspaces

4. **Same objects, different serialization**
   - `SessionContext` → JSON for UI
   - `SessionContext` → prompt for Agent
   - Same source of truth, different views

---

## Implementation Path

### Single Coordinated Delivery

**No phases. No milestones. One PR.**

The entire refactor lands atomically. Either it all works or nothing merges.

### Day 1-2: Create New Types

```bash
# Create the new modules
touch sunwell/context/__init__.py
touch sunwell/context/session.py
touch sunwell/memory/persistent.py
touch sunwell/memory/types.py
```

**SessionContext** — all session state in one place:
- Goal, workspace, options
- Briefing (loaded from disk)
- Project detection (inlined from `build_workspace_context`)
- Lens resolution
- Execution state (tasks, artifacts)

**PersistentMemory** — unified access to existing stores:
- SimulacrumStore
- DecisionMemory
- FailureMemory
- PatternProfile
- TeamKnowledgeStore (optional)

**MemoryContext** — query result type:
- Constraints (from decisions)
- Dead ends (from failures)
- Patterns (from profile)
- Learnings (from simulacrum)

### Day 3-4: Update Agent

Rewrite `agent/core.py`:

1. **Delete** `RunRequest` handling
2. **Delete** `_load_memory()`, `_load_briefing()`, `_run_prefetch()`
3. **Delete** internal state: `session`, `simulacrum`, `lens`, `_briefing`
4. **Change** `run()` signature to `(session, memory)`
5. **Add** memory query at ORIENT phase
6. **Add** memory recording at LEARN phase

```python
# The new Agent is ~300 lines instead of ~1300
# All the context/memory loading moved to callers
```

### Day 5: Update Planners

Update `naaru/planners/harmonic.py` and `artifact.py`:

1. **Add** `memory: PersistentMemory` parameter
2. **Query** memory for constraints before candidate generation
3. **Inject** constraints into planning prompt
4. **Remove** `simulacrum` parameter (now inside memory)

### Day 6-7: Update All Callers

Update every entry point in the same PR:

| File | Change |
|------|--------|
| `cli/main.py` | `SessionContext.build()` + `PersistentMemory.load()` |
| `cli/chat/command.py` | Same pattern |
| `server/routes/agent.py` | Same pattern + `WorkspaceManager` cache |

### Day 8: Delete Dead Code

In the same PR:

```bash
# Delete entire files
rm sunwell/cli/agent/run.py
rm sunwell/cli/agent/__init__.py  # if empty
rm sunwell/agent/request.py       # RunRequest is gone

# Delete from helpers.py
# - build_workspace_context() — inlined into SessionContext
# - format_workspace_context() — method on SessionContext
```

### Day 9-10: Fix Tests

Update all tests to use new signatures:

```python
# OLD
request = RunRequest(goal="test", context={})
async for event in agent.run(request):
    ...

# NEW
session = SessionContext.build(tmp_path, "test", RunOptions())
memory = PersistentMemory.load(tmp_path)
async for event in agent.run(session, memory):
    ...
```

### Day 11: Server Memory Cache

Create `server/workspace_manager.py`:

```python
class WorkspaceManager:
    """Caches PersistentMemory per workspace."""
    
    _cache: dict[str, PersistentMemory] = {}
    
    def get_memory(self, workspace: Path) -> PersistentMemory:
        key = str(workspace.resolve())
        if key not in self._cache:
            self._cache[key] = PersistentMemory.load(workspace)
        return self._cache[key]
    
    def invalidate(self, workspace: Path) -> None:
        key = str(workspace.resolve())
        self._cache.pop(key, None)
```

### Day 12-14: Integration Testing

Run full E2E tests:

1. `sunwell run "add auth"` → creates decision
2. `sunwell run "add caching with Redis"` → sees constraint, avoids Redis
3. Server run → same behavior
4. Studio → shows memory state

### PR Checklist

```markdown
## Breaking Changes

- [ ] `Agent.run()` signature changed: `(request)` → `(session, memory)`
- [ ] `RunRequest` deleted — use `SessionContext`
- [ ] `cli/agent/run.py` deleted — use `cli/main.py`
- [ ] Planners require `PersistentMemory` parameter

## Files Created

- [ ] `sunwell/context/session.py`
- [ ] `sunwell/memory/persistent.py`
- [ ] `sunwell/memory/types.py`
- [ ] `sunwell/server/workspace_manager.py`

## Files Modified

- [ ] `sunwell/agent/core.py` — new signature, removed internal loading
- [ ] `sunwell/agent/events.py` — added ORIENT event
- [ ] `sunwell/naaru/planners/harmonic.py` — accepts memory
- [ ] `sunwell/naaru/planners/artifact.py` — accepts memory
- [ ] `sunwell/cli/main.py` — uses new types
- [ ] `sunwell/cli/chat/command.py` — uses new types
- [ ] `sunwell/server/routes/agent.py` — uses new types

## Files Deleted

- [ ] `sunwell/cli/agent/run.py`
- [ ] `sunwell/cli/agent/__init__.py`
- [ ] `sunwell/agent/request.py`

## Tests

- [ ] All existing tests updated to new signatures
- [ ] New tests for SessionContext.build()
- [ ] New tests for PersistentMemory.load()
- [ ] New tests for memory constraint flow
- [ ] E2E: cross-session memory persistence
```

---

## Migration Strategy

### Guiding Principle

**Clean break. No backwards compatibility. No shims. No deprecation period.**

All changes land in a single coordinated PR. Old code is deleted, not deprecated.

### The Cut-Over

```
BEFORE (delete):                    AFTER (new):
─────────────────                   ────────────
RunRequest                          SessionContext
Agent._load_memory()                PersistentMemory.load()
Agent.run(request)                  Agent.run(session, memory)
cli/agent/run.py                    [deleted]
build_workspace_context() scattered SessionContext.build()
4 different context builders        1 unified path
```

### Single PR Structure

```
feat: unified memory facade and session context

├── Create new types
│   ├── sunwell/context/session.py      # SessionContext
│   ├── sunwell/memory/persistent.py    # PersistentMemory  
│   └── sunwell/memory/types.py         # MemoryContext
│
├── Update Agent (breaking change)
│   ├── agent/core.py                   # New run() signature
│   ├── agent/events.py                 # Add ORIENT event
│   └── agent/request.py                # Delete RunRequest
│
├── Update planners
│   ├── naaru/planners/harmonic.py      # Accept memory
│   └── naaru/planners/artifact.py      # Accept memory
│
├── Update ALL callers (same PR)
│   ├── cli/main.py                     # Use new types
│   ├── cli/chat/command.py             # Use new types
│   └── server/routes/agent.py          # Use new types
│
├── Delete dead code (same PR)
│   ├── cli/agent/run.py                # Delete entire file
│   ├── cli/agent/__init__.py           # Delete if empty
│   └── agent/core.py                   # Remove _load_memory()
│
└── Update tests (same PR)
    └── All tests use new signatures
```

### New Agent Signature

```python
# agent/core.py — FINAL STATE (no legacy)
@dataclass
class Agent:
    """THE execution engine for Sunwell."""
    
    model: ModelProtocol
    tool_executor: Any = None
    cwd: Path | None = None
    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    
    # Removed: session, simulacrum, lens, auto_lens
    # Removed: _learning_store, _briefing, _prefetched_context
    # All of that is now in SessionContext or PersistentMemory
    
    async def run(
        self,
        session: SessionContext,
        memory: PersistentMemory,
    ) -> AsyncIterator[AgentEvent]:
        """Execute goal with explicit context and memory.
        
        Args:
            session: Session state (goal, workspace, options)
            memory: Persistent memory (decisions, failures, patterns)
        
        Yields:
            AgentEvent for each step of execution
        """
        # ORIENT
        memory_ctx = await memory.get_relevant(session.goal)
        yield AgentEvent(EventType.ORIENT, {
            "constraints": len(memory_ctx.constraints),
            "dead_ends": len(memory_ctx.dead_ends),
        })
        
        # PLAN (memory flows through)
        async for event in self._plan(session, memory_ctx):
            yield event
        
        # EXECUTE (task-level memory)
        async for event in self._execute(session, memory):
            yield event
        
        # LEARN (record to memory)
        await memory.record_session(session)
        memory.sync()
        
        yield AgentEvent(EventType.COMPLETE, session.summary())
```

### New Entry Point Pattern

Every entry point follows the same pattern:

```python
# cli/main.py
async def _run_agent(goal: str, workspace: Path, options: RunOptions) -> None:
    # 1. Build session and memory
    session = SessionContext.build(workspace, goal, options)
    memory = PersistentMemory.load(workspace)
    
    # 2. Create agent
    agent = Agent(model=model, tool_executor=tools, cwd=workspace)
    
    # 3. Run with explicit dependencies
    async for event in agent.run(session, memory):
        handle_event(event)
```

```python
# server/routes/agent.py
@router.post("/workspace/{workspace_id}/run")
async def run_agent(workspace_id: str, request: RunAgentRequest):
    workspace = get_workspace_path(workspace_id)
    
    session = SessionContext.build(workspace, request.goal, request.options)
    memory = PersistentMemory.load(workspace)
    
    agent = Agent(model=model, tool_executor=tools, cwd=workspace)
    
    async for event in agent.run(session, memory):
        yield event.to_json()
```

### What Gets Deleted

| File/Code | Reason |
|-----------|--------|
| `cli/agent/run.py` | Entire file — bypassed Agent |
| `cli/agent/__init__.py` | Empty after deletion |
| `agent/request.py:RunRequest` | Replaced by SessionContext |
| `agent/core.py:_load_memory()` | Moved to PersistentMemory.load() |
| `agent/core.py:_load_briefing()` | Moved to SessionContext.build() |
| `agent/core.py:_run_prefetch()` | Moved to SessionContext |
| `agent/core.py:session` field | Moved to SessionContext |
| `agent/core.py:simulacrum` field | Moved to PersistentMemory |
| `agent/core.py:lens` field | Moved to SessionContext |
| `agent/core.py:_briefing` field | Moved to SessionContext |
| `cli/helpers.py:build_workspace_context()` | Inlined into SessionContext.build() |

### What Gets Moved (Not Deleted)

| From | To | Notes |
|------|---|-------|
| `Agent._load_memory()` logic | `PersistentMemory.load()` | Same logic, different location |
| `Agent._load_briefing()` logic | `SessionContext.build()` | Same logic, different location |
| `build_workspace_context()` logic | `SessionContext.build()` | Inlined, not wrapped |
| `Agent._learning_store` | `PersistentMemory.simulacrum` | Unified under facade |

### Files to Create

| File | Contents |
|------|----------|
| `sunwell/context/session.py` | `SessionContext` class |
| `sunwell/memory/persistent.py` | `PersistentMemory` class |
| `sunwell/memory/types.py` | `MemoryContext`, `TaskMemoryContext` |
| `sunwell/server/workspace_manager.py` | Server-side memory cache |

### Files to Modify

| File | Change |
|------|--------|
| `agent/core.py` | New `run()` signature, remove internal memory loading |
| `agent/events.py` | Add `ORIENT` event type |
| `naaru/planners/harmonic.py` | Accept `PersistentMemory`, query constraints |
| `naaru/planners/artifact.py` | Accept `PersistentMemory`, query constraints |
| `cli/main.py` | Use `SessionContext` + `PersistentMemory` |
| `cli/chat/command.py` | Use `SessionContext` + `PersistentMemory` |
| `server/routes/agent.py` | Use `SessionContext` + `PersistentMemory` |

### Files to Delete

| File | Reason |
|------|--------|
| `cli/agent/run.py` | Bypassed Agent, used Naaru directly |
| `cli/agent/__init__.py` | Empty module |
| `agent/request.py` | `RunRequest` replaced by `SessionContext` |

---

## Error Handling

### Memory Load Failures

```python
@classmethod
def load(cls, workspace: Path) -> PersistentMemory:
    """Load all memory components, gracefully handling failures."""
    
    # Each component loads independently
    # Failure in one doesn't block others
    
    simulacrum = None
    try:
        simulacrum = SimulacrumStore.load(workspace / ".sunwell/sessions")
    except Exception as e:
        logger.warning(f"Failed to load Simulacrum: {e}")
        simulacrum = SimulacrumStore.empty()  # Use empty store
    
    # ... same pattern for each component ...
    
    return cls(
        workspace=workspace,
        simulacrum=simulacrum or SimulacrumStore.empty(),
        decisions=decisions or DecisionMemory.empty(),
        failures=failures or FailureMemory.empty(),
        team=team,  # None is OK
        patterns=patterns or PatternProfile.empty(),
    )
```

### Workspace Detection Failures

```python
@classmethod
def build(cls, cwd: Path, goal: str, options: RunOptions) -> SessionContext:
    """Build context, with safe defaults for detection failures."""
    
    # Detection can fail - use safe defaults
    try:
        project_type, framework = detect_project_type(cwd)
    except Exception:
        project_type, framework = "unknown", None
    
    try:
        key_files = find_key_files(cwd)
    except Exception:
        key_files = []
    
    # ... etc ...
    
    return cls(
        cwd=cwd,
        goal=goal,
        project_type=project_type,
        framework=framework,
        key_files=key_files,
        # ... safe defaults for everything ...
    )
```

### Sync Failures

```python
def sync(self) -> SyncResult:
    """Persist all changes, collecting any failures."""
    results = []
    
    for name, component in [
        ("simulacrum", self.simulacrum),
        ("decisions", self.decisions),
        ("failures", self.failures),
        ("team", self.team),
        ("patterns", self.patterns),
    ]:
        if component is None:
            continue
        try:
            component.sync()
            results.append((name, True, None))
        except Exception as e:
            logger.error(f"Failed to sync {name}: {e}")
            results.append((name, False, str(e)))
    
    return SyncResult(results)
```

---

## Critical Integration: Memory → Planner

The key value of this RFC is wiring existing memory stores into planning. Here's exactly how it works:

### Current State (Memory Not Used)

```python
# naaru/planners/harmonic.py (current)
class HarmonicPlanner:
    def __init__(
        self,
        model: ModelProtocol,
        candidates: int = 5,
        simulacrum: SimulacrumStore | None = None,  # Only learnings, not decisions/failures
    ):
        ...
    
    async def plan(self, goals: list[str], context: dict) -> list[Task]:
        # PROBLEM: No access to DecisionMemory or FailureMemory
        # Agent might plan to "use Redis" even if we decided against it
        # Agent might repeat an approach that failed 3 times before
        ...
```

### Proposed State (Memory Flows Through)

```python
# naaru/planners/harmonic.py (proposed)
class HarmonicPlanner:
    def __init__(
        self,
        model: ModelProtocol,
        candidates: int = 5,
        memory: PersistentMemory | None = None,  # NEW: Full memory access
    ):
        self.memory = memory
    
    async def plan(self, goals: list[str], context: dict) -> list[Task]:
        # ORIENT: What do we know about this goal?
        if self.memory:
            memory_ctx = await self.memory.get_relevant(goals[0])
            
            # Inject constraints into candidate generation prompt
            if memory_ctx.constraints:
                context["_constraints"] = [
                    f"⛔ DO NOT: {c}" for c in memory_ctx.constraints
                ]
                # Example: "⛔ DO NOT: Use Redis (decided against it - too much operational complexity)"
            
            if memory_ctx.dead_ends:
                context["_dead_ends"] = [
                    f"⚠️ AVOID: {d}" for d in memory_ctx.dead_ends
                ]
                # Example: "⚠️ AVOID: Async SQLAlchemy with connection pooling (failed 3 times)"
            
            if memory_ctx.team_decisions:
                context["_team_standards"] = memory_ctx.team_decisions
                # Example: "Team uses Pydantic v2 for all models"
        
        # Generate candidates with constraints injected
        candidates = await self._generate_candidates(goals, context)
        
        # Score candidates (constraints already influenced generation)
        winner = await self._score_and_select(candidates)
        
        return winner.tasks
```

### Prompt Injection Example

Before memory integration:
```
Generate a plan for: "Add caching to the user service"

Project context:
- Python FastAPI backend
- SQLite database
...
```

After memory integration:
```
Generate a plan for: "Add caching to the user service"

⛔ CONSTRAINTS (DO NOT violate):
- Do not use Redis (decision: too much operational complexity for current scale)
- Do not add new dependencies without approval

⚠️ KNOWN DEAD ENDS (DO NOT repeat):
- In-memory dict caching caused memory leaks (failed 2x)
- Memcached integration had connection pool issues

✓ TEAM STANDARDS:
- Use Pydantic v2 for all data models
- Follow existing async patterns in services/

Project context:
- Python FastAPI backend
- SQLite database
...
```

### Recording New Learnings

After successful execution, Agent records what it learned:

```python
# agent/core.py (in _learn_from_execution)
async def _learn_from_execution(self, session: SessionContext, memory: PersistentMemory):
    """Extract learnings from completed execution."""
    
    # If we made an architectural decision, record it
    if self._detected_decision:
        await memory.decisions.record_decision(
            category="caching",
            question="What caching approach to use?",
            choice="SQLAlchemy-level caching with dogpile.cache",
            rejected=[("Redis", "Too much operational complexity")],
            rationale="Simpler deployment, sufficient for current scale",
            session_id=session.session_id,
        )
    
    # If something failed, record it
    if self._detected_failure:
        await memory.failures.record_failure(
            description="In-memory dict caching",
            error_type="runtime_error",
            error_message="Memory leak under load",
            context="User service caching",
            session_id=session.session_id,
        )
    
    # Sync to disk
    memory.sync()
```

---

## The Answer to Your Question

> Does the agent loop need to sit beside something?

**No.** The Agent loop is the center. But it needs TWO things passed INTO it:
- `SessionContext` — The "what" (workspace, goal, options)
- `PersistentMemory` — The "memory" (decisions, failures, learnings)

> Does something need to be carried through the agent loop?

**Yes.** Both objects flow THROUGH the loop:
- `SessionContext` is READ (workspace info) and WRITTEN (artifacts, tasks)
- `PersistentMemory` is READ (constraints, dead_ends) and WRITTEN (learnings, decisions)

> Help me understand.

The current architecture is **inside-out** — the Agent tries to load everything internally.

The ideal architecture is **outside-in** — context and memory are built OUTSIDE the Agent and passed IN.

```
CURRENT:
    Agent() → internally loads memory → internally builds context → runs

IDEAL:
    session = SessionContext.build(...)
    memory = PersistentMemory.load(...)
    Agent().run(session, memory)
```

This makes:
- Testing easy (inject mock memory)
- Tracing easy (see exactly what's passed)
- Reuse easy (same memory, different sessions)
- Debugging easy (inspect session/memory at any point)

---

## Risks and Mitigations

### Risk 1: Performance — Memory Loading Overhead

**Risk**: Loading all memory stores on every run adds latency.

**Mitigation**:
- Lazy loading: Only query stores when needed
- Server caching: `WorkspaceManager` keeps memory loaded
- Async initialization: Load stores in parallel

```python
@classmethod
async def load_async(cls, workspace: Path) -> PersistentMemory:
    """Load all stores in parallel."""
    import asyncio
    
    # Parallel loading
    sim, dec, fail, pat = await asyncio.gather(
        _load_simulacrum(workspace),
        _load_decisions(workspace),
        _load_failures(workspace),
        _load_patterns(workspace),
    )
    return cls(workspace, sim, dec, fail, None, pat)
```

### Risk 2: Complexity — Another Abstraction Layer

**Risk**: PersistentMemory adds indirection, harder to debug.

**Mitigation**:
- Not a wrapper: `PersistentMemory` owns the stores, provides unified query
- Logging: Log which stores were queried and what was returned
- Direct access: Individual stores still importable for targeted debugging

```python
# For debugging, can still import stores directly
from sunwell.intelligence.decisions import DecisionMemory
decisions = DecisionMemory(intel_path)
decisions.find_relevant_decisions("caching")
```

### Risk 3: Migration — Breaking Changes

**Risk**: Changing Agent signature breaks external callers.

**Mitigation**:
- **Accepted risk**: This is an internal API, no external callers
- **Clear PR**: All changes in one atomic commit
- **Test coverage**: Every caller updated and tested in same PR

### Risk 4: Scope Creep — TeamKnowledgeStore

**Risk**: TeamKnowledgeStore sync adds complexity.

**Mitigation**:
- Phase it: Team support is optional (`team: TeamKnowledgeStore | None`)
- Ship without: MVP works with `team=None`
- Separate RFC: Full team sync can be a follow-up

### Risk 5: Testing — Integration Complexity

**Risk**: Testing memory integration requires complex fixtures.

**Mitigation**:
- Empty facade: `PersistentMemory.empty()` for unit tests
- Mock stores: Each store can be mocked independently
- Integration fixtures: Pre-populated `.sunwell/` directories

```python
# Easy testing with empty memory
def test_agent_no_memory():
    memory = PersistentMemory.empty(tmp_path)
    session = SessionContext.build(tmp_path, "test goal", options)
    
    events = list(agent.run_v2(session, memory))
    assert EventType.COMPLETE in [e.type for e in events]
```

---

## Success Criteria

### Functional

- [ ] `PersistentMemory.load()` loads all stores
- [ ] `SessionContext.build()` detects project and loads briefing
- [ ] Planning queries `DecisionMemory` for constraints
- [ ] Planning queries `FailureMemory` for dead ends
- [ ] Agent records new decisions after execution
- [ ] Agent records failures when validation fails
- [ ] Memory persists across CLI sessions
- [ ] Server caches memory per workspace
- [ ] Studio shows memory state in real-time

### Code Quality

- [ ] `RunRequest` deleted — no legacy types
- [ ] `cli/agent/run.py` deleted — no bypass paths
- [ ] `Agent._load_memory()` deleted — memory passed in
- [ ] All callers use `SessionContext` + `PersistentMemory`
- [ ] No scattered context building — unified in `SessionContext.build()`

### Performance

- [ ] Memory load time < 100ms for typical workspace
- [ ] No regression in planning latency
- [ ] Server memory cache hit rate > 90%

### Tests

- [ ] All existing tests updated to new signatures
- [ ] New tests for `SessionContext.build()`
- [ ] New tests for `PersistentMemory.load()`
- [ ] New tests for memory constraint flow in planning
- [ ] E2E test: cross-session memory persistence

---

## TL;DR

**Problem**: We have good memory stores (`DecisionMemory`, `FailureMemory`, `PatternProfile`) that aren't wired into planning. Agent repeats rejected approaches and failed experiments.

**Solution**: 
1. Create `PersistentMemory` — unified access to existing stores
2. Create `SessionContext` — all session state in one object
3. Change `Agent.run(session, memory)` — explicit dependencies
4. Wire planners to query memory for constraints

**Approach**: Clean break. No backwards compatibility. One atomic PR.

**Timeline**: 2 weeks. Single coordinated delivery.

**What Gets Deleted**:
- `RunRequest` — replaced by `SessionContext`
- `cli/agent/run.py` — bypassed Agent, now deleted
- `Agent._load_memory()` — moved to `PersistentMemory.load()`
- Scattered context building — unified in `SessionContext.build()`

---

## Simplification Metrics

### Lines of Code

| Component | Before | After | Change |
|-----------|--------|-------|--------|
| `agent/core.py` | 1,370 | ~500 | **-870 lines** |
| `agent/request.py` | 174 | 0 (deleted) | **-174 lines** |
| `cli/agent/run.py` | 952 | 0 (deleted) | **-952 lines** |
| Context building (scattered) | ~200 across 5 files | ~150 in 1 file | **-50 lines, unified** |
| **Net change** | | | **~1,900 lines deleted** |

New code added:
- `context/session.py` — ~150 lines
- `memory/persistent.py` — ~200 lines
- `memory/types.py` — ~100 lines

**Net reduction: ~1,400 lines**

### Complexity Reduction

| Metric | Before | After |
|--------|--------|-------|
| Entry points into Agent | 4 (`run()`, `plan()`, `resume_from_recovery()`, + `cli/agent/run.py` bypass) | 1 (`run()`) |
| Context building locations | 5 files | 1 file (`SessionContext.build()`) |
| Memory loading locations | 2 (`Agent._load_memory()`, `cli/agent/run.py`) | 1 (`PersistentMemory.load()`) |
| Agent fields | 18 | 5 |
| Agent private methods | 15 | 8 |

### Agent Field Reduction

**Before (18 fields)**:
```python
model, tool_executor, cwd, budget,
session, simulacrum, lens, auto_lens,
stream_inference, token_batch_size,
_learning_store, _learning_extractor, _validation_runner, _fix_stage,
_naaru, _inference_metrics, _task_graph, _briefing, _prefetched_context,
_session_learnings, _current_blockers, _current_goal, _last_planning_context,
_files_changed_this_run, _workspace_context
```

**After (5 fields)**:
```python
model, tool_executor, cwd, budget, _naaru
```

Everything else moves to `SessionContext` or `PersistentMemory`.

### What This Eliminates

| Anti-Pattern | Example | Fixed By |
|--------------|---------|----------|
| **Bypass paths** | `cli/agent/run.py` called Naaru directly | Deleted |
| **Scattered state** | Agent had 18+ fields for context/memory | State consolidated into 2 objects |
| **Internal loading** | `Agent._load_memory()` made testing hard | Memory passed in, easily mocked |
| **Duplicate context building** | 5 different implementations | One `SessionContext.build()` |
| **Implicit dependencies** | Agent loaded its own memory | Explicit `run(session, memory)` |
| **Untestable internals** | Private `_briefing`, `_simulacrum` fields | Public objects passed in |

### Architectural Clarity

**Before**: Agent is a god object that loads its own dependencies, has multiple entry points, and maintains complex internal state.

```
cli/main.py ─────────────────────────────────┐
cli/chat.py ─────────────────────────────────┤
cli/agent/run.py (BYPASS) ──→ Naaru directly │
server/routes/agent.py ──────────────────────┴──→ Agent (1370 lines, 18 fields)
                                                    ├── _load_memory()
                                                    ├── _load_briefing()
                                                    ├── _run_prefetch()
                                                    └── ... 12 more private methods
```

**After**: Agent is a focused execution engine. Context and memory are passed in. One entry point.

```
cli/main.py ──────────────────────────────┐
cli/chat.py ──────────────────────────────┤
server/routes/agent.py ───────────────────┴──→ SessionContext.build()
                                              PersistentMemory.load()
                                                    │
                                                    ▼
                                              Agent.run(session, memory)
                                              (~500 lines, 5 fields)
```

### Testability Improvement

**Before**:
```python
# Hard to test — Agent loads its own dependencies
agent = Agent(model=mock_model, cwd=tmp_path)
# How do I inject test decisions? Test failures? Test briefing?
# Answer: You can't easily
```

**After**:
```python
# Easy to test — inject everything
session = SessionContext(
    goal="test",
    cwd=tmp_path,
    briefing=test_briefing,  # Inject test briefing
    ...
)
memory = PersistentMemory(
    decisions=mock_decisions,  # Inject test decisions
    failures=mock_failures,    # Inject test failures
    ...
)
agent = Agent(model=mock_model, cwd=tmp_path)

# Full control over all inputs
async for event in agent.run(session, memory):
    ...
```

---

## Post-Refactor Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ENTRY POINTS                                        │
│                                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│   │  CLI (main)  │   │    Chat      │   │   Server     │   │   Studio     │    │
│   │  sunwell run │   │ sunwell chat │   │   /api/*     │   │   WebSocket  │    │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘    │
│          │                  │                  │                  │             │
│          └──────────────────┼──────────────────┼──────────────────┘             │
│                             │                  │                                 │
│                             ▼                  ▼                                 │
│                    ┌────────────────────────────────────┐                       │
│                    │     ALL ENTRY POINTS DO THIS:      │                       │
│                    │                                    │                       │
│                    │  session = SessionContext.build()  │                       │
│                    │  memory = PersistentMemory.load()  │                       │
│                    │  agent.run(session, memory)        │                       │
│                    └────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CORE OBJECTS                                        │
│                                                                                  │
│  ┌─────────────────────────────┐      ┌─────────────────────────────────────┐  │
│  │      SessionContext         │      │        PersistentMemory             │  │
│  │  (lives during one run)     │      │    (lives across all runs)          │  │
│  ├─────────────────────────────┤      ├─────────────────────────────────────┤  │
│  │ • session_id                │      │ • simulacrum: SimulacrumStore       │  │
│  │ • cwd, goal                 │      │ • decisions: DecisionMemory         │  │
│  │ • project_type, framework   │      │ • failures: FailureMemory           │  │
│  │ • key_files, entry_points   │      │ • patterns: PatternProfile          │  │
│  │ • briefing: Briefing        │      │ • team: TeamKnowledgeStore | None   │  │
│  │ • lens: Lens                │      ├─────────────────────────────────────┤  │
│  │ • tasks: list[Task]         │      │ get_relevant(goal) → MemoryContext  │  │
│  │ • artifacts_created         │      │ record_decision(...)                │  │
│  ├─────────────────────────────┤      │ record_failure(...)                 │  │
│  │ to_planning_prompt()        │      │ sync()                              │  │
│  │ to_task_prompt(task)        │      └─────────────────────────────────────┘  │
│  │ save_briefing()             │                                               │
│  └─────────────────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 AGENT                                            │
│                          (~500 lines, 5 fields)                                  │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  class Agent:                                                              │  │
│  │      model: ModelProtocol                                                  │  │
│  │      tool_executor: ToolExecutor                                           │  │
│  │      cwd: Path                                                             │  │
│  │      budget: AdaptiveBudget                                                │  │
│  │      _naaru: Naaru                                                         │  │
│  │                                                                            │  │
│  │      async def run(session, memory) → AsyncIterator[AgentEvent]:           │  │
│  │          ├── ORIENT: memory.get_relevant(goal) → constraints, dead_ends   │  │
│  │          ├── PLAN: planner.plan(goal, memory_ctx) → tasks                  │  │
│  │          ├── EXECUTE: for task in tasks: execute(task, memory)            │  │
│  │          ├── VALIDATE: gates, convergence loops                            │  │
│  │          └── LEARN: memory.record_decision(), memory.sync()                │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               EXECUTION                                          │
│                                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  HarmonicPlanner    │  │    Naaru            │  │   ConvergenceLoop      │  │
│  │  (planning)         │  │    (execution)      │  │   (validation)         │  │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────────┤  │
│  │ Receives:           │  │ Receives:           │  │ Receives:               │  │
│  │ • goal              │  │ • tasks             │  │ • artifacts             │  │
│  │ • memory_ctx        │  │ • tool_executor     │  │ • gates                 │  │
│  │                     │  │                     │  │                         │  │
│  │ Injects:            │  │ Executes:           │  │ Runs:                   │  │
│  │ • constraints       │  │ • file writes       │  │ • lint, type, test      │  │
│  │ • dead_ends         │  │ • commands          │  │ • auto-fix loop         │  │
│  │ • team_decisions    │  │ • LLM calls         │  │                         │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PERSISTENT STORAGE                                    │
│                             (.sunwell/ directory)                                │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ .sunwell/                                                                 │   │
│  │ ├── memory/                    # SimulacrumStore                          │   │
│  │ │   ├── sessions/              # Conversation DAGs                        │   │
│  │ │   └── learnings/             # Extracted learnings                      │   │
│  │ ├── intelligence/              # Decision/Failure/Pattern stores          │   │
│  │ │   ├── decisions.jsonl        # Architectural decisions                  │   │
│  │ │   ├── failures.jsonl         # Failed approaches                        │   │
│  │ │   └── patterns.json          # User preferences                         │   │
│  │ ├── team/                      # TeamKnowledgeStore (optional)            │   │
│  │ │   └── shared.jsonl           # Team-shared decisions                    │   │
│  │ └── briefing.json              # Session continuity                       │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: A Single Run

```
                                USER GOAL
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 1. BUILD CONTEXT                                                               │
│                                                                                │
│    SessionContext.build(workspace, goal, options)                              │
│    ├── Detect project type (python, node, rust, etc.)                          │
│    ├── Find key files (README, pyproject.toml, etc.)                           │
│    ├── Build directory tree                                                    │
│    ├── Load briefing from previous session                                     │
│    └── Resolve lens                                                            │
│                                                                                │
│    PersistentMemory.load(workspace)                                            │
│    ├── Load SimulacrumStore (learnings, conversation history)                  │
│    ├── Load DecisionMemory (architectural decisions)                           │
│    ├── Load FailureMemory (failed approaches)                                  │
│    ├── Load PatternProfile (user preferences)                                  │
│    └── Load TeamKnowledgeStore (if configured)                                 │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 2. ORIENT (new phase)                                                          │
│                                                                                │
│    memory_ctx = memory.get_relevant(goal)                                      │
│                                                                                │
│    Returns MemoryContext:                                                      │
│    ├── constraints: ["Don't use Redis", "Don't add new deps without approval"] │
│    ├── dead_ends: ["Async SQLAlchemy failed 3x", "Memcached had pool issues"]  │
│    ├── team_decisions: ["Use Pydantic v2", "Follow async patterns"]            │
│    ├── learnings: ["billing.py is fragile", "tests require DB fixture"]        │
│    └── patterns: ["snake_case functions", "Google-style docstrings"]           │
│                                                                                │
│    yield AgentEvent(ORIENT, {constraints: 2, dead_ends: 2, ...})               │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 3. PLAN                                                                        │
│                                                                                │
│    planner.plan(goal, session, memory_ctx)                                     │
│                                                                                │
│    Prompt includes:                                                            │
│    ┌─────────────────────────────────────────────────────────────────────┐    │
│    │ Generate a plan for: "Add caching to user service"                  │    │
│    │                                                                     │    │
│    │ ⛔ CONSTRAINTS (DO NOT violate):                                    │    │
│    │ - Do not use Redis (too much operational complexity)                │    │
│    │ - Do not add new dependencies without approval                      │    │
│    │                                                                     │    │
│    │ ⚠️ KNOWN DEAD ENDS (DO NOT repeat):                                 │    │
│    │ - Async SQLAlchemy with connection pooling (failed 3 times)         │    │
│    │ - Memcached integration (connection pool issues)                    │    │
│    │                                                                     │    │
│    │ ✓ TEAM STANDARDS:                                                   │    │
│    │ - Use Pydantic v2 for all data models                               │    │
│    │ - Follow existing async patterns in services/                       │    │
│    │                                                                     │    │
│    │ Project: Python FastAPI, SQLite database                            │    │
│    └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
│    Output: TaskGraph with tasks and gates                                      │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 4. EXECUTE                                                                     │
│                                                                                │
│    for task in tasks:                                                          │
│        task_memory = memory.get_task_context(task)                             │
│        # Constraints specific to this file/path                                │
│                                                                                │
│        result = naaru.execute(task, task_memory)                               │
│                                                                                │
│        if result.created_file:                                                 │
│            session.artifacts_created.append(result.path)                       │
│                                                                                │
│        yield AgentEvent(TASK_COMPLETE, {task_id, duration_ms})                 │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 5. VALIDATE                                                                    │
│                                                                                │
│    for gate in gates:                                                          │
│        result = gate.validate(artifacts)                                       │
│                                                                                │
│        if result.failed:                                                       │
│            # Record failure                                                    │
│            memory.record_failure(                                              │
│                description=gate.description,                                   │
│                error=result.error,                                             │
│            )                                                                   │
│                                                                                │
│            # Auto-fix with convergence loop                                    │
│            for attempt in convergence_loop:                                    │
│                fix_result = await fix(artifacts, result.error)                 │
│                if fix_result.passed:                                           │
│                    break                                                       │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 6. LEARN                                                                       │
│                                                                                │
│    # Record architectural decision if one was made                             │
│    if detected_decision:                                                       │
│        memory.record_decision(                                                 │
│            category="caching",                                                 │
│            question="What caching approach?",                                  │
│            choice="dogpile.cache with SQLAlchemy",                             │
│            rejected=[("Redis", "operational complexity")],                     │
│        )                                                                       │
│                                                                                │
│    # Save briefing for next session                                            │
│    session.save_briefing()                                                     │
│                                                                                │
│    # Persist all memory to disk                                                │
│    memory.sync()                                                               │
│                                                                                │
│    yield AgentEvent(COMPLETE, {tasks: 5, gates: 2, learnings: 3})              │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          ARTIFACTS + UPDATED MEMORY
```

### Module Structure (Post-Refactor)

```
src/sunwell/
│
├── context/                          # NEW: Session context
│   ├── __init__.py
│   └── session.py                    # SessionContext class
│
├── memory/                           # EXPANDED: Unified memory access
│   ├── __init__.py
│   ├── persistent.py                 # NEW: PersistentMemory class
│   ├── types.py                      # NEW: MemoryContext, TaskMemoryContext
│   └── briefing.py                   # EXISTING: Briefing class
│
├── intelligence/                     # UNCHANGED: Individual stores
│   ├── decisions.py                  # DecisionMemory
│   ├── failures.py                   # FailureMemory
│   └── patterns.py                   # PatternProfile
│
├── simulacrum/                       # UNCHANGED: Conversation memory
│   └── core/
│       └── store.py                  # SimulacrumStore
│
├── team/                             # UNCHANGED: Team knowledge
│   └── store.py                      # TeamKnowledgeStore
│
├── agent/                            # SIMPLIFIED: Execution engine
│   ├── __init__.py
│   ├── core.py                       # Agent class (~500 lines, was 1370)
│   ├── events.py                     # Event types (+ ORIENT)
│   ├── budget.py                     # Token budgeting
│   ├── gates.py                      # Validation gates
│   ├── validation.py                 # Validation runner
│   ├── fixer.py                      # Auto-fix logic
│   └── [request.py]                  # DELETED
│
├── naaru/                            # UPDATED: Accepts memory
│   ├── planners/
│   │   ├── harmonic.py               # HarmonicPlanner (+ memory param)
│   │   └── artifact.py               # ArtifactPlanner (+ memory param)
│   └── ...
│
├── cli/                              # SIMPLIFIED: Unified entry point
│   ├── main.py                       # CLI entry (uses SessionContext)
│   ├── chat/
│   │   └── command.py                # Chat entry (uses SessionContext)
│   ├── [agent/]                      # DELETED (bypass path)
│   │   └── [run.py]                  # DELETED
│   └── helpers.py                    # REDUCED (context building moved)
│
├── server/                           # UPDATED: Memory caching
│   ├── routes/
│   │   └── agent.py                  # Uses SessionContext + PersistentMemory
│   └── workspace_manager.py          # NEW: Per-workspace memory cache
│
└── ... (other modules unchanged)
```

### Server Architecture (Studio Integration)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SUNWELL SERVER                                      │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        WorkspaceManager                                     │ │
│  │                                                                             │ │
│  │   Caches PersistentMemory per workspace (expensive to reload)               │ │
│  │                                                                             │ │
│  │   workspace_id → PersistentMemory                                           │ │
│  │   "a1b2c3d4"   → PersistentMemory(decisions, failures, patterns, ...)       │ │
│  │   "x9y8z7w6"   → PersistentMemory(decisions, failures, patterns, ...)       │ │
│  │                                                                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                             │
│       ┌────────────────────────────┼────────────────────────────┐               │
│       │                            │                            │               │
│       ▼                            ▼                            ▼               │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐  │
│  │ GET /workspace/  │  │ POST /workspace/     │  │ WS /workspace/           │  │
│  │     {id}/memory  │  │      {id}/run        │  │    {id}/events           │  │
│  ├──────────────────┤  ├──────────────────────┤  ├──────────────────────────┤  │
│  │ Returns:         │  │ Creates:             │  │ Streams:                 │  │
│  │ • decisions[]    │  │ • SessionContext     │  │ • ORIENT                 │  │
│  │ • failures[]     │  │                      │  │ • PLAN_COMPLETE          │  │
│  │ • learnings[]    │  │ Gets from cache:     │  │ • TASK_START/COMPLETE    │  │
│  │ • patterns       │  │ • PersistentMemory   │  │ • LEARNING_ADDED         │  │
│  │                  │  │                      │  │ • DECISION_MADE          │  │
│  │                  │  │ Runs:                │  │ • FAILURE_RECORDED       │  │
│  │                  │  │ • agent.run(s, m)    │  │ • COMPLETE               │  │
│  └──────────────────┘  └──────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STUDIO (Svelte)                                     │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                          State Store                                        │ │
│  │                                                                             │ │
│  │   workspace: { path, name, type, framework }                                │ │
│  │   memory: { decisions[], failures[], learnings[], patterns }                │ │
│  │   briefing: { mission, status, hazards, nextAction }                        │ │
│  │   activeRun: { id, goal, tasks[], events[], status }                        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                             │
│       ┌────────────────────────────┼────────────────────────────┐               │
│       │                            │                            │               │
│       ▼                            ▼                            ▼               │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐  │
│  │   Observatory    │  │   Memory Explorer    │  │   Briefing Panel         │  │
│  │   (runs)         │  │   (browse memory)    │  │   (session continuity)   │  │
│  ├──────────────────┤  ├──────────────────────┤  ├──────────────────────────┤  │
│  │ • Task progress  │  │ • Decision timeline  │  │ • Mission               │  │
│  │ • Event stream   │  │ • Failure patterns   │  │ • Status                 │  │
│  │ • Live learnings │  │ • Learning graph     │  │ • Hazards                │  │
│  └──────────────────┘  └──────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Memory Flow Across Sessions

```
                    SESSION 1                              SESSION 2
                    ─────────                              ─────────

              ┌─────────────────┐                    ┌─────────────────┐
              │ Goal: "Add auth"│                    │ Goal: "Add cache│
              └────────┬────────┘                    └────────┬────────┘
                       │                                      │
                       ▼                                      ▼
              ┌─────────────────┐                    ┌─────────────────┐
              │ memory.load()   │                    │ memory.load()   │
              │ (empty/minimal) │                    │ (has decisions) │
              └────────┬────────┘                    └────────┬────────┘
                       │                                      │
                       ▼                                      ▼
              ┌─────────────────┐                    ┌─────────────────┐
              │ ORIENT          │                    │ ORIENT          │
              │ constraints: 0  │                    │ constraints: 2  │◄─┐
              │ dead_ends: 0    │                    │ dead_ends: 1    │  │
              └────────┬────────┘                    └────────┬────────┘  │
                       │                                      │           │
                       ▼                                      ▼           │
              ┌─────────────────┐                    ┌─────────────────┐  │
              │ PLAN            │                    │ PLAN            │  │
              │ (no constraints)│                    │ (respects them) │  │
              └────────┬────────┘                    └────────┬────────┘  │
                       │                                      │           │
                       ▼                                      ▼           │
              ┌─────────────────┐                    ┌─────────────────┐  │
              │ EXECUTE         │                    │ EXECUTE         │  │
              │ Tries Redis     │                    │ Uses SQLAlchemy │  │
              │ (fails)         │                    │ cache (works!)  │  │
              └────────┬────────┘                    └────────┬────────┘  │
                       │                                      │           │
                       ▼                                      ▼           │
              ┌─────────────────┐                    ┌─────────────────┐  │
              │ LEARN           │                    │ LEARN           │  │
              │                 │                    │                 │  │
              │ record_decision:│─────────────────────────────────────────┘
              │ "Chose OAuth"   │                    │ record_decision:│
              │ "Rejected JWT"  │                    │ "Chose dogpile" │
              │                 │                    │                 │
              │ record_failure: │─────────────────────────────────────────┐
              │ "Redis failed"  │                    │                 │  │
              │                 │                    │                 │  │
              │ memory.sync()   │                    │ memory.sync()   │  │
              └─────────────────┘                    └─────────────────┘  │
                                                                          │
                                                                          │
                                         SESSION 3                        │
                                         ─────────                        │
                                                                          │
                                   ┌─────────────────┐                    │
                                   │ Goal: "Optimize │                    │
                                   │ caching layer"  │                    │
                                   └────────┬────────┘                    │
                                            │                             │
                                            ▼                             │
                                   ┌─────────────────┐                    │
                                   │ memory.load()   │                    │
                                   │ (has history)   │                    │
                                   └────────┬────────┘                    │
                                            │                             │
                                            ▼                             │
                                   ┌─────────────────┐                    │
                                   │ ORIENT          │                    │
                                   │ constraints: 3  │◄───────────────────┘
                                   │ dead_ends: 1    │
                                   │ learnings: 5    │
                                   └────────┬────────┘
                                            │
                                            ▼
                                   Agent KNOWS:
                                   • Don't use Redis (failed)
                                   • We chose OAuth for auth
                                   • We use dogpile.cache
                                   • Pydantic v2 everywhere
```

---

## Appendix: Quick Reference

### New Files
```
sunwell/context/session.py      # SessionContext
sunwell/memory/persistent.py    # PersistentMemory
sunwell/memory/types.py         # MemoryContext, TaskMemoryContext
sunwell/server/workspace_manager.py  # Server memory cache
```

### Deleted Files
```
sunwell/cli/agent/run.py        # Bypassed Agent
sunwell/cli/agent/__init__.py   # Empty module
sunwell/agent/request.py        # RunRequest replaced
```

### New Pattern (All Entry Points)
```python
# Every entry point follows this pattern
session = SessionContext.build(workspace, goal, options)
memory = PersistentMemory.load(workspace)

agent = Agent(model=model, tool_executor=tools, cwd=workspace)
async for event in agent.run(session, memory):
    handle(event)
```

### Memory Query During Planning
```python
# In planner
memory_ctx = await memory.get_relevant(goal)

# Inject into prompt
if memory_ctx.constraints:
    prompt += "\n⛔ DO NOT: " + "\n⛔ DO NOT: ".join(memory_ctx.constraints)

if memory_ctx.dead_ends:
    prompt += "\n⚠️ AVOID: " + "\n⚠️ AVOID: ".join(memory_ctx.dead_ends)
```

### Existing Stores (Unchanged)
These modules are unchanged, just accessed through `PersistentMemory`:
- `intelligence/decisions.py:DecisionMemory`
- `intelligence/failures.py:FailureMemory`
- `intelligence/patterns.py:PatternProfile`
- `simulacrum/core/store.py:SimulacrumStore`
- `team/store.py:TeamKnowledgeStore`
