# Event System Issues Fixed

**Status**: Fixed  
**Date**: 2026-01-20

---

## Issues Fixed

### 1. ✅ Missing Handler for `plan_refine_attempt` Event

**Problem**: HarmonicPlanner emits `plan_refine_attempt` events, but Studio had no handler.

**Fix**: Added handler in `studio/src/stores/agent.ts`:

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
    } else {
      // Create new round entry if it doesn't exist
      rounds.push({
        round,
        current_score: 0,
        improvements_identified: '',
        improved: false,
        improvements_applied: improvementsApplied,
      });
    }
    return { ...s, refinementRounds: rounds };
  });
  break;
}
```

**Files Changed**:
- `studio/src/stores/agent.ts` - Added handler
- `studio/src/lib/types.ts` - Added `improvements_applied?: string[]` to `RefinementRound`

---

### 2. ✅ Naaru Created Twice (Inefficient)

**Problem**: Naaru was created twice - once before setting event callback, then again after.

**Fix**: Refactored to set event callback BEFORE creating Naaru:

```python
# Set up event callback BEFORE creating Naaru
if json_output:
    # ... setup validated_emitter ...
    if isinstance(planner, HarmonicPlanner):
        planner.event_callback = validated_emitter.emit

# Create Naaru once with callback already configured
naaru = Naaru(...)
```

**Files Changed**:
- `src/sunwell/cli/agent/run.py` - Refactored Naaru creation

---

### 3. ✅ TypeScript Import Errors

**Problem**: Missing imports for `get` and `PlanCandidate` types.

**Fix**: Added imports:

```typescript
import { writable, derived, get } from 'svelte/store';
import type { 
  AgentState, 
  AgentEvent, 
  Task,
  Concept,
  ConceptCategory,
  PlanCandidate  // Added
} from '$lib/types';
```

**Files Changed**:
- `studio/src/stores/agent.ts` - Added imports

---

### 4. ✅ Unused Variables

**Problem**: `totalCandidates` was declared but never used in event handlers.

**Fix**: Removed unused variable declarations.

**Files Changed**:
- `studio/src/stores/agent.ts` - Removed unused variables

---

### 5. ✅ Type Error in plan_winner Handler

**Problem**: Code tried to access `metrics?.score` but `score` is not in the metrics type.

**Fix**: Removed incorrect property access:

```typescript
// Before (WRONG):
const score = (data.score as number) ?? metrics?.score ?? undefined;

// After (CORRECT):
const score = (data.score as number) ?? undefined;
```

**Files Changed**:
- `studio/src/stores/agent.ts` - Fixed score access

---

## Verification

### All Planning Events Now Handled

- [x] `plan_candidate_start` - ✅ Handler exists
- [x] `plan_candidate_generated` - ✅ Handler exists
- [x] `plan_candidates_complete` - ✅ Handler exists
- [x] `plan_candidate_scored` - ✅ Handler exists
- [x] `plan_scoring_complete` - ✅ Handler exists
- [x] `plan_refine_start` - ✅ Handler exists
- [x] `plan_refine_attempt` - ✅ **NOW HANDLED** (was missing)
- [x] `plan_refine_complete` - ✅ Handler exists
- [x] `plan_refine_final` - ✅ Handler exists

---

## Summary

All planning visibility events are now properly wired:
- ✅ All events have handlers
- ✅ Type definitions updated
- ✅ TypeScript errors fixed
- ✅ Code optimized (single Naaru creation)

The frontend will now receive and display all planning candidate completion signals correctly.
