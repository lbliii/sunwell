# Sunwell Memory Enhancement Implementation Progress

## Overview

Implementation of Hindsight-inspired memory enhancements to improve retrieval accuracy, entity understanding, and knowledge synthesis in Sunwell's memory system.

**Status**: **Phases 1 & 2 COMPLETED** (50% complete)

---

## ✅ Phase 1: Foundation (COMPLETED)

### 1.1 Entity Extraction System ✅

**Implementation**: `src/sunwell/memory/core/entities/`

**Features**:
- **Dual-mode extraction**: Pattern-based (default, zero-cost) and LLM-based (opt-in)
- **Entity types**: FILE, TECH, CONCEPT, PERSON, SYMBOL
- **Pattern-based extractor**: Regex patterns for files, technologies, code symbols, concepts
- **Entity resolution**: Levenshtein distance + user-defined aliases
- **SQLite storage**: Entity persistence with co-occurrence tracking
- **Integration**: Automatic extraction in learning workflow

**Files Created**:
- `entities/types.py`: Entity, EntityMention, EntityType, ExtractionResult
- `entities/extractor.py`: PatternEntityExtractor, LLMEntityExtractor
- `entities/resolver.py`: EntityResolver with DEFAULT_ALIASES
- `entities/store.py`: EntityStore (SQLite-backed)
- `entities/integration.py`: EntityIntegration for workflow

**Database Schema**: Extended LearningCache with:
```sql
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    aliases TEXT,
    mention_count INTEGER DEFAULT 0
);

CREATE TABLE learning_entities (
    learning_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    PRIMARY KEY (learning_id, entity_id)
);
```

**Configuration**:
```yaml
memory:
  entity_extraction:
    enabled: true
    mode: pattern  # or "llm"
    user_aliases:
      react: ReactJS
      py: Python
```

---

### 1.2 Cross-Encoder Reranking ✅

**Implementation**: `src/sunwell/memory/core/reranking/`

**Features**:
- **Two-stage retrieval**: Hybrid search (3x candidates) → cross-encoder reranking
- **Model support**: ms-marco-MiniLM-L-6-v2 (80MB), ms-marco-TinyBERT-L-2-v2 (17MB)
- **LRU cache**: 1-hour TTL, ~95% hit rate expected
- **Graceful fallback**: Returns original ranking if model unavailable
- **Integration**: Optional reranking in PlanningRetriever

**Files Created**:
- `reranking/config.py`: RerankingConfig with model selection
- `reranking/cache.py`: RerankingCache with LRU eviction
- `reranking/cross_encoder.py`: CrossEncoderReranker

**Integration**:
- Modified `planning_retriever.py` to add optional reranking step
- Only runs if `config.enabled=true` and min_candidates met

**Configuration**:
```yaml
memory:
  cross_encoder_reranking:
    enabled: false  # Opt-in (requires sentence-transformers)
    model: ms-marco-MiniLM-L-6-v2
    cache_ttl_seconds: 3600
    batch_size: 8
```

**Expected Improvement**: 75% → 85%+ retrieval accuracy

---

## ✅ Phase 2: Graph Enhancement (COMPLETED)

### 2.1 Entity Graph in UnifiedMemoryStore ✅

**Implementation**: `src/sunwell/memory/simulacrum/topology/`

**Features**:
- **EntityNode**: Extends MemoryNode with entity-specific fields
- **New relation types**: MENTIONS, CO_OCCURS (bidirectional), ALIAS_OF
- **Entity graph builder**: Constructs graphs from learnings automatically
- **Co-occurrence tracking**: Weight-based edges for entity relationships

**Files Created**:
- `topology/entity_node.py`: EntityNode class
- `topology/entity_graph_builder.py`: EntityGraphBuilder

**Modified Files**:
- `topology/topology_base.py`: Added MENTIONS, CO_OCCURS, ALIAS_OF to RelationType
- Updated `is_bidirectional` property

**Graph Structure**:
```
Learning → MENTIONS → Entity
Entity ↔ CO_OCCURS ↔ Entity (weighted)
Alias → ALIAS_OF → Canonical Entity
```

**Configuration**:
```yaml
memory:
  entity_graph:
    enabled: true
    co_occurrence_threshold: 2
    max_cooccurrences_per_entity: 50
```

---

### 2.2 Entity-Aware Retrieval ✅

**Implementation**: Enhanced `planning_retriever.py`

**Features**:
- **Entity extraction from queries**: Identifies entities in goal descriptions
- **Entity overlap boosting**: +0.15 score per matching entity
- **Co-occurrence expansion**: BFS through entity graph (depth=2, decay=0.5)
- **Merged top-k results**: Combines direct matches and expanded candidates
- **Backward compatible**: Falls back to standard retrieval if no entity support

**New Methods**:
- `retrieve_with_entities()`: Main entity-aware retrieval method
- `_expand_via_cooccurrence()`: BFS expansion through entity graph

**Algorithm**:
1. Extract entities from goal
2. Perform hybrid search (vector + BM25)
3. Boost scores for entity overlap
4. Expand via co-occurrence graph (2 hops)
5. Optional cross-encoder reranking
6. Return top-k per category

**Configuration**:
```yaml
memory:
  entity_retrieval:
    enabled: true
    entity_boost: 0.15
    cooccurrence_depth: 2
    cooccurrence_decay: 0.5
```

---

## 🚧 Phase 3: Reflection System (NOT STARTED)

### 3.1 Reflection Operation
**Status**: Pending

**Goal**: Synthesize higher-order insights about constraint causality.

**Planned Implementation**:
- `memory/core/reflection/reflector.py`: Main engine
- `memory/core/reflection/patterns.py`: Pattern detection
- `memory/core/reflection/causality.py`: Constraint causality analysis
- `memory/core/reflection/types.py`: Reflection schemas

**Trigger Conditions**:
- Every 50 new learnings
- When constraint category reaches 10+ items
- Explicit user request: `sunwell reflect`

**LLM Prompt** (optimized for 3B-12B models):
```
Given these constraints:
{constraints}

1. What principle connects them?
2. Why do they exist? (causality)
3. Summarize in 2-3 sentences.

Output JSON: {"theme": "...", "causality": "...", "summary": "..."}
```

---

### 3.2 Mental Model Synthesis
**Status**: Pending

**Goal**: Build coherent mental models for token-efficient context injection.

**Planned Implementation**:
- MentalModel dataclass
- Integration with HarmonicPlanner for single-shot context
- Storage as special learnings (category="mental_model")

**Expected Improvement**: ~30% token savings vs individual learnings

---

## 🚧 Phase 4: Optimization (NOT STARTED)

### 4.1 BM25 Inverted Index
**Status**: Pending

**Goal**: Optimize BM25 from O(n) to O(log n).

**Planned Implementation**:
- Add `bm25_index` table to LearningCache
- `build_bm25_index()` method
- `bm25_query_fast()` using inverted index

**Performance Target**: <20ms for 10k learnings (vs current ~500ms)

---

### 4.2 Query Expansion
**Status**: Pending

**Goal**: Improve recall with synonym expansion.

**Planned Implementation**:
- `memory/core/retrieval/query_expansion.py`
- Built-in synonym map (no LLM required)
- User-defined synonyms in `.sunwell/config/synonyms.json`

---

### 4.3 Benchmarking Harness
**Status**: Pending

**Goal**: Track retrieval accuracy over time.

**Planned Implementation**:
- `memory/benchmarks/longmemeval.py`: LongMemEval adapter
- `memory/benchmarks/synthetic.py`: Synthetic scenarios
- `memory/benchmarks/metrics.py`: Accuracy, recall@5, latency

**Metrics**:
- Accuracy: Correct answer in top-1
- Recall@5: Correct answer in top-5
- Latency: p50, p95, p99 retrieval time
- Memory usage: Storage per learning

---

## 🚧 Remaining Tasks

### Task 10: Update Configuration Schema ✅ (COMPLETED)
- [x] Added all Phase 1 & 2 config options to `.sunwell/config.yaml`
- [ ] Add Phase 3 & 4 options (when implemented)

### Task 11: Write Comprehensive Tests
**Status**: Pending

**Required Tests**:
- Unit tests for entity extraction (pattern matching)
- Integration tests for entity-aware retrieval
- Synthetic tests for reflection triggers (when implemented)
- Performance tests for BM25 inverted index (when implemented)
- End-to-end pipeline test

### Task 12: Documentation and Migration Guide
**Status**: Pending

**Required Documentation**:
- Update README with new memory capabilities
- Architecture overview document
- Entity extraction patterns guide
- Configuration examples
- Migration guide for existing workspaces

---

## Expected Improvements

Based on Hindsight's LongMemEval results and similar systems:

| Metric | Current | Target (Phase 1-2) | Target (All Phases) | Status |
|--------|---------|-------------------|---------------------|--------|
| Retrieval accuracy | ~75%* | ~80% | ~85% | 🚧 In Progress |
| Entity-aware recall | N/A | 75%+ | 85%+ | ✅ Implemented |
| BM25 query latency | ~500ms | ~500ms | <20ms | 🚧 Pending |
| Token efficiency | Baseline | Baseline | -30% | 🚧 Pending |

*Estimated baseline (not currently benchmarked)

---

## Installation & Usage

### Prerequisites

For full functionality:
```bash
pip install sentence-transformers  # Optional, for cross-encoder reranking
```

### Enabling Features

Edit `.sunwell/config.yaml`:

```yaml
memory:
  # Enable entity extraction (zero-cost)
  entity_extraction:
    enabled: true
    mode: pattern

  # Enable cross-encoder reranking (requires sentence-transformers)
  cross_encoder_reranking:
    enabled: true  # Set to true to enable
    model: ms-marco-MiniLM-L-6-v2

  # Enable entity graph
  entity_graph:
    enabled: true

  # Enable entity-aware retrieval
  entity_retrieval:
    enabled: true
```

### Using Entity-Aware Retrieval

```python
from sunwell.memory.simulacrum.core.store import SimulacrumStore

store = SimulacrumStore(base_path=".sunwell/memory")

# Standard retrieval
planning_context = await store.retrieve_for_planning(
    goal="Implement authentication with JWT"
)

# Entity-aware retrieval (automatic if entities enabled in config)
# Will extract entities from goal, boost matching learnings,
# and expand via co-occurrence graph
```

---

## Architecture Decisions

### Why Pattern-Based Extraction First?
- **Zero cost**: No LLM required for most use cases
- **Fast**: Regex patterns are ~1000x faster than LLM calls
- **Reliable**: Deterministic, no hallucinations
- **Extensible**: LLM mode available for ambiguous cases

### Why Opt-In Reranking?
- **Expensive**: Cross-encoder inference is ~100x slower than vector similarity
- **Model dependency**: Requires sentence-transformers (~200MB download)
- **Diminishing returns**: Only ~10% accuracy improvement over hybrid search
- **Use case specific**: Most valuable for complex, ambiguous queries

### Why SQLite for Entity Storage?
- **ACID guarantees**: Consistent entity relationships
- **WAL mode**: Concurrent reads, single writer
- **No dependencies**: Built into Python
- **Performance**: Fast enough for <100k entities

---

## Backward Compatibility

All features are:
- **Opt-in via config flags**
- **Gracefully degrade** if dependencies unavailable
- **Non-breaking**: Existing workspaces work unchanged
- **No migration required**: Entities extracted on-demand

---

## Next Steps

To complete the implementation:

1. **Phase 3: Reflection System**
   - Implement reflection operation for constraint causality
   - Build mental model synthesis
   - Integrate with HarmonicPlanner

2. **Phase 4: Optimization**
   - Build BM25 inverted index
   - Implement query expansion
   - Create benchmarking harness

3. **Testing & Documentation**
   - Write comprehensive test suite
   - Create migration guide
   - Update README and architecture docs

---

## References

- **Hindsight Paper**: https://arxiv.org/abs/2410.01373
- **LongMemEval**: Evaluation framework for long-term memory
- **RFC-122**: Compound Learning (Sunwell planning context)
- **RFC-014**: Multi-Topology Memory (Sunwell architecture)
