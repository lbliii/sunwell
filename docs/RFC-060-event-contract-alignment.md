# RFC-060: Event Contract Alignment — Single Source of Truth for Event Schemas

**Status**: Draft → Evaluated  
**Created**: 2026-01-20  
**Evaluated**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 90% 🟢 (post-evaluation)  
**Estimated Effort**: ~3 weeks, ~800 LOC  
**Depends on**: 
- RFC-053 (Studio Agent Bridge) — Event streaming ✅ Implemented
- RFC-058 (Planning Visibility) — Harmonic planning events ✅ Implemented
- RFC-059 (Observability Completeness) — Schema validation ✅ Partially implemented

**Enables**:
- Type-safe event contracts across Python/Rust/TypeScript
- Automatic schema validation preventing drift
- Better developer experience with generated types
- Reduced bugs from contract mismatches
- Easier event system evolution

---

## Summary

The event system has **8 critical misalignments** between Python schemas, JSON schema, TypeScript types, and actual emissions. The root cause is **no single source of truth** — schemas, types, and emissions have drifted independently.

**Current state**:
- Python schemas (`event_schema.py:32-37`) incomplete (missing RFC-058 fields)
- JSON schema (`agent-events.schema.json:355-393`) out of sync
- TypeScript types manually maintained (`agent.ts:642-668`, risk of drift)
- Actual emissions don't match schemas (`harmonic.py:372-391`)
- Frontend handlers expect different fields than backend emits

**Solution**: Establish Python schemas as the **single source of truth**, with automatic code generation for:
1. JSON schema (for validation)
2. TypeScript types (for frontend)
3. Runtime validation (for backend)
4. Documentation (for contracts)

**One-liner**: Transform event schemas from manually maintained, drift-prone definitions into a single source of truth with automatic code generation and validation.

---

## Goals and Non-Goals

### Goals

1. **Single source of truth** — Python `TypedDict` schemas are the canonical definition
2. **Automatic code generation** — JSON schema and TypeScript types generated from Python
3. **Runtime validation** — All event emissions validated against schemas
4. **Contract alignment** — Fix all 8 critical misalignments identified
5. **CI enforcement** — Prevent schema drift via automated checks

### Non-Goals

- **Event versioning** — Backward compatibility maintained, no versioning system
- **Breaking changes** — All fixes are additive or backward-compatible
- **Performance optimization** — Validation overhead acceptable (events are infrequent)
- **Historical migration** — Only affects new/updated events, no migration of logs
- **Rust schema validation** — Rust bridge forwards JSON as-is (Python/TypeScript sufficient)

---

## Motivation

### The Current State

**What's working**:
- Event streaming infrastructure (Python → Rust → TypeScript) ✅
- Basic event schemas exist (`event_schema.py`) ✅
- Frontend handlers work (with defensive coding) ✅
- JSON schema exists (but incomplete) ✅

**What's broken**:
- **8 critical misalignments** between schemas, emissions, and frontend
- **No single source of truth** — schemas, types, and emissions drift independently
- **Manual type maintenance** — TypeScript types manually written, risk of drift
- **Incomplete schemas** — RFC-058 fields missing from `PlanWinnerData`
- **No validation** — Events emitted without schema validation
- **JSON schema out of sync** — Doesn't include RFC-058 fields

**Partial Fixes Already Applied** (per `EVENT-ISSUES-FIXED.md`):
- ✅ `plan_refine_attempt` handler added to frontend
- ✅ Naaru double-creation refactored
- ✅ TypeScript imports fixed
- ⚠️ Score access patched (`metrics?.score` removed) — but root cause (schema drift) remains

### The Problem

**1. Schema Drift** (Verified with direct code references)

**Python Schema** (`src/sunwell/adaptive/event_schema.py:32-37`):
```python
class PlanWinnerData(TypedDict, total=False):
    """Data for plan_winner event."""
    tasks: int  # Required
    artifact_count: int
    gates: int
    technique: str
    # ❌ Missing: selected_index, metrics, selection_reason, total_candidates, etc.
```

**Actual Emission** (`src/sunwell/naaru/planners/harmonic.py:372-387`):
```python
self._emit_event("plan_winner", {
    "tasks": len(best_graph),
    "artifact_count": len(best_graph),
    "selected_index": selected_index,      # ❌ Not in schema
    "total_candidates": len(candidates),   # ❌ Not in schema
    "metrics": {                           # ❌ Not in schema
        "score": best_metrics.score,
        "depth": best_metrics.depth,
        "width": best_metrics.width,
        "leaf_count": best_metrics.leaf_count,
        "parallelism_factor": best_metrics.parallelism_factor,
        "balance_factor": best_metrics.balance_factor,
        "file_conflicts": best_metrics.file_conflicts,
        "estimated_waves": best_metrics.estimated_waves,
    },
    "selection_reason": self._format_selection_reason(best_metrics, scored),  # ❌ Not in schema
    ...
})
```

**Frontend Handler** (`studio/src/stores/agent.ts:642-648`):
```typescript
case 'plan_winner': {
  const selectedIndex = (data.selected_index as number) ?? 0;        // ✅ Used but not in schema
  const selectionReason = (data.selection_reason as string) ?? '';   // ✅ Used but not in schema
  const metrics = (data.metrics as PlanCandidate['metrics']) ?? undefined;  // ✅ Used but not in schema
  const score = (data.score as number) ?? undefined;  // ⚠️ Expected at top level, only in metrics.score
  ...
}
```

**Impact**: 
- Schema validation would reject valid events
- Type generation incomplete
- Documentation inaccurate
- Developers confused about what fields exist

**Evidence**: 
- Direct code inspection confirms misalignment
- `UI-BACKEND-ALIGNMENT-ANALYSIS.md` documents all 8 critical misalignments
- 3-path validation: Source ✅ → Emissions ✅ → Handlers ✅ = Confirmed drift

### Summary: 8 Critical Misalignments

| # | Event | Issue | Schema | Emission | Frontend |
|---|-------|-------|--------|----------|----------|
| 1 | `plan_winner` | Missing RFC-058 fields | 4 fields | 12+ fields | expects 8 |
| 2 | `plan_refine_complete` | Field name mismatch | `score_improvement` | `score_improvement` | expects `improvement` |
| 3 | `plan_refine_start` | Type mismatch | `list[str]` | `list[str]` | expects `string` |
| 4 | `plan_winner` | Missing top-level `score` | not defined | in `metrics.score` | expects `score` |
| 5 | `plan_winner` | Missing `variance_config` | not defined | emits `variance_strategy` | expects `variance_config.prompt_style` |
| 6 | JSON schema | Out of sync | matches Python | — | — |
| 7 | TypeScript types | Not generated | — | — | manual types |
| 8 | HarmonicPlanner | No validation | validators exist | not used | — |

### Detailed Evidence: Score Location & Variance Config

**Issue #4: Score Location Mismatch** (from `HARMONIC-PLANNER-UI-GAPS.md`)

```python
# HarmonicPlanner emits (harmonic.py:378):
{
    "metrics": {
        "score": best_metrics.score,  # Score is HERE only
        "depth": ...,
    }
}
```

```typescript
// Frontend handler expects (agent.ts:647):
const score = (data.score as number) ?? undefined;  // Looks for top-level score (undefined!)
const metrics = (data.metrics as PlanCandidate['metrics']) ?? undefined;

// UI accesses both (PlanningPanel.svelte:47):
selectedCandidate.metrics.score  // Works
selectedCandidate.score          // Undefined
```

**Impact**: Works but inconsistent — some places use `candidate.score`, others use `candidate.metrics.score`.

**Issue #5: Missing variance_config** (from `HARMONIC-PLANNER-UI-GAPS.md`)

```python
# HarmonicPlanner emits (harmonic.py:388):
{
    "variance_strategy": "prompting",  # Enum value, not config object
}
```

```svelte
<!-- UI expects (CandidateComparison.svelte:63): -->
{candidate.variance_config?.prompt_style ?? 'default'}  <!-- undefined! -->
```

**Impact**: Strategy column shows "default" for selected candidate even if it used "parallel_first" or "depth_first".

**2. Manual Type Maintenance**

```typescript
// studio/src/lib/types.ts (manually written)
export interface PlanCandidate {
  index: number;
  artifact_count: number;
  score?: number;
  metrics?: {
    depth: number;
    // ... manually maintained, can drift
  };
}
```

**Impact**:
- Types can drift from Python schemas
- No automatic sync when schemas change
- Requires manual updates across 3 languages

**3. No Runtime Validation**

```python
# harmonic.py
self._emit_event("plan_winner", {
    "selected_index": selected_index,  # ✅ Emitted
    "metrics": {...},  # ✅ Emitted
    # But no validation against schema!
})
```

**Impact**:
- Invalid events can be emitted
- Frontend may crash on unexpected fields
- Bugs discovered late (in production)

**4. JSON Schema Out of Sync**

```json
// schemas/agent-events.schema.json
{
  "type": "plan_winner",
  "data": {
    "properties": {
      "tasks": {"type": "integer"},
      "artifact_count": {"type": "integer"}
      // ❌ Missing: selected_index, metrics, selection_reason, etc.
    }
  }
}
```

**Impact**:
- Schema validation incomplete
- Documentation inaccurate
- Type generation from JSON schema fails

---

## Design Options

### Option A: Python-First with Code Generation ✅ **RECOMMENDED**

**Approach**: Python `TypedDict` schemas are the source of truth. Generate:
- JSON schema (via `generate_json_schema()`)
- TypeScript types (via `generate_typescript_types()`)
- Runtime validators (via `validate_event_data()`)

**Pros**:
- ✅ Single source of truth (Python)
- ✅ Automatic sync (generation ensures consistency)
- ✅ Type safety (Python types → TypeScript types)
- ✅ CI-enforceable (regenerate and diff)
- ✅ Minimal changes (extend existing generators)

**Cons**:
- ⚠️ Requires Python → TypeScript type mapping
- ⚠️ Some Python types don't map cleanly (e.g., `dict[str, Any]`)

**Implementation**:
1. Fix Python schemas (add RFC-058 fields)
2. Extend `generate_typescript_types()` to include all events
3. Regenerate JSON schema from Python
4. Add CI check: `make generate-schemas && git diff --exit-code`

**Confidence**: 90% 🟢

---

### Option B: JSON Schema First

**Approach**: JSON schema is source of truth. Generate Python and TypeScript from JSON.

**Pros**:
- ✅ Language-agnostic
- ✅ Standard format (JSON Schema)

**Cons**:
- ❌ Less type-safe (JSON Schema less expressive than TypedDict)
- ❌ Requires rewriting Python schemas
- ❌ More complex generation (JSON → Python types)

**Confidence**: 60% 🟡

---

### Option C: Shared Type Definitions (Protocol Buffers/JSON Schema)

**Approach**: Use Protocol Buffers or shared JSON Schema, generate all languages.

**Pros**:
- ✅ True single source of truth
- ✅ Language-agnostic

**Cons**:
- ❌ Major refactor (rewrite all schemas)
- ❌ Overkill for current needs
- ❌ Adds dependency

**Confidence**: 40% 🔴

---

## Recommended Solution: Option A (Python-First)

**Rationale**: 
- Minimal changes (extend existing system)
- Python is already the "source of truth" conceptually
- Type safety benefits
- CI-enforceable

---

## Implementation Plan

### Phase 1: Fix Schemas (Week 1)

**Goal**: Align Python schemas with actual emissions and frontend expectations.

**Complexity**: ~150 LOC | Low risk | 2-3 hours

**Tasks**:
1. Update `PlanWinnerData` to include RFC-058 fields (add 9 fields)
2. Fix `PlanRefineCompleteData` field names (rename 2 fields)
3. Fix `PlanRefineStartData` field types (clarify `list[str]`)
4. Add missing fields to other schemas (audit all 40+ events)

**Files**:
- `src/sunwell/adaptive/event_schema.py` (~100 LOC changes)

**Validation**:
- All emissions match schemas (verify via `grep _emit_event`)
- All frontend handlers match schemas (verify via TypeScript compilation)

---

### Phase 2: Extend Code Generation (Week 1-2)

**Goal**: Generate complete TypeScript types and JSON schema from Python.

**Complexity**: ~200 LOC | Medium risk | 4-6 hours

**Tasks**:
1. Extend `generate_typescript_types()` to include all 40+ event types
2. Refactor `generate_json_schema()` to iterate `EVENT_SCHEMAS` registry
3. Add generation for RFC-058 event types (10 new types)
4. Test generation produces correct output

**Files**:
- `src/sunwell/adaptive/event_schema.py` (extend generators, ~150 LOC)
- `scripts/generate_event_schema.py` (entry point, ~50 LOC)

**Output**:
- `studio/src/lib/generated/agent-events.ts` (generated, ~500 LOC)
- `schemas/agent-events.schema.json` (regenerated)

**Decision**: TypeScript generator will be a **standalone script** (`scripts/generate_event_schema.py`) invoked via `make generate-schemas`, not part of the build process.

---

### Phase 3: Add Runtime Validation (Week 2)

**Goal**: Validate all event emissions against schemas.

**Complexity**: ~100 LOC | Low risk | 2-3 hours

**Tasks**:
1. Update `HarmonicPlanner._emit_event()` to use `create_validated_event()`
2. Update `Naaru._emit_event()` to use `create_validated_event()`
3. Update CLI event emission to use `create_validated_event()`
4. Add error handling for validation failures

**Files**:
- `src/sunwell/naaru/planners/harmonic.py` (~20 LOC)
- `src/sunwell/naaru/naaru.py` (~20 LOC)
- `src/sunwell/cli/agent/run.py` (~20 LOC)

**Error Handling Policy** (DECIDED):
- **Development**: Strict validation — raise `ValueError` on schema mismatch
- **Production**: Lenient — log warning, emit event anyway (don't crash)
- **CI/Tests**: Strict — fail on any validation error
- Control via environment variable: `SUNWELL_EVENT_VALIDATION=strict|lenient|off`

**Validation**:
- All events pass schema validation in tests
- Invalid events log warnings in production (never crash)

---

### Phase 4: Fix Frontend Alignment (Week 2-3)

**Goal**: Update frontend handlers to match schemas.

**Complexity**: ~150 LOC | Medium risk | 3-4 hours

**Tasks**:
1. Fix `plan_refine_complete` handler: use `improvement` instead of `score_improvement`
2. Fix `plan_refine_start` handler: parse `improvements_identified` as `string[]`
3. Update `plan_winner` handler: use generated types, remove manual casts
4. Keep defensive fallbacks initially (remove in Phase 6 after integration tests pass)

**Files**:
- `studio/src/stores/agent.ts` (~100 LOC changes)
- `studio/src/lib/types.ts` (import generated types, ~50 LOC)

**Validation**:
- Frontend displays all expected fields (manual test)
- No runtime errors from missing fields (integration test)
- TypeScript compiles without errors

---

### Phase 5: CI Enforcement (Week 3)

**Goal**: Prevent schema drift via automated checks.

**Complexity**: ~50 LOC | Low risk | 1-2 hours

**Tasks**:
1. Add `make generate-schemas` command
2. Add CI check: `make generate-schemas && git diff --exit-code`
3. Add pre-commit hook (optional, using `husky` or `pre-commit`)
4. Document schema update process in README

**Files**:
- `Makefile` (~10 LOC)
- `.github/workflows/ci.yml` (~20 LOC)
- `README.md` (document process)

**CI Check**:
```yaml
- name: Verify schemas are up-to-date
  run: |
    make generate-schemas
    git diff --exit-code schemas/ studio/src/lib/generated/
```

**Validation**:
- CI fails if schemas drift
- PR comment explains how to regenerate

---

### Phase 6: Documentation & Testing (Week 3)

**Goal**: Document contracts and add integration tests.

**Complexity**: ~150 LOC | Low risk | 3-4 hours

**Tasks**:
1. Update `docs/EVENT-STANDARD.md` with RFC-058 fields
2. Add integration tests for event alignment
3. Document schema update process
4. Add examples of event contracts

**Files**:
- `docs/EVENT-STANDARD.md` (~50 LOC)
- `tests/integration/test_event_alignment.py` (new, ~100 LOC)

**Test Location**: `tests/integration/test_event_alignment.py` (not `tests/test_event_alignment.py`)

**Test Coverage**:
```python
# tests/integration/test_event_alignment.py

def test_plan_winner_schema_matches_emission():
    """Verify PlanWinnerData schema matches HarmonicPlanner emission."""

def test_all_event_types_have_schemas():
    """Verify every EventType has a corresponding schema in EVENT_SCHEMAS."""

def test_typescript_types_compile():
    """Verify generated TypeScript types compile without errors."""

def test_json_schema_validates_sample_events():
    """Verify JSON schema accepts valid events and rejects invalid ones."""
```

**Validation**:
- Documentation accurate (reviewed)
- Tests catch alignment issues (CI passes)

---

### Implementation Summary

| Phase | Effort | LOC | Risk |
|-------|--------|-----|------|
| 1. Fix Schemas | 2-3 hrs | ~150 | Low |
| 2. Code Generation | 4-6 hrs | ~200 | Medium |
| 3. Runtime Validation | 2-3 hrs | ~100 | Low |
| 4. Frontend Alignment | 3-4 hrs | ~150 | Medium |
| 5. CI Enforcement | 1-2 hrs | ~50 | Low |
| 6. Docs & Testing | 3-4 hrs | ~150 | Low |
| **Total** | **~18 hrs** | **~800** | **Low-Medium** |

---

## Detailed Changes

### 1. Update `PlanWinnerData` Schema

**REQUIRED** fields are enforced by `REQUIRED_FIELDS` registry. **Optional** fields use `total=False`.

```python
# src/sunwell/adaptive/event_schema.py

class PlanWinnerData(TypedDict, total=False):
    """Data for plan_winner event.
    
    Required: tasks
    Optional: All other fields (backward-compatible with non-Harmonic planners)
    """
    # Core fields (legacy)
    tasks: int              # REQUIRED - enforced via REQUIRED_FIELDS
    artifact_count: int     # Optional
    gates: int              # Optional
    technique: str          # Optional
    
    # RFC-058: Harmonic planning fields (all optional for backward compat)
    selected_index: int           # Optional - which candidate was selected (0-indexed)
    total_candidates: int         # Optional - how many candidates were generated
    metrics: dict[str, Any]       # Optional - PlanMetrics as dict (score, depth, width, etc.)
    selection_reason: str         # Optional - human-readable selection reason
    variance_strategy: str        # Optional - "prompting" | "temperature"
    variance_config: dict[str, Any]  # Optional - variance config used for this candidate
    refinement_rounds: int        # Optional - how many refinement rounds were run
    final_score_improvement: float  # Optional - total score improvement from refinement
    score: float                  # CANONICAL - top-level score (same as metrics.score)

# Update REQUIRED_FIELDS
REQUIRED_FIELDS[EventType.PLAN_WINNER] = {"tasks"}  # Only tasks is required
```

**Score Location** (DECIDED): Emit `score` at **top level** as canonical location. `metrics.score` is redundant but kept for backward compatibility. Frontend should prefer `data.score` over `data.metrics?.score`.

### 2. Fix `PlanRefineCompleteData`

**Decision**: Update schema to match frontend (Option A) — field names are more descriptive.

```python
class PlanRefineCompleteData(TypedDict, total=False):
    """Data for plan_refine_complete event.
    
    Required: round
    Optional: All other fields
    """
    round: int                    # REQUIRED - which refinement round (1-indexed)
    improved: bool                # Optional - did this round improve the plan?
    old_score: float | None       # Optional - score before refinement
    new_score: float | None       # Optional - score after refinement
    improvement: float | None     # Optional - delta (new_score - old_score)
    reason: str | None            # Optional - why refinement stopped or continued
    improvements_applied: list[str]  # Optional - list of improvements made

# Update REQUIRED_FIELDS
REQUIRED_FIELDS[EventType.PLAN_REFINE_COMPLETE] = {"round"}
```

**Migration**: Update `HarmonicPlanner._emit_event()` calls to use new field names.

### 3. Fix `PlanRefineStartData`

```python
class PlanRefineStartData(TypedDict, total=False):
    """Data for plan_refine_start event.
    
    Required: round, total_rounds
    Optional: current_score, improvements_identified
    """
    round: int                    # REQUIRED - current round (1-indexed)
    total_rounds: int             # REQUIRED - total planned rounds
    current_score: float          # Optional - score at start of round
    improvements_identified: list[str]  # Optional - LIST of improvement descriptions

# REQUIRED_FIELDS already correct
REQUIRED_FIELDS[EventType.PLAN_REFINE_START] = {"round", "total_rounds"}
```

**Frontend Fix** (`studio/src/stores/agent.ts`):
```typescript
// Before (incorrect):
const improvementsIdentified = (data.improvements_identified as string) ?? '';

// After (correct):
const improvementsIdentified = (data.improvements_identified as string[]) ?? [];
```

### 4. Extend TypeScript Generator

```python
def generate_typescript_types() -> str:
    """Generate TypeScript type definitions from Python schemas."""
    lines = [
        "// Auto-generated from Python event schemas",
        "// Do not edit manually - regenerate from event_schema.py",
        "",
        "export interface AgentEvent {",
        "  type: string;",
        "  data: Record<string, any>;",
        "  timestamp?: number;",
        "}",
        "",
    ]
    
    # Generate types for all event schemas
    for event_type, schema_class in EVENT_SCHEMAS.items():
        type_name = schema_class.__name__.replace("Data", "")
        lines.append(f"export interface {type_name} {{")
        
        # Extract fields from TypedDict
        annotations = get_type_hints(schema_class)
        for field_name, field_type in annotations.items():
            ts_type = python_to_typescript_type(field_type)
            lines.append(f"  {field_name}?: {ts_type};")
        
        lines.append("}")
        lines.append("")
    
    return "\n".join(lines)
```

### 5. Add Validation to HarmonicPlanner

```python
# src/sunwell/naaru/planners/harmonic.py

def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
    """Emit event via callback if configured (RFC-058)."""
    if self.event_callback is None:
        return

    try:
        from sunwell.adaptive.events import AgentEvent, EventType
        from sunwell.adaptive.event_schema import create_validated_event
        
        # Validate event data
        validated_event = create_validated_event(EventType(event_type), data)
        self.event_callback(validated_event)
    except ValueError as e:
        import logging
        logging.warning(f"Invalid event type '{event_type}': {e}")
    except Exception as e:
        import logging
        logging.warning(f"Event emission failed for '{event_type}': {e}")
```

---

## Testing Strategy

### Unit Tests

**Schema Validation**:
```python
def test_plan_winner_schema_includes_rfc058_fields():
    """Verify PlanWinnerData includes RFC-058 fields."""
    schema = PlanWinnerData
    assert 'selected_index' in schema.__annotations__
    assert 'metrics' in schema.__annotations__
    assert 'selection_reason' in schema.__annotations__
```

**Code Generation**:
```python
def test_typescript_generation_includes_all_events():
    """Verify TypeScript generator includes all event types."""
    ts_code = generate_typescript_types()
    assert 'PlanWinnerData' in ts_code
    assert 'PlanCandidateScoredData' in ts_code
    assert 'PlanRefineCompleteData' in ts_code
```

**Event Validation**:
```python
def test_harmonic_planner_validates_events():
    """Verify HarmonicPlanner validates events before emission."""
    planner = HarmonicPlanner(...)
    # Mock callback that captures events
    events = []
    planner.event_callback = lambda e: events.append(e)
    
    # Emit event with invalid data (missing required field)
    with pytest.raises(ValueError):
        planner._emit_event("plan_winner", {})  # Missing 'tasks'
```

### Integration Tests

**End-to-End Event Flow**:
```python
def test_event_alignment_python_to_typescript():
    """Verify Python emission → TypeScript handler alignment."""
    # Emit event from Python
    event = create_validated_event(EventType.PLAN_WINNER, {
        "tasks": 5,
        "selected_index": 0,
        "metrics": {...},
        # ... all RFC-058 fields
    })
    
    # Simulate TypeScript handler
    # Verify all fields are accessible
    assert event.data["selected_index"] == 0
    assert event.data["metrics"] is not None
```

**Schema Regeneration**:
```python
def test_schema_regeneration_no_changes():
    """Verify regenerating schemas produces no changes."""
    # Generate schemas
    generate_json_schema()
    generate_typescript_types()
    
    # Check git diff is empty
    result = subprocess.run(["git", "diff", "--exit-code"], cwd=repo_root)
    assert result.returncode == 0, "Schema regeneration produced changes"
```

---

## Migration Strategy

### Backward Compatibility

**All changes are additive**:
- New fields added to schemas (optional)
- Existing fields unchanged
- Frontend handles missing fields gracefully

**No breaking changes**:
- Old events still valid (missing new fields is OK)
- Frontend fallbacks handle old events
- Gradual migration possible

### Rollout Plan

1. **Week 1**: Fix schemas, extend generators (no frontend changes)
2. **Week 2**: Add validation, update frontend handlers
3. **Week 3**: CI enforcement, documentation, testing

**Risk**: Low — changes are additive, backward-compatible

---

## Success Metrics

### Alignment

- ✅ **0 critical misalignments** (down from 8)
- ✅ **100% schema coverage** (all events have complete schemas)
- ✅ **0 manual type definitions** (all generated)

### Validation

- ✅ **100% event validation** (all emissions validated)
- ✅ **0 validation failures** (all events pass)

### Developer Experience

- ✅ **CI catches drift** (regeneration check fails on drift)
- ✅ **Documentation accurate** (schemas match reality)
- ✅ **Type safety** (TypeScript types match Python)

---

## Risks and Mitigations

### Risk 1: Type Mapping Complexity

**Risk**: Python types don't map cleanly to TypeScript (e.g., `dict[str, Any]` → `Record<string, any>`)

**Mitigation**: 
- Use conservative mappings (prefer `any` over complex types)
- Document mapping rules
- Test generated types compile

### Risk 2: Validation Performance

**Risk**: Runtime validation adds overhead to event emission

**Mitigation**:
- Events are infrequent (not in hot path)
- Validation is fast (dict lookups)
- Can disable in production if needed

### Risk 3: Frontend Breaking Changes

**Risk**: Updating frontend handlers breaks existing behavior

**Mitigation**:
- Keep defensive fallbacks initially
- Gradual migration (test each handler)
- Integration tests catch issues

---

## Alternatives Considered

### Alternative 1: Shared Type Definitions (Protocol Buffers)

**Why not**: Overkill, major refactor, adds dependency

### Alternative 2: JSON Schema First

**Why not**: Less type-safe, requires rewriting Python schemas

### Alternative 3: Manual Alignment (Status Quo)

**Why not**: Drift continues, no enforcement, maintenance burden

---

## References

### Internal Documents

- `UI-BACKEND-ALIGNMENT-ANALYSIS.md` — Detailed misalignment analysis (8 issues documented)
- `HARMONIC-PLANNER-UI-GAPS.md` — **Key evidence**: Score location (`harmonic.py:378` → `agent.ts:647` → `PlanningPanel.svelte:47`) and variance_config (`harmonic.py:388` → `CandidateComparison.svelte:63`) issues
- `EVENT-ISSUES-FOUND.md` — Event handler audit, verification checklist
- `EVENT-ISSUES-FIXED.md` — Partial fixes applied (handlers, imports), but schema drift remains
- `EVENT-STANDARD.md` — Event format standard
- `RFC-058-planning-visibility.md` — RFC defining new events
- `RFC-059-observability-completeness.md` — Schema validation RFC

### Code References

- `src/sunwell/adaptive/event_schema.py` — Python schemas
- `schemas/agent-events.schema.json` — JSON schema
- `studio/src/stores/agent.ts` — TypeScript handlers
- `src/sunwell/naaru/planners/harmonic.py` — Event emissions

---

## Appendix: Complete Schema Updates

### All Schema Changes Required

| Schema | Field | Change | Reason |
|--------|-------|--------|--------|
| `PlanWinnerData` | `selected_index` | Add `int` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `total_candidates` | Add `int` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `metrics` | Add `dict[str, Any]` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `selection_reason` | Add `str` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `variance_strategy` | Add `str` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `variance_config` | Add `dict[str, Any]` | Needed by frontend |
| `PlanWinnerData` | `refinement_rounds` | Add `int` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `final_score_improvement` | Add `float` | Emitted by HarmonicPlanner |
| `PlanWinnerData` | `score` | Add `float` | Canonical score location |
| `PlanRefineCompleteData` | `improved` | Add `bool` | Frontend expects |
| `PlanRefineCompleteData` | `old_score` | Add `float \| None` | Frontend expects |
| `PlanRefineCompleteData` | `new_score` | Add `float \| None` | Frontend expects |
| `PlanRefineCompleteData` | `improvement` | Add `float \| None` | Frontend expects (rename) |
| `PlanRefineCompleteData` | `reason` | Add `str \| None` | Frontend expects |
| `PlanRefineCompleteData` | `score_improvement` | Remove | Replaced by `improvement` |

**HarmonicPlanner Changes** (`src/sunwell/naaru/planners/harmonic.py`):

1. **Add `score` at top level** in `plan_winner` emission (lines ~372-391):
```python
self._emit_event("plan_winner", {
    "score": best_metrics.score,  # ADD: top-level score (canonical)
    "metrics": {
        "score": best_metrics.score,  # KEEP: for backward compat
        ...
    },
})
```

2. **Add `variance_config`** in `plan_winner` emission:
```python
# Track which config was used for selected candidate
selected_config = configs[selected_index] if selected_index < len(configs) else {}

self._emit_event("plan_winner", {
    ...
    "variance_config": {  # ADD: actual config used
        "prompt_style": selected_config.get("prompt_style", "default"),
        "temperature": selected_config.get("temperature"),
        "constraint": selected_config.get("constraint"),
    },
})
```

3. **Use `create_validated_event()`** for all emissions:
```python
from sunwell.adaptive.event_schema import create_validated_event

def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
    if self.event_callback is None:
        return
    validated_event = create_validated_event(EventType(event_type), data)
    self.event_callback(validated_event)
```

**Frontend Changes** (`studio/src/stores/agent.ts`):
1. Parse `improvements_identified` as `string[]` not `string`
2. Use `improvement` instead of `score_improvement`
3. Remove manual type casts, use generated types

### Type Mapping Rules

```python
def python_to_typescript_type(py_type: type) -> str:
    """Map Python type to TypeScript type."""
    if py_type == int:
        return "number"
    elif py_type == float:
        return "number"
    elif py_type == str:
        return "string"
    elif py_type == bool:
        return "boolean"
    elif py_type == dict[str, Any] or py_type == dict:
        return "Record<string, any>"
    elif py_type == list[str]:
        return "string[]"
    elif py_type == list:
        return "any[]"
    elif hasattr(py_type, "__origin__"):  # Union, Optional, etc.
        # Handle Optional[str] -> str | null
        if py_type.__origin__ == Union:
            args = py_type.__args__
            if len(args) == 2 and type(None) in args:
                non_none = [a for a in args if a != type(None)][0]
                return f"{python_to_typescript_type(non_none)} | null"
        return "any"
    else:
        return "any"  # Fallback
```

---

## Open Questions

1. ~~**Should we version events?**~~ — Out of scope, future RFC
2. ~~**Should validation be strict or lenient?**~~ — **DECIDED**: Strict in dev/CI, lenient in prod (see Phase 3)
3. ~~**Should we generate Rust types?**~~ — **DECIDED**: No, Rust forwards JSON as-is
4. ~~**Where should `score` be emitted?**~~ — **DECIDED**: Top-level `score` is canonical; `metrics.score` kept for compat
5. ~~**TypeScript generator location?**~~ — **DECIDED**: Standalone script `scripts/generate_event_schema.py`

**Remaining Open Questions**: None — all questions resolved during evaluation.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-20 | Draft RFC-060 | Address event contract alignment |
| 2026-01-20 | Choose Option A (Python-first) | Minimal changes, single source of truth, CI-enforceable |
| 2026-01-20 | Score at top level | Simpler for frontend, `metrics.score` is redundant |
| 2026-01-20 | Strict in dev, lenient in prod | Catch errors early but don't crash in production |
| 2026-01-20 | Standalone TypeScript generator | Decoupled from build, explicit regeneration |
| 2026-01-20 | `PlanRefineCompleteData` uses frontend field names | More descriptive (`improved`, `improvement` vs `score_improvement`) |
| 2026-01-20 | `improvements_identified` is `list[str]` | Frontend must be updated to handle arrays |
| 2026-01-20 | RFC evaluated at 90% confidence | All claims verified via 3-path validation |
