# HarmonicPlanner UI Event Gaps

**Status**: Issues Found  
**Date**: 2026-01-20

---

## Issues Found

### 1. ⚠️ `plan_winner` Score Location Mismatch

**Problem**: HarmonicPlanner emits `score` in `metrics.score`, but UI expects it at top level OR in metrics.

**Evidence**:
- **Backend** (`harmonic.py:378`): Emits `metrics.score` 
- **Frontend** (`agent.ts:647`): Extracts `score` at top level: `const score = (data.score as number) ?? undefined`
- **UI** (`PlanningPanel.svelte:47`): Tries to access `selectedCandidate.metrics.score`

**Current Flow**:
```python
# HarmonicPlanner emits:
{
  "metrics": {
    "score": best_metrics.score,  # Score is HERE
    "depth": ...,
    ...
  }
}
```

```typescript
// Frontend handler extracts:
const score = (data.score as number) ?? undefined;  // Looks for top-level score
const metrics = (data.metrics as PlanCandidate['metrics']) ?? undefined;  // Gets metrics (with score inside)
```

**Impact**: 
- ✅ Works because `metrics.score` exists and UI accesses `selectedCandidate.metrics.score`
- ⚠️ But handler also tries to use top-level `score` which doesn't exist
- ⚠️ Inconsistent: some places use `candidate.score`, others use `candidate.metrics.score`

**Fix Options**:
1. **Option A**: Emit `score` at top level AND in metrics (for compatibility)
2. **Option B**: Update UI to always use `metrics.score` (cleaner, but requires UI changes)

**Recommendation**: Option A (emit both) for backward compatibility.

---

### 2. ⚠️ Missing `variance_config` in `plan_winner` Event

**Problem**: `plan_winner` emits `variance_strategy` (enum value like "prompting") but UI expects `variance_config.prompt_style` (specific config like "default", "parallel_first").

**Evidence**:
- **Backend** (`harmonic.py:388`): Emits `"variance_strategy": self.variance.value` (e.g., "prompting")
- **UI** (`CandidateComparison.svelte:63`): Displays `candidate.variance_config?.prompt_style ?? 'default'`
- **Issue**: Selected candidate might not have `variance_config` if it wasn't in the candidates array

**Current Flow**:
```python
# plan_winner emits:
{
  "variance_strategy": "prompting",  # Enum value, not config
  "selected_index": 0,
  ...
}
```

```typescript
// UI tries to display:
{candidate.variance_config?.prompt_style ?? 'default'}  // undefined if not in candidates array
```

**Impact**: 
- Strategy column shows "default" for selected candidate even if it used a different strategy
- Less informative than showing actual strategy used

**Fix**: Include `variance_config` in `plan_winner` event:
```python
# Find the selected candidate's variance config
selected_candidate_config = configs[selected_index] if selected_index < len(configs) else {}

self._emit_event("plan_winner", {
    ...
    "variance_config": {
        "prompt_style": selected_candidate_config.get("prompt_style", "default"),
        "temperature": selected_candidate_config.get("temperature"),
        "constraint": selected_candidate_config.get("constraint"),
    },
})
```

---

### 3. ✅ `plan_refine_final` Not Used (Not a Problem)

**Status**: Event is emitted but UI doesn't use it - this is fine.

**Evidence**:
- HarmonicPlanner emits `plan_refine_final` with summary stats
- UI only uses individual round events (`plan_refine_start`, `plan_refine_attempt`, `plan_refine_complete`)
- This is intentional - UI shows round-by-round timeline, not summary

**Impact**: None - event is emitted but not needed by UI.

---

### 4. ✅ All Required Metrics Emitted

**Status**: All metrics needed by UI are present.

**UI Displays**:
- Score ✅ (in metrics.score)
- Depth ✅
- Parallelism ✅ (parallelism_factor)
- Balance ✅ (balance_factor)
- Waves ✅ (estimated_waves)
- Conflicts ✅ (file_conflicts)

**HarmonicPlanner Emits**: All of the above ✅

---

## Summary

### Critical Issues
- None - UI works correctly

### Minor Issues
1. ⚠️ Score location inconsistency (works but confusing)
2. ⚠️ Missing variance_config in plan_winner (shows "default" instead of actual strategy)

### Recommendations

1. **Emit score at top level** for consistency:
```python
self._emit_event("plan_winner", {
    "score": best_metrics.score,  # Add top-level score
    "metrics": {
        "score": best_metrics.score,  # Keep in metrics too
        ...
    },
})
```

2. **Include variance_config in plan_winner**:
```python
# Track configs used for each candidate
selected_config = configs[selected_index] if selected_index < len(configs) else {}

self._emit_event("plan_winner", {
    ...
    "variance_config": {
        "prompt_style": selected_config.get("prompt_style", "default"),
        "temperature": selected_config.get("temperature"),
    },
})
```

---

## Testing Checklist

- [ ] Verify `plan_winner` includes top-level `score`
- [ ] Verify `plan_winner` includes `variance_config` with actual strategy used
- [ ] Verify UI displays correct strategy for selected candidate
- [ ] Verify UI displays score correctly (both locations work)
