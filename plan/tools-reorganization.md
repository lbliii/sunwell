# Tools Package Reorganization Plan

**Status**: Draft  
**Date**: 2026-01-25  
**Pattern**: Follows `agent/` and `identity/` package reorganization (RFC-138)

---

## Overview

Reorganize `sunwell.tools` from mixed flat/hierarchical structure to consistent hierarchical subpackages, following the same pattern used for `agent/` and `identity/` package reorganization. This improves modularity, discoverability, and maintainability.

---

## Current Structure

```
tools/
├── __init__.py              # Public API exports
├── builtins.py              # Tool definitions (CORE_TOOLS, GIT_TOOLS, ENV_TOOLS, EXPERTISE_TOOLS)
├── types.py                 # ToolTrust enum, ToolResult, ToolRateLimits, TRUST_LEVEL_TOOLS
├── executor.py              # ToolExecutor class
├── errors.py                # ToolError, ToolErrorCode, error handling utilities
├── progressive.py           # Progressive tool enablement (RFC-134)
├── prompted.py              # Prompted tools
├── run_analyzer.py          # Run analysis utilities
├── invocation_tracker.py    # Tool invocation tracking
├── web_search.py            # Web search provider protocol and implementation
├── expertise.py             # ExpertiseToolHandler (RFC-027)
├── sunwell_tools.py         # Sunwell self-access tool definitions (RFC-125)
├── sunwell_handlers.py      # Sunwell tool handlers (RFC-125)
└── handlers/                # Handler implementations
    ├── __init__.py
    ├── base.py              # BaseHandler, PathSecurityError
    ├── file.py              # FileHandlers
    ├── git.py               # GitHandlers
    ├── shell.py             # ShellHandlers
    └── env.py               # EnvHandlers
```

**Current imports**:
- `from sunwell.tools import ToolTrust, ToolResult, ToolRateLimits, TRUST_LEVEL_TOOLS`
- `from sunwell.tools import CORE_TOOLS, GIT_TOOLS, ENV_TOOLS, EXPERTISE_TOOLS`
- `from sunwell.tools import ToolExecutor`
- `from sunwell.tools import CoreToolHandlers, PathSecurityError`
- `from sunwell.tools import WebSearchProvider, WebSearchHandler, OllamaWebSearch`
- `from sunwell.tools import ExpertiseToolHandler, get_self_directed_prompt`

---

## Proposed Structure

```
tools/
├── __init__.py                  # Public API (backward compatible)
├── core/                        # Core types, enums, constants
│   ├── __init__.py
│   ├── types.py                 # ToolTrust enum, ToolResult, ToolRateLimits
│   └── constants.py             # TRUST_LEVEL_TOOLS, tool category constants
├── definitions/                 # Tool definitions
│   ├── __init__.py
│   ├── builtins.py              # CORE_TOOLS, GIT_TOOLS, ENV_TOOLS, EXPERTISE_TOOLS
│   └── sunwell.py               # Sunwell self-access tools (RFC-125)
├── execution/                   # Execution engine
│   ├── __init__.py
│   └── executor.py              # ToolExecutor class
├── handlers/                    # Handler implementations (keep as-is)
│   ├── __init__.py
│   ├── base.py
│   ├── file.py
│   ├── git.py
│   ├── shell.py
│   └── env.py
├── providers/                   # External tool providers
│   ├── __init__.py
│   ├── web_search.py            # WebSearchProvider, OllamaWebSearch, WebSearchHandler
│   └── expertise.py             # ExpertiseToolHandler, get_self_directed_prompt
├── sunwell/                     # Sunwell-specific handlers
│   ├── __init__.py
│   └── handlers.py               # SunwellToolHandlers (RFC-125)
├── errors/                      # Error handling
│   ├── __init__.py
│   └── errors.py                # ToolError, ToolErrorCode, error utilities
├── progressive/                 # Progressive tool enablement
│   ├── __init__.py
│   └── enablement.py            # Progressive tool enablement logic (RFC-134)
├── tracking/                    # Tool invocation tracking and analysis
│   ├── __init__.py
│   ├── tracker.py               # InvocationTracker
│   └── analyzer.py              # Run analyzer utilities
└── prompted/                    # Prompted tools
    ├── __init__.py
    └── prompted.py              # Prompted tool definitions
```

---

## Migration Mapping

### 1. Core Types (`tools/core/`)

**From**: `types.py`  
**To**: `core/types.py` + `core/constants.py`

**Move to `core/types.py`**:
- `ToolTrust` enum
- `ToolResult` dataclass
- `ToolRateLimits` dataclass

**Move to `core/constants.py`**:
- `TRUST_LEVEL_TOOLS` dict
- Tool category constants (if extracted from executor.py):
  - `_MEMORY_TOOLS`
  - `_SIMULACRUM_TOOLS`
  - `_WEB_TOOLS`
  - `_MIRROR_TOOLS`
  - `_EXPERTISE_TOOLS`
  - `_SUNWELL_TOOLS`

**New imports**:
```python
from sunwell.tools.core.types import ToolTrust, ToolResult, ToolRateLimits
from sunwell.tools.core.constants import TRUST_LEVEL_TOOLS
```

---

### 2. Tool Definitions (`tools/definitions/`)

**From**: `builtins.py`  
**To**: `definitions/builtins.py`

**Move**:
- `CORE_TOOLS` dict
- `GIT_TOOLS` dict
- `ENV_TOOLS` dict
- `EXPERTISE_TOOLS` dict
- `ENV_ALLOWLIST` set
- `ENV_BLOCKLIST_PATTERNS` set
- `get_all_tools()` function
- `get_tools_for_trust_level()` function

**From**: `sunwell_tools.py`  
**To**: `definitions/sunwell.py`

**Move**:
- `INTEL_TOOLS` dict
- `SEMANTIC_TOOLS` dict
- `LINEAGE_TOOLS` dict
- `WEAKNESS_TOOLS` dict
- `SELF_TOOLS` dict
- `WORKFLOW_TOOLS` dict
- `SUNWELL_TOOLS` dict (combined)

**Update imports**:
- Import `Tool` from `sunwell.models`
- Import `ToolTrust` from `..core.types`

**New imports**:
```python
from sunwell.tools.definitions import (
    CORE_TOOLS,
    GIT_TOOLS,
    ENV_TOOLS,
    EXPERTISE_TOOLS,
    ENV_ALLOWLIST,
    ENV_BLOCKLIST_PATTERNS,
    get_all_tools,
    get_tools_for_trust_level,
)
from sunwell.tools.definitions.sunwell import SUNWELL_TOOLS
```

---

### 3. Execution (`tools/execution/`)

**From**: `executor.py`  
**To**: `execution/executor.py`

**Move**:
- `ToolExecutor` class
- All execution logic and routing

**Update imports**:
- Import `ToolTrust`, `ToolResult`, `ToolRateLimits` from `..core.types`
- Import `TRUST_LEVEL_TOOLS` from `..core.constants`
- Import tool definitions from `..definitions`
- Import handlers from `..handlers`
- Import providers from `..providers`
- Import sunwell handlers from `..sunwell`

**New imports**:
```python
from sunwell.tools.execution import ToolExecutor
```

---

### 4. Handlers (`tools/handlers/`)

**Status**: Keep as-is (already well-organized)

**No changes needed** - handlers are already in a subpackage with clear separation.

---

### 5. Providers (`tools/providers/`)

**From**: `web_search.py`  
**To**: `providers/web_search.py`

**Move**:
- `WebSearchProvider` Protocol
- `WebSearchResult` dataclass
- `WebFetchResult` dataclass
- `OllamaWebSearch` class
- `WebSearchHandler` class
- `create_web_search_provider()` function

**From**: `expertise.py`  
**To**: `providers/expertise.py`

**Move**:
- `ExpertiseToolHandler` class
- `get_self_directed_prompt()` function

**Update imports**:
- Import types from `..core.types` if needed

**New imports**:
```python
from sunwell.tools.providers import (
    WebSearchProvider,
    WebSearchResult,
    WebFetchResult,
    WebSearchHandler,
    OllamaWebSearch,
    create_web_search_provider,
)
from sunwell.tools.providers.expertise import (
    ExpertiseToolHandler,
    get_self_directed_prompt,
)
```

---

### 6. Sunwell Handlers (`tools/sunwell/`)

**From**: `sunwell_handlers.py`  
**To**: `sunwell/handlers.py`

**Move**:
- `SunwellToolHandlers` class
- All sunwell-specific handler methods

**Update imports**:
- Import tool definitions from `..definitions.sunwell`
- Import types from `..core.types`

**New imports**:
```python
from sunwell.tools.sunwell import SunwellToolHandlers
```

---

### 7. Errors (`tools/errors/`)

**From**: `errors.py`  
**To**: `errors/errors.py`

**Move**:
- `ToolErrorCode` enum
- `ToolError` dataclass
- `should_retry()` function
- `get_retry_strategy()` function
- `format_error_for_model()` function

**New imports**:
```python
from sunwell.tools.errors import (
    ToolError,
    ToolErrorCode,
    should_retry,
    get_retry_strategy,
    format_error_for_model,
)
```

---

### 8. Progressive Enablement (`tools/progressive/`)

**From**: `progressive.py`  
**To**: `progressive/enablement.py`

**Move**:
- `ProgressiveToolEnabler` class (if exists)
- Progressive enablement logic
- Tool availability functions

**Update imports**:
- Import `ToolTrust` from `..core.types`
- Import `TRUST_LEVEL_TOOLS` from `..core.constants`

**New imports**:
```python
from sunwell.tools.progressive import ProgressiveToolEnabler  # if exists
```

---

### 9. Tracking (`tools/tracking/`)

**From**: `invocation_tracker.py`  
**To**: `tracking/tracker.py`

**Move**:
- `InvocationTracker` class
- Tracking logic

**From**: `run_analyzer.py`  
**To**: `tracking/analyzer.py`

**Move**:
- Run analysis utilities
- Analysis functions

**New imports**:
```python
from sunwell.tools.tracking import InvocationTracker
from sunwell.tools.tracking.analyzer import ...  # specific functions if needed
```

---

### 10. Prompted Tools (`tools/prompted/`)

**From**: `prompted.py`  
**To**: `prompted/prompted.py`

**Move**:
- Prompted tool definitions
- Prompted tool logic

**New imports**:
```python
from sunwell.tools.prompted import ...  # specific exports if needed
```

---

## Backward Compatibility

### Public API (`tools/__init__.py`)

Maintain all current exports for backward compatibility:

```python
"""Tool calling support for Sunwell (RFC-012, RFC-024, RFC-027).

This package provides:
- ToolTrust: Trust levels for tool execution
- CORE_TOOLS: Built-in tool definitions
- GIT_TOOLS: Git operation tools (RFC-024)
- ENV_TOOLS: Environment variable tools (RFC-024)
- EXPERTISE_TOOLS: Self-directed expertise retrieval tools (RFC-027)
- CoreToolHandlers: Handlers for built-in tools
- ToolExecutor: Tool dispatch and execution
- ExpertiseToolHandler: Handler for expertise tools (RFC-027)
- WebSearchProvider: Protocol for web search providers
- OllamaWebSearch: Web search via Ollama API
"""

# Core types
from sunwell.tools.core.types import ToolTrust, ToolResult, ToolRateLimits
from sunwell.tools.core.constants import TRUST_LEVEL_TOOLS

# Tool definitions
from sunwell.tools.definitions import (
    CORE_TOOLS,
    GIT_TOOLS,
    ENV_TOOLS,
    EXPERTISE_TOOLS,
    ENV_ALLOWLIST,
    ENV_BLOCKLIST_PATTERNS,
    get_all_tools,
    get_tools_for_trust_level,
)

# Execution
from sunwell.tools.execution import ToolExecutor

# Handlers
from sunwell.tools.handlers import CoreToolHandlers, PathSecurityError

# Providers
from sunwell.tools.providers import (
    WebSearchProvider,
    WebSearchResult,
    WebFetchResult,
    WebSearchHandler,
    OllamaWebSearch,
    create_web_search_provider,
)
from sunwell.tools.providers.expertise import (
    ExpertiseToolHandler,
    get_self_directed_prompt,
)

# Sunwell handlers
from sunwell.tools.sunwell import SunwellToolHandlers

# Errors
from sunwell.tools.errors import (
    ToolError,
    ToolErrorCode,
    should_retry,
    get_retry_strategy,
    format_error_for_model,
)

__all__ = [
    # Trust levels
    "ToolTrust",
    "ToolResult",
    "ToolRateLimits",
    "TRUST_LEVEL_TOOLS",
    # Tool definitions
    "CORE_TOOLS",
    "GIT_TOOLS",
    "ENV_TOOLS",
    "EXPERTISE_TOOLS",
    "ENV_ALLOWLIST",
    "ENV_BLOCKLIST_PATTERNS",
    "get_tools_for_trust_level",
    "get_all_tools",
    # Handlers and execution
    "CoreToolHandlers",
    "PathSecurityError",
    "ToolExecutor",
    # Expertise tools (RFC-027)
    "ExpertiseToolHandler",
    "get_self_directed_prompt",
    # Web search
    "WebSearchProvider",
    "WebSearchResult",
    "WebFetchResult",
    "WebSearchHandler",
    "OllamaWebSearch",
    "create_web_search_provider",
    # Errors
    "ToolError",
    "ToolErrorCode",
    "should_retry",
    "get_retry_strategy",
    "format_error_for_model",
]
```

**Result**: All existing imports continue to work without changes.

---

## Implementation Steps

### Phase 1: Create New Structure

1. **Create subdirectories**:
   ```bash
   mkdir -p src/sunwell/tools/{core,definitions,execution,providers,sunwell,errors,progressive,tracking,prompted}
   ```

2. **Create `__init__.py` files** for each subpackage

### Phase 2: Extract Core Types and Constants

1. **Create `core/types.py`**:
   - Move `ToolTrust` enum from `types.py`
   - Move `ToolResult` dataclass from `types.py`
   - Move `ToolRateLimits` dataclass from `types.py`

2. **Create `core/constants.py`**:
   - Move `TRUST_LEVEL_TOOLS` from `types.py`
   - Extract tool category constants from `executor.py` (if not already in types)

3. **Update imports** in moved files

### Phase 3: Move Tool Definitions

1. **Create `definitions/builtins.py`**:
   - Move all content from `builtins.py`
   - Update imports to use `..core.types` and `..core.constants`

2. **Create `definitions/sunwell.py`**:
   - Move all content from `sunwell_tools.py`
   - Update imports

3. **Update `definitions/__init__.py`** to export public APIs

### Phase 4: Move Execution Engine

1. **Create `execution/executor.py`**:
   - Move `ToolExecutor` class from `executor.py`
   - Update all imports to use new subpackage structure

2. **Update `execution/__init__.py`** to export `ToolExecutor`

### Phase 5: Move Providers

1. **Create `providers/web_search.py`**:
   - Move all content from `web_search.py`
   - Update imports

2. **Create `providers/expertise.py`**:
   - Move all content from `expertise.py`
   - Update imports

3. **Update `providers/__init__.py`** to export public APIs

### Phase 6: Move Sunwell Handlers

1. **Create `sunwell/handlers.py`**:
   - Move all content from `sunwell_handlers.py`
   - Update imports

2. **Update `sunwell/__init__.py`** to export `SunwellToolHandlers`

### Phase 7: Move Errors

1. **Create `errors/errors.py`**:
   - Move all content from `errors.py`
   - Update imports if needed

2. **Update `errors/__init__.py`** to export public APIs

### Phase 8: Move Progressive and Tracking

1. **Create `progressive/enablement.py`**:
   - Move all content from `progressive.py`
   - Update imports

2. **Create `tracking/tracker.py`**:
   - Move all content from `invocation_tracker.py`
   - Update imports

3. **Create `tracking/analyzer.py`**:
   - Move all content from `run_analyzer.py`
   - Update imports

4. **Create `prompted/prompted.py`**:
   - Move all content from `prompted.py`
   - Update imports

### Phase 9: Update Public API

1. **Update `tools/__init__.py`**:
   - Re-export all public APIs from subpackages
   - Maintain backward compatibility

### Phase 10: Update Internal Imports

1. **Update cross-package imports**:
   - Update all files importing from `sunwell.tools` to use new structure
   - Verify internal imports within tools package

2. **Update external imports** (if any break):
   - Check all files importing from `sunwell.tools`
   - Verify imports still work (should all use public API)

### Phase 11: Cleanup

1. **Remove old files**:
   - Delete `builtins.py`, `types.py`, `executor.py`, `errors.py`
   - Delete `progressive.py`, `prompted.py`, `run_analyzer.py`, `invocation_tracker.py`
   - Delete `web_search.py`, `expertise.py`, `sunwell_tools.py`, `sunwell_handlers.py`

2. **Run tests**:
   - Verify all tests pass
   - Check import paths

3. **Update documentation**:
   - Update any docs referencing old structure
   - Update RFC-012, RFC-024, RFC-027, RFC-125, RFC-134 if needed

---

## File Size Analysis

**Current files**:
- `builtins.py`: ~738 lines (tool definitions)
- `types.py`: ~230 lines (types + constants)
- `executor.py`: ~751 lines (execution engine)
- `errors.py`: ~313 lines (error handling)
- `progressive.py`: ~230 lines (progressive enablement)
- `web_search.py`: ~311 lines (web search provider)
- `expertise.py`: ~383 lines (expertise handler)
- `sunwell_tools.py`: ~343 lines (sunwell tool definitions)
- `sunwell_handlers.py`: ~? lines (sunwell handlers)
- `invocation_tracker.py`: ~? lines
- `run_analyzer.py`: ~? lines
- `prompted.py`: ~? lines

**After reorganization**:
- `core/types.py`: ~150 lines (types only)
- `core/constants.py`: ~80 lines (constants only)
- `definitions/builtins.py`: ~738 lines (unchanged)
- `definitions/sunwell.py`: ~343 lines (unchanged)
- `execution/executor.py`: ~751 lines (unchanged, but cleaner imports)
- `providers/web_search.py`: ~311 lines (unchanged)
- `providers/expertise.py`: ~383 lines (unchanged)
- `sunwell/handlers.py`: ~? lines (unchanged)
- `errors/errors.py`: ~313 lines (unchanged)
- `progressive/enablement.py`: ~230 lines (unchanged)
- `tracking/tracker.py`: ~? lines
- `tracking/analyzer.py`: ~? lines
- `prompted/prompted.py`: ~? lines

**Benefits**:
- Better separation of concerns
- Clearer package boundaries
- Easier to navigate and maintain
- Follows established pattern from `agent/` and `identity/`

---

## Import Impact Analysis

**Files importing from `sunwell.tools`** (48 files found):
- Internal tools package files - Will be updated
- External files (agent, interface, tests, etc.) - Should continue working via public API

**Verification needed**:
- All external imports use `from sunwell.tools import ...` (public API)
- No direct imports from `sunwell.tools.builtins` or `sunwell.tools.executor` (except internal)
- Check for any `from sunwell.tools.types import` that should use `from sunwell.tools import`

---

## Testing Strategy

1. **Unit tests**: Verify each subpackage works independently
2. **Integration tests**: Verify public API still works
3. **Import tests**: Verify all imports resolve correctly
4. **Tool execution tests**: Verify tool calling flow works
5. **End-to-end**: Verify agent tool usage works

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
- ✅ File sizes are reasonable
- ✅ Clear separation of concerns

---

## Open Questions

1. **Tool category constants**: Should constants like `_MEMORY_TOOLS`, `_WEB_TOOLS` be in `core/constants.py` or stay in `execution/executor.py`?
   - **Decision**: Move to `core/constants.py` for better organization and reusability

2. **Prompted tools**: Are prompted tools actively used or can they be deprecated?
   - **Decision**: Keep for now, can be deprecated later if unused

3. **Run analyzer**: Is this actively used or can it be moved to a separate utility package?
   - **Decision**: Keep in tools package as it's tool-specific analysis

---

## Related Work

- RFC-012: Tool calling system design
- RFC-024: Git and environment tools
- RFC-027: Expertise tools
- RFC-125: Sunwell self-access tools
- RFC-134: Progressive tool enablement
- RFC-138: Agent/Identity package reorganization (pattern reference)
- `agent/` package structure (reference implementation)
- `identity/` package structure (reference implementation)

---

## Next Steps

1. Review and approve plan
2. Create implementation branch
3. Execute Phase 1-11
4. Run tests and verify
5. Merge when complete
