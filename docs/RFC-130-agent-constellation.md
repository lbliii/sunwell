# RFC-130: Agent Constellation Architecture

**RFC Status**: Draft v2 (Revised)  
**Author**: Architecture Team  
**Created**: 2026-01-24  
**Revised**: 2026-01-24  
**Leapfrog Target**: Claude Code

---

## Executive Summary

This RFC proposes **Agent Constellation** — extending Sunwell's existing Agent, checkpoint, guardrail, and prefetch systems to enable **fully autonomous multi-agent workflows** that surpass Claude Code's capabilities.

**The thesis**: Sunwell already has the infrastructure. This RFC wires it together for autonomy:

1. **Dynamic agent spawning** — Extend `Agent` + `Naaru` workers to spawn specialists on-demand
2. **Semantic checkpoints** — Extend `AgentCheckpoint` with phase metadata for crash-safe autonomy
3. **Adaptive guards** — Extend `GuardrailSystem` with learning for unsupervised safety
4. **Memory-informed prefetch** — Extend `prefetch/dispatcher.py` with `PersistentMemory` integration

**Result**: Autonomous agents that run for hours without supervision, recover from crashes, and learn from mistakes.

---

## 🎯 Goal: Enable True Autonomy

Every feature in this RFC serves one purpose: **let the agent work autonomously without human babysitting**.

| Autonomy Blocker | Solution | Enables |
|------------------|----------|---------|
| Agent gets stuck on complex tasks | Dynamic spawning | Agent spawns specialists when needed |
| Crash loses all progress | Semantic checkpoints | Resume exactly where you left off |
| Agent does something dangerous | Adaptive guards | Safe unsupervised operation |
| Cold start is slow | Memory-informed prefetch | Instant context on similar goals |
| No learning across sessions | Memory integration | Agent improves over time |

---

## Existing Systems to Extend (Dogfooding)

**This RFC does NOT create parallel systems.** Every feature extends existing code:

| Pillar | Extends | File(s) |
|--------|---------|---------|
| Dynamic Spawning | `Agent`, `Naaru`, `Lens` | `agent/core.py`, `naaru/coordinator.py`, `core/lens.py` |
| Semantic Checkpoints | `AgentCheckpoint` | `naaru/checkpoint.py`, `cli/agent/resume.py` |
| Adaptive Guards | `GuardrailSystem`, `TrustZone`, `SmartActionClassifier` | `guardrails/types.py`, `guardrails/classifier.py` |
| Memory Prefetch | `prefetch/dispatcher.py`, `PersistentMemory` | `prefetch/dispatcher.py`, `memory/persistent.py` |

---

## Competitive Analysis: What We're Beating

| Capability | Claude Code | Sunwell (Current) | **Sunwell (This RFC)** |
|------------|-------------|-------------------|------------------------|
| Agent parallelism | 2-3 hardcoded | Naaru workers (8 parallel) | **+ Dynamic specialist spawning** |
| Checkpoints | None | `AgentCheckpoint` (task-based) | **+ Semantic phase metadata** |
| Guards | Static markdown patterns | `GuardrailSystem` + `SmartActionClassifier` | **+ Adaptive learning** |
| Context loading | Reactive | `prefetch/dispatcher.py` (briefing-driven) | **+ Memory-informed hints** |
| Memory | None | `PersistentMemory` (5 stores) | **+ Autonomy integration** |
| Cost | API $$$ | $0 local | **$0 local** |

---

## The Four Pillars

### Pillar 1: Dynamic Agent Spawning

**🎯 Autonomy Enabler**: Agent can request help instead of getting stuck or producing poor results.

Claude Code launches 2-3 agents with hardcoded roles. We extend `Agent` to spawn specialists dynamically based on task complexity.

```
                          ┌─────────────────┐
                          │      Agent      │  ← Existing Agent.run()
                          │   (THE brain)   │
                          └────────┬────────┘
                                   │ spawns via Naaru
              ┌────────────────────┼────────────────────┐
              │                    │                    │
       ┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐
       │  Explorer   │      │  Architect  │      │  Reviewer   │
       │  (Lens)     │      │  (Lens)     │      │  (Lens)     │
       └──────┬──────┘      └──────┬──────┘      └─────────────┘
              │ can spawn           │ can spawn
       ┌──────▼──────┐      ┌──────▼──────┐
       │ Specialist  │      │ Specialist  │
       │ (on-demand) │      │ (on-demand) │
       └─────────────┘      └─────────────┘
```

#### Extend Existing: `core/lens.py`

Add spawn capability to the existing `Lens` type:

```python
# EXTEND: core/lens.py - Add spawn fields to existing Lens

@dataclass(frozen=True, slots=True)
class Lens:
    """Domain expertise injection (existing fields + new spawn capability)."""
    
    # Existing fields (unchanged)
    name: str
    description: str
    heuristics: tuple[Heuristic, ...]
    personas: tuple[Persona, ...]
    tools: tuple[str, ...] = ()
    
    # NEW: Spawn capability for autonomy
    can_spawn: bool = False
    """Whether agent using this lens can spawn specialist sub-agents."""
    
    max_children: int = 3
    """Maximum specialist spawns allowed."""
    
    spawn_budget_tokens: int = 10_000
    """Token budget allocated to spawned specialists."""
```

**🎯 Autonomy Wire-up**: When `Agent.run()` encounters a complex subtask, it checks `lens.can_spawn` and creates a `SpawnRequest` instead of struggling alone.

#### Extend Existing: `naaru/coordinator.py`

Add spawn support to existing `Naaru`:

```python
# EXTEND: naaru/coordinator.py - Add spawn_specialist method

@dataclass
class Naaru:
    """Internal coordination layer (existing + spawn support)."""
    
    # Existing fields unchanged...
    
    # NEW: Track spawned specialists for autonomy
    _spawned_specialists: dict[str, SpecialistState] = field(default_factory=dict, init=False)
    _spawn_depth: int = field(default=0, init=False)
    _max_spawn_depth: int = 3
    
    async def spawn_specialist(
        self,
        request: SpawnRequest,
        parent_context: dict[str, Any],
    ) -> str:
        """Spawn a specialist worker for a focused subtask.
        
        🎯 AUTONOMY: Enables agent to delegate complex subtasks
        instead of producing poor results or getting stuck.
        
        Uses existing HarmonicSynthesisWorker pool — no new infrastructure.
        """
        if self._spawn_depth >= self._max_spawn_depth:
            raise SpawnDepthExceeded(f"Max depth {self._max_spawn_depth} reached")
        
        specialist_id = f"specialist-{request.role}-{_generate_id()}"
        
        # Use existing worker pool
        worker = self._synthesis_workers[self._spawn_depth % len(self._synthesis_workers)]
        
        # Create specialist lens from request
        specialist_lens = Lens(
            name=f"Specialist: {request.focus}",
            description=request.reason,
            heuristics=(),
            personas=(),
            tools=request.tools,
            can_spawn=False,  # Specialists don't spawn (prevent infinite recursion)
        )
        
        # Track for observability
        self._spawned_specialists[specialist_id] = SpecialistState(
            id=specialist_id,
            parent_id=request.parent_id,
            focus=request.focus,
            started_at=datetime.now(),
        )
        
        # Emit event for UI/logging
        await self._event_emitter.emit(SpecialistSpawned(
            specialist_id=specialist_id,
            parent_id=request.parent_id,
            focus=request.focus,
        ))
        
        return specialist_id
```

#### Extend Existing: `agent/core.py`

Wire spawning into Agent's execution loop:

```python
# EXTEND: agent/core.py - Add spawn handling to Agent.run()

async def run(
    self,
    session: SessionContext,
    memory: PersistentMemory,
) -> AsyncIterator[AgentEvent]:
    """Execute goal with explicit context and memory.
    
    Pipeline (existing + spawn support):
    1. ORIENT   → Load memory context
    2. SIGNAL   → Analyze goal complexity
    3. LENS     → Select expertise  
    4. PLAN     → Decompose into task graph
    5. EXECUTE  → Run tasks (+ SPAWN SPECIALISTS if needed)  ← NEW
    6. VALIDATE → Check gates
    7. FIX      → Auto-fix failures
    8. LEARN    → Persist to memory
    """
    # ... existing phases 1-4 ...
    
    # ─── PHASE 5: EXECUTE (with spawn support) ───
    for task in self._task_graph.get_ready_tasks():
        # Check if task needs specialist
        if self._should_spawn_specialist(task):
            # 🎯 AUTONOMY: Delegate instead of struggling
            spawn_request = self._create_spawn_request(task)
            specialist_id = await self._naaru.spawn_specialist(
                spawn_request,
                parent_context=self._get_context_snapshot(),
            )
            yield specialist_spawned_event(specialist_id, task.id)
            
            # Wait for specialist result
            specialist_result = await self._naaru.wait_specialist(specialist_id)
            task.integrate_result(specialist_result)
        else:
            # Normal execution (existing code)
            await self._execute_task(task)
    
    # ... existing phases 6-8 ...

def _should_spawn_specialist(self, task: Task) -> bool:
    """Decide if task needs specialist.
    
    🎯 AUTONOMY: Proactively spawn instead of producing poor output.
    """
    if not self.lens or not self.lens.can_spawn:
        return False
    
    # Spawn if task complexity exceeds threshold
    if task.estimated_complexity > 0.8:
        return True
    
    # Spawn if task requires tools not in current lens
    required_tools = set(task.required_tools)
    available_tools = set(self.lens.tools)
    if not required_tools.issubset(available_tools):
        return True
    
    return False
```

#### New Types (Minimal)

```python
# NEW: agent/spawn.py - Spawn-related types only

@dataclass(frozen=True, slots=True)
class SpawnRequest:
    """Request from agent to spawn a specialist.
    
    🎯 AUTONOMY: Explicit delegation signal for complex subtasks.
    """
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
```

---

### Pillar 2: Semantic Checkpoints

**🎯 Autonomy Enabler**: Agent can run for hours, crash, and resume exactly where it left off — no lost work.

Claude Code has no checkpoint system. Sunwell already has `AgentCheckpoint` — we extend it with semantic phase metadata.

#### Extend Existing: `naaru/checkpoint.py`

```python
# EXTEND: naaru/checkpoint.py - Add semantic fields to AgentCheckpoint

class CheckpointPhase(Enum):
    """Semantic phases for workflow checkpoints.
    
    🎯 AUTONOMY: Resume from meaningful points, not arbitrary task IDs.
    """
    ORIENT_COMPLETE = "orient_complete"        # Memory loaded
    EXPLORATION_COMPLETE = "exploration_complete"  # Codebase understood
    DESIGN_APPROVED = "design_approved"        # User approved approach
    IMPLEMENTATION_COMPLETE = "implementation_complete"  # Code written
    REVIEW_COMPLETE = "review_complete"        # Quality checked
    
    # User-initiated
    USER_CHECKPOINT = "user_checkpoint"
    
    # Automatic (existing)
    TASK_COMPLETE = "task_complete"

@dataclass
class AgentCheckpoint:
    """Saved state for resuming agent execution.
    
    🎯 AUTONOMY: Crash recovery enables long-running autonomous sessions.
    
    Checkpoints are saved (existing behavior):
    - Every 60 seconds during execution
    - After each task completes
    - On timeout or graceful shutdown
    
    NEW: Also saved at semantic phase boundaries.
    """
    
    # Existing fields (unchanged)
    goal: str
    started_at: datetime = field(default_factory=datetime.now)
    checkpoint_at: datetime = field(default_factory=datetime.now)
    tasks: list[Task] = field(default_factory=list)
    completed_ids: set[str] = field(default_factory=set)
    artifacts: list[Path] = field(default_factory=list)
    working_directory: str = "."
    context: dict[str, Any] = field(default_factory=dict)
    execution_config: TaskExecutionConfig = field(default_factory=TaskExecutionConfig)
    parallel_config: ParallelConfig = field(default_factory=ParallelConfig)
    
    # NEW: Semantic phase tracking for autonomy
    phase: CheckpointPhase = CheckpointPhase.TASK_COMPLETE
    """Current semantic phase (enables phase-based resume)."""
    
    phase_summary: str = ""
    """Human-readable summary of what was accomplished."""
    
    user_decisions: tuple[str, ...] = ()
    """User decisions recorded (e.g., 'Approved approach: minimal')."""
    
    spawned_specialists: tuple[str, ...] = ()
    """IDs of specialists spawned (for constellation tracking)."""
    
    memory_snapshot_path: str | None = None
    """Path to memory snapshot (for memory-informed resume)."""
    
    @classmethod
    def find_latest_for_goal(cls, workspace: Path, goal: str) -> AgentCheckpoint | None:
        """Find the most recent checkpoint for a specific goal.
        
        🎯 AUTONOMY: Resume same goal after crash/restart.
        """
        checkpoint_dir = workspace / ".sunwell" / "checkpoints"
        if not checkpoint_dir.exists():
            return None
        
        matching = []
        for path in checkpoint_dir.glob("*.json"):
            try:
                cp = cls.load(path)
                if cp.goal == goal:
                    matching.append(cp)
            except Exception:
                continue
        
        if not matching:
            return None
        
        return max(matching, key=lambda c: c.checkpoint_at)
    
    def get_resume_phase(self) -> CheckpointPhase:
        """Get the phase to resume from.
        
        🎯 AUTONOMY: Skip completed phases on resume.
        """
        return self.phase
```

#### Extend Existing: `agent/core.py`

Wire checkpoint saving into Agent phases:

```python
# EXTEND: agent/core.py - Add phase checkpoints to Agent.run()

async def run(
    self,
    session: SessionContext,
    memory: PersistentMemory,
) -> AsyncIterator[AgentEvent]:
    """Execute goal with semantic checkpoints.
    
    🎯 AUTONOMY: Checkpoint at each phase boundary for crash recovery.
    """
    
    # Check for existing checkpoint to resume
    existing_cp = AgentCheckpoint.find_latest_for_goal(session.cwd, session.goal)
    if existing_cp:
        yield checkpoint_found_event(existing_cp.phase, existing_cp.checkpoint_at)
        if session.options.auto_resume:
            # 🎯 AUTONOMY: Auto-resume without user prompt
            self._restore_from_checkpoint(existing_cp)
            start_phase = existing_cp.get_resume_phase()
        else:
            # Interactive: ask user
            start_phase = CheckpointPhase.ORIENT_COMPLETE  # Start fresh
    else:
        start_phase = CheckpointPhase.ORIENT_COMPLETE
    
    # ─── PHASE 1: ORIENT ───
    if start_phase <= CheckpointPhase.ORIENT_COMPLETE:
        memory_ctx = await memory.get_relevant(session.goal)
        yield orient_event(...)
        
        # 🎯 AUTONOMY: Checkpoint after orient
        self._save_checkpoint(
            phase=CheckpointPhase.ORIENT_COMPLETE,
            summary=f"Loaded {len(memory_ctx.learnings)} learnings, {len(memory_ctx.constraints)} constraints",
        )
    
    # ─── PHASE 2-3: SIGNAL + LENS ───
    # ... (checkpoint after each) ...
    
    # ─── PHASE 4: PLAN ───
    if start_phase <= CheckpointPhase.EXPLORATION_COMPLETE:
        # ... planning ...
        
        # 🎯 AUTONOMY: Checkpoint with task graph
        self._save_checkpoint(
            phase=CheckpointPhase.EXPLORATION_COMPLETE,
            summary=f"Created {len(self._task_graph.tasks)} tasks",
        )
    
    # ─── PHASE 5: EXECUTE ───
    if start_phase <= CheckpointPhase.IMPLEMENTATION_COMPLETE:
        for task in self._task_graph.get_ready_tasks():
            await self._execute_task(task)
            
            # 🎯 AUTONOMY: Checkpoint after each task (existing behavior, now with phase)
            self._save_checkpoint(
                phase=CheckpointPhase.TASK_COMPLETE,
                summary=f"Completed: {task.description}",
            )
        
        self._save_checkpoint(
            phase=CheckpointPhase.IMPLEMENTATION_COMPLETE,
            summary=f"All {len(self._task_graph.completed_ids)} tasks complete",
        )

def _save_checkpoint(self, phase: CheckpointPhase, summary: str) -> None:
    """Save checkpoint with semantic phase.
    
    🎯 AUTONOMY: Enable phase-based resume for long sessions.
    """
    cp = AgentCheckpoint(
        goal=self._current_goal,
        phase=phase,
        phase_summary=summary,
        tasks=list(self._task_graph.tasks),
        completed_ids=self._task_graph.completed_ids.copy(),
        artifacts=[str(a) for a in self._artifacts],
        user_decisions=tuple(self._user_decisions),
        spawned_specialists=tuple(self._spawned_specialist_ids),
        working_directory=str(self.cwd),
        context=self._get_context_snapshot(),
    )
    
    checkpoint_path = self.cwd / ".sunwell" / "checkpoints"
    cp.save(checkpoint_path / f"{phase.value}-{_generate_id()}.json")
```

#### Extend Existing: `cli/agent/resume.py`

```python
# EXTEND: cli/agent/resume.py - Add phase-based resume

@click.command()
@click.option("--checkpoint", "-c", default=None, help="Path to checkpoint file")
@click.option("--phase", "-p", default=None, 
              type=click.Choice([p.value for p in CheckpointPhase]),
              help="Resume from specific phase (NEW)")
@click.option("--goal", "-g", default=None, help="Resume latest checkpoint for goal (NEW)")
def resume(checkpoint: str | None, phase: str | None, goal: str | None, ...) -> None:
    """Resume agent from checkpoint.
    
    🎯 AUTONOMY: Multiple resume strategies for different scenarios.
    
    Examples:
        sunwell resume                           # Latest checkpoint
        sunwell resume --goal "Add OAuth"        # Latest for specific goal
        sunwell resume --phase design_approved   # From specific phase
    """
    # NEW: Goal-based resume
    if goal:
        cp = AgentCheckpoint.find_latest_for_goal(Path.cwd(), goal)
        if not cp:
            console.print(f"[red]No checkpoint found for goal: {goal}[/red]")
            return
        console.print(f"[green]Found checkpoint: {cp.phase.value}[/green]")
        console.print(f"   Summary: {cp.phase_summary}")
    
    # ... existing resume logic ...
```

---

### Pillar 3: Adaptive Guards

**🎯 Autonomy Enabler**: Agent can run unsupervised because guards prevent dangerous actions AND learn from false positives.

Claude Code's hookify uses static markdown patterns. Sunwell already has `GuardrailSystem` — we extend it with adaptive learning.

#### Extend Existing: `guardrails/types.py`

```python
# EXTEND: guardrails/types.py - Add learning fields to TrustZone

@dataclass(frozen=True, slots=True)
class TrustZone:
    """A path pattern with associated trust level.
    
    🎯 AUTONOMY: Defines where agent can operate unsupervised.
    """
    
    # Existing fields (unchanged)
    pattern: str
    risk_override: ActionRisk | None = None
    allowed_in_autonomous: bool = True
    reason: str = ""
    
    # NEW: Adaptive learning for autonomy
    learn_from_violations: bool = False
    """Track violations to suggest pattern refinements."""
    
    violation_history_path: str | None = None
    """Path to violation log (JSON lines)."""
    
    false_positive_threshold: int = 3
    """After N false positives, suggest pattern refinement."""
    
    override_threshold: int = 5
    """After N user overrides, suggest adding exception."""

@dataclass
class GuardViolation:
    """Record of a guard triggering.
    
    🎯 AUTONOMY: Learn from violations to reduce false positives.
    """
    guard_id: str
    timestamp: datetime
    context: str
    action_taken: str  # "blocked", "warned", "allowed"
    user_feedback: str | None = None  # "false_positive", "correct", None
    
@dataclass
class GuardEvolution:
    """Suggested improvement to a guard.
    
    🎯 AUTONOMY: Guards self-improve over time.
    """
    guard_id: str
    evolution_type: str  # "refine_pattern", "add_exception", "relax_risk"
    reason: str
    suggested_change: dict[str, Any]
    confidence: float
```

#### Extend Existing: `guardrails/classifier.py`

```python
# EXTEND: guardrails/classifier.py - Add learning to SmartActionClassifier

class SmartActionClassifier(ActionClassifier):
    """LLM-powered action classifier with adaptive learning.
    
    🎯 AUTONOMY: Learns from violations to reduce false positives,
    enabling longer unsupervised sessions.
    """
    
    def __init__(
        self,
        taxonomy: ActionTaxonomy,
        model: Any = None,
        # NEW: Learning configuration
        violation_store_path: Path | None = None,
        enable_learning: bool = True,
    ) -> None:
        super().__init__(taxonomy)
        self._model = model
        self._violation_store_path = violation_store_path
        self._enable_learning = enable_learning
        self._violations: list[GuardViolation] = []
        
        if violation_store_path and violation_store_path.exists():
            self._load_violations()
    
    def record_violation(
        self,
        classification: ActionClassification,
        context: str,
        action_taken: str,
    ) -> None:
        """Record a violation for learning.
        
        🎯 AUTONOMY: Builds history for pattern refinement.
        """
        if not self._enable_learning:
            return
        
        violation = GuardViolation(
            guard_id=classification.blocking_rule or "unknown",
            timestamp=datetime.now(),
            context=context,
            action_taken=action_taken,
        )
        self._violations.append(violation)
        self._save_violations()
    
    def record_user_feedback(self, violation_index: int, feedback: str) -> None:
        """Record user feedback on a violation.
        
        🎯 AUTONOMY: User feedback enables guard evolution.
        """
        if 0 <= violation_index < len(self._violations):
            # Violations are immutable, so we need to rebuild
            old = self._violations[violation_index]
            self._violations[violation_index] = GuardViolation(
                guard_id=old.guard_id,
                timestamp=old.timestamp,
                context=old.context,
                action_taken=old.action_taken,
                user_feedback=feedback,
            )
            self._save_violations()
    
    def suggest_evolutions(self) -> list[GuardEvolution]:
        """Analyze violations and suggest guard improvements.
        
        🎯 AUTONOMY: Reduces false positives over time,
        enabling longer autonomous sessions.
        """
        evolutions: list[GuardEvolution] = []
        
        # Group violations by guard
        by_guard: dict[str, list[GuardViolation]] = {}
        for v in self._violations:
            by_guard.setdefault(v.guard_id, []).append(v)
        
        for guard_id, violations in by_guard.items():
            # Check for false positive pattern
            false_positives = [v for v in violations if v.user_feedback == "false_positive"]
            if len(false_positives) >= 3:
                evolutions.append(GuardEvolution(
                    guard_id=guard_id,
                    evolution_type="refine_pattern",
                    reason=f"{len(false_positives)} false positives detected",
                    suggested_change=self._generate_refined_pattern(false_positives),
                    confidence=0.7,
                ))
            
            # Check for frequent overrides
            overrides = [v for v in violations if v.action_taken == "allowed"]
            if len(overrides) >= 5:
                evolutions.append(GuardEvolution(
                    guard_id=guard_id,
                    evolution_type="add_exception",
                    reason=f"{len(overrides)} user overrides",
                    suggested_change=self._generate_exception(overrides),
                    confidence=0.6,
                ))
        
        return evolutions
```

#### Extend Existing: `guardrails/system.py`

```python
# EXTEND: guardrails/system.py - Add autonomy checks

class GuardrailSystem:
    """Multi-layer guardrail system with autonomy support.
    
    🎯 AUTONOMY: Central safety check for all autonomous operations.
    """
    
    async def check_autonomous_action(
        self,
        action: Action,
        session_context: dict[str, Any],
    ) -> AutonomousActionResult:
        """Check if action is safe for autonomous execution.
        
        🎯 AUTONOMY: Called before every action in autonomous mode.
        Returns whether to proceed, block, or escalate.
        """
        # 1. Classify action risk
        classification = self._classifier.classify(action)
        
        # 2. Check trust zone
        trust_match = self._trust_evaluator.evaluate(action.path)
        
        # 3. Check scope limits
        scope_result = self._scope_tracker.check(action, session_context)
        
        # 4. Decide action
        if classification.risk == ActionRisk.FORBIDDEN:
            # 🎯 AUTONOMY: Never proceed with forbidden actions
            return AutonomousActionResult(
                allowed=False,
                reason="Forbidden action type",
                escalation_required=True,
            )
        
        if classification.risk == ActionRisk.DANGEROUS:
            if not trust_match.allowed_in_autonomous:
                # 🎯 AUTONOMY: Escalate dangerous actions outside trust zones
                return AutonomousActionResult(
                    allowed=False,
                    reason=f"Dangerous action outside trust zone: {trust_match.reason}",
                    escalation_required=True,
                )
        
        if not scope_result.passed:
            # 🎯 AUTONOMY: Enforce scope limits
            return AutonomousActionResult(
                allowed=False,
                reason=f"Scope limit exceeded: {scope_result.reason}",
                escalation_required=True,
            )
        
        # Record for learning
        self._classifier.record_violation(classification, str(action), "allowed")
        
        return AutonomousActionResult(allowed=True)
```

---

### Pillar 4: Memory-Informed Prefetch

**🎯 Autonomy Enabler**: Agent starts with relevant context already loaded, reducing exploration time and improving first-attempt accuracy.

Sunwell already has `prefetch/dispatcher.py` and `PersistentMemory` — we connect them.

#### Extend Existing: `prefetch/dispatcher.py`

```python
# EXTEND: prefetch/dispatcher.py - Add memory integration

async def analyze_briefing_for_prefetch(
    briefing: Briefing,
    router_model: str = "gpt-4o-mini",
    # NEW: Memory integration for autonomy
    memory: PersistentMemory | None = None,
) -> PrefetchPlan:
    """Analyze briefing and plan prefetch.
    
    🎯 AUTONOMY: Memory-informed hints enable faster autonomous execution
    by pre-loading context from similar past goals.
    
    Hint sources (priority order):
    1. Briefing signals (existing)
    2. Memory: Similar past goals (NEW)
    3. Memory: User access patterns (NEW)
    4. Semantic search (existing)
    """
    hints: list[str] = []
    
    # 1. Briefing-driven hints (existing)
    if briefing.predicted_skills or briefing.suggested_lens:
        hints.extend(briefing.hot_files)
    
    # 2. NEW: Memory-based hints for autonomy
    if memory:
        # Similar goals accessed these files
        similar_context = await memory.get_relevant(briefing.goal)
        for learning in similar_context.learnings[:5]:
            if learning.files_accessed:
                hints.extend(learning.files_accessed[:5])
        
        # User patterns: frequently accessed files for this goal type
        if memory.patterns:
            user_hints = memory.patterns.get_files_for_goal_type(briefing.goal)
            hints.extend(user_hints[:10])
        
        # Dead ends: DON'T prefetch files from failed approaches
        for dead_end in similar_context.dead_ends:
            if dead_end.file_path in hints:
                hints.remove(dead_end.file_path)
    
    # Deduplicate
    unique_hints = list(dict.fromkeys(hints))
    
    return PrefetchPlan(
        files_to_read=tuple(unique_hints[:30]),
        learnings_to_load=tuple(l.id for l in similar_context.learnings) if memory else (),
        skills_needed=briefing.predicted_skills,
        dag_nodes_to_fetch=(briefing.goal_hash,) if briefing.goal_hash else (),
        suggested_lens=briefing.suggested_lens,
    )
```

#### Extend Existing: `memory/persistent.py`

```python
# EXTEND: memory/persistent.py - Add goal similarity search

@dataclass
class PersistentMemory:
    """Unified access to all memory stores.
    
    🎯 AUTONOMY: Memory enables learning across sessions,
    improving autonomous performance over time.
    """
    
    # ... existing fields ...
    
    async def find_similar_goals(
        self,
        goal: str,
        limit: int = 5,
    ) -> list[GoalMemory]:
        """Find past goals similar to the current one.
        
        🎯 AUTONOMY: Reuse context from similar past work.
        """
        if not self.simulacrum:
            return []
        
        # Use simulacrum's semantic search
        similar = await self.simulacrum.search_by_goal(goal, limit=limit)
        
        return [
            GoalMemory(
                goal=s.goal,
                files_accessed=s.files_accessed,
                approach_taken=s.approach,
                outcome=s.outcome,
                duration_seconds=s.duration,
            )
            for s in similar
        ]

@dataclass(frozen=True, slots=True)
class GoalMemory:
    """Memory of a past goal execution.
    
    🎯 AUTONOMY: Learn from past to improve future autonomous runs.
    """
    goal: str
    files_accessed: tuple[str, ...]
    approach_taken: str
    outcome: str  # "success", "partial", "failed"
    duration_seconds: float
```

#### Wire into `agent/core.py`

```python
# EXTEND: agent/core.py - Use memory-informed prefetch

async def run(
    self,
    session: SessionContext,
    memory: PersistentMemory,
) -> AsyncIterator[AgentEvent]:
    """Execute goal with memory-informed prefetch.
    
    🎯 AUTONOMY: Start with relevant context already loaded.
    """
    
    # ─── PHASE 0: PREFETCH (runs in background) ───
    # 🎯 AUTONOMY: Pre-load context while doing other setup
    prefetch_task = asyncio.create_task(
        self._run_prefetch(session.briefing, memory)
    )
    yield prefetch_start_event()
    
    # ─── PHASE 1: ORIENT ───
    # ... existing orient phase ...
    
    # Wait for prefetch before exploration
    try:
        prefetched = await asyncio.wait_for(prefetch_task, timeout=PREFETCH_TIMEOUT)
        yield prefetch_complete_event(len(prefetched.files))
        
        # 🎯 AUTONOMY: Inject prefetched context
        self._context.update(prefetched.to_context_dict())
    except asyncio.TimeoutError:
        yield prefetch_timeout_event()

async def _run_prefetch(
    self,
    briefing: Briefing | None,
    memory: PersistentMemory,
) -> PrefetchedContext:
    """Run memory-informed prefetch.
    
    🎯 AUTONOMY: Uses past goal patterns to predict needed context.
    """
    if not briefing:
        return PrefetchedContext.empty()
    
    # Use extended prefetch with memory
    plan = await analyze_briefing_for_prefetch(
        briefing,
        memory=memory,  # NEW: Pass memory for learning-based hints
    )
    
    return await execute_prefetch(plan, self.cwd)
```

---

## Unified Autonomous Workflow

Putting all four pillars together — a workflow that runs autonomously:

```python
async def autonomous_goal(
    goal: str,
    workspace: Path,
    trust_level: TrustLevel = TrustLevel.GUARDED,
) -> AutonomousResult:
    """Run a goal with full autonomy support.
    
    🎯 AUTONOMY: Combines all four pillars for unsupervised execution.
    
    Pillars in action:
    1. PREFETCH — Memory-informed context loading (Pillar 4)
    2. CHECKPOINT — Resume from crash (Pillar 2)
    3. GUARDS — Safe execution (Pillar 3)
    4. SPAWNING — Delegate complex subtasks (Pillar 1)
    """
    
    # === SETUP ===
    memory = PersistentMemory.load(workspace)
    guardrails = GuardrailSystem(workspace, trust_level=trust_level)
    
    # 🎯 AUTONOMY: Check for checkpoint to resume
    existing_checkpoint = AgentCheckpoint.find_latest_for_goal(workspace, goal)
    if existing_checkpoint:
        logger.info(f"Resuming from {existing_checkpoint.phase.value}")
    
    # === BUILD SESSION ===
    session = SessionContext.build(
        workspace,
        goal,
        options=RunOptions(
            auto_resume=True,  # 🎯 AUTONOMY: Auto-resume without prompt
            enable_spawning=True,  # 🎯 AUTONOMY: Allow specialist spawning
            checkpoint_phases=True,  # 🎯 AUTONOMY: Save at phase boundaries
        ),
    )
    
    # === CREATE AGENT ===
    agent = Agent(
        model=synthesis_model,
        tool_executor=ToolExecutor(
            workspace=workspace,
            policy=ToolPolicy(
                trust_level=trust_level,
                # 🎯 AUTONOMY: Pre-action guard check
                pre_action_hook=guardrails.check_autonomous_action,
            ),
        ),
        budget=AdaptiveBudget(total_budget=100_000),
    )
    
    # === RUN WITH AUTONOMY ===
    results: list[AgentEvent] = []
    
    async for event in agent.run(session, memory):
        results.append(event)
        
        # 🎯 AUTONOMY: Handle escalations without stopping
        if event.type == EventType.ESCALATION_REQUIRED:
            if trust_level == TrustLevel.FULL:
                # Auto-approve in FULL trust mode
                await agent.resolve_escalation(event.escalation_id, "approve")
            else:
                # Log and continue (or queue for human review)
                logger.warning(f"Escalation: {event.details}")
                await agent.resolve_escalation(event.escalation_id, "skip")
        
        # 🎯 AUTONOMY: Handle specialist completion
        if event.type == EventType.SPECIALIST_COMPLETED:
            logger.info(f"Specialist {event.specialist_id} completed: {event.summary}")
    
    # === RECORD LEARNING ===
    # 🎯 AUTONOMY: Learn from this session for future runs
    await memory.record_goal_completion(
        goal=goal,
        outcome="success" if agent.success else "failed",
        files_accessed=agent.files_accessed,
        approach=agent.approach_summary,
        duration=agent.elapsed_seconds,
    )
    
    return AutonomousResult(
        success=agent.success,
        files_created=agent.artifacts,
        checkpoints_saved=agent.checkpoint_count,
        specialists_spawned=agent.specialist_count,
        guard_checks=guardrails.check_count,
    )
```

---

## CLI Commands

```bash
# === AUTONOMOUS MODE ===
# 🎯 Full autonomy with all pillars active
sunwell autonomous "Add OAuth authentication"
sunwell autonomous "Refactor payment module" --trust full

# === CHECKPOINT MANAGEMENT ===
# 🎯 Crash recovery
sunwell resume                                  # Latest checkpoint
sunwell resume --goal "Add OAuth"               # Latest for goal
sunwell resume --phase design_approved          # From specific phase
sunwell checkpoints list                        # List all
sunwell checkpoint "Before risky change"        # Manual checkpoint

# === GUARD MANAGEMENT ===
# 🎯 Safe autonomy
sunwell guard list                              # Show guards
sunwell guard stats                             # Violation stats
sunwell guard evolve                            # Apply suggested improvements
sunwell guard feedback <id> false_positive      # Mark false positive

# === MEMORY INSIGHTS ===
# 🎯 Learning across sessions
sunwell memory similar "Add caching"            # Find similar past goals
sunwell memory patterns                         # Show access patterns
sunwell memory learnings                        # Show learnings
```

---

## Implementation Plan

### Phase 1: Wire Up Spawning (Week 1)
- [ ] Extend `Lens` with `can_spawn`, `max_children` fields
- [ ] Add `spawn_specialist()` to `Naaru`
- [ ] Wire spawning into `Agent.run()` execution loop
- [ ] Add `SpecialistSpawned`, `SpecialistCompleted` events

### Phase 2: Wire Up Semantic Checkpoints (Week 2)
- [ ] Extend `AgentCheckpoint` with `phase`, `phase_summary`, `user_decisions`
- [ ] Add checkpoint saving at Agent phase boundaries
- [ ] Extend `cli/agent/resume.py` with `--goal`, `--phase` options
- [ ] Add `find_latest_for_goal()` to checkpoint

### Phase 3: Wire Up Adaptive Guards (Week 3)
- [ ] Extend `TrustZone` with learning fields
- [ ] Add `record_violation()`, `suggest_evolutions()` to `SmartActionClassifier`
- [ ] Add `check_autonomous_action()` to `GuardrailSystem`
- [ ] Add `sunwell guard evolve` CLI command

### Phase 4: Wire Up Memory Prefetch (Week 4)
- [ ] Extend `analyze_briefing_for_prefetch()` with `memory` parameter
- [ ] Add `find_similar_goals()` to `PersistentMemory`
- [ ] Wire memory-informed prefetch into `Agent.run()`
- [ ] Add `sunwell memory similar` CLI command

### Phase 5: Integration & Testing (Week 5)
- [ ] Create `autonomous_goal()` unified workflow
- [ ] Add `sunwell autonomous` CLI command
- [ ] Integration tests for each pillar
- [ ] End-to-end autonomous workflow tests

### Phase 6: Benchmarking (Week 6)
- [ ] Benchmark against Claude Code feature-dev
- [ ] Measure autonomous session duration
- [ ] Measure checkpoint recovery success rate
- [ ] Measure guard false positive rate after learning

---

## Success Metrics

| Metric | Target | 🎯 Autonomy Impact |
|--------|--------|-------------------|
| Autonomous session duration | >2 hours | Checkpoints + guards enable long sessions |
| Checkpoint recovery rate | 100% | Never lose progress |
| Guard false positive rate | <5% after learning | Fewer interruptions |
| Prefetch cache hit rate | >70% | Faster start, better first attempts |
| Specialist spawn rate | ~20% of complex goals | Better quality on hard tasks |

---

## Open Questions

1. **Spawn budget allocation**: How to split token budget between parent and specialists?
2. **Checkpoint retention**: How many checkpoints to keep per goal?
3. **Guard evolution approval**: Auto-apply or require human approval?
4. **Memory privacy**: How to handle sensitive learnings in shared workspaces?

---

## References

- **Existing Systems Extended**:
  - `agent/core.py` — Agent execution engine
  - `naaru/coordinator.py` — Parallel worker coordination
  - `naaru/checkpoint.py` — Checkpoint save/load
  - `guardrails/` — GuardrailSystem, TrustZone, SmartActionClassifier
  - `prefetch/dispatcher.py` — Briefing-driven prefetch
  - `memory/persistent.py` — PersistentMemory facade
  - `cli/agent/resume.py` — Resume CLI command

- **Competitive Analysis**:
  - Claude Code Plugin Architecture: `claude-code/plugins/README.md`
  - Claude Code Feature Dev: `claude-code/plugins/feature-dev/`
  - Claude Code Hookify: `claude-code/plugins/hookify/`

- **Prior Sunwell RFCs**:
  - RFC-032: Agent checkpoints
  - RFC-048: Autonomy guardrails
  - RFC-071: Briefing-driven prefetch
  - RFC-110: Agent as THE entry point
  - RFC-MEMORY: PersistentMemory unification
