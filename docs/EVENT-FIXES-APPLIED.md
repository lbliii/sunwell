# Event System Fixes Applied

**Status**: Complete  
**Date**: 2026-01-20

---

## Issues Fixed

### 1. Field Name Mismatch ✅

**Problem**: Incremental execution used `artifact_id` but Studio expects `task_id`

**Fix**: Updated `src/sunwell/cli/agent/run.py` to use validated event factories that ensure `task_id` is always present:

```python
# Before (BROKEN):
emit("task_start", {"artifact_id": spec.id, "description": spec.description})

# After (FIXED):
from sunwell.adaptive.event_schema import validated_task_start_event
start_event = validated_task_start_event(
    task_id=spec.id,
    description=spec.description,
    artifact_id=spec.id,  # Alias for compatibility
)
```

**Files Changed**:
- `src/sunwell/cli/agent/run.py:700-744` - Incremental run event emission

---

### 2. Event Validation ✅

**Problem**: Events were emitted without validation, allowing invalid data to reach Studio

**Fix**: Added validation wrapper to event callbacks:

```python
from sunwell.adaptive.event_schema import ValidatedEventEmitter

validated_emitter = ValidatedEventEmitter(
    CallbackEmitter(emit_json),
    validate=True,
)
naaru_config.event_callback = validated_emitter.emit
```

**Files Changed**:
- `src/sunwell/cli/agent/run.py:343-371` - Event callback setup with validation

---

### 3. Event Callback Not Always Set ✅

**Problem**: Event callback only set for HarmonicPlanner, not other planners

**Fix**: Ensure event callback is set for all planners when `json_output=True`:

```python
if json_output:
    # Set up validated event callback
    validated_emitter = ValidatedEventEmitter(...)
    naaru_config.event_callback = validated_emitter.emit
    
    # Also set on HarmonicPlanner if used
    if isinstance(planner, HarmonicPlanner):
        planner.event_callback = validated_emitter.emit
```

**Files Changed**:
- `src/sunwell/cli/agent/run.py:343-371` - Universal event callback setup

---

### 4. Redundant Serialization ✅

**Problem**: Backlog commands manually serialized events instead of using `event.to_dict()`

**Fix**: Use `event.to_dict()` directly:

```python
# Before:
print(json.dumps({
    "type": event.type.value if hasattr(event.type, 'value') else str(event.type),
    "data": event.data,
    "timestamp": event.timestamp,
}), flush=True)

# After:
print(json.dumps(event.to_dict()), flush=True)
```

**Files Changed**:
- `src/sunwell/cli/backlog_cmd.py:355-360` - Use `event.to_dict()`

---

### 5. Plan Winner Event Validation ✅

**Problem**: `plan_winner` events not using validated factories

**Fix**: Use validated factory in Naaru:

```python
from sunwell.adaptive.event_schema import validated_plan_winner_event
plan_winner_event = validated_plan_winner_event(
    tasks=len(graph),
    artifact_count=len(graph),
)
if self.config.event_callback:
    self.config.event_callback(plan_winner_event)
```

**Files Changed**:
- `src/sunwell/naaru/naaru.py:474-482` - Use validated factory

---

### 6. Type Checker References ✅

**Problem**: Documentation referenced `mypy` but codebase uses `ty`

**Fix**: Updated all documentation references:

- `docs/EVENT-TYPE-SAFETY.md` - Changed mypy → ty
- `docs/EVENT-TYPE-SAFETY-SUMMARY.md` - Changed mypy → ty
- `src/sunwell/adaptive/event_schema.py` - Added note about ty

**Files Changed**:
- `docs/EVENT-TYPE-SAFETY.md`
- `docs/EVENT-TYPE-SAFETY-SUMMARY.md`
- `src/sunwell/adaptive/event_schema.py`

---

## Summary

All critical issues from `docs/EVENT-ANALYSIS.md` have been fixed:

- ✅ Field name mismatch (`artifact_id` → `task_id`)
- ✅ Event validation added
- ✅ Event callback always set for JSON mode
- ✅ Redundant serialization removed
- ✅ Plan winner events use validated factories
- ✅ Documentation updated (mypy → ty)

---

## Testing Checklist

- [ ] Studio receives `plan_start` event
- [ ] Studio receives `plan_winner` with `tasks` count
- [ ] Studio receives `task_start` with `task_id` (not `artifact_id`)
- [ ] Studio receives `task_progress` updates
- [ ] Studio receives `task_complete` with `duration_ms`
- [ ] Studio receives `task_failed` with error message
- [ ] Studio receives `complete` event at end
- [ ] All events have `type`, `data`, `timestamp` fields
- [ ] Event types match `EventType` enum values
- [ ] Validation catches missing required fields

---

## Next Steps

1. Test Studio integration with fixed events
2. Generate TypeScript types: `python scripts/generate_event_types.py > studio/src/lib/types/events.ts`
3. Update Studio to use generated types
4. Add CI check to regenerate types on schema changes
