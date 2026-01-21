# Event System Issues Found

**Status**: Issues Identified  
**Date**: 2026-01-20

---

## Critical Issues

### 1. ❌ Missing Handler for `plan_refine_attempt` Event

**Problem**: HarmonicPlanner emits `plan_refine_attempt` events (line 658 in `harmonic.py`), but Studio has no handler for this event type.

**Impact**: Refinement attempt progress is not displayed in the UI.

**Evidence**:
- **Backend**: `src/sunwell/naaru/planners/harmonic.py:658` emits `plan_refine_attempt`
- **Frontend**: `studio/src/stores/agent.ts` - No case for `plan_refine_attempt`

**Fix Needed**: Add handler in `studio/src/stores/agent.ts`:

```typescript
case 'plan_refine_attempt': {
  const round = (data.round as number) ?? 0;
  const improvementsApplied = (data.improvements_applied as string[]) ?? [];
  
  agentState.update(s => {
    const rounds = [...s.refinementRounds];
    const roundIndex = rounds.findIndex(r => r.round === round);
    if (roundIndex >= 0) {
      rounds[roundIndex] = {
        ...rounds[roundIndex],
        improvements_applied: improvementsApplied,
      };
    }
    return { ...s, refinementRounds: rounds };
  });
  break;
}
```

---

### 2. ⚠️ Naaru Created Twice (Inefficient)

**Problem**: In `src/sunwell/cli/agent/run.py`, Naaru is created twice:
1. Line 322-328: First creation (without event callback)
2. Line 360-367: Second creation (with event callback) - rebuilds entire object

**Impact**: Unnecessary object creation, but functionally works.

**Evidence**:
```python
# Line 322: First creation
naaru = Naaru(...)

# Line 357: Set callback
if isinstance(planner, HarmonicPlanner):
    planner.event_callback = validated_emitter.emit

# Line 360: Second creation (rebuild)
naaru = Naaru(...)
```

**Fix Needed**: Set event callback BEFORE first Naaru creation, or only create once.

---

### 3. ⚠️ Event Callback Timing

**Problem**: Event callback is set on HarmonicPlanner AFTER Naaru is created the first time, but BEFORE planning starts. This should work, but the double creation is confusing.

**Current Flow**:
1. HarmonicPlanner created (line 267) with `event_callback=None`
2. Naaru created first time (line 322)
3. Event callback set on planner (line 357)
4. Naaru created second time (line 360) - planner already has callback

**Impact**: Works correctly, but inefficient and confusing.

**Fix Needed**: Set event callback before first Naaru creation:

```python
# Set up event callback BEFORE creating Naaru
if json_output:
    # ... setup validated_emitter ...
    if isinstance(planner, HarmonicPlanner):
        planner.event_callback = validated_emitter.emit

# Create Naaru once with callback already set
naaru = Naaru(...)
```

---

## Verification Checklist

### Events Emitted by HarmonicPlanner

- [x] `plan_candidate_start` - ✅ Has handler
- [x] `plan_candidate_generated` - ✅ Has handler
- [x] `plan_candidates_complete` - ✅ Has handler
- [x] `plan_candidate_scored` - ✅ Has handler
- [x] `plan_scoring_complete` - ✅ Has handler
- [x] `plan_refine_start` - ✅ Has handler
- [ ] `plan_refine_attempt` - ❌ **MISSING HANDLER**
- [x] `plan_refine_complete` - ✅ Has handler
- [x] `plan_refine_final` - ✅ Has handler

### Event Data Fields

- [x] `plan_candidate_generated` includes `candidate_index`, `artifact_count`, `progress`, `total_candidates`, `variance_config` - ✅ All handled
- [x] `plan_candidate_scored` includes `candidate_index`, `score`, `metrics`, `progress` - ✅ All handled
- [x] `plan_refine_start` includes `round`, `total_rounds`, `current_score`, `improvements_identified` - ✅ All handled
- [ ] `plan_refine_attempt` includes `round`, `improvements_applied` - ❌ **NOT HANDLED**

---

## Summary

1. **Critical**: Missing `plan_refine_attempt` handler in Studio
2. **Minor**: Naaru created twice (inefficient but works)
3. **Minor**: Event callback setup timing could be cleaner

---

## Recommended Fixes

1. Add `plan_refine_attempt` handler to `studio/src/stores/agent.ts`
2. Refactor Naaru creation to happen once, after event callback is set
3. Consider adding event schema validation for refinement events
