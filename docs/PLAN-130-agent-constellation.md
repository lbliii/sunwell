# Implementation Plan: RFC-130 Agent Constellation

**Status**: Ready for Implementation  
**Created**: 2026-01-24  
**Estimated Duration**: 5-6 weeks  
**No Backwards Compatibility**: Clean integration, no shims

---

## 🎯 Implementation Philosophy

1. **Extend, don't duplicate** — Every feature modifies existing files, not new parallel systems
2. **Wire completely** — No stub implementations, no "TODO: integrate later"
3. **No shims** — Replace old signatures directly; callers adapt
4. **Test at boundaries** — Integration tests prove wiring works

---

## Phase 1: Dynamic Agent Spawning (Week 1)

### Task 1.1: Define Spawn Types
**File**: `src/sunwell/agent/spawn.py` (NEW)

```python
@dataclass(frozen=True, slots=True)
class SpawnRequest:
    """Request from agent to spawn a specialist."""
    parent_id: str
    role: str
    focus: str
    reason: str
    tools: tuple[str, ...] = ()
    context_keys: tuple[str, ...] = ()
    budget_tokens: int = 5_000

@dataclass
class SpecialistState:
    """Tracking state for spawned specialist."""
    id: str
    parent_id: str
    focus: str
    started_at: datetime
    completed_at: datetime | None = None
    result: Any = None

class SpawnDepthExceeded(Exception):
    """Raised when spawn depth limit is reached."""
    pass
```

### Task 1.2: Extend Lens
**File**: `src/sunwell/core/lens.py`

Add to `Lens` dataclass (line ~165):
```python
# Add after skill_sources field
can_spawn: bool = False
"""Whether agent using this lens can spawn specialist sub-agents."""

max_children: int = 3
"""Maximum specialist spawns allowed."""

spawn_budget_tokens: int = 10_000
"""Token budget allocated to spawned specialists."""
```

### Task 1.3: Extend Naaru
**File**: `src/sunwell/naaru/coordinator.py`

Add fields to `Naaru` dataclass (after line ~157):
```python
# Internal spawn tracking
_spawned_specialists: dict[str, SpecialistState] = field(default_factory=dict, init=False)
_spawn_depth: int = field(default=0, init=False)
_max_spawn_depth: int = 3
```

Add methods:
```python
async def spawn_specialist(
    self,
    request: SpawnRequest,
    parent_context: dict[str, Any],
) -> str:
    """Spawn a specialist worker for a focused subtask."""
    # Implementation per RFC
    
async def wait_specialist(self, specialist_id: str) -> Any:
    """Wait for specialist to complete and return result."""
    # Implementation per RFC
```

### Task 1.4: Wire into Agent
**File**: `src/sunwell/agent/core.py`

Modify `_execute_with_gates()` method to check for spawn need:
```python
for task in ready:
    if self._should_spawn_specialist(task):
        spawn_request = self._create_spawn_request(task)
        specialist_id = await self._naaru.spawn_specialist(
            spawn_request,
            parent_context=self._get_context_snapshot(),
        )
        yield specialist_spawned_event(specialist_id, task.id)
        
        specialist_result = await self._naaru.wait_specialist(specialist_id)
        task.integrate_result(specialist_result)
    else:
        # Existing execution code
```

Add helper methods:
```python
def _should_spawn_specialist(self, task: Task) -> bool:
    """Decide if task needs specialist."""

def _create_spawn_request(self, task: Task) -> SpawnRequest:
    """Create spawn request for task."""

def _get_context_snapshot(self) -> dict[str, Any]:
    """Get current context for specialist."""
```

### Task 1.5: Add Events
**File**: `src/sunwell/agent/events.py`

Add to `EventType` enum:
```python
SPECIALIST_SPAWNED = "specialist_spawned"
"""Specialist agent spawned for subtask."""

SPECIALIST_COMPLETED = "specialist_completed"
"""Specialist agent completed its task."""
```

Add event factories:
```python
def specialist_spawned_event(specialist_id: str, task_id: str, ...) -> AgentEvent:
def specialist_completed_event(specialist_id: str, summary: str, ...) -> AgentEvent:
```

### Tests
- `tests/agent/test_spawn.py` — Unit tests for spawn types
- `tests/naaru/test_specialist.py` — Naaru spawn/wait integration
- `tests/agent/test_agent_spawn.py` — Agent spawning E2E

---

## Phase 2: Semantic Checkpoints (Week 2)

### Task 2.1: Add CheckpointPhase Enum
**File**: `src/sunwell/naaru/checkpoint.py`

Add after `FailurePolicy` enum (line ~24):
```python
class CheckpointPhase(Enum):
    """Semantic phases for workflow checkpoints."""
    ORIENT_COMPLETE = "orient_complete"
    EXPLORATION_COMPLETE = "exploration_complete"
    DESIGN_APPROVED = "design_approved"
    IMPLEMENTATION_COMPLETE = "implementation_complete"
    REVIEW_COMPLETE = "review_complete"
    USER_CHECKPOINT = "user_checkpoint"
    TASK_COMPLETE = "task_complete"
```

### Task 2.2: Extend AgentCheckpoint
**File**: `src/sunwell/naaru/checkpoint.py`

Add fields to `AgentCheckpoint` dataclass (after line ~123):
```python
phase: CheckpointPhase = CheckpointPhase.TASK_COMPLETE
"""Current semantic phase."""

phase_summary: str = ""
"""Human-readable summary of what was accomplished."""

user_decisions: tuple[str, ...] = ()
"""User decisions recorded during execution."""

spawned_specialists: tuple[str, ...] = ()
"""IDs of specialists spawned (for constellation tracking)."""

memory_snapshot_path: str | None = None
"""Path to memory snapshot for memory-informed resume."""
```

Add class method:
```python
@classmethod
def find_latest_for_goal(cls, workspace: Path, goal: str) -> AgentCheckpoint | None:
    """Find the most recent checkpoint for a specific goal."""
```

Update `to_dict()` and `from_dict()` to include new fields.

### Task 2.3: Wire into Agent
**File**: `src/sunwell/agent/core.py`

Add at start of `run()` method:
```python
# Check for existing checkpoint to resume
existing_cp = AgentCheckpoint.find_latest_for_goal(session.cwd, session.goal)
if existing_cp:
    yield checkpoint_found_event(existing_cp.phase, existing_cp.checkpoint_at)
    if session.options.auto_resume:
        self._restore_from_checkpoint(existing_cp)
        start_phase = existing_cp.get_resume_phase()
```

Add `_save_checkpoint()` method:
```python
def _save_checkpoint(self, phase: CheckpointPhase, summary: str) -> None:
    """Save checkpoint with semantic phase."""
```

Insert checkpoint saves after each phase (ORIENT, PLAN, each task, etc.).

### Task 2.4: Extend Resume CLI
**File**: `src/sunwell/cli/agent/resume.py`

Add options:
```python
@click.option("--phase", "-p", default=None,
              type=click.Choice([p.value for p in CheckpointPhase]),
              help="Resume from specific phase")
@click.option("--goal", "-g", default=None, help="Resume latest checkpoint for goal")
```

Update resume logic to support goal-based and phase-based resume.

### Task 2.5: Add Events
**File**: `src/sunwell/agent/events.py`

Add to `EventType`:
```python
CHECKPOINT_FOUND = "checkpoint_found"
"""Found existing checkpoint for goal."""

CHECKPOINT_SAVED = "checkpoint_saved"
"""Semantic checkpoint saved."""

PHASE_COMPLETE = "phase_complete"
"""Agent completed a semantic phase."""
```

### Tests
- `tests/naaru/test_checkpoint_phase.py` — CheckpointPhase serialization
- `tests/agent/test_checkpoint_resume.py` — Goal-based resume
- `tests/cli/test_resume_options.py` — CLI --goal/--phase tests

---

## Phase 3: Adaptive Guards (Week 3)

### Task 3.1: Extend TrustZone
**File**: `src/sunwell/guardrails/types.py`

Add fields to `TrustZone` (after line ~227):
```python
learn_from_violations: bool = False
"""Track violations to suggest pattern refinements."""

violation_history_path: str | None = None
"""Path to violation log (JSON lines)."""

false_positive_threshold: int = 3
"""After N false positives, suggest pattern refinement."""

override_threshold: int = 5
"""After N user overrides, suggest adding exception."""
```

### Task 3.2: Add Violation and Evolution Types
**File**: `src/sunwell/guardrails/types.py`

Add after `TrustZone`:
```python
@dataclass
class GuardViolation:
    """Record of a guard triggering."""
    guard_id: str
    timestamp: datetime
    context: str
    action_taken: str  # "blocked", "warned", "allowed"
    user_feedback: str | None = None  # "false_positive", "correct", None

@dataclass(frozen=True, slots=True)
class GuardEvolution:
    """Suggested improvement to a guard."""
    guard_id: str
    evolution_type: str  # "refine_pattern", "add_exception", "relax_risk"
    reason: str
    suggested_change: dict[str, Any]
    confidence: float
```

### Task 3.3: Extend SmartActionClassifier
**File**: `src/sunwell/guardrails/classifier.py`

Add to `__init__`:
```python
violation_store_path: Path | None = None,
enable_learning: bool = True,
```

Add fields:
```python
self._violation_store_path = violation_store_path
self._enable_learning = enable_learning
self._violations: list[GuardViolation] = []
```

Add methods:
```python
def record_violation(
    self,
    classification: ActionClassification,
    context: str,
    action_taken: str,
) -> None:
    """Record a violation for learning."""

def record_user_feedback(self, violation_index: int, feedback: str) -> None:
    """Record user feedback on a violation."""

def suggest_evolutions(self) -> list[GuardEvolution]:
    """Analyze violations and suggest guard improvements."""

def _load_violations(self) -> None:
    """Load violations from disk."""

def _save_violations(self) -> None:
    """Save violations to disk."""
```

### Task 3.4: Add check_autonomous_action to GuardrailSystem
**File**: `src/sunwell/guardrails/system.py`

Add method:
```python
async def check_autonomous_action(
    self,
    action: Action,
    session_context: dict[str, Any],
) -> AutonomousActionResult:
    """Check if action is safe for autonomous execution."""
```

Add result type:
```python
@dataclass(frozen=True, slots=True)
class AutonomousActionResult:
    allowed: bool
    reason: str
    escalation_required: bool = False
```

### Task 3.5: Add Guard CLI Commands
**File**: `src/sunwell/cli/guardrails_cmd.py`

Add commands:
```python
@guardrails.command("evolve")
def evolve_guards():
    """Apply suggested guard improvements."""

@guardrails.command("feedback")
@click.argument("violation_id")
@click.argument("feedback", type=click.Choice(["false_positive", "correct"]))
def guard_feedback(violation_id: str, feedback: str):
    """Record feedback on a guard violation."""

@guardrails.command("stats")
def guard_stats():
    """Show violation statistics."""
```

### Tests
- `tests/guardrails/test_violation_learning.py` — Violation recording
- `tests/guardrails/test_guard_evolution.py` — Evolution suggestions
- `tests/guardrails/test_autonomous_check.py` — Autonomous action checking

---

## Phase 4: Memory-Informed Prefetch (Week 4)

### Task 4.1: Extend analyze_briefing_for_prefetch
**File**: `src/sunwell/prefetch/dispatcher.py`

Update function signature:
```python
async def analyze_briefing_for_prefetch(
    briefing: Briefing,
    router_model: str = "gpt-4o-mini",
    memory: PersistentMemory | None = None,  # NEW
) -> PrefetchPlan:
```

Add memory-based hint extraction:
```python
if memory:
    # Similar goals accessed these files
    similar_context = await memory.get_relevant(briefing.goal)
    for learning in similar_context.learnings[:5]:
        if learning.files_accessed:
            hints.extend(learning.files_accessed[:5])
    
    # Dead ends: DON'T prefetch files from failed approaches
    for dead_end in similar_context.dead_ends:
        if dead_end.file_path in hints:
            hints.remove(dead_end.file_path)
```

### Task 4.2: Add find_similar_goals to PersistentMemory
**File**: `src/sunwell/memory/persistent.py`

Add method:
```python
async def find_similar_goals(
    self,
    goal: str,
    limit: int = 5,
) -> list[GoalMemory]:
    """Find past goals similar to the current one."""
```

Add to module:
```python
@dataclass(frozen=True, slots=True)
class GoalMemory:
    """Memory of a past goal execution."""
    goal: str
    files_accessed: tuple[str, ...]
    approach_taken: str
    outcome: str  # "success", "partial", "failed"
    duration_seconds: float
```

Add method for recording goal completion:
```python
async def record_goal_completion(
    self,
    goal: str,
    outcome: str,
    files_accessed: list[str],
    approach: str,
    duration: float,
) -> None:
    """Record goal completion for future prefetch hints."""
```

### Task 4.3: Wire into Agent
**File**: `src/sunwell/agent/core.py`

Add at start of `run()`:
```python
# PHASE 0: PREFETCH (runs in background)
prefetch_task = asyncio.create_task(
    self._run_prefetch(session.briefing, memory)
)
yield prefetch_start_event()
```

Add after orient phase:
```python
# Wait for prefetch before exploration
try:
    prefetched = await asyncio.wait_for(prefetch_task, timeout=PREFETCH_TIMEOUT)
    yield prefetch_complete_event(len(prefetched.files))
    self._context.update(prefetched.to_context_dict())
except asyncio.TimeoutError:
    yield prefetch_timeout_event()
```

Add helper:
```python
async def _run_prefetch(
    self,
    briefing: Briefing | None,
    memory: PersistentMemory,
) -> PrefetchedContext:
    """Run memory-informed prefetch."""
```

### Task 4.4: Add Memory CLI Commands
**File**: `src/sunwell/cli/intel_cmd.py` (or new `memory_cmd.py`)

Add commands:
```python
@memory.command("similar")
@click.argument("goal")
def memory_similar(goal: str):
    """Find similar past goals."""

@memory.command("patterns")
def memory_patterns():
    """Show access patterns."""
```

### Tests
- `tests/prefetch/test_memory_hints.py` — Memory-informed prefetch
- `tests/memory/test_goal_similarity.py` — Goal similarity search
- `tests/agent/test_prefetch_integration.py` — Agent prefetch wiring

---

## Phase 5: Integration & CLI (Week 5)

### Task 5.1: Create autonomous_goal Function
**File**: `src/sunwell/agent/autonomous.py` (NEW)

```python
async def autonomous_goal(
    goal: str,
    workspace: Path,
    trust_level: TrustLevel = TrustLevel.GUARDED,
) -> AutonomousResult:
    """Run a goal with full autonomy support.
    
    Combines all four pillars:
    1. PREFETCH — Memory-informed context loading (Pillar 4)
    2. CHECKPOINT — Resume from crash (Pillar 2)
    3. GUARDS — Safe execution (Pillar 3)
    4. SPAWNING — Delegate complex subtasks (Pillar 1)
    """
    # Implementation per RFC
```

### Task 5.2: Add Autonomous CLI
**File**: `src/sunwell/cli/main.py`

Add command:
```python
@click.command()
@click.argument("goal")
@click.option("--trust", type=click.Choice(["conservative", "guarded", "supervised", "full"]),
              default="guarded")
@click.option("--timeout", type=int, default=None, help="Max duration in minutes")
@click.option("--dry-run", is_flag=True, help="Plan only, don't execute")
def autonomous(goal: str, trust: str, timeout: int | None, dry_run: bool):
    """Run a goal with full autonomy support."""
```

### Task 5.3: Wire All Events
**File**: Various

Ensure all new events are:
1. Emitted at correct points in code
2. Handled in CLI renderers
3. Forwarded to Studio via server bridge

### Task 5.4: Update RunOptions
**File**: `src/sunwell/agent/request.py`

Add fields:
```python
auto_resume: bool = False
"""Whether to auto-resume from checkpoint without prompt."""

enable_spawning: bool = True
"""Whether to allow specialist spawning."""

checkpoint_phases: bool = True
"""Whether to save checkpoints at phase boundaries."""
```

### Tests
- `tests/agent/test_autonomous_workflow.py` — Full autonomous E2E
- `tests/cli/test_autonomous_command.py` — CLI integration
- `tests/integration/test_four_pillars.py` — All pillars working together

---

## Phase 6: Benchmarking & Validation (Week 6)

### Task 6.1: Create Benchmark Tasks
**File**: `benchmark/tasks/autonomous/`

Create tasks that exercise:
- Long-running sessions (>30 min)
- Checkpoint recovery scenarios
- Guard learning over multiple runs
- Specialist spawning for complex goals

### Task 6.2: Measure Metrics
- Autonomous session duration
- Checkpoint recovery success rate
- Guard false positive rate after learning
- Prefetch cache hit rate
- Specialist spawn rate

### Task 6.3: Claude Code Comparison
Run same tasks on Claude Code, compare:
- Time to completion
- Quality of output
- Human intervention required
- Cost

---

## File Change Summary

| File | Change Type | Lines Changed |
|------|-------------|---------------|
| `agent/spawn.py` | NEW | ~50 |
| `core/lens.py` | MODIFY | +15 |
| `naaru/coordinator.py` | MODIFY | +80 |
| `naaru/checkpoint.py` | MODIFY | +60 |
| `agent/core.py` | MODIFY | +150 |
| `agent/events.py` | MODIFY | +80 |
| `guardrails/types.py` | MODIFY | +50 |
| `guardrails/classifier.py` | MODIFY | +100 |
| `guardrails/system.py` | MODIFY | +40 |
| `prefetch/dispatcher.py` | MODIFY | +40 |
| `memory/persistent.py` | MODIFY | +60 |
| `agent/request.py` | MODIFY | +10 |
| `agent/autonomous.py` | NEW | ~100 |
| `cli/agent/resume.py` | MODIFY | +50 |
| `cli/guardrails_cmd.py` | MODIFY | +60 |
| `cli/main.py` | MODIFY | +30 |

**Total**: ~975 lines of production code

---

## Integration Checklist

### Pillar 1: Spawning
- [ ] `Lens.can_spawn` wired to agent decision
- [ ] `Naaru.spawn_specialist()` uses existing worker pool
- [ ] `Agent.run()` yields spawn events
- [ ] Events render in CLI and Studio

### Pillar 2: Checkpoints
- [ ] `CheckpointPhase` serializes correctly
- [ ] `AgentCheckpoint.find_latest_for_goal()` searches correctly
- [ ] `Agent.run()` auto-resumes when checkpoint exists
- [ ] `sunwell resume --goal` works E2E

### Pillar 3: Guards
- [ ] Violations recorded to JSON lines file
- [ ] `suggest_evolutions()` returns actionable suggestions
- [ ] `check_autonomous_action()` called before every autonomous action
- [ ] `sunwell guard evolve` applies suggestions

### Pillar 4: Memory Prefetch
- [ ] `analyze_briefing_for_prefetch()` accepts memory parameter
- [ ] Similar goals influence prefetch hints
- [ ] Dead ends excluded from prefetch
- [ ] Prefetch runs in parallel with orient

### Integration
- [ ] `autonomous_goal()` combines all four pillars
- [ ] `sunwell autonomous` command works E2E
- [ ] All events emit and render correctly
- [ ] Benchmark shows improvement over Claude Code

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Spawn budget allocation | Parent keeps 80%, specialist gets 20% per spawn |
| Checkpoint retention | Keep last 5 per goal, prune weekly |
| Guard evolution approval | Auto-apply for SAFE zones, require approval for others |
| Memory privacy | Filter sensitive patterns before storing in GoalMemory |

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Autonomous session duration | >2 hours | Benchmark suite |
| Checkpoint recovery rate | 100% | Unit tests |
| Guard false positive rate | <5% after 10 sessions | Benchmark |
| Prefetch cache hit rate | >70% | Instrumentation |
| Specialist spawn rate | ~20% of complex goals | Benchmark |
