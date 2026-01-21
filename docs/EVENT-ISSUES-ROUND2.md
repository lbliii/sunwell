# Event System Issues - Round 2 Audit

**Status**: Issues Found  
**Date**: 2026-01-20

---

## Issues Found

### 1. ⚠️ Missing `old_score` Field Handling

**Problem**: `plan_refine_complete` event emits `old_score` when improved=True, but Studio doesn't extract or display it.

**Evidence**:
- **Backend**: `src/sunwell/naaru/planners/harmonic.py:673` emits `old_score` in refine_complete
- **Frontend**: `studio/src/stores/agent.ts:519-540` - Handler doesn't extract `old_score`

**Impact**: Cannot display score improvement delta (old → new) in UI.

**Fix Needed**: Extract `old_score` in handler:

```typescript
case 'plan_refine_complete': {
  const round = (data.round as number) ?? 0;
  const improved = (data.improved as boolean) ?? false;
  const oldScore = (data.old_score as number) ?? undefined;  // ADD THIS
  const newScore = (data.new_score as number) ?? undefined;
  const improvement = (data.improvement as number) ?? undefined;
  const reason = (data.reason as string) ?? undefined;

  agentState.update(s => {
    const rounds = [...s.refinementRounds];
    const roundIndex = rounds.findIndex(r => r.round === round);
    if (roundIndex >= 0) {
      rounds[roundIndex] = {
        ...rounds[roundIndex],
        improved,
        old_score: oldScore,  // ADD THIS
        new_score: newScore,
        improvement,
        reason,
      };
    }
    return { ...s, refinementRounds: rounds };
  });
  break;
}
```

Also update `RefinementRound` type:

```typescript
export interface RefinementRound {
  improvements_applied?: string[];
  round: number;
  current_score: number;
  improvements_identified?: string;
  improved: boolean;
  old_score?: number;  // ADD THIS
  new_score?: number;
  improvement?: number;
  reason?: string;
}
```

---

### 2. ⚠️ Error Event Validation May Fail Silently

**Problem**: Error events use `emit()` which validates, but if validation fails, it falls back to unvalidated event. This could mask issues.

**Evidence**:
- `src/sunwell/cli/agent/run.py:666` - `emit("error", {"message": f"Discovery failed: {e}"})`
- `src/sunwell/cli/agent/run.py:828` - `emit("error", {"message": "Interrupted by user"})`
- `src/sunwell/cli/agent/run.py:832` - `emit("error", {"message": str(e)})`

**Current Behavior**: If validation fails, falls back to unvalidated event (line 614-620).

**Impact**: Error events might not have required `message` field if validation fails.

**Fix Needed**: Ensure error events always have `message` field (they do, but validation should be stricter).

---

### 3. ⚠️ Missing Event Handlers (Low Priority)

**Problem**: `plan_expanded` and `plan_assess` events are defined but have no handlers in Studio.

**Evidence**:
- **Backend**: `src/sunwell/adaptive/events.py:65,68` - Events defined
- **Frontend**: `studio/src/stores/agent.ts` - No handlers found

**Impact**: If these events are emitted, they'll be silently ignored.

**Status**: These events may not be used yet (iterative DAG expansion feature). Low priority unless actively used.

---

### 4. ⚠️ `plan_winner` Score Field Inconsistency

**Problem**: `plan_winner` event includes `score` at top level, but frontend tries to get it from `metrics` first, then falls back to top level.

**Evidence**:
- **Backend**: `src/sunwell/naaru/planners/harmonic.py:365-380` - Emits `score` in metrics dict AND potentially at top level
- **Frontend**: `studio/src/stores/agent.ts:559` - `const score = (data.score as number) ?? undefined;`

**Current Behavior**: Frontend correctly gets score from top level (not metrics).

**Impact**: None - works correctly, but could be clearer.

**Recommendation**: Document that `score` is at top level, not in metrics.

---

### 5. ✅ Error Events Use Validated Path

**Good**: Error events in incremental run use `emit()` which validates via `validate_event_data()`.

**Evidence**:
- `src/sunwell/cli/agent/run.py:604-620` - `emit()` function validates events
- All error emissions use this function

**Status**: Working correctly.

---

## Summary

### Critical Issues
- None

### Medium Priority
1. Missing `old_score` field handling in `plan_refine_complete`
2. Error event validation fallback behavior (works but could be stricter)

### Low Priority
3. Missing handlers for `plan_expanded` and `plan_assess` (may not be used)
4. `plan_winner` score field documentation

---

## Recommended Fixes

1. **Add `old_score` handling** in `plan_refine_complete` handler
2. **Update `RefinementRound` type** to include `old_score`
3. **Consider stricter error validation** (fail loudly instead of fallback)
4. **Document event field locations** (score at top level, not metrics)
