# Event System Issues - Round 4 Audit

**Status**: Issues Found  
**Date**: 2026-01-20

---

## Critical Issues Found

### 1. ❌ Missing `complete` Event in Incremental Run

**Problem**: `_incremental_run()` does not emit a `complete` event at the end, unlike `Naaru.run()` which does.

**Evidence**:
- `src/sunwell/naaru/naaru.py:595-601` - `Naaru.run()` emits `complete` event
- `src/sunwell/cli/agent/run.py:800-835` - `_incremental_run()` has no `complete` event emission
- Comment at line 370 says "complete event is emitted by Naaru.run() via callback" but incremental run doesn't use Naaru.run()

**Impact**: Studio never receives completion signal for incremental runs, leaving UI in "running" state.

**Fix Needed**: Add `complete` event emission at end of `_incremental_run()`:

```python
# After execution completes
completed = len(execution_result.completed)
failed = len(execution_result.failed)
elapsed = (datetime.now() - start_time).total_seconds()

if json_output:
    from sunwell.adaptive.events import AgentEvent, EventType
    from sunwell.adaptive.event_schema import validate_event_data
    
    complete_data = validate_event_data(EventType.COMPLETE, {
        "tasks_completed": completed,
        "tasks_failed": failed,
        "duration_s": elapsed,
    })
    complete_event = AgentEvent(EventType.COMPLETE, complete_data)
    print(json.dumps(complete_event.to_dict()), file=sys.stdout, flush=True)
```

---

### 2. ⚠️ Potential Duplicate `plan_winner` Events

**Problem**: Both `Naaru._run_with_incremental()` and `HarmonicPlanner` emit `plan_winner` events.

**Evidence**:
- `src/sunwell/naaru/naaru.py:474-481` - Emits `plan_winner` in incremental path
- `src/sunwell/naaru/planners/harmonic.py:365-380` - Emits `plan_winner` after selection
- When using HarmonicPlanner with incremental execution, both emit

**Impact**: Studio receives duplicate `plan_winner` events, potentially causing UI confusion.

**Current Flow**:
1. HarmonicPlanner emits `plan_winner` (line 365)
2. Naaru._run_with_incremental() emits `plan_winner` again (line 474)

**Fix Options**:

**Option 1**: Remove `plan_winner` from Naaru when using HarmonicPlanner (check planner type)

**Option 2**: Make HarmonicPlanner's `plan_winner` the canonical one, skip in Naaru

**Option 3**: Add deduplication logic in Studio (not ideal)

**Recommendation**: Option 1 - Check if planner already emitted `plan_winner` before emitting in Naaru.

---

### 3. ⚠️ Event Validation Swallows Errors

**Problem**: `HarmonicPlanner._emit_event()` catches all exceptions and silently passes, hiding validation errors.

**Evidence**:
- `src/sunwell/naaru/planners/harmonic.py:252-254` - `except Exception: pass`
- This means invalid events are silently dropped

**Impact**: Invalid events fail silently, making debugging difficult.

**Current Behavior**:
```python
try:
    event = AgentEvent(EventType(event_type), data)
    self.event_callback(event)
except Exception:
    # Don't let event emission errors break planning
    pass  # ⚠️ Silently swallows ValueError from invalid EventType
```

**Fix Needed**: At least log validation errors:

```python
except ValueError as e:
    # Invalid event type - log but don't break planning
    import logging
    logging.warning(f"Invalid event type: {event_type}: {e}")
except Exception as e:
    # Other errors - log but don't break planning
    import logging
    logging.warning(f"Event emission failed: {e}")
```

---

### 4. ⚠️ Inconsistent Event Validation

**Problem**: Different code paths use different validation:
- `_incremental_run()` uses `validate_event_data()` ✅
- `HarmonicPlanner._emit_event()` does NOT validate ❌
- `Naaru._emit_event()` does NOT validate ❌

**Evidence**:
- `src/sunwell/cli/agent/run.py:611` - Uses `validate_event_data()`
- `src/sunwell/naaru/planners/harmonic.py:250` - Direct `AgentEvent()` creation
- `src/sunwell/naaru/naaru.py:206` - Direct `AgentEvent()` creation

**Impact**: Events from HarmonicPlanner and Naaru may have missing required fields.

**Fix Needed**: Use validated factories or add validation to `_emit_event()` methods.

---

## Summary

### Critical
1. ❌ Missing `complete` event in incremental run

### Medium Priority
2. ⚠️ Duplicate `plan_winner` events
3. ⚠️ Event validation errors silently swallowed
4. ⚠️ Inconsistent validation across code paths

---

## Recommended Fixes

1. **Add `complete` event** to `_incremental_run()` (CRITICAL)
2. **Deduplicate `plan_winner`** emissions (check if planner already emitted)
3. **Add logging** to event emission error handlers
4. **Standardize validation** - use validated factories everywhere
