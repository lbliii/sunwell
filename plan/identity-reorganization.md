# Identity Package Reorganization Plan

**Status**: Draft  
**Date**: 2026-01-25  
**Pattern**: Follows `agent/` package reorganization (RFC-138)

---

## Overview

Reorganize `sunwell.identity` from flat structure to hierarchical subpackages, following the same pattern used for `agent/` package reorganization. This improves modularity, discoverability, and maintainability.

---

## Current Structure

```
identity/
├── __init__.py          # Public API exports
├── commands.py          # CLI command handlers
├── digest.py            # Identity synthesis/digest logic
├── extractor.py         # Behavior/fact extraction
├── injection.py         # System prompt injection
└── store.py             # Storage + models (Identity, Observation, IdentityStore)
```

**Current imports**:
- `from sunwell.identity.store import Identity, IdentityStore, Observation`
- `from sunwell.identity.extractor import extract_behaviors, extract_with_categories`
- `from sunwell.identity.digest import digest_identity`
- `from sunwell.identity.injection import build_system_prompt_with_identity`
- `from sunwell.identity.commands import handle_identity_command`

---

## Proposed Structure

```
identity/
├── __init__.py              # Public API (backward compatible)
├── core/                    # Core models and types
│   ├── __init__.py
│   ├── models.py            # Identity, Observation dataclasses
│   └── constants.py         # MIN_IDENTITY_CONFIDENCE, MAX_OBSERVATIONS_PER_SESSION, etc.
├── store/                   # Storage and persistence
│   ├── __init__.py
│   └── store.py             # IdentityStore class
├── extraction/              # Extraction logic
│   ├── __init__.py
│   ├── extractor.py         # extract_with_categories, extract_behaviors
│   └── patterns.py          # BEHAVIOR_PATTERNS regex patterns
├── synthesis/               # Identity synthesis/digest
│   ├── __init__.py
│   ├── digest.py            # digest_identity, quick_digest
│   └── prompts.py           # _DIGEST_PROMPT, extraction prompts
├── injection/               # System prompt integration
│   ├── __init__.py
│   └── injection.py         # build_system_prompt_with_identity, inject_identity, format_identity_panel
└── commands/                # CLI command handlers
    ├── __init__.py
    └── commands.py          # handle_identity_command, format_identity_display
```

---

## Migration Mapping

### 1. Core Models (`identity/core/`)

**From**: `store.py` (lines 32-127)  
**To**: `core/models.py`

**Move**:
- `Observation` dataclass
- `Identity` dataclass

**Extract to `core/constants.py`**:
- `MIN_IDENTITY_CONFIDENCE`
- `MAX_OBSERVATIONS_PER_SESSION`
- `MAX_OBSERVATIONS_GLOBAL`
- `MAX_IDENTITY_PROMPT_LENGTH`

**New imports**:
```python
from sunwell.identity.core.models import Identity, Observation
from sunwell.identity.core.constants import (
    MIN_IDENTITY_CONFIDENCE,
    MAX_OBSERVATIONS_PER_SESSION,
    MAX_OBSERVATIONS_GLOBAL,
    MAX_IDENTITY_PROMPT_LENGTH,
)
```

---

### 2. Storage (`identity/store/`)

**From**: `store.py` (lines 130-340)  
**To**: `store/store.py`

**Move**:
- `IdentityStore` class
- All storage methods (`_load`, `_save`, `add_observation`, `needs_digest`, `update_digest`, `pause`, `resume`, `clear`, `force_refresh`, `persist_to_global`, `export`)

**Update imports**:
- Import `Identity`, `Observation` from `..core.models`
- Import constants from `..core.constants`

**New imports**:
```python
from sunwell.identity.store import IdentityStore
```

---

### 3. Extraction (`identity/extraction/`)

**From**: `extractor.py`  
**To**: `extraction/extractor.py` + `extraction/patterns.py`

**Move to `extractor.py`**:
- `extract_behaviors()`
- `extract_with_categories()`
- `extract_behaviors_regex()`
- `_is_low_quality()`
- `_categorize_fact()`

**Move to `patterns.py`**:
- `BEHAVIOR_PATTERNS` dict
- `_TWO_TIER_EXTRACTION_PROMPT`
- `_BEHAVIOR_EXTRACTION_PROMPT`

**Update imports**:
- Import `Identity` from `..core.models` (for type hints)

**New imports**:
```python
from sunwell.identity.extraction import extract_behaviors, extract_with_categories
```

---

### 4. Synthesis (`identity/synthesis/`)

**From**: `digest.py`  
**To**: `synthesis/digest.py` + `synthesis/prompts.py`

**Move to `digest.py`**:
- `digest_identity()`
- `quick_digest()`
- `_extract_confidence()`
- `_extract_prompt()`
- `_extract_tone()`
- `_extract_values()`

**Move to `prompts.py`**:
- `_DIGEST_PROMPT`
- `_TWO_TIER_EXTRACTION_PROMPT` (if shared with extraction)
- `_BEHAVIOR_EXTRACTION_PROMPT` (if shared with extraction)

**Update imports**:
- Import `Identity` from `..core.models`
- Import constants from `..core.constants`

**New imports**:
```python
from sunwell.identity.synthesis import digest_identity, quick_digest
```

---

### 5. Injection (`identity/injection/`)

**From**: `injection.py`  
**To**: `injection/injection.py`

**Move**:
- `build_system_prompt_with_identity()`
- `inject_identity()`
- `_format_lens_identity()`
- `format_identity_panel()`

**Update imports**:
- Import `Identity`, `IdentityStore` from `..store`
- Import constants from `..core.constants`

**New imports**:
```python
from sunwell.identity.injection import (
    build_system_prompt_with_identity,
    inject_identity,
    format_identity_panel,
)
```

---

### 6. Commands (`identity/commands/`)

**From**: `commands.py`  
**To**: `commands/commands.py`

**Move**:
- `handle_identity_command()`
- `format_identity_display()`
- `_handle_rate()`
- `_handle_refresh()`
- `_handle_export()`

**Update imports**:
- Import `IdentityStore` from `..store`
- Import `digest_identity`, `quick_digest` from `..synthesis`

**New imports**:
```python
from sunwell.identity.commands import handle_identity_command, format_identity_display
```

---

## Backward Compatibility

### Public API (`identity/__init__.py`)

Maintain all current exports for backward compatibility:

```python
"""Identity module - Adaptive behavioral learning for personalized interaction.

RFC-023: Two-tier learning system that captures both facts and behaviors:
- Facts → Inject into context for recall
- Behaviors → Digest into evolving identity prompt that shapes interaction

Key components:
- extraction: Two-tier extraction (facts vs behaviors) from user messages
- store: Identity storage with session/global persistence
- synthesis: Behavior → Identity synthesis with adaptive frequency
- injection: System prompt integration
"""

# Core models
from sunwell.identity.core.models import Identity, Observation

# Storage
from sunwell.identity.store import IdentityStore

# Extraction
from sunwell.identity.extraction import extract_behaviors, extract_with_categories

# Synthesis
from sunwell.identity.synthesis import digest_identity

# Injection
from sunwell.identity.injection import build_system_prompt_with_identity

# Commands (optional, may not need to export)
# from sunwell.identity.commands import handle_identity_command

__all__ = [
    # Core
    "Identity",
    "IdentityStore",
    "Observation",
    # Extraction
    "extract_with_categories",
    "extract_behaviors",
    # Synthesis
    "digest_identity",
    # Injection
    "build_system_prompt_with_identity",
]
```

**Result**: All existing imports continue to work without changes.

---

## Implementation Steps

### Phase 1: Create New Structure

1. **Create subdirectories**:
   ```bash
   mkdir -p src/sunwell/identity/{core,store,extraction,synthesis,injection,commands}
   ```

2. **Create `__init__.py` files** for each subpackage

### Phase 2: Move and Split Files

1. **Extract constants**:
   - Create `core/constants.py` with all constants
   - Update imports in moved files

2. **Move models**:
   - Create `core/models.py` with `Identity` and `Observation`
   - Update all imports

3. **Move storage**:
   - Create `store/store.py` with `IdentityStore`
   - Update imports to use `..core.models` and `..core.constants`

4. **Move extraction**:
   - Create `extraction/extractor.py` with extraction functions
   - Create `extraction/patterns.py` with regex patterns and prompts
   - Update imports

5. **Move synthesis**:
   - Create `synthesis/digest.py` with digest functions
   - Create `synthesis/prompts.py` with prompts (or keep in digest.py if not shared)
   - Update imports

6. **Move injection**:
   - Create `injection/injection.py` with injection functions
   - Update imports

7. **Move commands**:
   - Create `commands/commands.py` with command handlers
   - Update imports

### Phase 3: Update Public API

1. **Update `identity/__init__.py`**:
   - Re-export all public APIs from subpackages
   - Maintain backward compatibility

### Phase 4: Update Internal Imports

1. **Update cross-package imports**:
   - `identity/digest.py` → `identity/synthesis/digest.py` imports
   - `identity/extractor.py` → `identity/extraction/extractor.py` imports
   - `identity/injection.py` → `identity/injection/injection.py` imports
   - `identity/commands.py` → `identity/commands/commands.py` imports

2. **Update external imports** (if any break):
   - Check all files importing from `sunwell.identity`
   - Verify imports still work

### Phase 5: Cleanup

1. **Remove old files**:
   - Delete `store.py`, `extractor.py`, `digest.py`, `injection.py`, `commands.py`

2. **Run tests**:
   - Verify all tests pass
   - Check import paths

3. **Update documentation**:
   - Update any docs referencing old structure
   - Update RFC-023 if needed

---

## File Size Analysis

**Current files**:
- `store.py`: ~340 lines (models + storage)
- `extractor.py`: ~308 lines
- `digest.py`: ~202 lines
- `injection.py`: ~192 lines
- `commands.py`: ~311 lines

**After reorganization**:
- `core/models.py`: ~100 lines (Identity + Observation)
- `core/constants.py`: ~10 lines
- `store/store.py`: ~240 lines (IdentityStore only)
- `extraction/extractor.py`: ~200 lines
- `extraction/patterns.py`: ~100 lines
- `synthesis/digest.py`: ~150 lines
- `synthesis/prompts.py`: ~50 lines (optional)
- `injection/injection.py`: ~130 lines
- `commands/commands.py`: ~310 lines

**Benefits**:
- Better separation of concerns
- Smaller, focused files
- Easier to navigate and maintain

---

## Import Impact Analysis

**Files importing from `sunwell.identity`**:
1. `src/sunwell/identity/__init__.py` - Will be updated
2. `src/sunwell/identity/digest.py` - Internal, will be moved
3. `src/sunwell/identity/injection.py` - Internal, will be moved
4. `src/sunwell/identity/commands.py` - Internal, will be moved
5. `src/sunwell/memory/simulacrum/unified_view.py` - External, should continue working
6. `src/sunwell/interface/cli/chat/command.py` - External, should continue working

**Verification needed**:
- All external imports use `from sunwell.identity import ...` (public API)
- No direct imports from `sunwell.identity.store` or `sunwell.identity.extractor` (except internal)

---

## Testing Strategy

1. **Unit tests**: Verify each subpackage works independently
2. **Integration tests**: Verify public API still works
3. **Import tests**: Verify all imports resolve correctly
4. **CLI tests**: Verify `/identity` commands work
5. **End-to-end**: Verify identity learning flow works

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
- ✅ Follows same pattern as `agent/` package
- ✅ File sizes are reasonable (<300 lines per file)

---

## Open Questions

1. **Prompts location**: Should prompts be in separate `prompts.py` files or kept with their usage?
   - **Decision**: Keep prompts with their usage files unless shared across modules

2. **Constants**: Should constants be in `core/constants.py` or alongside models?
   - **Decision**: Separate `constants.py` for better organization

3. **Commands export**: Should `handle_identity_command` be exported from `__init__.py`?
   - **Decision**: No, commands are CLI-specific and not part of core API

---

## Related Work

- RFC-023: Identity system design
- RFC-138: Agent package reorganization (pattern reference)
- `agent/` package structure (reference implementation)

---

## Next Steps

1. Review and approve plan
2. Create implementation branch
3. Execute Phase 1-5
4. Run tests and verify
5. Merge when complete
