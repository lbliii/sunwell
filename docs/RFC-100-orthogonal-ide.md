# RFC-100: Orthogonal IDE — Mental Model-First Control Plane

**Status**: Evaluated (Landscape + Codebase Validated)  
**Author**: Lawrence Lane  
**Created**: 2026-01-22  
**Updated**: 2026-01-23 (added two-DAG architecture, State DAG scanning, user journeys, S-tier quality criteria)  
**Target Version**: v0.3+  
**Confidence**: 88% 🟢  
**Depends On**: RFC-097 (Studio UX), RFC-084 (Memory System), RFC-051 (Multi-Instance Coordination)  
**Evidence**: Studio implementation, parallel module, existing docs health scripts, user feedback, industry trajectory

---

## Cross-Stack Integration

This RFC touches **all three stacks**. Implementation requires coordinated changes:

### Python (Agent Backend)
| File | Change | Phase |
|------|--------|-------|
| `sunwell/analysis/state_dag.py` | **New**: State DAG builder from project scan | 0 |
| `sunwell/analysis/scanners/docs.py` | **New**: Docs-specific scanner (toctree, links) | 0 |
| `sunwell/analysis/scanners/code.py` | **New**: Code-specific scanner (imports, deps) | 0 |
| `sunwell/analysis/components.py` | New: Component detection from file structure | 1 |
| `sunwell/confidence/aggregation.py` | New: Confidence propagation logic | 2 |
| `sunwell/parallel/coordinator.py` | Add state export methods for UI | 4 |
| `sunwell/parallel/locks.py` | Add conflict events for UI notification | 4 |
| `sunwell/parallel/types.py` | Add `CoordinatorUIState` type | 4 |

### Rust (Tauri Bridge)
| File | Change | Phase |
|------|--------|-------|
| `studio/src-tauri/src/coordinator.rs` | **New**: Bridge to Python parallel module | 4 |
| `studio/src-tauri/src/main.rs` | Register coordinator commands | 4 |
| `studio/src-tauri/src/project.rs` | Add component detection commands | 1 |

### Svelte (Studio UI)
| File | Change | Phase |
|------|--------|-------|
| `studio/src/stores/coordinator.svelte.ts` | **New**: Multi-agent state store | 4 |
| `studio/src/components/dag/` | Extend for ATC view (reuse existing patterns) | 4 |
| `studio/src/components/project/` | Add interactive component graph | 1 |
| `studio/src/components/primitives/` | Reuse existing `DiffView.svelte`, `Chart.svelte` | 4 |

### Existing Assets to Leverage
| Asset | Location | Reuse For |
|-------|----------|-----------|
| DAG graph layout | `studio/src/stores/dag.svelte.ts` | ATC agent visualization |
| `DagNode.svelte` | `studio/src/components/dag/` | Worker status cards |
| `DagEdge.svelte` | `studio/src/components/dag/` | Dependency lines |
| `DiffView.svelte` | `studio/src/components/primitives/` | Conflict resolution |
| `Chart.svelte` | `studio/src/components/primitives/` | Confidence visualization |
| Confidence gradients | `studio/src/styles/variables.css` | `--confidence-high/med/low` tokens |

---

## Summary

Sunwell should evolve as an **orthogonal axis** to traditional IDEs—not better code editing, but a **mental model-first control plane** for directing autonomous agents.

**Core insight**: Developers don't want to troll through files, terminals, and bug reports. They want a mental model of their project they can reason about and a futuristic control panel where their AI assistant handles the details.

**The shift**:
- **Traditional IDE axis**: Human → Code (optimize keystrokes, autocomplete, refactoring)
- **Sunwell axis**: Human → Agent → Code (optimize goal articulation, supervision, review)

**Two-DAG Architecture**:
- **State DAG**: Scan existing project → show "what exists and its health" → click to give intent
- **Execution DAG**: Plan tasks → track progress → complete goal (current Sunwell behavior)

This enables both **greenfield** ("build me X") and **brownfield** ("here's my project, improve it") workflows. Since ~95% of real work is brownfield, State DAG unlocks Sunwell for the majority of developer tasks.

**S-tier Sunwell** achieves four things:
1. **The model is scannable** — understand existing projects at a glance (State DAG)
2. **The model is manipulable** — click to give intent, not just view
3. **Trust through transparency** — confidence gradients, provenance, proactive uncertainty
4. **Multi-session orchestration** — air traffic control for parallel agents

---

## Goals and Non-Goals

### Goals

1. **Model-first interaction** — Project mental model as primary interface, files as drill-down
2. **Intent-to-execution** — Express intent at model level, agent translates to artifacts
3. **Earned trust** — Systematic confidence visualization so users know when to verify
4. **Orchestration at scale** — Multiple agents, one control plane
5. **Seamless escape hatch** — When you need files, one click to your preferred editor

### Non-Goals

1. **Replacing editors** — Sunwell is control plane, not text editor
2. **Code execution environment** — Not a notebook or REPL
3. **Full IDE feature parity** — No syntax highlighting arms race, no debugger integration
4. **Forcing the paradigm** — Users can still work file-by-file if they prefer

---

## User Journeys

### Journey 1: Brownfield Docs Improvement (NEW capability)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  "I have a docs project. Show me what needs attention."                         │
│                                                                                 │
│  1. User runs: sunwell scan ~/my-docs                                           │
│     → Sunwell detects conf.py, auto-selects tech-writer.lens                    │
│     → Runs health probes (check_health.py, find_orphans.py, detect_drift.py)    │
│     → Builds State DAG                                                          │
│                                                                                 │
│  2. Studio opens with State DAG view:                                           │
│     ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│     │ index   │──▶│tutorials│──▶│reference│   │ orphans │                       │
│     │  🟢 95% │   │  🔴 45% │   │  🟡 72% │   │  ⚠️ 3   │                       │
│     └─────────┘   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                                 │
│  3. User clicks red node (tutorials/)                                           │
│     → Panel shows: "Drift detected. 3 stale refs. Last updated 24 days ago."    │
│     → Shows top issues: broken links, outdated code examples                    │
│                                                                                 │
│  4. User types intent: "Update this tutorial to match current API"              │
│     → Execution DAG spawns (same as greenfield)                                 │
│     → Agent reads source code, updates tutorial, validates                      │
│                                                                                 │
│  5. State DAG refreshes automatically                                           │
│     → tutorials/ node now shows 🟢 88%                                          │
│     → User moves to next problem area                                           │
│                                                                                 │
│  TIME: 5 minutes to understand project health, give targeted intent             │
│  VERSUS: 30+ minutes manually checking each file                                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Journey 2: Greenfield Build (existing capability, unchanged)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  "Build me a forum app with posts and comments"                                 │
│                                                                                 │
│  1. User gives goal in Studio or CLI                                            │
│     → No State DAG needed (nothing exists yet)                                  │
│                                                                                 │
│  2. Execution DAG created:                                                      │
│     ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│     │ Plan    │──▶│ Models  │──▶│ Views   │──▶│ Tests   │                       │
│     │ PENDING │   │ PENDING │   │ PENDING │   │ PENDING │                       │
│     └─────────┘   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                                 │
│  3. Agent executes tasks, user watches progress                                 │
│                                                                                 │
│  4. Done! Forum app created.                                                    │
│                                                                                 │
│  ✅ This flow is EXACTLY the same as current Sunwell                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Journey 3: Multi-Agent Orchestration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  "Run 3 agents in parallel on different parts of my codebase"                   │
│                                                                                 │
│  1. User gives 3 goals:                                                         │
│     - Agent 1: "Implement auth flow"                                            │
│     - Agent 2: "Write API tests"                                                │
│     - Agent 3: "Update docs for new endpoints"                                  │
│                                                                                 │
│  2. ATC View shows all agents:                                                  │
│     ┌─────────────────────────────────────────────────────────────┐             │
│     │  Agent 1: 🟢 Implementing auth      [=====>    ] 60%        │             │
│     │  Agent 2: 🟡 Writing tests          [==>       ] 25%        │             │
│     │  Agent 3: ⏸️  Waiting (needs auth types from Agent 1)       │             │
│     │                                                             │             │
│     │  ⚠️ Conflict: Agent 2 touched file Agent 1 needs            │             │
│     │  [View Diff] [Pause Agent 2] [Auto-resolve]                 │             │
│     └─────────────────────────────────────────────────────────────┘             │
│                                                                                 │
│  3. User clicks [View Diff]                                                     │
│     → DiffView shows conflicting changes                                        │
│     → User sees Agent 2 modified auth.py while Agent 1 was reading it           │
│                                                                                 │
│  4. User clicks [Pause Agent 2]                                                 │
│     → Agent 2 pauses, Agent 1 continues                                         │
│     → When Agent 1 finishes, Agent 2 auto-resumes                               │
│                                                                                 │
│  5. All agents complete, branches merged                                        │
│     → User never touched a terminal for coordination                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Journey 4: Trust Verification

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  "Why does it say AuthService is well-understood?"                              │
│                                                                                 │
│  1. User sees model node: "AuthService 🟢 92%"                                  │
│                                                                                 │
│  2. User clicks "Why?" / provenance link                                        │
│     → Panel shows confidence breakdown:                                         │
│       - 40% from code analysis (found tests, docstrings)                        │
│       - 30% from memory (previous successful edits)                             │
│       - 22% from recency (modified 2 days ago)                                  │
│                                                                                 │
│  3. User sees evidence trail:                                                   │
│     - "Found 12 unit tests covering 85% of functions"                           │
│     - "Agent successfully refactored this 3 times"                              │
│     - "No errors reported in last 5 sessions"                                   │
│                                                                                 │
│  4. User now trusts (or disputes) the confidence score                          │
│     → If wrong, user can correct: "Actually this is fragile"                    │
│     → System learns, adjusts future confidence                                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## S-Tier UI Quality

> **Reference**: See RFC-097 (Studio UX Elevation) for full quality rubric and component audit.

### Quality Rubric (from RFC-097)

All new components in this RFC must pass:

| Criterion | Requirement | Why It Matters |
|-----------|-------------|----------------|
| **Token Compliance** | Uses CSS variables, no hardcoded colors | Consistency, theming |
| **Visual Hierarchy** | Clear primary/secondary/tertiary levels | Scannable at a glance |
| **Interactions** | Hover/focus states, keyboard nav, loading states | Professional feel |
| **Motion** | Entrance animations, micro-interactions | Life, not static |
| **Ambient Effects** | Subtle pulse, sparkles for magical moments | Delight, not generic |

### S-Tier Reference Implementations

Use these existing components as templates:

| Component | Location | What Makes It S-Tier |
|-----------|----------|---------------------|
| `Home.svelte` | `studio/src/routes/Home.svelte` | Full token compliance, staggered animations, ambient motes |
| `Demo.svelte` | `studio/src/routes/Demo.svelte` | Split-view comparison, real-time streaming, progress states |
| `BriefingCard.svelte` | `studio/src/components/primitives/` | Confidence gradients, expandable detail, hover preview |

### New Components Quality Targets

| New Component | Must Have | Nice to Have |
|---------------|-----------|--------------|
| **State DAG View** | Health colors from tokens, smooth node transitions | Motes on healthy nodes |
| **ATC View** | Progress bars, conflict badges, pause/resume states | Worker avatars, activity sparklines |
| **Intent Dialog** | Auto-focus, keyboard submit, loading shimmer | Context-aware suggestions |
| **Provenance Panel** | Evidence links, confidence breakdown chart | Animated confidence meter |

### Anti-Patterns to Avoid

```yaml
avoid:
  - Hardcoded colors (use --ui-gold, --text-primary, etc.)
  - Static renders (add entrance animations)
  - Click-only (support keyboard navigation)
  - Loading spinners without context (use skeletons with shimmer)
  - Generic styling (maintain Holy Light aesthetic)
```

---

## Motivation

### The Cognitive Load Problem

```
Current developer workflow:
┌─────────────────────────────────────────────────────────────┐
│  Open 15 files                                              │
│  + grep through logs                                        │
│  + read stack traces                                        │
│  + cross-reference documentation                            │
│  + manually build mental model in head                      │
│  = THEN finally make a decision                             │
└─────────────────────────────────────────────────────────────┘

Proposed workflow:
┌─────────────────────────────────────────────────────────────┐
│  Look at project model (maintained by system)               │
│  → Express intent to model ("this service is too coupled")  │
│  → Agent translates to file changes                         │
│  → Model updates to reflect new state                       │
│  = Decision-making at the right abstraction level           │
└─────────────────────────────────────────────────────────────┘
```

### Why This Axis is Orthogonal

| Traditional IDE | Sunwell |
|-----------------|---------|
| File tree primary | Project model primary |
| Buffer-focused | Intent-focused |
| Debugging = stepping through code | Debugging = understanding agent reasoning |
| Optimize keystrokes | Optimize goal articulation |
| Human types code | Human reviews agent code |

These axes can coexist. Cursor moves toward agent assistance. Sunwell moves toward agent orchestration. The sweet spot: Sunwell as control plane that works alongside any editor.

### Why Now

| Signal | Evidence | Implication |
|--------|----------|-------------|
| Agent capability | Claude, GPT-4, Codex generations | Agents can now do real work |
| Studio foundation | Tabs, memory, DAG, events | Infrastructure exists |
| User feedback | "I don't want to read files" | Pull from real need |
| Market timing | Cursor/Copilot prove demand | Agent-assisted is mainstream |

---

## Competitive Landscape

> **Research date**: 2026-01-22

### Current Market Positions

| Competitor | Approach | Strengths | What They Don't Have |
|------------|----------|-----------|---------------------|
| **Cursor** | Shadow workspaces + LSP | Iteration safety, real-time linting, fast feedback | No persistent model, no confidence, no provenance |
| **Continue** | Tool handshake + MCP | Standardized tool protocol, editor-agnostic | File-centric, no orchestration visualization |
| **Devin** | Full autonomy | End-to-end execution | Black box, low trust, expensive |
| **Copilot Workspace** | Issue-to-PR | GitHub integration, familiar workflow | Limited scope, no multi-agent |

### Key Industry Patterns

**1. Shadow Workspace Pattern (Cursor)**

Cursor's insight: Agents need real development environments with LSP access (lints, go-to-definition) to write working code. They isolate agent iteration in a hidden background environment to avoid disrupting the user's main workspace. Key finding: "No minute-long delays anywhere" is a hard requirement.

**Implication for Sunwell**: Our model manipulation layer needs sub-second response. Latency budget: < 500ms for model updates.

**2. Standardized Context (`.agent` directory proposal)**

Industry is converging on standardized context delivery—a `.agent` directory containing PRDs, architecture docs, monitoring configs alongside code. This mirrors our model concept but without the visualization layer.

**Decision**: Consider `.agent` directory compatibility. Our model could be the visualization layer *on top* of this emerging standard rather than a proprietary replacement.

**3. 12-Factor Agents Framework**

Best practices from HumanLayer:
- Small, focused agents over monolithic ones (aligns with our multi-agent approach)
- Human-in-the-loop via explicit tool calls (aligns with our approval gates)
- Stateless reducers with owned context windows (aligns with our memory system)

### Where RFC-100 Differentiates

**The gap no one fills**: No competitor is doing "explorable project model with confidence gradients" at scale.

| Aspect | Cursor/Continue | RFC-100 (Sunwell) |
|--------|-----------------|-------------------|
| **Model** | Dynamic tool invocation | Persistent maintained model |
| **Trust** | Implicit (does it compile?) | Explicit (confidence + provenance) |
| **Mental model** | Invisible (in context window) | Visible (interactive visualization) |
| **Multi-agent** | Not supported | First-class ATC view |

**Our moat**: Trust through transparency. The "why does it say this?" provenance trace linked to evidence is genuinely absent from Cursor's shadow workspace and Continue's tool framework.

### Risk: Model Accuracy

Cursor gets model accuracy "for free" from LSP—compilers and linters do the work. Our model has to own accuracy ourselves. This is the hardest problem.

**Mitigation**: Start with heuristic-based component detection (directory structure) and evolve to agent-enhanced understanding. Don't promise AST-level accuracy initially.

---

## Design

### The Three Pillars

#### Pillar 1: Manipulable Model

**Current state**: Overview tab shows project type, confidence, pipeline, and detection signals. Memory tab shows learnings and decisions. Both are **viewable but not manipulable**—users can see status but cannot express intent to the model directly.

**Target state**: Interactive project model where you:
- See components/modules as clickable entities
- Click → give intent ("this is too complex")
- Drag → reorganize ("move this to that boundary")
- Agent responds with proposed changes

**Implementation layers**:

```
Layer 0: Static component visualization (exists partially in Overview)
Layer 1: Clickable components → show details, dependencies
Layer 2: Click → open intent dialog → agent acts
Layer 3: Drag-and-drop model manipulation → agent translates
Layer 4: Real-time model updates as agent works
```

**Key insight**: The model doesn't need to be a perfect AST-level representation. It needs to match the user's mental model—services, boundaries, data flows—at whatever granularity they think about the project.

#### Pillar 2: Trust Through Transparency

**Problem**: Users verify at file level because they don't trust the abstraction.

**Solution**: Make confidence a first-class visual language.

```
Confidence gradient (applied everywhere):
┌──────────────────────────────────────────────────────┐
│  🟢 90-100%  │  "I'm sure" — no drill-down needed    │
│  🟡 70-89%   │  "Likely right" — spot check          │
│  🟠 50-69%   │  "Uncertain" — review recommended     │
│  🔴 <50%     │  "I don't know" — human must verify   │
└──────────────────────────────────────────────────────┘
```

**Applied to**:
- Model components ("AuthService: 🟢 well-understood")
- Agent actions ("Refactored boundary: 🟡 review recommended")
- Memory items (already partially implemented)
- Health indicators ("Test coverage: 🟠 may have gaps")

**Provenance traces**: Every claim in the model links to evidence:
- "Why does it say this?" → shows source files, agent reasoning, confidence factors
- Builds trust over time as user learns when system is right

**Proactive uncertainty**: System surfaces "I'm not sure about X" before user asks.

#### Pillar 3: Multi-Session Orchestration

**Current state**: Backend supports parallel agents (RFC-051 `Coordinator`, `WorkerProcess`, `FileLockManager`), but no unified UI. Users must use CLI and can't see all agents at once.

**Target state**: Air traffic control.

```
Control Plane View:
┌─────────────────────────────────────────────────────────────┐
│  Project: my-saas-app                                       │
│                                                             │
│  Agent 1: 🟢 Implementing auth flow      [=====>    ] 60%   │
│  Agent 2: 🟡 Writing tests for API       [==>       ] 25%   │
│  Agent 3: ⏸️  Waiting (depends on Agent 1's auth types)     │
│                                                             │
│  ⚠️ Conflict detected: Agent 2 touched file Agent 1 needs   │
│  [Resolve at model level] [View diff] [Pause Agent 2]       │
└─────────────────────────────────────────────────────────────┘
```

**Capabilities**:
- Start multiple agents with different goals
- See all activity in unified view
- Detect conflicts before they become merge hell
- Resolve at model level ("Agent 2, wait for Agent 1")
- Never touch a terminal for coordination

---

### The Two-DAG Architecture

A critical insight: Sunwell needs **two types of DAGs** that serve different purposes but work together.

#### State DAG vs. Execution DAG

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STATE DAG — "What exists and its health"                                       │
│                                                                                 │
│  Created: When user scans existing project                                      │
│  Purpose: Understand current state before acting                                │
│  Nodes:   Artifacts that exist (files, modules, docs)                           │
│  Edges:   Relationships (imports, links, dependencies)                          │
│  Colors:  Health scores (🟢 healthy → 🔴 needs attention)                       │
│  Lifecycle: Persistent, updates after changes                                   │
│                                                                                 │
│  Example (docs project):                                                        │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                          │
│  │ index   │──▶│tutorials│──▶│reference│   │ orphans │                          │
│  │  🟢 95% │   │  🔴 45% │   │  🟡 72% │   │  ⚠️ 3   │                          │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                          │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  EXECUTION DAG — "What to do" (current Sunwell behavior)                        │
│                                                                                 │
│  Created: When user gives a goal                                                │
│  Purpose: Plan and track task execution                                         │
│  Nodes:   Tasks to complete                                                     │
│  Edges:   Dependencies ("do A before B")                                        │
│  Colors:  Status (pending → in-progress → complete)                             │
│  Lifecycle: Ephemeral, created per goal                                         │
│                                                                                 │
│  Example (greenfield or intent-triggered):                                      │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                          │
│  │ Plan    │──▶│ Build   │──▶│ Test    │──▶│ Deploy  │                          │
│  │   ✓     │   │   ✓     │   │ working │   │ pending │                          │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### How They Work Together

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  GREENFIELD: "Build me a forum app" (Execution DAG only)                        │
│                                                                                 │
│  User gives goal → Execution DAG created → Tasks complete → Done                │
│  [No State DAG needed — nothing exists yet]                                     │
│                                                                                 │
│  ✅ This is current Sunwell behavior — unchanged                                │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  BROWNFIELD: "Here's my existing project" (State DAG → Execution DAG)           │
│                                                                                 │
│  1. User: sunwell scan ~/my-docs                                                │
│  2. Sunwell builds State DAG (scans files, runs health probes)                  │
│  3. User sees project health in Studio                                          │
│  4. User clicks red node: "Fix this stale tutorial"                             │
│  5. Sunwell spawns Execution DAG for that intent                                │
│  6. Agent executes tasks                                                        │
│  7. State DAG refreshes — node turns green                                      │
│                                                                                 │
│  ✅ NEW capability — enables working with existing projects                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Lens-Driven Scanners

Each lens can define **scanners** for building State DAGs specific to its domain:

```yaml
# tech-writer.lens (scanner addition)
scanner:
  type: documentation
  detect_markers:
    - conf.py           # Sphinx
    - mkdocs.yml        # MkDocs  
    - docusaurus.config.js
  
  state_dag:
    node_source: "**/*.md"
    edge_extraction: 
      - toctree
      - cross_references
      - internal_links
    
    health_probes:
      - script: check_health.py
        output: health_score
      - script: find_orphans.py  
        output: orphan_flag
      - script: detect_drift.py
        output: drift_warning

# coder.lens (scanner addition)
scanner:
  type: software
  detect_markers:
    - pyproject.toml
    - package.json
    - Cargo.toml
    
  state_dag:
    node_source: modules/packages
    edge_extraction:
      - imports
      - dependencies
    
    health_probes:
      - script: pytest --cov --json
        output: coverage_score
      - script: ruff check --format json
        output: lint_issues
```

#### Why This Matters

| Metric | Greenfield Only | + State DAG |
|--------|-----------------|-------------|
| **Real-world coverage** | ~5% of tasks | ~95% of tasks |
| **Project understanding** | Start from scratch | See health at a glance |
| **Intent targeting** | Describe everything | Click the problem |
| **Continuous improvement** | One-shot goals | Ongoing health monitoring |

Most developer work is **brownfield** — improving existing projects, not building from scratch. State DAG makes Sunwell useful for the 95% of work that's maintenance, documentation, refactoring, and incremental improvement.

---

## Phased Approach

### Phasing Strategy

> **Key insight from codebase review**: The parallel backend (RFC-051) is 95% complete—only needs Tauri exposure. Trust layer extends existing infrastructure. Manipulable model requires new conceptual work.

**Recommended execution order** (differs from presentation order):

| Priority | Phase | Rationale |
|----------|-------|-----------|
| 1 | Phase 0 (State DAG Scanning) | Foundation for brownfield projects, enables model-first |
| 2 | Phase 2 (Trust Layer) | Extends existing `ProjectAnalysis.confidence`, low risk |
| 3 | Phase 4 (ATC UI) | Backend complete, just needs bridge + view |
| 4 | Phase 1 (Manipulable Model) | New paradigm, higher risk, can learn from 0, 2 & 4 |
| 5 | Phase 3 (Mid-Flight Control) | Depends on agent context from Phase 1 |
| 6 | Phase 5 (Escape Hatch) | Polish, can run in parallel with Phase 3 |

This order ships value faster:
1. **Phase 0** immediately enables brownfield projects (95% of real work)
2. **Phase 2 + 4** add trust and multi-agent visualization
3. **Phase 1** builds on learnings from seeing real State DAGs in use

---

### Phase 0: State DAG Scanning (1-2 weeks)

> **Foundation**: Build the State DAG infrastructure that enables model-first interaction with existing projects.

**Deliverables**:
1. **`sunwell scan` command** — Scan existing project and build State DAG
2. **Lens-driven scanners** — Each lens defines how to scan its domain
3. **Health probe integration** — Run existing scripts (check_health.py, pytest, ruff)
4. **State DAG visualization** — Show project health in Studio using existing DAG components

**Technical approach**:
```python
# sunwell/analysis/state_dag.py
@dataclass
class StateDagNode:
    id: str
    path: Path
    artifact_type: str  # "file", "module", "package", "doc"
    health_score: float  # 0.0-1.0
    health_probes: dict[str, Any]  # Results from each probe
    
@dataclass  
class StateDagEdge:
    source: str
    target: str
    edge_type: str  # "import", "link", "toctree", "depends"

class StateDagBuilder:
    def __init__(self, root: Path, lens: Lens):
        self.root = root
        self.scanner = lens.get_scanner()
        
    async def build(self) -> StateDag:
        nodes = await self.scanner.scan_nodes()
        edges = await self.scanner.extract_edges()
        health = await self.scanner.run_health_probes()
        return StateDag(nodes, edges, health)
```

**CLI interface**:
```bash
# Scan and show State DAG in Studio
sunwell scan ~/my-docs --lens tech-writer.lens

# Scan with JSON output (for CI/scripting)
sunwell scan ~/my-docs --json

# Auto-detect lens from project markers
sunwell scan ~/my-docs  # detects conf.py → tech-writer.lens
```

**Success criteria**:
- `sunwell scan` produces State DAG for docs project
- `sunwell scan` produces State DAG for Python project
- Studio shows State DAG with health colors
- Click node → shows health details

---

### Phase 0.5: Read-Only Model Validation (1-2 weeks)

> **De-risking step**: Validate that our component detection matches user mental models *before* building manipulation.

**Deliverables**:
1. **Component graph visualization** — Read-only view of detected components
2. **Feedback mechanism** — "Does this grouping look right?" [Yes] [No]
3. **Accuracy metrics** — Track agreement rate before proceeding

**Technical approach**:
- Extend `ProjectOverview.svelte` with collapsible component tree
- Use directory-based heuristics (`src/*`, `services/*`, `packages/*`, `apps/*`)
- Log user feedback to `.sunwell/component_feedback.json`

**Success criteria**:
- 80% of users agree with auto-detected components (or correct without frustration)
- If < 60% agreement, pause Phase 1 and improve detection

**Why this matters**: If we build manipulation on a foundation users don't trust, they'll never use it. Better to validate first.

---

### Phase 1: Manipulable Model Foundation (4-6 weeks)

**Deliverables**:
1. **Component graph visualization** — Interactive view of project structure
2. **Click-to-intent** — Click component → give instruction → agent acts
3. **Live model updates** — Model reflects agent changes in real-time

**Technical approach**:
- Build on existing Overview tab
- Use simple graph visualization (not full AST)
- Component detection from file structure + agent analysis
- Intent dialog triggers existing goal system

**Success criteria**:
- User can see project as component graph
- User can click component and say "refactor this"
- Agent executes, model updates

**Concrete scenario (validates design)**:

```
1. User opens project "my-saas-app" in Studio
2. Overview shows component graph:
   ┌──────────────┐     ┌──────────────┐
   │ AuthService  │ ──► │ UserService  │
   │ 🟢 95%       │     │ 🟡 72%       │
   └──────────────┘     └──────────────┘
           │
           ▼
   ┌──────────────┐
   │ Database     │
   │ 🟢 88%       │
   └──────────────┘

3. User clicks AuthService node
4. Intent dialog opens: "What would you like to do with AuthService?"
5. User types: "Extract this into a separate package"
6. Agent proposes:
   - Create `auth-lib/` directory
   - Move 5 files (listed)
   - Update 12 import statements (listed)
   - Estimated confidence: 85%
7. User clicks "Execute"
8. Agent runs, model updates in real-time
9. AuthService node moves to "auth-lib/" in visualization
10. Completion: "Refactored AuthService → auth-lib (12 files, 45 imports)"
```

**Critical requirement**: Steps 5-6 must complete in < 2 seconds. Step 8 model updates must be < 500ms latency.

### Phase 2: Trust Layer (3-4 weeks)

**Deliverables**:
1. **Confidence gradients everywhere** — Visual language across UI
2. **Provenance traces** — "Why does it say this?" on all claims
3. **Proactive uncertainty** — System surfaces doubts

**Technical approach**:
- Confidence scoring infrastructure (extend existing)
- Provenance links stored in memory system
- Uncertainty detection heuristics

**Success criteria**:
- User can see at a glance what needs review
- User can trace any claim to evidence
- System warns about uncertain areas without being asked

**Confidence calibration strategy**:

The 90% correlation target requires a feedback loop. Implementation:

```python
@dataclass(frozen=True, slots=True)
class ConfidenceFeedback:
    """User feedback on confidence accuracy."""
    claim_id: str
    predicted_confidence: float
    user_judgment: Literal["correct", "incorrect", "partially_correct"]
    timestamp: datetime

# Calibration process:
# 1. Log all claims with confidence scores
# 2. Sample user for verification on 🟡/🟠 claims (70-89%, 50-69%)
# 3. Track prediction accuracy over time
# 4. Adjust thresholds quarterly based on actual performance

# Example prompt (shown occasionally):
# "We said 'AuthService has 3 dependencies' (75% confident).
#  Was this accurate? [Yes] [Partially] [No]"
```

**Calibration metrics** (tracked in `.sunwell/confidence_calibration.json`):
- Brier score per confidence band
- Precision/recall for 🔴 claims (should be conservative)
- User override rate (high rate = recalibrate)

### Phase 3: Mid-Flight Control (2-3 weeks)

**Deliverables**:
1. **Pause/resume** — Stop agent mid-execution
2. **Redirect** — "Try a different approach"
3. **Feedback loop** — "That's wrong, here's why"

**Technical approach**:
- Agent state checkpointing
- Interrupt handling in execution loop
- Feedback ingestion into agent context

**Success criteria**:
- User can stop runaway agent
- User can steer without restarting
- Feedback improves subsequent attempts

### Phase 4: Multi-Agent Orchestration UI (3-4 weeks)

> **Note**: Builds on existing RFC-051 infrastructure. Backend already supports parallel agents—this phase focuses on **UX**.

**Deliverables**:
1. **ATC view** — Unified control plane visualizing existing `Coordinator` state
2. **Conflict resolution UI** — Expose existing `FileLockManager` decisions to user
3. **Real-time status streaming** — Connect `WorkerStatus` to frontend
4. **Model-level controls** — Pause/redirect/prioritize at model level

**Technical approach**:

| Task | Reuses | New Code |
|------|--------|----------|
| ATC layout engine | `dag.svelte.ts` dagre patterns | Adapt for workers |
| Worker status cards | `DagNode.svelte` | Style variations |
| Dependency edges | `DagEdge.svelte` | As-is |
| Conflict diff view | `DiffView.svelte` | As-is |
| Progress charts | `Chart.svelte` | As-is |
| Coordinator bridge | — | `studio/src-tauri/src/coordinator.rs` |
| Store | `dag.svelte.ts` patterns | `coordinator.svelte.ts` |

**What already exists** (no build needed):
- ✅ `Coordinator` (`sunwell/parallel/coordinator.py:68`): spawns workers, monitors health
- ✅ `FileLockManager` (`sunwell/parallel/locks.py:30`): flock() with deadlock prevention
- ✅ `DagCanvas.svelte`, `DagNode.svelte`, `DagEdge.svelte`: graph visualization
- ✅ `DiffView.svelte`: side-by-side and inline diff with LCS algorithm
- ✅ Event streaming patterns: `agent.svelte.ts`

**What needs to be built**:
- ❌ `studio/src-tauri/src/coordinator.rs` — Tauri bridge to Python
- ❌ `studio/src/stores/coordinator.svelte.ts` — State management
- ❌ `studio/src/components/coordinator/ATCView.svelte` — Main view
- ❌ Python CLI: `sunwell workers status --json`

**Success criteria**:
- 3 agents work in parallel (already works via CLI)
- User sees all activity in one view (new)
- Conflicts surface in UI for model-level resolution (new)

### Phase 5: Escape Hatch Polish (1-2 weeks)

**Deliverables**:
1. **Open in editor** — One click from any file reference
2. **Editor detection** — Respect user's preferred editor
3. **Sync back** — External edits reflected in model

**Technical approach**:
- System editor detection (VS Code, Cursor, nvim, etc.)
- File watcher for external changes
- Model refresh on external modification

---

## Current Foundation

What already exists that supports this vision:

| Component | Current State | Location | Readiness |
|-----------|--------------|----------|-----------|
| Project-centric architecture | ✅ Projects, not files | `studio/src/stores/project.svelte.ts` | Ready |
| Agent event streaming | ✅ Real-time updates | `studio/src/stores/agent.svelte.ts` | Ready |
| Memory system | ✅ Decisions, learnings | `studio/src-tauri/src/memory.rs` | Ready |
| DAG visualization | ✅ Task graph with dagre | `studio/src/stores/dag.svelte.ts` | Ready |
| DAG components | ✅ Nodes, edges, canvas | `studio/src/components/dag/` (5 files) | Ready |
| Lens system | ✅ Behavior variation | `studio/src-tauri/src/lens.rs` | Ready |
| Overview tab | ✅ Confidence, signals | `studio/src/components/project/` | Ready (enhance) |
| Parallel coordination | ✅ Full RFC-051 impl | `sunwell/parallel/` (8 files) | Ready (expose) |
| Diff view | ✅ Side-by-side, inline | `studio/src/components/primitives/DiffView.svelte` | Ready |
| Charts | ✅ Data visualization | `studio/src/components/primitives/Chart.svelte` | Ready |
| Confidence scoring | ⚠️ Exists scattered | Memory, ProjectAnalysis | Needs unification |
| Health monitoring | ⚠️ Security only | `studio/src-tauri/src/security.rs` | Needs project health |
| ATC-style multi-agent UI | ❌ No frontend | — | **Needs build** |
| Coordinator Tauri bridge | ❌ Not exposed | — | **Needs build** |

**Foundation score: 75%** — Core infrastructure exists. Key gaps: coordinator Tauri bridge, ATC view, confidence unification. Existing DAG components provide strong foundation for Phase 4.

### Foundation Score Breakdown

| Category | Score | Evidence |
|----------|-------|----------|
| Parallel backend | 95% | Full RFC-051 impl, only needs Tauri exposure |
| Project analysis | 80% | `ProjectAnalysis` has confidence, signals, pipeline |
| DAG visualization | 100% | Production-ready `DagCanvas`, `DagNode`, `DagEdge` |
| Memory/learnings | 90% | `LearningsPanel`, `MemoryGraph`, briefing system |
| Trust/confidence | 65% | Exists but not unified "everywhere" |
| Component detection | 0% | Genuine gap—`ProjectAnalysis` detects type, not components |
| ATC multi-agent UI | 0% | Backend complete, no frontend |
| **Weighted Average** | **75%** | Backend strong, UX gaps confirmed |

### Existing Parallel Infrastructure (RFC-051)

The `sunwell.parallel` module provides full multi-agent coordination:

```
sunwell/parallel/
├── coordinator.py    # Coordinator class — spawns workers, monitors health, merges results
├── worker.py         # WorkerProcess — claims goals, executes, commits to isolated branch
├── locks.py          # FileLockManager — advisory flock() locks, deadlock prevention
├── dependencies.py   # GoalDependencyGraph — conflict detection, parallel scheduling
├── resources.py      # ResourceGovernor — LLM rate limits, memory management
├── git.py            # Git operations — branch checkout, merge, rebase
├── config.py         # MultiInstanceConfig — worker count, timeouts
└── types.py          # CoordinatorResult, WorkerResult, MergeResult
```

**Key classes** (already implemented):

| Class | File:Line | Responsibility |
|-------|-----------|----------------|
| `Coordinator` | `coordinator.py:68` | Orchestrates workers, monitors health, merges branches |
| `CoordinatorResult` | `coordinator.py:37` | Execution summary (completed, failed, merged branches) |
| `FileLockManager` | `locks.py:30` | Advisory flock() locks with deadlock prevention |
| `FileLock` | `locks.py:16` | Acquired lock handle (path, lock_file, fd) |

**What Phase 4 builds ON this foundation**:
- **Tauri bridge** (`studio/src-tauri/src/coordinator.rs` — NEW) — expose `Coordinator` state to frontend
- **ATC view** — visualize existing `CoordinatorResult` with DAG-style components
- **Conflict resolution UI** — surface `FileLockManager` decisions to user
- **Real-time streaming** — connect `WorkerStatus` via existing event system

---

## Success Metrics

### User Experience

| Metric | Current | Phase 1 | Phase 4 |
|--------|---------|---------|---------|
| Time to understand project state | 5-10 min (read files) | 30 sec (scan model) | 10 sec (glance) |
| Context switches to editor | Every action | Only for review | Only for anomalies |
| Trust level (subjective) | Low (must verify) | Medium (spot check) | High (trust model) |
| Agents coordinatable | 1 | 1 | 3+ |

### Technical

| Metric | Target | Rationale |
|--------|--------|-----------|
| Model update latency | < 500ms after agent action | Cursor learned "no minute-long delays anywhere" is critical |
| Intent dialog response | < 2s from click to proposal | Users won't wait for model manipulation |
| Confidence accuracy | 90% correlation with actual correctness | Measured via Brier score + user feedback |
| Conflict detection | < 5% false negatives | Better to over-flag than miss conflicts |
| Multi-agent throughput | 3x single-agent for parallelizable work | Justifies orchestration complexity |
| Component detection | < 3s for 10k file project | Initial load must be fast |

### Latency Budget (Critical)

> **Lesson from Cursor shadow workspace**: Speed is non-negotiable. Users tolerate latency in background operations but not in interactive operations.

| Operation | Budget | Implementation Strategy |
|-----------|--------|------------------------|
| Model refresh | < 500ms | Incremental updates, not full recalculation |
| Click → intent dialog | < 100ms | Pre-render dialog, lazy load details |
| Intent → proposal | < 2s | Stream partial results |
| Agent progress → model update | < 500ms | Event streaming (existing infrastructure) |
| ATC view refresh | < 200ms | Poll `Coordinator.get_worker_statuses()` |

If we can't hit these budgets, the UX degrades to "just use the files"—defeating the purpose.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Model doesn't match mental model** | High | High | User-configurable granularity + feedback loop |
| **Latency exceeds budget** | Medium | High | Streaming, caching, incremental updates; hard-fail if > 2s |
| **Model accuracy without LSP** | High | Medium | Start with heuristics, evolve to agent-enhanced; don't promise AST-level |
| Over-trust leads to bugs shipped | Medium | High | Conservative confidence scoring, default to 🟡 not 🟢 |
| Multi-agent UI complexity | Low | Medium | Build on proven RFC-051 backend, reuse DAG components |
| Performance at scale | Medium | Medium | Incremental model updates, not full refresh |
| Escape hatch friction | Low | High | Prioritize editor integration early |
| Cross-stack coordination | Medium | Medium | Clear interface contracts between Python/Rust/Svelte |
| Python↔Rust serialization drift | Low | Medium | Shared type definitions, integration tests |
| `.agent` standard changes | Low | Low | Loose coupling—read if present, don't require |

### Risk Deep Dive: Model Accuracy

Cursor gets model accuracy "for free" from LSP—compilers and linters validate code. We don't have that luxury for component detection.

**Why this is hard**:
- Different users have different mental models of the same codebase
- "Component" is subjective (is `utils/` a component?)
- Dependencies aren't always explicit in code

**Mitigation strategy**:
1. **Phase 0.5 (validate before manipulate)**: Ship read-only component visualization first. See if users agree with what we show.
2. **User feedback loop**: "Does this grouping look right?" [Yes] [No, show me X instead]
3. **Conservative defaults**: Better to under-detect (show directories) than over-detect (claim false boundaries)
4. **Explicit uncertainty**: Mark auto-detected components as 🟡, user-confirmed as 🟢

---

## Alternatives Considered

### Alternative 1: Enhance traditional IDE

**Approach**: Add agent features to VS Code/Cursor model.

**Rejected because**: 
- File-centric architecture fights against model-first
- Already being done by Cursor, Copilot
- Sunwell's value is the orthogonal axis

### Alternative 2: Full code visualization (AST-level)

**Approach**: Show every function, class, variable in model.

**Rejected because**:
- Too much detail, loses mental model benefit
- Performance challenges
- Users don't think at AST level

### Alternative 3: Start with multi-agent UI

**Approach**: Build ATC view on RFC-051 backend before interactive model.

**Rejected because**:
- Multi-agent without good visualization is chaos (RFC-051 proved this—works via CLI but hard to use)
- Model-first gives foundation for orchestration UX
- Better to build confidence/provenance layer first, then apply to multi-agent view

---

## Open Questions

1. **Model granularity**: Auto-detect vs. user-configured? Start with file/directory level and evolve?

   > **Leaning toward**: Auto-detect with user override. Start with directory-based heuristics (`src/*`, `services/*`, `packages/*`), enhance with agent analysis. User can click "Show more detail" or "Group these together" to adjust granularity.

2. ~~**Confidence calibration**: How do we know our confidence scores are accurate? Need feedback loop.~~ **Resolved**: See Phase 2 implementation—Brier scoring with user feedback sampling.

3. **Conflict resolution UX**: Modal dialog vs. inline vs. separate view? Needs user testing.

   > **Leaning toward**: Inline notification with drill-down. Show banner in ATC view: "⚠️ Conflict in `auth.py`" with [View Diff] [Pause Worker] [Auto-resolve] buttons. Modal only for complex multi-file conflicts.

4. **Editor integration depth**: Just "open file" or bidirectional sync? Sync adds complexity.

   > **Leaning toward**: Start with "open file" only (Phase 5). Bidirectional sync is Phase 6+ if demand exists.

5. ~~**Agent isolation strategy**: Git branches vs. working directories vs. virtual filesystem?~~ **Resolved**: RFC-051 uses git branches with `WorkerProcess` committing to isolated branches.

6. **`.agent` directory compatibility**: Should we adopt the emerging `.agent` standard for context?

   > **Leaning toward**: Yes. Our model can be the visualization layer on top of `.agent` context. Read `.agent/prd.md`, `.agent/architecture.md` if present. Don't require it, but honor it.

7. **Component detection vs. project type detection**: Current `ProjectAnalysis` detects project *type* (code, docs, data), not internal *components*. These are different problems.

   > **Leaning toward**: Treat as separate layers:
   > - `ProjectAnalysis` → What kind of project? (existing)
   > - `ComponentGraph` → What's inside? (new in Phase 1)
   > Both feed into the unified model visualization.

---

## Implementation Notes

### Component Detection (Phase 1)

New module: `sunwell/analysis/components.py`

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class ProjectComponent:
    """A logical component in the project model."""
    name: str
    path: Path
    component_type: str  # "service", "library", "config", "test"
    confidence: float    # 0.0-1.0
    dependencies: tuple[str, ...]

def detect_components(root: Path) -> list[ProjectComponent]:
    """Level 1: Directory-based detection."""
    # Heuristics: src/*, services/*, packages/*, apps/*
    ...

def enhance_with_analysis(
    components: list[ProjectComponent], 
    agent_analysis: str
) -> list[ProjectComponent]:
    """Level 2: Agent-enhanced understanding."""
    # Parse agent suggestions for:
    # - Logical boundaries that don't match directory structure
    # - Cross-component dependencies
    # - Coupling metrics
    ...
```

### Confidence Propagation (Phase 2)

New module: `sunwell/confidence/aggregation.py`

```python
from dataclasses import dataclass
from statistics import mean

@dataclass(frozen=True, slots=True)
class Evidence:
    """Provenance for a confidence claim."""
    source_file: str
    line_range: tuple[int, int] | None
    reasoning: str

@dataclass
class ModelNode:
    name: str
    confidence: float  # 0.0-1.0
    provenance: tuple[Evidence, ...]
    children: tuple["ModelNode", ...]
    
    def aggregate_confidence(self) -> float:
        """Roll up confidence from children (conservative)."""
        if not self.children:
            return self.confidence
        child_conf = mean(c.aggregate_confidence() for c in self.children)
        return min(self.confidence, child_conf)
```

### Coordinator Bridge (Phase 4)

**New Rust module**: `studio/src-tauri/src/coordinator.rs`

```rust
use serde::{Deserialize, Serialize};
use tauri::Window;

#[derive(Serialize, Deserialize, Clone)]
pub struct WorkerStatus {
    pub id: u32,
    pub goal: String,
    pub status: String,  // "running", "waiting", "completed", "failed"
    pub progress: f32,
    pub current_file: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct FileConflict {
    pub path: String,
    pub worker_a: u32,
    pub worker_b: u32,
    pub resolution: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct CoordinatorState {
    pub workers: Vec<WorkerStatus>,
    pub conflicts: Vec<FileConflict>,
    pub total_progress: f32,
    pub merged_branches: Vec<String>,
}

#[tauri::command]
pub async fn get_coordinator_state(project_path: String) -> Result<CoordinatorState, String> {
    // Call: sunwell workers status --json --project {project_path}
    ...
}

#[tauri::command]
pub async fn pause_worker(worker_id: u32) -> Result<(), String> {
    // Call: sunwell workers pause {worker_id}
    ...
}
```

**New Svelte store**: `studio/src/stores/coordinator.svelte.ts`

```typescript
// Reuses patterns from dag.svelte.ts
import { invoke } from '@tauri-apps/api/core';
import type { CoordinatorState, WorkerStatus, FileConflict } from '$lib/types';

let _state = $state<CoordinatorState | null>(null);
let _isLoading = $state(false);

export async function loadCoordinatorState(projectPath: string): Promise<void> {
  _isLoading = true;
  try {
    _state = await invoke<CoordinatorState>('get_coordinator_state', { projectPath });
  } finally {
    _isLoading = false;
  }
}

// Expose reactive state
export const coordinatorStore = {
  get state() { return _state; },
  get isLoading() { return _isLoading; },
  get workers() { return _state?.workers ?? []; },
  get conflicts() { return _state?.conflicts ?? []; },
};
```

### ATC View Component (Phase 4)

Reuses existing DAG infrastructure:

```svelte
<!-- studio/src/components/coordinator/ATCView.svelte -->
<script lang="ts">
  import DagCanvas from '../dag/DagCanvas.svelte';
  import DagNode from '../dag/DagNode.svelte';
  import DiffView from '../primitives/DiffView.svelte';
  import { coordinatorStore, loadCoordinatorState } from '../../stores/coordinator.svelte';
  
  // Transform workers to DAG nodes for visualization
  const dagNodes = $derived(
    coordinatorStore.workers.map(w => ({
      id: `worker-${w.id}`,
      label: w.goal,
      status: w.status,
      progress: w.progress,
    }))
  );
</script>

<div class="atc-view">
  <DagCanvas nodes={dagNodes} edges={[]} />
  
  {#if coordinatorStore.conflicts.length > 0}
    <aside class="conflict-panel">
      {#each coordinatorStore.conflicts as conflict}
        <DiffView 
          leftLabel="Worker {conflict.worker_a}"
          rightLabel="Worker {conflict.worker_b}"
          mode="side-by-side"
        />
      {/each}
    </aside>
  {/if}
</div>
```

---

## Timeline

### Recommended Execution Order

| Order | Phase | Duration | Milestone | Risk Level |
|-------|-------|----------|-----------|------------|
| 1 | **Phase 0 (State DAG Scanning)** | 1-2 weeks | `sunwell scan` for brownfield projects | Low |
| 2 | Phase 2 (Trust Layer) | 3-4 weeks | Confidence gradients everywhere | Low |
| 3 | Phase 4 (ATC UI) | 2-3 weeks | Multi-agent orchestration view | Low |
| 4 | Phase 0.5 (Read-Only Model) | 1-2 weeks | Validate component detection | De-risk |
| 5 | Phase 1 (Manipulable Model) | 4-6 weeks | Interactive model MVP | High |
| 6 | Phase 3 (Mid-Flight Control) | 2-3 weeks | Pause/redirect/feedback | Medium |
| 7 | Phase 5 (Escape Hatch) | 1-2 weeks | Editor integration polish | Low |
| **Total** | | **14-22 weeks** | **S-tier control plane** | |

**Key insight**: Phase 0 ships brownfield capability in 1-2 weeks. This covers ~95% of real-world usage (improving existing projects vs. greenfield builds).

### Alternative: Original Presentation Order

If stakeholders prefer building the "hero feature" (manipulable model) first:

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1 | 4-6 weeks | Interactive model MVP |
| Phase 2 | 3-4 weeks | Trust layer complete |
| Phase 3 | 2-3 weeks | Mid-flight control |
| Phase 4 | 3-4 weeks | Multi-agent orchestration UI |
| Phase 5 | 1-2 weeks | Escape hatch polish |
| **Total** | **13-19 weeks** | **S-tier control plane** |

**Trade-off**: Original order is more impressive early but higher risk. Recommended order ships value faster with lower risk.

---

## References

### Related RFCs
- RFC-097: Studio UX Elevation
- RFC-084: Memory System
- RFC-094: Agent Events
- RFC-051: Multi-Instance Coordination (parallel agent infrastructure)
- RFC-042: Agent Event Streaming

### Codebase Evidence

| Evidence | Location |
|----------|----------|
| Coordinator implementation | `sunwell/parallel/coordinator.py:68` |
| File lock manager | `sunwell/parallel/locks.py:30` |
| DAG store (reusable patterns) | `studio/src/stores/dag.svelte.ts` |
| DAG components | `studio/src/components/dag/` |
| DiffView primitive | `studio/src/components/primitives/DiffView.svelte` |
| Chart primitive | `studio/src/components/primitives/Chart.svelte` |
| Tauri command patterns | `studio/src-tauri/src/main.rs:101-257` |
| Agent event streaming | `studio/src/stores/agent.svelte.ts` |

### External

| Source | URL | Key Insight |
|--------|-----|-------------|
| Cursor Shadow Workspace | `cursor.com/blog/shadow-workspace` | LSP access critical; "no minute-long delays" |
| Continue Agent Mode | `docs.continue.dev/ide-extensions/agent/how-it-works` | Tool handshake pattern standard |
| 12-Factor Agents | `humanlayer.dev/12-factor-agents` | Human-in-loop, small focused agents |
| `.agent` directory proposal | `github.com/openai/agents.md/issues/71` | Standardized context emerging |

**Industry trajectory**: Agent-assisted IDEs converging on tool calling + background iteration. Nobody owns "visual model + confidence" yet—that's our opening.

---

## Appendix: The Vision Statement

> People don't want to troll through files and terminals and bug reports. They want a mental model of their project to reason about and a futuristic control panel they can go to, inspect, and have their AI assistant deal with.
>
> Sunwell is an orthogonal evolution of the IDE—not better code editing, but a fundamentally different relationship between human and codebase. The human reasons about the model. The agent deals with the files.
