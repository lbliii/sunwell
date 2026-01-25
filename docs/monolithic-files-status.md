# Monolithic Files Status Report

**Date**: 2026-01-25  
**Purpose**: Current status of files needing modularization per RFC-138

---

## ✅ Already Modularized

### 1. `agent/event_schema.py` ✅ COMPLETE
- **Status**: Modularized into `agent/events/schemas/` package
- **Current**: 293 lines (deprecation wrapper, re-exports from modular structure)
- **Original**: 1284 lines, 98 TypedDict classes
- **Result**: Split into 20+ focused schema files by domain

### 2. `naaru/planners/harmonic.py` ✅ COMPLETE  
- **Status**: Modularized into `naaru/planners/harmonic/` package
- **Current**: Package with 7 modules (planner.py, candidate.py, scoring.py, refinement.py, parsing.py, utils.py, template.py)
- **Original**: 1309 lines, 2 classes, 31 functions
- **Result**: Clear separation of concerns across focused modules

---

## 🔴 CRITICAL Priority (1000+ lines)

### 1. `simulacrum/core/store.py` (1111 lines, 1 class, 54 methods)

**Status**: MONOLITHIC CLASS - Too many responsibilities

**Current Structure**:
- Single `SimulacrumStore` class with 54 methods
- Handles: session management, turn management, episode management, retrieval, chunk management, topology extraction, tier management, focus management, DAG operations

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

**Refactoring Approach**:
1. Extract session operations to `SessionManager` (already exists)
2. Extract episode operations to `EpisodeManager` (already exists)  
3. Extract retrieval to retrieval modules (already exist)
4. Keep `SimulacrumStore` as thin facade that coordinates

**Priority**: 🔴 CRITICAL - High impact, aligns with RFC-138 memory domain consolidation

---

### 2. `naaru/planners/artifact.py` (1224 lines, 1 class, 24 methods)

**Status**: LARGE PLANNER - Review needed

**Structure**: Single `ArtifactPlanner` class with discovery logic

**Potential Split**:
```
naaru/planners/artifact/
├── __init__.py              # ArtifactPlanner facade
├── planner.py               # Main class (orchestration)
├── discovery.py             # Artifact discovery logic
├── dependencies.py          # Dependency resolution
└── graph.py                 # Graph construction
```

**Analysis Needed**: Review if methods can be grouped into:
- Discovery logic
- Dependency resolution
- Graph construction
- Validation

**Priority**: 🔴 CRITICAL - Large file, clear split points

---

### 3. `agent/loop.py` (1160 lines, 1 class, 14 methods)

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

**Priority**: 🔴 CRITICAL - Components exist, low risk refactor

---

## 🟡 HIGH Priority (800-1000 lines)

### 4. `cli/main.py` (1055 lines, 1 class, 11 functions)

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
    └── project.py           # Project name extraction
```

**Current State**: Some commands already in separate files (`plan_cmd.py`, `chat.py`, `eval_cmd.py`), but `main.py` still has too much logic.

**Refactoring**: Move command implementations to `commands/`, keep `main.py` as thin router.

**Priority**: 🟡 HIGH - Low risk, commands already separated

---

### 5. `tools/handlers.py` (993 lines, 1 class, ~50 methods)

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

**Priority**: 🟡 HIGH - Low risk, clear split by category

---

### 6. `agent/core.py` (992 lines, 1 class, 26 methods)

**Status**: LARGE CORE CLASS - Main execution engine

**Structure**: Single `Agent` class - THE execution engine

**Analysis**: This is the central orchestration point. May be cohesive enough, but could benefit from extracting:
- Orientation logic
- Planning coordination
- Execution coordination
- Learning coordination

**Potential Split**:
```
agent/core/
├── __init__.py              # Agent facade
├── agent.py                 # Main Agent class (orchestration)
├── orientation.py           # Orientation logic
├── planning_coord.py        # Planning coordination
├── execution_coord.py       # Execution coordination
└── learning_coord.py        # Learning coordination
```

**Priority**: 🟡 HIGH - Review after other splits, may be cohesive enough

---

## 🟢 MODERATE Priority (Additional Large Files)

### 7. `demo/lens_experiments.py` (1126 lines, 20 definitions)

**Status**: EXPERIMENT FILE - May not need modularization

**Structure**: Experimental code for lens injection variants

**Note**: This is demo/experimental code. May not need modularization if it's temporary or for testing only.

**Priority**: 🟢 MODERATE - Review if this is production code

---

### 8. `simulacrum/manager/manager.py` (1045 lines, 1 class)

**Status**: LARGE MANAGER CLASS - Multi-simulacrum orchestration

**Structure**: Single `SimulacrumManager` class for managing multiple simulacrums

**Potential Split**:
```
simulacrum/manager/
├── __init__.py              # SimulacrumManager facade
├── manager.py               # Main class (orchestration)
├── switching.py             # Simulacrum switching logic
├── querying.py              # Cross-simulacrum querying
└── lifecycle.py             # Lifecycle management
```

**Priority**: 🟢 MODERATE - Review if splitting improves clarity

---

### 9. `benchmark/naaru/conditions.py` (1075 lines, 19 definitions)

**Status**: LARGE CONDITIONS FILE - Multiple condition types

**Structure**: Multiple condition classes/functions for benchmark framework

**Potential Split**:
```
benchmark/naaru/conditions/
├── __init__.py              # Re-exports
├── base.py                  # Base condition classes
├── routing.py               # Routing conditions
├── quality.py               # Quality conditions
└── execution.py             # Execution conditions
```

**Priority**: 🟢 MODERATE - Review if splitting improves organization

---

### 10. `naaru/persistence.py` (1038 lines, 13 definitions)

**Status**: LARGE PERSISTENCE FILE - Multiple persistence concerns

**Structure**: Persistence logic for Naaru planning system

**Potential Split**: Review structure to identify clear boundaries

**Priority**: 🟢 MODERATE - Review needed

---

### 11. `schema/loader.py` (1013 lines, 1 class)

**Status**: LARGE LOADER CLASS - Schema loading logic

**Structure**: Single class handling schema loading

**Potential Split**: Review if schema loading can be split by schema type

**Priority**: 🟢 MODERATE - Review needed

---

### 12. `cli/chat.py` (991 lines)

**Status**: LARGE CLI COMMAND - Chat interface

**Structure**: Chat command implementation

**Priority**: 🟢 MODERATE - May be cohesive enough

---

### 13. `cli/lens.py` (994 lines)

**Status**: LARGE CLI COMMAND - Lens management

**Structure**: Lens command implementation

**Priority**: 🟢 MODERATE - May be cohesive enough

---

### 14. `cli/plan_cmd.py` (953 lines)

**Status**: LARGE CLI COMMAND - Plan command

**Structure**: Plan command implementation

**Priority**: 🟢 MODERATE - May be cohesive enough

---

### 15. `backlog/manager.py` (933 lines, 2 classes, 37 methods)

**Status**: LARGE MANAGER - Backlog management

**Structure**: Two classes handling backlog operations

**Priority**: 🟢 MODERATE - Review if splitting improves clarity

---

## Summary Table

| File | Lines | Classes | Methods/Functions | Priority | Status |
|------|-------|---------|------------------|----------|--------|
| `simulacrum/core/store.py` | 1111 | 1 | 54 | 🔴 CRITICAL | Needs refactoring |
| `naaru/planners/artifact.py` | 1224 | 1 | 24 | 🔴 CRITICAL | Needs splitting |
| `agent/loop.py` | 1160 | 1 | 14 | 🔴 CRITICAL | Needs refactoring |
| `cli/main.py` | 1055 | 1 | 11 | 🟡 HIGH | Needs splitting |
| `tools/handlers.py` | 993 | 1 | ~50 | 🟡 HIGH | Needs splitting |
| `agent/core.py` | 992 | 1 | 26 | 🟡 HIGH | Review needed |
| `demo/lens_experiments.py` | 1126 | - | 20 | 🟢 MODERATE | Review if production |
| `simulacrum/manager/manager.py` | 1045 | 1 | - | 🟢 MODERATE | Review needed |
| `benchmark/naaru/conditions.py` | 1075 | - | 19 | 🟢 MODERATE | Review needed |
| `naaru/persistence.py` | 1038 | - | 13 | 🟢 MODERATE | Review needed |
| `schema/loader.py` | 1013 | 1 | - | 🟢 MODERATE | Review needed |
| `cli/chat.py` | 991 | - | - | 🟢 MODERATE | May be cohesive |
| `cli/lens.py` | 994 | - | - | 🟢 MODERATE | May be cohesive |
| `cli/plan_cmd.py` | 953 | - | - | 🟢 MODERATE | May be cohesive |
| `backlog/manager.py` | 933 | 2 | 37 | 🟢 MODERATE | Review needed |

---

## Recommended Action Plan

### Immediate (Week 1-2)
1. **Refactor `simulacrum/core/store.py`** - Extract to existing manager classes
2. **Split `naaru/planners/artifact.py`** - Create package structure
3. **Refactor `agent/loop.py`** - Move logic to existing modules

### Short-term (Week 3-4)
4. **Split `cli/main.py`** - Move commands to `commands/` directory
5. **Split `tools/handlers.py`** - Split by tool category

### Medium-term (Week 5+)
6. **Review `agent/core.py`** - Assess if splitting improves clarity
7. **Review other 800+ line files** - Determine if modularization needed

---

## Notes

- **Already Complete**: `event_schema.py` and `harmonic.py` have been successfully modularized
- **Low Risk**: Most splits involve moving code to existing modules or clear boundaries
- **High Impact**: Modularization aligns with RFC-138 architecture consolidation goals
- **Testing**: All splits must maintain test coverage and backward compatibility
