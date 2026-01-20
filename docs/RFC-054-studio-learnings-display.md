# RFC-054: Studio Learnings Display & Memory Visualization

**Status**: Draft  
**Author**: Human + Claude  
**Created**: 2026-01-19  
**Related**: RFC-053 (Studio Agent Bridge), RFC-040 (Project Checkpointing)

---

## Summary

Add real-time learnings display and an ambient memory visualization to Sunwell Studio. As the agent works, users see what it's learning and a small graph representing its growing understanding of the project.

---

## Motivation

### Problem

Currently, Studio shows task progress but not *what* the agent is learning. The agent's internal state (Simulacrum memories, discovered patterns, inferred context) is invisible to the user.

### User Value

1. **Entertainment** — Watching the agent "think" is engaging
2. **Trust** — Seeing learnings builds confidence in agent decisions
3. **Debugging** — If something goes wrong, learnings hint at why
4. **Personality** — Makes Sunwell feel alive, not just a progress bar

### Design Principles

- **Ambient, not intrusive** — Supplements progress, doesn't compete
- **Real-time** — Learnings appear as discovered
- **Minimal** — Small footprint, CSS-only visualization
- **Delightful** — Subtle animations make it feel organic

---

## Design

### Visual Mockup

```
┌─────────────────────────────────────────────────┐
│  ← forum-app                                    │
│                                                 │
│  > build a forum with posts and comments        │
│  ─────────────────────────────────────────────  │
│                                                 │
│  ⚡ Building                                    │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ ● Creating database models              │   │
│  │ ○ Implementing API routes               │   │
│  │ ○ Adding authentication                 │   │
│  │ ○ Writing tests                         │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  3/7 tasks · 1m 23s                            │
│                                                 │
│  ─────────────────────────────────────────────  │
│                                                 │
│  💡 Learnings                      ┌─────────┐ │
│                                    │  ○   ○  │ │
│  • Detected Flask web framework    │   ╲ ╱   │ │
│  • Using SQLAlchemy for ORM        │    ○    │ │
│  • pytest available for testing    │   ╱ ╲   │ │
│  • SQLite database detected        │  ○   ○  │ │
│                                    └─────────┘ │
│                                      memory    │
└─────────────────────────────────────────────────┘
```

### Component Architecture

```
Project.svelte
├── Progress (existing)
├── LearningsPanel.svelte (new)
│   ├── Learnings list
│   └── MemoryGraph.svelte (new)
│       └── SVG node visualization
```

### Data Model

```typescript
// Extended AgentState
interface AgentState {
  // ... existing fields
  learnings: string[];      // Raw learning facts (exists)
  concepts: Concept[];      // Extracted for graph (new)
}

interface Concept {
  id: string;
  label: string;           // Short name: "Flask", "SQLAlchemy"
  category: ConceptCategory;
  timestamp: number;
}

type ConceptCategory = 
  | 'framework'    // Flask, FastAPI, Django
  | 'database'     // SQLite, PostgreSQL, SQLAlchemy
  | 'testing'      // pytest, unittest
  | 'pattern'      // MVC, REST, GraphQL
  | 'tool'         // Docker, Git, npm
  | 'language';    // Python, TypeScript
```

### Concept Extraction

Parse learnings for keywords to create graph nodes:

```typescript
const CONCEPT_PATTERNS: Record<ConceptCategory, RegExp[]> = {
  framework: [/flask/i, /fastapi/i, /django/i, /express/i, /svelte/i],
  database: [/sqlite/i, /postgres/i, /mysql/i, /sqlalchemy/i, /prisma/i],
  testing: [/pytest/i, /jest/i, /unittest/i, /vitest/i],
  pattern: [/rest/i, /graphql/i, /mvc/i, /api/i],
  tool: [/docker/i, /git/i, /npm/i, /pip/i],
  language: [/python/i, /typescript/i, /javascript/i, /rust/i],
};

function extractConcepts(learning: string): Concept[] {
  const concepts: Concept[] = [];
  for (const [category, patterns] of Object.entries(CONCEPT_PATTERNS)) {
    for (const pattern of patterns) {
      const match = learning.match(pattern);
      if (match) {
        concepts.push({
          id: match[0].toLowerCase(),
          label: match[0],
          category: category as ConceptCategory,
          timestamp: Date.now(),
        });
      }
    }
  }
  return concepts;
}
```

### Memory Graph Visualization

**Approach**: Fixed-position CSS/SVG graph (not physics-based)

```
Layout (max 8 nodes):

    ○───○
   ╱│   │╲
  ○ │   │ ○
   ╲│   │╱
    ○───○
     ╲ ╱
      ○
```

**Node positioning**: Predefined positions in a rough circle/cluster:

```typescript
const NODE_POSITIONS = [
  { x: 60, y: 20 },   // top center
  { x: 100, y: 35 },  // top right
  { x: 110, y: 60 },  // right
  { x: 90, y: 85 },   // bottom right
  { x: 50, y: 90 },   // bottom center
  { x: 20, y: 70 },   // bottom left
  { x: 10, y: 40 },   // left
  { x: 40, y: 50 },   // center
];
```

**Edges**: Connect nodes by category proximity or recency.

**Animation**:
- New nodes: scale from 0 + pulse
- New edges: fade in
- Overflow: oldest nodes fade out when > 8

---

## Implementation

### Phase 1: Learnings Panel (Simple)

1. Create `LearningsPanel.svelte`
2. Wire into `Project.svelte` working state
3. Show learnings as bullet list with fade-in animation

**Files**:
- `src/components/LearningsPanel.svelte` (create)
- `src/routes/Project.svelte` (modify)

### Phase 2: Memory Graph

1. Create `MemoryGraph.svelte` with SVG
2. Add concept extraction to `agent.ts`
3. Connect concepts to graph nodes
4. Add animations

**Files**:
- `src/components/MemoryGraph.svelte` (create)
- `src/stores/agent.ts` (modify)
- `src/lib/types.ts` (modify)

### Phase 3: Polish

1. Category-based node colors
2. Edge animations
3. Collapse/expand toggle
4. Persist across done state

---

## Component Specifications

### LearningsPanel.svelte

```svelte
<script lang="ts">
  export let learnings: string[] = [];
  export let concepts: Concept[] = [];
</script>

<div class="learnings-panel">
  <div class="learnings-list">
    <h4>💡 Learnings</h4>
    <ul>
      {#each learnings as learning, i}
        <li class="learning-item" style="animation-delay: {i * 50}ms">
          {learning}
        </li>
      {/each}
    </ul>
  </div>
  
  <div class="memory-graph">
    <MemoryGraph {concepts} />
    <span class="graph-label">memory</span>
  </div>
</div>
```

### MemoryGraph.svelte

```svelte
<script lang="ts">
  import type { Concept } from '$lib/types';
  
  export let concepts: Concept[] = [];
  
  const NODE_POSITIONS = [
    { x: 60, y: 20 }, { x: 100, y: 35 }, { x: 110, y: 60 },
    { x: 90, y: 85 }, { x: 50, y: 90 }, { x: 20, y: 70 },
    { x: 10, y: 40 }, { x: 40, y: 50 },
  ];
  
  const CATEGORY_COLORS: Record<string, string> = {
    framework: '#60a5fa',  // blue
    database: '#34d399',   // green
    testing: '#fbbf24',    // yellow
    pattern: '#a78bfa',    // purple
    tool: '#f472b6',       // pink
    language: '#fb923c',   // orange
  };
  
  $: visibleConcepts = concepts.slice(-8);
  $: nodes = visibleConcepts.map((c, i) => ({
    ...c,
    ...NODE_POSITIONS[i],
    color: CATEGORY_COLORS[c.category] ?? '#888',
  }));
</script>

<svg viewBox="0 0 120 100" class="memory-graph">
  <!-- Edges -->
  {#each nodes as node, i}
    {#if i > 0}
      <line
        x1={nodes[i-1].x}
        y1={nodes[i-1].y}
        x2={node.x}
        y2={node.y}
        class="edge"
      />
    {/if}
  {/each}
  
  <!-- Nodes -->
  {#each nodes as node (node.id)}
    <circle
      cx={node.x}
      cy={node.y}
      r="6"
      fill={node.color}
      class="node"
    >
      <title>{node.label}</title>
    </circle>
  {/each}
</svg>
```

---

## Styling

```css
/* LearningsPanel */
.learnings-panel {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-4);
  border-top: 1px solid var(--border-color);
  margin-top: var(--space-4);
}

.learnings-list {
  flex: 1;
}

.learnings-list h4 {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.learnings-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 120px;
  overflow-y: auto;
}

.learning-item {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  padding: var(--space-1) 0;
  animation: slideIn 0.3s ease-out forwards;
  opacity: 0;
}

.learning-item::before {
  content: '•';
  margin-right: var(--space-2);
  color: var(--accent);
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* MemoryGraph */
.memory-graph {
  width: 120px;
  height: 100px;
}

.memory-graph .edge {
  stroke: var(--border-color);
  stroke-width: 1;
  opacity: 0.4;
}

.memory-graph .node {
  opacity: 0.8;
  animation: nodeAppear 0.4s ease-out;
}

@keyframes nodeAppear {
  0% {
    r: 0;
    opacity: 0;
  }
  50% {
    r: 8;
  }
  100% {
    r: 6;
    opacity: 0.8;
  }
}

.graph-label {
  display: block;
  text-align: center;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}
```

---

## Event Integration

### Current Events (RFC-053)

```
memory_learning { fact: string }  →  learnings[]
```

### Derived Processing

```typescript
// In agent.ts handleAgentEvent
case 'memory_learning': {
  const fact = data.fact as string;
  if (fact) {
    const newConcepts = extractConcepts(fact);
    agentState.update(s => ({
      ...s,
      learnings: [...s.learnings, fact],
      concepts: deduplicateConcepts([...s.concepts, ...newConcepts]),
    }));
  }
  break;
}
```

---

## Future Enhancements

### v1.1: Richer Graph
- Physics-based layout (optional)
- Hover tooltips with full context
- Click to filter tasks by concept

### v1.2: Persistent Memory
- Show learnings from previous sessions
- "What Sunwell remembers about this project"
- Cross-project knowledge graph

### v1.3: Memory Categories
- Separate tabs: Facts / Patterns / Warnings
- Filterable by category
- Search within learnings

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Too distracting | Keep small, muted colors, below fold |
| No learnings emitted | Show placeholder "Analyzing..." |
| Too many learnings | Cap at 20, scroll older ones |
| Performance | SVG is lightweight, cap nodes at 8 |

---

## Success Criteria

- [ ] Learnings appear in real-time during agent execution
- [ ] Memory graph grows as concepts are discovered
- [ ] Animations are smooth and delightful
- [ ] Does not interfere with task progress visibility
- [ ] Works in both running and done states

---

## References

- RFC-053: Studio Agent Bridge (event streaming)
- RFC-040: Project Checkpointing (state persistence)
- Simulacrum memory types (Working, Long-term, Episodic, Semantic, Procedural)
