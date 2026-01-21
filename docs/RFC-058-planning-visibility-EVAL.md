## 🔍 RFC Evaluation: RFC-058 Planning Visibility

### Executive Summary

RFC-058 proposes comprehensive visibility into harmonic planning by emitting detailed events for candidate generation, scoring, and refinement. The RFC is **well-structured** with clear problem statement and implementation plan, but has **gaps in evidence** for event callback integration and **lacks design alternatives**. Current confidence: **82%** 🟡 — **REVISE** before approval.

**Key Findings**:
- ✅ Harmonic planning infrastructure exists and works
- ✅ PlanMetrics and refinement logic are implemented
- ❌ HarmonicPlanner lacks event callback support (needs implementation)
- ⚠️ Only one design approach presented (should consider alternatives)
- ✅ Studio event handling infrastructure exists

---

### Evidence Quality

| Claim | Evidence | Quality | Status |
|-------|----------|---------|--------|
| Harmonic planning generates multiple candidates | `harmonic.py:254-307` | Direct | ✅ |
| PlanMetrics includes depth, parallelism, balance | `harmonic.py:47-101` | Direct | ✅ |
| Refinement rounds exist | `harmonic.py:512-547` | Direct | ✅ |
| Event system supports streaming | `events.py:23-135`, `agent.ts:346-506` | Direct | ✅ |
| PLAN_WINNER event currently minimal | `agent.py:411-418`, `run.py:624` | Direct | ✅ |
| HarmonicPlanner accepts event callbacks | **NONE** | Missing | ❌ |
| Candidate generation emits events | **NONE** | Missing | ❌ |
| Scoring emits per-candidate events | **NONE** | Missing | ❌ |
| Refinement emits round-by-round events | **NONE** | Missing | ❌ |
| Studio handles new event types | `agent.ts:346-506` | Inferred | ⚠️ |

**Evidence Score**: 28/40
- **Direct code references**: 5 claims (20 points)
- **Inferred from context**: 1 claim (8 points)
- **Missing evidence**: 4 critical claims (0 points)

**Missing Evidence Details**:
1. **Event callback pattern**: RFC assumes HarmonicPlanner can accept callbacks, but current implementation (`harmonic.py:179-223`) has no `event_callback` parameter. Need to verify:
   - How other components pass event callbacks (e.g., `ArtifactExecutor.on_event` pattern)
   - Whether callback should be sync or async
   - Whether callback should be optional or required

2. **Event emission points**: RFC shows code examples but these don't exist yet. Need to verify:
   - Where exactly events should be emitted (inside `_generate_candidates`, `_score_plans_parallel`, `_refine_plan`)
   - Whether events should block planning or be fire-and-forget
   - Error handling if callback raises exception

3. **Event callback propagation**: RFC mentions wiring through `Naaru` → `run.py` → Studio, but need to verify:
   - How `run.py` currently creates HarmonicPlanner (`run.py:784`)
   - Whether `AdaptiveAgent._harmonic_plan` should pass callback (`agent.py:397-400`)
   - Whether callback should be same signature as `AgentEvent` emission

---

### Design Completeness

| Section | Status | Notes |
|---------|--------|-------|
| Executive Summary | ✅ | Clear one-liner |
| Problem Statement | ✅ | Well-motivated with examples |
| Goals/Non-Goals | ✅ | Clear boundaries |
| Design Options | ⚠️ | **Only 1 approach** — should consider alternatives |
| Architecture | ✅ | Detailed flow diagram |
| Implementation Plan | ✅ | Phased with effort estimates |
| Risks & Mitigations | ✅ | Event volume, performance, UI complexity addressed |
| Testing | ✅ | Unit and integration tests outlined |
| Success Metrics | ✅ | Clear acceptance criteria |

**Completeness Score**: 13/15
- Missing: Design alternatives (2 points deducted)

**Design Alternatives to Consider**:

1. **Alternative A: Batch Events** (vs. per-candidate streaming)
   - Emit single `PLAN_CANDIDATES_COMPLETE` with all candidates + scores
   - Pros: Lower event volume, simpler UI updates
   - Cons: Less real-time feedback, larger payloads
   - Tradeoff: Better for high candidate counts (>10)

2. **Alternative B: Lazy Event Emission** (vs. always emit)
   - Only emit detailed events if `--verbose` flag or Studio connected
   - Pros: Zero overhead when not needed, backward compatible
   - Cons: Conditional logic complexity
   - Tradeoff: Performance vs. simplicity

3. **Alternative C: Event Aggregation** (vs. individual events)
   - Emit single `PLAN_DETAILS` event with nested candidate/refinement data
   - Pros: Atomic updates, easier to reason about
   - Cons: Less granular progress updates
   - Tradeoff: Progress visibility vs. event simplicity

---

### HIGH Criticality Validation

#### Claim: HarmonicPlanner can emit events via callback parameter

| Path | Location | Finding | Status |
|------|----------|---------|--------|
| Source | `harmonic.py:179-223` | HarmonicPlanner has no `event_callback` parameter | ❌ |
| Tests | `test_harmonic_planning.py` | No tests for event emission | ❌ |
| Config | N/A | Not applicable | - |

**Agreement**: 0/2 applicable paths — **CONFLICT**

**Finding**: Current `HarmonicPlanner` implementation does not support event callbacks. RFC proposes adding this, but:
- No evidence of callback pattern in HarmonicPlanner
- Need to verify callback signature matches existing patterns (e.g., `ArtifactExecutor.on_event: EventCallback`)
- Need to ensure callback is optional (backward compatible)

**Recommendation**: Add evidence section showing:
1. How `ArtifactExecutor.on_event` pattern works (`executor.py:194`)
2. Proposed callback signature for HarmonicPlanner
3. Backward compatibility strategy (optional callback)

#### Claim: Event types exist in EventType enum

| Path | Location | Finding | Status |
|------|----------|---------|--------|
| Source | `events.py:23-135` | EventType enum exists, but new types not present | ⚠️ |
| Tests | `test_adaptive.py:220-234` | Tests verify EventType exists | ✅ |
| Config | N/A | Not applicable | - |

**Agreement**: 1/2 applicable paths — **PARTIAL**

**Finding**: `EventType` enum exists and is extensible, but RFC-proposed events (`PLAN_CANDIDATE_START`, `PLAN_CANDIDATE_GENERATED`, etc.) are not yet implemented. This is expected (RFC is for future work), but should be noted.

#### Claim: Studio can handle new event types

| Path | Location | Finding | Status |
|------|----------|---------|--------|
| Source | `agent.ts:346-506` | `handleAgentEvent` uses switch statement, needs new cases | ⚠️ |
| Tests | N/A | No TypeScript tests found | ❌ |
| Config | `agent.ts:355-361` | `plan_winner` handler exists, minimal | ✅ |

**Agreement**: 1/2 applicable paths — **PARTIAL**

**Finding**: Studio event handler exists and can be extended, but:
- Switch statement needs new cases for planning visibility events
- No TypeScript tests to verify event handling
- Current `plan_winner` handler only sets `totalTasks` (`agent.ts:355-361`)

---

### Confidence Score

| Component | Score | Max | Notes |
|-----------|-------|-----|-------|
| Evidence Strength | 28 | 40 | Missing 4 critical claims (event callback integration) |
| Self-Consistency | 25 | 30 | Code examples don't match current implementation |
| Recency | 15 | 15 | RFC dated 2026-01-20, codebase is current |
| Completeness | 14 | 15 | Missing design alternatives |
| **Total** | **82** | **100** | 🟡 |

**Confidence**: 82% 🟡 — **MODERATE**

**Breakdown**:
- **Evidence Strength (28/40)**: Missing evidence for event callback integration pattern
- **Self-Consistency (25/30)**: Code examples show proposed changes, not current state (minor inconsistency)
- **Recency (15/15)**: RFC is current, references implemented dependencies
- **Completeness (14/15)**: All sections present, but missing design alternatives

---

### 📋 Action Items

**Critical (must fix before approval)**:
- [ ] **Add evidence for event callback pattern**: Show how HarmonicPlanner should accept callbacks (reference `ArtifactExecutor.on_event` pattern from `executor.py:194`)
- [ ] **Clarify callback signature**: Define whether callback is `Callable[[AgentEvent], None]` or `Callable[[AgentEvent], Awaitable[None]]`
- [ ] **Verify backward compatibility**: Ensure event callback is optional (no breaking changes)
- [ ] **Add design alternatives**: Consider batch events, lazy emission, or event aggregation approaches

**Recommended (should fix)**:
- [ ] **Add evidence for event propagation**: Show how events flow from HarmonicPlanner → Naaru → run.py → Studio
- [ ] **Clarify error handling**: What happens if event callback raises exception?
- [ ] **Add performance benchmarks**: Estimate event emission overhead (RFC claims <5% but no evidence)
- [ ] **Consider event batching**: For high candidate counts, consider batching candidate events

**Open Questions**:
- [ ] Should event callback be sync or async? (Current `AgentEvent` emission in `AdaptiveAgent` is sync via `yield`)
- [ ] Should events block planning or be fire-and-forget? (RFC implies non-blocking)
- [ ] How should Studio handle event ordering? (Events may arrive out of order with parallel candidate generation)
- [ ] Should reasoning capture (Phase 3) be required or truly optional? (RFC says optional but no opt-in mechanism)

---

### Recommendation

**REVISE** 🔄

**Reasoning**:
RFC-058 has a **solid foundation** with clear problem statement, detailed architecture, and phased implementation plan. However, it has **critical gaps** in evidence for event callback integration and lacks design alternatives.

**Key Issues**:
1. **Missing implementation evidence**: RFC shows code examples that don't exist yet (event callback parameter, event emission points)
2. **No design alternatives**: Only one approach presented, should consider batch/lazy/aggregation alternatives
3. **Unclear callback pattern**: Need to verify callback signature matches existing patterns

**Next Steps**:
1. **Gather evidence**: Research how other components (e.g., `ArtifactExecutor`) handle event callbacks
2. **Add design alternatives**: Consider batch events, lazy emission, event aggregation
3. **Clarify callback signature**: Define exact callback type and error handling
4. **Re-run evaluation**: After addressing critical items, re-evaluate for approval

**Approval Criteria** (not yet met):
- ❌ Confidence ≥ 85% (currently 82%)
- ❌ All HIGH criticality claims validated (1/3 validated)
- ❌ At least 2 design options analyzed (only 1 presented)
- ✅ No fundamental design flaws (architecture is sound)

---

### Evidence References

**Direct Code References**:
- `src/sunwell/naaru/planners/harmonic.py:254-307` — `plan_with_metrics()` generates candidates
- `src/sunwell/naaru/planners/harmonic.py:47-101` — `PlanMetrics` dataclass with all fields
- `src/sunwell/naaru/planners/harmonic.py:512-547` — `_refine_plan()` refinement logic
- `src/sunwell/adaptive/events.py:23-135` — `EventType` enum and `AgentEvent` dataclass
- `src/sunwell/adaptive/agent.py:411-418` — Current minimal `PLAN_WINNER` emission
- `studio/src/stores/agent.ts:346-506` — Studio event handler

**Missing Evidence**:
- Event callback parameter in HarmonicPlanner (needs implementation)
- Event emission in `_generate_candidates()` (needs implementation)
- Event emission in `_score_plans_parallel()` (needs implementation)
- Event emission in `_refine_plan()` (needs implementation)

---

**Evaluation Date**: 2026-01-20  
**Evaluator**: RFC Evaluation System  
**Confidence**: 82% 🟡
