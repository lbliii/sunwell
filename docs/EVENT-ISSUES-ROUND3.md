# Event System Issues - Round 3 Audit

**Status**: Minor Issue Found  
**Date**: 2026-01-20

---

## Issue Found

### ⚠️ `duration_ms` Set to 0 in Incremental Run

**Problem**: In `_incremental_run()`, the `task_complete` event is emitted with `duration_ms=0` and a comment saying "Will be updated by executor", but the executor calculates duration AFTER the event is emitted.

**Evidence**:
- `src/sunwell/cli/agent/run.py:754` - `duration_ms=0  # Will be updated by executor`
- `src/sunwell/naaru/incremental.py:434` - Executor calculates `duration_ms` AFTER artifact creation
- Event is emitted in `create_artifact()` function BEFORE executor returns

**Impact**: `task_complete` events show `duration_ms=0` instead of actual duration.

**Current Flow**:
1. `create_artifact()` calls `planner.create_artifact()` 
2. `create_artifact()` emits `task_complete` with `duration_ms=0`
3. `IncrementalExecutor._execute_artifact()` calculates actual `duration_ms`
4. But event already emitted with wrong value

**Fix Options**:

**Option 1**: Calculate duration in `create_artifact()`:
```python
async def create_artifact(spec):
    start_time = datetime.now()
    # ... create artifact ...
    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    complete_event = validated_task_complete_event(
        task_id=spec.id,
        duration_ms=duration_ms,  # Use calculated value
        artifact_id=spec.id,
        file=spec.produces_file,
    )
```

**Option 2**: Emit event from executor after duration is calculated (requires refactoring).

**Recommendation**: Use Option 1 (simpler, immediate fix).

---

## Status

This is a **minor issue** - events work correctly but show incorrect duration. The actual duration is calculated and stored in `ArtifactResult`, just not in the event.

---

## Summary

- ✅ All critical issues fixed
- ✅ All planning events handled correctly
- ⚠️ Minor: `duration_ms` shows 0 in incremental run events (actual duration calculated but not in event)
