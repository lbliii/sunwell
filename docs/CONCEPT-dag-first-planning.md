# Concept: DAG-First Planning Interface

**Status**: Exploration  
**Created**: 2026-01-20  

---

## The Problem with Columns

Every planning tool copies Trello's 1996 Kanban board:

```
┌────────────┬────────────┬────────────┬────────────┐
│   TODO     │  DOING     │   REVIEW   │    DONE    │
├────────────┼────────────┼────────────┼────────────┤
│    □       │     □      │      □     │     ✓      │
│    □       │            │            │     ✓      │
│    □       │            │            │            │
└────────────┴────────────┴────────────┴────────────┘
```

**What's wrong:**
- No dependencies visible (why is X blocked?)
- No parallelization insight (what can run together?)
- No flow understanding (what unlocks when Y completes?)
- Status is binary (column), not continuous (progress)
- Manual movement (drag cards between columns)

**Reality**: Work is a graph, not a list of lists.

---

## The DAG-First Approach

What if the dependency graph WAS the interface?

```
                          ┌─────────────────────────────────────────────────────┐
                          │                                                     │
                          │                  YOUR WORK                          │
                          │                                                     │
                          │         ┌─────────┐                                 │
                          │         │  USER   │ ✓                               │
                          │         │  MODEL  │                                 │
                          │         └────┬────┘                                 │
                          │              │                                      │
                          │     ┌────────┼────────┬────────┐                    │
                          │     │        │        │        │                    │
                          │     ▼        ▼        ▼        ▼                    │
                          │ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐            │
                          │ │ POST  │ │ AUTH  │ │COMMENT│ │ TESTS │            │
                          │ │ MODEL │ │SYSTEM │ │ MODEL │ │       │            │
                          │ │███░░░ │ │██████ │ │  ✓    │ │ ready │            │
                          │ └───┬───┘ └───┬───┘ └───────┘ └───────┘            │
                          │     │         │                                     │
                          │     ▼         ▼                                     │
                          │ ┌───────┐ ┌───────┐                                 │
                          │ │ POST  │ │ RATE  │                                 │
                          │ │ CRUD  │ │LIMIT  │                                 │
                          │ │blocked│ │blocked│                                 │
                          │ └───────┘ └───────┘                                 │
                          │                                                     │
                          └─────────────────────────────────────────────────────┘
```

---

## Key Innovations

### 1. Status is Visual Position + State

No columns. A node's position shows its place in the flow:
- **Top** = Foundation (no dependencies)
- **Middle** = In the flow (has deps and dependents)
- **Bottom** = Leaves (nothing depends on this)

A node's visual state shows progress:
- `✓` = Complete (faded, but still shows edges)
- `███░░░` = In progress (animated pulse)
- `ready` = Dependencies met, can start
- `blocked` = Waiting on upstream

### 2. Edges Are First-Class

Click an edge to see:
- What artifact flows between nodes
- Whether it's a hard dependency or soft
- The "contract" (interface) being fulfilled

```
           ┌─────────┐
           │  AUTH   │
           │ SYSTEM  │
           └────┬────┘
                │
           UserProtocol  ← Click to see interface
                │
                ▼
           ┌─────────┐
           │  RATE   │
           │ LIMITER │
           └─────────┘
```

### 3. Parallel Groups Are Swim Lanes

Tasks that can run concurrently appear horizontally:

```
        Phase: Contracts          Phase: Implementation        Phase: Integration
       ──────────────────        ─────────────────────        ──────────────────
       
       ┌───────┐ ┌───────┐       ┌───────┐ ┌───────┐         ┌───────┐
       │User   │ │Auth   │   →   │User   │ │Auth   │    →    │E2E    │
       │Proto  │ │Proto  │       │Impl   │ │Impl   │         │Tests  │
       └───────┘ └───────┘       └───────┘ └───────┘         └───────┘
```

### 4. Interactive Manipulation

**Add dependency**: Drag from one node to another
**Remove dependency**: Click edge, press delete
**Add task**: Double-click empty space
**Execute**: Click node → "▶ Run this"

### 5. Live Execution Overlay

When Sunwell is working, the DAG animates:

```
       ┌─────────┐
       │  USER   │ ✓ done
       │  MODEL  │
       └────┬────┘
            │
            ▼
       ┌─────────┐
       │  AUTH   │ ████████░░ 80%  ← pulsing
       │ SYSTEM  │ "Generating JWT helpers..."
       └────┬────┘
            │
            ▼
       ┌─────────┐
       │  RATE   │ ░░░░░░░░░░ waiting
       │ LIMITER │
       └─────────┘
```

---

## Layouts

### Layout 1: Top-Down (Default)

Flow from top (foundations) to bottom (leaves):

```
           ┌─────┐
           │  A  │
           └──┬──┘
         ┌────┴────┐
         ▼         ▼
      ┌─────┐   ┌─────┐
      │  B  │   │  C  │
      └──┬──┘   └──┬──┘
         └────┬────┘
              ▼
           ┌─────┐
           │  D  │
           └─────┘
```

### Layout 2: Left-to-Right (Timeline-ish)

Flow from left (start) to right (end):

```
    ┌─────┐      ┌─────┐      ┌─────┐
    │  A  │ ──→  │  B  │ ──→  │  D  │
    └─────┘      └─────┘      └─────┘
                    │
                    ▼
                 ┌─────┐
                 │  C  │
                 └─────┘
```

### Layout 3: Radial (For Large Graphs)

Central nodes, dependencies radiate outward:

```
                    C
                   /
              B ← A → D
                   \
                    E
```

### Layout 4: Force-Directed (Organic)

Nodes find natural positions based on connections:

```
          B ─── A ─── C
               / \
              D   E
```

---

## Interactions

### Hover: Show Impact

Hover over a node to see what it affects:

```
       ┌─────────┐                    ┌─────────┐
       │  AUTH   │   hover →          │  AUTH   │ ← highlighted
       │ SYSTEM  │                    │ SYSTEM  │
       └────┬────┘                    └────┬────┘
            │                              │ highlighted
            ▼                              ▼
       ┌─────────┐                    ╔═════════╗
       │  RATE   │                    ║  RATE   ║ ← "would unblock"
       │ LIMITER │                    ║ LIMITER ║
       └─────────┘                    ╚═════════╝
```

### Click: Show Details

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   AUTH SYSTEM                                      [▶ Execute]  │
│   ─────────────────────────────────────────────────────────────│
│                                                                 │
│   Implement JWT-based authentication with refresh tokens        │
│                                                                 │
│   Status: In Progress (80%)                                     │
│   Effort: Medium                                                │
│   Source: 🤖 AI-discovered from TODO in routes.py:45            │
│                                                                 │
│   Dependencies:                                                 │
│   └─ ✓ User Model                                               │
│                                                                 │
│   Blocks:                                                       │
│   ├─ □ Rate Limiter                                             │
│   └─ □ API Gateway                                              │
│                                                                 │
│   Subtasks:                                                     │
│   ├─ ✓ Create auth/jwt.py                                       │
│   ├─ ✓ Implement token generation                               │
│   ├─ ███░ Add refresh token logic                               │
│   └─ □ Write tests                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Drag: Add Dependency

Drag from node A to node B:

```
Before:                          After:
   A       B                        A
                                    │
                                    ▼
                                    B
```

Sunwell asks: "What does B need from A?"
- Auto-detect from code analysis
- Or user specifies: "B needs UserModel from A"

### Right-Click: Context Menu

```
┌────────────────────────────┐
│ ▶ Execute this task        │
│ ⏸ Pause execution          │
│ ─────────────────────────  │
│ ➕ Add dependency          │
│ ➖ Remove from graph       │
│ 📋 Copy as Markdown        │
│ ─────────────────────────  │
│ 🔍 View in code            │
│ 📊 Show execution history  │
└────────────────────────────┘
```

---

## Smart Features

### 1. Critical Path Highlighting

Show the longest path to completion:

```
       ┌─────────┐
       │    A    │ ← critical path
       └────┬────┘
       ┌────┴────┐
       ▼         ▼
   ┌───────┐ ┌───────┐
   │   B   │ │   C   │ ← critical
   │ ready │ │ ready │
   └───┬───┘ └───────┘
       │
       ▼
   ┌───────┐
   │   D   │ ← critical
   │blocked│
   └───────┘
   
   Critical path: A → B → D (3 steps)
   C can run in parallel with B
```

### 2. "What If" Mode

Toggle a task complete to see what unblocks:

```
   "What if AUTH completes?"
   
   → RATE LIMITER: would become ready
   → API GATEWAY: would become ready
   → 2 tasks unblocked
   → Estimated time saved: 2 hours
```

### 3. Bottleneck Detection

Highlight nodes that block many others:

```
       ┌─────────┐
       │  AUTH   │ ⚠️ BOTTLENECK: blocks 5 tasks
       │ SYSTEM  │
       └────┬────┘
     ┌──────┼──────┬──────┬──────┐
     ▼      ▼      ▼      ▼      ▼
    ...    ...    ...    ...    ...
```

### 4. Suggested Parallelization

AI notices you could parallelize:

```
   💡 These tasks have no shared dependencies:
   
   ┌───────┐   ┌───────┐   ┌───────┐
   │ Tests │   │ Docs  │   │ CI    │
   └───────┘   └───────┘   └───────┘
   
   [Run all in parallel]
```

### 5. Progress Rollup

Parent goals show aggregate progress of children:

```
       ┌─────────────────┐
       │   FORUM APP     │ 45% ████████░░░░░░░░░░
       │   (meta-goal)   │
       └────────┬────────┘
          ┌─────┼─────┬─────┐
          ▼     ▼     ▼     ▼
        ┌───┐ ┌───┐ ┌───┐ ┌───┐
        │ ✓ │ │80%│ │20%│ │ 0%│
        └───┘ └───┘ └───┘ └───┘
```

---

## Comparison to Traditional Tools

| Feature | Trello/Jira | Linear | Sunwell DAG |
|---------|-------------|--------|-------------|
| Dependency visibility | ❌ None | ⚠️ Basic links | ✅ First-class edges |
| Parallel work insight | ❌ Manual | ❌ Manual | ✅ Automatic swim lanes |
| Bottleneck detection | ❌ No | ❌ No | ✅ Visual highlighting |
| Progress propagation | ❌ Manual | ❌ Manual | ✅ Automatic rollup |
| "What if" analysis | ❌ No | ❌ No | ✅ Interactive |
| Live execution view | ❌ No | ❌ No | ✅ Animated |
| AI task generation | ❌ No | ❌ No | ✅ Native |

---

## Technical Approach

### Rendering Library Options

| Library | Pros | Cons |
|---------|------|------|
| **D3.js** | Full control, powerful | Complex, large |
| **Cytoscape.js** | Graph-specific, good layouts | Medium learning curve |
| **Mermaid.js** | Already integrated! | Limited interactivity |
| **ReactFlow/SvelteFlow** | Modern, interactive | React/Svelte-specific |
| **Dagre** | Great DAG layouts | Just layout, no rendering |
| **ELK.js** | Eclipse Layout Kernel | Industrial-strength layouts |

**Recommended**: Use **Dagre** for layout + **Svelte** for rendering
- Dagre computes optimal node positions
- Svelte renders as SVG with full interactivity
- Clean separation of layout vs. rendering

### Data Flow

```
Backlog (Python)
     │
     ▼ JSON via Rust command
┌─────────────────────────────────────────────────────────────────┐
│   Svelte Store: planningGraph                                   │
│   ─────────────────────────────────────────────────────────────│
│   {                                                             │
│     nodes: [                                                    │
│       { id: "auth", title: "Auth System", status: "progress",   │
│         progress: 0.8, x: 100, y: 200 },                        │
│       ...                                                       │
│     ],                                                          │
│     edges: [                                                    │
│       { source: "user", target: "auth", artifact: "UserModel" },│
│       ...                                                       │
│     ]                                                           │
│   }                                                             │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼ Dagre layout
┌─────────────────────────────────────────────────────────────────┐
│   Positioned nodes with x, y coordinates                        │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼ SVG render
┌─────────────────────────────────────────────────────────────────┐
│   <svg>                                                         │
│     <g class="edges">                                           │
│       <path d="M100,200 C150,300 200,300 250,400" />           │
│     </g>                                                        │
│     <g class="nodes">                                           │
│       <foreignObject x="80" y="180">                           │
│         <DagNode {...node} />                                   │
│       </foreignObject>                                          │
│     </g>                                                        │
│   </svg>                                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Component Structure

```
studio/src/
├── components/
│   └── dag/
│       ├── DagCanvas.svelte      # Main SVG container
│       ├── DagNode.svelte        # Single node (foreignObject)
│       ├── DagEdge.svelte        # Single edge (path)
│       ├── DagMinimap.svelte     # Overview for large graphs
│       ├── DagControls.svelte    # Zoom, pan, layout buttons
│       ├── DagTooltip.svelte     # Hover info
│       └── layout.ts             # Dagre layout logic
├── stores/
│   └── dag.ts                    # Graph state, selection, hover
```

---

## Why This Could Win

1. **Honest representation** — Work IS a graph. Show the graph.

2. **AI-native** — Sunwell generates DAGs naturally. This is its native view.

3. **Differentiating** — No one else does this well. Linear's closest, but still column-based.

4. **Insightful** — Bottlenecks, critical path, parallelization visible at a glance.

5. **Interactive** — Not just visualization, but manipulation.

6. **Live** — Watch your work execute in real-time.

---

## Mockup: Full Interface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  forum-app › DAG                              [Fit] [+] [−]  🔄  ⚙️  ─ □ x │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                     │   │
│   │                          ┌─────────┐                                │   │
│   │                          │  USER   │                                │   │
│   │                          │  MODEL  │ ✓                              │   │
│   │                          └────┬────┘                                │   │
│   │                               │                                     │   │
│   │              ┌────────────────┼────────────────┐                    │   │
│   │              │                │                │                    │   │
│   │              ▼                ▼                ▼                    │   │
│   │         ┌─────────┐     ┌─────────┐     ┌─────────┐                │   │
│   │         │  POST   │     │  AUTH   │     │ COMMENT │                │   │
│   │         │  MODEL  │     │ SYSTEM  │     │  MODEL  │ ✓              │   │
│   │         │ ████░░░ │     │████████ │     └─────────┘                │   │
│   │         └────┬────┘     └────┬────┘                                │   │
│   │              │               │                                      │   │
│   │              ▼               ▼                                      │   │
│   │         ┌─────────┐     ┌─────────┐                                │   │
│   │         │  POST   │     │  RATE   │                                │   │
│   │         │  CRUD   │     │ LIMITER │                                │   │
│   │         │ blocked │     │ blocked │                                │   │
│   │         └─────────┘     └─────────┘                                │   │
│   │                                                                     │   │
│   │   ┌───────┐                                           ┌─────────┐  │   │
│   │   │minimap│                                           │ legend  │  │   │
│   │   └───────┘                                           └─────────┘  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ─────────────────────────────────────────────────────────────────────────│
│   AUTH SYSTEM                              80% ████████████████░░░░         │
│   Generating refresh token logic...                              [▶ Focus] │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Prototype**: Build a static DAG renderer with Dagre + Svelte
2. **Wire data**: Connect to existing `Backlog.to_mermaid()` / goals
3. **Add interactivity**: Click, hover, drag
4. **Execution overlay**: Show live progress
5. **Polish**: Animations, transitions, keyboard shortcuts

---

*This could be Sunwell's signature feature—the thing people screenshot and share.*
