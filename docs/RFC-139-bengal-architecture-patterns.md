# RFC-139: Bengal Architecture Patterns

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-25  
**Updated**: 2026-01-25  
**Related**: RFC-138 (Module Architecture Consolidation), RFC-110 (Agent Simplification)

---

## Executive Summary

Cross-pollination analysis of Bengal (documentation SSG) reveals architectural patterns that would strengthen Sunwell's codebase. This RFC proposes a **clean-break refactoring** — no backward compatibility shims, no deprecation warnings. Wire the new paths, update all imports, delete the old.

| Pattern | Bengal Has | Sunwell Lacks |
|---------|-----------|---------------|
| **Centralized Protocols** | `bengal/protocols/` — single source of truth | Protocols scattered across 12+ modules |
| **Passive Core Models** | `bengal/core/` explicitly forbids I/O | `sunwell/core/` mixes models with utilities |
| **Rich Error System** | Investigation helpers, session tracking | Single `SunwellError` class |
| **Module Size Discipline** | 400-line threshold | Files up to 1968 lines |

### Scope of Changes

| Category | Count | Action |
|----------|-------|--------|
| Protocols to move | 25 | Create `protocols/`, delete old locations |
| Protocol duplicates | 3 | Delete, keep one canonical |
| Files to rewrite imports | **~130** | Batch find-replace |
| Files to split (>400 lines) | 11 | Split into packages |
| New domain exceptions | 7 | Add to `errors/` |
| Old files to delete | ~8 | After migration complete |

**Approach**: Full refactor in one PR per phase. No shims. Tests must pass before merge.

---

## 🎯 Goals

| Goal | Benefit |
|------|---------|
| **Single canonical location** | No ambiguity about where things live |
| **Enforced passive core** | Predictable, testable data models |
| **AI-debuggable errors** | Investigation commands for self-healing |
| **Small, focused modules** | Easier review, faster navigation |

---

## 🚫 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Backward compatibility | Clean code > migration ease |
| Deprecation warnings | Noise; just fix the imports |
| Gradual rollout | Atomic changes are easier to reason about |

---

## Pattern 1: Centralized Protocols Package

### Target State

```
sunwell/protocols/
├── __init__.py              # Re-exports all protocols
├── serialization.py         # Serializable, DictSerializable
├── models.py                # ModelProtocol
├── tools.py                 # ToolExecutorProtocol, WebSearchProvider
├── memory.py                # MemoryStoreProtocol, Promptable, Embeddable
├── agent.py                 # EventEmitter, Renderer, ChatSessionProtocol
├── planning.py              # SkillExecutor, WorkerProtocol
├── infrastructure.py        # ConsoleProtocol, ParallelExecutorProtocol, HasStats, Saveable
├── interface.py             # InterfaceOutput, UIProtocol
└── capabilities.py          # TypeGuard protocols (HasTools, etc.)
```

### Files to Delete After Migration

| File | Protocols Moved |
|------|-----------------|
| `types/protocol.py` | All 8 protocols → `protocols/` |
| `workflow/types.py` | `Serializable` (duplicate) |
| `team/types.py` | `Serializable` (duplicate), `Embeddable` |
| `models/protocol.py` | `ModelProtocol` → `protocols/models.py`, data types stay |

### Import Rewrites (110 files)

```python
# BEFORE
from sunwell.models.protocol import ModelProtocol, Tool, ToolCall, Message
from sunwell.types.protocol import ToolExecutorProtocol, ConsoleProtocol

# AFTER
from sunwell.protocols import ModelProtocol, ToolExecutorProtocol, ConsoleProtocol
from sunwell.models.types import Tool, ToolCall, Message
```

### Wiring: Exact Files to Update

| Old Import | New Import | File Count |
|------------|------------|------------|
| `from sunwell.models.protocol import ModelProtocol` | `from sunwell.protocols import ModelProtocol` | 110 |
| `from sunwell.models.protocol import Tool, ToolCall, Message, ...` | `from sunwell.models.types import Tool, ToolCall, Message, ...` | 110 |
| `from sunwell.types.protocol import *Protocol` | `from sunwell.protocols import *Protocol` | ~25 |
| `from sunwell.workflow.types import Serializable` | `from sunwell.protocols import Serializable` | ~5 |
| `from sunwell.team.types import Serializable` | `from sunwell.protocols import Serializable` | ~3 |

**Batch command**:
```bash
# Run from src/sunwell/
rg -l "from sunwell.models.protocol import" | xargs sed -i '' \
  -e 's/from sunwell.models.protocol import ModelProtocol/from sunwell.protocols import ModelProtocol/g'

rg -l "from sunwell.types.protocol import" | xargs sed -i '' \
  -e 's/from sunwell.types.protocol import/from sunwell.protocols import/g'
```

---

## Pattern 2: Passive Core Models

### Target State

```
core/                    # PASSIVE ONLY
├── __init__.py          # No freethreading, no context
├── lens.py
├── persona.py
├── spell.py
├── types.py
├── errors.py
├── heuristic.py
├── identity.py
├── validator.py
├── workflow.py
└── framework.py

runtime/                 # ACTIVE UTILITIES (exists, expand it)
├── __init__.py
├── freethreading.py     # MOVED from core/
├── context.py           # MOVED from core/
├── parallel.py
├── types.py
└── ...
```

### Files to Update (5 total)

| File | Line | Old Import | New Import |
|------|------|------------|------------|
| `simulacrum/core/store.py` | 1133 | `from sunwell.core.freethreading import ...` | `from sunwell.runtime.freethreading import ...` |
| `workspace/indexer.py` | 22 | `from sunwell.core.freethreading import ...` | `from sunwell.runtime.freethreading import ...` |
| `runtime/parallel.py` | 30 | `from sunwell.core.freethreading import ...` | `from sunwell.runtime.freethreading import ...` |
| `cli/helpers.py` | 11 | `from sunwell.core.freethreading import ...` | `from sunwell.runtime.freethreading import ...` |
| `cli/runtime_cmd.py` | 9 | `from sunwell.core.freethreading import ...` | `from sunwell.runtime.freethreading import ...` |

### Files to Move

| Source | Destination |
|--------|-------------|
| `core/freethreading.py` | `runtime/freethreading.py` |
| `core/context.py` | `runtime/context.py` |

### core/__init__.py Update

```python
# REMOVE these exports:
# from sunwell.core.context import AppContext
# from sunwell.core.freethreading import (...)

# ADD docstring constraint:
"""
Core domain models for Sunwell.

⚠️ ARCHITECTURE CONSTRAINT:
- NO I/O (file reads, network calls)
- NO logging (no logger imports)
- NO side effects (no global state mutation)

Active utilities live in sunwell.runtime/
"""
```

---

## Pattern 3: Enhanced Error System

### Target State

```
core/errors/
├── __init__.py          # Exports all, lazy loads heavy modules
├── codes.py             # ErrorCode enum (exists)
├── exceptions.py        # SunwellError + domain subclasses
├── session.py           # ErrorSession for pattern tracking
├── aggregation.py       # ErrorAggregator for batch ops
└── reporter.py          # format_error_report (lazy loaded)
```

### Domain Exceptions to Add

```python
# core/errors/exceptions.py

class SunwellError(Exception):
    """Base class - add investigation helpers."""
    
    def get_investigation_commands(self) -> list[str]:
        """Return shell commands to debug this error."""
        ...
    
    def get_related_test_files(self) -> list[str]:
        """Return test files for this error category."""
        ...

class SunwellModelError(SunwellError):
    """LLM model operations."""

class SunwellToolError(SunwellError):
    """Tool execution."""

class SunwellLensError(SunwellError):
    """Lens loading/parsing."""

class SunwellAgentError(SunwellError):
    """Agent execution."""

class SunwellConfigError(SunwellError):
    """Configuration loading."""

class SunwellNetworkError(SunwellError):
    """Network operations."""

class SunwellValidationError(SunwellError):
    """Validation gates."""
```

### Files to Update (15 total)

| File | Current | Change To |
|------|---------|-----------|
| `models/ollama.py` | `raise SunwellError(ErrorCode.MODEL_*)` | `raise SunwellModelError(...)` |
| `models/openai.py` | `raise SunwellError(ErrorCode.MODEL_*)` | `raise SunwellModelError(...)` |
| `models/anthropic.py` | `raise SunwellError(ErrorCode.MODEL_*)` | `raise SunwellModelError(...)` |
| `embedding/ollama.py` | `raise SunwellError(ErrorCode.MODEL_*)` | `raise SunwellModelError(...)` |
| `runtime/model_router.py` | `raise SunwellError(ErrorCode.MODEL_*)` | `raise SunwellModelError(...)` |
| `cli/chat.py` | `except SunwellError` | `except SunwellModelError` |
| `cli/chat/command.py` | `except SunwellError` | `except SunwellModelError` |
| `schema/loader.py` | `raise SunwellError(ErrorCode.CONFIG_*)` | `raise SunwellConfigError(...)` |
| `fount/client.py` | `raise SunwellError(ErrorCode.NETWORK_*)` | `raise SunwellNetworkError(...)` |
| `cli/lens.py` | `raise SunwellError(ErrorCode.LENS_*)` | `raise SunwellLensError(...)` |
| `cli/main.py` | Keep generic handler | No change |
| `cli/error_handler.py` | Update to show investigation commands | Add `get_investigation_commands()` display |

---

## Pattern 4: Module Size Discipline (400-line threshold)

### Files to Split

| File | Lines | Split Into |
|------|-------|------------|
| `agent/core.py` | 1968 | `agent/core/` package (5 files) |
| `simulacrum/core/store.py` | 1903 | `simulacrum/core/store/` package |
| `naaru/planners/harmonic.py` | 1665 | `naaru/planners/harmonic/` package |
| `agent/loop.py` | 1549 | `agent/loop/` package |
| `cli/chat.py` | 1323 | `cli/chat/` package (partial exists) |
| `reasoning/reasoner.py` | 1321 | `reasoning/` package |
| `naaru/planners/artifact.py` | 1224 | `naaru/planners/artifact/` package |
| `routing/unified.py` | 603* | Already split, verify |
| `agent/learning.py` | 1129 | `agent/learning/` package |
| `benchmark/runner.py` | 1246 | `benchmark/runner/` package |
| `benchmark/cli.py` | 1070 | `benchmark/cli/` package |

*Note: `routing/unified.py` shows 603 lines now — already partially split.

### Split Template

```
# BEFORE: module.py (1000+ lines)

# AFTER: module/
├── __init__.py          # Re-exports public API only
├── core.py              # Main class (~400 lines)
├── helpers.py           # Helper functions
├── types.py             # Types and enums
└── ...
```

### `agent/core.py` Split Plan (1968 lines)

```
agent/core/
├── __init__.py          # from .agent import Agent; from .task_graph import TaskGraph
├── agent.py             # Agent class (~600 lines)
├── task_graph.py        # TaskGraph class (~400 lines)
├── execution.py         # Task execution logic (~400 lines)
├── planning.py          # Plan generation (~300 lines)
└── types.py             # AgentState, TaskResult (~200 lines)
```

### `agent/loop.py` Split Plan (1549 lines)

```
agent/loop/
├── __init__.py          # from .loop import AgentLoop, LoopConfig
├── loop.py              # AgentLoop class (~500 lines)
├── state.py             # LoopState management (~300 lines)
├── tool_handling.py     # Tool call processing (~400 lines)
├── streaming.py         # Stream handling (~200 lines)
└── types.py             # Config types (~150 lines)
```

---

## Implementation Checklist

### Phase 1: Protocols Package

- [ ] Create `protocols/__init__.py`
- [ ] Create `protocols/serialization.py` — move `Serializable`, `DictSerializable`
- [ ] Create `protocols/models.py` — move `ModelProtocol`
- [ ] Create `protocols/tools.py` — move `ToolExecutorProtocol`, `WebSearchProvider`
- [ ] Create `protocols/memory.py` — move `MemoryStoreProtocol`, `Promptable`, `Embeddable`
- [ ] Create `protocols/agent.py` — move `EventEmitter`, `Renderer`, `ChatSessionProtocol`
- [ ] Create `protocols/planning.py` — move `SkillExecutor`, `WorkerProtocol`
- [ ] Create `protocols/infrastructure.py` — move `ConsoleProtocol`, etc.
- [ ] Create `protocols/interface.py` — move `InterfaceOutput`, `UIProtocol`
- [ ] Create `protocols/capabilities.py` — move TypeGuard protocols
- [ ] Create `models/types.py` — move `Tool`, `ToolCall`, `Message`, etc. from `models/protocol.py`
- [ ] Update 110 files: `from sunwell.models.protocol import` → split imports
- [ ] Update ~25 files: `from sunwell.types.protocol import` → `from sunwell.protocols import`
- [ ] Delete `types/protocol.py`
- [ ] Delete `Serializable` from `workflow/types.py`
- [ ] Delete `Serializable`, `Embeddable` from `team/types.py`
- [ ] Delete `ModelProtocol` from `models/protocol.py` (keep data types or move to `models/types.py`)
- [ ] Run tests, fix failures

### Phase 2: Passive Core

- [ ] Move `core/freethreading.py` → `runtime/freethreading.py`
- [ ] Move `core/context.py` → `runtime/context.py`
- [ ] Update `core/__init__.py` — remove freethreading/context exports, add docstring
- [ ] Update 5 files importing `core.freethreading`
- [ ] Run tests, fix failures

### Phase 3: Error System

- [ ] Add `get_investigation_commands()` to `SunwellError`
- [ ] Add `get_related_test_files()` to `SunwellError`
- [ ] Create `SunwellModelError`, `SunwellToolError`, etc. in `core/errors/exceptions.py`
- [ ] Create `core/errors/session.py` with `ErrorSession`
- [ ] Add lazy loading to `core/errors/__init__.py`
- [ ] Update 15 files to use domain exceptions
- [ ] Update `cli/error_handler.py` to show investigation commands
- [ ] Run tests, fix failures

### Phase 4: Module Splitting

- [ ] Split `agent/core.py` → `agent/core/` package
- [ ] Split `agent/loop.py` → `agent/loop/` package
- [ ] Split `simulacrum/core/store.py` → `simulacrum/core/store/` package
- [ ] Split `naaru/planners/harmonic.py` → `naaru/planners/harmonic/` package
- [ ] Split `reasoning/reasoner.py` → `reasoning/` package
- [ ] Split remaining >400 line files
- [ ] Add CI check `scripts/ci/check_module_size.py`
- [ ] Add CI check `scripts/ci/check_passive_core.py`
- [ ] Run tests, fix failures

---

## CI Checks to Add

### 1. Passive Core Checker

```python
# scripts/ci/check_passive_core.py
"""FAIL if core/ imports I/O libraries."""

FORBIDDEN = {"logging", "open(", "requests", "httpx", "subprocess", "shutil"}
CORE_FILES = list(Path("src/sunwell/core").glob("*.py"))

for f in CORE_FILES:
    if f.name in {"__init__.py", "errors.py"}:
        continue  # errors.py may need logging
    content = f.read_text()
    for pattern in FORBIDDEN:
        if pattern in content:
            sys.exit(f"FORBIDDEN: {pattern} in {f}")
```

### 2. Module Size Checker

```python
# scripts/ci/check_module_size.py
"""FAIL if any .py file exceeds 400 lines."""

THRESHOLD = 400
EXEMPT = {"agent/event_schema.py"}  # Generated

for f in Path("src/sunwell").rglob("*.py"):
    if str(f) in EXEMPT:
        continue
    lines = len(f.read_text().splitlines())
    if lines > THRESHOLD:
        sys.exit(f"TOO LARGE: {f} has {lines} lines (max {THRESHOLD})")
```

### 3. Protocol Location Checker

```python
# scripts/ci/check_protocol_locations.py
"""FAIL if Protocol classes defined outside protocols/."""

for f in Path("src/sunwell").rglob("*.py"):
    if "protocols/" in str(f):
        continue
    content = f.read_text()
    if "class " in content and "(Protocol)" in content:
        sys.exit(f"PROTOCOL OUTSIDE protocols/: {f}")
```

---

## Appendix A: Complete Protocol Inventory

| Protocol | Current Location | New Location | Delete Original |
|----------|-----------------|--------------|-----------------|
| `Serializable` | `types/protocol.py` | `protocols/serialization.py` | ✓ |
| `Serializable` | `workflow/types.py` | DELETE (duplicate) | ✓ |
| `Serializable` | `team/types.py` | DELETE (duplicate) | ✓ |
| `DictSerializable` | `types/protocol.py` | `protocols/serialization.py` | ✓ |
| `ConsoleProtocol` | `types/protocol.py` | `protocols/infrastructure.py` | ✓ |
| `ChatSessionProtocol` | `types/protocol.py` | `protocols/agent.py` | ✓ |
| `MemoryStoreProtocol` | `types/protocol.py` | `protocols/memory.py` | ✓ |
| `ToolExecutorProtocol` | `types/protocol.py` | `protocols/tools.py` | ✓ |
| `ParallelExecutorProtocol` | `types/protocol.py` | `protocols/infrastructure.py` | ✓ |
| `WorkerProtocol` | `types/protocol.py` | `protocols/planning.py` | ✓ |
| `ModelProtocol` | `models/protocol.py` | `protocols/models.py` | ✓ |
| `EventEmitter` | `agent/event_schema.py` | `protocols/agent.py` | ✓ |
| `Renderer` | `agent/renderer.py` | `protocols/agent.py` | ✓ |
| `HasStats` | `routing/__init__.py` | `protocols/infrastructure.py` | ✓ |
| `SchemaAdapter` | `models/capability/schema.py` | `protocols/models.py` | ✓ |
| `SkillExecutor` | `workflow/engine.py` | `protocols/planning.py` | ✓ |
| `WebSearchProvider` | `tools/web_search.py` | `protocols/tools.py` | ✓ |
| `Embeddable` | `team/types.py` | `protocols/memory.py` | ✓ |
| `Saveable` | `runtime/types.py` | `protocols/infrastructure.py` | ✓ |
| `Promptable` | `memory/types.py` | `protocols/memory.py` | ✓ |
| `InterfaceOutput` | `interface/router.py` | `protocols/interface.py` | ✓ |
| `SummarizerProtocol` | `simulacrum/hierarchical/summarizer.py` | `protocols/memory.py` | ✓ |
| `UIProtocol` | `guardrails/escalation.py` | `protocols/interface.py` | ✓ |
| `FountProtocol` | `fount/client.py` | `protocols/features.py` | ✓ |
| `EventCallback` | `external/types.py` | `protocols/features.py` | ✓ |

---

## Appendix B: Data Types (Stay in `models/types.py`)

These are **data classes**, not protocols. They stay coupled to the models layer:

| Type | Current Location | New Location |
|------|-----------------|--------------|
| `Tool` | `models/protocol.py` | `models/types.py` |
| `ToolCall` | `models/protocol.py` | `models/types.py` |
| `Message` | `models/protocol.py` | `models/types.py` |
| `GenerateResult` | `models/protocol.py` | `models/types.py` |
| `GenerateOptions` | `models/protocol.py` | `models/types.py` |
| `TokenUsage` | `models/protocol.py` | `models/types.py` |

After split, `models/protocol.py` can be deleted entirely.

---

## Appendix C: Batch Rewrite Commands

```bash
# 1. Protocol imports (110 files)
rg -l "from sunwell\.models\.protocol import.*ModelProtocol" src/sunwell | \
  xargs sed -i '' 's/from sunwell\.models\.protocol import \(.*\)ModelProtocol\(.*\)/from sunwell.protocols import ModelProtocol\nfrom sunwell.models.types import \1\2/g'

# 2. types/protocol imports (~25 files)
rg -l "from sunwell\.types\.protocol import" src/sunwell | \
  xargs sed -i '' 's/from sunwell\.types\.protocol import/from sunwell.protocols import/g'

# 3. core.freethreading imports (5 files)
rg -l "from sunwell\.core\.freethreading import" src/sunwell | \
  xargs sed -i '' 's/from sunwell\.core\.freethreading import/from sunwell.runtime.freethreading import/g'

# 4. core.context imports
rg -l "from sunwell\.core\.context import" src/sunwell | \
  xargs sed -i '' 's/from sunwell\.core\.context import/from sunwell.runtime.context import/g'

# 5. Verify no old imports remain
rg "from sunwell\.(models\.protocol|types\.protocol|core\.freethreading|core\.context) import" src/sunwell
```

---

## References

- RFC-138: Module Architecture Consolidation
- Bengal codebase: `bengal/protocols/`, `bengal/core/`, `bengal/errors/`
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
