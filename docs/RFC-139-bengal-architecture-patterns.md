# RFC-139: Bengal Architecture Patterns

**RFC Status**: Draft  
**Author**: Architecture Team  
**Created**: 2026-01-25  
**Updated**: 2026-01-25  
**Related**: RFC-138 (Module Architecture Consolidation), RFC-110 (Agent Simplification)

---

## Executive Summary

Cross-pollination analysis of Bengal (documentation SSG) reveals architectural patterns that would strengthen Sunwell's codebase. While RFC-138 addresses module *organization*, this RFC addresses module *design patterns*:

| Pattern | Bengal Has | Sunwell Lacks |
|---------|-----------|---------------|
| **Centralized Protocols** | `bengal/protocols/` — single source of truth for all interface contracts | Protocols scattered across modules |
| **Passive Core Models** | `bengal/core/` explicitly forbids I/O | `sunwell/core/` mixes models with utilities |
| **Rich Error System** | Investigation helpers, lazy loading, error aggregation, session tracking | Single `SunwellError` class, no lazy loading |
| **Module Size Discipline** | 400-line threshold, explicit splitting rules | Large files (e.g., `routing/unified.py` at 1160 lines) |

**Current**: Good foundations, but patterns inconsistently applied

**Proposed**: Adopt Bengal's battle-tested patterns to improve maintainability, debuggability, and contributor experience

### Scope of Changes

| Category | Count | Examples |
|----------|-------|----------|
| Protocols to consolidate | 25 | `ModelProtocol`, `ToolExecutorProtocol`, `EventEmitter` |
| Protocol duplicates to remove | 3 | `Serializable` defined 3 times |
| Files importing `models/protocol.py` | **110** | `agent/core.py`, `routing/unified.py`, etc. |
| Files to update (freethreading) | 5 | `simulacrum/core/store.py`, `workspace/indexer.py` |
| Files using `SunwellError` | 15 | `cli/chat.py`, `models/anthropic.py` |
| Large files (>400 lines) | 30+ | `agent/core.py` (1968), `routing/unified.py` (1159) |
| New domain exceptions | 7 | `SunwellModelError`, `SunwellToolError`, etc. |
| CI checks to add | 3 | Passive core, module size, protocol location |

> ⚠️ **Note**: 110 files import from `models/protocol.py`. Migration requires careful backward-compatible re-exports to avoid breaking changes.

---

## 🎯 Goals

| Goal | Benefit |
|------|---------|
| **Centralized protocol definitions** | Single import path for all contracts, better discoverability |
| **Enforced passive core** | No surprise I/O in data models, easier testing |
| **Enhanced error debugging** | AI-friendly investigation commands, faster root cause analysis |
| **Consistent module sizing** | Predictable file organization, easier code review |

---

## 🚫 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Copy Bengal's domain model | Sunwell and Bengal solve different problems |
| Rewrite existing code | Incremental adoption of patterns |
| Break existing public APIs | Backward compatible changes only |

---

## Pattern 1: Centralized Protocols Package

### Current State (Sunwell)

Protocols are scattered across the codebase:

```python
# Protocols defined in various places
from sunwell.models.protocol import ModelProtocol        # models/
from sunwell.tools.types import ToolHandler              # tools/
from sunwell.agent.events import EventEmitter            # agent/
from sunwell.memory.types import MemoryStore             # memory/
```

**Problems**:
- No single place to see all contracts
- Duplicate/conflicting protocol definitions possible
- Hard for new contributors to understand interface boundaries

### Bengal's Approach

Single `bengal/protocols/` package:

```python
# bengal/protocols/__init__.py
"""
Canonical protocol definitions for Bengal.

All protocols should be imported from this module. This ensures a single
source of truth for interface contracts across the codebase.

Organization:
- core: PageLike, SectionLike, SiteLike
- rendering: TemplateRenderer, TemplateEngine, HighlightService
- infrastructure: ProgressReporter, Cacheable, OutputCollector
"""

from bengal.protocols.core import PageLike, SectionLike, SiteLike
from bengal.protocols.rendering import TemplateRenderer, HighlightService
from bengal.protocols.infrastructure import ProgressReporter, Cacheable
```

### Proposed Change

Create `sunwell/protocols/` as the canonical location for all interface contracts:

```
protocols/
├── __init__.py          # Re-exports all protocols
├── models.py            # ModelProtocol, ToolCall, Message
├── tools.py             # ToolHandler, ToolExecutor
├── memory.py            # MemoryStore, PersistentMemory
├── agent.py             # EventEmitter, Renderer
├── planning.py          # Planner, Router
└── capabilities.py      # TypeGuard protocols (HasTools, HasStreaming)
```

```python
# sunwell/protocols/__init__.py
"""
Canonical protocol definitions for Sunwell.

All protocols should be imported from this module. This ensures a single
source of truth for interface contracts across the codebase.

Internal modules may define implementation-specific protocols, but
cross-module contracts belong here.

Thread Safety:
    All protocols are designed for use in multi-threaded contexts.
    Implementations must be thread-safe for concurrent execution.

Example:
    >>> from sunwell.protocols import ModelProtocol, ToolHandler
    >>> 
    >>> def run_with_model(model: ModelProtocol) -> str:
    ...     return model.complete("Hello")
"""

from sunwell.protocols.models import (
    ModelProtocol,
    ToolCall,
    Message,
    StreamingProtocol,
)
from sunwell.protocols.tools import (
    ToolHandler,
    ToolExecutor,
    ToolResult,
)
from sunwell.protocols.memory import (
    MemoryStore,
    PersistentMemoryProtocol,
)
from sunwell.protocols.agent import (
    EventEmitter,
    RendererProtocol,
)
from sunwell.protocols.planning import (
    PlannerProtocol,
    RouterProtocol,
)
from sunwell.protocols.capabilities import (
    HasTools,
    HasStreaming,
    HasThinking,
    has_tools,
    has_streaming,
    has_thinking,
)

__all__ = [
    # Models
    "ModelProtocol",
    "ToolCall",
    "Message",
    "StreamingProtocol",
    # Tools
    "ToolHandler",
    "ToolExecutor",
    "ToolResult",
    # Memory
    "MemoryStore",
    "PersistentMemoryProtocol",
    # Agent
    "EventEmitter",
    "RendererProtocol",
    # Planning
    "PlannerProtocol",
    "RouterProtocol",
    # Capabilities (TypeGuard)
    "HasTools",
    "HasStreaming",
    "HasThinking",
    "has_tools",
    "has_streaming",
    "has_thinking",
]
```

### Migration

1. Create `protocols/` package with new structure
2. Move existing protocol definitions (keep re-exports at old locations)
3. Add deprecation warnings to old import paths
4. Update internal imports over time
5. Remove deprecated paths in future release

---

## Pattern 2: Passive Core Models

### Current State (Sunwell)

`sunwell/core/` mixes passive models with active utilities:

```python
# sunwell/core/__init__.py exports:
# PASSIVE MODELS (good)
from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.persona import Persona
from sunwell.core.spell import Spell, Grimoire

# ACTIVE UTILITIES (shouldn't be here)
from sunwell.core.freethreading import run_parallel, optimal_workers
from sunwell.core.context import AppContext
```

**Problems**:
- Unclear what "core" means
- Testing models requires mocking I/O utilities
- Violates single responsibility

### Bengal's Approach

Explicit constraint in docstring + architecture enforcement:

```python
# bengal/core/__init__.py
"""
Core domain models for Bengal SSG.

This package provides the foundational data models representing
the content structure of a Bengal site. All models are passive
data structures—they do not perform I/O, logging, or side effects.

Architecture:
    Core models are passive data structures with computed properties.
    They do not perform I/O, logging, or side effects. Operations on
    models are handled by orchestrators (see bengal/orchestration/).
"""
```

### Proposed Change

1. **Enforce passive core**: Move utilities out of `core/`

```
# BEFORE
core/
├── lens.py           # Passive ✓
├── persona.py        # Passive ✓
├── spell.py          # Passive ✓
├── freethreading.py  # ACTIVE - move out
├── context.py        # ACTIVE - move out
└── ...

# AFTER
core/
├── __init__.py       # Only passive models
├── lens.py
├── persona.py
├── spell.py
├── types.py
└── ...

runtime/              # New home for active utilities
├── __init__.py
├── freethreading.py  # Moved from core/
├── context.py        # Moved from core/
└── ...
```

2. **Add architecture constraint**:

```python
# sunwell/core/__init__.py
"""
Core domain models for Sunwell.

This package provides foundational data models. All models are passive
data structures—they do not perform I/O, logging, or side effects.

⚠️ ARCHITECTURE CONSTRAINT:
- NO I/O (file reads, network calls)
- NO logging (no logger imports)
- NO side effects (no global state mutation)
- Operations on models are handled by orchestrators

If you need active behavior, use:
- sunwell.runtime/ for execution utilities
- sunwell.orchestration/ for I/O operations
"""
```

3. **Add CI check**:

```python
# scripts/check_passive_core.py
"""Verify core/ modules don't import I/O libraries."""
FORBIDDEN_IN_CORE = {
    "logging",
    "pathlib.Path.read",
    "pathlib.Path.write", 
    "open(",
    "requests",
    "httpx",
    "aiohttp",
}
```

---

## Pattern 3: Enhanced Error System

### Current State (Sunwell)

`sunwell/core/errors.py` provides basic structured errors:

```python
class SunwellError(Exception):
    """Base error type for all Sunwell errors."""
    
    def __init__(self, code: ErrorCode, context: dict, cause: Exception | None):
        self.code = code
        self.context = context
        self.cause = cause
    
    @property
    def message(self) -> str: ...
    @property
    def recovery_hints(self) -> list[str]: ...
    def for_llm(self) -> str: ...
```

**Missing**:
- Investigation commands for debugging
- Error session tracking for recurring patterns
- Lazy loading of heavy error infrastructure
- Error aggregation for batch operations
- Domain-specific exception classes

### Bengal's Approach

Rich error system with multiple layers:

```python
# Bengal error with investigation helpers
try:
    render_page(page)
except BengalError as e:
    # Get debugging commands
    print("Investigation commands:")
    for cmd in e.get_investigation_commands():
        print(f"  {cmd}")
    
    # Get related test files
    print("Related test files:")
    for path in e.get_related_test_files():
        print(f"  {path}")
```

Bengal also has:
- `ErrorSession` for tracking recurring patterns
- `ErrorAggregator` for batch processing
- Lazy loading via `__getattr__` for heavy modules
- Domain-specific exceptions (`BengalRenderingError`, `BengalConfigError`, etc.)

### Proposed Change

#### 3.1: Add Investigation Helpers to SunwellError

```python
class SunwellError(Exception):
    """Base error type for all Sunwell errors."""
    
    # ... existing code ...
    
    def get_investigation_commands(self) -> list[str]:
        """Return shell commands to help debug this error.
        
        AI agents can run these commands to gather more context.
        """
        commands = []
        
        if self.code.category == "model":
            commands.append(f"sunwell models list")
            commands.append(f"sunwell models test {self.context.get('model', '')}")
        
        if self.code.category == "tool":
            tool = self.context.get("tool", "")
            commands.append(f"sunwell tools info {tool}")
            commands.append(f"rg -l '{tool}' src/sunwell/tools/")
        
        if self.code.category == "lens":
            lens = self.context.get("lens", "")
            commands.append(f"sunwell lens show {lens}")
            commands.append(f"sunwell lens validate {lens}")
        
        return commands
    
    def get_related_test_files(self) -> list[str]:
        """Return test files that might help understand this error."""
        patterns = {
            "model": ["tests/unit/models/", "tests/integration/providers/"],
            "tool": ["tests/unit/tools/", "tests/integration/tools/"],
            "lens": ["tests/unit/core/test_lens.py"],
            "validation": ["tests/unit/agent/test_validation.py"],
        }
        return patterns.get(self.code.category, [])
    
    def get_related_docs(self) -> list[str]:
        """Return documentation that might help."""
        return [f"docs/errors/{self.code.name.lower()}.md"]
```

#### 3.2: Add Domain-Specific Exceptions

```python
# sunwell/core/errors.py

class SunwellModelError(SunwellError):
    """Errors related to LLM model operations."""
    pass

class SunwellToolError(SunwellError):
    """Errors related to tool execution."""
    pass

class SunwellLensError(SunwellError):
    """Errors related to lens loading/parsing."""
    pass

class SunwellAgentError(SunwellError):
    """Errors related to agent execution."""
    pass

class SunwellConfigError(SunwellError):
    """Errors related to configuration."""
    pass
```

This enables more specific exception handling:

```python
# BEFORE
try:
    result = agent.run(goal)
except SunwellError as e:
    if e.code.category == "model":
        # handle model error
    elif e.code.category == "tool":
        # handle tool error

# AFTER
try:
    result = agent.run(goal)
except SunwellModelError as e:
    # handle model error
except SunwellToolError as e:
    # handle tool error
except SunwellError as e:
    # handle other errors
```

#### 3.3: Add Lazy Loading for Heavy Error Infrastructure

```python
# sunwell/core/errors.py

# Eagerly loaded - core types needed everywhere
from sunwell.core.errors.codes import ErrorCode
from sunwell.core.errors.exceptions import (
    SunwellError,
    SunwellModelError,
    SunwellToolError,
    # ...
)

# Lazy loaded - heavy modules only when needed
_LAZY_IMPORTS = {
    "ErrorAggregator": ("sunwell.core.errors.aggregation", "ErrorAggregator"),
    "ErrorSession": ("sunwell.core.errors.session", "ErrorSession"),
    "format_error_report": ("sunwell.core.errors.reporter", "format_error_report"),
}

def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module 'sunwell.core.errors' has no attribute {name!r}")
```

#### 3.4: Add Error Session Tracking

```python
# sunwell/core/errors/session.py
"""Track errors across a session to detect recurring patterns."""

from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

@dataclass
class ErrorOccurrence:
    """Single occurrence of an error."""
    error_code: int
    message: str
    timestamp: datetime
    file_path: str | None = None
    context: dict = field(default_factory=dict)

@dataclass
class ErrorPattern:
    """Pattern of recurring errors."""
    error_code: int
    count: int
    first_seen: datetime
    last_seen: datetime
    files: set[str] = field(default_factory=set)

class ErrorSession:
    """Track errors during a build/run session."""
    
    def __init__(self):
        self._occurrences: list[ErrorOccurrence] = []
        self._patterns: dict[int, ErrorPattern] = {}
    
    def record(self, error: SunwellError, file_path: str | None = None) -> dict:
        """Record an error and return pattern info."""
        occurrence = ErrorOccurrence(
            error_code=error.code.value,
            message=error.message,
            timestamp=datetime.now(),
            file_path=file_path,
            context=error.context,
        )
        self._occurrences.append(occurrence)
        
        # Update pattern
        code = error.code.value
        if code in self._patterns:
            pattern = self._patterns[code]
            pattern.count += 1
            pattern.last_seen = occurrence.timestamp
            if file_path:
                pattern.files.add(file_path)
        else:
            self._patterns[code] = ErrorPattern(
                error_code=code,
                count=1,
                first_seen=occurrence.timestamp,
                last_seen=occurrence.timestamp,
                files={file_path} if file_path else set(),
            )
        
        return {
            "is_recurring": self._patterns[code].count > 1,
            "occurrence_count": self._patterns[code].count,
            "affected_files": len(self._patterns[code].files),
        }
    
    def get_summary(self) -> dict:
        """Get summary of all errors in session."""
        return {
            "total_errors": len(self._occurrences),
            "unique_errors": len(self._patterns),
            "most_common": sorted(
                self._patterns.values(),
                key=lambda p: p.count,
                reverse=True,
            )[:5],
        }

# Global session (reset per agent run)
_session: ErrorSession | None = None

def get_session() -> ErrorSession:
    global _session
    if _session is None:
        _session = ErrorSession()
    return _session

def reset_session() -> None:
    global _session
    _session = None

def record_error(error: SunwellError, file_path: str | None = None) -> dict:
    return get_session().record(error, file_path)
```

---

## Pattern 4: Module Size Discipline

### Current State (Sunwell)

Some modules exceed reasonable size:

| File | Lines | Status |
|------|-------|--------|
| `routing/unified.py` | 1160 | ⚠️ Too large |
| `agent/loop.py` | ~800 | ⚠️ Borderline |
| `naaru/workers/harmonic.py` | ~600 | ⚠️ Borderline |

### Bengal's Approach

Explicit organization pattern documented in `core/__init__.py`:

```python
"""
Organization Pattern:
- Simple models (< 400 lines): Single file (e.g., section.py)
- Complex models (> 400 lines): Package (e.g., page/, site/)
"""
```

### Proposed Change

1. **Document the threshold**:

Add to `CONTRIBUTING.md`:

```markdown
## Module Size Guidelines

- **< 400 lines**: Single file (e.g., `lens.py`)
- **> 400 lines**: Split into package with focused submodules

When splitting:
1. Identify cohesive responsibilities
2. Create package directory with `__init__.py`
3. Move related code to focused files
4. Re-export public API from `__init__.py`
```

2. **Split `routing/unified.py`** (1160 lines):

```
# BEFORE
routing/
├── __init__.py
├── briefing_router.py
└── unified.py           # 1160 lines - too large

# AFTER
routing/
├── __init__.py
├── briefing_router.py
└── unified/
    ├── __init__.py      # Re-exports public API
    ├── router.py        # UnifiedRouter class (~400 lines)
    ├── intent.py        # Intent classification (~200 lines)
    ├── confidence.py    # Confidence scoring (~150 lines)
    ├── fallback.py      # Fallback handling (~150 lines)
    └── types.py         # Types and enums (~100 lines)
```

3. **Add CI check**:

```python
# scripts/check_module_size.py
"""Warn about modules exceeding size threshold."""
THRESHOLD = 400

def check_file(path: Path) -> tuple[bool, int]:
    lines = len(path.read_text().splitlines())
    return lines <= THRESHOLD, lines

# Run in CI, warn but don't fail (for now)
```

---

## Implementation Plan

### Phase 1: Protocols Package (Week 1)

1. Create `sunwell/protocols/` structure
2. Move/consolidate existing protocols
3. Add re-exports at old locations with deprecation warnings
4. Update internal imports

### Phase 2: Error System Enhancement (Week 1-2)

1. Add `get_investigation_commands()` and `get_related_test_files()`
2. Create domain-specific exception classes
3. Add lazy loading for heavy error modules
4. Implement `ErrorSession` for pattern tracking
5. Update error handling in agent/tools to use new features

### Phase 3: Passive Core Enforcement (Week 2)

1. Move `freethreading.py` and `context.py` to `runtime/`
2. Add architecture constraint docstring to `core/__init__.py`
3. Create CI check for forbidden imports in `core/`
4. Update imports across codebase

### Phase 4: Module Size Discipline (Week 2-3)

1. Document size guidelines in `CONTRIBUTING.md`
2. Split `routing/unified.py` into package
3. Review other large files, split if needed
4. Add CI warning for oversized modules

---

## Backward Compatibility

All changes maintain backward compatibility:

| Change | Compatibility Strategy |
|--------|----------------------|
| Protocols package | Re-exports at old locations with deprecation warnings |
| Domain exceptions | Inherit from `SunwellError`, old catches still work |
| Error helpers | Additive methods, no breaking changes |
| Core split | Re-exports from `core/` for moved utilities |
| Module splits | Re-exports from original location |

---

## Metrics for Success

| Metric | Current | Target |
|--------|---------|--------|
| Protocol import paths | Scattered | Single `sunwell.protocols` |
| Core I/O imports | Mixed | Zero (enforced by CI) |
| Error debugging time | Manual investigation | Commands provided |
| Files > 400 lines | ~5 | 0 (with CI warning) |
| Error pattern detection | None | Session tracking |

---

## Alternatives Considered

### Alternative 1: Monolithic Error Class

Keep single `SunwellError` class, don't add domain subclasses.

**Pros**: Simpler
**Cons**: Verbose exception handling, category checks everywhere
**Decision**: Rejected — domain classes improve ergonomics significantly

### Alternative 2: Strict 400-Line Enforcement

Fail CI if any file exceeds 400 lines.

**Pros**: Forces compliance
**Cons**: Churn, some files are legitimately complex
**Decision**: Start with warnings, evaluate enforcement later

### Alternative 3: Skip Protocols Package

Keep protocols distributed across modules.

**Pros**: No migration effort
**Cons**: Discoverability remains poor, contracts scattered
**Decision**: Rejected — centralization provides clear benefits

---

## Appendix A: Complete Protocol Inventory

### Protocols to Consolidate into `sunwell/protocols/`

| Current Location | Protocol | Category | Used By |
|-----------------|----------|----------|---------|
| `types/protocol.py` | `Serializable` | serialization | routing, project, providers, interface |
| `types/protocol.py` | `DictSerializable` | serialization | lens/identity, environment/model |
| `types/protocol.py` | `ConsoleProtocol` | infrastructure | CLI, testing |
| `types/protocol.py` | `ChatSessionProtocol` | agent | chat, testing |
| `types/protocol.py` | `MemoryStoreProtocol` | memory | simulacrum, memory |
| `types/protocol.py` | `ToolExecutorProtocol` | tools | agent, testing |
| `types/protocol.py` | `ParallelExecutorProtocol` | infrastructure | runtime, testing |
| `types/protocol.py` | `WorkerProtocol` | naaru | naaru/workers/* |
| `models/protocol.py` | `ModelProtocol` | models | agent, chat, providers |
| `agent/event_schema.py` | `EventEmitter` | agent | agent, CLI |
| `agent/renderer.py` | `Renderer` | agent | CLI, Studio |
| `routing/__init__.py` | `HasStats` | infrastructure | routing, benchmark |
| `models/capability/schema.py` | `SchemaAdapter` | models | providers |
| `workflow/types.py` | `Serializable` | **DUPLICATE** | workflow |
| `workflow/engine.py` | `SkillExecutor` | planning | skills, agent |
| `tools/web_search.py` | `WebSearchProvider` | tools | web_search |
| `team/types.py` | `Serializable` | **DUPLICATE** | team |
| `team/types.py` | `Embeddable` | memory | team, embedding |
| `runtime/types.py` | `Saveable` | infrastructure | runtime |
| `memory/types.py` | `Promptable` | memory | memory, agent |
| `interface/router.py` | `InterfaceOutput` | interface | interface |
| `simulacrum/hierarchical/summarizer.py` | `SummarizerProtocol` | memory | simulacrum |
| `guardrails/escalation.py` | `UIProtocol` | interface | guardrails, CLI |
| `fount/client.py` | `FountProtocol` | features | fount |
| `external/types.py` | `EventCallback` | features | external |

### Proposed `protocols/` Structure

```
sunwell/protocols/
├── __init__.py              # Re-exports all protocols
├── serialization.py         # Serializable, DictSerializable (DEDUPE 3 copies)
├── models.py                # ModelProtocol, StreamingProtocol
├── tools.py                 # ToolExecutorProtocol, WebSearchProvider
├── memory.py                # MemoryStoreProtocol, Promptable, Embeddable
├── agent.py                 # EventEmitter, Renderer, ChatSessionProtocol
├── planning.py              # SkillExecutor, WorkerProtocol
├── infrastructure.py        # ConsoleProtocol, ParallelExecutorProtocol, HasStats, Saveable
├── interface.py             # InterfaceOutput, UIProtocol
└── capabilities.py          # TypeGuard protocols (HasTools, etc.)
```

### Protocol Deduplication Required

⚠️ **`Serializable` is defined 3 times**:
1. `types/protocol.py:20` — canonical
2. `workflow/types.py:9` — duplicate
3. `team/types.py:36` — duplicate

**Action**: Delete duplicates, import from `sunwell/protocols/serialization.py`

### High-Traffic Types (110 importers)

The following types from `models/protocol.py` are imported by **110 files**:

| Type | Category | Keep In | Reason |
|------|----------|---------|--------|
| `ModelProtocol` | Protocol | `protocols/models.py` | Interface contract |
| `Tool` | Data class | `models/types.py` | Tightly coupled to model layer |
| `ToolCall` | Data class | `models/types.py` | Tightly coupled to model layer |
| `Message` | Data class | `models/types.py` | Tightly coupled to model layer |
| `GenerateResult` | Data class | `models/types.py` | Tightly coupled to model layer |
| `GenerateOptions` | Data class | `models/types.py` | Tightly coupled to model layer |
| `TokenUsage` | Data class | `models/types.py` | Tightly coupled to model layer |

**Decision**: Split `models/protocol.py` into:
- `models/types.py` — Data classes (Tool, ToolCall, Message, etc.)
- `protocols/models.py` — Protocol only (ModelProtocol)

**Migration Strategy**:
```python
# models/protocol.py (becomes re-export shim)
"""DEPRECATED: Import from sunwell.models.types or sunwell.protocols.models."""
import warnings
warnings.warn(
    "sunwell.models.protocol is deprecated. "
    "Import types from sunwell.models.types, "
    "protocols from sunwell.protocols.models",
    DeprecationWarning,
    stacklevel=2
)
from sunwell.models.types import Tool, ToolCall, Message, GenerateResult, GenerateOptions, TokenUsage
from sunwell.protocols.models import ModelProtocol
```

This allows gradual migration of 110 files without breaking changes.

---

## Appendix B: Core Module Active Utilities (Move to `runtime/`)

### Current `core/` Exports That Violate Passive Core

| Export | File | Reason to Move |
|--------|------|----------------|
| `AppContext` | `core/context.py` | Contains runtime state |
| `is_free_threaded` | `core/freethreading.py` | Runtime detection |
| `optimal_workers` | `core/freethreading.py` | Runtime calculation |
| `WorkloadType` | `core/freethreading.py` | Execution enum |
| `run_parallel` | `core/freethreading.py` | I/O operation |
| `run_parallel_async` | `core/freethreading.py` | I/O operation |
| `run_cpu_bound` | `core/freethreading.py` | I/O operation |
| `runtime_info` | `core/freethreading.py` | System inspection |

### Files Importing from `core.freethreading` (Require Update)

| File | Line | Import |
|------|------|--------|
| `simulacrum/core/store.py` | 1133 | `WorkloadType, optimal_workers, run_parallel` |
| `workspace/indexer.py` | 22 | `WorkloadType, optimal_workers, run_parallel` |
| `runtime/parallel.py` | 30 | `is_free_threaded, optimal_workers, run_parallel` |
| `cli/helpers.py` | 11 | `is_free_threaded` |
| `cli/runtime_cmd.py` | 9 | `runtime_info` |
| `core/__init__.py` | 5 | Re-export (update to new location) |

### Migration Script

```python
# scripts/migrate_core_freethreading.py
"""Migrate core/freethreading imports to runtime/freethreading."""

REPLACEMENTS = [
    ("from sunwell.core.freethreading import", "from sunwell.runtime.freethreading import"),
    ("from sunwell.core import AppContext", "from sunwell.runtime import AppContext"),
]

FILES_TO_UPDATE = [
    "src/sunwell/simulacrum/core/store.py",
    "src/sunwell/workspace/indexer.py",
    "src/sunwell/runtime/parallel.py",
    "src/sunwell/cli/helpers.py",
    "src/sunwell/cli/runtime_cmd.py",
]
```

---

## Appendix C: Error System Wiring

### Files Using `SunwellError` (Require Domain Exception Update)

| File | Usage Pattern | Suggested Exception |
|------|---------------|---------------------|
| `cli/chat.py` | Model errors | `SunwellModelError` |
| `cli/chat/command.py` | Model errors | `SunwellModelError` |
| `schema/loader.py` | Config errors | `SunwellConfigError` |
| `runtime/model_router.py` | Model errors | `SunwellModelError` |
| `fount/client.py` | Network errors | `SunwellNetworkError` |
| `embedding/ollama.py` | Model errors | `SunwellModelError` |
| `models/ollama.py` | Model errors | `SunwellModelError` |
| `models/openai.py` | Model errors | `SunwellModelError` |
| `models/anthropic.py` | Model errors | `SunwellModelError` |
| `cli/main.py` | Generic handler | Keep `SunwellError` |
| `cli/error_handler.py` | Generic handler | Keep `SunwellError` |
| `cli/lens.py` | Lens errors | `SunwellLensError` |
| `core/types.py` | Type definitions | N/A |
| `types/core.py` | Type definitions | N/A |

### Domain Exception Hierarchy

```python
# sunwell/core/errors/exceptions.py

class SunwellError(Exception):
    """Base class for all Sunwell errors."""
    # ... existing implementation ...

class SunwellModelError(SunwellError):
    """Errors from LLM model operations."""
    pass

class SunwellToolError(SunwellError):
    """Errors from tool execution."""
    pass

class SunwellLensError(SunwellError):
    """Errors from lens loading/parsing."""
    pass

class SunwellAgentError(SunwellError):
    """Errors from agent execution."""
    pass

class SunwellConfigError(SunwellError):
    """Errors from configuration loading."""
    pass

class SunwellNetworkError(SunwellError):
    """Errors from network operations."""
    pass

class SunwellValidationError(SunwellError):
    """Errors from validation gates."""
    pass
```

### Error Handler Update (`cli/error_handler.py`)

```python
# Add domain-specific handling
def _print_human_error(error: SunwellError) -> None:
    # Existing code...
    
    # NEW: Add investigation commands for AI debugging
    if hasattr(error, 'get_investigation_commands'):
        commands = error.get_investigation_commands()
        if commands:
            console.print("\n[bold]Investigation commands:[/]")
            for cmd in commands:
                console.print(f"  $ {cmd}", style="dim")
```

---

## Appendix D: Large File Split Plan

### Files Exceeding 400-Line Threshold

| File | Lines | Priority | Split Strategy |
|------|-------|----------|----------------|
| `agent/core.py` | 1968 | HIGH | Package: `agent/core/` |
| `simulacrum/core/store.py` | 1903 | HIGH | Package: `simulacrum/core/store/` |
| `naaru/planners/harmonic.py` | 1665 | MEDIUM | Package: `naaru/planners/harmonic/` |
| `agent/loop.py` | 1549 | HIGH | Package: `agent/loop/` |
| `cli/chat.py` | 1323 | MEDIUM | Package: `cli/chat/` (partial exists) |
| `reasoning/reasoner.py` | 1321 | MEDIUM | Package: `reasoning/` |
| `agent/event_schema.py` | 1284 | LOW | Keep (generated/schema) |
| `benchmark/runner.py` | 1246 | LOW | Package if needed |
| `naaru/planners/artifact.py` | 1224 | MEDIUM | Package: `naaru/planners/artifact/` |
| `routing/unified.py` | 1159 | HIGH | Package: `routing/unified/` |
| `agent/learning.py` | 1129 | MEDIUM | Package: `agent/learning/` |

### `routing/unified.py` Split (Example)

```
# BEFORE
routing/
├── __init__.py
├── briefing_router.py
└── unified.py           # 1159 lines

# AFTER
routing/
├── __init__.py
├── briefing_router.py
└── unified/
    ├── __init__.py      # Re-exports: UnifiedRouter, route_goal
    ├── router.py        # UnifiedRouter class (~400 lines)
    ├── intent.py        # IntentClassifier, classify_intent (~200 lines)
    ├── confidence.py    # ConfidenceScorer (~150 lines)
    ├── fallback.py      # FallbackHandler (~150 lines)
    ├── metrics.py       # RoutingMetrics, stats collection (~100 lines)
    └── types.py         # RoutingResult, IntentSignal, etc. (~100 lines)
```

### `agent/core.py` Split (Example)

```
# BEFORE
agent/
├── __init__.py
├── core.py              # 1968 lines
└── ...

# AFTER
agent/
├── __init__.py
├── core/
│   ├── __init__.py      # Re-exports: Agent, TaskGraph
│   ├── agent.py         # Agent class (~600 lines)
│   ├── task_graph.py    # TaskGraph class (~400 lines)
│   ├── execution.py     # Task execution logic (~400 lines)
│   ├── planning.py      # Plan generation (~300 lines)
│   └── types.py         # AgentState, TaskResult (~200 lines)
└── ...
```

---

## Appendix E: CI Checks to Add

### 1. Passive Core Checker

```python
# scripts/ci/check_passive_core.py
"""Verify core/ modules don't import I/O libraries."""

FORBIDDEN_IMPORTS = {
    "logging",
    "pathlib.Path.read_text",
    "pathlib.Path.write_text",
    "pathlib.Path.read_bytes",
    "pathlib.Path.write_bytes",
    "open",
    "requests",
    "httpx",
    "aiohttp",
    "aiofiles",
    "subprocess",
    "os.system",
    "shutil",
}

ALLOWED_CORE_FILES = {
    "core/__init__.py",
    "core/errors.py",
    "core/types.py",
    "core/lens.py",
    "core/persona.py",
    "core/spell.py",
    "core/heuristic.py",
    "core/identity.py",
    "core/validator.py",
    "core/workflow.py",
    "core/framework.py",
}

# Check via AST or grep patterns
```

### 2. Module Size Checker

```python
# scripts/ci/check_module_size.py
"""Warn about modules exceeding size threshold."""

THRESHOLD = 400
EXEMPTIONS = {
    "agent/event_schema.py",  # Generated schema
}

def check_file(path: Path) -> tuple[bool, int]:
    if path.name in EXEMPTIONS:
        return True, 0
    lines = len(path.read_text().splitlines())
    return lines <= THRESHOLD, lines

# Output warnings (not failures) for now
```

### 3. Protocol Location Checker

```python
# scripts/ci/check_protocol_locations.py
"""Ensure cross-module protocols are in sunwell/protocols/."""

def find_protocol_definitions(path: Path) -> list[tuple[str, int]]:
    """Find 'class Foo(Protocol)' definitions."""
    ...

# Flag protocols NOT in sunwell/protocols/ that are imported
# from more than one module
```

---

## Appendix F: Implementation Checklist (Detailed)

### Phase 1: Protocols Package (5 tasks)

- [ ] Create `sunwell/protocols/__init__.py` with structure
- [ ] Move `types/protocol.py` contents to `protocols/`
- [ ] Move `models/protocol.py` protocols to `protocols/models.py`
- [ ] Delete duplicate `Serializable` from `workflow/types.py` and `team/types.py`
- [ ] Add deprecation warnings to old import locations

### Phase 2: Error Enhancement (8 tasks)

- [ ] Add `get_investigation_commands()` to `SunwellError`
- [ ] Add `get_related_test_files()` to `SunwellError`
- [ ] Add `get_related_docs()` to `SunwellError`
- [ ] Create domain exception classes in `core/errors/exceptions.py`
- [ ] Add lazy loading via `__getattr__` in `core/errors/__init__.py`
- [ ] Create `core/errors/session.py` for `ErrorSession`
- [ ] Update `cli/error_handler.py` to show investigation commands
- [ ] Update model providers to raise `SunwellModelError`

### Phase 3: Passive Core (6 tasks)

- [ ] Create `sunwell/runtime/freethreading.py` (copy from core)
- [ ] Create `sunwell/runtime/context.py` (copy from core)
- [ ] Add re-exports in `core/__init__.py` with deprecation warnings
- [ ] Update 5 files importing from `core.freethreading`
- [ ] Add docstring constraint to `core/__init__.py`
- [ ] Add CI check `scripts/ci/check_passive_core.py`

### Phase 4: Module Size Discipline (7 tasks)

- [ ] Document 400-line threshold in `CONTRIBUTING.md`
- [ ] Split `routing/unified.py` into package (1159 → 5 files)
- [ ] Split `agent/core.py` into package (1968 → 5 files)
- [ ] Split `agent/loop.py` into package (1549 → 4 files)
- [ ] Split `simulacrum/core/store.py` into package (1903 → 5 files)
- [ ] Add CI check `scripts/ci/check_module_size.py`
- [ ] Review remaining large files, prioritize splits

---

## Appendix G: Import Path Migration Guide

### Old → New Import Paths

| Old Path | New Path | Files Affected |
|----------|----------|----------------|
| `sunwell.models.protocol.ModelProtocol` | `sunwell.protocols.models.ModelProtocol` | 110 |
| `sunwell.models.protocol.Tool` | `sunwell.models.types.Tool` | 110 |
| `sunwell.models.protocol.ToolCall` | `sunwell.models.types.ToolCall` | 110 |
| `sunwell.models.protocol.Message` | `sunwell.models.types.Message` | 110 |
| `sunwell.types.protocol.ToolExecutorProtocol` | `sunwell.protocols.tools.ToolExecutorProtocol` | ~20 |
| `sunwell.types.protocol.MemoryStoreProtocol` | `sunwell.protocols.memory.MemoryStoreProtocol` | ~10 |
| `sunwell.types.protocol.ConsoleProtocol` | `sunwell.protocols.infrastructure.ConsoleProtocol` | ~5 |
| `sunwell.core.freethreading.*` | `sunwell.runtime.freethreading.*` | 5 |
| `sunwell.core.context.AppContext` | `sunwell.runtime.context.AppContext` | 1 (re-export) |
| `sunwell.workflow.types.Serializable` | `sunwell.protocols.serialization.Serializable` | ~5 |
| `sunwell.team.types.Serializable` | `sunwell.protocols.serialization.Serializable` | ~3 |
| `sunwell.core.errors.SunwellError` | Keep (add subclasses) | 15 |

### Backward Compatibility Shims

All old import paths will continue working with deprecation warnings:

```python
# sunwell/models/protocol.py (after migration)
"""DEPRECATED: Use sunwell.models.types and sunwell.protocols.models."""
import warnings
warnings.warn("...", DeprecationWarning, stacklevel=2)

# Re-export for backward compatibility
from sunwell.models.types import (
    Tool, ToolCall, Message, GenerateResult, 
    GenerateOptions, TokenUsage, sanitize_llm_content
)
from sunwell.protocols.models import ModelProtocol

__all__ = ["ModelProtocol", "Tool", "ToolCall", "Message", ...]
```

### Test Files Requiring Update

| Test File | Reason |
|-----------|--------|
| `tests/unit/models/test_protocol.py` | Protocol moved |
| `tests/unit/agent/test_*.py` | May import protocols |
| `tests/unit/tools/test_executor.py` | ToolExecutorProtocol moved |
| `tests/integration/test_*.py` | May import various protocols |

**Migration validation**: Run full test suite after each phase to catch import issues.

---

## Appendix H: Rollout Timeline

### Phase 1: Foundation (Week 1)
| Day | Task |
|-----|------|
| 1-2 | Create `protocols/` package, move protocol definitions |
| 3 | Add deprecation shims at old locations |
| 4 | Run full test suite, fix any issues |
| 5 | Merge PR for protocols package |

### Phase 2: Error System (Week 2)
| Day | Task |
|-----|------|
| 1 | Add investigation helpers to `SunwellError` |
| 2 | Create domain exception classes |
| 3 | Add lazy loading, `ErrorSession` |
| 4 | Update `cli/error_handler.py` |
| 5 | Update provider error handling, merge PR |

### Phase 3: Passive Core (Week 3)
| Day | Task |
|-----|------|
| 1 | Create `runtime/freethreading.py`, `runtime/context.py` |
| 2 | Add deprecation shims in `core/` |
| 3 | Update 5 importing files |
| 4 | Add CI check for passive core |
| 5 | Merge PR |

### Phase 4: Module Splitting (Week 3-4)
| Day | Task |
|-----|------|
| 1-2 | Split `routing/unified.py` |
| 3-4 | Split `agent/core.py` |
| 5-6 | Split `agent/loop.py` |
| 7 | Add CI check for module size |
| 8 | Merge PR |

### Phase 5: Cleanup (Week 5+)
- Remove deprecation shims (after 2 release cycles)
- Delete old files
- Update documentation

---

## References

- RFC-138: Module Architecture Consolidation
- Bengal codebase: `bengal/protocols/`, `bengal/core/`, `bengal/errors/`
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- [Lazy Module Loading](https://docs.python.org/3/library/importlib.html#module-importlib)
