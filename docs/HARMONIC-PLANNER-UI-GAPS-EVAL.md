# Evaluation: HarmonicPlanner UI Event Gaps

**Evaluator**: AI Assistant  
**Date**: 2026-01-20  
**Document**: `HARMONIC-PLANNER-UI-GAPS.md`

---

## Overall Assessment

**Confidence**: 85% 🟡 MODERATE

The document accurately identifies two real issues with clear evidence, but the proposed fix for Issue #2 has a technical flaw that would prevent implementation.

---

## Evidence Quality: 90% ✅

### Strengths

1. **Accurate Code References**: All file:line references are correct:
   - ✅ `harmonic.py:378` - Score is indeed in `metrics.score`
   - ✅ `agent.ts:647` - Handler does extract top-level `score`
   - ✅ `PlanningPanel.svelte:47` - UI accesses `metrics.score`
   - ✅ `harmonic.py:388` - Emits `variance_strategy` enum value
   - ✅ `CandidateComparison.svelte:65` - UI expects `variance_config.prompt_style`

2. **Clear Problem Statements**: Both issues are well-described with:
   - Current behavior
   - Expected behavior
   - Impact assessment

3. **Working Code Examples**: Code snippets accurately reflect the actual implementation.

### Minor Gaps

- Issue #1: Could mention that `plan_candidate_scored` events emit score at top level (line 330), creating additional inconsistency
- Issue #2: Missing verification that `configs` array is accessible when emitting `plan_winner`

---

## Design Completeness: 70% ⚠️

### Issue #1: Score Location - COMPLETE ✅

**Fix Options**: Both options are viable:
- Option A (emit both): Simple, backward-compatible
- Option B (UI-only): Cleaner but requires more changes

**Recommendation**: Option A is reasonable for backward compatibility.

### Issue #2: variance_config - INCOMPLETE ⚠️

**Critical Flaw**: The proposed fix assumes `configs` is available in `plan_with_metrics()`, but:

```372:391:src/sunwell/naaru/planners/harmonic.py
        self._emit_event("plan_winner", {
            "tasks": len(best_graph),
            "artifact_count": len(best_graph),
            "selected_index": selected_index,
            "total_candidates": len(candidates),
            "metrics": {
                "score": best_metrics.score,
                "depth": best_metrics.depth,
                "width": best_metrics.width,
                "leaf_count": best_metrics.leaf_count,
                "parallelism_factor": best_metrics.parallelism_factor,
                "balance_factor": best_metrics.balance_factor,
                "file_conflicts": best_metrics.file_conflicts,
                "estimated_waves": best_metrics.estimated_waves,
            },
            "selection_reason": self._format_selection_reason(best_metrics, scored),
            "variance_strategy": self.variance.value,
            "refinement_rounds": refinement_rounds_applied,
            "final_score_improvement": best_metrics.score - initial_score if refinement_rounds_applied > 0 else 0.0,
        })
```

**Problem**: `configs` is created inside `_generate_candidates()` (line 460) but not returned or stored. The proposed fix references `configs[selected_index]` which doesn't exist in scope.

**Required Changes**:
1. `_generate_candidates()` must return both candidates AND configs (or track original indices)
2. OR: Store configs as instance state during generation
3. OR: Track original candidate index before sorting (since `selected_index` is always 0 after sorting)

**Better Solution**:
```python
# In _generate_candidates(), return tuple:
return candidates, configs

# In plan_with_metrics():
candidates, configs = await self._generate_candidates(goal, context)
# ... scoring and sorting ...
# Find original index before sorting:
original_index = scored[0][2] if len(scored[0]) > 2 else 0  # Would need to track this
selected_config = configs[original_index] if original_index < len(configs) else {}
```

---

## Clarity & Structure: 95% ✅

### Strengths

- Clear status indicators (⚠️, ✅)
- Well-organized sections
- Good use of code examples
- Impact assessment for each issue
- Testing checklist at end

### Minor Improvements

- Could add "Confidence" scores per issue
- Could reference related RFCs (RFC-058)
- Could mention that `plan_candidate_scored` also has score inconsistency

---

## Actionability: 75% ⚠️

### Issue #1: READY TO IMPLEMENT ✅

The fix is straightforward:
```python
self._emit_event("plan_winner", {
    "score": best_metrics.score,  # Add this
    "metrics": {
        "score": best_metrics.score,  # Keep existing
        ...
    },
    ...
})
```

### Issue #2: NEEDS DESIGN WORK ⚠️

The proposed fix won't work as written. Requires:
1. Refactoring `_generate_candidates()` to return configs
2. OR tracking original indices through sorting
3. OR storing configs as instance state

**Recommendation**: Add a design step before implementation.

---

## Missing Analysis

1. **Index Mapping**: After sorting by score, `selected_index` is always 0, but the original candidate index (for config lookup) is lost. Need to track this.

2. **plan_candidate_scored Consistency**: These events emit score at top level (line 330), creating the same inconsistency pattern.

3. **Fallback Case**: When `candidates` is empty and fallback is used (line 309-318), no variance_config would be available anyway.

---

## Recommendations

### Immediate Actions

1. ✅ **Issue #1**: Implement Option A (emit score at both levels)
2. ⚠️ **Issue #2**: Redesign fix to handle config access properly

### Design Options for Issue #2

**Option A**: Return configs from `_generate_candidates()`
```python
async def _generate_candidates(...) -> tuple[list[ArtifactGraph], list[dict]]:
    # ... existing code ...
    return candidates, configs

# In plan_with_metrics():
candidates, configs = await self._generate_candidates(goal, context)
# Track original index before sorting:
scored_with_index = [(g, m, i) for i, (g, m) in enumerate(zip(candidates, scores))]
scored_with_index.sort(key=lambda x: x[1].score, reverse=True)
best_graph, best_metrics, original_index = scored_with_index[0]
selected_config = configs[original_index] if original_index < len(configs) else {}
```

**Option B**: Store configs as instance state
```python
self._candidate_configs: list[dict] | None = None

# In _generate_candidates():
self._candidate_configs = configs

# In plan_with_metrics():
selected_config = (self._candidate_configs[original_index] 
                   if self._candidate_configs and original_index < len(self._candidate_configs)
                   else {})
```

**Recommendation**: Option A (return tuple) is cleaner and more functional.

---

## Testing Gaps

The testing checklist is good but missing:
- [ ] Verify fallback case (no candidates) doesn't crash
- [ ] Verify configs array length matches candidates length
- [ ] Test with different variance strategies
- [ ] Verify selected_index mapping after sorting

---

## Final Verdict

**Status**: ✅ **APPROVED WITH MODIFICATIONS**

The document correctly identifies real issues with strong evidence, but Issue #2's fix needs redesign. Recommend:

1. ✅ Implement Issue #1 fix immediately
2. ⚠️ Redesign Issue #2 fix (use Option A from recommendations)
3. 📝 Update document with corrected fix before implementation

**Confidence Breakdown**:
- Evidence: 90% (accurate references)
- Design: 70% (Issue #2 fix incomplete)
- Clarity: 95% (well-structured)
- Actionability: 75% (Issue #1 ready, Issue #2 needs work)

**Overall**: 85% MODERATE confidence - ready for Issue #1, needs design work for Issue #2.
