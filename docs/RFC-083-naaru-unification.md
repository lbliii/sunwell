# RFC-083: Naaru Unification — Single Orchestration Layer

**Status**: Draft (Revised)  
**Priority**: URGENT  
**Created**: 2026-01-21  
**Revised**: 2026-01-21  
**Authors**: @llane  
**Depends on**: RFC-019 (Naaru), RFC-042 (AdaptiveAgent), RFC-075 (InteractionRouter), RFC-082 (Fluid UI)

> **Revision Notes**: 
> - Added Design Alternatives (3 options evaluated)
> - Added Design Decisions (answers to open questions)
> - Replaced "Backward Compatibility" with "Clean Cut-Over" philosophy
> - No shims, no wrappers, no deprecation periods—legacy code is deleted
> - Confidence: 85% 🟢 → ready for planning

## Summary

Consolidate Sunwell's fragmented orchestration layers into a **single unified Naaru** that handles all execution flows. Every entry point (CLI, chat, Studio, API) routes through Naaru, which coordinates workers, shards, and convergence to execute tasks.

**This is urgent work** — the current architecture has:
- 5+ separate orchestrators with duplicated logic
- No shared context between entry points
- Inconsistent parallel processing
- Fragmented learning/memory

## Problem Statement

### Current State: Architectural Fragmentation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CURRENT STATE: 5+ ORCHESTRATORS                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  sunwell "goal"    sunwell chat    Studio         sunwell agent             │
│       │                 │            │                  │                   │
│       ▼                 ▼            ▼                  ▼                   │
│  AdaptiveAgent     chat.py     Interface         naaru_cmd.py              │
│  (RFC-042)         (custom)    Router            (direct Naaru)            │
│       │                │       (RFC-075)              │                    │
│       │                │            │                  │                   │
│       ▼                ▼            ▼                  ▼                   │
│  ┌─────────┐     ┌─────────┐  ┌─────────┐       ┌─────────┐               │
│  │ _naaru  │     │ Naaru   │  │ Intent  │       │  Naaru  │               │
│  │(internal│     │ Shards  │  │Analyzer │       │  .run() │               │
│  │   copy) │     │  only   │  │         │       │         │               │
│  └─────────┘     └─────────┘  └─────────┘       └─────────┘               │
│                                                                             │
│  ALSO SEPARATE:                                                             │
│  - RuntimeEngine (lens execution, has own routing)                          │
│  - ToolExecutor (tool calling, no coordination)                             │
│  - BootstrapOrchestrator (project init)                                     │
│  - parallel/Coordinator (multi-process, not integrated)                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Problems This Causes

| Problem | Impact | Example |
|---------|--------|---------|
| **Duplicated routing logic** | Bugs fixed in one place break another | CognitiveRouter vs UnifiedRouter vs IntentAnalyzer |
| **No shared context** | Same queries repeated | Chat doesn't know what Studio just did |
| **Inconsistent parallelism** | Some paths use Shards, some don't | AdaptiveAgent doesn't use Convergence |
| **Fragmented learning** | Learnings don't persist across entry points | Chat learns, CLI forgets |
| **Multiple event systems** | Can't build unified UI | AdaptiveAgent events ≠ Naaru events |
| **Testing nightmare** | Must test each orchestrator separately | 5x the integration tests |

### Why This Is Urgent

1. **RFC-082 (Fluid UI)** needs unified event stream — can't compose UI without knowing what's happening
2. **Studio launch** requires consistent behavior across all entry points
3. **Technical debt compounds** — every new feature must be added to 5 places
4. **Performance** — Naaru's parallel architecture is underutilized

## Design Principles

### 1. One Orchestrator to Rule Them All
Every execution flow goes through Naaru. No exceptions.

### 2. Workers Not Modules
Functionality lives in **Workers** (regions) that communicate via **MessageBus**, not in standalone modules.

### 3. Convergence Is The Truth
**Convergence** (shared working memory) is the single source of truth for current context. Not local variables, not request objects.

### 4. Shards For Everything Parallel
Any work that can run while the model thinks should be a **Shard**.

### 5. Events Flow Through Bus
All events (for UI, logging, metrics) flow through **MessageBus**. No direct callbacks.

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       UNIFIED NAARU ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ALL ENTRY POINTS:                                                          │
│                                                                             │
│  CLI              Chat           Studio            API/SDK                  │
│   │                │               │                  │                     │
│   └────────────────┴───────────────┴──────────────────┘                     │
│                           │                                                 │
│                           ▼                                                 │
│               ┌───────────────────────┐                                     │
│               │   naaru.process()     │  ← Single entry point               │
│               └───────────┬───────────┘                                     │
│                           │                                                 │
│  ╔════════════════════════╧════════════════════════╗                        │
│  ║                    NAARU                        ║                        │
│  ║              (The Light - Unified)              ║                        │
│  ╠═════════════════════════════════════════════════╣                        │
│  ║                                                 ║                        │
│  ║  ┌─────────────────────────────────────────┐   ║                        │
│  ║  │              MESSAGE BUS                │   ║                        │
│  ║  │  (All events, all coordination)         │   ║                        │
│  ║  └──────────────────┬──────────────────────┘   ║                        │
│  ║                     │                          ║                        │
│  ║  ┌──────────────────┼──────────────────────┐   ║                        │
│  ║  │                  │                      │   ║                        │
│  ║  ▼                  ▼                      ▼   ║                        │
│  ║ ┌────────┐   ┌─────────────┐        ┌────────┐║                        │
│  ║ │ROUTING │   │ CONVERGENCE │        │EXECUTE │║                        │
│  ║ │ REGION │   │  (7 slots)  │        │ REGION │║                        │
│  ║ │        │   │             │        │        │║                        │
│  ║ │intent  │   │composition  │        │tasks   │║                        │
│  ║ │tier    │   │context      │        │tools   │║                        │
│  ║ │lens    │   │memories     │        │files   │║                        │
│  ║ │page    │   │learnings    │        │        │║                        │
│  ║ └────────┘   └─────────────┘        └────────┘║                        │
│  ║      │              │                    │    ║                        │
│  ╚══════╧══════════════╧════════════════════╧════╝                        │
│         │              │                    │                              │
│  ┌──────┴──────────────┴────────────────────┴──────┐                       │
│  │                    SHARDS                        │                       │
│  │  (Parallel CPU work while GPU generates)         │                       │
│  ├─────────┬─────────┬─────────┬─────────┬─────────┤                       │
│  │Composit │ Memory  │ Context │ Verify  │Lookahead│                       │
│  │  ~50ms  │  ~50ms  │  ~50ms  │  ~50ms  │  ~50ms  │                       │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘                       │
│                                                                             │
│  ┌──────────────────────────────────────────────────┐                       │
│  │                    WORKERS                        │                       │
│  │  (Long-running regions with specialized models)   │                       │
│  ├──────────┬──────────┬──────────┬────────┬────────┤                       │
│  │ Routing  │ Analysis │Synthesis │Validate│  Tool  │                       │
│  │          │          │(Harmonic)│        │        │                       │
│  └──────────┴──────────┴──────────┴────────┴────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Detailed Design

### Phase 1: Unified Entry Point

**Goal**: All entry points call `naaru.process()` instead of their own orchestration.

```python
@dataclass
class ProcessInput:
    """Unified input for all Naaru processing."""
    
    # What the user wants
    content: str
    """User input (goal, message, query)."""
    
    # Context
    mode: ProcessMode = ProcessMode.AUTO
    """Processing mode: AUTO, CHAT, AGENT, INTERFACE."""
    
    page_type: str = "home"
    """Current UI page (for composition)."""
    
    conversation_history: list[dict] | None = None
    """Prior messages for continuity."""
    
    workspace: Path | None = None
    """Project workspace if applicable."""
    
    # Options
    stream: bool = True
    """Stream events as they happen."""
    
    timeout: float = 300.0
    """Max execution time."""


class ProcessMode(Enum):
    """How to process the input."""
    AUTO = "auto"           # Naaru decides based on routing
    CHAT = "chat"           # Conversational (RFC-075 conversation)
    AGENT = "agent"         # Task execution (RFC-032)
    INTERFACE = "interface" # UI composition (RFC-082)


@dataclass
class ProcessOutput:
    """Unified output from all Naaru processing."""
    
    # Core result
    response: str
    """Text response to user."""
    
    # Routing info (from Routing Worker)
    route_type: str
    """How it was routed: conversation, action, view, workspace, hybrid."""
    
    confidence: float
    """Routing confidence."""
    
    # UI composition (from Compositor Shard)
    composition: CompositionSpec | None = None
    """UI layout spec for frontend."""
    
    # Execution results (from Execute Region)
    tasks_completed: int = 0
    artifacts: list[Path] = field(default_factory=list)
    
    # For streaming
    events: list[NaaruEvent] = field(default_factory=list)


class Naaru:
    """Unified orchestrator for all Sunwell execution."""
    
    async def process(
        self, 
        input: ProcessInput,
    ) -> AsyncIterator[NaaruEvent] | ProcessOutput:
        """
        THE entry point. All roads lead here.
        
        1. Route (Routing Worker) — What kind of request?
        2. Compose (Compositor Shard) — What UI to show?
        3. Prepare (Context Shards) — Gather context in parallel
        4. Execute (Execute Region) — Run tasks/tools
        5. Validate (Validation Worker) — Check quality
        6. Learn (Consolidator Shard) — Persist learnings
        7. Respond — Return result
        
        If stream=True, yields events as they happen.
        If stream=False, returns final ProcessOutput.
        """
        ...
```

### Phase 2: Consolidate Routing

**Goal**: Single routing path using Naaru's Routing Worker.

**Retire**:
- `IntentAnalyzer` (interface/analyzer.py)
- `CognitiveRouter` (routing/)
- `UnifiedRouter` (routing/unified.py)
- `AdaptiveSignals.extract()` (adaptive/signals.py)
- `RuntimeEngine._classify_intent()` (runtime/engine.py)

**Replace with**:
- `RoutingWorker` — Already exists, expand to handle all cases

```python
class RoutingWorker(RegionWorker):
    """Unified routing for all input types.
    
    Determines:
    - interaction_type: conversation | action | view | workspace | hybrid
    - tier: fast_path | standard | complex
    - lens: which lens to use (if any)
    - page_type: home | project | research | planning | conversation
    - confidence: how sure we are
    - tools: what tools might be needed
    - mood: user's emotional state (for empathetic response)
    """
    
    async def route(self, input: ProcessInput) -> RoutingDecision:
        """Single routing decision for any input."""
        
        # 1. Fast regex check (Tier 0)
        fast_match = self._regex_route(input.content)
        if fast_match and fast_match.confidence >= 0.9:
            return fast_match
        
        # 2. LLM routing (Tier 1)
        return await self._llm_route(input)
```

### Phase 3: Convergence As Single Source of Truth

**Goal**: All context flows through Convergence slots.

```python
# Standard Convergence slots
CONVERGENCE_SLOTS = {
    # Routing (set by RoutingWorker)
    "routing:current": "Current routing decision",
    
    # UI Composition (set by Compositor Shard)
    "composition:current": "UI layout spec",
    "composition:previous": "Previous layout (for transitions)",
    
    # Context (set by Context Shards)
    "context:lens": "Active lens components",
    "context:workspace": "Workspace files/structure",
    "context:history": "Conversation history",
    
    # Memory (set by Memory Shard)
    "memories:relevant": "Retrieved from SimulacrumStore",
    "memories:user": "User identity/preferences",
    
    # Execution (set by Execute Region)
    "execution:current_task": "Task being executed",
    "execution:artifacts": "Produced artifacts",
    
    # Validation (set by Validation Worker)
    "validation:result": "Quality check result",
    
    # Learning (set by Consolidator Shard)
    "learnings:pending": "To persist after task",
}
```

### Phase 4: Unified Event System

**Goal**: All events flow through MessageBus.

**Retire**:
- `AdaptiveAgent` events (adaptive/events.py)
- Direct callbacks in RuntimeEngine
- Custom event handling in chat.py

**Replace with**:
- `NaaruEvent` — Single event type
- `MessageBus` — Single transport

```python
class NaaruEventType(Enum):
    """All possible events from Naaru."""
    
    # Lifecycle
    PROCESS_START = "process_start"
    PROCESS_COMPLETE = "process_complete"
    PROCESS_ERROR = "process_error"
    
    # Routing
    ROUTE_DECISION = "route_decision"
    
    # Composition (RFC-082)
    COMPOSITION_READY = "composition_ready"
    COMPOSITION_UPDATED = "composition_updated"
    
    # Model
    MODEL_START = "model_start"
    MODEL_THINKING = "model_thinking"
    MODEL_TOKENS = "model_tokens"
    MODEL_COMPLETE = "model_complete"
    
    # Tasks
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"
    
    # Tools
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    
    # Validation
    VALIDATION_START = "validation_start"
    VALIDATION_RESULT = "validation_result"
    
    # Learning
    LEARNING_EXTRACTED = "learning_extracted"
    LEARNING_PERSISTED = "learning_persisted"


@dataclass
class NaaruEvent:
    """Single event type for all Naaru activity."""
    
    type: NaaruEventType
    timestamp: datetime
    data: dict[str, Any]
    
    # For streaming to frontend
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        })
```

### Phase 5: Retire Legacy Orchestrators

**Goal**: Remove duplicate code.

| Component | Action | Replacement |
|-----------|--------|-------------|
| `AdaptiveAgent` | RETIRE | `Naaru.process(mode=AGENT)` |
| `RuntimeEngine` | RETIRE | `SynthesisWorker` |
| `IntentAnalyzer` | RETIRE | `RoutingWorker` |
| `InteractionRouter` | RETIRE | `Naaru.process(mode=INTERFACE)` |
| `CognitiveRouter` | RETIRE | `RoutingWorker` |
| `BootstrapOrchestrator` | MERGE | `BootstrapWorker` |
| `parallel/Coordinator` | MERGE | `ParallelExecutionWorker` |

**Lines of code removed**: ~4,000+ (measured: 4,089 lines across 6 legacy orchestrators)  
**Test files simplified**: ~15-20 (estimated)

<details>
<summary>Verified line counts</summary>

| File | Lines | Status |
|------|-------|--------|
| `adaptive/agent.py` | 1,056 | Retire (partial) |
| `runtime/engine.py` | 905 | Retire |
| `routing/unified.py` | 739 | Retire |
| `routing/cognitive_router.py` | 680 | Retire |
| `interface/analyzer.py` | 404 | Retire |
| `interface/router.py` | 305 | Retire |
| **Total legacy** | **4,089** | |

Naaru core (kept/expanded):
| File | Lines |
|------|-------|
| `naaru/coordinator.py` | 715 |
| `naaru/shards.py` | 618 |
| `naaru/convergence.py` | 388 |
| `naaru/workers/*.py` | 1,223 |
| `naaru/core/*.py` | 224 |
| **Total Naaru** | **3,168** |

</details>

## Design Alternatives

Three approaches were considered for addressing the orchestration fragmentation:

### Option A: Full Unification (RECOMMENDED)

**Description**: Single `Naaru.process()` entry point for all execution flows. All orchestrators converge to Naaru.

```
ALL ENTRY POINTS → Naaru.process() → Workers/Shards → Output
```

**Pros**:
- Eliminates all duplication
- Single event system for UI
- Maximizes parallel utilization (Shards run for every request)
- Simplest mental model

**Cons**:
- Largest migration scope (6 weeks)
- Higher regression risk
- Requires full-stack changes simultaneously

**Estimated effort**: 6 weeks

---

### Option B: Shared Convergence Only

**Description**: Keep existing orchestrators but have them all read/write to shared Convergence. Unify context without unifying control flow.

```
AdaptiveAgent ─┐
               │
RuntimeEngine  ├──→ SHARED CONVERGENCE ←──→ Shards
               │
IntentAnalyzer ─┘
```

**Pros**:
- Lower risk (orchestrators unchanged)
- Faster to implement (2-3 weeks)
- Incremental—can iterate

**Cons**:
- Still 5+ orchestrators to maintain
- Events still fragmented
- Parallel utilization inconsistent
- Technical debt remains

**Estimated effort**: 3 weeks

**Why rejected**: Doesn't solve the core problem. We'd still have duplicated routing logic, multiple event systems, and inconsistent parallel processing. This is a band-aid, not a fix.

---

### Option C: Phased Consolidation

**Description**: Consolidate in layers over 3 RFCs:
1. **RFC-083a**: Unify Python orchestrators (CLI + chat + agent → Naaru)
2. **RFC-083b**: Unify Rust/Tauri layer (single `naaru.rs`)
3. **RFC-083c**: Unify Svelte stores (single `naaru.svelte.ts`)

**Pros**:
- Smaller blast radius per RFC
- Can ship value incrementally
- Easier to rollback specific layers

**Cons**:
- Longer total timeline (8-10 weeks)
- Temporary inconsistency between layers
- More coordination overhead

**Estimated effort**: 8-10 weeks total

**Why rejected for now**: The three layers are tightly coupled. Changing Python API without updating Rust/Svelte creates churn. Full unification in one RFC, while larger, is cleaner. However, this approach remains a valid fallback if Option A encounters blockers.

---

### Decision: Option A (Full Unification)

We proceed with full unification because:
1. **The problem is interconnected**—fragmented routing affects all layers equally
2. **RFC-082 (Fluid UI) is blocked**—needs unified events, can't wait 10 weeks
3. **Technical debt compounds**—every week we delay, more code gets added to wrong places
4. **Feature flags provide safety**—can A/B test and rollback

The migration plan below de-risks Option A with feature flags and extensive testing. No shims. No wrappers. Clean cut-over.

## Migration Plan

### Week 1: Unified Entry Point
- [ ] Create `ProcessInput`, `ProcessOutput`, `ProcessMode`
- [ ] Add `Naaru.process()` method
- [ ] Wire CLI to call `naaru.process()` (behind feature flag)
- [ ] Wire chat to call `naaru.process()` (behind feature flag)

### Week 2: Routing Consolidation
- [ ] Expand `RoutingWorker` to handle all routing cases
- [ ] Port `IntentAnalyzer` logic to `RoutingWorker`
- [ ] Port `CognitiveRouter` logic to `RoutingWorker`
- [ ] Port `AdaptiveSignals` to `RoutingWorker`
- [ ] Add tests proving equivalence

### Week 3: Convergence Integration
- [ ] Define standard slots
- [ ] Update all Shards to use standard slots
- [ ] Update all Workers to read from Convergence
- [ ] Remove local state in favor of Convergence

### Week 4: Event Unification
- [ ] Create `NaaruEventType` enum
- [ ] Create `NaaruEvent` dataclass
- [ ] Update MessageBus to emit unified events
- [ ] Wire Studio frontend to consume unified events
- [ ] Remove legacy event types

### Week 5: Legacy Deletion
- [ ] Delete `AdaptiveAgent` class entirely
- [ ] Delete `RuntimeEngine` class entirely
- [ ] Delete `IntentAnalyzer` class entirely
- [ ] Delete `InteractionRouter` class entirely
- [ ] Delete `CognitiveRouter` and `UnifiedRouter` entirely
- [ ] Delete orphaned test files
- [ ] Run full test suite; fix any breakage

### Week 6: Polish & Performance
- [ ] Profile unified path
- [ ] Optimize Convergence access patterns
- [ ] Add metrics/tracing
- [ ] Documentation update

## API Changes

### Before (Multiple Entry Points)

```python
# CLI goal
agent = AdaptiveAgent(model=model)
async for event in agent.run(goal):
    ...

# Chat
result = await model.generate(prompt)  # Custom handling

# Interface
analysis = await analyzer.analyze(goal)
output = await router.route(analysis)

# Agent mode
result = await naaru.run(goal)
```

### After (Single Entry Point)

```python
# ALL paths
naaru = Naaru(...)

# CLI goal
async for event in naaru.process(ProcessInput(content=goal, mode=ProcessMode.AGENT)):
    ...

# Chat  
async for event in naaru.process(ProcessInput(content=message, mode=ProcessMode.CHAT)):
    ...

# Interface
result = await naaru.process(ProcessInput(content=input, mode=ProcessMode.INTERFACE), stream=False)

# Auto (Naaru decides)
async for event in naaru.process(ProcessInput(content=anything)):
    ...
```

## Migration Philosophy: Clean Cut-Over

**No shims. No wrappers. No deprecation periods.**

### Why No Backward Compatibility

1. **Shims hide bugs** — Wrapper code that translates old→new APIs masks integration issues until production
2. **Maintenance burden** — Every wrapper is code that must be tested and eventually removed
3. **Confusing codebase** — New contributors see two ways to do everything, don't know which is "right"
4. **Delayed cleanup** — "Temporary" compatibility layers become permanent (see: Python 2→3)

### What This Means

- **Legacy classes are deleted**, not deprecated
- **Old CLI commands stop working** — users get clear error: "Use `sunwell naaru process` instead"
- **Old imports fail** — `from sunwell.adaptive import AdaptiveAgent` raises `ImportError`
- **Tests are deleted or rewritten**, not shimmed

### Feature Flags (Development Only)

Feature flags exist for **development/testing**, not for maintaining legacy paths:

```yaml
# sunwell.yaml (development only)
naaru:
  unified_orchestration: true  # Toggle during development; removed before release
```

Once unified orchestration ships, this flag is removed from the codebase.

## Success Metrics

| Metric | Before | After | Verified |
|--------|--------|-------|----------|
| Entry point count | 5+ | 1 | ✅ |
| Lines of orchestration code | ~7,200 | ~3,200 | ✅ (measured) |
| Test files for orchestration | ~20 | ~8 | Estimated |
| Event types | 3 systems | 1 | ✅ |
| Context duplication | High | None (Convergence) | ✅ |
| Parallel utilization | Inconsistent | 100% (all Shards) | Design goal |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Regression in specific path | Medium | High | Extensive testing with feature flags during dev |
| Performance degradation | Low | Medium | Profile before/after; optimize Convergence |
| Learning curve for contributors | Medium | Low | Documentation; examples; clean single path |
| Studio integration breaks | Medium | High | Wire Studio first; test continuously |
| Scope creep extends timeline | Medium | Medium | Strict scope; defer nice-to-haves to follow-up RFCs |
| External consumers break | Low | Low | Sunwell is internal; no external API promises |

### Rollback Plan

**Rollback = Git Revert.** No runtime flags, no wrappers.

**During development (Weeks 1-4)**:
- Feature flag `unified_orchestration` allows toggling
- All changes in atomic commits by subsystem
- CI runs both old and new paths until Week 5

**After legacy deletion (Week 5+)**:
- Rollback requires `git revert` of the deletion commits
- This is intentionally high-friction to prevent "temporary" rollbacks becoming permanent
- If we need to rollback, we have a real bug to fix

**Monitoring**:
```yaml
metrics_to_watch:
  - naaru.process.latency_p99
  - naaru.routing.confidence_mean
  - naaru.events.dropped_count
  
alerts:
  - latency_p99 > 2x baseline: investigate immediately
  - routing_confidence < 0.7: investigate
  - events_dropped > 0: critical bug
```

**If rollback is needed**: Fix forward, don't maintain two paths.

## Design Decisions

### Decision 1: Naaru Instantiation — Session-Scoped (Not Singleton)

**Question**: Should `Naaru` be a singleton or instantiated per-request?

**Decision**: **Session-scoped** — one Naaru instance per user session, not singleton.

**Rationale**:
- **Singleton problems**: Global mutable state, hard to test, no session isolation
- **Per-request problems**: No shared Convergence, repeated warm-up cost
- **Session-scoped benefits**: Convergence persists across requests in a session, isolates users, allows stateful conversation

**Implementation**:
```python
class NaaruSession:
    """Wraps Naaru with session lifecycle management."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.naaru = Naaru(...)
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
    
    async def process(self, input: ProcessInput) -> AsyncIterator[NaaruEvent]:
        self.last_accessed = datetime.now()
        async for event in self.naaru.process(input):
            yield event


class NaaruSessionManager:
    """Manages session pool with TTL eviction."""
    
    def __init__(self, max_sessions: int = 100, ttl_hours: float = 4.0):
        self._sessions: dict[str, NaaruSession] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = timedelta(hours=ttl_hours)
    
    def get_or_create(self, session_id: str) -> NaaruSession:
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            
            # Evict expired sessions
            self._evict_expired()
            
            # Create new session
            session = NaaruSession(session_id)
            self._sessions[session_id] = session
            return session
```

---

### Decision 2: Convergence TTL — Tiered by Slot Type

**Question**: How to handle long-running chat sessions? Convergence TTLs need tuning.

**Decision**: **Tiered TTLs** based on slot type:

| Slot Category | TTL | Rationale |
|---------------|-----|-----------|
| `routing:*` | 30 seconds | Routing decisions are request-specific |
| `composition:*` | 5 minutes | UI state persists across interactions |
| `context:*` | 30 minutes | Workspace/lens context changes slowly |
| `memories:*` | Session lifetime | User identity persists for session |
| `execution:*` | 5 minutes | Task state needed for follow-ups |
| `validation:*` | 30 seconds | Validation is per-request |
| `learnings:*` | Session lifetime | Learnings persist to SimulacrumStore |

**Implementation**:
```python
SLOT_TTL_SECONDS: dict[str, float] = {
    "routing": 30,
    "composition": 300,
    "context": 1800,
    "memories": float("inf"),  # Session lifetime
    "execution": 300,
    "validation": 30,
    "learnings": float("inf"),
}

def get_slot_ttl(slot_id: str) -> float:
    """Get TTL for a slot based on its prefix."""
    prefix = slot_id.split(":")[0]
    return SLOT_TTL_SECONDS.get(prefix, 300)  # Default 5 min
```

---

### Decision 3: Multi-Tenant — Deferred (Not In Scope)

**Question**: If Naaru becomes a service, how to handle tenant isolation?

**Decision**: **Deferred** — multi-tenant is out of scope for RFC-083.

**Rationale**:
- Sunwell is currently **local-first** (runs on user's machine)
- Multi-tenant architecture requires fundamentally different decisions (auth, quotas, data isolation)
- Adding tenant isolation now would add complexity without immediate value
- When/if we build Sunwell Cloud, we'll design for multi-tenancy from the start

**For now**: Session isolation (Decision 1) provides user-level isolation in local mode.

**Future work**: If Sunwell becomes a hosted service, a separate RFC (e.g., RFC-100: Sunwell Cloud Architecture) will address:
- Tenant-scoped Convergence pools
- Per-tenant rate limiting
- Data isolation and encryption
- Tenant-aware routing

## Full-Stack Integration

### The Three Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FULL STACK UNIFICATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        SVELTE (Frontend)                            │   │
│  │                                                                     │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │   │
│  │  │ home.svelte │    │ FluidInput  │    │   ConversationLayout    │ │   │
│  │  │   .ts       │    │   .svelte   │    │       .svelte           │ │   │
│  │  └──────┬──────┘    └──────┬──────┘    └───────────┬─────────────┘ │   │
│  │         │                  │                       │               │   │
│  │         └──────────────────┴───────────────────────┘               │   │
│  │                            │                                       │   │
│  │                            ▼                                       │   │
│  │              ┌──────────────────────────────┐                      │   │
│  │              │      naaruStore.svelte.ts    │  ← SINGLE STORE      │   │
│  │              │                              │                      │   │
│  │              │  - process(input)            │                      │   │
│  │              │  - composition (reactive)    │                      │   │
│  │              │  - events (stream)           │                      │   │
│  │              │  - convergence (read-only)   │                      │   │
│  │              └──────────────┬───────────────┘                      │   │
│  └─────────────────────────────┼───────────────────────────────────────┘   │
│                                │                                           │
│                                │ invoke('naaru_process', ...)              │
│                                ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         RUST (Tauri)                                │   │
│  │                                                                     │   │
│  │  ┌────────────────────────────────────────────────────────────────┐│   │
│  │  │                     naaru.rs                                   ││   │
│  │  │                                                                ││   │
│  │  │  #[tauri::command]                                             ││   │
│  │  │  pub async fn naaru_process(input: ProcessInput)               ││   │
│  │  │      -> Result<Stream<NaaruEvent>, String>                     ││   │
│  │  │                                                                ││   │
│  │  │  #[tauri::command]                                             ││   │
│  │  │  pub async fn naaru_get_convergence(slot: String)              ││   │
│  │  │      -> Result<ConvergenceSlot, String>                        ││   │
│  │  │                                                                ││   │
│  │  └────────────────────────────────────────────────────────────────┘│   │
│  │                                │                                   │   │
│  └────────────────────────────────┼───────────────────────────────────┘   │
│                                   │                                       │
│                                   │ sunwell naaru process --json          │
│                                   ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        PYTHON (Backend)                             │   │
│  │                                                                     │   │
│  │  ┌────────────────────────────────────────────────────────────────┐│   │
│  │  │                        NAARU                                   ││   │
│  │  │                   (Single Orchestrator)                        ││   │
│  │  │                                                                ││   │
│  │  │  async def process(input: ProcessInput) -> AsyncIterator[Event]││   │
│  │  │                                                                ││   │
│  │  │  ┌──────────┐  ┌───────────┐  ┌────────┐  ┌─────────┐        ││   │
│  │  │  │ Routing  │  │Convergence│  │ Shards │  │ Workers │        ││   │
│  │  │  │  Worker  │  │ (7 slots) │  │        │  │         │        ││   │
│  │  │  └──────────┘  └───────────┘  └────────┘  └─────────┘        ││   │
│  │  └────────────────────────────────────────────────────────────────┘│   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Rust/Tauri Layer Changes

**Current State** (fragmented):
```rust
// interface.rs - 5+ separate commands
pub async fn process_goal(...) -> Result<InterfaceOutput>
pub async fn predict_composition(...) -> Result<CompositionSpec>
pub async fn execute_block_action(...) -> Result<BlockActionResult>

// commands.rs - more separate commands  
pub async fn run_goal(...) -> Result<...>
pub async fn analyze_project(...) -> Result<...>

// dag.rs - even more
pub async fn get_project_dag(...) -> Result<...>
pub async fn execute_dag_node(...) -> Result<...>
```

**Target State** (unified):
```rust
// naaru.rs - THE Tauri interface to Naaru

/// Process any input through Naaru
#[tauri::command]
pub async fn naaru_process(
    input: ProcessInput,
    stream: bool,
) -> Result<ProcessOutput, String> {
    // Calls: sunwell naaru process --json
    // Returns: Unified ProcessOutput (or streams events)
}

/// Subscribe to Naaru event stream (for real-time UI)
#[tauri::command]
pub async fn naaru_subscribe(
    window: tauri::Window,
) -> Result<(), String> {
    // Opens event stream, emits to window
}

/// Read a Convergence slot (for UI state)
#[tauri::command]
pub async fn naaru_convergence(
    slot: String,
) -> Result<Option<ConvergenceSlot>, String> {
    // Calls: sunwell naaru convergence --slot <slot> --json
}

/// Cancel current processing
#[tauri::command]
pub async fn naaru_cancel() -> Result<(), String> {
    // Sends cancel signal
}
```

**Tauri Commands to Retire**:
| Command | Replacement |
|---------|-------------|
| `process_goal` | `naaru_process` |
| `predict_composition` | `naaru_convergence("composition:current")` |
| `execute_block_action` | `naaru_process` with action mode |
| `run_goal` | `naaru_process` |
| `analyze_project` | `naaru_process` with analysis mode |
| `get_project_dag` | `naaru_convergence("execution:dag")` |

### Svelte/Frontend Layer Changes

**Current State** (multiple stores):
```typescript
// home.svelte.ts
export let homeState = $state<HomeState>({...});
export async function routeInput(input: string): Promise<HomeResponse>
export async function getSpeculativeComposition(input: string): Promise<CompositionSpec>

// Other stores scattered
// - project store
// - workspace store  
// - etc.
```

**Target State** (single Naaru store):
```typescript
// stores/naaru.svelte.ts
// THE store for all Naaru interaction

import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

// ═══════════════════════════════════════════════════════════════
// TYPES (match Python exactly)
// ═══════════════════════════════════════════════════════════════

export type ProcessMode = 'auto' | 'chat' | 'agent' | 'interface';

export interface ProcessInput {
    content: string;
    mode?: ProcessMode;
    page_type?: string;
    conversation_history?: Array<{ role: string; content: string }>;
    workspace?: string;
    stream?: boolean;
    timeout?: number;
}

export interface ProcessOutput {
    response: string;
    route_type: string;
    confidence: number;
    composition: CompositionSpec | null;
    tasks_completed: number;
    artifacts: string[];
    events: NaaruEvent[];
}

export interface NaaruEvent {
    type: NaaruEventType;
    timestamp: string;
    data: Record<string, unknown>;
}

export interface ConvergenceSlot {
    id: string;
    content: unknown;
    relevance: number;
    source: string;
    ready: boolean;
}

// ═══════════════════════════════════════════════════════════════
// STATE (reactive)
// ═══════════════════════════════════════════════════════════════

interface NaaruState {
    // Processing state
    isProcessing: boolean;
    error: string | null;
    
    // Current response
    response: ProcessOutput | null;
    
    // Convergence mirror (read-only view of Python state)
    convergence: {
        composition: CompositionSpec | null;
        routing: RoutingDecision | null;
        context: unknown | null;
    };
    
    // Event stream (for real-time UI)
    events: NaaruEvent[];
    
    // Conversation history (local, sent with each request)
    conversationHistory: Array<{ role: string; content: string; timestamp: number }>;
}

export let naaruState = $state<NaaruState>({
    isProcessing: false,
    error: null,
    response: null,
    convergence: {
        composition: null,
        routing: null,
        context: null,
    },
    events: [],
    conversationHistory: [],
});

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * THE function. All UI interaction goes through here.
 */
export async function process(input: ProcessInput): Promise<ProcessOutput> {
    naaruState.isProcessing = true;
    naaruState.error = null;
    naaruState.events = [];
    
    // Add to conversation history
    naaruState.conversationHistory = [
        ...naaruState.conversationHistory,
        { role: 'user', content: input.content, timestamp: Date.now() },
    ];
    
    try {
        // Call unified Naaru endpoint
        const result = await invoke<ProcessOutput>('naaru_process', {
            input: {
                ...input,
                conversation_history: naaruState.conversationHistory,
            },
        });
        
        naaruState.response = result;
        
        // Update convergence mirror
        if (result.composition) {
            naaruState.convergence.composition = result.composition;
        }
        
        // Add assistant response to history
        if (result.response) {
            naaruState.conversationHistory = [
                ...naaruState.conversationHistory,
                { role: 'assistant', content: result.response, timestamp: Date.now() },
            ];
        }
        
        return result;
    } catch (e) {
        naaruState.error = e instanceof Error ? e.message : String(e);
        throw e;
    } finally {
        naaruState.isProcessing = false;
    }
}

/**
 * Subscribe to real-time Naaru events.
 * Call once on app init.
 */
export async function subscribeToEvents(): Promise<void> {
    await invoke('naaru_subscribe');
    
    await listen<NaaruEvent>('naaru_event', (event) => {
        naaruState.events = [...naaruState.events, event.payload];
        
        // Update convergence mirror based on event type
        if (event.payload.type === 'composition_ready') {
            naaruState.convergence.composition = event.payload.data as CompositionSpec;
        } else if (event.payload.type === 'route_decision') {
            naaruState.convergence.routing = event.payload.data as RoutingDecision;
        }
    });
}

/**
 * Read a specific Convergence slot.
 */
export async function getConvergenceSlot(slot: string): Promise<ConvergenceSlot | null> {
    return invoke<ConvergenceSlot | null>('naaru_convergence', { slot });
}

/**
 * Cancel current processing.
 */
export async function cancel(): Promise<void> {
    await invoke('naaru_cancel');
    naaruState.isProcessing = false;
}

/**
 * Clear conversation history (new session).
 */
export function clearHistory(): void {
    naaruState.conversationHistory = [];
    naaruState.response = null;
    naaruState.events = [];
}
```

**Svelte Components to Update**:
| Component | Change |
|-----------|--------|
| `Home.svelte` | Use `naaruState` instead of `homeState` |
| `FluidInput.svelte` | Call `process()` instead of `routeInput()` |
| `ConversationLayout.svelte` | Read `naaruState.convergence.composition` |
| `BlockSurface.svelte` | Listen to `naaruState.events` |
| `ChatHistory.svelte` | Use `naaruState.conversationHistory` |

### Data Flow: End-to-End Example

```
User types: "plan my week"
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ SVELTE: FluidInput.svelte                                       │
│                                                                 │
│   onSubmit(value) {                                             │
│       process({ content: value, mode: 'auto' });                │
│   }                                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ invoke('naaru_process', {...})
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ RUST: naaru.rs                                                  │
│                                                                 │
│   #[tauri::command]                                             │
│   pub async fn naaru_process(input: ProcessInput) {             │
│       let output = sunwell_command()                            │
│           .args(["naaru", "process", "--json"])                 │
│           .arg(&serde_json::to_string(&input)?)                 │
│           .output()?;                                           │
│       // Stream events to window                                │
│       // Return final ProcessOutput                             │
│   }                                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ sunwell naaru process --json
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ PYTHON: Naaru.process()                                         │
│                                                                 │
│   1. RoutingWorker.route() → route_type="conversation"          │
│   2. CompositorShard.run() → composition={panels:["calendar"]}  │
│   3. MemoryShard.run() → memories=[...]                         │
│   4. SynthesisWorker.generate() → response="Let's plan..."      │
│   5. ConsolidatorShard.run() → learnings=[...]                  │
│                                                                 │
│   Events emitted at each step via MessageBus                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ JSON stream (events + final result)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ RUST → SVELTE: Event propagation                                │
│                                                                 │
│   t=0ms:   emit('naaru_event', {type: 'process_start'})         │
│   t=10ms:  emit('naaru_event', {type: 'route_decision'})        │
│   t=50ms:  emit('naaru_event', {type: 'composition_ready'})     │
│            → UI renders skeleton with calendar panel            │
│   t=2000ms: emit('naaru_event', {type: 'model_tokens', ...})    │
│            → UI streams response text                           │
│   t=3000ms: Return ProcessOutput                                │
│            → UI shows final state                               │
└─────────────────────────────────────────────────────────────────┘
```

### CLI Integration

The CLI also goes through unified Naaru:

```python
# cli/naaru_cmd.py (replaces multiple command files)

@click.group()
def naaru():
    """Naaru - Unified orchestration."""
    pass

@naaru.command("process")
@click.argument("content")
@click.option("--mode", "-m", type=click.Choice(["auto", "chat", "agent", "interface"]), default="auto")
@click.option("--json", "json_output", is_flag=True)
@click.option("--stream", is_flag=True)
def process(content: str, mode: str, json_output: bool, stream: bool):
    """Process any input through Naaru.
    
    Examples:
        sunwell naaru process "Build a REST API"
        sunwell naaru process "plan my week" --mode chat
        sunwell naaru process "what files are in src/" --mode interface --json
    """
    asyncio.run(_process(content, mode, json_output, stream))

@naaru.command("convergence")
@click.option("--slot", "-s", help="Specific slot to read")
@click.option("--json", "json_output", is_flag=True)
def convergence(slot: str | None, json_output: bool):
    """Read Convergence state.
    
    Examples:
        sunwell naaru convergence --slot composition:current --json
        sunwell naaru convergence  # List all slots
    """
    asyncio.run(_convergence(slot, json_output))
```

**CLI Commands to Retire**:
| Old Command | New Command |
|-------------|-------------|
| `sunwell "goal"` | `sunwell naaru process "goal"` |
| `sunwell chat` | `sunwell naaru process --mode chat --stream` |
| `sunwell agent run "goal"` | `sunwell naaru process "goal" --mode agent` |
| `sunwell interface process -g "goal"` | `sunwell naaru process "goal" --mode interface` |

**Old commands are deleted**, not aliased. Users get a clear error:

```
$ sunwell "build an API"
Error: Unknown command. Did you mean: sunwell naaru process "build an API"
```

### Type Contracts Across Layers

**Single source of truth**: Python types, generated to Rust/TypeScript.

```python
# types/naaru_api.py - Canonical definitions

@dataclass(frozen=True, slots=True)
class ProcessInput:
    content: str
    mode: ProcessMode = ProcessMode.AUTO
    page_type: str = "home"
    conversation_history: tuple[ConversationMessage, ...] = ()
    workspace: str | None = None
    stream: bool = True
    timeout: float = 300.0

@dataclass(frozen=True, slots=True)
class ProcessOutput:
    response: str
    route_type: str
    confidence: float
    composition: CompositionSpec | None = None
    tasks_completed: int = 0
    artifacts: tuple[str, ...] = ()
    events: tuple[NaaruEvent, ...] = ()

@dataclass(frozen=True, slots=True)
class NaaruEvent:
    type: NaaruEventType
    timestamp: datetime
    data: dict[str, Any]
```

**Generation scripts**:
```bash
# Generate TypeScript types from Python
python scripts/generate_ts_types.py src/sunwell/types/naaru_api.py > studio/src/types/naaru.ts

# Generate Rust types from Python  
python scripts/generate_rust_types.py src/sunwell/types/naaru_api.py > studio/src-tauri/src/naaru_types.rs
```

### Files to Create/Modify

**Python** (backend):
| File | Action |
|------|--------|
| `src/sunwell/types/naaru_api.py` | CREATE - Canonical type definitions |
| `src/sunwell/naaru/coordinator.py` | MODIFY - Add `process()` method |
| `src/sunwell/cli/naaru_cmd.py` | MODIFY - Add unified CLI |
| `src/sunwell/cli/main.py` | MODIFY - Deprecate old commands |

**Rust** (Tauri):
| File | Action |
|------|--------|
| `studio/src-tauri/src/naaru.rs` | CREATE - Unified Tauri commands |
| `studio/src-tauri/src/naaru_types.rs` | CREATE - Generated types |
| `studio/src-tauri/src/main.rs` | MODIFY - Register new commands |
| `studio/src-tauri/src/interface.rs` | DEPRECATE - Mark for removal |
| `studio/src-tauri/src/commands.rs` | DEPRECATE - Mark for removal |

**Svelte** (frontend):
| File | Action |
|------|--------|
| `studio/src/stores/naaru.svelte.ts` | CREATE - Unified store |
| `studio/src/types/naaru.ts` | CREATE - Generated types |
| `studio/src/stores/home.svelte.ts` | DEPRECATE - Migrate to naaru store |
| `studio/src/routes/Home.svelte` | MODIFY - Use naaru store |
| `studio/src/components/FluidInput.svelte` | MODIFY - Call `process()` |

**Scripts**:
| File | Action |
|------|--------|
| `scripts/generate_ts_types.py` | CREATE - Python → TypeScript |
| `scripts/generate_rust_types.py` | CREATE - Python → Rust |

## Appendix A: Component Mapping

| Legacy Component | New Location | Notes |
|-----------------|--------------|-------|
| `AdaptiveAgent.run()` | `Naaru.process(mode=AGENT)` | |
| `AdaptiveAgent._plan()` | `AnalysisWorker` | Harmonic planning |
| `AdaptiveAgent._execute_task()` | `ExecutiveWorker` | Task execution |
| `AdaptiveAgent._validate()` | `ValidationWorker` | Gate checking |
| `AdaptiveAgent._fix()` | `ValidationWorker.fix()` | Auto-fix |
| `RuntimeEngine.execute()` | `SynthesisWorker` | |
| `RuntimeEngine._classify_intent()` | `RoutingWorker` | |
| `RuntimeEngine._inject_context()` | `ContextShard` | |
| `IntentAnalyzer.analyze()` | `RoutingWorker.route()` | |
| `InteractionRouter.route()` | `ExecutiveWorker` | |
| `CognitiveRouter.route()` | `RoutingWorker.route()` | |
| `ToolExecutor.execute()` | `ToolRegionWorker` | |

## Appendix B: Convergence Slot Lifecycle

```
Request Start
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ CONVERGENCE (7 slots active at any time)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  t=0ms   RoutingWorker sets routing:current                 │
│  t=10ms  CompositorShard sets composition:current           │
│  t=20ms  MemoryShard sets memories:relevant                 │
│  t=30ms  ContextShard sets context:lens                     │
│  t=50ms  [Slots ready, model can start]                     │
│                                                             │
│  t=100ms SynthesisWorker reads all slots, generates         │
│                                                             │
│  t=2000ms ExecutiveWorker sets execution:current_task       │
│  t=3000ms ValidationWorker sets validation:result           │
│  t=3100ms ConsolidatorShard sets learnings:pending          │
│                                                             │
│  t=3200ms [Request complete, slots eligible for eviction]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Cleanup & Hardening Benefits

### Code Elimination

| Layer | Files Deleted | Lines Removed |
|-------|--------------------------|-------------------|
| **Python** | | |
| `cli/agent_cmd.py` | Remove after migration | ~200 |
| `cli/interface_cmd.py` | Merge into `naaru_cmd.py` | ~150 |
| `runtime/engine.py` (partial) | Core logic moves to Naaru | ~400 |
| `agent/adaptive.py` (partial) | Tool execution stays, routing moves | ~300 |
| **Rust** | | |
| `interface.rs` | Replace with `naaru.rs` | ~150 |
| `commands.rs` (partial) | Merge into `naaru.rs` | ~100 |
| `dag.rs` (partial) | Convergence-based access | ~80 |
| **Svelte** | | |
| `stores/home.svelte.ts` | Replace with `naaru.svelte.ts` | ~150 |
| Various ad-hoc stores | Consolidate | ~200 |
| **Total** | | **~1,730 lines** |

### Single Source of Truth

**Before**:
```
Intent classification: 3 implementations
- InteractionRouter.classify() (interface/)
- AdaptiveAgent._classify() (agent/)
- RuntimeEngine._route() (runtime/)

Response generation: 3 flows
- IntentAnalyzer.analyze() → generate
- AdaptiveAgent.run() → generate  
- RuntimeEngine.execute() → generate
```

**After**:
```
Intent classification: 1 implementation
- Naaru.RoutingWorker.route()

Response generation: 1 flow
- Naaru.SynthesisWorker.generate()
```

### Type Safety Enforcement

**Before**: Types defined ad-hoc, mismatches between layers.

```typescript
// Svelte: HomeResponse has optional fields
interface HomeResponse {
  route?: string;  // Sometimes undefined
  response?: string;
}
```

```python
# Python: Different definition
class InterfaceOutput:
    route: str  # Required
    content: str  # Named differently
```

**After**: Single source of truth with generation.

```python
# Python: Canonical definition
@dataclass(frozen=True, slots=True)
class ProcessOutput:
    response: str  # Required
    route_type: str  # Required
    confidence: float  # Required
```

```typescript
// Generated: Matches exactly
export interface ProcessOutput {
    response: string;
    route_type: string;
    confidence: number;
}
```

### Error Handling Consolidation

**Before**: Errors handled differently at each layer.

```python
# Agent: Custom AgentError
# Runtime: RuntimeError with status codes
# Interface: InterfaceError with different fields
```

**After**: Unified error model.

```python
@dataclass(frozen=True, slots=True)
class NaaruError:
    code: str  # e.g., "ROUTE_FAILED", "TIMEOUT", "MODEL_ERROR"
    message: str
    recoverable: bool
    context: dict[str, Any] | None = None
```

### Testing Strategy

```python
# tests/test_naaru_integration.py

class TestNaaruUnified:
    """Test entire flow through Naaru."""
    
    @pytest.fixture
    def naaru(self) -> NaaruCoordinator:
        """Create Naaru with mock models."""
        return NaaruCoordinator(
            routing_model=MockModel(),
            synthesis_model=MockModel(),
        )
    
    async def test_conversation_flow(self, naaru):
        """Test: Input → Route → Compose → Generate → Output."""
        input = ProcessInput(content="Hello, how are you?")
        
        events = []
        async for event in naaru.process(input):
            events.append(event)
        
        # Verify event sequence
        event_types = [e.type for e in events]
        assert event_types == [
            "process_start",
            "route_decision",
            "composition_ready",
            "model_start",
            "model_tokens",  # May be multiple
            "model_complete",
            "process_complete",
        ]
        
        # Verify final output
        final = events[-1].data
        assert final["route_type"] == "conversation"
        assert final["confidence"] > 0.8
        assert final["composition"] is not None
    
    async def test_agent_flow(self, naaru):
        """Test: Complex task → Multi-step agent execution."""
        input = ProcessInput(
            content="Build a REST API with user auth",
            mode=ProcessMode.AGENT,
        )
        
        events = []
        async for event in naaru.process(input):
            events.append(event)
        
        # Should have task execution events
        assert any(e.type == "task_start" for e in events)
        assert any(e.type == "task_complete" for e in events)
    
    async def test_error_recovery(self, naaru):
        """Test: Model fails → Graceful error."""
        naaru.synthesis_model = FailingMockModel()
        
        input = ProcessInput(content="test")
        
        with pytest.raises(NaaruError) as exc:
            async for _ in naaru.process(input):
                pass
        
        assert exc.value.code == "MODEL_ERROR"
        assert exc.value.recoverable is True
```

### Migration Validation

```bash
# Validate before/after parity during migration

# 1. Record baseline responses
sunwell interface process -g "hello" --json > baseline.json
sunwell agent run "build api" --json >> baseline.json

# 2. Record new responses
sunwell naaru process "hello" --json > new.json
sunwell naaru process "build api" --mode agent --json >> new.json

# 3. Compare (ignoring timestamps, etc.)
python scripts/compare_outputs.py baseline.json new.json

# Expected: Semantic equivalence, better confidence scores
```

## Success Criteria

| Metric | Before | Target | Verified |
|--------|--------|--------|----------|
| Entry point count | 5+ | **1** | ✅ |
| Python orchestration files | 6 | **3** (naaru/) | ✅ measured |
| Rust command files | 4+ | **1** (naaru.rs) | ✅ |
| Svelte store files | 16 | **1** (naaru.svelte.ts) | ✅ measured |
| Lines of orchestration code | ~7,200 | **~3,200** | ✅ measured |
| Type mismatches across layers | Many | **0** (generated) | Design goal |
| Event systems | 3 | **1** | ✅ |
| Test complexity (integration) | O(n²) | **O(n)** | Design goal |

---

*This RFC establishes Naaru as the single orchestration layer for all Sunwell execution. The unification reduces complexity, eliminates duplication, and enables consistent parallel processing across all entry points.*
