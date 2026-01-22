# RFC: Backlog-Driven Execution Architecture

**Status**: Ready for Review  
**Created**: 2026-01-22  
**Updated**: 2026-01-22  
**Author**: AI Assistant  
**Issue**: DAG doesn't update when goals complete; planning ignores existing work

---

## Problem Statement

### Current State: Fragmented Execution

Three separate code paths execute goals:

1. **`sunwell agent run`** — Adds goal to backlog, never marks complete
2. **`sunwell backlog run`** — Marks complete via direct manipulation, no events emitted
3. **Studio "Run Goal"** — Calls `agent run`, inherits its bugs

This causes:
- DAG shows completed goals as "pending" forever (`agent run` path)
- Manual refresh required to see updates (no events emitted)
- Planning creates duplicate work (ignores existing goals)
- Race conditions possible (no goal claiming)
- Inconsistent completion handling (direct vs. method call)

### Evidence

```python
# src/sunwell/cli/agent/run.py:747-761
# Goal added to backlog...
await backlog_manager.add_external_goal(backlog_goal)

# ...but NEVER marked complete after execution
# No call to backlog_manager.complete_goal() anywhere in this file
```

```python
# src/sunwell/cli/backlog_cmd.py:382-391
# backlog run marks complete, but via direct manipulation (no events)
manager.backlog.completed.add(goal_id)  # Direct set manipulation
manager._save()
# No call to complete_goal(), no event emission
```

```svelte
<!-- studio/src/routes/Project.svelte:119-121 -->
<!-- DAG only reloads if you're on Pipeline tab -->
if (activeTab === ViewTab.PIPELINE) {
  loadDag();
}
```

---

## Goals

1. **Single execution pipeline** — All goal execution flows through one manager
2. **Event-driven UI** — DAG updates reactively via events, no manual refresh
3. **Backlog-aware planning** — Planners receive existing work context
4. **Goal claiming** — Prevent duplicate execution of same goal

---

## Non-Goals

- Backwards compatibility shims for old execution paths
- Gradual migration period
- Supporting mixed old/new execution

---

## Design Decisions

### Partial Failure Handling

**Decision**: Mark goal as `completed` if ANY artifacts succeed; `failed` only if ALL fail.

**Rationale**: 
- Partial progress is valuable and should be tracked
- Failed artifacts can be retried in a subsequent run
- UI event includes `partial: true` flag for visibility

### Goal Similarity Matching

**Decision**: Simple word overlap (Jaccard-like) with 0.8 threshold.

**Rationale**:
- Fast, deterministic, no external dependencies
- Embeddings would be more accurate but add complexity
- Can be upgraded later without breaking changes

### Worker ID Sentinel

**Decision**: Use `-1` for single-instance execution claims.

**Rationale**:
- Keeps `claim_goal()` API unified for both single and parallel modes
- Workers use positive IDs (1+), so no collision
- Easier than maintaining two separate code paths

### Cross-Language Event Sync

**Decision**: Mirror Python `EventType` enum in Rust `agent.rs`.

**Rationale**:
- Rust Tauri bridge parses Python NDJSON events and forwards to Svelte
- Type-safe enum prevents typos and enables IDE autocomplete
- Serde `rename_all = "snake_case"` handles Python→Rust naming automatically
- Existing pattern in codebase (see `agent.rs:17` comment)

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  All execution paths (CLI, Studio, autonomous)              │
│        │                                                    │
│        ▼                                                    │
│  ┌──────────────────┐                                       │
│  │ ExecutionManager │  ← Single entry point                 │
│  │ (owns backlog)   │                                       │
│  └────────┬─────────┘                                       │
│           │                                                 │
│           ├──→ BacklogManager.claim_goal()                  │
│           │                                                 │
│           ├──→ Planner.plan(goal, backlog_context)          │
│           │         │                                       │
│           │         └── Existing goals, completed artifacts │
│           │                                                 │
│           ├──→ Execute artifacts                            │
│           │                                                 │
│           ├──→ BacklogManager.complete_goal()               │
│           │         │                                       │
│           │         └── Emits BACKLOG_GOAL_COMPLETED        │
│           │                                                 │
│           └──→ Event stream ──→ Studio (reactive update)    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Component 1: ExecutionManager

Single entry point for all goal execution.

```python
# src/sunwell/execution/manager.py
from dataclasses import dataclass
from pathlib import Path

from sunwell.adaptive.events import AgentEvent, EventType
from sunwell.backlog.manager import BacklogManager, GoalResult
from sunwell.execution.context import BacklogContext
from sunwell.naaru.events import EventEmitter


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of goal execution."""
    success: bool
    goal_id: str
    artifacts_created: tuple[str, ...]
    artifacts_failed: tuple[str, ...]
    error: str | None = None


class ExecutionManager:
    """Single entry point for all goal execution.
    
    Owns the backlog and ensures consistent state updates.
    All CLI commands and Studio go through this.
    """
    
    def __init__(
        self,
        root: Path,
        emitter: EventEmitter,
    ):
        self.root = root
        self.emitter = emitter
        self.backlog = BacklogManager(root)
    
    async def run_goal(
        self,
        goal: str,
        planner,  # Planner protocol
        executor,  # ToolExecutor
        *,
        goal_id: str | None = None,
    ) -> ExecutionResult:
        """Execute a goal with full backlog lifecycle.
        
        1. Create/find goal in backlog
        2. Claim it (prevents duplicate execution)
        3. Plan with backlog context
        4. Execute artifacts
        5. Mark complete/failed in backlog
        6. Emit events for UI
        """
        # 1. Ensure goal exists in backlog
        goal_obj = await self._ensure_goal(goal, goal_id)
        
        # 2. Claim goal (atomic - fails if already claimed)
        # worker_id=None for single-instance execution (uses -1 sentinel)
        claimed = await self.backlog.claim_goal(goal_obj.id, worker_id=None)
        if not claimed:
            return ExecutionResult(
                success=False,
                goal_id=goal_obj.id,
                artifacts_created=(),
                artifacts_failed=(),
                error=f"Goal {goal_obj.id} already being executed",
            )
        
        self._emit(EventType.BACKLOG_GOAL_STARTED, {
            "goal_id": goal_obj.id,
            "title": goal_obj.title,
        })
        
        try:
            # 3. Build backlog context for planner
            context = await self._build_context()
            
            # 4. Plan with context
            self._emit(EventType.PLAN_START, {"goal": goal})
            plan = await planner.plan(goal, backlog=context)
            self._emit(EventType.PLAN_WINNER, {"tasks": len(plan.tasks)})
            
            # 5. Execute
            result = await self._execute(plan, executor)
            
            # 6. Update backlog based on result
            # Partial success: mark complete if ANY artifacts succeeded
            # Full failure: mark failed only if ALL artifacts failed
            if result.artifacts_created:
                await self.backlog.complete_goal(
                    goal_obj.id,
                    GoalResult(
                        success=len(result.artifacts_failed) == 0,
                        summary=f"Created {len(result.artifacts_created)}/{len(result.artifacts_created) + len(result.artifacts_failed)} artifacts",
                        artifacts_created=list(result.artifacts_created),
                        files_changed=len(result.artifacts_created),
                    ),
                )
                self._emit(EventType.BACKLOG_GOAL_COMPLETED, {
                    "goal_id": goal_obj.id,
                    "artifacts": list(result.artifacts_created),
                    "failed": list(result.artifacts_failed),
                    "partial": len(result.artifacts_failed) > 0,
                })
            else:
                # Total failure - no artifacts created
                error_msg = f"All tasks failed: {', '.join(result.artifacts_failed)}"
                await self.backlog.mark_failed(goal_obj.id, error_msg)
                self._emit(EventType.BACKLOG_GOAL_FAILED, {
                    "goal_id": goal_obj.id,
                    "error": error_msg,
                })
            
            return result
            
        except Exception as e:
            await self.backlog.mark_failed(goal_obj.id, str(e))
            self._emit(EventType.BACKLOG_GOAL_FAILED, {
                "goal_id": goal_obj.id,
                "error": str(e),
            })
            raise
        finally:
            # Always unclaim on exit
            await self.backlog.unclaim_goal(goal_obj.id)
    
    async def _build_context(self) -> BacklogContext:
        """Build context for planner from current backlog state."""
        pending = await self.backlog.get_pending_goals()
        completed_artifacts = await self.backlog.get_completed_artifacts()
        
        return BacklogContext(
            existing_goals=tuple(pending),
            completed_artifacts=frozenset(completed_artifacts),
            in_progress=self.backlog.backlog.in_progress,
        )
    
    async def _ensure_goal(self, goal: str, goal_id: str | None) -> Goal:
        """Create goal in backlog if not exists."""
        from sunwell.backlog.goals import Goal, GoalScope
        from sunwell.util import hash_goal
        
        gid = goal_id or hash_goal(goal)
        
        # Check if already exists
        existing = self.backlog.backlog.goals.get(gid)
        if existing:
            return existing
        
        # Create new goal
        new_goal = Goal(
            id=gid,
            title=goal[:100],
            description=goal,
            source_signals=(),
            priority=1.0,
            estimated_complexity="moderate",
            requires=frozenset(),
            category="user",
            auto_approvable=True,
            scope=GoalScope(max_files=50, max_lines_changed=5000),
        )
        await self.backlog.add_external_goal(new_goal)
        self._emit(EventType.BACKLOG_GOAL_ADDED, {
            "goal_id": gid,
            "title": new_goal.title,
        })
        return new_goal
    
    async def _execute(self, plan, executor) -> ExecutionResult:
        """Execute plan artifacts."""
        created: list[str] = []
        failed: list[str] = []
        
        for task in plan.tasks:
            try:
                await executor.execute_task(task)
                created.append(task.id)
                self._emit(EventType.TASK_COMPLETE, {"task_id": task.id})
            except Exception as e:
                failed.append(task.id)
                self._emit(EventType.TASK_FAILED, {
                    "task_id": task.id,
                    "error": str(e),
                })
        
        return ExecutionResult(
            success=len(failed) == 0,
            goal_id=plan.goal_id,
            artifacts_created=tuple(created),
            artifacts_failed=tuple(failed),
        )
    
    def _emit(self, event_type: EventType, data: dict) -> None:
        """Emit event via configured emitter."""
        self.emitter.emit(AgentEvent(event_type, data))
```

### Component 2: BacklogContext

What planners need to know about existing work.

```python
# src/sunwell/execution/context.py
from dataclasses import dataclass

from sunwell.backlog.goals import Goal


@dataclass(frozen=True, slots=True)
class BacklogContext:
    """Existing work context for planning.
    
    Passed to planners so they can:
    - Avoid creating duplicate goals
    - Reference existing artifacts instead of recreating
    - Understand what's in progress
    """
    
    existing_goals: tuple[Goal, ...]
    """Goals already in backlog."""
    
    completed_artifacts: frozenset[str]
    """Artifact IDs already created."""
    
    in_progress: str | None
    """Goal ID currently being executed."""
    
    def artifact_exists(self, artifact_id: str) -> bool:
        """Check if artifact already exists."""
        return artifact_id in self.completed_artifacts
    
    def has_similar_goal(self, description: str, threshold: float = 0.8) -> Goal | None:
        """Find existing goal similar to description.
        
        Uses simple keyword overlap. Could use embeddings for better matching.
        """
        desc_words = set(description.lower().split())
        
        for goal in self.existing_goals:
            goal_words = set(goal.description.lower().split())
            if not goal_words:
                continue
            overlap = len(desc_words & goal_words) / len(goal_words)
            if overlap >= threshold:
                return goal
        
        return None
```

### Component 3: Planner Protocol Update

Add backlog parameter to planner interface.

```python
# src/sunwell/naaru/planners/protocol.py
from typing import Protocol

from sunwell.execution.context import BacklogContext


class Planner(Protocol):
    """Protocol for goal planners."""
    
    async def plan(
        self,
        goal: str,
        context: dict | None = None,
        backlog: BacklogContext | None = None,
    ) -> Plan:
        """Generate execution plan.
        
        Args:
            goal: What to accomplish
            context: Execution context (cwd, etc.)
            backlog: Existing work context for smarter planning
        
        Returns:
            Execution plan with tasks
        """
        ...
```

### Component 4: BacklogManager Updates

Extend `BacklogManager` to support single-instance claiming and artifact tracking.

```python
# src/sunwell/backlog/manager.py (modifications)

# CHANGE: Make worker_id optional for single-instance execution
async def claim_goal(self, goal_id: str, worker_id: int | None = None) -> bool:
    """Claim a goal for execution.
    
    Args:
        goal_id: ID of the goal to claim
        worker_id: Worker ID (None for single-instance, required for parallel)
    
    Returns:
        True if successfully claimed, False if already claimed
    """
    goal = self.backlog.goals.get(goal_id)
    if goal is None:
        return False
    
    # Check if already claimed
    if goal.claimed_by is not None:
        return False
    
    # For single-instance, use -1 as sentinel
    effective_worker_id = worker_id if worker_id is not None else -1
    
    claimed_goal = Goal(
        # ... existing fields ...
        claimed_by=effective_worker_id,
        claimed_at=datetime.now(),
    )
    
    self.backlog.goals[goal_id] = claimed_goal
    self._save()
    return True


# ADD: New method to track completed artifacts
async def get_completed_artifacts(self) -> list[str]:
    """Get list of artifact IDs from completed goals.
    
    Reads from completion history to find all artifacts created.
    
    Returns:
        List of artifact IDs that were successfully created
    """
    history_path = self.backlog_path / "completed.jsonl"
    if not history_path.exists():
        return []
    
    artifacts: list[str] = []
    for line in history_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            artifacts.extend(entry.get("artifacts_created", []))
        except json.JSONDecodeError:
            continue
    
    return artifacts


# MODIFY: _record_completion to include artifacts
async def _record_completion(self, goal_id: str, result: GoalResult) -> None:
    """Record goal completion in history."""
    history_path = self.backlog_path / "completed.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "goal_id": goal_id,
        "success": result.success,
        "duration_seconds": result.duration_seconds,
        "files_changed": result.files_changed,
        "failure_reason": result.failure_reason,
        "artifacts_created": result.artifacts_created,  # NEW: track artifacts
        "timestamp": datetime.now().isoformat(),
    }

    with history_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
```

### Component 5: Backlog Event Types (Python)

```python
# src/sunwell/adaptive/events.py (additions)
class EventType(Enum):
    # ... existing events ...
    
    # Backlog lifecycle (NEW)
    BACKLOG_GOAL_ADDED = "backlog_goal_added"
    """Goal added to backlog."""
    
    BACKLOG_GOAL_STARTED = "backlog_goal_started"
    """Goal execution started (claimed)."""
    
    BACKLOG_GOAL_COMPLETED = "backlog_goal_completed"
    """Goal completed successfully."""
    
    BACKLOG_GOAL_FAILED = "backlog_goal_failed"
    """Goal execution failed."""
    
    BACKLOG_REFRESHED = "backlog_refreshed"
    """Backlog refreshed from signals."""
```

### Component 6: Backlog Event Types (Rust)

The Tauri backend must stay in sync with Python events. Add to `EventType` enum.

```rust
// studio/src-tauri/src/agent.rs (additions to EventType enum)
// KEEP IN SYNC WITH: src/sunwell/adaptive/events.py

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    // ... existing events ...
    
    // Backlog lifecycle (NEW - matches Python)
    BacklogGoalAdded,
    BacklogGoalStarted,
    BacklogGoalCompleted,
    BacklogGoalFailed,
    BacklogRefreshed,
}
```

> **Note**: Rust `EventType` uses PascalCase variants that serde converts to `snake_case` 
> for JSON serialization. `BacklogGoalAdded` → `"backlog_goal_added"`.

### Component 7: Studio Event Handling (Svelte/TypeScript)

```typescript
// studio/src/stores/agent.svelte.ts (additions to handleAgentEvent)
case 'backlog_goal_added':
case 'backlog_goal_started':
case 'backlog_goal_completed':
case 'backlog_goal_failed':
case 'backlog_refreshed':
  // Trigger DAG reload (debounced to prevent flood)
  debouncedReloadDag();
  break;
```

```typescript
// studio/src/stores/dag.svelte.ts (add exports)
import { debounce } from '../utils/debounce';

async function reloadDagInternal(): Promise<void> {
  const path = get(project).current?.path;
  if (!path) return;
  
  try {
    const graph = await invoke<DagGraph>('get_project_dag', { path });
    setGraph(graph);
  } catch (e) {
    console.error('Failed to reload DAG:', e);
  }
}

// Debounce to 100ms to handle rapid event bursts
export const reloadDag = debounce(reloadDagInternal, 100);

// Also export immediate version for manual refresh
export { reloadDagInternal as reloadDagImmediate };
```

```typescript
// studio/src/utils/debounce.ts (new file if not exists)
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      fn(...args);
      timeoutId = null;
    }, delay);
  };
}
```

### Component 8: Simplified Project.svelte

Remove manual refresh logic.

```svelte
<!-- studio/src/routes/Project.svelte -->
<!-- DELETE these lines (109-124): -->
<!--
  let prevAgentDone = $state(false);
  $effect(() => {
    const isDone = agent.isDone;
    const path = project.current?.path;
    if (isDone && !prevAgentDone && path) {
      filesLoadedForPath = null;
      loadProjectFiles();
      if (activeTab === ViewTab.PIPELINE) {
        loadDag();
      }
    }
    prevAgentDone = isDone;
  });
-->

<!-- Keep only the tab-switch effect for initial load: -->
$effect(() => {
  if (activeTab === ViewTab.PIPELINE && project.current?.path && dag.nodes.length === 0) {
    loadDag();  // Initial load only
  }
});
```

---

## CLI Integration

### agent run

```python
# src/sunwell/cli/agent/run.py
# Replace _incremental_run() body with:

async def _incremental_run(
    goal: str,
    planner,
    plan_id: str | None,
    force: bool,
    verbose: bool,
    max_time: int,
    tool_executor,
    json_output: bool = False,
) -> None:
    """Execute goal using ExecutionManager."""
    from sunwell.execution.manager import ExecutionManager
    from sunwell.naaru.events import NaaruEventEmitter, StdoutEmitter
    
    # Setup emitter based on output mode
    emitter = StdoutEmitter(json=json_output)
    
    # Create execution manager
    manager = ExecutionManager(
        root=Path.cwd(),
        emitter=emitter,
    )
    
    # Execute (all backlog handling is internal)
    result = await manager.run_goal(
        goal=goal,
        planner=planner,
        executor=tool_executor,
        goal_id=plan_id,
    )
    
    # Summary already emitted via events
    if not result.success and not json_output:
        console.print(f"[red]Failed: {result.error}[/red]")
```

### backlog run

```python
# src/sunwell/cli/backlog_cmd.py
# Replace _run_backlog_goal() with delegation to ExecutionManager

async def _run_backlog_goal(goal_id: str, ...) -> None:
    """Run a specific backlog goal."""
    from sunwell.execution.manager import ExecutionManager
    
    manager = ExecutionManager(root=Path.cwd(), emitter=emitter)
    
    # Load existing goal from backlog
    goal = manager.backlog.backlog.goals.get(goal_id)
    if not goal:
        raise click.ClickException(f"Goal {goal_id} not found in backlog")
    
    # Execute via manager
    await manager.run_goal(
        goal=goal.description,
        planner=planner,
        executor=tool_executor,
        goal_id=goal_id,
    )
```

---

## Migration Plan

### Phase 1: Add ExecutionManager (non-breaking)

1. Create `src/sunwell/execution/manager.py`
2. Create `src/sunwell/execution/context.py`
3. Update `BacklogManager`:
   - Make `worker_id` optional in `claim_goal()` (default `None` → `-1` sentinel)
   - Add `get_completed_artifacts()` method
   - Update `_record_completion()` to include `artifacts_created`
4. Update `GoalResult` to include `artifacts_created: list[str]` field
5. Add backlog event types to `events.py`
6. Add `backlog` param to planner protocol (optional, backwards compatible)

### Phase 2: Wire CLI

1. Update `agent run` to use `ExecutionManager`
2. Update `backlog run` to use `ExecutionManager`
3. Delete duplicate backlog handling code

### Phase 3: Wire Studio (Rust + Svelte)

**Rust (Tauri)**:
1. Add backlog event variants to `EventType` enum in `agent.rs`

**Svelte/TypeScript**:
2. Create `studio/src/utils/debounce.ts` (if not exists)
3. Add debounced `reloadDag()` export to `dag.svelte.ts`
4. Add backlog event handlers to `agent.svelte.ts` (using debounced reload)
5. Remove `prevAgentDone` tracking from `Project.svelte`
6. Remove conditional DAG reload logic

### Phase 4: Delete Dead Code

1. Remove `_incremental_run()` backlog manipulation
2. Remove `_run_backlog_goal()` backlog manipulation
3. Remove manual backlog instantiation in CLI commands

---

## Testing

### Unit Tests

```python
# tests/execution/test_manager.py
async def test_goal_lifecycle():
    """Goal goes through full lifecycle."""
    manager = ExecutionManager(tmp_path, mock_emitter)
    
    result = await manager.run_goal("Build X", mock_planner, mock_executor)
    
    assert result.success
    assert "goal-hash" in manager.backlog.backlog.completed
    assert mock_emitter.events == [
        ("backlog_goal_added", ...),
        ("backlog_goal_started", ...),
        ("plan_start", ...),
        ("plan_winner", ...),
        ("task_complete", ...),
        ("backlog_goal_completed", ...),
    ]

async def test_duplicate_execution_blocked():
    """Cannot execute same goal twice simultaneously."""
    manager = ExecutionManager(tmp_path, mock_emitter)
    
    # Claim goal (worker_id=None for single-instance)
    await manager.backlog.claim_goal("goal-1", worker_id=None)
    
    # Second execution should fail
    result = await manager.run_goal("Build X", mock_planner, mock_executor, goal_id="goal-1")
    
    assert not result.success
    assert "already being executed" in result.error

async def test_partial_success_marks_complete():
    """Goal with partial success is marked complete with artifacts."""
    manager = ExecutionManager(tmp_path, mock_emitter)
    
    # Planner returns 3 tasks, executor fails 1
    mock_executor.fail_on = ["task-2"]
    
    result = await manager.run_goal("Build X", mock_planner, mock_executor)
    
    # Goal is marked complete because some artifacts succeeded
    assert result.success is False  # Not fully successful
    assert len(result.artifacts_created) == 2
    assert len(result.artifacts_failed) == 1
    # But goal is in completed set (partial success)
    assert "goal-hash" in manager.backlog.backlog.completed

async def test_planner_receives_context():
    """Planner gets backlog context."""
    manager = ExecutionManager(tmp_path, mock_emitter)
    
    # Pre-populate backlog
    await manager.backlog.add_external_goal(existing_goal)
    await manager.backlog.complete_goal("existing-1", result)
    
    # Run new goal
    await manager.run_goal("Build Y", spy_planner, mock_executor)
    
    # Planner should have received context
    assert spy_planner.last_backlog.existing_goals == (existing_goal,)
    assert "artifact-1" in spy_planner.last_backlog.completed_artifacts
```

### Integration Tests

```python
# tests/integration/test_studio_events.py
async def test_dag_updates_on_completion():
    """Studio DAG updates when goal completes."""
    # Start goal via CLI
    # Capture events
    # Verify BACKLOG_GOAL_COMPLETED emitted
    # Verify DAG reload triggered
```

---

## Files Changed

### Python (Backend)

| File | Change |
|---|---|
| `src/sunwell/execution/__init__.py` | NEW |
| `src/sunwell/execution/manager.py` | NEW |
| `src/sunwell/execution/context.py` | NEW |
| `src/sunwell/backlog/manager.py` | Add `get_completed_artifacts()`, make `worker_id` optional |
| `src/sunwell/backlog/goals.py` | Add `artifacts_created` to `GoalResult` |
| `src/sunwell/adaptive/events.py` | Add backlog event types |
| `src/sunwell/naaru/planners/protocol.py` | Add backlog param |
| `src/sunwell/naaru/planners/harmonic.py` | Accept backlog param |
| `src/sunwell/naaru/planners/agent.py` | Accept backlog param |
| `src/sunwell/cli/agent/run.py` | Use ExecutionManager |
| `src/sunwell/cli/backlog_cmd.py` | Use ExecutionManager |

### Rust (Tauri Bridge)

| File | Change |
|---|---|
| `studio/src-tauri/src/agent.rs` | Add backlog event variants to `EventType` enum |

### Svelte/TypeScript (Frontend)

| File | Change |
|---|---|
| `studio/src/stores/agent.svelte.ts` | Handle backlog events, use debounced reload |
| `studio/src/stores/dag.svelte.ts` | Export debounced `reloadDag()` |
| `studio/src/utils/debounce.ts` | NEW (if not exists) |
| `studio/src/routes/Project.svelte` | Remove manual refresh |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Breaking existing CLI scripts | Phase 1 is additive, no breaking changes until Phase 2 |
| Event flood overwhelming UI | Debounce `reloadDag()` calls (100ms) - see Component 7 |
| Backlog file corruption | ExecutionManager uses atomic writes via BacklogManager |
| Planner ignores backlog param | Protocol change is optional param, graceful degradation |
| Partial success ambiguity | Clear event includes `partial: true` flag; UI can distinguish |
| `worker_id=-1` collision with real worker | Workers use positive IDs (1+); -1 reserved for single-instance |
| Python/Rust event enum drift | Comment in `agent.rs` says "KEEP IN SYNC"; add CI check if drift recurs |

---

## Success Criteria

1. ✅ DAG updates automatically when any goal completes
2. ✅ No manual refresh button needed
3. ✅ Planners receive existing work context
4. ✅ Duplicate goal execution prevented
5. ✅ Single code path for all execution
6. ✅ Partial success tracked and visible
7. ✅ No event flood in UI (debounced)
8. ✅ Completed artifacts queryable for planning