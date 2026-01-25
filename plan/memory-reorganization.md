# Memory Package Reorganization Plan

**Status**: Draft  
**Date**: 2026-01-25  
**Pattern**: Follows `agent/` and `identity/` package reorganization (RFC-138)

---

## Overview

Reorganize `sunwell.memory` from mixed flat/hierarchical structure to consistent hierarchical subpackages, following the same pattern used for `agent/` and `identity/` package reorganization. This improves modularity, discoverability, and maintainability.

---

## Current Structure

```
memory/
├── __init__.py          # Public API exports
├── briefing.py          # Briefing system (RFC-071) - ~480 lines
├── persistent.py        # Unified memory facade (RFC-MEMORY) - ~717 lines
├── types.py             # Memory context types - ~199 lines
├── lineage/             # Artifact lineage tracking (RFC-121) - already organized
│   ├── __init__.py
│   ├── dependencies.py
│   ├── human_detection.py
│   ├── identity.py
│   ├── listener.py
│   ├── models.py
│   └── store.py
├── session/             # Session tracking (RFC-120) - already organized
│   ├── __init__.py
│   ├── summary.py
│   └── tracker.py
└── simulacrum/          # Portable problem-solving context - already organized
    ├── __init__.py
    ├── core/
    ├── hierarchical/
    ├── topology/
    ├── extractors/
    ├── context/
    ├── manager/
    ├── identity.py
    ├── memory_tools.py
    ├── patterns.py
    ├── tracer.py
    └── unified_view.py
```

**Current imports**:
- `from sunwell.memory.briefing import Briefing, BriefingStatus, ...`
- `from sunwell.memory.persistent import PersistentMemory`
- `from sunwell.memory.types import MemoryContext, TaskMemoryContext, Promptable, SyncResult`
- `from sunwell.memory.simulacrum import *` (wildcard re-export)
- `from sunwell.memory.lineage import *` (wildcard re-export)
- `from sunwell.memory.session import *` (wildcard re-export)

---

## Proposed Structure

```
memory/
├── __init__.py              # Public API (backward compatible)
├── core/                    # Core types and models
│   ├── __init__.py
│   ├── types.py             # MemoryContext, TaskMemoryContext, Promptable, SyncResult
│   └── constants.py         # Memory-related constants (if any)
├── briefing/                # Briefing system (RFC-071)
│   ├── __init__.py
│   ├── briefing.py          # Briefing, BriefingStatus, ExecutionSummary
│   ├── compression.py       # compress_briefing, briefing_to_learning
│   └── prefetch.py          # PrefetchPlan, PrefetchedContext
├── facade/                  # Unified memory facade (RFC-MEMORY)
│   ├── __init__.py
│   └── persistent.py        # PersistentMemory class
├── lineage/                 # Artifact lineage tracking (RFC-121) - keep as-is
│   └── [unchanged]
├── session/                 # Session tracking (RFC-120) - keep as-is
│   └── [unchanged]
└── simulacrum/              # Portable problem-solving context - keep as-is
    └── [unchanged]
```

---

## Migration Mapping

### 1. Core Types (`memory/core/`)

**From**: `types.py`  
**To**: `core/types.py`

**Move**:
- `Promptable` protocol
- `MemoryContext` dataclass
- `TaskMemoryContext` dataclass
- `SyncResult` dataclass

**Extract to `core/constants.py`** (if any constants exist):
- Any memory-related constants (currently none, but reserved for future)

**New imports**:
```python
from sunwell.memory.core.types import (
    MemoryContext,
    Promptable,
    SyncResult,
    TaskMemoryContext,
)
```

---

### 2. Briefing System (`memory/briefing/`)

**From**: `briefing.py` (~480 lines)  
**To**: `briefing/briefing.py` + `briefing/compression.py` + `briefing/prefetch.py`

**Move to `briefing/briefing.py`**:
- `BriefingStatus` enum
- `Briefing` dataclass
- `ExecutionSummary` dataclass
- Core briefing logic (save, load, update methods if any)

**Move to `briefing/compression.py`**:
- `compress_briefing()` function
- `briefing_to_learning()` function
- Compression-related utilities

**Move to `briefing/prefetch.py`**:
- `PrefetchPlan` dataclass
- `PrefetchedContext` dataclass
- Prefetch-related logic

**Update imports**:
- Import `Learning` from `..agent.learning` (TYPE_CHECKING)
- Import types from `..core.types` if needed

**New imports**:
```python
from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchPlan,
    PrefetchedContext,
    briefing_to_learning,
    compress_briefing,
)
```

---

### 3. Persistent Memory Facade (`memory/facade/`)

**From**: `persistent.py` (~717 lines)  
**To**: `facade/persistent.py`

**Move**:
- `PersistentMemory` class
- All facade methods (`get_relevant`, `get_task_context`, `sync`, etc.)
- Module-level constants (`_CODE_KEYWORDS`, `_GENERATION_KEYWORDS`)

**Update imports**:
- Import `MemoryContext`, `TaskMemoryContext`, `SyncResult` from `..core.types`
- Import `Briefing` from `..briefing.briefing`
- Import from `..simulacrum.core.store` for SimulacrumStore
- Import from `..knowledge.codebase.*` for DecisionMemory, FailureMemory, PatternProfile
- Import from `..features.team.store` for TeamKnowledgeStore

**New imports**:
```python
from sunwell.memory.facade import PersistentMemory
```

---

### 4. Lineage (`memory/lineage/`)

**Status**: ✅ **Keep as-is** - Already well-organized

No changes needed. This subpackage is already properly structured.

---

### 5. Session (`memory/session/`)

**Status**: ✅ **Keep as-is** - Already well-organized

No changes needed. This subpackage is already properly structured.

---

### 6. Simulacrum (`memory/simulacrum/`)

**Status**: ✅ **Keep as-is** - Already well-organized

No changes needed. This subpackage is already properly structured with its own internal organization.

---

## Backward Compatibility

### Public API (`memory/__init__.py`)

Maintain all current exports for backward compatibility:

```python
"""Memory subsystem for Sunwell.

Contains:
- Briefing system (RFC-071) for rolling handoff notes
- PersistentMemory facade for unified memory access
- Memory context types for planning and execution
- Simulacrum, lineage, and session tracking

RFC-138: Module Architecture Consolidation
"""

# Core types
from sunwell.memory.core.types import (
    MemoryContext,
    Promptable,
    SyncResult,
    TaskMemoryContext,
)

# Briefing system
from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchPlan,
    PrefetchedContext,
    briefing_to_learning,
    compress_briefing,
)

# Persistent memory facade
from sunwell.memory.facade import PersistentMemory

# Re-exports from consolidated modules (Phase 5)
from sunwell.memory.simulacrum import *  # noqa: F403, F401
from sunwell.memory.lineage import *  # noqa: F403, F401
from sunwell.memory.session import *  # noqa: F403, F401

__all__ = [
    # Core types
    "MemoryContext",
    "Promptable",
    "TaskMemoryContext",
    "SyncResult",
    # Briefing types
    "Briefing",
    "BriefingStatus",
    "ExecutionSummary",
    "PrefetchPlan",
    "PrefetchedContext",
    "briefing_to_learning",
    "compress_briefing",
    # Persistent memory facade
    "PersistentMemory",
]
```

**Result**: All existing imports continue to work without changes.

---

## Implementation Steps

### Phase 1: Create New Structure

1. **Create subdirectories**:
   ```bash
   mkdir -p src/sunwell/memory/{core,briefing,facade}
   ```

2. **Create `__init__.py` files** for each new subpackage

### Phase 2: Move and Split Files

1. **Move core types**:
   - Create `core/types.py` with all types from `types.py`
   - Create `core/constants.py` (empty for now, reserved for future)
   - Update `core/__init__.py` to export types

2. **Split briefing**:
   - Create `briefing/briefing.py` with core briefing classes
   - Create `briefing/compression.py` with compression functions
   - Create `briefing/prefetch.py` with prefetch types
   - Update `briefing/__init__.py` to export all briefing APIs
   - Update imports in moved files

3. **Move persistent facade**:
   - Create `facade/persistent.py` with `PersistentMemory` class
   - Update imports to use `..core.types`, `..briefing.briefing`, etc.
   - Update `facade/__init__.py` to export `PersistentMemory`

### Phase 3: Update Public API

1. **Update `memory/__init__.py`**:
   - Re-export all public APIs from subpackages
   - Maintain backward compatibility
   - Keep wildcard re-exports for `simulacrum`, `lineage`, `session`

### Phase 4: Update Internal Imports

1. **Update cross-package imports**:
   - `memory/persistent.py` → `memory/facade/persistent.py` imports
   - `memory/briefing.py` → `memory/briefing/briefing.py` imports
   - `memory/types.py` → `memory/core/types.py` imports

2. **Update external imports** (verify no breakage):
   - Check all files importing from `sunwell.memory`
   - Verify imports still work (should all use public API)

### Phase 5: Cleanup

1. **Remove old files**:
   - Delete `briefing.py`, `persistent.py`, `types.py`

2. **Run tests**:
   - Verify all tests pass
   - Check import paths
   - Verify no circular imports

3. **Update documentation**:
   - Update any docs referencing old structure
   - Update RFC-071, RFC-MEMORY if needed

---

## File Size Analysis

**Current files**:
- `briefing.py`: ~480 lines (needs splitting)
- `persistent.py`: ~717 lines (large but cohesive)
- `types.py`: ~199 lines (reasonable size)

**After reorganization**:
- `core/types.py`: ~199 lines (unchanged)
- `core/constants.py`: ~10 lines (reserved for future)
- `briefing/briefing.py`: ~250 lines (core briefing classes)
- `briefing/compression.py`: ~150 lines (compression logic)
- `briefing/prefetch.py`: ~80 lines (prefetch types)
- `facade/persistent.py`: ~717 lines (unchanged, but better organized)

**Benefits**:
- Better separation of concerns (briefing split by functionality)
- Smaller, focused files
- Easier to navigate and maintain
- Consistent with agent/identity patterns

---

## Import Impact Analysis

**Files importing from `sunwell.memory`** (from grep analysis):

**External imports** (should continue working):
1. `src/sunwell/interface/cli/commands/goal.py` - Uses `PersistentMemory` ✅
2. `src/sunwell/interface/cli/commands/briefing_cmd.py` - Uses `Briefing`, `BriefingStatus` ✅
3. `src/sunwell/agent/core/agent.py` - Uses `PersistentMemory` ✅
4. `src/sunwell/agent/prefetch/dispatcher.py` - Uses `Briefing`, `PrefetchedContext`, `PrefetchPlan` ✅
5. `src/sunwell/planning/routing/briefing_router.py` - Uses `Briefing` ✅
6. `src/sunwell/interface/cli/chat/command.py` - Uses `SimulacrumStore` (via simulacrum) ✅
7. `src/sunwell/interface/cli/chat.py` - Uses `SimulacrumStore`, `ConversationDAG` (via simulacrum) ✅
8. `src/sunwell/agent/utils/builtin_templates.py` - Uses `Learning`, `TemplateData`, `TemplateVariable` (via simulacrum) ✅

**Internal imports** (will be updated):
1. `src/sunwell/memory/persistent.py` - Uses `types.py` → will use `core/types.py`
2. `src/sunwell/memory/briefing.py` - Uses `agent.learning` → will use `..agent.learning`
3. `src/sunwell/memory/session/tracker.py` - Uses `session.summary` → unchanged
4. `src/sunwell/memory/lineage/*` - Internal imports → unchanged

**Verification needed**:
- All external imports use `from sunwell.memory import ...` (public API) ✅
- No direct imports from `sunwell.memory.briefing` or `sunwell.memory.persistent` (except internal) ✅

---

## Testing Strategy

1. **Unit tests**: Verify each subpackage works independently
2. **Integration tests**: Verify public API still works
3. **Import tests**: Verify all imports resolve correctly
4. **CLI tests**: Verify `/briefing` commands work
5. **End-to-end**: Verify memory facade flow works
6. **Simulacrum tests**: Verify simulacrum imports still work

---

## Rollback Plan

If issues arise:
1. Keep old files until migration is verified
2. Use feature flag or gradual migration
3. Maintain both structures temporarily if needed

---

## Success Criteria

- ✅ All existing imports continue to work
- ✅ No breaking changes to public API
- ✅ Tests pass
- ✅ Code is more modular and maintainable
- ✅ Follows same pattern as `agent/` and `identity/` packages
- ✅ File sizes are reasonable (<300 lines per file, except facade which is cohesive)
- ✅ Briefing system properly split by functionality

---

## Open Questions

1. **Briefing split**: Should `briefing.py` be split into 3 files or kept as one?
   - **Decision**: Split into `briefing.py`, `compression.py`, `prefetch.py` for better organization
   - **Rationale**: Compression and prefetch are distinct concerns, even if related

2. **Facade location**: Should `persistent.py` go in `facade/` or `persistent/`?
   - **Decision**: Use `facade/` to match architectural pattern (facade pattern)
   - **Alternative considered**: `persistent/` but that implies it's the only persistent storage

3. **Constants**: Should constants be in `core/constants.py` or alongside types?
   - **Decision**: Separate `constants.py` for better organization (matches identity pattern)

4. **Wildcard re-exports**: Should we keep wildcard re-exports for simulacrum/lineage/session?
   - **Decision**: Keep for now (backward compatibility), consider removing in Phase 6 cleanup
   - **Rationale**: These are large subpackages with many exports, wildcard is convenient

---

## Related Work

- RFC-071: Briefing system design
- RFC-MEMORY: PersistentMemory facade design
- RFC-120: Session tracking
- RFC-121: Artifact lineage tracking
- RFC-138: Agent/Identity package reorganization (pattern reference)
- `agent/` package structure (reference implementation)
- `identity/` package reorganization plan (reference implementation)

---

## Next Steps

1. Review and approve plan
2. Create implementation branch
3. Execute Phase 1-5
4. Run tests and verify
5. Merge when complete
