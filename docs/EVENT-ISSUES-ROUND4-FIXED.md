# Event System Issues - Round 4 Fixed

**Status**: Fixed  
**Date**: 2026-01-20

---

## Issues Fixed

### 1. ✅ Fixed `complete` Event Field Names

**Problem**: Incremental run emitted `complete` event with wrong field names (`completed`/`failed` instead of `tasks_completed`/`tasks_failed`).

**Fix**: Updated to use validated event data with correct field names:

```python
complete_data = validate_event_data(EventType.COMPLETE, {
    "tasks_completed": len(result.completed),
    "tasks_failed": len(result.failed),
    "completed": len(result.completed),  # Alias for compatibility
    "failed": len(result.failed),  # Alias for compatibility
    "duration_s": elapsed,
    "learnings_count": learnings_count,
})
```

**Files Changed**:
- `src/sunwell/cli/agent/run.py:810-817` - Fixed complete event emission

---

### 2. ✅ Fixed Duplicate `plan_winner` Events

**Problem**: Both HarmonicPlanner and Naaru emitted `plan_winner` events, causing duplicates.

**Fix**: 
- HarmonicPlanner sets `_plan_winner_emitted = True` after emitting
- Naaru checks this flag before emitting its own `plan_winner`

**Files Changed**:
- `src/sunwell/naaru/planners/harmonic.py:370` - Set flag after emission
- `src/sunwell/naaru/naaru.py:474-486` - Check flag before emission

---

### 3. ✅ Added Error Logging to Event Emission

**Problem**: Event emission errors were silently swallowed, making debugging difficult.

**Fix**: Added logging for ValueError (invalid event type) and other exceptions:

```python
except ValueError as e:
    import logging
    logging.warning(f"Invalid event type '{event_type}': {e}")
except Exception as e:
    import logging
    logging.warning(f"Event emission failed for '{event_type}': {e}")
```

**Files Changed**:
- `src/sunwell/naaru/planners/harmonic.py:252-257` - Added logging

---

### 4. ✅ Added Duration Tracking to Incremental Run

**Problem**: `complete` event didn't include `duration_s` field.

**Fix**: Track `start_time` and calculate `elapsed` duration:

```python
start_time = datetime.now()
# ... execution ...
elapsed = (datetime.now() - start_time).total_seconds()
```

**Files Changed**:
- `src/sunwell/cli/agent/run.py:601` - Added start_time tracking
- `src/sunwell/cli/agent/run.py:816` - Calculate elapsed duration

---

## Summary

All Round 4 issues have been fixed:
- ✅ Complete event uses correct field names
- ✅ Duplicate plan_winner events prevented
- ✅ Event emission errors now logged
- ✅ Duration tracking added to incremental run

The event system is now more robust with better error visibility and correct field names.
