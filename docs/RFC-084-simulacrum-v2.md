# RFC-084: Simulacrum v2 — Unified Memory Architecture

**Status**: Implemented  
**Author**: Sunwell Team  
**Date**: 2026-01-21  
**Supersedes**: RFC-013 (Hierarchical Memory), RFC-014 (Multi-Topology Memory)  
**Related**: RFC-083 (Naaru Unification)

---

## Summary

Sunwell's memory system is split across two competing abstractions (`Simulacrum` and `SimulacrumStore`), with several features designed but never wired:

- **ConceptGraph** (knowledge hubs) — empty, never populated
- **COLD tier** — never auto-demoted
- **Summaries** — never generated (no summarizer configured)
- **Focus/weighting** — only in legacy `Simulacrum`, not `SimulacrumStore`
- **Topology extraction** — requires manual `ingest_chunks()` call

This RFC proposes a clean unification with no shims or wrappers.

---

## Goals

1. **Single source of truth**: One `Simulacrum` class across Python, Rust, and Svelte
2. **Wire everything**: Auto-topology, auto-summarization, auto-cold-demotion
3. **Delete legacy**: Remove `Simulacrum` (core/core.py), keep only `SimulacrumStore`
4. **Consistent storage format**: Same `.sunwell/memory/` structure everywhere
5. **Studio-native**: Rust reads/writes the same format Python does

---

## Current Architecture Problems

### Problem 1: Two Competing Classes

```
Simulacrum (core/core.py)           SimulacrumStore (core/store.py)
├── WorkingMemory                   ├── ConversationDAG
├── LongTermMemory                  ├── ChunkManager (hierarchical)
├── EpisodicMemory                  ├── UnifiedMemoryStore (topology)
├── SemanticMemory                  ├── IntelligenceExtractor
├── ProceduralMemory                └── Embeddings
└── Focus (weighting)
```

**Result**: Neither is complete. `Simulacrum` has Focus but no hierarchical chunking. `SimulacrumStore` has chunking but no Focus.

### Problem 2: Unwired Features

| Feature | Implementation | Wired? |
|---------|---------------|--------|
| HOT → WARM demotion | `_maybe_demote_hot_chunks()` | ✅ Auto |
| WARM → COLD demotion | `demote_to_cold()` | ❌ Never called |
| Summaries | `Summarizer` protocol | ❌ No default |
| Fact extraction | `Summarizer.extract_facts()` | ❌ No default |
| ConceptGraph | `TopologyExtractor` | ❌ Needs manual call |
| Focus weighting | `Focus` class | ❌ Only in legacy |

### Problem 3: Rust/Svelte Divergence

**Rust** (`memory.rs`):
- Reads `.sunwell/memory/` and `.sunwell/intelligence/` directly
- Has its own type definitions (`MemoryStats`, `Learning`, `Decision`)
- Parses JSONL files manually

**Svelte** (`MemoryView.svelte`, `MemoryGraph.svelte`):
- Receives types from Rust via Tauri commands
- `MemoryGraph` expects `Concept[]` but ConceptGraph is empty
- `MemoryView` shows stats but can't show actual chunk hierarchy

---

## Proposed Architecture

### Single Unified Class

```python
@dataclass
class Simulacrum:
    """Unified memory architecture — the only memory class.
    
    Subsumes: SimulacrumStore, legacy Simulacrum, SimulacrumManager routing
    """
    
    base_path: Path
    """Storage root: .sunwell/memory/{name}/"""
    
    name: str
    """Unique identifier for this memory context."""
    
    # === Core Memory ===
    dag: ConversationDAG
    """Primary turn storage with branching and learnings."""
    
    chunks: ChunkManager
    """Hierarchical compression: HOT → WARM → COLD."""
    
    graph: ConceptGraph
    """Relationship topology: ELABORATES, CONTRADICTS, DEPENDS_ON."""
    
    # === Focus Mechanism ===
    focus: Focus
    """Weighted topic tracking for relevance scoring."""
    
    # === Extractors (auto-wired) ===
    summarizer: Summarizer | None = None
    """Generates summaries and extracts facts. Default: HeuristicSummarizer."""
    
    topology_extractor: TopologyExtractor | None = None
    """Extracts relationships between chunks. Default: HeuristicExtractor."""
    
    embedder: EmbeddingProtocol | None = None
    """Generates embeddings for semantic search."""
```

### Delete These Files

```
# Legacy Simulacrum (replaced by unified class)
src/sunwell/simulacrum/core/core.py
src/sunwell/simulacrum/core/memory.py  # WorkingMemory, LongTermMemory, etc.

# SimulacrumStore (merged into Simulacrum)
# Keep the file but rename class

# Duplicate context assembly
src/sunwell/simulacrum/context/unified.py  # Merge into Simulacrum.assemble()
```

### Unified Storage Format

```
.sunwell/memory/{name}/
├── meta.json              # Name, created_at, models_used, focus_topics
├── dag.json               # Turns, learnings, branches
├── chunks/
│   ├── hot/               # Last 2 micro-chunks (full JSON)
│   ├── warm/              # CTF-encoded with summaries
│   └── cold/              # Summaries only, archive refs
├── graph.json             # ConceptGraph edges
├── embeddings.bin         # FAISS index (optional)
└── intelligence/          # Decisions, failures, dead_ends
    ├── decisions.jsonl
    ├── failures.jsonl
    └── dead_ends.jsonl
```

---

## Implementation Plan

### Phase 1: Wire Missing Features (Python)

**1.1 Auto-Summarization**

```python
# Add default summarizer in ChunkConfig
summarization_strategy: Literal["llm", "heuristic", "local"] = "heuristic"

# HeuristicSummarizer (no LLM needed)
class HeuristicSummarizer(Summarizer):
    """Extracts key sentences using TF-IDF scoring."""
    
    def summarize_turns(self, turns: Sequence[Turn]) -> str:
        # Extract sentences with highest information density
        sentences = [s for t in turns for s in t.content.split('. ')]
        scored = [(self._score(s), s) for s in sentences]
        top_3 = sorted(scored, reverse=True)[:3]
        return '. '.join(s for _, s in top_3)
    
    def extract_facts(self, turns: Sequence[Turn]) -> list[str]:
        # Pattern matching for "X is Y", "We use X", etc.
        patterns = [
            r"(?:my name is|I am|I'm) (\w+)",
            r"(?:we use|using|with) ([\w\s]+)",
            r"(?:the \w+ is) ([\w\s]+)",
        ]
        return self._match_patterns(turns, patterns)
```

**1.2 Auto-Topology Extraction**

Wire topology extraction into `add_turn()`:

```python
async def add_turn(self, turn: Turn) -> str:
    turn_id = await super().add_turn(turn)
    
    # Auto-extract topology every N turns
    if self._turn_count % 10 == 0:
        await self._extract_topology_batch()
    
    return turn_id

async def _extract_topology_batch(self):
    """Extract relationships from recent chunks."""
    recent = self.chunks.get_recent(limit=5)
    
    for chunk in recent:
        if chunk.id in self._topology_extracted:
            continue
        
        edges = self.topology_extractor.extract_heuristic_relationships(
            source_id=chunk.id,
            source_text=chunk.summary or self._turns_to_text(chunk.turns),
            candidate_ids=[c.id for c in recent if c.id != chunk.id],
            candidate_texts=[c.summary for c in recent if c.id != chunk.id],
        )
        
        for edge in edges:
            self.graph.add_edge(edge)
        
        self._topology_extracted.add(chunk.id)
```

**1.3 Auto-Cold Demotion**

Wire cold demotion into tier management:

```python
def _maybe_demote_warm_chunks(self) -> None:
    """Demote old warm chunks to cold tier."""
    warm_chunks = self._get_warm_chunks()
    
    # By age: older than config threshold
    now = time.time()
    for chunk in warm_chunks:
        age_days = (now - chunk.timestamp_end) / 86400
        if age_days > self.config.warm_retention_days:
            self.demote_to_cold(chunk.id)
    
    # By count: keep only N warm chunks
    warm_chunks.sort(key=lambda c: c.turn_range[0])
    while len(warm_chunks) > self.config.max_warm_chunks:
        oldest = warm_chunks.pop(0)
        self.demote_to_cold(oldest.id)
```

**1.4 Focus Porting**

Move Focus from legacy `Simulacrum` to unified class:

```python
async def add_turn(self, turn: Turn) -> str:
    turn_id = await super().add_turn(turn)
    
    # Update focus based on content
    self.focus.update_from_query(turn.content)
    
    return turn_id

def get_context_for_prompt(self, query: str, max_tokens: int) -> str:
    # Use focus to weight chunk relevance
    focus_boost = self.focus.get_relevance_boost(query)
    
    # Semantic search with focus weighting
    relevant = await self.chunks.get_relevant_chunks_weighted(
        query,
        focus_weights=self.focus.topics,
        limit=5,
    )
    
    return self._format_context(relevant)
```

### Phase 2: Rust Alignment

**2.1 Shared Schema**

Create a JSON Schema that both Python and Rust validate against:

```json
// schemas/simulacrum.schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "definitions": {
    "Chunk": {
      "type": "object",
      "required": ["id", "chunk_type", "turn_range", "token_count"],
      "properties": {
        "id": { "type": "string" },
        "chunk_type": { "enum": ["micro", "mini", "macro"] },
        "turn_range": {
          "type": "array",
          "items": { "type": "integer" },
          "minItems": 2,
          "maxItems": 2
        },
        "summary": { "type": "string" },
        "themes": { "type": "array", "items": { "type": "string" } },
        "key_facts": { "type": "array", "items": { "type": "string" } },
        "token_count": { "type": "integer" },
        "embedding": { "type": "array", "items": { "type": "number" } }
      }
    },
    "ConceptEdge": {
      "type": "object",
      "required": ["source_id", "target_id", "relation"],
      "properties": {
        "source_id": { "type": "string" },
        "target_id": { "type": "string" },
        "relation": { 
          "enum": ["elaborates", "contradicts", "depends_on", "relates_to", "supersedes"] 
        },
        "confidence": { "type": "number" },
        "evidence": { "type": "string" }
      }
    }
  }
}
```

**2.2 Rust Implementation**

Rewrite `memory.rs` to read the unified format:

```rust
// studio/src-tauri/src/memory.rs

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Chunk {
    pub id: String,
    pub chunk_type: ChunkType,
    pub turn_range: (u32, u32),
    pub summary: Option<String>,
    pub themes: Vec<String>,
    pub key_facts: Vec<String>,
    pub token_count: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ChunkType {
    Micro,
    Mini,
    Macro,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConceptEdge {
    pub source_id: String,
    pub target_id: String,
    pub relation: RelationType,
    pub confidence: f32,
    pub evidence: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RelationType {
    Elaborates,
    Contradicts,
    DependsOn,
    RelatesTo,
    Supersedes,
}

/// Read ConceptGraph from disk
#[tauri::command]
pub async fn get_concept_graph(path: String) -> Result<Vec<ConceptEdge>, String> {
    let graph_path = PathBuf::from(&path).join(".sunwell/memory/graph.json");
    
    if !graph_path.exists() {
        return Ok(Vec::new());
    }
    
    let content = std::fs::read_to_string(&graph_path)
        .map_err(|e| e.to_string())?;
    
    let graph: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| e.to_string())?;
    
    let edges = graph.get("edges")
        .and_then(|e| e.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| serde_json::from_value(v.clone()).ok())
                .collect()
        })
        .unwrap_or_default();
    
    Ok(edges)
}

/// Get chunk hierarchy for visualization
#[tauri::command]
pub async fn get_chunk_hierarchy(path: String) -> Result<ChunkHierarchy, String> {
    let chunks_path = PathBuf::from(&path).join(".sunwell/memory/chunks");
    
    let mut hierarchy = ChunkHierarchy::default();
    
    // Read each tier
    for tier in ["hot", "warm", "cold"] {
        let tier_path = chunks_path.join(tier);
        if tier_path.exists() {
            if let Ok(entries) = std::fs::read_dir(&tier_path) {
                for entry in entries.filter_map(|e| e.ok()) {
                    let path = entry.path();
                    if path.extension().map_or(false, |e| e == "json") {
                        if let Ok(content) = std::fs::read_to_string(&path) {
                            if let Ok(chunk) = serde_json::from_str::<Chunk>(&content) {
                                match tier {
                                    "hot" => hierarchy.hot.push(chunk),
                                    "warm" => hierarchy.warm.push(chunk),
                                    "cold" => hierarchy.cold.push(chunk),
                                    _ => {}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    Ok(hierarchy)
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChunkHierarchy {
    pub hot: Vec<Chunk>,
    pub warm: Vec<Chunk>,
    pub cold: Vec<Chunk>,
}
```

### Phase 3: Svelte Updates

**3.1 MemoryGraph — Wire to ConceptGraph**

```svelte
<!-- MemoryGraph.svelte — visualize actual ConceptGraph -->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { ConceptEdge } from '$lib/types';
  
  interface Props {
    projectPath: string;
  }
  
  let { projectPath }: Props = $props();
  
  let edges: ConceptEdge[] = $state([]);
  let nodes: Map<string, ConceptNode> = $state(new Map());
  
  // Load graph on mount
  $effect(() => {
    loadGraph();
  });
  
  async function loadGraph() {
    try {
      edges = await invoke('get_concept_graph', { path: projectPath });
      
      // Extract unique nodes from edges
      const nodeSet = new Set<string>();
      for (const edge of edges) {
        nodeSet.add(edge.sourceId);
        nodeSet.add(edge.targetId);
      }
      
      // Position nodes using force-directed layout
      nodes = layoutNodes(Array.from(nodeSet), edges);
    } catch (e) {
      console.warn('Failed to load concept graph:', e);
    }
  }
  
  // Color by relation type
  const RELATION_COLORS = {
    elaborates: '#60a5fa',   // blue
    contradicts: '#ef4444',  // red
    dependsOn: '#34d399',    // green
    relatesTo: '#a78bfa',    // purple
    supersedes: '#fbbf24',   // amber
  };
</script>

<svg viewBox="0 0 200 150" class="concept-graph">
  <!-- Edges -->
  {#each edges as edge (edge.sourceId + '-' + edge.targetId)}
    {@const source = nodes.get(edge.sourceId)}
    {@const target = nodes.get(edge.targetId)}
    {#if source && target}
      <line
        x1={source.x}
        y1={source.y}
        x2={target.x}
        y2={target.y}
        stroke={RELATION_COLORS[edge.relation] ?? 'var(--border-color)'}
        stroke-width={edge.confidence * 2}
        opacity={0.6}
      />
    {/if}
  {/each}
  
  <!-- Nodes -->
  {#each Array.from(nodes.values()) as node (node.id)}
    <circle
      cx={node.x}
      cy={node.y}
      r="6"
      fill="var(--accent)"
    >
      <title>{node.id}</title>
    </circle>
  {/each}
  
  <!-- Empty state -->
  {#if edges.length === 0}
    <text x="100" y="75" text-anchor="middle" class="empty-text">
      No relationships yet
    </text>
  {/if}
</svg>
```

**3.2 New ChunkViewer Component**

```svelte
<!-- ChunkViewer.svelte — visualize chunk hierarchy -->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { ChunkHierarchy, Chunk } from '$lib/types';
  
  interface Props {
    projectPath: string;
  }
  
  let { projectPath }: Props = $props();
  
  let hierarchy: ChunkHierarchy = $state({ hot: [], warm: [], cold: [] });
  let selectedChunk: Chunk | null = $state(null);
  
  $effect(() => {
    loadChunks();
  });
  
  async function loadChunks() {
    try {
      hierarchy = await invoke('get_chunk_hierarchy', { path: projectPath });
    } catch (e) {
      console.warn('Failed to load chunks:', e);
    }
  }
</script>

<div class="chunk-viewer">
  <div class="tier tier-hot">
    <h4>HOT ({hierarchy.hot.length})</h4>
    <div class="chunk-list">
      {#each hierarchy.hot as chunk (chunk.id)}
        <button 
          class="chunk-card"
          class:selected={selectedChunk?.id === chunk.id}
          onclick={() => selectedChunk = chunk}
        >
          <span class="turn-range">
            T{chunk.turnRange[0]}–{chunk.turnRange[1]}
          </span>
          <span class="token-count">{chunk.tokenCount} tok</span>
        </button>
      {/each}
    </div>
  </div>
  
  <div class="tier tier-warm">
    <h4>WARM ({hierarchy.warm.length})</h4>
    <div class="chunk-list">
      {#each hierarchy.warm as chunk (chunk.id)}
        <button 
          class="chunk-card"
          class:selected={selectedChunk?.id === chunk.id}
          onclick={() => selectedChunk = chunk}
        >
          <span class="turn-range">
            T{chunk.turnRange[0]}–{chunk.turnRange[1]}
          </span>
          {#if chunk.summary}
            <span class="summary">{chunk.summary.slice(0, 50)}...</span>
          {/if}
        </button>
      {/each}
    </div>
  </div>
  
  <div class="tier tier-cold">
    <h4>COLD ({hierarchy.cold.length})</h4>
    <div class="chunk-list">
      {#each hierarchy.cold as chunk (chunk.id)}
        <button 
          class="chunk-card"
          class:selected={selectedChunk?.id === chunk.id}
          onclick={() => selectedChunk = chunk}
        >
          <span class="turn-range">
            T{chunk.turnRange[0]}–{chunk.turnRange[1]}
          </span>
          {#if chunk.themes?.length > 0}
            <span class="themes">
              {chunk.themes.slice(0, 3).join(', ')}
            </span>
          {/if}
        </button>
      {/each}
    </div>
  </div>
</div>

<!-- Detail panel for selected chunk -->
{#if selectedChunk}
  <aside class="chunk-detail">
    <h4>Chunk {selectedChunk.id.slice(0, 12)}...</h4>
    <dl>
      <dt>Type</dt>
      <dd>{selectedChunk.chunkType}</dd>
      
      <dt>Turns</dt>
      <dd>{selectedChunk.turnRange[0]}–{selectedChunk.turnRange[1]}</dd>
      
      <dt>Tokens</dt>
      <dd>{selectedChunk.tokenCount}</dd>
      
      {#if selectedChunk.summary}
        <dt>Summary</dt>
        <dd class="summary">{selectedChunk.summary}</dd>
      {/if}
      
      {#if selectedChunk.keyFacts?.length > 0}
        <dt>Key Facts</dt>
        <dd>
          <ul>
            {#each selectedChunk.keyFacts as fact}
              <li>{fact}</li>
            {/each}
          </ul>
        </dd>
      {/if}
      
      {#if selectedChunk.themes?.length > 0}
        <dt>Themes</dt>
        <dd>{selectedChunk.themes.join(', ')}</dd>
      {/if}
    </dl>
  </aside>
{/if}
```

---

## Migration Path

### Step 1: Feature Flag

```python
# config.py
@dataclass
class SimulacrumConfig:
    # Feature flags for gradual rollout
    auto_summarize: bool = True
    auto_topology: bool = True
    auto_cold_demotion: bool = True
    enable_focus: bool = True
    
    # Use new unified class
    use_simulacrum_v2: bool = False  # Flip to True when ready
```

### Step 2: Dual-Write Period

During migration, write to both old and new formats:

```python
async def add_turn(self, turn: Turn) -> str:
    turn_id = await self._add_turn_v2(turn)
    
    # Also write legacy format for backward compat
    if self.config.dual_write:
        self._write_legacy_format(turn)
    
    return turn_id
```

### Step 3: Delete Legacy

Once Studio is updated:

```bash
# Delete legacy files
rm src/sunwell/simulacrum/core/core.py
rm src/sunwell/simulacrum/core/memory.py

# Rename SimulacrumStore → Simulacrum
mv src/sunwell/simulacrum/core/store.py src/sunwell/simulacrum/core/simulacrum.py
```

---

## File Changes Summary

### Python

| File | Action |
|------|--------|
| `simulacrum/core/core.py` | DELETE (merge into store.py) |
| `simulacrum/core/memory.py` | DELETE (unused memory types) |
| `simulacrum/core/store.py` | RENAME to `simulacrum.py`, add Focus |
| `simulacrum/hierarchical/chunk_manager.py` | ADD auto-cold demotion |
| `simulacrum/hierarchical/summarizer.py` | ADD HeuristicSummarizer |
| `simulacrum/topology/topology_base.py` | WIRE auto-extraction |

### Rust

| File | Action |
|------|--------|
| `studio/src-tauri/src/memory.rs` | REWRITE for new format |
| `studio/src-tauri/src/main.rs` | ADD new commands |

### Svelte

| File | Action |
|------|--------|
| `studio/src/components/MemoryGraph.svelte` | WIRE to ConceptGraph |
| `studio/src/components/ChunkViewer.svelte` | NEW component |
| `studio/src/lib/types.ts` | ADD Chunk, ConceptEdge types |

---

## Success Metrics

1. **All features wired**: ConceptGraph populated, cold tier used, summaries generated
2. **Single class**: Only `Simulacrum` exists, no `SimulacrumStore`
3. **Studio parity**: MemoryGraph shows real relationships
4. **Benchmark**: Fact recall at 100% (already achieved with semantic search fix)
5. **Storage efficiency**: Cold tier reduces disk usage by 60%+

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing sessions | Dual-write period, migration script |
| Heuristic summarizer quality | Allow LLM fallback in config |
| Topology extraction noise | Confidence threshold filtering |
| Rust/Python format divergence | JSON Schema validation |

---

## Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1: Wire Python | 3 days | Auto-topology, auto-summary, auto-cold |
| 2: Rust alignment | 2 days | New commands, schema validation |
| 3: Svelte updates | 2 days | ChunkViewer, MemoryGraph wiring |
| 4: Migration | 1 day | Dual-write, legacy deletion |
| 5: Testing | 2 days | Integration tests, benchmarks |

**Total**: ~10 days

---

## Appendix: HeuristicSummarizer Implementation

```python
"""Heuristic-based summarization (no LLM required)."""

import re
from collections import Counter
from dataclasses import dataclass

from sunwell.simulacrum.hierarchical.summarizer import Summarizer
from sunwell.simulacrum.core.turn import Turn


@dataclass
class HeuristicSummarizer(Summarizer):
    """Extract summaries using TF-IDF-like scoring."""
    
    max_summary_sentences: int = 3
    min_sentence_length: int = 20
    
    async def summarize_turns(self, turns: tuple[Turn, ...]) -> str:
        """Extract most informative sentences."""
        text = ' '.join(t.content for t in turns)
        sentences = self._split_sentences(text)
        
        if not sentences:
            return ""
        
        # Score sentences by term frequency
        word_freq = Counter(w.lower() for s in sentences for w in s.split())
        total_words = sum(word_freq.values())
        
        scored = []
        for s in sentences:
            if len(s) < self.min_sentence_length:
                continue
            words = s.lower().split()
            score = sum(word_freq[w] / total_words for w in words) / len(words)
            scored.append((score, s))
        
        scored.sort(reverse=True)
        top = [s for _, s in scored[:self.max_summary_sentences]]
        
        return '. '.join(top) + '.'
    
    async def extract_facts(self, turns: tuple[Turn, ...]) -> list[str]:
        """Extract factual statements using patterns."""
        text = ' '.join(t.content for t in turns)
        
        patterns = [
            r"(?:my name is|I am|I'm) ([\w\s]+)",
            r"(?:we use|using|we're using) ([\w\s]+)",
            r"(?:the \w+ is) ([\w\s]+)",
            r"(?:it has|there are|there is) ([\w\s]+)",
            r"(\w+ (?:equals?|is|are|was|were) [\w\s]+)",
        ]
        
        facts = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                fact = match.group(0).strip()
                if len(fact) > 10 and len(fact) < 100:
                    facts.append(fact)
        
        # Deduplicate
        return list(set(facts))
    
    async def generate_executive_summary(self, summaries: list[str]) -> str:
        """Combine mini-chunk summaries into macro summary."""
        combined = ' '.join(summaries)
        sentences = self._split_sentences(combined)
        
        # Take first sentence from each + most unique
        result = []
        seen_words = set()
        
        for s in sentences[:len(summaries)]:
            words = set(s.lower().split())
            new_words = words - seen_words
            if len(new_words) > len(words) * 0.3:  # >30% new info
                result.append(s)
                seen_words.update(words)
        
        return '. '.join(result[:5]) + '.'
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
```

---

## Appendix: HeuristicTopologyExtractor Implementation

```python
"""Heuristic-based topology extraction (no LLM required)."""

import re
from dataclasses import dataclass

from sunwell.simulacrum.topology.topology_base import ConceptEdge, RelationType


@dataclass
class HeuristicTopologyExtractor:
    """Extract relationships using pattern matching."""
    
    def extract_heuristic_relationships(
        self,
        source_id: str,
        source_text: str,
        candidate_ids: list[str],
        candidate_texts: list[str],
    ) -> list[ConceptEdge]:
        """Identify relationships using lexical overlap and patterns."""
        edges = []
        source_words = set(source_text.lower().split())
        
        for cid, ctext in zip(candidate_ids, candidate_texts, strict=True):
            candidate_words = set(ctext.lower().split())
            
            # Jaccard similarity for RELATES_TO
            overlap = len(source_words & candidate_words)
            union = len(source_words | candidate_words)
            similarity = overlap / union if union > 0 else 0
            
            if similarity > 0.3:
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.RELATES_TO,
                    confidence=similarity,
                ))
            
            # Pattern matching for specific relations
            if self._is_elaboration(source_text, ctext):
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.ELABORATES,
                    confidence=0.7,
                ))
            
            if self._is_contradiction(source_text, ctext):
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.CONTRADICTS,
                    confidence=0.8,
                ))
        
        return edges
    
    def _is_elaboration(self, source: str, target: str) -> bool:
        """Check if source elaborates on target."""
        # Elaboration: source mentions target topic + adds detail
        patterns = [
            r"(?:specifically|in particular|for example)",
            r"(?:this means|in other words|that is)",
            r"(?:to clarify|more precisely)",
        ]
        return any(re.search(p, source, re.I) for p in patterns)
    
    def _is_contradiction(self, source: str, target: str) -> bool:
        """Check if source contradicts target."""
        patterns = [
            r"(?:actually|however|but|instead)",
            r"(?:not|never|don't|doesn't|won't)",
            r"(?:wrong|incorrect|false|mistake)",
        ]
        return any(re.search(p, source, re.I) for p in patterns)
```
