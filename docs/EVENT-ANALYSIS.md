# Event System Analysis — Codebase-Wide Audit

**Status**: Analysis Complete  
**Created**: 2026-01-20  
**Scope**: All event emission patterns across Python → Rust → TypeScript

---

## Executive Summary

The event system has **3 main emission patterns** with **inconsistencies**:

1. ✅ **Standard Pattern** (Most code): Uses `AgentEvent` class → `to_dict()` → NDJSON
2. ⚠️ **Custom Pattern** (Some code): Custom dicts with manual JSON serialization
3. ❌ **Missing Events** (Incremental execution): Uses `artifact_id` instead of `task_id`

---

## Event Emission Patterns

### Pattern 1: Standard AgentEvent (✅ Preferred)

**Used in:**
- `src/sunwell/cli/agent/run.py:274-276` - Main agent run
- `src/sunwell/adaptive/renderer.py:351` - JSONRenderer
- `src/sunwell/naaru/naaru.py:191-210` - Naaru._emit_event()
- `src/sunwell/naaru/planners/harmonic.py:239-253` - HarmonicPlanner events

**Format:**
```python
from sunwell.adaptive.events import AgentEvent, EventType
event = AgentEvent(EventType.TASK_START, {"task_id": "..."})
print(json.dumps(event.to_dict()), file=sys.stdout, flush=True)
```

**Output:**
```json
{"type": "task_start", "data": {"task_id": "..."}, "timestamp": 1234.5}
```

### Pattern 2: Custom Dict (⚠️ Inconsistent)

**Used in:**
- `src/sunwell/cli/backlog_cmd.py:356-360` - Backlog goal execution
- `src/sunwell/cli/agent/run.py:608-615` - Incremental run (fallback)
- `src/sunwell/cli/backlog_cmd.py:371-375` - Error handling

**Format:**
```python
print(json.dumps({
    "type": event_type,  # String, not EventType enum
    "data": data or {},
    "timestamp": time.time(),
}), flush=True)
```

**Issues:**
- Event types are strings, not validated against `EventType` enum
- No guarantee of format consistency
- May emit unknown event types that Studio doesn't handle

### Pattern 3: Direct Event Streaming (✅ Good)

**Used in:**
- `src/sunwell/cli/main.py:243` - AdaptiveAgent.run() yields events
- `src/sunwell/cli/backlog_cmd.py:355` - Naaru.run() yields events

**Format:**
```python
async for event in naaru.run(goal, context):
    print(json.dumps({
        "type": event.type.value if hasattr(event.type, 'value') else str(event.type),
        "data": event.data,
        "timestamp": event.timestamp,
    }), flush=True)
```

**Issues:**
- Redundant serialization (event already has `to_dict()`)
- Should use `event.to_dict()` directly

---

## Field Name Inconsistencies

### Task vs Artifact Terminology

**Problem**: Incremental execution uses `artifact_id` but Studio expects `task_id`

**Evidence:**
```python
# src/sunwell/cli/agent/run.py:700
emit("task_start", {"artifact_id": spec.id, "description": spec.description})
# ↑ Uses artifact_id

# studio/src/stores/agent.ts:365
const taskId = (data.task_id as string) ?? `task-${Date.now()}`;
# ↑ Expects task_id
```

**Impact**: Studio may not correctly track artifact execution progress

**Fix Needed**: Standardize on `task_id` (or map `artifact_id` → `task_id`)

### Event Data Fields

**Required fields by Studio:**

| Event Type | Required Fields | Current Status |
|------------|----------------|----------------|
| `plan_start` | `goal` | ✅ Emitted |
| `plan_winner` | `tasks` (count) | ✅ Emitted |
| `task_start` | `task_id`, `description` | ⚠️ Uses `artifact_id` |
| `task_progress` | `task_id`, `progress` | ⚠️ May use `artifact_id` |
| `task_complete` | `task_id`, `duration_ms` | ⚠️ Uses `artifact_id` |
| `task_failed` | `task_id`, `error` | ⚠️ Uses `artifact_id` |
| `memory_learning` | `fact` | ✅ Emitted |
| `complete` | `completed`, `failed` | ✅ Emitted |
| `error` | `message` | ✅ Emitted |

---

## Event Flow Paths

### Path 1: CLI Agent Run (Standard)

```
sunwell agent run --json <goal>
    ↓
_run_agent() sets up emit_json callback
    ↓
Naaru.run() → _emit_event() → event_callback
    ↓
stdout (NDJSON)
    ↓
Rust bridge → Studio
```

**Status**: ✅ Working, standardized

### Path 2: Incremental Run

```
sunwell agent run --incremental --json <goal>
    ↓
_incremental_run() uses custom emit() function
    ↓
emit() → AgentEvent (with fallback)
    ↓
stdout (NDJSON)
    ↓
Rust bridge → Studio
```

**Status**: ⚠️ Uses `artifact_id` instead of `task_id`

### Path 3: Backlog Goal Execution

```
sunwell backlog run <goal_id> --json
    ↓
_run_backlog_goal() → naaru.run() yields events
    ↓
Manual serialization (should use to_dict())
    ↓
stdout (NDJSON)
    ↓
Rust bridge → Studio
```

**Status**: ⚠️ Redundant serialization, should use `event.to_dict()`

### Path 4: Harmonic Planning

```
HarmonicPlanner.plan_with_metrics()
    ↓
_emit_event() → event_callback (if set)
    ↓
AgentEvent → to_dict()
    ↓
stdout (NDJSON)
    ↓
Rust bridge → Studio
```

**Status**: ✅ Working, but callback only set in JSON mode

---

## Critical Issues

### Issue 1: Field Name Mismatch (HIGH PRIORITY)

**Location**: `src/sunwell/cli/agent/run.py:700, 720, 723`

**Problem**: Incremental execution emits `artifact_id` but Studio expects `task_id`

**Impact**: Studio cannot track artifact execution properly

**Fix**:
```python
# Change from:
emit("task_start", {"artifact_id": spec.id, ...})

# To:
emit("task_start", {"task_id": spec.id, "artifact_id": spec.id, ...})
# Or standardize on task_id everywhere
```

### Issue 2: Event Callback Not Always Set (MEDIUM PRIORITY)

**Location**: `src/sunwell/cli/agent/run.py:267-278`

**Problem**: Event callback only set up for HarmonicPlanner, not always available

**Impact**: Events may be silently dropped

**Fix**: Set up callback earlier, before planner creation

### Issue 3: Redundant Serialization (LOW PRIORITY)

**Location**: `src/sunwell/cli/backlog_cmd.py:356-360`

**Problem**: Manual dict construction instead of `event.to_dict()`

**Impact**: Code duplication, potential format drift

**Fix**: Use `event.to_dict()` directly

### Issue 4: Missing Event Validation (MEDIUM PRIORITY)

**Problem**: No validation that emitted events match Studio expectations

**Impact**: Runtime errors if format drifts

**Fix**: Add event schema validation

---

## Event Coverage Analysis

### Events Emitted by Naaru.run()

✅ `plan_start` - Line 393  
✅ `plan_winner` - Line 385, 475  
✅ `complete` - Line 418-424  
✅ `learning` - Line 1006  
❌ `task_start` - **NOT EMITTED** (only in incremental run)  
❌ `task_progress` - **NOT EMITTED**  
❌ `task_complete` - **NOT EMITTED** (only in incremental run)  
❌ `task_failed` - **NOT EMITTED** (only in incremental run)

### Events Emitted by Incremental Run

✅ `plan_start` - Line 628  
✅ `plan_winner` - Line 632  
✅ `task_start` - Line 700  
✅ `task_progress` - Line 708, 734  
✅ `task_complete` - Line 720  
✅ `task_failed` - Line 723  
✅ `complete` - Line 754  
❌ `memory_learning` - **NOT EMITTED** (extracted but not emitted)

### Events Emitted by HarmonicPlanner

✅ `plan_candidate_start` - Line 427  
✅ `plan_candidate_generated` - Line 440  
✅ `plan_candidates_complete` - Line 465  
✅ `plan_candidate_scored` - Line 323  
✅ `plan_scoring_complete` - Line 341  
✅ `plan_refine_start` - Line 640  
✅ `plan_refine_attempt` - Line 658  
✅ `plan_refine_complete` - Line 670, 679  
✅ `plan_refine_final` - Line 687  
✅ `plan_winner` - Line 365

---

## Recommendations

### Immediate Fixes

1. **Standardize field names**: Use `task_id` consistently (or map `artifact_id` → `task_id`)
2. **Fix incremental events**: Ensure all events use standard `AgentEvent` format
3. **Add event validation**: Validate events before emission

### Short-term Improvements

1. **Unify emission**: All code paths use `AgentEvent.to_dict()`
2. **Add event tests**: Test that Studio receives all expected events
3. **Document event contract**: Clear spec of required fields per event type

### Long-term Improvements

1. **Event schema validation**: Runtime checks for required fields
2. **TypeScript types**: Generate types from Python EventType enum
3. **Event versioning**: Handle format changes gracefully

---

## Files Requiring Changes

### High Priority

1. `src/sunwell/cli/agent/run.py:700, 720, 723` - Fix `artifact_id` → `task_id`
2. `src/sunwell/cli/agent/run.py:267-278` - Ensure callback always set

### Medium Priority

3. `src/sunwell/cli/backlog_cmd.py:356-360` - Use `event.to_dict()`
4. `src/sunwell/naaru/naaru.py` - Emit task events during execution

### Low Priority

5. `src/sunwell/cli/agent/run.py:608-615` - Remove fallback, always use AgentEvent
6. Add event validation layer

---

## Testing Checklist

- [ ] Studio receives `plan_start` event
- [ ] Studio receives `plan_winner` with `tasks` count
- [ ] Studio receives `task_start` with `task_id` (not `artifact_id`)
- [ ] Studio receives `task_progress` updates
- [ ] Studio receives `task_complete` with `duration_ms`
- [ ] Studio receives `task_failed` with error message
- [ ] Studio receives `complete` event at end
- [ ] Studio receives `error` event on failure
- [ ] All events have `type`, `data`, `timestamp` fields
- [ ] Event types match `EventType` enum values

---

## References

- `src/sunwell/adaptive/events.py` - Event definitions
- `src/sunwell/cli/agent/run.py` - Main emission point
- `studio/src-tauri/src/agent.rs` - Rust bridge
- `studio/src/stores/agent.ts` - Studio handlers
- `docs/EVENT-STANDARD.md` - Standardization plan
- RFC-053: Studio Agent Bridge
- RFC-058: Planning Visibility
