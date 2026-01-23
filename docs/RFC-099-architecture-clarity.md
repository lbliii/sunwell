# RFC-099: Architecture Clarity — Self-Documentation for Scale

**Status**: Draft  
**Author**: Lawrence Lane  
**Created**: 2026-01-22  
**Target Version**: v0.2  
**Confidence**: 92% 🟢  
**Depends On**: None  
**Evidence**: `TECHNICAL-VISION.md`, `src/sunwell/naaru/__init__.py`, 98 existing RFCs

---

## Summary

Create **three essential architecture artifacts** that reduce cognitive load and prevent architectural drift as Sunwell grows:

1. **`ARCHITECTURE.md`** — One-page module map and data flow (60-second scan)
2. **`DESIGN-PRINCIPLES.md`** — Crystallized rules already being followed
3. **`scripts/arch_graph.py`** — Auto-generated dependency visualization

**Why now**: With 98 RFCs and 470+ files, the architecture has stabilized enough to document but is complex enough to need a map. This is documentation *for the maintainer*, not external users.

**Scope**: Internal clarity only. External documentation (API stability tiers, contributor onboarding, ADRs) deferred until external users exist.

---

## Goals and Non-Goals

### Goals

1. **One-page architecture reference** — Scannable in 60 seconds, answers "where does X go?"
2. **Crystallized design rules** — Prevent drift by documenting implicit decisions
3. **Dependency visualization** — Auto-generated graph to catch coupling issues early
4. **Self-documentation** — Reduce cognitive load when returning to code after breaks

### Non-Goals

1. **External documentation** — No contributor guides, API contracts, or stability tiers yet
2. **ADRs (Architecture Decision Records)** — Document "why" when others need to know
3. **Refactoring for clarity** — Don't simplify `naaru/__init__.py`; it works
4. **Marketing documentation** — This is internal reference, not user-facing

---

## Motivation

### The Problem

```
Current state:
┌────────────────────────────────────────────────────────────┐
│  TECHNICAL-VISION.md (5000+ lines)                        │
│  + 98 RFCs (scattered)                                    │
│  + naaru/__init__.py (537 lines of re-exports)            │
│  = "Where does X go?" takes 10+ minutes to answer         │
└────────────────────────────────────────────────────────────┘
```

Symptoms:
- **Mental overhead**: Holding 40+ module purposes in working memory
- **Drift risk**: Implicit rules not written down → inconsistent decisions
- **Post-break re-orientation**: Returning to code after a week requires re-discovery

### Why Now

| Signal | Value | Implication |
|--------|-------|-------------|
| RFC count | 98 | Core design has stabilized |
| File count | 470+ | Past exploration phase |
| Thesis verified | ✅ | Not pivoting on fundamentals |
| Version | 0.1.0 | Pre-1.0 but architecture is real |

The architecture is stable enough to document but complex enough to need a map.

### Why Not More

| Artifact | Why Defer |
|----------|-----------|
| ADRs | The "why" matters when others join; for now, you know why |
| API stability markers | No external users importing your code yet |
| Contributor onboarding | Write when you actually onboard someone |
| Simplified exports | Don't refactor working code for aesthetics |

---

## Design

### Artifact 1: `ARCHITECTURE.md`

**Purpose**: One-page reference for "where does X go?"

**Location**: `/ARCHITECTURE.md` (root level, high visibility)

**Structure**:

```markdown
# Sunwell Architecture

## Module Map

```
sunwell/
├── core/           # Primitive types, errors, protocols (NO I/O)
├── types/          # Shared type definitions
├── naaru/          # Cognitive coordination layer
│   ├── planners/   # Task planning strategies
│   ├── workers/    # Parallel execution workers
│   ├── experiments/# Research experiments (not stable)
│   └── ...
├── models/         # LLM provider adapters
├── providers/      # Provider implementations (Ollama, OpenAI, etc.)
├── tools/          # Tool implementations (file, shell, code)
├── adaptive/       # Learning agent with feedback
├── guardrails/     # Safety constraints
├── simulacrum/     # Persona simulation (internal)
├── cli/            # Command-line interface
└── ...
```

## Data Flow

```
User Goal → Router → Planner → [Tasks] → Executor → [Results] → Synthesis → Output
              │                    │                    │
              ▼                    ▼                    ▼
           Lenses            Shards (∥)            Resonance
```

## Core Abstractions

| Concept | Type | Location | Purpose |
|---------|------|----------|---------|
| `Naaru` | Class | `naaru/coordinator.py` | Orchestrates everything |
| `Convergence` | Class | `naaru/convergence.py` | Working memory (7±2 slots) |
| `Shard` | Class | `naaru/shards.py` | Parallel CPU worker |
| `ArtifactSpec` | Dataclass | `naaru/artifacts.py` | What must exist when goal is complete |
| `Task` | Dataclass | `naaru/types.py` | Unit of work with dependencies |
| `Lens` | Dataclass | `core/lens.py` | Domain expertise container |

## Module Boundaries

| Layer | Modules | Rule |
|-------|---------|------|
| **Core** | `core/`, `types/` | No I/O, no dependencies on other sunwell modules |
| **Models** | `models/`, `providers/` | Adapters only, no business logic |
| **Intelligence** | `naaru/`, `adaptive/`, `simulacrum/` | Can use Core + Models |
| **Execution** | `tools/`, `execution/`, `runtime/` | Can use Intelligence |
| **Interface** | `cli/`, `interface/` | Top layer, can use everything |

## Quick Reference

| I want to... | Look in |
|--------------|---------|
| Add a new tool | `tools/` |
| Modify planning | `naaru/planners/` |
| Add CLI command | `cli/` |
| Change core types | `core/` (read DESIGN-PRINCIPLES.md first) |
| Add model provider | `providers/` |
| Modify event system | `adaptive/events.py` |
```

**Estimated length**: ~100 lines

---

### Artifact 2: `DESIGN-PRINCIPLES.md`

**Purpose**: Crystallize rules already being followed to prevent drift.

**Location**: `/DESIGN-PRINCIPLES.md` (root level)

**Structure**:

```markdown
# Sunwell Design Principles

## 1. The Prism Principle

> "The prism doesn't add light. It reveals what was already there."

Don't enhance the model. Refract it into perspectives.

**Application**:
- Harmonic synthesis = multiple perspectives in parallel
- Resonance = feedback reveals hidden capability
- Lenses = wavelength filters for expertise

---

## 2. Types as Contracts

> "Type signatures are contracts that define behavior."

If it's not in the type, it doesn't exist.

```python
# ❌ Bad: behavior not in type
def process(data: dict) -> dict: ...

# ✅ Good: contract is clear
def process(artifact: ArtifactSpec) -> ExecutionResult: ...
```

**Enforced by**: `mypy --strict`

---

## 3. Immutable by Default

> "Mutations are bugs waiting to happen in parallel code."

All core types use frozen dataclasses for thread safety.

```python
# ✅ Standard pattern
@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    id: str
    description: str
    requires: frozenset[str] = frozenset()
```

**Why**: Python 3.14t (free-threaded) requires immutable data for safe parallelism.

---

## 4. Models are Passive

> "Core models do no I/O. Orchestrators do all I/O."

```python
# ❌ Bad: I/O in core model
class ArtifactSpec:
    def save(self, path: Path): ...  # I/O in model!

# ✅ Good: orchestrator handles I/O
class ArtifactExecutor:
    def save(self, spec: ArtifactSpec, path: Path): ...
```

**Boundary**: Everything in `core/` is I/O-free.

---

## 5. Fail Loudly

> "Explicit errors over silent degradation."

```python
# ❌ Bad: silent failure
def get_model(name: str) -> Model | None: ...

# ✅ Good: explicit error
def get_model(name: str) -> Model:
    raise ModelNotFoundError(name)
```

**Pattern**: Use `SunwellError` hierarchy with `ErrorCode` enum.

---

## 6. Evidence-First

> "All claims require `file:line` references."

When documenting behavior:
```markdown
The Naaru uses 7±2 slots for working memory.
**Source**: `sunwell/naaru/convergence.py:45`
```

---

## Quick Checklist

Before committing changes to `core/` or `naaru/`:

- [ ] Types are frozen dataclasses with `slots=True`
- [ ] No I/O in model classes
- [ ] Errors are explicit (no `Optional` for error cases)
- [ ] `mypy --strict` passes
- [ ] `ruff check` passes
```

**Estimated length**: ~80 lines

---

### Artifact 3: `scripts/arch_graph.py`

**Purpose**: Auto-generate dependency graph from imports to catch coupling issues.

**Location**: `/scripts/arch_graph.py`

**Output**: Mermaid diagram showing module dependencies

**Implementation**:

```python
#!/usr/bin/env python3
"""Generate architecture dependency graph from imports.

Usage:
    python scripts/arch_graph.py src/sunwell > docs/DEPENDENCY-GRAPH.md
    python scripts/arch_graph.py src/sunwell --format dot | dot -Tpng > arch.png
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path


def extract_imports(file_path: Path) -> set[str]:
    """Extract sunwell imports from a Python file."""
    try:
        tree = ast.parse(file_path.read_text())
    except SyntaxError:
        return set()
    
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("sunwell."):
                    imports.add(alias.name.split(".")[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("sunwell."):
                imports.add(node.module.split(".")[1])
    return imports


def build_dependency_graph(src_dir: Path) -> dict[str, set[str]]:
    """Build module-level dependency graph."""
    graph: dict[str, set[str]] = defaultdict(set)
    
    for py_file in src_dir.rglob("*.py"):
        # Get module name from path
        rel_path = py_file.relative_to(src_dir)
        if len(rel_path.parts) < 2:
            continue
        module = rel_path.parts[0]
        
        # Get imports
        imports = extract_imports(py_file)
        for imp in imports:
            if imp != module:  # Ignore self-imports
                graph[module].add(imp)
    
    return dict(graph)


def to_mermaid(graph: dict[str, set[str]]) -> str:
    """Convert graph to Mermaid diagram."""
    lines = ["graph TD"]
    
    # Define layers
    layers = {
        "core": "Core",
        "types": "Core",
        "models": "Models",
        "providers": "Models",
        "naaru": "Intelligence",
        "adaptive": "Intelligence",
        "simulacrum": "Intelligence",
        "tools": "Execution",
        "execution": "Execution",
        "runtime": "Execution",
        "cli": "Interface",
        "interface": "Interface",
    }
    
    # Group by layer
    by_layer: dict[str, list[str]] = defaultdict(list)
    for module in graph:
        layer = layers.get(module, "Other")
        by_layer[layer].append(module)
    
    # Add subgraphs
    for layer, modules in sorted(by_layer.items()):
        lines.append(f'    subgraph {layer}')
        for mod in sorted(modules):
            lines.append(f'        {mod}[{mod}/]')
        lines.append('    end')
    
    # Add edges
    lines.append('')
    for src, dests in sorted(graph.items()):
        for dest in sorted(dests):
            lines.append(f'    {src} --> {dest}')
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: arch_graph.py <src_dir> [--format mermaid|dot]", file=sys.stderr)
        sys.exit(1)
    
    src_dir = Path(sys.argv[1])
    fmt = "mermaid"
    if "--format" in sys.argv:
        fmt = sys.argv[sys.argv.index("--format") + 1]
    
    graph = build_dependency_graph(src_dir)
    
    if fmt == "mermaid":
        print("# Dependency Graph\n")
        print("```mermaid")
        print(to_mermaid(graph))
        print("```")
    else:
        # DOT format for graphviz
        print("digraph sunwell {")
        print("    rankdir=TB;")
        for src, dests in graph.items():
            for dest in dests:
                print(f'    "{src}" -> "{dest}";')
        print("}")


if __name__ == "__main__":
    main()
```

**Usage**:
```bash
# Generate Mermaid markdown
python scripts/arch_graph.py src/sunwell > docs/DEPENDENCY-GRAPH.md

# Generate PNG via Graphviz
python scripts/arch_graph.py src/sunwell --format dot | dot -Tpng -o docs/arch.png
```

---

## Implementation Plan

### Phase 1: Create Artifacts (2-3 hours)

| Task | Time | Output |
|------|------|--------|
| Write `ARCHITECTURE.md` | 1h | `/ARCHITECTURE.md` |
| Write `DESIGN-PRINCIPLES.md` | 45m | `/DESIGN-PRINCIPLES.md` |
| Create `arch_graph.py` | 45m | `/scripts/arch_graph.py` |
| Generate initial graph | 15m | `/docs/DEPENDENCY-GRAPH.md` |

### Phase 2: Validate (30 min)

| Check | Pass Criteria |
|-------|---------------|
| Architecture map covers all modules | Every `src/sunwell/*` dir mentioned |
| Principles match actual code | Spot-check 5 files against rules |
| Dependency graph is accurate | Manual verification of 3 edges |

### Commit Strategy

```bash
# Single atomic commit
git add ARCHITECTURE.md DESIGN-PRINCIPLES.md scripts/arch_graph.py docs/DEPENDENCY-GRAPH.md
git commit -m "docs: add architecture clarity artifacts (RFC-099)"
```

---

## Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Time to answer "where does X go?"** | < 30 seconds | Self-test with random module |
| **Architecture doc scannable** | < 60 seconds | Time yourself reading it |
| **Principles actionable** | Yes/No checklist | Each principle has code example |
| **Dependency graph accurate** | 95% edges correct | Spot-check 10 imports |

---

## Future Work (Deferred)

When external users exist:

| Artifact | Trigger |
|----------|---------|
| ADRs (Architecture Decision Records) | First external contributor |
| API stability tiers (Stable/Evolving/Experimental) | First external import |
| Contributor onboarding guide | Onboarding someone |
| Simplified `naaru/__init__.py` | User feedback on import confusion |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Docs go stale | Medium | Low | Keep docs minimal; link to code |
| Over-documentation | Low | Medium | Strict scope: 3 artifacts only |
| Premature abstraction | Low | Low | Document what exists, don't prescribe |

---

## Alternatives Considered

### Alternative 1: Full Documentation Suite Now

Create ADRs, API contracts, contributor guides, etc.

**Rejected because**: No external users yet. Documentation for non-existent audience is waste.

### Alternative 2: Do Nothing

Wait until v1.0 or external users.

**Rejected because**: Cognitive load is already a problem at 470+ files. Self-documentation has immediate ROI.

### Alternative 3: Inline Documentation Only

Rely solely on module docstrings.

**Rejected because**: Docstrings don't show cross-module relationships or architectural rules.

---

## References

- `TECHNICAL-VISION.md` — Existing comprehensive vision doc
- `src/sunwell/naaru/__init__.py` — 537-line export file showing complexity
- RFC-001 through RFC-098 — Design decisions to crystallize
- ADR format: https://adr.github.io/
