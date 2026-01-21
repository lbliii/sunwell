# RFC-076: Naaru Decomposition — Completing the RFC-074 Migration

**Status**: Draft (revised)  
**Created**: 2026-01-21  
**Revised**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 90% 🟢  
**Supersedes**: Finalizes RFC-074 migration  
**Depends on**: RFC-074 (Incremental Execution v2)

---

## Summary

**Complete the RFC-074 migration** by rewriting `Naaru._run_with_incremental()` to use the v2 `IncrementalExecutor`, decompose the `Naaru` god object into focused components, and remove the deprecated `naaru/incremental.py` module.

RFC-074 delivered the new `sunwell/incremental/` package (✅), but the main execution path in `Naaru._run_with_incremental()` still uses the deprecated RFC-040 implementation. This RFC addresses the gap.

---

## Problem Statement

### 1. The Migration Is Incomplete

RFC-074's status shows "Implemented ✅" but the main production code path still uses deprecated imports:

```python
# naaru/naaru.py:511-553 (CURRENT STATE)
from sunwell.naaru.incremental import ChangeDetector, IncrementalExecutor
from sunwell.naaru.persistence import PlanStore, hash_goal
...
from sunwell.naaru.incremental import compute_rebuild_set
```

**Evidence**:
| Location | Import | Status |
|----------|--------|--------|
| `naaru/naaru.py:511` | `ChangeDetector, IncrementalExecutor` | ❌ Deprecated |
| `naaru/naaru.py:553` | `compute_rebuild_set` | ❌ Deprecated |
| `naaru/__init__.py:179` | Public API re-export | ❌ Deprecated |
| `weakness/cascade.py:177` | `find_invalidated` | ❌ Deprecated |
| `cli/agent/run.py:574,655` | Multiple imports | ❌ Deprecated |

### 2. API Incompatibility

The old and new `IncrementalExecutor` have **different interfaces**:

```python
# OLD (naaru/incremental.py)
executor = IncrementalExecutor(store=PlanStore())
result = await executor.execute(graph, create_fn, goal, force_rebuild, on_progress)

# NEW (sunwell/incremental/)
cache = ExecutionCache(Path(".sunwell/cache/execution.db"))
executor = IncrementalExecutor(graph, cache)
result = await executor.execute(create_fn)
```

**Key differences**:
- Old: `store=PlanStore()` (JSON files) → New: `cache=ExecutionCache()` (SQLite)
- Old: `graph` passed to `execute()` → New: `graph` passed to constructor
- Old: `goal` parameter for hashing → New: Goal embedded in graph spec hashing
- Old: `force_rebuild: bool` → New: `force_rerun: set[str] | None` (artifact IDs)
- Old: `on_progress` only → New: Both `on_progress` callback AND RFC-060 events
- Old: Returns `ExecutionResult` with `.completed/.failed` dicts → New: Returns `IncrementalResult`

### 3. Naaru Is a God Object

`Naaru` class (~1311 lines) does too much:

```
Naaru responsibilities (CURRENT):
├── Worker lifecycle (bus, workers, routing_worker, tool_worker)
├── Event emission (_emit_event, event_callback)
├── Planning coordination (planner, discover_graph)
├── Execution orchestration (run_incremental, _execute_task_graph)
├── Integration verification (_get_integration_verifier)
├── Artifact collection (_collect_artifacts)
├── Learning extraction (_extract_and_emit_learnings)
├── State persistence (_persist_execution_state)
└── Session management (illuminate, run)
```

This violates single responsibility and makes testing/modification difficult.

### 4. PlanStore vs ExecutionCache Overlap

Two persistence mechanisms exist:

| Mechanism | Storage | Purpose | Location |
|-----------|---------|---------|----------|
| `PlanStore` | JSON files | Goal→execution mapping, task completion | `naaru/persistence.py` |
| `ExecutionCache` | SQLite | Artifact hashes, skip decisions, provenance | `incremental/cache.py` |

Both track "what was executed" but with different schemas and query patterns.

---

## Goals

1. **Complete RFC-074 migration** — `Naaru._run_with_incremental()` uses v2 executor
2. **Remove deprecated module** — Delete `naaru/incremental.py` (~766 lines)
3. **Decompose Naaru** — Extract focused components from god object
4. **Unify persistence** — Single source of truth for execution state
5. **Preserve behavior** — All existing tests continue to pass

---

## Non-Goals

- Redesigning the planning system
- Changing the public `Naaru` API (preserve `run()`, `illuminate()`)
- Modifying `AdaptiveAgent` (it has its own execution flow)

---

## Design

### Phase 1: Migrate `Naaru._run_with_incremental()` (Priority: Critical)

Rewrite `naaru/naaru.py:495-671` (`_run_with_incremental()`) to use v2 executor.

**Before** (current `_run_with_incremental()` at L495-671):
```python
async def _run_with_incremental(self, goal, context, output, start_time, max_time_seconds, force_rebuild=False):
    from sunwell.naaru.incremental import ChangeDetector, IncrementalExecutor
    from sunwell.naaru.persistence import PlanStore, hash_goal
    
    # ... discover graph ...
    
    store = PlanStore()
    goal_hash = hash_goal(goal)
    previous = store.load(goal_hash) if not force_rebuild else None
    
    if previous:
        detector = ChangeDetector()
        changes = detector.detect(graph, previous)
        from sunwell.naaru.incremental import compute_rebuild_set
        to_rebuild = compute_rebuild_set(graph, changes, previous)
    
    executor = IncrementalExecutor(
        store=store,
        trace_enabled=False,
        event_callback=self.config.event_callback,
        integration_verifier=self._get_integration_verifier(),
        project_root=self.sunwell_root,
    )
    
    execution_result = await executor.execute(
        graph=graph,
        create_fn=create_artifact,
        goal=goal,
        force_rebuild=force_rebuild,
        on_progress=progress_handler,
    )
```

**After** (target):
```python
async def _run_with_incremental(self, goal, context, output, start_time, max_time_seconds, force_rebuild=False):
    from sunwell.incremental import ExecutionCache, IncrementalExecutor
    
    # ... discover graph ...
    
    # Initialize v2 cache
    cache_path = self.sunwell_root / ".sunwell" / "cache" / "execution.db"
    cache = ExecutionCache(cache_path)
    
    # Create v2 executor
    executor = IncrementalExecutor(
        graph=graph,
        cache=cache,
        event_callback=self.config.event_callback,
        integration_verifier=self._get_integration_verifier(),
        project_root=self.sunwell_root,
    )
    
    # Convert bool flag to artifact ID set (v2 API uses set[str], not bool)
    force_artifacts = set(graph.keys()) if force_rebuild else None
    
    # Preview what will execute
    plan = executor.plan_execution(force_rerun=force_artifacts)
    if plan.to_skip:
        output(f"   📊 Skipping {len(plan.to_skip)} unchanged artifacts")
    
    def progress_handler(msg: str) -> None:
        output(f"   {msg}")
    
    # Execute (v2 supports both event_callback AND on_progress)
    result = await executor.execute(
        create_fn=create_artifact,
        force_rerun=force_artifacts,
        on_progress=progress_handler,
    )
```

**Migration mapping**:

| Old (RFC-040) | New (RFC-074) | Notes |
|---------------|---------------|-------|
| `PlanStore()` | `ExecutionCache(path)` | SQLite replaces JSON |
| `hash_goal(goal)` | Embedded in `compute_input_hash()` | Per-artifact hashing |
| `store.load(goal_hash)` | `cache.get(artifact_id)` | Per-artifact lookup |
| `ChangeDetector().detect()` | `executor.plan_execution()` | Returns `ExecutionPlan` |
| `compute_rebuild_set()` | `plan.to_execute` | Already computed |
| `executor.execute(graph, ...)` | `executor.execute(create_fn)` | Graph in constructor |
| `force_rebuild: bool` | `force_rerun: set[str] \| None` | Convert: `set(graph.keys()) if force_rebuild else None` |
| `on_progress=handler` | `on_progress=handler` + RFC-060 events | v2 supports both (RFC-060 for structured events, `on_progress` for UI) |

### Phase 2: Update Secondary Call Sites

Update remaining imports after `Naaru` is migrated:

```python
# weakness/cascade.py:177
# OLD:
from sunwell.naaru.incremental import find_invalidated
# NEW:
from sunwell.incremental import ExecutionCache
# Then use cache.get_downstream() for invalidation

# cli/agent/run.py:574,655
# OLD:
from sunwell.naaru.incremental import PlanPreview, IncrementalExecutor, ...
# NEW:
from sunwell.incremental import ExecutionPlan, IncrementalExecutor, ...
```

### Phase 3: Decompose Naaru (Priority: Medium)

Extract focused components from `Naaru`:

```
CURRENT: Naaru (~1311 lines, god object)
         ↓
PROPOSED:
├── NaaruCore (200 lines)
│   └── Worker lifecycle, message bus, configuration
│
├── ExecutionCoordinator (300 lines)  
│   └── run_incremental(), _execute_task_graph()
│   └── Uses IncrementalExecutor from sunwell.incremental
│
├── LearningExtractor (150 lines)
│   └── _extract_and_emit_learnings()
│   └── Moved to sunwell.adaptive.learning
│
├── EventEmitter (100 lines)
│   └── _emit_event(), RFC-060 validation
│   └── Protocol, injectable
│
└── Naaru (facade, 200 lines)
    └── Public API: run(), illuminate()
    └── Delegates to focused components
```

**File structure**:
```
src/sunwell/naaru/
├── core.py          # NaaruCore (existing, expand)
├── coordinator.py   # ExecutionCoordinator (NEW)
├── naaru.py         # Naaru facade (simplified)
└── ... (other existing files)
```

### Phase 4: Unify Persistence

Consolidate `PlanStore` and `ExecutionCache`:

| Feature | PlanStore | ExecutionCache | Unified |
|---------|-----------|----------------|---------|
| Hash storage | JSON file per goal | SQLite per artifact | SQLite |
| Task status | `SavedExecution` | `CachedExecution` | `CachedExecution` |
| Provenance | None | Recursive CTE | Keep |
| Goal lookup | `load(goal_hash)` | N/A | Add `get_by_goal()` |

**Migration**: Add goal tracking to `ExecutionCache`:

```sql
-- Schema addition (incremental/cache.py)
CREATE TABLE IF NOT EXISTS goal_executions (
    goal_hash TEXT PRIMARY KEY,
    artifact_ids TEXT NOT NULL,  -- JSON array of artifact IDs
    executed_at REAL NOT NULL,
    execution_time_ms REAL
);

CREATE INDEX IF NOT EXISTS idx_goal_executions_time 
    ON goal_executions(executed_at DESC);
```

```python
# incremental/cache.py (addition)
def record_goal_execution(
    self, 
    goal_hash: str, 
    artifact_ids: list[str],
    execution_time_ms: float | None = None,
) -> None:
    """Record which artifacts belong to a goal execution."""
    with self._connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO goal_executions 
               (goal_hash, artifact_ids, executed_at, execution_time_ms)
               VALUES (?, ?, ?, ?)""",
            (goal_hash, json.dumps(artifact_ids), time.time(), execution_time_ms),
        )

def get_artifacts_for_goal(self, goal_hash: str) -> list[str] | None:
    """Get artifact IDs from a previous goal execution."""
    with self._connection() as conn:
        row = conn.execute(
            "SELECT artifact_ids FROM goal_executions WHERE goal_hash = ?",
            (goal_hash,),
        ).fetchone()
        return json.loads(row[0]) if row else None
```

### Phase 5: Delete Deprecated Module

After all callers migrated:

```bash
# Remove deprecated files
rm src/sunwell/naaru/incremental.py  # ~766 lines

# Update naaru/__init__.py - remove re-exports
# Lines 179-186 (current):
from sunwell.naaru.incremental import (
    ChangeDetector,
    ChangeReport,
    IncrementalExecutor,
    PlanPreview,
    compute_rebuild_set,
    find_invalidated,
)
# DELETE these lines
```

---

## Implementation Plan

| Phase | Task | Effort | Risk | Status |
|-------|------|--------|------|--------|
| 1a | Add goal tracking to `ExecutionCache` | 2h | Low | ⏳ |
| 1b | Rewrite `Naaru._run_with_incremental()` | 4h | Medium | ⏳ |
| 1c | Update `Naaru` tests | 2h | Low | ⏳ |
| 2a | Migrate `weakness/cascade.py` | 1h | Low | ⏳ |
| 2b | Migrate `cli/agent/run.py` | 2h | Low | ⏳ |
| 2c | Remove re-exports from `naaru/__init__.py` | 30m | Low | ⏳ |
| 3a | Extract `ExecutionCoordinator` | 3h | Medium | ⏳ |
| 3b | Extract `EventEmitter` protocol | 1h | Low | ⏳ |
| 3c | Simplify `Naaru` to facade | 2h | Medium | ⏳ |
| 4 | Consolidate `PlanStore` into `ExecutionCache` | 3h | Medium | ⏳ |
| 5 | Delete `naaru/incremental.py` | 30m | Low | ⏳ |

**Total estimated effort**: ~20h

**Recommended order**: 1a → 1b → 1c → 2a → 2b → 5 → (then 3, 4 as separate PRs)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing `Naaru.run()` callers | Medium | High | Comprehensive test coverage before changes |
| SQLite vs JSON performance regression | Low | Medium | Benchmark before/after |
| `PlanStore` features not in `ExecutionCache` | Medium | Medium | Audit `PlanStore` usage first |
| Phase 3 decomposition breaks internal coupling | Medium | Medium | Defer decomposition; do migration first |

---

## Verification

### Unit Tests

```python
# tests/test_naaru_migration.py

def test_run_with_incremental_uses_v2_executor():
    """Verify Naaru uses sunwell.incremental, not naaru.incremental."""
    import sunwell.naaru.naaru as naaru_module
    source = inspect.getsource(naaru_module.Naaru._run_with_incremental)
    
    assert "from sunwell.incremental import" in source
    assert "from sunwell.naaru.incremental import" not in source

def test_no_deprecation_warnings():
    """Verify no deprecation warnings from naaru imports."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from sunwell.naaru import Naaru
        
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0

def test_execution_cache_goal_tracking():
    """Verify ExecutionCache can track goal→artifacts mapping."""
    cache = ExecutionCache(tmp_path / "test.db")
    cache.record_goal_execution("goal_abc123", ["artifact_1", "artifact_2"])
    
    artifacts = cache.get_artifacts_for_goal("goal_abc123")
    assert set(artifacts) == {"artifact_1", "artifact_2"}
```

### Integration Tests

```python
def test_naaru_run_incremental_skips_unchanged():
    """Full integration: run goal twice, verify second run skips artifacts."""
    naaru = Naaru(...)
    
    # First run - all execute
    result1 = await naaru.run("Create a hello.py file")
    assert result1.completed_count > 0
    
    # Second run - should skip
    result2 = await naaru.run("Create a hello.py file")
    # Verify cache was used (check events or logs)
```

---

## Success Criteria

1. **No deprecation warnings** when importing `sunwell.naaru`
2. **`naaru/incremental.py` deleted** (~766 lines removed)
3. **All 971 tests pass** (or equivalent after test updates)
4. **`Naaru._run_with_incremental()` uses `sunwell.incremental`** (verified by source inspection)
5. **Benchmark**: No >10% regression in incremental execution time

---

## Appendix: Current Deprecated Module Contents

For reference, `naaru/incremental.py` contains:

```
naaru/incremental.py (~766 lines):
├── ChangeDetector (class)
├── ChangeReport (dataclass)
├── IncrementalExecutor (class) - OLD API
├── PlanPreview (dataclass)
├── compute_rebuild_set (function)
├── find_invalidated (function)
└── [internal helpers]
```

All functionality has equivalents in `sunwell/incremental/`:

| Old | New Equivalent |
|-----|----------------|
| `ChangeDetector` | `IncrementalExecutor.plan_execution()` |
| `ChangeReport` | `ExecutionPlan` |
| `IncrementalExecutor` | `IncrementalExecutor` (v2) |
| `PlanPreview` | `ExecutionPlan` |
| `compute_rebuild_set()` | `plan.to_execute` |
| `find_invalidated()` | `cache.get_downstream()` |

---

## Revision History

### 2026-01-21 (Revision 1)

**Fixed API mismatch**: The draft incorrectly showed `force_rerun=force_rebuild` passing a `bool` to v2 executor. The v2 API actually uses `force_rerun: set[str] | None` (artifact IDs). Updated:
- "After" code example now converts `bool` → `set[str]`
- Migration mapping table documents the conversion
- "Key differences" section updated

**Added schema detail**: Phase 1a (goal tracking) now includes SQLite schema and implementation sketch for `record_goal_execution()` / `get_artifacts_for_goal()`.

**Clarified `on_progress`**: v2 executor supports BOTH `on_progress` callbacks AND RFC-060 events — they're not mutually exclusive.

**Corrected line counts**: Updated to actual values (~766, ~1311).

---

## References

- RFC-040: Original incremental execution design
- RFC-074: Incremental Execution v2 (content-addressed cache)
- RFC-060: Event system integration
- RFC-067: Integration-aware DAG
- `src/sunwell/naaru/naaru.py:495-671`: Current `_run_with_incremental()` implementation
- `src/sunwell/incremental/executor.py:256-306`: v2 `IncrementalExecutor` constructor
- `src/sunwell/incremental/executor.py:339-358`: v2 `plan_execution()` signature
- `src/sunwell/incremental/executor.py:424-449`: v2 `execute()` signature
