# RFC-085: Self-Knowledge Architecture

**Status**: Draft  
**Author**: Sunwell Team  
**Date**: 2026-01-21  
**Supersedes**: RFC-015 (Mirror Neurons) — never documented  
**Related**: RFC-084 (Simulacrum v2), RFC-083 (Naaru Unification)

---

## Summary

Sunwell should be able to understand, debug, and improve itself. This capability is partially implemented in `sunwell/mirror/` but is broken in production: the system conflates "workspace root" (user's project) with "Sunwell source root" (where Sunwell's code lives), causing self-introspection to fail when running from user projects.

This RFC proposes a clean **Self-Knowledge Architecture** that:

1. Separates workspace from self-knowledge permanently
2. Makes self-introspection work in all contexts (Studio, CLI, tests)
3. Enables three key use cases: Learn, Debug, Code

---

## Goals

1. **Fix introspection in all contexts** — `introspect_source("sunwell.tools")` works from any workspace
2. **Unify self-knowledge access** — Single `Self.get()` entry point, no path passing
3. **Add sandbox testing for proposals** — Test changes before applying to real source
4. **Thread-safe singleton** — Safe under Python 3.14t free-threading

## Non-Goals

1. **Multi-installation support** — We assume one Sunwell per environment (no venv introspection)
2. **Remote introspection** — No support for introspecting Sunwell on another machine
3. **Automatic proposal application** — Human approval always required before merge
4. **Full CI/CD integration** — PR creation is in scope, but pipeline orchestration is not
5. **Self-modification of `sunwell/self/`** — Meta-circular modification is explicitly blocked

---

## Use Cases

### UC-1: "I want to learn about Sunwell"

**Actor**: New user, contributor, or the agent itself

**Scenarios**:
- "How does the planning system work?"
- "What tools are available?"
- "Explain the memory architecture"
- "Show me the types used in the tool executor"

**Current state**: Partially works in `sunwell chat --mirror`, completely broken in Studio.

**Why Studio is broken**: Studio spawns Naaru with `workspace` set to the user's project directory. When `MirrorHandler` is created, it passes this workspace path to `SourceIntrospector`. Despite the fix in `introspection.py:46-48` that auto-resolves the source root, `MirrorHandler` at line 67 still instantiates `SourceIntrospector(self.sunwell_root)` — the constructor ignores the parameter but the handler shouldn't be passing workspace paths at all.

**Desired state**: Sunwell can explain any part of itself with source citations, architecture diagrams, and working examples.

---

### UC-2: "I want Sunwell to debug itself"

**Actor**: Developer debugging Sunwell, or Sunwell itself during self-diagnosis

**Scenarios**:
- "Why did that tool call fail?"
- "What's causing high latency in synthesis?"
- "Find the root cause of this error traceback"
- "Which model performs best for code generation?"

**Current state**: `analyze_failures`, `analyze_patterns`, `analyze_model_performance` tools exist but are disconnected from source introspection.

**Desired state**: Sunwell can trace errors to source code, correlate patterns with implementations, and propose fixes.

---

### UC-3: "I want Sunwell to code itself"

**Actor**: Developer improving Sunwell, or Sunwell proposing self-improvements

**Scenarios**:
- "Add a new tool for X"
- "Improve the error messages in the validator"
- "Optimize the hot path in chunk retrieval"
- "Fix this bug in the planner"

**Current state**: `propose_improvement`, `apply_proposal` exist but proposals can't be tested, and there's no CI integration.

**Desired state**: Sunwell can write code, create tests, run them, and submit PRs with proper review workflow.

---

## Current Architecture Problems

### Problem 1: Conflated Roots

The parameter `sunwell_root` conflates two unrelated concepts:

| Passed as `sunwell_root` | Actually means | Used for |
|-------------------------|----------------|----------|
| User's project dir | Workspace | File tools, `.sunwell/` storage, lenses |
| User's project dir | ❌ Not Sunwell source | Source introspection (broken) |

```python
# cli/agent/run.py — uses cwd (user's project)
naaru = Naaru(sunwell_root=Path.cwd(), ...)

# cli/chat.py — correctly resolves Sunwell source
sunwell_root = Path(sunwell.__file__).parent.parent.parent
```

**Result**: `introspect_source("sunwell.tools")` looks for `~/projects/forum-app/src/sunwell/tools.py` which doesn't exist.

### Problem 2: No Unified Self-Knowledge Service

Self-knowledge is scattered across:

| Location | What it does | State |
|----------|-------------|-------|
| `mirror/introspection.py` | Source reading | Works (with fix) |
| `mirror/analysis.py` | Pattern analysis | Works |
| `mirror/proposals.py` | Improvement proposals | Works |
| `mirror/handler.py` | Tool routing | Needs path passed |
| `mirror/model_tracker.py` | Model performance | Works |

Each component is created separately with paths passed around. No central coordination.

### Problem 3: Self-Coding is Unsafe

Current implementation:
- `apply_proposal` writes directly to source files
- No sandboxing for self-modifications
- No test execution before apply
- No rollback if tests fail
- No PR workflow

---

## Design Alternatives Considered

### Alternative 1: Dependency Injection

Pass `SelfKnowledge` instance to components that need it.

```python
class Naaru:
    def __init__(self, workspace: Path, self_knowledge: SelfKnowledge | None = None):
        self._self = self_knowledge or SelfKnowledge.create_default()
```

**Pros**: Explicit dependencies, easy to mock in tests  
**Cons**: Requires threading `self_knowledge` through many layers; self-knowledge is truly global (one installation), not contextual

**Rejected**: Added complexity without benefit — there's genuinely only one Sunwell to know about.

### Alternative 2: ContextVar-Based Singleton

Use `contextvars.ContextVar` for test isolation.

```python
_self_instance: ContextVar[Self | None] = ContextVar("self_instance", default=None)

@classmethod
def get(cls) -> "Self":
    instance = _self_instance.get()
    if instance is None:
        instance = cls._create_default()
        _self_instance.set(instance)
    return instance
```

**Pros**: Perfect test isolation per-context  
**Cons**: Overhead per-coroutine; self-knowledge doesn't vary by context

**Rejected**: Unnecessary complexity — `Self.reset()` is sufficient for test isolation.

### Alternative 3: Module-Level Instance

Simpler than class-based singleton.

```python
# sunwell/self/__init__.py
_self: Self | None = None

def get_self() -> Self:
    global _self
    if _self is None:
        _self = Self._create_default()
    return _self
```

**Pros**: Simpler, no class machinery  
**Cons**: Global state mutation, harder to type, no `reset()` without touching `_self` directly

**Rejected**: Class-based singleton is more explicit and testable.

### Chosen: Class-Based Singleton with Lock

The `Self` class with `_instance` class variable and thread-safe initialization provides:
- Clear API (`Self.get()`)
- Test support (`Self.reset()`)
- Thread safety for 3.14t (see implementation)

---

## Proposed Architecture

### Core Principle: Sunwell's Self-Knowledge is Global

There is exactly **one** Sunwell installation. Self-knowledge should be a global singleton, not parameterized by workspace.

```
┌─────────────────────────────────────────────────────────────┐
│                     Global Singleton                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                      Self                            │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │  Source  │  │ Analysis │  │    Proposals     │  │   │
│  │  │          │  │          │  │                  │  │   │
│  │  │ read     │  │ patterns │  │ create           │  │   │
│  │  │ search   │  │ failures │  │ test (sandbox)   │  │   │
│  │  │ explain  │  │ models   │  │ apply            │  │   │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          │ auto-resolved                    │
│                          ▼                                  │
│              Path(sunwell.__file__).parent.parent.parent   │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ accessed by
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Per-Session Instances                       │
│                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│   │    Naaru     │    │    Agent     │    │    Studio    │ │
│   │              │    │              │    │              │ │
│   │ workspace:   │    │ workspace:   │    │ workspace:   │ │
│   │ ~/forum-app/ │    │ ~/my-proj/   │    │ ~/todo-app/  │ │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘ │
│          │                   │                   │          │
│          └───────────────────┼───────────────────┘          │
│                              │                              │
│                    Self.get().introspect(...)               │
└─────────────────────────────────────────────────────────────┘
```

### The `Self` Singleton

```python
# sunwell/self/__init__.py

import threading
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path


@dataclass
class Self:
    """Sunwell's self-knowledge service.
    
    Singleton — there is exactly one Sunwell installation to know about.
    Auto-resolves source location from package metadata.
    
    Thread-safe under Python 3.14t free-threading via double-checked locking.
    
    Access via Self.get():
        >>> Self.get().source.read_module("sunwell.tools.executor")
        >>> Self.get().analysis.recent_failures()
        >>> Self.get().proposals.create(...)
    """
    
    _source_root: Path
    _storage_root: Path
    
    # === Components (lazy-initialized) ===
    
    @cached_property
    def source(self) -> "SourceKnowledge":
        """Read and understand Sunwell's source code."""
        from sunwell.self.source import SourceKnowledge
        return SourceKnowledge(self._source_root)
    
    @cached_property
    def analysis(self) -> "AnalysisKnowledge":
        """Analyze Sunwell's behavior and performance."""
        from sunwell.self.analysis import AnalysisKnowledge
        return AnalysisKnowledge(self._storage_root / "analysis")
    
    @cached_property
    def proposals(self) -> "ProposalManager":
        """Create and manage self-improvement proposals."""
        from sunwell.self.proposals import ProposalManager
        return ProposalManager(
            source_root=self._source_root,
            storage_root=self._storage_root / "proposals",
        )
    
    # === Thread-Safe Singleton Access (3.14t compatible) ===
    
    _instance: "Self | None" = None
    _lock: threading.Lock = threading.Lock()
    
    @classmethod
    def get(cls) -> "Self":
        """Get the global Self instance (thread-safe).
        
        Uses double-checked locking for performance:
        - Fast path: no lock if already initialized
        - Slow path: lock only during first initialization
        """
        if cls._instance is not None:
            return cls._instance
        
        with cls._lock:
            # Double-check after acquiring lock
            if cls._instance is None:
                cls._instance = cls._create_default()
            return cls._instance
    
    @classmethod
    def _create_default(cls) -> "Self":
        """Create Self with auto-resolved paths."""
        import sunwell
        
        # sunwell/__init__.py → src/sunwell → src → <project_root>
        source_root = Path(sunwell.__file__).parent.parent.parent
        
        # Global storage in ~/.sunwell/ (not per-workspace)
        storage_root = Path.home() / ".sunwell" / "self"
        storage_root.mkdir(parents=True, exist_ok=True)
        
        return cls(
            _source_root=source_root,
            _storage_root=storage_root,
        )
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing).
        
        Thread-safe — acquires lock before clearing.
        """
        with cls._lock:
            cls._instance = None
```

### Source Knowledge

```python
# sunwell/self/source.py

@dataclass
class SourceKnowledge:
    """Understand Sunwell's source code."""
    
    root: Path
    
    def read_module(self, module: str) -> str:
        """Read source code of a module.
        
        >>> Self.get().source.read_module("sunwell.tools.executor")
        '"""Tool calling support..."""\\n\\nfrom dataclasses...'
        """
        ...
    
    def find_symbol(self, module: str, name: str) -> SymbolInfo:
        """Find a class, function, or constant.
        
        >>> info = Self.get().source.find_symbol("sunwell.tools.executor", "ToolExecutor")
        >>> info.type
        'class'
        >>> info.methods
        ['execute', 'get_audit_log', ...]
        """
        ...
    
    def search(self, query: str) -> list[SearchResult]:
        """Semantic search across Sunwell's codebase.
        
        >>> results = Self.get().source.search("how does tool execution work")
        >>> results[0].module
        'sunwell.tools.executor'
        """
        ...
    
    def explain(self, topic: str) -> Explanation:
        """Generate an explanation of a Sunwell concept.
        
        Uses source code + docstrings + type signatures to create
        a coherent explanation with citations.
        
        >>> explanation = Self.get().source.explain("planning system")
        >>> explanation.summary
        "Sunwell's planning system uses..."
        >>> explanation.citations
        [Citation(module='sunwell.naaru.planners', line=45), ...]
        """
        ...
    
    def list_modules(self) -> list[str]:
        """List all Sunwell modules."""
        ...
    
    def get_architecture(self) -> ArchitectureDiagram:
        """Generate architecture overview.
        
        Analyzes imports and class relationships to build
        a dependency graph visualization.
        """
        ...
```

### Analysis Knowledge

```python
# sunwell/self/analysis.py

@dataclass  
class AnalysisKnowledge:
    """Analyze Sunwell's runtime behavior."""
    
    storage: Path
    
    def record_execution(self, event: ExecutionEvent) -> None:
        """Record an execution event for analysis."""
        ...
    
    def recent_failures(self, limit: int = 10) -> list[FailureReport]:
        """Get recent failures with root cause analysis.
        
        >>> failures = Self.get().analysis.recent_failures()
        >>> failures[0].error
        'PathSecurityError: Path escapes workspace'
        >>> failures[0].root_cause
        'User path "../../../etc/passwd" attempted to escape jail'
        >>> failures[0].source_location
        SourceLocation(module='sunwell.tools.handlers', line=67)
        """
        ...
    
    def patterns(self, scope: str = "session") -> PatternReport:
        """Analyze behavioral patterns.
        
        >>> patterns = Self.get().analysis.patterns("week")
        >>> patterns.most_used_tools
        [('read_file', 1523), ('search_files', 892), ...]
        >>> patterns.error_hotspots
        [Hotspot(module='sunwell.tools.handlers', method='_safe_path', errors=23)]
        """
        ...
    
    def model_performance(self) -> ModelReport:
        """Compare model performance across task types."""
        ...
    
    def diagnose(self, error: Exception) -> Diagnosis:
        """Diagnose an error with source-level analysis.
        
        Traces the error to source code, finds similar past errors,
        and suggests fixes.
        """
        ...
```

### Proposal Manager (Safe Self-Coding)

```python
# sunwell/self/proposals.py

@dataclass
class ProposalManager:
    """Manage self-improvement proposals with safety guarantees."""
    
    source_root: Path
    storage_root: Path
    
    def create(
        self,
        title: str,
        description: str,
        changes: list[FileChange],
        tests: list[TestCase] | None = None,
    ) -> Proposal:
        """Create a self-improvement proposal.
        
        >>> proposal = Self.get().proposals.create(
        ...     title="Improve error messages in tool handlers",
        ...     description="Add context to PathSecurityError",
        ...     changes=[
        ...         FileChange(
        ...             path="sunwell/tools/handlers.py",
        ...             diff="...",
        ...         )
        ...     ],
        ...     tests=[
        ...         TestCase(
        ...             name="test_error_message_includes_context",
        ...             code="...",
        ...         )
        ...     ],
        ... )
        """
        ...
    
    def test(self, proposal: Proposal) -> TestResult:
        """Test a proposal in a sandbox.
        
        1. Creates a temporary copy of Sunwell source
        2. Applies the proposed changes
        3. Runs existing tests + new tests
        4. Returns pass/fail with details
        
        No changes to real source until apply().
        """
        ...
    
    def apply(self, proposal: Proposal, *, require_tests_pass: bool = True) -> ApplyResult:
        """Apply a tested proposal to source.
        
        Safety:
        - Requires tests to pass (unless overridden)
        - Creates git commit with proposal metadata
        - Stores rollback information
        - Does NOT push (human reviews first)
        """
        ...
    
    def rollback(self, proposal: Proposal) -> None:
        """Rollback an applied proposal."""
        ...
    
    def create_pr(self, proposal: Proposal) -> PullRequest:
        """Create a GitHub PR for human review.
        
        Generates:
        - Clear title and description
        - Test results summary
        - Source citations for reasoning
        - Links to related issues/RFCs
        """
        ...
```

---

## Tool Definitions

### Introspection Tools (Trust: DISCOVERY)

```yaml
introspect_source:
  description: "Read Sunwell's own source code"
  parameters:
    module: string  # e.g., "sunwell.tools.executor"
    symbol: string?  # Optional: specific class/function

explain_sunwell:
  description: "Get explanation of a Sunwell concept with source citations"
  parameters:
    topic: string  # e.g., "planning system", "memory architecture"

list_sunwell_modules:
  description: "List all Sunwell modules"
  parameters: {}

search_sunwell:
  description: "Semantic search across Sunwell's codebase"
  parameters:
    query: string
    limit: int = 10
```

### Analysis Tools (Trust: READ_ONLY)

```yaml
analyze_failures:
  description: "Analyze recent failures with root cause identification"
  parameters:
    limit: int = 10
    scope: enum[session, day, week, all]

analyze_patterns:
  description: "Analyze behavioral patterns"
  parameters:
    focus: enum[tool_usage, latency, errors]
    scope: enum[session, day, week, all]

diagnose_error:
  description: "Diagnose a specific error with source-level analysis"
  parameters:
    error_message: string
    traceback: string?
```

### Proposal Tools (Trust: WORKSPACE)

```yaml
propose_improvement:
  description: "Create a self-improvement proposal"
  parameters:
    title: string
    description: string
    changes: array[FileChange]
    tests: array[TestCase]?

test_proposal:
  description: "Test a proposal in sandbox before applying"
  parameters:
    proposal_id: string

apply_proposal:
  description: "Apply a tested proposal (requires human approval)"
  parameters:
    proposal_id: string
    skip_tests: bool = false  # Dangerous, requires confirmation

create_pr:
  description: "Create GitHub PR for proposal"
  parameters:
    proposal_id: string
```

---

## Migration Plan

### Phase 1: Create `Self` Singleton (Week 1)

1. Create `sunwell/self/` package
2. Move `SourceIntrospector` → `sunwell/self/source.py`
3. Implement `Self.get()` singleton with thread-safe locking
4. Update `MirrorHandler` to use `Self.get().source`

**Tests**:
- Existing mirror tests pass with new implementation
- **New**: `test_self_resolves_from_any_cwd()` — verify introspection works when cwd is not Sunwell root
- **New**: `test_self_thread_safe()` — verify concurrent `Self.get()` calls return same instance

### Phase 2: Rename `sunwell_root` → `workspace` (Week 1)

1. Rename parameter in `Naaru`, workers, tools
2. Update all callers
3. Remove legacy `sunwell_root` from mirror components

**Tests**: All existing tests pass

### Phase 3: Unify Analysis (Week 2)

1. Move `PatternAnalyzer`, `FailureAnalyzer` → `sunwell/self/analysis.py`
2. Connect to `Self.get().analysis`
3. Add execution event recording

**Tests**: Analysis tools work via Self singleton

### Phase 4: Safe Self-Coding (Week 2-3)

1. Implement `ProposalManager` with sandbox testing
2. Add test execution before apply
3. Implement rollback
4. Add PR creation workflow

**Tests**: Proposals can be created, tested, applied, rolled back

### Phase 5: Studio Integration (Week 3)

1. Add Tauri commands for Self access
2. Create "About Sunwell" panel in Studio
3. Add "Self-Debug" mode for error diagnosis
4. Add "Proposals" view for self-improvements

**Tests**: Studio can display Sunwell internals

---

## Storage Layout

```
~/.sunwell/
└── self/
    ├── analysis/
    │   ├── executions.jsonl    # Execution event log
    │   ├── failures.jsonl      # Failure records
    │   └── model_performance/  # Per-model stats
    │       ├── qwen3-30b.json
    │       └── gemma3-27b.json
    └── proposals/
        ├── index.json          # All proposals
        ├── prop_abc123/
        │   ├── proposal.json   # Proposal metadata
        │   ├── changes/        # File diffs
        │   ├── tests/          # Test files
        │   └── results/        # Test results
        └── prop_def456/
            └── ...
```

---

## Safety Considerations

### Self-Modification Risks

| Risk | Mitigation |
|------|------------|
| Breaking changes | Mandatory tests before apply |
| Infinite loops | Proposal rate limiting |
| Security bypass | Changes to `safety.py` require human review |
| Data loss | Git commits + rollback support |
| Runaway costs | Model call budgets in proposals |

### Thread-Safety Considerations (Python 3.14t)

| Component | Thread-Safety | Notes |
|-----------|---------------|-------|
| `Self.get()` | ✅ Safe | Double-checked locking with `threading.Lock` |
| `Self.reset()` | ✅ Safe | Acquires lock before clearing |
| `@cached_property` | ⚠️ Race possible | Multiple threads may compute same property once; result is immutable so safe after first access |
| `AnalysisKnowledge` writes | 🔒 Needs lock | File writes to `executions.jsonl` need internal locking |
| `ProposalManager` | 🔒 Needs lock | Proposal creation/modification needs internal locking |

**Design decision**: Component-level locking inside `AnalysisKnowledge` and `ProposalManager` rather than coarse-grained locking in `Self`. This allows concurrent reads while serializing writes.

### Trust Escalation

Self-coding requires WORKSPACE trust. Additional safeguards:

1. **Test gate**: Proposals must pass tests before apply (default)
2. **Review gate**: `create_pr` for human review before merge
3. **Blocklist**: Certain files require human approval:
   - `sunwell/self/` (meta-circular protection)
   - `sunwell/tools/types.py` (trust levels)
   - `sunwell/mirror/safety.py` (safety checks)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Self-introspection works in Studio | 100% |
| "Explain X" produces useful output | >80% user satisfaction |
| Self-diagnosis finds root cause | >70% accuracy |
| Proposals pass tests before apply | 100% |
| Rollback success rate | 100% |

---

## Future Extensions

### Self-Documentation

Sunwell generates its own documentation:

```python
# Automatically keep docs in sync with code
Self.get().docs.regenerate("docs/reference/tools.md")
```

### Self-Benchmarking

Sunwell runs benchmarks on itself:

```python
# "Am I getting slower?"
Self.get().benchmark.compare_to_baseline()
```

### Self-Teaching

Sunwell learns from its mistakes:

```python
# Extract lessons from failures
Self.get().analysis.extract_learnings() → Simulacrum
```

---

## Appendix: Existing Implementation Audit

### What Exists (in `sunwell/mirror/`)

| File | Status | Notes |
|------|--------|-------|
| `introspection.py` | ✅ Works | Fixed to auto-resolve source |
| `analysis.py` | ✅ Works | Pattern/failure analysis |
| `proposals.py` | ⚠️ Partial | No sandbox testing |
| `handler.py` | ⚠️ Needs update | Uses passed path |
| `safety.py` | ✅ Works | Diff validation |
| `tools.py` | ✅ Works | Tool definitions |
| `model_tracker.py` | ✅ Works | Performance tracking |
| `router.py` | ✅ Works | Model selection |

### What's Missing

1. **Sandbox testing** for proposals
2. **PR creation** workflow
3. **Semantic search** across source
4. **Explanation generation** with citations
5. **Studio integration** for self-knowledge
6. **Global singleton** pattern

---

## References

- RFC-015: Mirror Neurons (original, never documented)
- RFC-083: Naaru Unification (workspace handling)
- RFC-084: Simulacrum v2 (memory integration)
- `sunwell/mirror/` (existing implementation)
