# RFC-082: Fluid Canvas UI

**Status**: Revised (Evaluated 2026-01-21)  
**Created**: 2026-01-21  
**Authors**: @llane  
**Depends on**: RFC-080 (Unified Home Surface), RFC-072 (Surface Composition)  
**Integrates with**: Naaru architecture (`src/sunwell/naaru/shards.py`, `convergence.py`)

### Dependency Verification

| Dependency | Status | Location |
|------------|--------|----------|
| RFC-080 (Unified Home Surface) | ✅ Exists | `docs/RFC-080-unified-home-surface.md` |
| RFC-072 (Surface Composition) | ✅ Exists | `docs/RFC-072-generative-surface.md` |
| Naaru shards.py | ✅ Exists | `src/sunwell/naaru/shards.py` |
| Naaru convergence.py | ✅ Exists | `src/sunwell/naaru/convergence.py` |
| FluidInput.svelte | ✅ Exists | `studio/src/components/FluidInput.svelte` |
| BlockSurface.svelte | ✅ Exists | `studio/src/components/BlockSurface.svelte` |
| Spring physics (svelte/motion) | ✅ In use | `BlockSurface.svelte:9`, `ThinkingBlock.svelte:13` |

---

## Summary

Transform Sunwell's UI from a page-based navigation model to a **fluid canvas** where elements morph, flow, and persist spatially. Inspired by Apple's iOS/iPadOS fluid design language, this creates a premium feel where the interface adapts to context rather than forcing users through discrete states.

## Problem Statement

Current Sunwell UI exhibits common "web app" patterns that feel disconnected:

1. **Teleporting elements** — Components appear/disappear rather than transitioning through space
2. **Disconnected inputs** — "Ask more" button separate from main input; input doesn't flow with context
3. **Page-based thinking** — Home, Project, Interface as separate destinations
4. **Linear animations** — CSS ease curves feel mechanical, not physical
5. **Stateless transitions** — Dismissed panels are gone; no spatial memory
6. **Click-only interaction** — No gesture support for direct manipulation

### User Experience Gap

```
Current State (B-tier):
┌─────────────────────────────────────────┐
│ Page A ──click──► Page B ──click──► A   │
│                                         │
│ Elements: appear/disappear              │
│ Input: stuck in one place               │
│ Panels: modal, blocking                 │
│ Feel: functional but forgettable        │
└─────────────────────────────────────────┘

Target State (S-tier):
┌─────────────────────────────────────────┐
│     ◄────── fluid canvas ──────►        │
│                                         │
│ Elements: morph, slide, bounce          │
│ Input: flows to where it's needed       │
│ Panels: spatial, persistent, stackable  │
│ Feel: magical, invites exploration      │
└─────────────────────────────────────────┘
```

## Goals

1. **Instant perceived responsiveness** — UI skeleton appears in <200ms via speculative composition
2. **Spatial coherence** — Elements have persistent positions; nothing teleports
3. **Physical motion** — Spring physics replace linear CSS transitions
4. **Direct manipulation** — Touch/trackpad gestures are first-class interactions
5. **Premium feel** — Achieve Apple-level fluid design that "invites exploration"

## Non-Goals

1. **3D interfaces** — No depth/z-axis navigation (rejected as unnecessary complexity)
2. **Multiplayer cursors** — Real-time collaboration is out of scope for this RFC
3. **Backwards compatibility** — Existing page-based navigation will be replaced, not maintained
4. **Mobile-first** — Desktop/tablet optimized; mobile adaptation is a follow-up
5. **Full canvas freedom** — Users cannot arbitrarily place elements; layouts are LLM-composed

## Design Options Considered

### Animation System

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: CSS-only** | Zero dependencies, hardware accelerated | No spring physics, limited orchestration | ❌ Rejected |
| **B: svelte/motion** | Native Svelte, spring physics, small bundle | Limited gesture support | ✅ **Selected** |
| **C: Framer Motion** | Industry standard, excellent DX | React-focused, large bundle (50kb+) | ❌ Rejected |
| **D: GSAP** | Powerful, excellent performance | License concerns, jQuery-era API | ❌ Rejected |

**Rationale**: `svelte/motion` provides spring physics without framework mismatch. Gestures handled separately via `@use-gesture/vanilla`.

### Canvas Architecture

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: DOM-based** | Accessibility, familiar tooling | Performance at scale, complex transforms | ✅ **Selected** |
| **B: Canvas 2D** | Excellent performance | Accessibility nightmare, custom hit testing | ❌ Rejected |
| **C: WebGL** | Best performance | Overkill, complexity, accessibility | ❌ Rejected |

**Rationale**: DOM with CSS transforms provides best accessibility/performance balance. Can optimize specific hot paths with canvas if needed.

### Speculative UI Strategy

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **A: Wait for LLM** | Simple, always correct | 2-5s latency feels slow | ❌ Rejected |
| **B: Hardcoded layouts** | Instant, predictable | Inflexible, doesn't adapt | ❌ Rejected |
| **C: Tiered prediction** | Instant + adaptive | Complexity, possible mismatch | ✅ **Selected** |

**Rationale**: Tiered prediction (Tier 0 regex → Tier 1 fast model → Tier 2 authoritative) balances speed with accuracy. Implemented in `compositor.py`.

## Design Principles

### 1. Spatial Coherence
Everything exists in space. When something leaves, it goes somewhere. When it returns, it comes from where it went.

### 2. Physical Motion
Elements have mass and momentum. Springs, not linear interpolation. Overshoot and settle, don't just stop.

### 3. Direct Manipulation
Touch it, drag it, swipe it. Gestures are first-class, not afterthoughts.

### 4. Contextual Morphing
The interface adapts to task. Input shrinks and moves when you need workspace. Panels expand when you focus them.

### 5. Persistent State
Nothing is truly dismissed. Minimized, collapsed, tucked away — but recoverable with spatial memory.

## Architecture

### Layer Model (Tetris Analogy)

```
┌─────────────────────────────────────────────────────────────────────┐
│ TETROMINOES (Primitives)                                            │
│ ────────────────────────                                            │
│ Atomic, immutable building blocks. Fixed vocabulary.                │
│                                                                     │
│ CodeEditor, DataTable, Preview, Terminal, FileTree, Canvas,         │
│ Timeline, ProseEditor, DiffView, Outline, ImageViewer, Chart        │
├─────────────────────────────────────────────────────────────────────┤
│ PIECES (Blocks)                                                     │
│ ──────────────                                                      │
│ Primitives + data binding + interaction handlers.                   │
│                                                                     │
│ ConversationBlock, CalendarBlock, HabitsBlock, FilesBlock,          │
│ ChartBlock, UploadBlock, SearchBlock, ProjectsBlock                 │
├─────────────────────────────────────────────────────────────────────┤
│ GRID (Layouts)                                          [DYNAMIC]   │
│ ────────────                                                        │
│ Spatial arrangements of blocks. LLM-composed at runtime.            │
│                                                                     │
│ ConversationLayout, WorkspaceLayout, ExplorerLayout,                │
│ ResearchLayout, PlanningLayout                                      │
├─────────────────────────────────────────────────────────────────────┤
│ CANVAS (Surface)                                        [INFINITE]  │
│ ──────────────                                                      │
│ The unified space containing all layouts. Pan, zoom, navigate.      │
│                                                                     │
│ One canvas. Multiple "areas" for different work contexts.           │
│ Zoom out to see everything. Zoom in to focus.                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```typescript
// Primitives: Pure rendering, no state
interface Primitive {
  render(data: unknown): VNode;
}

// Blocks: Data-bound, interactive
interface Block {
  primitive: Primitive;
  data: Reactive<unknown>;
  actions: ActionHandler[];
  position: SpringValue<Position>;  // Animated position
}

// Layouts: Spatial arrangement of blocks
interface Layout {
  blocks: Block[];
  arrangement: 'conversation' | 'workspace' | 'explorer' | 'custom';
  inputMode: 'hero' | 'chat' | 'search' | 'command';
  transitions: TransitionConfig;
}

// Canvas: The infinite surface
interface Canvas {
  layouts: Map<string, Layout>;
  viewport: Viewport;  // Current view position/zoom
  spatialMemory: Map<string, Position>;  // Where things were
  gestureHandler: GestureHandler;
}

// Page: A named canvas area (replaces traditional page navigation)
interface Page {
  id: string;                           // "home", "project:sunwell", "research:auth"
  layout: Layout;                       // Current layout in this area
  position: Position;                   // Location on the infinite canvas
  scale: number;                        // Zoom level (1.0 = default)
  state: 'active' | 'minimized' | 'hidden';
}
```

### Pages vs. Traditional Navigation

**Traditional**: Discrete pages with route changes, unmounting/mounting components
**Sunwell**: Canvas areas that persist spatially — "pages" are just focused regions

| Concept | Traditional | Sunwell Canvas |
|---------|-------------|----------------|
| **Navigation** | Route change, component remount | Pan/zoom to canvas area |
| **State** | Lost on unmount (unless lifted) | Persisted in canvas area |
| **Switching** | Instant but jarring | Smooth animated transition |
| **Multi-view** | Tabs, split panes | Zoom out to see multiple areas |
| **Memory** | Browser history | Spatial memory + recents |

**Page Types** (canvas areas):

| Page ID Pattern | Purpose | Example Layout |
|-----------------|---------|----------------|
| `home` | Default landing | ConversationLayout with HabitsBlock, ProjectsBlock |
| `project:{name}` | Project workspace | WorkspaceLayout with CodeEditor, FileTree, Terminal |
| `research:{topic}` | Research session | ResearchLayout with ProseEditor, References, SearchBlock |
| `planning:{name}` | Planning board | PlanningLayout with Kanban, Timeline, GoalTree |
| `data:{source}` | Data exploration | ExplorerLayout with DataTable, Chart, QueryBuilder |

## Detailed Design

### Phase 1: Spring Physics & Orchestration

Replace CSS transitions with spring-based motion.

#### Motion System

```typescript
// Core spring configuration
interface SpringConfig {
  stiffness: number;   // Higher = snappier (200-400 typical)
  damping: number;     // Higher = less bounce (20-30 typical)
  mass: number;        // Higher = more sluggish (1 typical)
}

// Preset configs for different contexts
const SPRING_PRESETS = {
  snappy: { stiffness: 400, damping: 30, mass: 1 },      // UI elements
  gentle: { stiffness: 200, damping: 25, mass: 1 },      // Panels
  bouncy: { stiffness: 300, damping: 15, mass: 1 },      // Playful
  heavy:  { stiffness: 150, damping: 20, mass: 1.5 },    // Large elements
};
```

#### Svelte Implementation

```svelte
<script>
  import { spring } from 'svelte/motion';
  
  // Spring-animated position
  const position = spring({ x: 0, y: 0 }, {
    stiffness: 0.1,
    damping: 0.4
  });
  
  // Spring-animated scale
  const scale = spring(1, { stiffness: 0.15, damping: 0.5 });
</script>

<div 
  style="transform: translate({$position.x}px, {$position.y}px) scale({$scale})"
>
  {content}
</div>
```

#### Orchestration Pattern

Stagger animations for visual hierarchy:

```typescript
interface AnimationSequence {
  stages: AnimationStage[];
}

interface AnimationStage {
  selector: string;
  delay: number;        // ms from sequence start
  spring: SpringConfig;
  properties: AnimatedProperties;
}

// Example: Conversation response sequence
const conversationEnterSequence: AnimationSequence = {
  stages: [
    { selector: '.input',    delay: 0,   spring: SPRING_PRESETS.snappy, properties: { y: 0, scale: 0.95 } },
    { selector: '.response', delay: 50,  spring: SPRING_PRESETS.gentle, properties: { y: 0, opacity: 1 } },
    { selector: '.panel-1',  delay: 100, spring: SPRING_PRESETS.bouncy, properties: { x: 0, opacity: 1 } },
    { selector: '.panel-2',  delay: 150, spring: SPRING_PRESETS.bouncy, properties: { x: 0, opacity: 1 } },
    { selector: '.input',    delay: 200, spring: SPRING_PRESETS.snappy, properties: { y: 'bottom', scale: 1 } },
  ]
};
```

### Phase 2: Spatial Memory & Persistence

Elements remember where they were and can return.

#### Spatial State Store

```typescript
interface SpatialState {
  // Where each element is currently
  positions: Map<ElementId, Position>;
  
  // Where elements go when minimized
  docks: {
    left: ElementId[];
    right: ElementId[];
    bottom: ElementId[];
  };
  
  // Full history for undo
  history: SpatialSnapshot[];
}

interface Position {
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  state: 'expanded' | 'collapsed' | 'minimized' | 'hidden';
}
```

#### Minimize Behavior

```
When user dismisses a panel:

1. Panel doesn't disappear instantly
2. Animates toward dock position (edge of screen)
3. Shrinks to icon size
4. Leaves "peek" indicator showing it's available
5. Click indicator → panel springs back to last position

┌─────────────────────────────────────────┐
│                                    [💬] │ ← Minimized conversation
│                                         │
│         Main content area               │
│                                         │
│ [📁]                               [📊] │ ← Minimized file tree, chart
└─────────────────────────────────────────┘
```

### Phase 3: Gesture System

Touch/trackpad gestures for direct manipulation.

#### Gesture Vocabulary

| Gesture | Action |
|---------|--------|
| Swipe down on panel | Minimize to dock |
| Swipe from edge | Restore minimized panel |
| Pinch on panel | Collapse to summary |
| Spread on panel | Expand to full |
| Two-finger pan | Navigate canvas |
| Pinch on canvas | Zoom in/out |
| Long press | Context menu |
| Drag panel edge | Resize |
| Drag panel header | Reposition |

#### Implementation

```typescript
import { createGesture } from '@use-gesture/vanilla';

const gesture = createGesture(element, {
  onDrag: ({ movement: [mx, my], velocity, direction }) => {
    // Update spring target based on drag
    position.set({ x: mx, y: my });
    
    // On release, snap to dock if velocity/direction indicates dismiss
    if (velocity > 0.5 && direction[1] > 0.7) {
      minimizeToBottom();
    }
  },
  onPinch: ({ scale }) => {
    if (scale < 0.7) collapse();
    if (scale > 1.3) expand();
  }
});
```

### Phase 4: Shared Element Transitions

Elements morph between states, maintaining identity.

#### Crossfade System

```svelte
<script>
  import { crossfade } from 'svelte/transition';
  
  const [send, receive] = crossfade({
    duration: 400,
    fallback: scale
  });
</script>

<!-- In project list -->
{#if !selectedProject}
  <div 
    in:receive={{ key: project.id }}
    out:send={{ key: project.id }}
  >
    <ProjectCard {project} />
  </div>
{/if}

<!-- In workspace -->
{#if selectedProject}
  <div
    in:receive={{ key: selectedProject.id }}
    out:send={{ key: selectedProject.id }}
  >
    <WorkspaceHeader project={selectedProject} />
  </div>
{/if}
```

#### Visual Example

```
ProjectCard in list                    WorkspaceHeader
┌────────────────┐                    ┌─────────────────────────────────┐
│ 🎮 pirate-game │                    │ 🎮 pirate-game                  │
│ ───────────────│   ══MORPHS═══►     │ ────────────────────────────────│
│ A pirate RPG   │                    │ src/ components/ package.json   │
└────────────────┘                    └─────────────────────────────────┘

The card BECOMES the header, it doesn't disappear and reappear.
```

### Phase 5: Canvas Model

One infinite surface instead of discrete pages.

#### Canvas Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CANVAS (infinite)                              │
│                                                                          │
│    ┌─────────────────┐                                                  │
│    │  Research Zone  │    ← Zoom: 0.3x                                  │
│    │  📚 🔍 📝       │                                                  │
│    └────────┬────────┘                                                  │
│             │                                                            │
│    ┌────────┴────────┬─────────────────┐                                │
│    │                 │                 │                                │
│    ▼                 ▼                 ▼                                │
│ ┌──────────┐   ┌──────────┐   ┌──────────┐                             │
│ │   Home   │◄─►│ Projects │◄─►│  Chats   │  ← Zoom: 1x (current)       │
│ │          │   │          │   │          │                              │
│ └──────────┘   └──────────┘   └──────────┘                             │
│                     │                                                    │
│                     ▼                                                    │
│              ┌──────────────────┐                                       │
│              │  Active Project  │  ← Zoom: 1.5x (focused)               │
│              │  ┌─────┬───────┐ │                                       │
│              │  │Files│ Code  │ │                                       │
│              │  └─────┴───────┘ │                                       │
│              └──────────────────┘                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Navigation

```typescript
interface Viewport {
  x: number;        // Canvas position
  y: number;
  zoom: number;     // 0.1 to 3.0
  
  // Animate to a specific area
  navigateTo(area: string, options?: NavigationOptions): void;
  
  // Zoom to fit specific content
  zoomToFit(elementIds: string[]): void;
  
  // Overview (zoom out to see everything)
  overview(): void;
}

// Example: Navigate to project workspace
canvas.viewport.navigateTo('project-pirate-game', {
  zoom: 1.2,
  spring: SPRING_PRESETS.gentle
});
```

### Phase 6: Predictive Intelligence

The UI anticipates needs based on patterns.

#### Pattern Recognition

```typescript
interface UserPattern {
  timeOfDay: Map<HourRange, ActivityType>;
  projectAffinities: Map<ProjectId, number>;
  layoutPreferences: Map<TaskType, LayoutConfig>;
  frequentTransitions: Array<[StateA, StateB, frequency]>;
}

// Example learned patterns
const patterns: UserPattern = {
  timeOfDay: {
    '6-9': 'email_triage',
    '9-12': 'deep_coding',
    '12-13': 'admin',
    '13-17': 'meetings_and_coding',
    '17-19': 'review_and_plan',
  },
  projectAffinities: {
    'pirate-game': 0.8,    // High recent activity
    'tax-docs': 0.2,       // Occasional
  },
  layoutPreferences: {
    'coding': { primary: 'CodeEditor', secondary: ['Terminal', 'FileTree'] },
    'writing': { primary: 'ProseEditor', secondary: ['Outline', 'Notes'] },
  }
};
```

#### Proactive Suggestions

```svelte
{#if suggestion}
  <div class="ambient-suggestion" transition:fly={{ y: 20 }}>
    <span class="suggestion-icon">💡</span>
    <span class="suggestion-text">{suggestion.text}</span>
    <div class="suggestion-actions">
      <button onclick={suggestion.accept}>Yes</button>
      <button onclick={suggestion.dismiss}>Not now</button>
    </div>
  </div>
{/if}

<!-- Example suggestions -->
<!-- "Continue working on pirate-game?" (based on time + recent activity) -->
<!-- "Open terminal? You usually have it open when coding Python" -->
<!-- "This looks like research — want me to add a notes panel?" -->
```

## Implementation Status

> **Note**: Significant portions of the speculative UI architecture are **already implemented**. This section documents current state to guide remaining work.

### ✅ Complete

| Component | Location | Notes |
|-----------|----------|-------|
| Compositor service | `src/sunwell/interface/compositor.py` | Full 3-tier prediction strategy |
| COMPOSITOR ShardType | `src/sunwell/naaru/shards.py:73` | Integrated with Naaru |
| `_compose_ui()` shard | `shards.py:352-401` | Stores to `composition:current` slot |
| Convergence slot support | `convergence.py:67` | COMPOSITOR source type |
| Tier 0 regex signals | `compositor.py:90-254` | 12 intent signal categories |
| Tier 1 fast model | `compositor.py:395-454` | JSON parsing, fallback handling |
| CompositionSpec/PanelSpec | `compositor.py:29-66` | Frozen dataclasses |
| FluidInput component | `studio/src/components/FluidInput.svelte` | 5 modes (hero/chat/search/command/hidden) |
| ConversationLayout | `studio/src/components/blocks/ConversationLayout.svelte` | Auxiliary panels, suggested tools |
| Block components | `studio/src/components/blocks/` | Calendar, Habits, Files, Projects, Notes, Search |

### ⏳ In Progress

| Component | Status | Blocker |
|-----------|--------|---------|
| Frontend skeleton rendering | Designed | Needs WebSocket integration to fetch from Convergence |
| Panel streaming | Designed | Depends on skeleton rendering |

### 🔲 Not Started

| Component | Phase | Complexity |
|-----------|-------|------------|
| Spring physics (`svelte/motion`) | Phase 1 | Medium |
| Animation orchestration | Phase 1 | Medium |
| Spatial memory store | Phase 2 | Medium |
| Dock/minimize system | Phase 2 | Medium |
| Gesture system (`@use-gesture`) | Phase 3 | High |
| Shared element transitions | Phase 4 | High |
| Canvas model (infinite surface) | Phase 5 | Very High |
| Predictive intelligence | Phase 6 | High |

---

## Implementation Phases

### Phase 1: Spring Physics & Orchestration (Week 1-2)

**Prerequisites**: Compositor backend ✅ complete

- [ ] Integrate `svelte/motion` spring stores
- [ ] Create `SpringValue` wrapper for animated values
- [ ] Implement `AnimationSequence` orchestration
- [ ] Update FluidInput with spring-based mode transitions (currently CSS easing)
- [ ] Add staggered entry animations to ConversationLayout
- [ ] Connect frontend to Convergence `composition:current` slot via WebSocket

### Phase 2: Spatial Memory (Week 3-4)
- [ ] Create `SpatialStateStore` (Svelte store)
- [ ] Implement dock system (minimize to edges)
- [ ] Add peek indicators for minimized panels
- [ ] Persist spatial state to localStorage
- [ ] Implement restore animations

### Phase 3: Gestures (Week 5-6)
- [ ] Integrate @use-gesture/vanilla
- [ ] Implement swipe-to-dismiss
- [ ] Add pinch-to-collapse/expand
- [ ] Implement drag-to-reposition
- [ ] Add two-finger pan for canvas navigation

### Phase 4: Shared Elements (Week 7-8)
- [ ] Implement crossfade transitions
- [ ] Create element identity system
- [ ] ProjectCard → WorkspaceHeader morph
- [ ] Input → ChatInput morph
- [ ] Block → FullPanel morph

### Phase 5: Canvas Model (Week 9-12)
- [ ] Refactor from pages to single canvas
- [ ] Implement viewport (pan/zoom)
- [ ] Create area system (named regions)
- [ ] Add minimap/overview mode
- [ ] Implement navigation animations

### Phase 6: Intelligence (Week 13-16)
- [ ] Create pattern tracking system
- [ ] Implement time-of-day awareness
- [ ] Add project affinity scoring
- [ ] Build suggestion engine
- [ ] Create ambient suggestion UI

## Success Metrics

| Metric | Current | Target | Measurement Method |
|--------|---------|--------|-------------------|
| Frame rate during transitions | ~30fps | ≥55fps sustained | Chrome DevTools Performance panel |
| First input delay (FID) | Unknown | <100ms | Web Vitals API |
| Cumulative Layout Shift (CLS) | Unknown | <0.1 | Web Vitals API |
| Time to skeleton render | N/A (no skeleton) | <200ms | `performance.mark()` instrumentation |
| Gesture recognition latency | N/A | <50ms | Event timestamp delta |
| Animation completion callbacks | 0% reliable | 100% | Spring `onComplete` fired |
| Spatial state persistence | 0% | 100% | LocalStorage + session resume test |

### Qualitative Metrics (User Testing)
| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Task completion rate | Baseline TBD | +15% | A/B test: old nav vs canvas |
| Feature discovery | Baseline TBD | +25% | Heat map analysis |
| User satisfaction (SUS score) | Baseline TBD | ≥80 | System Usability Scale survey |

## File Changes Summary

### Svelte Components (studio/src/components/)

| File | Action | Description |
|------|--------|-------------|
| `FluidInput.svelte` | MODIFY | Add spring physics, remove CSS cubic-bezier fallbacks |
| `BlockSurface.svelte` | MODIFY | Add gesture handlers, spatial persistence |
| `SpatialStateStore.ts` | CREATE | Centralized spatial memory with localStorage |
| `GestureProvider.svelte` | CREATE | Wrapper for `@use-gesture` integration |
| `Canvas.svelte` | CREATE | Infinite pan/zoom surface |
| `MinimizedDock.svelte` | CREATE | Edge dock for minimized panels |
| `SkeletonLayout.svelte` | CREATE | Speculative composition renderer |
| `blocks/*.svelte` | MODIFY | Add crossfade transitions, element identity |

### Python (src/sunwell/)

| File | Action | Description |
|------|--------|-------------|
| `naaru/shards.py` | MODIFY | Implement COMPOSITOR shard logic (type exists, logic partial) |
| `interface/compositor.py` | CREATE | Fast UI composition prediction service |
| `interface/intent_signals.py` | CREATE | Regex pattern database for Tier 0 matching |

### Configuration

| File | Action | Description |
|------|--------|-------------|
| `package.json` | MODIFY | Add `@use-gesture/vanilla`, verify `svelte-motion` |
| `schemas/composition.schema.json` | CREATE | JSON Schema for CompositionSpec validation |

---

## Accessibility Plan

Gesture-heavy interfaces require careful A11y design.

### 1. Keyboard Equivalents (Required)

| Gesture | Keyboard Equivalent |
|---------|---------------------|
| Swipe down (minimize) | `Escape` or `Cmd+M` |
| Swipe from edge (restore) | `Cmd+Shift+M` (cycle through docked) |
| Pinch (collapse) | `Cmd+-` |
| Spread (expand) | `Cmd++` |
| Two-finger pan | Arrow keys |
| Pinch canvas (zoom) | `Cmd+0` (reset), `Cmd+scroll` |
| Long press (context) | `Shift+F10` or context menu key |

### 2. Motion Sensitivity

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 3. WCAG 2.1 Compliance Checklist

- [ ] **2.1.1 Keyboard**: All gestures have keyboard alternatives
- [ ] **2.3.3 Animation**: Motion can be disabled
- [ ] **2.4.3 Focus Order**: Spatial layout doesn't break tab order
- [ ] **2.5.1 Pointer Gestures**: Multi-point gestures have single-point alternatives
- [ ] **2.5.4 Motion Actuation**: Motion-based features can be disabled

---

## Performance Budget

| Metric | Budget | Enforcement |
|--------|--------|-------------|
| JS bundle increase | <50KB gzipped | CI check on bundle size |
| Animation frame budget | <16ms (60fps) | Performance monitor in dev |
| Memory per minimized panel | <1KB | Spatial state audit |
| Spring calculations/frame | <10 elements | Automatic batching |
| Skeleton render time | <100ms | `performance.measure()` |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance on low-end devices | Medium | High | Progressive enhancement; reduce effects (see Performance Budget) |
| Gesture conflicts with OS | Medium | Medium | Respect system gestures; provide keyboard alternatives (see A11y Plan) |
| Spatial model confusion | Low | Medium | Clear visual cues; overview mode; undo |
| Scope creep | High | Medium | Strict phase gates; ship incrementally |
| A11y regression | Medium | High | WCAG checklist in PR template; automated a11y testing |

## Alternatives Considered

### 1. Traditional Page Navigation
**Rejected**: Doesn't achieve premium feel; feels like every other app.
- Pros: Simple mental model, well-understood patterns
- Cons: Breaks spatial coherence, creates "teleporting" UX

### 2. Tab-based Workspaces (like VS Code)
**Rejected**: Better than pages but still discrete; no spatial coherence.
- Pros: Familiar to developers, good for task switching
- Cons: Tabs become cluttered; no relationship between workspaces visible

### 3. Tiling Window Manager Style (i3/Sway)
**Partially adopted**: Good for workspace arrangement but needs fluid transitions.
- Pros: Efficient use of screen space, keyboard-driven
- Cons: Harsh snapping, no animations, steep learning curve
- **Adopted elements**: Panel arrangement system, dock concept

### 4. Full 3D Canvas (like Blender)
**Rejected**: Too complex; unnecessary dimensionality for this use case.
- Pros: Maximum flexibility, impressive demos
- Cons: Disorienting, accessibility nightmare, performance-heavy

### 5. Figma-style Multiplayer Canvas
**Deferred**: Excellent UX but requires significant infrastructure.
- Pros: Real-time collaboration, presence awareness
- Cons: Server-side state, CRDT complexity, out of scope for v1
- **Future work**: Could layer on top of this RFC's canvas model

### Decision Matrix

| Alternative | Premium Feel | A11y | Performance | Complexity | Decision |
|-------------|--------------|------|-------------|------------|----------|
| Traditional pages | ❌ | ✅ | ✅ | Low | Rejected |
| Tabs | ⚠️ | ✅ | ✅ | Low | Rejected |
| Tiling | ⚠️ | ⚠️ | ✅ | Medium | Partial |
| 3D canvas | ✅ | ❌ | ❌ | High | Rejected |
| **Fluid canvas (this RFC)** | ✅ | ✅* | ⚠️ | Medium | **Selected** |

*With A11y Plan implementation

## Open Questions

1. ~~**Mobile adaptation**~~: ✅ **Resolved** — Mobile explicitly a non-goal (see Non-Goals). Tablets supported in Phase 3.
2. ~~**Accessibility**~~: ✅ **Resolved** — See Accessibility Plan section above.
3. ~~**Performance budget**~~: ✅ **Resolved** — See Performance Budget section above.
4. **Offline behavior**: How does spatial memory persist across sessions/devices?
   - *Decision*: localStorage for single-device. Cross-device sync out of scope (requires user accounts).
5. **WebSocket integration**: How does frontend fetch `composition:current` from Convergence?
   - *Blocker for skeleton rendering*
   - **Options**:
     - A) Tauri command polling (`get_composition`) — Simple but latency
     - B) WebSocket push from Python → Tauri → Svelte — Complex but instant
     - C) HTTP SSE from Python directly — Bypasses Tauri, needs CORS
   - **Recommended**: Option A for Phase 1 (simplicity), migrate to B in Phase 5

---

## Speculative UI Architecture

### Problem: LLM Latency Creates Dead Time

Current flow:
```
User input ────► LLM (2-5s) ────► Parse response ────► Render UI
                   ↑
            User sees spinner for entire duration
```

### Solution: Parallel Composition with Fast Model

Split the work between a **fast compositor model** and **content model**:

```
User input ─┬──► Fast Model (100-200ms) ──► Composition Spec ──► Render Skeleton
            │                                                           │
            └──► Large Model (2-5s) ──────► Content ─────────────────► Stream into skeleton
```

The UI appears **instantly** with the right layout, then content fills in.

### Two-Model Architecture (Naaru Integration)

The compositor integrates with Sunwell's existing **Naaru** parallel intelligence architecture (`src/sunwell/naaru/`). Naaru handles parallel model execution via **Shards** that run while the main model thinks.

> **Implementation Status**:
> | Component | Status | Evidence |
> |-----------|--------|----------|
> | `ShardType.COMPOSITOR` enum | ✅ Exists | `naaru/shards.py:73` |
> | `ShardType.COMPOSITOR` in `convergence.py` | ✅ Exists | `naaru/convergence.py:67` |
> | COMPOSITOR shard logic | ⚠️ Partial | `shards.py:125` (handler exists, needs composition logic) |
> | Intent signals database | ❌ Not started | Needs `interface/intent_signals.py` |
> | Frontend Convergence polling | ❌ Not started | Needs Tauri command |

```
              ┌─────────────────┐
              │      NAARU      │
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │
 │Composit│       │ Memory │       │Context │
 │  ~50ms │       │  ~50ms │       │  ~50ms │
 └────────┘       └────────┘       └────────┘
     │                 │                 │
     └─────────────────┼─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   MAIN MODEL    │  ← Full content generation
              │     (2-5s)      │
              └─────────────────┘
```

**New Shard Type**: `COMPOSITOR`

```python
class ShardType(Enum):
    MEMORY_FETCHER = "memory_fetcher"
    CONTEXT_PREPARER = "context_preparer"
    QUICK_CHECKER = "quick_checker"
    LOOKAHEAD = "lookahead"
    CONSOLIDATOR = "consolidator"
    THOUGHT_LEXER = "thought_lexer"
    COMPOSITOR = "compositor"  # NEW: RFC-082 UI composition
```

The COMPOSITOR shard:
1. Runs Tier 0 regex matching (~0ms)
2. If no high-confidence match, uses the Naaru "voice" model (gemma3:1b) for Tier 1 (~50-100ms)
3. Stores result in Convergence slot `composition:current`
4. Frontend fetches from Convergence before main response arrives

```typescript
interface CompositionPipeline {
  // Stage 1: Fast layout prediction (Naaru COMPOSITOR shard)
  compositor: {
    model: 'naaru.voice' | 'gemma3:1b' | 'phi-4-mini';  // Configurable in sunwell.yaml
    task: 'Predict layout composition from intent signals';
    output: CompositionSpec;
    slot: 'composition:current';  // Convergence slot
  };
  
  // Stage 2: Content generation (runs in parallel, streams)
  generator: {
    model: 'claude-sonnet' | 'gpt-4o' | 'llama-3.3-70b';
    task: 'Generate response content';
    output: StreamingContent;
  };
}

interface CompositionSpec {
  page_type: 'home' | 'project' | 'research' | 'planning' | 'conversation';
  layout: LayoutSpec;
  panels: PanelSpec[];
  input_mode: 'hero' | 'chat' | 'command' | 'search';
  suggested_tools: string[];
  confidence: number;  // If low, wait for large model to confirm
}
```

### Fast Model Prompt (Compositor)

The fast model gets a **constrained task** — just classify and compose:

```
You are a UI compositor. Given user input and context, predict the optimal layout.

VALID PAGE TYPES: home, project, research, planning, conversation

VALID PANELS (by page type):
- conversation: calendar, tasks, chart, image, upload, code, map, editor, document, products, links
- project: file_tree, terminal, code, preview, diff, test_runner, deploy
- research: notes, sources, web, diagram, citations
- planning: kanban, calendar, tasks, timeline, team, progress

INTENT SIGNALS → COMPOSITION:
| Signal | Page Type | Panels |
|--------|-----------|--------|
| schedule/time/day words | conversation | calendar |
| todo/task/remind | conversation | tasks |
| budget/money/spending | conversation | chart, upload |
| explain/how/what is | conversation | image, links |
| code/function/error | conversation | code |
| plan week + fitness | conversation | calendar, chart |
| open [project] | project | file_tree, code, terminal |
| research [topic] | research | notes, sources |

USER INPUT: "{input}"
CONTEXT: {page_type: "{current_page}", recent_panels: [...]}

Respond with JSON only:
{
  "page_type": "...",
  "panels": [{"type": "...", "title": "..."}],
  "input_mode": "...",
  "tools": [...],
  "confidence": 0.0-1.0
}
```

### Confidence-Based Fallback

```typescript
async function processInput(input: string): Promise<void> {
  // Start both models in parallel
  const compositionPromise = fastModel.predict(input);
  const contentPromise = largeModel.generate(input);
  
  // Wait for fast model first (~100ms)
  const composition = await compositionPromise;
  
  if (composition.confidence >= 0.8) {
    // High confidence: render immediately
    renderSkeleton(composition);
    
    // Stream content into skeleton as it arrives
    for await (const chunk of contentPromise) {
      updateContent(chunk);
    }
  } else {
    // Low confidence: wait for large model's composition
    // (Large model response includes layout hints)
    const fullResponse = await contentPromise;
    renderWithContent(fullResponse);
  }
}
```

### Visual Timeline

```
                    0ms     100ms    200ms    500ms    1000ms   2000ms
                    │        │        │        │        │        │
Fast Model:         ████████│        │        │        │        │
                            ↓        │        │        │        │
UI Skeleton:                ▓▓▓▓▓▓▓▓▓│        │        │        │
                                     │        │        │        │
Large Model:        ░░░░░░░░░░░░░░░░░█████████████████████████████
                                     │        │        ↓        │
Content Streaming:                   │        │  ══════════════►│
                                     │        │        │        │
User Perception:    [input]  [layout appears]  [content flows in]
                            "instant"         "feels fast"
```

### Page-Specific Composition Schemas

Each page type has a **validated schema** the fast model must conform to:

```typescript
// Composition schemas per page type
const COMPOSITION_SCHEMAS: Record<PageType, CompositionSchema> = {
  home: {
    valid_layouts: ['hero_only', 'conversation', 'quick_actions'],
    valid_panels: [],  // Home has no auxiliary panels initially
    default_input_mode: 'hero',
    transitions_to: ['conversation', 'project', 'research', 'planning'],
  },
  
  conversation: {
    valid_layouts: ['chat_only', 'chat_with_panels'],
    valid_panels: ['calendar', 'tasks', 'chart', 'image', 'upload', 'code', 
                   'map', 'editor', 'document', 'products', 'links'],
    max_panels: 3,
    default_input_mode: 'chat',
    panel_rules: {
      // Mutual exclusivity
      'calendar': { conflicts_with: [] },
      'tasks': { conflicts_with: [] },
      'chart': { conflicts_with: [] },
      'code': { conflicts_with: ['editor'] },  // Don't show both
      'editor': { conflicts_with: ['code'] },
    },
  },
  
  project: {
    valid_layouts: ['code_focused', 'terminal_focused', 'review_mode'],
    valid_panels: ['file_tree', 'terminal', 'code', 'preview', 'diff', 
                   'test_runner', 'deploy', 'conversation'],
    required_panels: ['file_tree'],  // Always show file tree
    default_input_mode: 'command',
    panel_rules: {
      'code': { pairs_well_with: ['terminal', 'preview'] },
      'diff': { replaces: 'code' },  // Diff takes code's spot
    },
  },
  
  research: {
    valid_layouts: ['notes_focused', 'sources_focused', 'split'],
    valid_panels: ['notes', 'sources', 'web', 'diagram', 'citations', 'conversation'],
    required_panels: ['notes'],
    default_input_mode: 'search',
  },
  
  planning: {
    valid_layouts: ['kanban_focused', 'calendar_focused', 'overview'],
    valid_panels: ['kanban', 'calendar', 'tasks', 'timeline', 'team', 'progress'],
    default_input_mode: 'command',
  },
};
```

### Intent Signal Database

> **Status**: ✅ **Implemented** — See `compositor.py:90-254` for all 12 signal categories

Pre-computed intent signals for fast matching (can run **without LLM** for common cases):

```typescript
const INTENT_SIGNALS: IntentSignal[] = [
  // Calendar triggers
  { patterns: [/plan (my |the )?week/i, /schedule/i, /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i, 
               /\d{1,2}(:\d{2})?\s*(am|pm)/i, /meeting/i, /appointment/i, /when am i free/i],
    composition: { page: 'conversation', panels: ['calendar'] } },
  
  // Task triggers
  { patterns: [/todo/i, /task/i, /remind me/i, /checklist/i, /things to do/i, /i need to/i],
    composition: { page: 'conversation', panels: ['tasks'] } },
  
  // Finance triggers  
  { patterns: [/budget/i, /spending/i, /money/i, /financ/i, /expense/i, /how much did i spend/i],
    composition: { page: 'conversation', panels: ['chart', 'upload'], tools: ['upload'] } },
  
  // Code triggers
  { patterns: [/\b(code|function|class|method|bug|error|exception)\b/i, 
               /\b(python|javascript|typescript|rust|go|java|c\+\+)\b/i,
               /how (do|can) i (write|implement|create)/i],
    composition: { page: 'conversation', panels: ['code'] } },
  
  // Location triggers
  { patterns: [/where is/i, /near me/i, /directions/i, /restaurant/i, /hotel/i, /how (do|can) i get to/i],
    composition: { page: 'conversation', panels: ['map'], tools: ['location'] } },
  
  // Creative writing triggers
  { patterns: [/write (a |me )?(story|poem|essay|article)/i, /help me write/i, /draft/i, /creative/i],
    composition: { page: 'conversation', panels: ['editor'], tools: ['voice'] } },
  
  // Project triggers
  { patterns: [/open (.+) project/i, /work on (.+)/i, /let's code/i, /start coding/i],
    composition: { page: 'project', panels: ['file_tree', 'code', 'terminal'] } },
  
  // Research triggers
  { patterns: [/research (.+)/i, /learn about/i, /study/i, /take notes on/i],
    composition: { page: 'research', panels: ['notes', 'sources'] } },
  
  // Planning triggers
  { patterns: [/plan (the |my )?sprint/i, /organize (my |the )?work/i, /project board/i, /kanban/i],
    composition: { page: 'planning', panels: ['kanban', 'calendar'] } },
];

// Fast regex-based pre-screening (no LLM needed for high-confidence matches)
function fastIntentMatch(input: string): CompositionSpec | null {
  for (const signal of INTENT_SIGNALS) {
    const matches = signal.patterns.filter(p => p.test(input));
    if (matches.length >= 2) {  // Multiple pattern hits = high confidence
      return {
        ...signal.composition,
        confidence: 0.9 + (matches.length * 0.02),  // More matches = higher confidence
        source: 'regex',
      };
    }
  }
  return null;  // Fall back to fast model
}
```

### Three-Tier Composition Strategy

> **Status**: ✅ **Implemented** — See `compositor.py:342-371` (`predict()` method)

```
Tier 0: Regex Pre-screen (0ms)
  ├─ High confidence match → Render immediately
  └─ No match → Tier 1

Tier 1: Fast Model (100-200ms)
  ├─ Confidence ≥ 0.8 → Render skeleton
  └─ Confidence < 0.8 → Tier 2

Tier 2: Large Model (2-5s)
  └─ Always authoritative, can override Tier 0/1
```

### Implementation: Compositor Service

> **Status**: ✅ **Implemented** — See `src/sunwell/interface/compositor.py` (492 lines)

```python
# src/sunwell/interface/compositor.py

@dataclass(frozen=True, slots=True)
class CompositionSpec:
    """Speculative UI composition from fast analysis."""
    page_type: str
    panels: tuple[dict[str, Any], ...]
    input_mode: str
    suggested_tools: tuple[str, ...]
    confidence: float
    source: str  # 'regex' | 'fast_model' | 'large_model'

class Compositor:
    """Fast UI composition prediction."""
    
    def __init__(self, fast_model: Model, intent_signals: list[IntentSignal]):
        self.fast_model = fast_model
        self.intent_signals = intent_signals
    
    async def predict(
        self, 
        input: str, 
        context: CompositionContext,
    ) -> CompositionSpec:
        """Predict composition with tiered strategy."""
        
        # Tier 0: Regex pre-screen
        regex_match = self._regex_match(input)
        if regex_match and regex_match.confidence >= 0.9:
            return regex_match
        
        # Tier 1: Fast model
        fast_result = await self._fast_model_predict(input, context)
        return fast_result
    
    def _regex_match(self, input: str) -> CompositionSpec | None:
        """Ultra-fast regex-based intent matching."""
        for signal in self.intent_signals:
            hits = sum(1 for p in signal.patterns if p.search(input))
            if hits >= 2:
                return CompositionSpec(
                    page_type=signal.page_type,
                    panels=tuple(signal.panels),
                    input_mode=signal.input_mode,
                    suggested_tools=tuple(signal.tools),
                    confidence=min(0.95, 0.85 + hits * 0.03),
                    source='regex',
                )
        return None
    
    async def _fast_model_predict(
        self, 
        input: str, 
        context: CompositionContext,
    ) -> CompositionSpec:
        """Fast model composition prediction."""
        prompt = self._build_prompt(input, context)
        result = await self.fast_model.generate(prompt, max_tokens=200)
        return self._parse_result(result)
```

### Frontend: Skeleton Rendering

> **Status**: 🔲 **Not Started** — Backend ready, needs WebSocket integration to fetch from Convergence

```svelte
<!-- SkeletonLayout.svelte -->
<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  
  interface Props {
    composition: CompositionSpec;
    content?: StreamingContent;
  }
  
  let { composition, content }: Props = $props();
</script>

<div class="layout layout-{composition.page_type}">
  <!-- Main content area with loading state -->
  <main class="main-content" transition:fade>
    {#if content?.text}
      <div class="content">{@html content.text}</div>
    {:else}
      <div class="skeleton-content">
        <div class="skeleton-line w-75"></div>
        <div class="skeleton-line w-100"></div>
        <div class="skeleton-line w-60"></div>
      </div>
    {/if}
  </main>
  
  <!-- Panels appear immediately with their own loading states -->
  {#if composition.panels.length > 0}
    <aside class="panels" transition:fly={{ x: 100, duration: 200 }}>
      {#each composition.panels as panel, i (panel.type)}
        <div 
          class="panel panel-{panel.type}" 
          transition:fly={{ x: 50, delay: i * 50, duration: 200 }}
        >
          <SkeletonPanel type={panel.type} data={panel.data} />
        </div>
      {/each}
    </aside>
  {/if}
  
  <!-- Input positioned based on mode -->
  <FluidInput mode={composition.input_mode} tools={composition.suggested_tools} />
</div>

<style>
  .skeleton-line {
    height: 1em;
    background: linear-gradient(90deg, 
      rgba(255,255,255,0.05) 0%, 
      rgba(255,255,255,0.1) 50%, 
      rgba(255,255,255,0.05) 100%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;
    margin-bottom: 0.5em;
  }
  
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  
  .w-75 { width: 75%; }
  .w-100 { width: 100%; }
  .w-60 { width: 60%; }
</style>
```

### Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SPECULATIVE UI PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Input                                                                 │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ TIER 0: Regex Pre-screen (0ms)                                      │   │
│  │   - Pattern matching against INTENT_SIGNALS                         │   │
│  │   - If 2+ patterns match → confidence ≥0.9 → skip to render         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│      │                                                                      │
│      ▼ (no match)                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ TIER 1: Fast Model (100-200ms)                                      │   │
│  │   - gemma-3-4b / phi-4-mini / qwen-0.5b                            │   │
│  │   - Constrained JSON output                                         │   │
│  │   - Validates against COMPOSITION_SCHEMAS                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│      │                                                                      │
│      ├── confidence ≥0.8 ───► RENDER SKELETON ◄─── (parallel) ───┐        │
│      │                               │                            │        │
│      ▼ (low confidence)              │                            │        │
│  ┌────────────────────────────────────────────────────────────────┴───┐   │
│  │ TIER 2: Large Model (2-5s)                                         │   │
│  │   - claude-sonnet / gpt-4o / llama-70b                            │   │
│  │   - Full content generation                                        │   │
│  │   - Can override Tier 0/1 composition                              │   │
│  │   - Streams content into skeleton                                  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Appendix A: Tetris Composition Catalog

This appendix defines the **valid layout compositions** for each major interaction context. The LLM uses these patterns to compose appropriate UIs.

### Composition Notation

```
┌─────────────────────────────────────────────────────────────────┐
│  [PRIMARY]     Main content area (always present)               │
│  [AUXILIARY]   Context panels (0-3, LLM-selected)               │
│  [INPUT]       Where the fluid input lives                      │
│  [TOOLS]       Suggested input enhancements                     │
└─────────────────────────────────────────────────────────────────┘
```

---

### CONVERSATION LAYOUTS

#### 1. General Chat (No Specific Context)
**Triggers**: Casual questions, greetings, emotional support

```
┌────────────────────────────────────────┐
│ 💬 Conversation                      ✕ │
│ ────────────────────────────────────── │
│ 👤 How's your day going?               │
│ ✨ I'm here to help! What's on your    │
│    mind today?                         │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ Tell me more...                [↑] │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘

Composition: Chat-only (no auxiliary panels)
Tools: None
```

#### 2. Calendar/Scheduling Context
**Triggers**: "plan my week", "schedule", "Thursday at 2pm", "meeting", "appointment", "when am I free"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 I want to plan my week                                       │
│ ✨ Let's plan your week! I can see your calendar...             │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 📅 This Week                  │
│ 👤 Thursday 2pm pizza with Joe  │ ┌───────────────────────────┐ │
│ ✨ Added! I've put "Pizza with  │ │ Mon  Tue  Wed  THU  Fri   │ │
│    Joe" on Thursday at 2pm.     │ │                  ███      │ │
│                                 │ │             2pm Pizza     │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │                               │
│ │ What else this week?    [↑] │ │ [+ Add Event]                 │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + CalendarPanel
Tools: None (calendar has its own add UI)
Signals: time words, day names, "plan", "schedule", "free", "busy"
```

#### 3. Task/Todo Context  
**Triggers**: "todo", "tasks", "I need to", "remind me", "checklist", "things to do"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 What do I need to do today?                                  │
│ ✨ Here's your task list for today...                           │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ ✓ Today's Tasks               │
│                                 │ ┌───────────────────────────┐ │
│                                 │ │ ○ Review PR #432          │ │
│                                 │ │ ○ Call dentist            │ │
│                                 │ │ ✓ Send invoice (done)     │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │                               │
│ │ Add a task...           [↑] │ │ [Show all lists]              │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + TaskListPanel
Tools: None (tasks have checkbox UI)
```

#### 4. Finance/Budget Context
**Triggers**: "finances", "budget", "spending", "money", "expenses", "how much did I spend"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 Help me with my finances                                     │
│ ✨ I can help analyze your spending! Would you like to upload   │
│    a bank statement, or shall I work with what I know?          │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 📊 Spending Overview          │
│ [📎] [📷]                       │ ┌───────────────────────────┐ │
│                                 │ │     [PIE CHART]           │ │
│                                 │ │  Food: 35%                │ │
│                                 │ │  Transport: 20%           │ │
│                                 │ │  Entertainment: 15%       │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │                               │
│ │ Ask about spending...   [↑] │ │ 📎 Upload Statement           │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + ChartPanel + UploadPanel
Tools: [upload, camera] (for receipts/statements)
```

#### 5. Learning/Explanation Context
**Triggers**: "how does", "what is", "explain", "teach me", "why does", educational questions

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 How do birds fly?                                            │
│ ✨ Birds fly using a combination of lift and thrust...          │
│                                                                 │
│    The wing shape creates lower pressure above...               │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 🖼️ Wing Aerodynamics          │
│                                 │ ┌───────────────────────────┐ │
│                                 │ │    [DIAGRAM: airflow]     │ │
│                                 │ │    over wing shape        │ │
│                                 │ └───────────────────────────┘ │
│                                 ├───────────────────────────────┤
│                                 │ 🌐 Learn More                 │
│                                 │ • Wikipedia: Bird flight      │
│                                 │ • Video: How Wings Work       │
│ ┌─────────────────────────────┐ │                               │
│ │ Ask a follow-up...      [↑] │ │                               │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + ImagePanel + LinksPanel
Tools: None
```

#### 6. Location/Travel Context
**Triggers**: "where is", "directions", "how to get to", "near me", "restaurant", "hotel"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 Find me a good pizza place near downtown                     │
│ ✨ I found some great pizza spots downtown!                     │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 🗺️ Downtown Area              │
│ 🍕 Tony's Pizza - 4.5⭐         │ ┌───────────────────────────┐ │
│    0.3 mi • $$ • Italian        │ │                           │ │
│                                 │ │    [MAP with pins]        │ │
│ 🍕 Slice House - 4.2⭐          │ │     📍 📍                  │ │
│    0.5 mi • $ • NY Style        │ │        📍                 │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │                               │
│ │ Refine search...        [↑] │ │ [Get Directions]              │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + MapPanel + ListPanel
Tools: [location] (to use current location)
```

#### 7. Creative Writing Context
**Triggers**: "write a story", "poem", "help me write", "draft", "creative"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 Write a story about a dragon                                 │
│ ✨ Here's a story for you...                                    │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 📝 Draft                      │
│ [Story preview in chat]         │ ┌───────────────────────────┐ │
│                                 │ │ The Last Dragon of        │ │
│                                 │ │ Thornwood                  │ │
│                                 │ │                           │ │
│                                 │ │ In the misty peaks of...  │ │
│                                 │ │ [full editable text]      │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │                               │
│ │ Continue or revise...   [↑] │ │ [Copy] [Expand] [Edit]        │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + EditorPanel
Tools: [voice] (for dictation)
```

#### 8. Photo/Image Context
**Triggers**: User uploads image, "look at this", "what's in this picture", "edit this photo"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 [Uploaded: sunset.jpg]                                       │
│ ✨ Beautiful sunset! I can see warm orange and pink tones       │
│    with silhouetted trees. Would you like me to enhance it?     │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 🖼️ sunset.jpg                 │
│                                 │ ┌───────────────────────────┐ │
│                                 │ │                           │ │
│                                 │ │    [IMAGE PREVIEW]        │ │
│                                 │ │                           │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │ [Enhance] [Crop] [Filter]     │
│ │ What should I do?       [↑] │ │                               │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + ImagePreviewPanel
Tools: [camera, upload] (to add more images)
```

#### 9. Code/Technical Context
**Triggers**: "code", "function", "bug", "error", programming language names, technical terms

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 How do I sort a list in Python?                              │
│ ✨ There are several ways to sort lists in Python...            │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 🐍 Python                     │
│ You can use `sorted()` or       │ ┌───────────────────────────┐ │
│ `.sort()` method:               │ │ # Using sorted()          │ │
│                                 │ │ nums = [3, 1, 4, 1, 5]    │ │
│ • `sorted()` returns new list   │ │ sorted_nums = sorted(nums)│ │
│ • `.sort()` modifies in place   │ │                           │ │
│                                 │ │ # Using .sort()           │ │
│                                 │ │ nums.sort()               │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │ [Copy] [Run] [Explain More]   │
│ │ Show me another example [↑] │ │                               │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + CodePanel
Tools: None (code panel has copy/run)
```

#### 10. Health/Fitness Context
**Triggers**: "workout", "exercise", "calories", "health", "steps", "sleep", "weight"

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 How many steps did I take this week?                         │
│ ✨ Here's your activity for this week...                        │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 👟 Steps This Week            │
│ Great progress! You averaged    │ ┌───────────────────────────┐ │
│ 8,200 steps/day.                │ │ M   T   W   T   F   S   S │ │
│                                 │ │ █   █   ▄   █   █   ▂   ▄ │ │
│ Your best day was Tuesday       │ │ 9k  10k 6k  9k  8k  3k  7k│ │
│ with 10,234 steps!              │ └───────────────────────────┘ │
│                                 │ Total: 52,400 steps           │
│ ┌─────────────────────────────┐ │ Goal: 70,000 (75% complete)   │
│ │ Tips to hit my goal?    [↑] │ │                               │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + ChartPanel (bar chart)
Tools: None
```

#### 11. Shopping/Product Context
**Triggers**: "buy", "shop", "product", "price", "compare", "review", specific product names

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 Help me find a good laptop for coding                        │
│ ✨ I'd recommend looking at these options for development...    │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 💻 Recommendations            │
│ For coding, you want:           │ ┌───────────────────────────┐ │
│ • Good RAM (16GB+)              │ │ MacBook Pro 14"           │ │
│ • Fast SSD                      │ │ ⭐⭐⭐⭐⭐ $1,999          │ │
│ • Nice keyboard                 │ ├───────────────────────────┤ │
│                                 │ │ ThinkPad X1 Carbon        │ │
│                                 │ │ ⭐⭐⭐⭐½ $1,649          │ │
│                                 │ ├───────────────────────────┤ │
│                                 │ │ Dell XPS 15               │ │
│                                 │ │ ⭐⭐⭐⭐ $1,499            │ │
│ ┌─────────────────────────────┐ │ └───────────────────────────┘ │
│ │ Compare specs...        [↑] │ │ [Compare] [Reviews]           │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + ProductListPanel
Tools: None
```

#### 12. Document/File Context
**Triggers**: "document", "pdf", "file", "spreadsheet", user uploads document

```
┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
│ ─────────────────────────────────────────────────────────────── │
│ 👤 [Uploaded: contract.pdf]                                     │
│ ✨ I've analyzed this contract. Here are the key points...      │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 📄 contract.pdf               │
│ Key Terms:                      │ ┌───────────────────────────┐ │
│ • Duration: 2 years             │ │                           │ │
│ • Value: $50,000                │ │   [PDF PREVIEW]           │ │
│ • Notice period: 30 days        │ │   Page 1 of 12            │ │
│                                 │ │                           │ │
│ ⚠️ Note: Clause 4.2 has an      │ └───────────────────────────┘ │
│ unusual termination condition   │ [◀ Prev] [Page 1] [Next ▶]    │
│ ┌─────────────────────────────┐ │                               │
│ │ Explain clause 4.2...   [↑] │ │ [Highlight] [Extract Text]   │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Composition: Chat + DocumentPreviewPanel
Tools: [upload] (for more documents)
```

---

### COMPOSITION DECISION MATRIX

| Intent Signal | Primary Panel | Secondary Panels | Input Tools |
|--------------|---------------|------------------|-------------|
| Time/schedule keywords | CalendarPanel | - | - |
| Task/todo keywords | TaskListPanel | - | - |
| Money/finance keywords | ChartPanel | UploadPanel | upload |
| Educational question | ImagePanel | LinksPanel | - |
| Location/place keywords | MapPanel | ListPanel | location |
| Creative writing | EditorPanel | - | voice |
| Image uploaded | ImagePreviewPanel | - | camera, upload |
| Code/programming | CodePanel | - | - |
| Health/fitness | ChartPanel | - | - |
| Shopping/product | ProductListPanel | - | - |
| Document uploaded | DocumentPreviewPanel | - | upload |
| No specific context | - | - | - |

---

### MULTI-INTENT COMPOSITIONS

When conversation includes multiple intents, panels stack:

```
User: "I want to plan my week and track my fitness goals"

┌─────────────────────────────────────────────────────────────────┐
│ 💬 Conversation                                               ✕ │
├─────────────────────────────────┬───────────────────────────────┤
│                                 │ 📅 This Week                  │
│ [conversation thread]           │ ┌───────────────────────────┐ │
│                                 │ │ [calendar view]           │ │
│                                 │ └───────────────────────────┘ │
│                                 ├───────────────────────────────┤
│                                 │ 👟 Fitness                    │
│                                 │ ┌───────────────────────────┐ │
│                                 │ │ [activity chart]          │ │
│                                 │ └───────────────────────────┘ │
│ ┌─────────────────────────────┐ │                               │
│ │                         [↑] │ │                               │
│ └─────────────────────────────┘ │                               │
└─────────────────────────────────┴───────────────────────────────┘

Max panels: 3 (to avoid overwhelm)
Priority: Most recent intent gets top position
```

---

### CONTEXT PIVOTS

When conversation changes topic, panels should animate:

```
State 1: Discussing calendar
┌────────┬─────────┐
│  Chat  │ 📅      │
└────────┴─────────┘

User: "actually, help me with my code"

Transition: CalendarPanel slides out right, CodePanel slides in right

State 2: Discussing code
┌────────┬─────────┐
│  Chat  │ 🐍      │
└────────┴─────────┘

The CHAT persists, only the auxiliary panels change.
```

## Appendix B: Major Pages & Default Surfaces

This appendix defines the **static page contexts** and their default tetris compositions before any user interaction.

### Page Types

| Page | Purpose | Default Composition |
|------|---------|---------------------|
| Home | Fresh start, open conversation | Hero input only |
| Project | Working on specific project | CodeEditor + FileTree + Terminal |
| Research | Exploring topics | ProseEditor + WebPanel + NotesPanel |
| Planning | Organizing work | Kanban + CalendarPanel + TasksPanel |
| Review | Evaluating work | DiffView + CodeEditor + CommentsPanel |

---

### HOME PAGE (Default Entry)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│                         ☀️ Sunwell                              │
│                                                                 │
│              ┌──────────────────────────────────┐               │
│              │ What would you like to create? ↑ │               │
│              └──────────────────────────────────┘               │
│                                                                 │
│               [Recent Projects]  [Habits]  [Notes]              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

State: EMPTY
Input Mode: hero (centered, large)
Auxiliary Panels: None (until intent detected)

User says "plan my week" → morphs to Conversation + CalendarPanel
User says "work on pirate game" → morphs to Project workspace
```

---

### PROJECT PAGE

```
┌─────────────────────────────────────────────────────────────────┐
│ 🎮 pirate-game                    [⚙️] [▶️ Run] [📦 Build]     │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────┬────────────────────────────────────────┬─────────┐ │
│ │ 📁 Files │ 📝 main.py                             │ 💬 Ask  │ │
│ │ ├ src/   │ ──────────────────────────────────────│ ─────── │ │
│ │ │ ├ main │ import pygame                          │ Q: How  │ │
│ │ │ └ game │                                        │ do I    │ │
│ │ ├ assets │ class Game:                            │ add a   │ │
│ │ └ tests/ │     def __init__(self):                │ score?  │ │
│ │          │         self.running = True            │         │ │
│ │          │ ────────────────────────────────────── │ ✨ You  │ │
│ │          │ $ python main.py ▐                     │ can add │ │
│ │ [+ New]  │ > Game starting...                     │ a score │ │
│ └──────────┴────────────────────────────────────────┴─────────┘ │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ Ask about this project...                               [↑] │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Default Composition:
  - PRIMARY: CodeEditor (focused file)
  - LEFT: FileTree (collapsible)
  - BOTTOM: Terminal (collapsible)
  - RIGHT: ConversationPanel (mini, expandable)

Input Mode: command (compact, code-aware)

Context-Aware Panels:
  User views an image file → ImagePreviewPanel replaces Code
  User opens test file → TestRunnerPanel appears in right
  User mentions "deploy" → DeploymentPanel slides in
```

---

### RESEARCH PAGE

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔬 Research: Machine Learning Basics              [Save] [Share]│
├─────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────┬───────────────────────────┤
│ │ 📝 Notes                          │ 🌐 Sources                │
│ │ ──────────────────────────────────│ ─────────────────────────│
│ │ # Neural Networks                 │ 📄 Wikipedia: Neural Net  │
│ │                                   │ 📄 3Blue1Brown: Deep Lea  │
│ │ Neural networks are composed of   │ 📄 PyTorch Tutorials      │
│ │ layers of interconnected nodes... │                           │
│ │                                   │ ─────────────────────────│
│ │ ## Key Concepts                   │ 💬 Chat with Sources      │
│ │ - Weights                         │ ─────────────────────────│
│ │ - Activation functions            │ ✨ What would you like to │
│ │ - Backpropagation                 │ know about these sources? │
│ │                                   │                           │
│ └───────────────────────────────────┴───────────────────────────┘
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ Search or ask a question...                             [↑] │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Default Composition:
  - PRIMARY: ProseEditor (notes)
  - RIGHT: WebPanel (sources) + ConversationPanel (mini)

Input Mode: search (dual-purpose: search + chat)

Context-Aware Panels:
  User pastes code → CodePanel appears
  User uploads PDF → DocumentPreviewPanel
  User mentions "diagram" → DiagramPanel (editable)
```

---

### PLANNING PAGE

```
┌─────────────────────────────────────────────────────────────────┐
│ 📋 Planning: Sprint 23                          [Week] [Month]  │
├─────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────┬──────────────────────┤
│ │ 📅 Calendar                            │ ✓ Tasks              │
│ │ ──────────────────────────────────────│ ────────────────────│
│ │    Mon   Tue   Wed   Thu   Fri        │ □ Design API         │
│ │    ─────────────────────────          │ □ Write tests        │
│ │    │ ██ │    │ ██ │    │ ██ │          │ ■ Code review        │
│ │    │9-11│    │2-4 │    │10+ │          │ □ Deploy to staging  │
│ │    ─────────────────────────          │                      │
│ │                                       │ ────────────────────│
│ │ ──────────────────────────────────────│ 📊 Progress          │
│ │         Kanban Board                   │ ▓▓▓▓▓▓░░░░ 60%      │
│ │ ┌──────┬──────┬──────┬──────┐         │                      │
│ │ │ Todo │ WIP  │Review│ Done │         │ 6/10 tasks complete  │
│ │ │ ──── │ ──── │ ──── │ ──── │         │                      │
│ │ │ □ □  │ □    │ □    │ ■ ■  │         │                      │
│ │ └──────┴──────┴──────┴──────┘         │                      │
│ └────────────────────────────────────────┴──────────────────────┘
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ Add task or ask about schedule...                       [↑] │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Default Composition:
  - PRIMARY: Kanban + CalendarPanel (split)
  - RIGHT: TasksPanel + ProgressChart

Input Mode: command (action-oriented)

Context-Aware Panels:
  User mentions "team" → TeamPanel (who's doing what)
  User mentions "deadline" → TimelinePanel
  User mentions "meeting" → Calendar expands
```

---

### PAGE TRANSITION RULES

```
Home → Project:
  1. Hero input shrinks and slides to bottom
  2. FileTree slides in from left
  3. CodeEditor fades in center
  4. Terminal slides up from bottom
  Duration: 400ms staggered

Project → Home:
  1. CodeEditor fades out
  2. Panels slide to edges
  3. Hero input grows and centers
  Duration: 300ms

Home → Conversation (via intent):
  1. Hero input slides down to bottom
  2. ConversationBlock fades in above
  3. Auxiliary panels slide in from right (staggered)
  Duration: 350ms staggered

Conversation → Conversation (panel change):
  1. Old panels slide out right
  2. New panels slide in right
  3. Chat persists (no animation)
  Duration: 250ms
```

---

### INPUT MODE TRANSITIONS

> **Status**: ✅ **Partially Implemented** — `FluidInput.svelte` supports all modes; uses CSS easing (not yet spring physics)

The FluidInput morphs between modes based on context:

| From | To | Trigger | Animation |
|------|----|---------|-----------|
| hero | chat | User sends message, gets conversation response | Shrink + slide down |
| hero | command | User opens project | Shrink + slide to bottom |
| chat | hero | User dismisses conversation | Grow + slide to center |
| command | chat | User asks question in project | Expand slightly + add chat styling |
| any | search | User triggers search (Cmd+K) | Expand + overlay mode |

```
Hero mode:          Chat mode:         Command mode:      Search mode:
┌────────────────┐  ┌──────────────┐   ┌──────────────┐   ╔══════════════╗
│ What would you │  │ Follow up..↑ │   │ cmd> ...   ↑ │   ║ Search...  ↑ ║
│ like to create?│  └──────────────┘   └──────────────┘   ╚══════════════╝
└────────────────┘  
    (centered)         (bottom)          (bottom-left)       (overlay)
```

## Appendix C: Reference Implementations

- **Apple iOS**: Fluid spring animations, shared element transitions
- **Framer**: Spring physics, gesture system
- **Linear**: Clean transitions, keyboard-first with gesture support
- **Figma**: Infinite canvas, zoom/pan, multiplayer cursors
- **Stage Manager (iPadOS)**: Window grouping, spatial persistence

## Appendix D: Motion Specifications

```css
/* Spring curve approximation for CSS fallback */
--spring-snappy: cubic-bezier(0.34, 1.56, 0.64, 1);
--spring-gentle: cubic-bezier(0.22, 1, 0.36, 1);
--spring-bouncy: cubic-bezier(0.68, -0.55, 0.265, 1.55);

/* Duration guidelines */
--duration-instant: 100ms;   /* Micro-interactions */
--duration-fast: 200ms;      /* UI feedback */
--duration-normal: 300ms;    /* Standard transitions */
--duration-slow: 500ms;      /* Large element moves */
--duration-dramatic: 800ms;  /* Shared element morphs */
```

## Appendix E: Gesture Cheat Sheet

```
╔═══════════════════════════════════════════════════════════════════╗
║  PANEL GESTURES                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  Swipe ↓         Minimize to bottom dock                          ║
║  Swipe ←         Minimize to left dock                            ║
║  Swipe →         Minimize to right dock                           ║
║  Pinch in        Collapse to summary                              ║
║  Spread out      Expand to full                                   ║
║  Drag header     Reposition panel                                 ║
║  Drag edge       Resize panel                                     ║
║  Long press      Context menu                                     ║
╠═══════════════════════════════════════════════════════════════════╣
║  CANVAS GESTURES                                                  ║
╠═══════════════════════════════════════════════════════════════════╣
║  Two-finger pan  Navigate canvas                                  ║
║  Pinch           Zoom in/out                                      ║
║  Double-tap      Zoom to fit / reset                              ║
║  Three-finger ↑  Overview mode                                    ║
╠═══════════════════════════════════════════════════════════════════╣
║  INPUT GESTURES                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  Swipe up        Expand input to full                             ║
║  Swipe down      Collapse input                                   ║
║  Long press      Voice input                                      ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Summary of Changes (2026-01-21 Revision)

- Added explicit **Goals/Non-Goals** section
- Added **Design Options Considered** with decision rationale
- Added **Implementation Status** section documenting completed work
- Fixed Naaru reference (was RFC-019, now points to actual code)
- Added status badges to implemented sections
- Updated Phase 1 to include WebSocket integration prerequisite
- Expanded Open Questions with proposed answers

---

*This RFC establishes the vision for Sunwell's next-generation UI. The speculative UI backend (Compositor, Naaru integration) is complete. Remaining work focuses on frontend animation, gestures, and canvas model. Implementation should be incremental, with each phase delivering tangible improvements while building toward the full fluid canvas experience.*
