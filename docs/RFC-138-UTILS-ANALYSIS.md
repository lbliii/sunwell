# RFC-138 Utils Analysis: Systems, Subsystems, and Information Flow

**Status**: Analysis  
**Related**: RFC-138 (Module Architecture Consolidation)  
**Created**: 2026-01-25

---

## Executive Summary

This document analyzes:
1. **Systems and subsystems** - How Sunwell's domains interact
2. **Information flow** - How data moves through the system
3. **Orchestration patterns** - Where coordination happens
4. **Utility organization** - Whether `utils/` is needed and where utilities belong

**Conclusion**: We should **NOT** create a top-level `utils/` module. Instead:
- **Generic utilities** → `foundation/utils/` (zero-dependency helpers)
- **Domain-specific utilities** → Stay in their domains (e.g., `agent/utils/`, `knowledge/utils/`)
- **Cross-cutting concerns** → `foundation/` (hashing, serialization, validation)

---

## Systems and Subsystems Analysis

### Tier 0: Foundation (Zero Dependencies)

**Purpose**: Base types, config, errors, identity - no sunwell imports

**Current State**:
- `types/` - Type definitions
- `config.py` - Configuration
- `core/errors.py` - Error types
- `core/identity.py` - URI system, slugify, validation
- `core/freethreading.py` - Parallelism utilities
- `schema/` - Schema loading
- `binding/` - Binding system

**Information Flow**: 
- **Input**: None (stdlib only)
- **Output**: Types, config, errors consumed by all tiers

**Utilities Here**:
- ✅ String manipulation (`slugify`, `normalize_path`)
- ✅ Validation (`validate_slug`, `validate_uri`)
- ✅ Hashing (generic content hashing)
- ✅ Serialization (JSON, YAML helpers)
- ✅ Path utilities (filesystem-safe operations)

---

### Tier 1: Models (LLM Abstraction)

**Purpose**: Model protocols, providers, capability detection

**Current State**:
- `models/` - Model protocols
- `providers/` - Provider implementations

**Information Flow**:
- **Input**: `foundation/` (types, config, errors)
- **Output**: Model calls, tool capability detection

**Utilities Here**:
- ✅ Model-specific parsing (response parsing, tool call extraction)
- ✅ Capability detection helpers
- ❌ NOT generic string/path utilities (those belong in foundation)

---

### Tier 2: Tools (Tool System)

**Purpose**: Tool definitions, handlers, execution

**Current State**:
- `tools/` - Well-organized already

**Information Flow**:
- **Input**: `foundation/`, `models/`
- **Output**: Tool execution results

**Utilities Here**:
- ✅ Tool-specific validation
- ✅ Tool result formatting
- ❌ NOT generic utilities

---

### Tier 3: Knowledge (Codebase Understanding)

**Purpose**: Understanding code, projects, workspaces

**Current State**:
- `analysis/`, `indexing/`, `workspace/`, `project/`, `bootstrap/`, `embedding/`, `navigation/`, `intelligence/`, `environment/`

**Information Flow**:
- **Input**: `foundation/`, `models/`, `tools/`
- **Output**: Codebase understanding, embeddings, navigation

**Utilities Here**:
- ✅ Code parsing utilities (`knowledge/utils/parsing.py`)
- ✅ AST manipulation (`knowledge/utils/ast.py`)
- ✅ File scanning (`knowledge/utils/scanner.py`)
- ❌ NOT generic string/path utilities

---

### Tier 4: Memory (Persistent State)

**Purpose**: Remembering past interactions

**Current State**:
- `memory/`, `simulacrum/`, `lineage/`, `session/`

**Information Flow**:
- **Input**: `foundation/`, `knowledge/`
- **Output**: Memory queries, session state

**Utilities Here**:
- ✅ Memory serialization (`memory/utils/serialization.py`)
- ✅ Session utilities (`memory/utils/session.py`)
- ❌ NOT generic serialization (that's foundation)

---

### Tier 5: Planning (Intent → Plan)

**Purpose**: Routing, reasoning, planning, skills

**Current State**:
- `routing/`, `reasoning/`, `naaru/`, `skills/`, `lens/`

**Information Flow**:
- **Input**: `foundation/`, `memory/`, `knowledge/`
- **Output**: Plans, routes, skill compositions

**Utilities Here**:
- ✅ Plan validation (`planning/utils/validation.py`)
- ✅ Route matching (`planning/utils/matching.py`)
- ❌ NOT generic utilities

---

### Tier 6: Agent (Core Execution)

**Purpose**: THE execution engine

**Current State**:
- `agent/` + merged: `context/`, `convergence/`, `recovery/`, `prefetch/`, `chat/`, `incremental/`, `execution/`, `runtime/`, `parallel/`

**Information Flow**:
- **Input**: All lower tiers
- **Output**: Execution results, events, state changes

**Utilities Here**:
- ✅ Execution utilities (`agent/utils/execution.py`)
- ✅ Event formatting (`agent/utils/events.py`)
- ✅ State management (`agent/utils/state.py`)
- ❌ NOT generic utilities

**Special Case**: `incremental/hasher.py`
- This is **domain-specific** (artifact hashing for incremental execution)
- Should move to `agent/incremental/utils/hashing.py` or stay as `agent/incremental/hasher.py`
- NOT generic hashing (that's `foundation/utils/hashing.py`)

---

### Tier 7: Quality (Verification & Safety)

**Purpose**: Quality assurance

**Current State**:
- `verification/`, `guardrails/`, `security/`, `confidence/`, `weakness/`

**Information Flow**:
- **Input**: `foundation/`, `agent/`
- **Output**: Validation results, confidence scores

**Utilities Here**:
- ✅ Validation utilities (`quality/utils/validation.py`)
- ✅ Scoring utilities (`quality/utils/scoring.py`)
- ❌ NOT generic validation (that's foundation)

---

### Tier 8: Interface (User-Facing)

**Purpose**: CLI, Server, UI

**Current State**:
- `cli/`, `server/`, `surface/`, `interface/`

**Information Flow**:
- **Input**: All tiers
- **Output**: User interactions, API responses

**Utilities Here**:
- ✅ CLI formatting (`interface/cli/utils/formatting.py`)
- ✅ Server utilities (`interface/server/utils/`)
- ✅ UI primitives (`interface/surface/utils/`)
- ❌ NOT generic formatting (that's foundation)

---

## Information Flow Patterns

### Pattern 1: Request → Planning → Execution → Response

```
User Request
    ↓
[interface/] CLI/Server receives
    ↓
[planning/] Routing → Reasoning → Naaru planning
    ↓
[agent/] Execution engine
    ↓
[tools/] Tool execution
    ↓
[models/] LLM calls
    ↓
[agent/] Event emission
    ↓
[interface/] Response formatting
    ↓
User Response
```

**Orchestration Point**: `agent/core.py` (Agent class)

---

### Pattern 2: Codebase Understanding → Memory → Planning

```
Codebase Change
    ↓
[knowledge/] Analysis → Indexing → Embedding
    ↓
[memory/] Store in simulacrum/lineage
    ↓
[planning/] Use for routing/reasoning
    ↓
[agent/] Execution uses context
```

**Orchestration Point**: `knowledge/workspace/` (workspace detection triggers analysis)

---

### Pattern 3: Incremental Execution (Hash-Based)

```
Artifact Spec
    ↓
[agent/incremental/] Compute input hash
    ↓
[memory/] Check cache
    ↓
Cache Hit? → Return cached
Cache Miss → Execute → Store result
```

**Orchestration Point**: `agent/incremental/executor.py`

**Utility Location**: `agent/incremental/hasher.py` (domain-specific, NOT generic)

---

## Utility Classification

### Generic Utilities (→ `foundation/utils/`)

**Criteria**: 
- Zero dependencies on sunwell modules
- Used by 3+ domains
- Pure functions (no state)

**Examples**:
```python
# foundation/utils/strings.py
def slugify(name: str) -> str: ...
def normalize_path(path: str) -> str: ...
def sanitize_filename(name: str) -> str: ...

# foundation/utils/validation.py
def validate_slug(slug: str) -> None: ...
def validate_uri(uri: str) -> None: ...

# foundation/utils/hashing.py
def compute_hash(content: bytes) -> str: ...
def compute_file_hash(path: Path) -> str: ...

# foundation/utils/serialization.py
def safe_json_loads(data: str) -> dict: ...
def safe_yaml_load(path: Path) -> dict: ...
```

**Current Location**: Some in `core/identity.py`, `core/freethreading.py`

---

### Domain-Specific Utilities (→ Stay in Domain)

**Criteria**:
- Used by 1-2 domains
- Domain-specific logic

**Examples**:
```python
# agent/incremental/hasher.py (artifact hashing)
def compute_input_hash(spec: ArtifactSpec, deps: dict) -> str: ...

# knowledge/utils/ast.py (AST manipulation)
def extract_function_defs(node: ast.AST) -> list: ...

# planning/utils/matching.py (route matching)
def match_intent(text: str, routes: list) -> Route: ...

# interface/cli/utils/formatting.py (CLI output)
def format_table(data: list) -> str: ...
```

---

### Cross-Cutting Utilities (→ `foundation/`)

**Criteria**:
- Used by many domains
- But have domain-specific behavior

**Examples**:
```python
# foundation/errors.py (already exists)
def from_openai_error(exc: Exception) -> SunwellError: ...

# foundation/identity.py (already exists)
def parse_legacy_name(name: str) -> SunwellURI: ...

# foundation/freethreading.py (already exists)
def optimal_workers(workload: WorkloadType) -> int: ...
```

**These stay in `foundation/` but are NOT in `utils/` because they're core domain models, not utilities.**

---

## Proposed Structure

### Option A: No Top-Level Utils (RECOMMENDED)

```
foundation/
├── types/           # Type definitions
├── config.py        # Configuration
├── errors.py        # Error types + translation utilities
├── identity.py      # URI system + slugify/validate utilities
├── freethreading.py # Parallelism utilities
├── utils/           # NEW: Generic utilities
│   ├── __init__.py
│   ├── strings.py   # slugify, normalize, sanitize
│   ├── validation.py # validate_slug, validate_uri
│   ├── hashing.py   # Generic content hashing
│   ├── serialization.py # JSON/YAML helpers
│   └── paths.py     # Path utilities
└── ...

agent/
├── incremental/
│   ├── hasher.py    # Domain-specific artifact hashing
│   └── ...
└── utils/           # Agent-specific utilities
    ├── execution.py
    └── events.py

knowledge/
└── utils/           # Knowledge-specific utilities
    ├── parsing.py
    └── ast.py

planning/
└── utils/           # Planning-specific utilities
    └── matching.py

interface/
├── cli/
│   └── utils/       # CLI-specific utilities
│       └── formatting.py
└── ...
```

**Rationale**:
- ✅ Generic utilities in `foundation/utils/` (zero-deps, reusable)
- ✅ Domain utilities stay in domains (clear ownership)
- ✅ No top-level `utils/` (avoids "where does this belong?" confusion)

---

### Option B: Top-Level Utils (NOT RECOMMENDED)

```
utils/               # Top-level utils
├── strings.py
├── validation.py
├── hashing.py
└── ...

foundation/
└── ... (no utils/)

agent/utils/
knowledge/utils/
...
```

**Problems**:
- ❌ Breaks tier hierarchy (utils would need to import foundation)
- ❌ Unclear what's generic vs domain-specific
- ❌ Creates "dumping ground" risk

---

## Migration Plan

### Phase 1: Create `foundation/utils/`

1. Create `foundation/utils/__init__.py`
2. Move generic utilities from `core/identity.py`:
   - `slugify()` → `foundation/utils/strings.py`
   - `validate_slug()` → `foundation/utils/validation.py`
3. Extract generic hashing from `incremental/hasher.py`:
   - Generic `compute_hash()` → `foundation/utils/hashing.py`
   - Keep `compute_input_hash()` in `agent/incremental/hasher.py` (domain-specific)

### Phase 2: Create Domain Utils

1. Create `agent/utils/` for agent-specific utilities
2. Create `knowledge/utils/` for knowledge-specific utilities
3. Create `planning/utils/` for planning-specific utilities
4. Create `interface/cli/utils/` for CLI-specific utilities

### Phase 3: Update Imports

1. Update all imports to use `foundation/utils/` for generic utilities
2. Update domain-specific imports to use domain utils
3. Remove duplicate utility functions

---

## Decision Matrix

| Utility Type | Current Location | Proposed Location | Rationale |
|-------------|------------------|-------------------|-----------|
| `slugify()` | `core/identity.py` | `foundation/utils/strings.py` | Generic string manipulation |
| `validate_slug()` | `core/identity.py` | `foundation/utils/validation.py` | Generic validation |
| `compute_input_hash()` | `incremental/hasher.py` | `agent/incremental/hasher.py` | Domain-specific (artifact hashing) |
| Generic `compute_hash()` | (doesn't exist) | `foundation/utils/hashing.py` | Generic hashing |
| `is_free_threaded()` | `core/freethreading.py` | `foundation/freethreading.py` | Cross-cutting, stays in foundation |
| `format_workspace_context()` | `cli/helpers.py` | `interface/cli/utils/formatting.py` | CLI-specific |
| AST utilities | (scattered) | `knowledge/utils/ast.py` | Knowledge-specific |

---

## Open Questions

1. **Should `foundation/utils/` be a package or flat module?**
   - **Recommendation**: Package (`utils/strings.py`, `utils/validation.py`) for organization
   - Alternative: Flat (`utils.py`) if utilities are small

2. **What about CLI helpers that are used by server too?**
   - **Recommendation**: If truly shared, move to `foundation/utils/formatting.py`
   - If CLI-specific, keep in `interface/cli/utils/`

3. **Should we have `foundation/utils/` at all, or keep everything in domain modules?**
   - **Recommendation**: Yes, for truly generic utilities (string manipulation, validation, generic hashing)
   - Domain-specific utilities stay in domains

---

## Recommendations

1. ✅ **Create `foundation/utils/`** for generic utilities
2. ✅ **Create domain-specific `utils/` subdirectories** where needed
3. ❌ **Do NOT create top-level `utils/`** (breaks tier hierarchy)
4. ✅ **Move `slugify()` and `validate_slug()`** from `core/identity.py` to `foundation/utils/`
5. ✅ **Keep `compute_input_hash()`** in `agent/incremental/hasher.py` (domain-specific)
6. ✅ **Extract generic hashing** to `foundation/utils/hashing.py` if needed

---

## Next Steps

1. Review this analysis
2. Decide on utility organization (Option A recommended)
3. Update RFC-138 with utility placement decisions
4. Create migration plan for utilities
5. Execute migration alongside RFC-138 domain consolidation
