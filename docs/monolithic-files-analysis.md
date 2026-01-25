# Monolithic Files Analysis

**Date**: 2026-01-25  
**Purpose**: Identify files that need modularization per RFC-138 architecture consolidation

---

## Summary

Found **8 files** over 500 lines that need modularization. Priority order:

1. **CRITICAL** (1000+ lines, clear split points): 3 files
2. **HIGH** (800-1000 lines, multiple responsibilities): 3 files  
3. **MODERATE** (500-800 lines, review needed): 2 files

---

## 🔴 CRITICAL Priority

### 1. `agent/event_schema.py` (1284 lines, 98 TypedDict classes)

**Status**: CLEARLY MONOLITHIC - Collection of schemas, no cohesion

**Structure**:
- 98 TypedDict classes (all event data schemas)
- Organized by sections with clear boundaries
- No shared logic, just type definitions

**Split Strategy**:
```
agent/events/schemas/
├── __init__.py              # Re-exports all
├── base.py                  # PlanStartData, CompleteData, ErrorData
├── planning.py              # Planning Events (PlanCandidateData, PlanExpandedData, etc.)
├── harmonic.py              # Harmonic Planning Events (RFC-058)
├── refinement.py            # Refinement Events
├── memory.py                # Memory Events
├── signal.py                # Signal Events
├── gate.py                  # Gate Events
├── validation.py            # Validation Events
├── fix.py                   # Fix Events
├── discovery.py             # Plan Discovery Events
├── lens.py                  # Lens Events
├── briefing.py              # Briefing Events
├── prefetch.py              # Prefetch Events
├── model.py                 # Model Events
├── skill.py                 # Skill Events
├── backlog.py               # Backlog Events
├── convergence.py           # Convergence Events
├── recovery.py              # Recovery Events
├── integration.py           # Integration Events
└── task.py                  # Task Events (TaskStartData, TaskProgressData, etc.)
```

**Benefits**:
- Clear organization by event domain
- Easier to find specific schemas
- Reduced cognitive load (98 classes → ~5-10 per file)
- Better import hygiene

**Migration**: Low risk - pure type definitions, no logic

---

### 2. `simulacrum/core/store.py` (1275 lines, 1 class, 58 methods)

**Status**: MONOLITHIC CLASS - Too many responsibilities

**Responsibilities** (from method analysis):
- Session management (`new_session`, `save_session`, `load_session`, `list_sessions`)
- Turn management (`add_turn`, `add_user`, `add_assistant`, `add_learning`)
- Episode management (`add_episode`, `get_episodes`, `get_dead_ends`)
- Retrieval (`retrieve_for_planning`, `retrieve_parallel`, `get_context_for_prompt`)
- Chunk management (via `_chunk_manager`)
- Topology extraction (`_extract_topology_batch`)
- Tier management (via `_tier_manager`)
- Focus management (via `_focus`)
- DAG operations (`get_dag`)

**Split Strategy**:
```
simulacrum/core/store.py          # Main facade (200-300 lines)
simulacrum/core/session_manager.py # Session CRUD (already exists, consolidate)
simulacrum/core/turn_manager.py   # Turn operations
simulacrum/core/episode_manager.py # Episode operations (already exists, consolidate)
simulacrum/core/retrieval.py      # Retrieval operations (already exists, consolidate)
simulacrum/core/chunk_ops.py     # Chunk operations wrapper
simulacrum/core/topology_ops.py   # Topology extraction wrapper
```

**Current State**: Some components already exist (`SessionManager`, `EpisodeManager`, `PlanningRetriever`, etc.) but `SimulacrumStore` directly implements many operations instead of delegating.

**Refactoring Approach**:
1. Extract session operations to `SessionManager` (already exists)
2. Extract episode operations to `EpisodeManager` (already exists)  
3. Extract retrieval to retrieval modules (already exist)
4. Keep `SimulacrumStore` as thin facade that coordinates

**Benefits**:
- Single Responsibility Principle
- Easier testing (mock individual components)
- Clearer dependencies
- Better alignment with RFC-138 (memory domain consolidation)

---

### 3. `naaru/planners/harmonic.py` (1309 lines, 2 classes, 31 functions)

**Status**: LARGE PLANNER - Could benefit from splitting

**Structure**:
- `ScoringVersion` enum (small)
- `HarmonicPlanner` class (very large, ~1200 lines)
- Many helper functions

**Responsibilities** (from code structure):
- Candidate generation
- Scoring/metrics calculation
- Refinement
- JSON parsing/validation
- Keyword extraction
- Variance application

**Split Strategy**:
```
naaru/planners/harmonic/
├── __init__.py              # HarmonicPlanner facade
├── planner.py               # Main HarmonicPlanner class (orchestration only, ~300 lines)
├── candidate.py             # Candidate generation logic
├── scoring.py                # Scoring and metrics calculation
├── refinement.py            # Refinement logic
├── parsing.py               # JSON parsing and validation helpers
└── utils.py                 # Keyword extraction, variance helpers
```

**Benefits**:
- Clear separation of concerns
- Easier to test individual components
- Better code navigation
- Aligns with RFC-138 planning domain structure

**Note**: This is a complex planner, so splitting requires careful dependency management.

---

## 🟡 HIGH Priority

### 4. `agent/loop.py` (1160 lines, 1 class, 14 methods)

**Status**: LARGE CLASS - Multiple responsibilities

**Responsibilities**:
- Tool loop orchestration
- Confidence routing (Vortex/Interference/Single-shot)
- Tool call introspection
- Retry logic
- Learning injection
- Validation integration

**Split Strategy**:
```
agent/loop/
├── __init__.py              # AgentLoop facade
├── core.py                  # Main AgentLoop class (orchestration, ~300 lines)
├── routing.py               # Confidence routing logic (already exists as loop_routing.py)
├── retry.py                 # Retry logic (already exists as loop_retry.py)
├── introspection.py         # Tool call introspection (already exists)
└── config.py                # LoopConfig (already exists as loop_config.py)
```

**Current State**: Some components already extracted (`loop_routing.py`, `loop_retry.py`, `loop_config.py`), but `AgentLoop` still has too much logic.

**Refactoring**: Extract remaining logic to existing modules, keep `AgentLoop` thin.

---

### 5. `naaru/planners/artifact.py` (1224 lines, 1 class, 24 methods)

**Status**: LARGE PLANNER - Review needed

**Structure**: Single `ArtifactPlanner` class with discovery logic

**Analysis Needed**: Review if methods can be grouped into:
- Discovery logic
- Dependency resolution
- Graph construction
- Validation

**Potential Split**:
```
naaru/planners/artifact/
├── __init__.py              # ArtifactPlanner facade
├── planner.py               # Main class (orchestration)
├── discovery.py             # Artifact discovery logic
├── dependencies.py          # Dependency resolution
└── graph.py                 # Graph construction
```

**Note**: May be cohesive enough to keep as-is. Review after other splits.

---

### 6. `cli/main.py` (1055 lines, 1 class, 11 functions)

**Status**: LARGE CLI FILE - Multiple commands

**Structure**:
- `GoalFirstGroup` class (custom Click group)
- `main()` function (large, handles goal-first interface)
- Multiple command handlers
- Helper functions

**Split Strategy**:
```
cli/
├── main.py                  # Entry point, GoalFirstGroup (~200 lines)
├── commands/
│   ├── __init__.py
│   ├── goal.py             # Goal-first execution
│   ├── plan.py              # Plan command (already exists as plan_cmd.py)
│   ├── chat.py              # Chat command (already exists)
│   └── eval.py              # Eval command (already exists as eval_cmd.py)
└── helpers/
    ├── __init__.py
    ├── events.py            # Event printing helpers
    ├── studio.py            # Studio integration
    └── project.py            # Project name extraction
```

**Current State**: Some commands already in separate files (`plan_cmd.py`, `chat.py`, `eval_cmd.py`), but `main.py` still has too much logic.

**Refactoring**: Move command implementations to `commands/`, keep `main.py` as thin router.

---

## 🟢 MODERATE Priority

### 7. `tools/handlers.py` (993 lines, 1 class)

**Status**: LARGE HANDLER CLASS - Multiple tool types

**Structure**: `CoreToolHandlers` class with many handler methods

**Split Strategy**:
```
tools/handlers/
├── __init__.py              # CoreToolHandlers facade
├── base.py                  # Base class, security utilities
├── file.py                  # File operations
├── git.py                   # Git operations
├── shell.py                 # Shell operations
└── env.py                   # Environment operations
```

**Benefits**: Clear separation by tool category, easier to extend

---

### 8. `agent/fixer.py` (579 lines, 4 classes)

**Status**: MODERATE SIZE - Multiple related classes

**Structure**:
- `FixAttempt` (dataclass)
- `FixResult` (dataclass)
- `FixStage` (main class)
- `StaticAnalysisFixer` (helper)

**Analysis**: May be cohesive enough. Review after other splits. If splitting:
```
agent/fixer/
├── __init__.py              # Re-exports
├── stage.py                 # FixStage
├── static.py                # StaticAnalysisFixer
└── types.py                 # FixAttempt, FixResult
```

---

## Recommendations

### Immediate Actions (Week 1)

1. **Split `event_schema.py`** - Low risk, high impact
   - Create `agent/events/schemas/` directory
   - Split by event category (20+ files)
   - Update imports (use re-exports in `__init__.py`)

2. **Refactor `store.py`** - Medium risk, high impact
   - Extract to existing manager classes
   - Keep `SimulacrumStore` as thin facade
   - Aligns with RFC-138 memory domain

### Short-term (Week 2-3)

3. **Split `harmonic.py`** - Medium risk, medium impact
   - Create `naaru/planners/harmonic/` package
   - Extract candidate generation, scoring, refinement

4. **Refactor `loop.py`** - Low risk (components exist)
   - Move logic to existing `loop_*.py` modules
   - Keep `AgentLoop` thin

### Medium-term (Week 4+)

5. **Split `cli/main.py`** - Low risk
   - Move commands to `cli/commands/`
   - Move helpers to `cli/helpers/`

6. **Review `artifact.py`** - Assess after other splits
   - May be cohesive enough to keep

7. **Split `handlers.py`** - Low risk
   - Split by tool category

---

## Metrics

| File | Lines | Classes | Functions | Priority | Split Complexity |
|------|-------|---------|-----------|----------|------------------|
| `event_schema.py` | 1284 | 98 | 9 | 🔴 CRITICAL | Low (pure types) |
| `store.py` | 1275 | 1 | 58 | 🔴 CRITICAL | Medium (refactor) |
| `harmonic.py` | 1309 | 2 | 31 | 🔴 CRITICAL | Medium (split) |
| `loop.py` | 1160 | 1 | 14 | 🟡 HIGH | Low (components exist) |
| `artifact.py` | 1224 | 1 | 24 | 🟡 HIGH | Medium (review first) |
| `main.py` | 1055 | 1 | 11 | 🟡 HIGH | Low (commands exist) |
| `handlers.py` | 993 | 1 | ~50 | 🟢 MODERATE | Low (by category) |
| `fixer.py` | 579 | 4 | ~10 | 🟢 MODERATE | Low (if needed) |

---

## Alignment with RFC-138

These modularizations align with RFC-138's goals:

- **Clear domain boundaries**: Event schemas organized by domain
- **Reduced cognitive load**: Smaller, focused files
- **Better import hierarchy**: Cleaner dependencies
- **Domain consolidation**: `store.py` refactoring aligns with memory domain

---

## Next Steps

1. Create RFC for event schema split (low-hanging fruit)
2. Review `store.py` refactoring approach with team
3. Plan `harmonic.py` split (coordinate with planning domain work)
4. Track progress in RFC-138 implementation checklist
