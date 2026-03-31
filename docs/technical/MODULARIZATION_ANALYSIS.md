# Monolithic Files - Modularization Analysis

Analysis of large Python files that need modularization, prioritized by size and complexity.

## Summary

| File | Lines | Methods | Classes | Priority | Status |
|------|-------|---------|---------|----------|--------|
| `simulacrum/core/store.py` | 1546 | 60 | 1 | 🔴 HIGH | Needs split |
| `cli/chat.py` | 1323 | 17+ | 1 | 🔴 HIGH | Needs split |
| `reasoning/reasoner.py` | 1321 | 48 | 1 | 🟡 MEDIUM | Consider split |
| `naaru/planners/harmonic.py` | 1309 | ? | ? | 🟡 MEDIUM | Review |
| `agent/event_schema.py` | 1284 | ? | ? | 🟢 LOW | Generated |
| `benchmark/runner.py` | 1246 | 22 | 1+ | 🟡 MEDIUM | Consider split |
| `agent/learning.py` | 1226 | 28 | 4 | 🟡 MEDIUM | Consider split |
| `naaru/planners/artifact.py` | 1224 | 23 | 1 | 🟡 MEDIUM | Review |
| `agent/loop.py` | 1160 | 13 | 1 | 🟢 LOW | OK |
| `agent/core.py` | 992 | 26 | 1 | 🟡 MEDIUM | Review |

---

## 🔴 HIGH PRIORITY

### 1. `simulacrum/core/store.py` (1546 lines, 60 methods)

**Current State**: Single massive `SimulacrumStore` class handling:
- Session management
- Tier management (HOT/WARM/COLD)
- Chunk management
- Memory retrieval
- Context assembly
- Multi-topology storage
- Intelligence extraction
- Planning context

**Modularization Plan**:

```
simulacrum/core/
├── store.py (200 lines) - Main facade, delegates to managers
├── session_manager.py ✅ (already extracted)
├── tier_manager.py ✅ (already extracted)
├── chunk_manager.py (extract from store)
├── retrieval/
│   ├── __init__.py
│   ├── semantic_retriever.py (embedding-based retrieval)
│   ├── topology_retriever.py (multi-topology retrieval)
│   └── context_assembler.py (token-budgeted assembly)
├── planning/
│   ├── __init__.py
│   └── context_builder.py (extract retrieve_for_planning logic)
└── intelligence/
    ├── __init__.py
    └── extractor_interface.py (intelligence extraction callbacks)
```

**Extraction Targets**:
- `_init_chunk_manager()` → `ChunkManager` class
- `retrieve_for_planning()` → `PlanningContextBuilder`
- `assemble_context()` → `ContextAssembler`
- `retrieve_semantic()` → `SemanticRetriever`
- Multi-topology retrieval → `TopologyRetriever`

**Benefits**:
- Testability: Each component can be tested independently
- Reusability: Retrieval strategies can be swapped
- Maintainability: Clear separation of concerns
- Performance: Easier to optimize individual components

---

### 2. `cli/chat.py` (1323 lines, 17+ functions)

**Current State**: Single file mixing:
- Project detection logic
- Context building (workspace, RAG, codebase indexing)
- CLI command handling
- Event rendering
- Checkpoint management
- RAG result formatting

**Modularization Plan**:

```
cli/
├── chat.py (300 lines) - Main command, orchestrates components
├── chat/
│   ├── __init__.py
│   ├── project_detector.py (project type/framework detection)
│   ├── context_builder.py (workspace context assembly)
│   ├── rag_provider.py (semantic retrieval integration)
│   ├── renderer.py (event/response rendering)
│   └── checkpoint_handler.py (checkpoint save/load)
└── helpers.py (shared utilities)
```

**Extraction Targets**:
- `_detect_project_type()` → `ProjectDetector.detect()`
- `_build_smart_workspace_context()` → `ContextBuilder.build()`
- `_build_codebase_index()` → `RAGProvider.get_context()`
- `_render_agent_event()` → `EventRenderer.render()`
- `_handle_checkpoint()` → `CheckpointHandler.save/load()`

**Benefits**:
- Reusability: Context building can be used by other CLI commands
- Testability: Each component can be unit tested
- Clarity: Main command file becomes orchestrator only

---

## 🟡 MEDIUM PRIORITY

### 3. `reasoning/reasoner.py` (1321 lines, 48 methods)

**Current State**: Single `Reasoner` class with:
- Multiple decision types (severity, recovery, approval, etc.)
- Context enrichment from multiple sources
- Prompt building for each decision type
- JSON parsing and validation
- Fast path vs full reasoning

**Modularization Plan**:

```
reasoning/
├── reasoner.py (200 lines) - Main facade
├── decisions/
│   ├── __init__.py
│   ├── severity.py (SeverityDecision)
│   ├── recovery.py (RecoveryDecision)
│   ├── approval.py (ApprovalDecision)
│   └── base.py (BaseDecision)
├── enrichment/
│   ├── __init__.py
│   ├── codebase_enricher.py
│   ├── cache_enricher.py
│   ├── project_enricher.py
│   └── artifact_enricher.py
└── prompts/
    ├── __init__.py
    ├── builder.py (PromptBuilder)
    └── templates.py (prompt templates)
```

**Extraction Targets**:
- Each `decide_*()` method → separate decision class
- Each `_enrich_*()` method → separate enricher
- Prompt building → `PromptBuilder` with strategy pattern

**Benefits**:
- Extensibility: Easy to add new decision types
- Testability: Each decision type can be tested independently
- Maintainability: Prompt templates separated from logic

---

### 4. `agent/learning.py` (1226 lines, 28 methods, 4 classes)

**Current State**: Multiple concerns:
- `Learning` dataclass (simple)
- `DeadEnd` dataclass (simple)
- `ToolPattern` class (tool sequence tracking)
- `LearningExtractor` class (extraction logic)
- `LearningStore` class (storage and retrieval)

**Modularization Plan**:

```
agent/learning/
├── __init__.py
├── types.py (Learning, DeadEnd dataclasses)
├── extractor.py (LearningExtractor)
├── store.py (LearningStore)
└── patterns.py (ToolPattern)
```

**Extraction Targets**:
- Already well-structured, just needs directory organization
- `LearningExtractor` could be split into:
  - `code_extractor.py` (extract_from_code)
  - `fix_extractor.py` (extract_from_fix)
  - `llm_extractor.py` (extract_with_llm)
  - `template_extractor.py` (extract_template, extract_heuristic)

**Benefits**:
- Clear separation: extraction vs storage
- Easier to add new extraction strategies

---

### 5. `benchmark/runner.py` (1246 lines, 22 methods)

**Current State**: Single file with:
- `PromptBuilder` class (multiple strategies)
- Benchmark execution logic
- Result collection and evaluation
- Report generation

**Modularization Plan**:

```
benchmark/
├── runner.py (300 lines) - Main orchestrator
├── prompts/
│   ├── __init__.py
│   ├── builder.py (PromptBuilder)
│   └── strategies.py (strategy implementations)
├── execution/
│   ├── __init__.py
│   └── executor.py (condition execution)
└── reporting/
    ├── __init__.py
    └── reporter.py (result formatting)
```

**Extraction Targets**:
- `PromptBuilder` → `prompts/builder.py`
- Execution logic → `execution/executor.py`
- Report generation → `reporting/reporter.py`

---

### 6. `naaru/planners/artifact.py` (1224 lines, 23 methods)

**Current State**: Single `ArtifactPlanner` class with:
- Discovery logic
- Dependency resolution
- Verification
- Graph building

**Modularization Plan**:

```
naaru/planners/artifact/
├── __init__.py
├── planner.py (main facade)
├── discovery.py (artifact discovery)
├── resolver.py (dependency resolution)
└── verifier.py (verification logic)
```

---

## 🟢 LOW PRIORITY / REVIEW

### 7. `agent/loop.py` (1160 lines, 13 methods)

**Status**: Well-structured single class. Methods are cohesive.
**Action**: Monitor, but not urgent. Consider extracting:
- `_retry_with_escalation()` → `retry/strategy.py`
- `_run_validation_gates()` → `validation/gates.py`

### 8. `agent/core.py` (992 lines, 26 methods)

**Status**: Main Agent orchestrator. Methods are cohesive.
**Action**: Review if it grows further. Consider extracting:
- Orientation logic → `orientation/`
- Signal extraction → `signals/` (already exists)

### 9. `agent/event_schema.py` (1284 lines)

**Status**: Likely generated code (event schema definitions)
**Action**: Verify if generated. If so, exclude from modularization.

---

## Implementation Strategy

### Phase 1: High Priority (Week 1-2)
1. ✅ Extract `SessionManager` from `store.py` (already done)
2. ✅ Extract `TierManager` from `store.py` (already done)
3. Extract retrieval logic from `store.py` → `retrieval/`
4. Extract context building from `store.py` → `planning/`
5. Extract project detection from `chat.py` → `chat/project_detector.py`
6. Extract context building from `chat.py` → `chat/context_builder.py`

### Phase 2: Medium Priority (Week 3-4)
1. Split `reasoner.py` by decision type
2. Organize `learning.py` into `learning/` directory
3. Split `benchmark/runner.py` by concern

### Phase 3: Review & Refine (Week 5)
1. Review extracted modules for cohesion
2. Add integration tests
3. Update documentation

---

## Principles

1. **Single Responsibility**: Each module should have one clear purpose
2. **Dependency Injection**: Managers should be injected, not created internally
3. **Interface Segregation**: Extract protocols/interfaces for testability
4. **Composition over Inheritance**: Prefer composition for flexibility
5. **Backwards Compatibility**: Maintain public API during extraction

---

## Testing Strategy

For each extraction:
1. Create unit tests for extracted module
2. Create integration tests for original facade
3. Ensure existing tests still pass
4. Add tests for new module boundaries

---

## Notes

- Files marked ✅ already have some extraction done (SessionManager, TierManager)
- Generated files (`event_schema.py`) should be excluded
- Focus on files > 1000 lines with multiple responsibilities
- Prioritize files with high method counts (> 20 methods)
