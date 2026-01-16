# RFC-025: Architectural Refactor - Scaling Beyond Prototype

| Field | Value |
|-------|-------|
| **RFC** | 025 |
| **Title** | Architectural Refactor - Consolidation, Modularity, and Testability |
| **Status** | Draft |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-010 through RFC-024 (All existing) |
| **Affects** | `cli.py`, `simulacrum/`, `naaru/`, `config.py`, `runtime/` |

---

## Abstract

Sunwell has grown from 0 to 42K lines through rapid RFC-driven prototyping. The vision is clear: **RAG for Judgment** with the Naaru coordinated intelligence architecture. However, the codebase has accumulated architectural debt that will impede the next phase of development.

This RFC proposes a **three-phase refactor** to:
1. **Consolidate** duplicate types and eliminate code smell
2. **Modularize** the 3,852-line CLI monolith
3. **Establish protocols** for major subsystems to enable testing and extension

```
Current State:                          Target State:
┌─────────────────────────────┐        ┌─────────────────────────────┐
│         cli.py              │        │         cli/                │
│    (3,852 lines, 47 funcs)  │        │  ├── __init__.py (main)     │
│    - chat loop              │        │  ├── chat.py (500 lines)    │
│    - apply commands         │   ──▶  │  ├── apply.py (400 lines)   │
│    - binding management     │        │  ├── bind.py (300 lines)    │
│    - skill commands         │        │  ├── session.py (200 lines) │
│    - session management     │        │  └── helpers.py (shared)    │
└─────────────────────────────┘        └─────────────────────────────┘

        6 duplicate classes            Single source of truth in types/
        235 dataclasses scattered      Organized by domain
        No protocol layer              Clear protocols for extension
```

---

## Motivation

### The Prototype Tax

Rapid prototyping served us well—RFC-019 through RFC-024 shipped in days, not weeks. But that velocity created technical debt:

| Smell | Count | Impact |
|-------|-------|--------|
| God file (`cli.py`) | 3,852 lines | Untestable, hard to modify |
| Duplicate classes | 6 pairs | Confusion, divergent behavior |
| Functions >100 lines | 12 | Hard to test, hard to reason about |
| Overlapping modules | 4 areas | Unclear responsibilities |
| Global singletons | 2 | Testing friction, no multi-tenancy |

### Why Now?

Three signals indicate it's time:

1. **Feature velocity is slowing**: Adding to `cli.py` requires understanding 3,800 lines of context
2. **Testing is painful**: The chat loop can't be unit tested without mocking everything
3. **Reuse is blocked**: `_chat_loop` logic can't be used in a library context

### Non-Goals

This RFC does **not** propose:
- Rewriting from scratch (incremental migration only)
- Changing public APIs (backward compatible)
- Adding new features (pure refactor)
- Changing the thematic naming (Naaru, Convergence, etc. stay)

---

## Analysis

### Code Smell Inventory

#### 1. The `cli.py` Monolith

```
File: src/sunwell/cli.py
Lines: 3,852
Functions: 47
Largest function: _apply_async (504 lines)

Responsibilities (too many):
├── CLI argument parsing (Click)
├── Chat session management
├── Tool execution loop
├── Identity injection
├── Naaru shard coordination
├── Model creation/switching
├── Binding CRUD operations
├── Skill import/export
├── Session persistence
└── Rich console formatting
```

**Problem**: Single file has 10+ responsibilities. Testing any one requires loading all.

#### 2. Duplicate Type Definitions

| Class Name | Location 1 | Location 2 | Divergence Risk |
|------------|------------|------------|-----------------|
| `NaaruConfig` | `config.py:118` | `naaru/naaru.py:91` | High - config vs runtime |
| `ContextBudget` | `simulacrum/context.py` | `simulacrum/unified_context.py` | Medium |
| `RetrievalResult` | `simulacrum/parallel.py` | `runtime/retriever.py` | High |
| `ModelRouter` | `runtime/model_router.py` | `mirror/router.py` | High |
| `MockModel` | `naaru/resonance.py` | `models/mock.py` | Low |
| `Tier` | `core/types.py` | `routing/tiered_attunement.py` | Medium |

**Problem**: When updating `NaaruConfig`, which one is canonical? Import errors when the wrong one is used.

#### 3. Simulacrum Module Explosion

```
simulacrum/           # 28 files, ~7,000 lines total
├── RFC-013 additions (hierarchical memory)
│   ├── chunks.py
│   ├── chunk_manager.py
│   ├── ctf.py
│   └── summarizer.py
├── RFC-014 additions (multi-topology)
│   ├── spatial.py, spatial_extractor.py
│   ├── topology.py, topology_extractor.py
│   ├── structural.py, structural_chunker.py
│   └── facets.py, facet_extractor.py
├── Unified layer (attempted consolidation)
│   ├── unified_store.py
│   └── unified_context.py
└── Original core
    ├── store.py (785 lines)
    ├── manager.py (1,848 lines)
    ├── context.py
    └── dag.py
```

**Problem**: Three generations of memory architecture coexist. `manager.py` alone is 1,848 lines.

#### 4. Parallel Execution Fragmentation

Four separate parallel execution implementations:

| Location | Purpose | Pattern |
|----------|---------|---------|
| `core/freethreading.py` | GIL-free parallelism | `run_parallel()`, `run_parallel_async()` |
| `naaru/parallel.py` | Autonomous runner pool | `ParallelAutonomousRunner` |
| `simulacrum/parallel.py` | Memory retrieval | `ParallelRetriever` |
| `runtime/parallel.py` | Unknown (to audit) | TBD |

**Problem**: No shared abstraction. Each reinvents worker pools, error handling, progress tracking.

---

## Proposed Architecture

### Phase 1: Type Consolidation (Week 1)

#### 1.1 Create `sunwell/types/` Package

```
src/sunwell/types/
├── __init__.py          # Re-exports everything
├── core.py              # Severity, Tier, Confidence, etc.
├── config.py            # All *Config dataclasses
├── memory.py            # ContextBudget, RetrievalResult, etc.
├── routing.py           # Intent, RouteDecision, etc.
└── protocol.py          # All Protocol definitions (moved from scattered locations)
```

**Migration**: 
1. Move canonical definitions to `types/`
2. Add deprecation warnings to old locations
3. Update imports across codebase

#### 1.2 Consolidate Config Classes

```python
# BEFORE: Two NaaruConfig classes

# config.py:118
@dataclass
class NaaruConfig:
    voice: str = "gemma3:1b"
    voice_temperature: float = 0.3
    # ... 15 fields

# naaru/naaru.py:91
@dataclass
class NaaruConfig:
    harmonic_synthesis: bool = True
    convergence: int = 7
    # ... 12 fields (different!)

# AFTER: Single source in types/config.py

@dataclass
class NaaruConfig:
    """Configuration for the Naaru coordinated intelligence architecture.
    
    This is the single source of truth. Used by:
    - config.py for YAML/env loading
    - naaru/naaru.py for runtime defaults
    """
    # Voice (synthesis model)
    voice: str = "gemma3:1b"
    voice_temperature: float = 0.3
    
    # Wisdom (judge model)  
    wisdom: str = "gemma3:4b"
    purity_threshold: float = 6.0
    
    # Naaru features
    harmonic_synthesis: bool = True
    resonance: int = 2
    convergence: int = 7
    discernment: bool = True
    attunement: bool = True
    
    # Shards
    num_analysis_shards: int = 2
    num_synthesis_shards: int = 2
```

### Phase 2: CLI Modularization (Week 2)

#### 2.1 New CLI Structure

```
src/sunwell/cli/
├── __init__.py          # Main Click group, version, quiet handling
├── chat.py              # chat command + _chat_loop
├── apply.py             # apply command + _apply_async
├── bind.py              # bind group (create, list, show, delete, default)
├── session.py           # sessions group (list, stats, archive)
├── skill.py             # skill commands (exec, export, import, validate)
├── lens.py              # lens commands (list, validate, inspect, install, publish)
├── config_cmd.py        # config command
├── ask.py               # ask command + _ask_with_binding
├── helpers.py           # _create_model, _format_args, _display_execution_stats
└── state.py             # ChatState, global managers
```

#### 2.2 Function Decomposition

The 504-line `_apply_async` becomes:

```python
# apply.py

async def _apply_async(
    lens: Lens,
    input_text: str,
    model: ModelProtocol,
    ...
) -> ExecutionResult:
    """Orchestrate lens application."""
    
    # Step 1: Retrieve expertise (100 lines → helpers)
    expertise = await _retrieve_expertise(lens, input_text, model)
    
    # Step 2: Build context (50 lines → helpers)
    context = _build_application_context(lens, expertise, input_text)
    
    # Step 3: Execute with tools if enabled (150 lines → tools.py)
    if tools_enabled:
        return await _execute_with_tools(model, context, tool_executor)
    
    # Step 4: Simple generation (50 lines)
    return await _execute_simple(model, context)
    
    # Step 5: Post-process and validate (50 lines → helpers)
    return _post_process_result(result, lens)
```

#### 2.3 Testability Pattern

```python
# Before: Untestable because of Click decorators and console I/O
@click.command()
@click.option("--model", ...)
def chat(model: str, ...):
    console.print(...)  # Side effect
    asyncio.run(_chat_loop(...))  # Async + global state

# After: Separates CLI interface from core logic
@click.command()
@click.option("--model", ...)
def chat(model: str, ...):
    """CLI wrapper - thin layer over ChatSession."""
    config = ChatConfig(model=model, ...)
    session = ChatSession(config)
    asyncio.run(session.run(console=Console()))

class ChatSession:
    """Core chat logic - no Click, no globals, fully testable."""
    
    def __init__(self, config: ChatConfig):
        self.config = config
        self.state = ChatState()
    
    async def run(self, console: ConsoleProtocol | None = None):
        """Run chat loop. Console optional for testing."""
        ...
    
    async def process_message(self, message: str) -> str:
        """Process single message. Easy to test."""
        ...
```

### Phase 3: Protocol Layer (Week 3)

#### 3.1 Core Protocols

```python
# types/protocol.py

from typing import Protocol, AsyncIterator

class ConsoleProtocol(Protocol):
    """Abstract console for testing."""
    def print(self, message: str) -> None: ...
    def input(self, prompt: str) -> str: ...

class ChatSessionProtocol(Protocol):
    """Abstract chat session."""
    async def process_message(self, message: str) -> str: ...
    async def handle_command(self, command: str) -> str | None: ...

class MemoryStoreProtocol(Protocol):
    """Unified memory store interface."""
    async def store(self, key: str, value: Any) -> None: ...
    async def retrieve(self, query: str, limit: int = 10) -> list[Any]: ...
    async def search(self, embedding: list[float], limit: int = 10) -> list[Any]: ...

class ToolExecutorProtocol(Protocol):
    """Abstract tool execution."""
    async def execute(self, tool: str, args: dict) -> ToolResult: ...
    def available_tools(self) -> list[Tool]: ...

class ParallelExecutorProtocol(Protocol):
    """Unified parallel execution."""
    async def map(self, fn: Callable, items: list[T]) -> list[R]: ...
    async def gather(self, *coros: Coroutine) -> list[Any]: ...
```

#### 3.2 Dependency Injection Pattern

```python
# Before: Global singleton, hard to test
_simulacrum_manager = None

def _get_simulacrum_manager():
    global _simulacrum_manager
    if _simulacrum_manager is None:
        _simulacrum_manager = SimulacrumManager(...)
    return _simulacrum_manager

# After: Injected dependency, easy to test
@dataclass
class AppContext:
    """Application context with all dependencies."""
    config: SunwellConfig
    memory: MemoryStoreProtocol
    embedder: EmbeddingProtocol
    console: ConsoleProtocol = field(default_factory=Console)
    
    @classmethod
    def from_config(cls, config: SunwellConfig) -> "AppContext":
        """Factory for production use."""
        return cls(
            config=config,
            memory=SimulacrumManager.from_config(config),
            embedder=create_embedder(config),
        )
    
    @classmethod
    def for_testing(cls) -> "AppContext":
        """Factory for test use."""
        return cls(
            config=SunwellConfig(),
            memory=InMemoryStore(),
            embedder=HashEmbedder(),
            console=NullConsole(),
        )
```

### Phase 4: Simulacrum Reorganization (Week 4)

#### 4.1 Subpackage Structure

```
src/sunwell/simulacrum/
├── __init__.py              # Public API (unchanged for compatibility)
├── core/                    # Core abstractions
│   ├── __init__.py
│   ├── store.py            # SimulacrumStore
│   ├── dag.py              # ConversationDAG
│   ├── turn.py             # Turn, Learning
│   └── memory.py           # MemoryType, base classes
├── hierarchical/            # RFC-013
│   ├── __init__.py
│   ├── chunks.py
│   ├── chunk_manager.py
│   ├── ctf.py
│   └── summarizer.py
├── topology/                # RFC-014 multi-topology
│   ├── __init__.py
│   ├── spatial.py
│   ├── structural.py
│   ├── concept_graph.py
│   └── facets.py
├── extractors/              # All extractors
│   ├── __init__.py
│   ├── spatial.py
│   ├── topology.py
│   ├── structural.py
│   └── facet.py
├── context/                 # Context assembly
│   ├── __init__.py
│   ├── assembler.py        # ContextAssembler (unified)
│   ├── budget.py           # ContextBudget (single source)
│   └── focus.py            # Focus, FocusFilter
├── manager/                 # Multi-simulacrum
│   ├── __init__.py
│   ├── manager.py          # SimulacrumManager (slimmed)
│   ├── policy.py           # SpawnPolicy, LifecyclePolicy
│   ├── metadata.py         # SimulacrumMetadata
│   └── tools.py            # SimulacrumToolHandler
└── parallel/                # Parallel retrieval
    ├── __init__.py
    └── retriever.py
```

#### 4.2 Slim Down `manager.py`

Current 1,848 lines → Target 500 lines by extracting:

| Extract To | Lines | Content |
|------------|-------|---------|
| `policy.py` | 200 | SpawnPolicy, LifecyclePolicy, policy logic |
| `metadata.py` | 150 | SimulacrumMetadata, PendingDomain, ArchiveMetadata |
| `tools.py` | 300 | SimulacrumToolHandler, SIMULACRUM_TOOLS |
| `manager.py` | 500 | Core orchestration only |

---

## Migration Strategy

### Principle: No Big Bang

Every change must be:
1. **Incremental**: One PR per logical change
2. **Clean refactor only**: No shims, wrappers, or deprecated aliases
3. **Tested**: No merge without test coverage
4. **Reviewable**: PRs under 500 lines when possible

### Migration Order

```
Week 1: Type Consolidation
├── Day 1-2: Create types/ package, move protocols
├── Day 3-4: Consolidate config classes
├── Day 5: Consolidate remaining duplicates
└── Day 6-7: Update imports everywhere, delete old definitions

Week 2: CLI Modularization  
├── Day 1-2: Create cli/ package structure
├── Day 3-4: Extract bind.py, session.py (easiest)
├── Day 5-6: Extract apply.py, skill.py
└── Day 7: Extract chat.py (hardest, most dependencies)

Week 3: Protocol Layer
├── Day 1-2: Define protocols in types/protocol.py
├── Day 3-4: Create AppContext with DI
├── Day 5-6: Migrate CLI to use AppContext
└── Day 7: Add test helpers using protocols

Week 4: Simulacrum Reorganization
├── Day 1-2: Create subpackage structure
├── Day 3-4: Move files into subpackages
├── Day 5-6: Slim down manager.py
└── Day 7: Update __init__.py exports, verify compatibility
```

### No Shim Policy

Refactors are clean moves only:
- Move the canonical definition once.
- Update all imports in the same PR.
- Delete the old definition (no aliases, no wrappers, no deprecation warnings).

---

## Success Criteria

### Quantitative

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Max file size | 3,852 lines | <600 lines | `wc -l` |
| Max function size | 504 lines | <100 lines | AST analysis |
| Duplicate classes | 6 pairs | 0 | grep |
| Test coverage | ~30% | >70% | pytest-cov |
| Import time | ~2s | <0.5s | `time python -c "import sunwell"` |

### Qualitative

- [ ] New developer can understand a module in <10 minutes
- [ ] Any CLI command can be tested without mocking console
- [ ] Adding a new command requires touching only 1-2 files
- [ ] Protocol allows swapping implementations (e.g., different memory backends)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing scripts | Medium | High | Deprecation warnings, not removal |
| Scope creep into features | High | Medium | Strict "refactor only" rule |
| Test coverage gaps | Medium | Medium | Write tests for each extracted module |
| Import cycle introduction | Low | High | CI check for circular imports |

---

## Appendix: Code Smell Evidence

### A. Large Functions (Top 10)

```
504 lines: cli.py::_apply_async
361 lines: cli.py::_chat_loop
224 lines: cli.py::_handle_chat_command
196 lines: cli.py::chat
193 lines: cli.py::_ask_with_binding
193 lines: tools/executor.py::execute
150 lines: runtime/engine.py::execute
143 lines: naaru/naaru.py::harmonize
133 lines: config.py::save_default_config
129 lines: cli.py::setup
```

### B. Duplicate Class Locations

```
NaaruConfig:
  - config.py:118
  - naaru/naaru.py:91

ContextBudget:
  - simulacrum/context.py
  - simulacrum/unified_context.py

RetrievalResult:
  - simulacrum/parallel.py
  - runtime/retriever.py

ModelRouter:
  - runtime/model_router.py
  - mirror/router.py

MockModel:
  - naaru/resonance.py
  - models/mock.py

Tier:
  - core/types.py
  - routing/tiered_attunement.py
```

### C. Module Size Distribution

```
> 1000 lines: 3 files (cli.py, manager.py, naaru.py)
500-1000:     12 files
200-500:      35 files
< 200:        75 files
```

---

## References

- RFC-010: Sunwell Core Architecture
- RFC-013: Hierarchical Memory
- RFC-014: Multi-Topology Memory
- RFC-019: Naaru Architecture
- [Martin Fowler: Refactoring](https://refactoring.com/)
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
