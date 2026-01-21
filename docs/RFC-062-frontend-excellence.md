# RFC-062: Frontend Excellence — Svelte 5 Migration & S-Tier Patterns

**Status**: Evaluated  
**Created**: 2026-01-20  
**Evaluated**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 95% 🟢  
**Depends on**: RFC-043 (Sunwell Studio), RFC-061 (Holy Light Design System)

---

## Summary

Migrate Sunwell Studio from Svelte 4 legacy patterns to idiomatic Svelte 5 runes, while establishing S-tier frontend practices: proper accessibility, component architecture, error handling, and type safety.

**The goal**: Transform the frontend from "working but dated" (B grade) to "exemplary modern Svelte" (S tier).

**Key changes:**
- Svelte 5 runes (`$state`, `$derived`, `$props`, `$effect`) replace legacy syntax
- Large components decomposed into focused, testable units
- ARIA roles and keyboard navigation throughout
- Error boundaries for graceful degradation
- Constants/enums replace magic strings

---

## Goals

1. **Modern Svelte 5** — Full runes adoption, no legacy `export let` or `createEventDispatcher`
2. **Accessibility (WCAG AA)** — All interactive elements keyboard-navigable with proper ARIA
3. **Component architecture** — No component exceeds 300 lines; single responsibility
4. **Type safety** — Strict TypeScript, discriminated unions for state, no `any`
5. **Testability** — Components isolated and testable in Vitest
6. **Performance** — No regressions; derived state over reactive effects where possible

## Non-Goals

1. **UI redesign** — Layout, colors, spacing handled by RFC-061
2. **New features** — This is refactoring, not feature work
3. **Backend changes** — Event schema unchanged
4. **Router replacement** — Keep current simple routing; SvelteKit migration is separate
5. **State library adoption** — Svelte 5 runes are sufficient; no Redux/Zustand

---

## Motivation

### Current State Assessment

| Category | Grade | Issues |
|----------|-------|--------|
| Architecture | A- | Well-organized, good separation |
| Type Safety | A | Strict TS, comprehensive types |
| Testing | B+ | Setup good, needs more coverage |
| Svelte Best Practices | **C+** | Stuck on Svelte 4 patterns |
| Accessibility | **C** | Missing ARIA in several places |
| Component Design | **B-** | Some components too large |

### The Svelte 5 Gap

We're running `svelte@^5.0.0` but writing Svelte 4 code:

```svelte
<!-- Current: Svelte 4 legacy mode -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let variant: 'primary' | 'secondary' = 'primary';
  export let disabled = false;
  
  const dispatch = createEventDispatcher<{ click: MouseEvent }>();
  
  $: isActive = variant === 'primary' && !disabled;
</script>
```

```svelte
<!-- Target: Svelte 5 runes -->
<script lang="ts">
  interface Props {
    variant?: 'primary' | 'secondary';
    disabled?: boolean;
    onclick?: (e: MouseEvent) => void;
  }
  
  let { variant = 'primary', disabled = false, onclick }: Props = $props();
  
  let isActive = $derived(variant === 'primary' && !disabled);
</script>
```

**Why this matters:**
1. Runes are more explicit about reactivity (easier to reason about)
2. `$props()` provides better TypeScript inference
3. Callback props (`onclick`) are simpler than event dispatchers
4. `$derived` clearly marks computed values
5. `$effect` makes side effects explicit (no hidden `$:` magic)

### The Accessibility Gap

Current tab implementation:

```svelte
<!-- Missing: ARIA roles, keyboard navigation -->
<div class="view-tabs">
  <button class="tab" class:active={activeTab === 'progress'} on:click={() => activeTab = 'progress'}>
    Progress
  </button>
  <!-- ... -->
</div>
```

Required for accessibility:

```svelte
<div class="view-tabs" role="tablist" aria-label="Project views">
  <button 
    role="tab"
    id="tab-progress"
    aria-selected={activeTab === 'progress'}
    aria-controls="panel-progress"
    tabindex={activeTab === 'progress' ? 0 : -1}
    onclick={() => activeTab = 'progress'}
    onkeydown={handleTabKeydown}
  >
    Progress
  </button>
  <!-- ... -->
</div>
<div 
  role="tabpanel"
  id="panel-progress"
  aria-labelledby="tab-progress"
  hidden={activeTab !== 'progress'}
>
  <!-- content -->
</div>
```

### The Component Size Problem

`Project.svelte` is **1528 lines** — a monolithic component handling:
- Project header and navigation
- Idle state (landing page)
- Working state (agent running)
- Done state (completion view)
- Error state
- Memory view
- Pipeline view
- File browser
- File preview modal

This violates single responsibility, makes testing difficult, and increases cognitive load.

---

## Design Options

### Option A: Big-Bang Migration ✅ RECOMMENDED

Migrate all components in a focused sprint (~5-7 days), shipping when complete.

**Pros:**
- ✅ Clean cutover — no mixed Svelte 4/5 patterns in codebase
- ✅ Faster total duration (5-7 days vs 12 days)
- ✅ Mental model stays consistent throughout
- ✅ No discipline required to "finish later"
- ✅ Low actual risk — UI is early-stage, half doesn't work yet anyway

**Cons:**
- All-or-nothing (but acceptable given current state)
- svelte-check errors pile up initially (but manageable for 28 components)

**Why this works for us**: The UI is greenfield — we're building, not maintaining. There's no production traffic, no users relying on current behavior, and broken things are already broken. The "risk" of a big-bang rewrite assumes a mature codebase; we don't have that.

### Option B: Incremental Phase-by-Phase Migration

Migrate in 6 phases over ~12 days, starting with foundation, then leaf components, then composite components, etc.

**Pros:**
- Each phase independently testable
- Team can learn patterns gradually

**Cons:**
- ❌ Longer duration (12 days)
- ❌ Mixed patterns in codebase for 2 weeks
- ❌ Cognitive overhead switching between Svelte 4/5 styles
- ❌ Requires discipline to complete all phases

**Not recommended** — The overhead of maintaining two patterns isn't worth it when we can just fix everything at once.

### Option C: Opportunistic "Fix on Touch"

Only migrate components when making feature changes.

**Pros:**
- No dedicated migration time
- Changes bundled with features

**Cons:**
- ❌ Mixed patterns persist indefinitely
- ❌ Tech debt accumulates
- ❌ New developers confused by two patterns
- ❌ Accessibility never gets fixed (no feature drives it)

**Rejected** — Legacy patterns would persist for months/years.

### Recommendation

**Option A (Big-Bang)** is the right choice for our stage. Benefits:
- Ship faster (5-7 days vs 12)
- Clean, consistent codebase from day one
- No "finish the migration" hanging over us
- Risk is low because the UI is still being built

---

## Risks & Mitigations

> **Note**: Risk assessment reflects that this is an early-stage UI with incomplete functionality. Traditional "migration risk" concerns are lower than they would be for a production system.

### Risk 1: Compiler Errors Pile Up

**Risk**: Enabling `runes: true` causes many errors at once.

**Likelihood**: High  
**Impact**: Low (expected, not blocking)

**Mitigation**:
1. Run `svelte-check` before enabling — know the baseline
2. Enable runes mode first, fix all errors before moving on
3. Expect ~50-100 errors initially; this is normal
4. Use find-replace for mechanical changes (`on:click` → `onclick`)

### Risk 2: Store Migration Breaks Subscriptions

**Risk**: Converting stores to `.svelte.ts` breaks components using `$storeName` syntax.

**Likelihood**: Medium  
**Impact**: Medium

**Mitigation**:
1. Migrate stores and their consumers together (same commit)
2. Search for all `$storeName` usages before migrating each store
3. `agent.ts` has the most subscribers — do it carefully but not last

### Risk 3: Slot → Snippet Confusion

**Risk**: Team unfamiliar with snippet syntax makes mistakes.

**Likelihood**: Low  
**Impact**: Low

**Mitigation**:
1. Cheatsheet in appendix covers this
2. Pattern is mechanical: `<slot>` → `{@render children()}`
3. TypeScript will catch most errors

### Risk 4: Accessibility Scope Creep

**Risk**: Fixing a11y reveals UX issues that need design changes.

**Likelihood**: Medium  
**Impact**: Low

**Mitigation**:
1. Only add ARIA attributes and keyboard handlers
2. Log UX issues for follow-up, don't fix in this RFC
3. RFC-061 handles visual/interaction design

### Rollback Strategy

**Full rollback** (if needed):
```bash
git checkout pre-rfc062-migration
```

**Reality check**: We probably won't need this. The UI is early-stage — if something breaks, we fix it and move on. There's no production to protect.

---

## Technical Specification

### 1. Svelte 5 Runes Migration

#### Enable Runes Mode

```js
// svelte.config.js
export default {
  preprocess: vitePreprocess(),
  compilerOptions: {
    runes: true,  // Enable Svelte 5 runes
  },
};
```

#### Props Pattern

```typescript
// Before
export let variant: ButtonVariant = 'primary';
export let disabled = false;

// After
interface Props {
  variant?: ButtonVariant;
  disabled?: boolean;
  onclick?: (e: MouseEvent) => void;
  children?: Snippet;  // For slot replacement
}

let { 
  variant = 'primary', 
  disabled = false, 
  onclick,
  children 
}: Props = $props();
```

#### Reactive State Pattern

```typescript
// Before
let count = 0;
$: doubled = count * 2;
$: {
  console.log('count changed:', count);
}

// After
let count = $state(0);
let doubled = $derived(count * 2);

$effect(() => {
  console.log('count changed:', count);
});
```

#### Store Subscription Pattern

```typescript
// Before (auto-subscription with $)
$: currentTask = $agentState.tasks[$agentState.currentTaskIndex];

// After (explicit subscription)
import { agentState } from '../stores/agent.svelte';

let currentTask = $derived(agentState.tasks[agentState.currentTaskIndex]);
```

Note: Stores will need migration to `*.svelte.ts` files with `$state` at module level.

#### Event Handler Pattern

```svelte
<!-- Before -->
<button on:click={handleClick} on:keydown={handleKeydown}>

<!-- After -->
<button onclick={handleClick} onkeydown={handleKeydown}>
```

```svelte
<!-- Before (dispatching events) -->
<script>
  const dispatch = createEventDispatcher<{ select: { id: string } }>();
  function handleClick() {
    dispatch('select', { id: item.id });
  }
</script>

<!-- After (callback props) -->
<script>
  interface Props {
    onselect?: (detail: { id: string }) => void;
  }
  let { onselect }: Props = $props();
  
  function handleClick() {
    onselect?.({ id: item.id });
  }
</script>
```

### 2. Component Decomposition

#### Project.svelte Breakdown

```
src/routes/Project.svelte (orchestrator, ~150 lines)
├── src/components/project/ProjectHeader.svelte (~50 lines)
├── src/components/project/ProjectIdle.svelte (~200 lines)
│   ├── ProjectInfo
│   ├── LastRunStatus
│   ├── QuickActions
│   └── GoalInput
├── src/components/project/ProjectWorking.svelte (~200 lines)
│   ├── StatusHeader
│   ├── PlanningPanel (existing)
│   ├── Progress (existing)
│   └── WorkingActions
├── src/components/project/ProjectDone.svelte (~150 lines)
│   ├── DoneHeader
│   ├── DoneActions
│   └── DoneFiles
├── src/components/project/ProjectError.svelte (~50 lines)
├── src/components/project/MemoryView.svelte (~250 lines)
│   ├── MemoryStats
│   ├── LearningsList
│   ├── DeadEndsList
│   └── DecisionsList
├── src/components/project/PipelineView.svelte (~100 lines)
└── src/components/project/FilePreviewModal.svelte (~80 lines)
```

#### Component Size Guidelines

| Threshold | Action |
|-----------|--------|
| < 100 lines | ✅ Ideal |
| 100-200 lines | ✅ Acceptable for complex logic |
| 200-300 lines | ⚠️ Consider splitting |
| > 300 lines | ❌ Must split |

### 3. Accessibility Implementation

#### Tabs Component

```svelte
<!-- Tabs.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Tab {
    id: string;
    label: string;
  }
  
  interface Props {
    tabs: Tab[];
    activeTab: string;
    onchange: (tabId: string) => void;
    children: Snippet<[string]>;  // Receives active tab ID
    label?: string;
  }
  
  let { tabs, activeTab, onchange, children, label = 'Tabs' }: Props = $props();
  
  function handleKeydown(e: KeyboardEvent, index: number) {
    let newIndex = index;
    
    switch (e.key) {
      case 'ArrowRight':
        newIndex = (index + 1) % tabs.length;
        break;
      case 'ArrowLeft':
        newIndex = (index - 1 + tabs.length) % tabs.length;
        break;
      case 'Home':
        newIndex = 0;
        break;
      case 'End':
        newIndex = tabs.length - 1;
        break;
      default:
        return;
    }
    
    e.preventDefault();
    onchange(tabs[newIndex].id);
    // Focus the new tab
    document.getElementById(`tab-${tabs[newIndex].id}`)?.focus();
  }
</script>

<div class="tabs">
  <div class="tab-list" role="tablist" aria-label={label}>
    {#each tabs as tab, i}
      <button
        role="tab"
        id="tab-{tab.id}"
        aria-selected={activeTab === tab.id}
        aria-controls="panel-{tab.id}"
        tabindex={activeTab === tab.id ? 0 : -1}
        onclick={() => onchange(tab.id)}
        onkeydown={(e) => handleKeydown(e, i)}
        class="tab"
        class:active={activeTab === tab.id}
      >
        {tab.label}
      </button>
    {/each}
  </div>
  
  {#each tabs as tab}
    <div
      role="tabpanel"
      id="panel-{tab.id}"
      aria-labelledby="tab-{tab.id}"
      hidden={activeTab !== tab.id}
      tabindex="0"
      class="tab-panel"
    >
      {#if activeTab === tab.id}
        {@render children(tab.id)}
      {/if}
    </div>
  {/each}
</div>
```

#### Focus Management

```typescript
// lib/a11y.ts

/** Trap focus within a container (for modals) */
export function trapFocus(container: HTMLElement): () => void {
  const focusable = container.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }
  
  container.addEventListener('keydown', handleKeydown);
  first?.focus();
  
  return () => container.removeEventListener('keydown', handleKeydown);
}

/** Announce to screen readers */
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite') {
  const el = document.createElement('div');
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', priority);
  el.setAttribute('aria-atomic', 'true');
  el.className = 'sr-only';
  el.textContent = message;
  
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1000);
}
```

#### ARIA Checklist

| Component | Required ARIA |
|-----------|---------------|
| Tabs | `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, `aria-controls` |
| Modal | `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, focus trap |
| Progress | `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax` |
| File Tree | `role="tree"`, `role="treeitem"`, `aria-expanded`, `aria-selected` |
| Alerts | `role="alert"` or `aria-live="polite"` |
| Loading | `aria-busy="true"`, `aria-describedby` |

### 4. Constants & Enums

```typescript
// lib/constants.ts

export const AgentStatus = {
  IDLE: 'idle',
  STARTING: 'starting',
  PLANNING: 'planning',
  RUNNING: 'running',
  DONE: 'done',
  ERROR: 'error',
} as const;

export type AgentStatus = typeof AgentStatus[keyof typeof AgentStatus];

export const PlanningPhase = {
  GENERATING: 'generating',
  SCORING: 'scoring',
  REFINING: 'refining',
  COMPLETE: 'complete',
} as const;

export type PlanningPhase = typeof PlanningPhase[keyof typeof PlanningPhase];

export const TaskStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETE: 'complete',
  FAILED: 'failed',
} as const;

export type TaskStatus = typeof TaskStatus[keyof typeof TaskStatus];

export const ViewTab = {
  PROGRESS: 'progress',
  PIPELINE: 'pipeline',
  MEMORY: 'memory',
} as const;

export type ViewTab = typeof ViewTab[keyof typeof ViewTab];
```

Usage:

```typescript
// Before
if ($agentState.status === 'planning') { ... }

// After
import { AgentStatus } from '$lib/constants';
if ($agentState.status === AgentStatus.PLANNING) { ... }
```

### 5. Error Boundaries

```svelte
<!-- ErrorBoundary.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    children: Snippet;
    fallback?: Snippet<[Error]>;
    onError?: (error: Error) => void;
  }
  
  let { children, fallback, onError }: Props = $props();
  
  let error = $state<Error | null>(null);
  
  // Svelte 5 error boundary using $effect.root
  $effect.root(() => {
    return () => {
      // Cleanup on unmount
    };
  });
  
  function handleError(e: Error) {
    error = e;
    onError?.(e);
    console.error('[ErrorBoundary]', e);
  }
  
  function reset() {
    error = null;
  }
</script>

{#if error}
  {#if fallback}
    {@render fallback(error)}
  {:else}
    <div class="error-boundary" role="alert">
      <h3>Something went wrong</h3>
      <p>{error.message}</p>
      <button onclick={reset}>Try again</button>
    </div>
  {/if}
{:else}
  {@render children()}
{/if}
```

Note: Svelte 5's error boundary support is still evolving. We may need to use `onMount` with try-catch for async operations.

### 6. Store Migration to Svelte 5

```typescript
// stores/agent.svelte.ts (note: .svelte.ts extension)

import { AgentStatus } from '$lib/constants';
import type { AgentState, Task, PlanCandidate } from '$lib/types';

// Module-level reactive state
let state = $state<AgentState>({
  status: AgentStatus.IDLE,
  goal: null,
  tasks: [],
  currentTaskIndex: -1,
  totalTasks: 0,
  startTime: null,
  endTime: null,
  error: null,
  learnings: [],
  concepts: [],
  planningCandidates: [],
  selectedCandidate: null,
  refinementRounds: [],
  planningProgress: null,
});

// Derived values
export const isRunning = $derived(
  [AgentStatus.STARTING, AgentStatus.PLANNING, AgentStatus.RUNNING].includes(state.status)
);

export const isDone = $derived(state.status === AgentStatus.DONE);
export const hasError = $derived(state.status === AgentStatus.ERROR);

export const progress = $derived(() => {
  if (state.totalTasks === 0) return 0;
  const completed = state.tasks.filter(t => t.status === 'complete').length;
  return Math.round((completed / state.totalTasks) * 100);
});

export const duration = $derived(() => {
  if (!state.startTime) return 0;
  const end = state.endTime ?? Date.now();
  return Math.round((end - state.startTime) / 1000);
});

// Actions
export function resetAgent() {
  state = { ...initialState };
}

export function updateState(partial: Partial<AgentState>) {
  Object.assign(state, partial);
}

// Export readonly state for components
export const agentState = {
  get status() { return state.status; },
  get goal() { return state.goal; },
  get tasks() { return state.tasks; },
  // ... etc
};
```

---

## Migration Strategy

> **Approach**: Bottom-up. Build the foundation artifacts first, then everything above them compiles cleanly.

### Dependency Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 6: ROUTES (orchestrators)                            │
│  Project.svelte, Home.svelte, Preview.svelte, Planning.svelte│
├─────────────────────────────────────────────────────────────┤
│  Layer 5: FEATURE COMPONENTS (domain-specific)              │
│  PlanningPanel, DagCanvas, MemoryView, FileTree             │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: COMPOSITE COMPONENTS (combine atomics)            │
│  Panel, InputBar, LearningsPanel, CandidateComparison       │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: ATOMIC COMPONENTS (leaf nodes)                    │
│  Button, Logo, Progress, RisingMotes                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: STORES (reactive state)                           │
│  agent.svelte.ts, app.svelte.ts, dag.svelte.ts, etc.        │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: UTILITIES (pure functions)                        │
│  lib/a11y.ts, lib/format.ts                                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: TYPES + CONSTANTS (the contract)                  │
│  lib/types.ts, lib/constants.ts                             │
├─────────────────────────────────────────────────────────────┤
│  Layer -1: CONFIG (enables everything)                      │
│  svelte.config.js (runes: true), tsconfig.json              │
└─────────────────────────────────────────────────────────────┘
```

**Rule**: Each layer only imports from layers below it. Never up.

---

### Layer -1: Config (30 min)

Enable Svelte 5 runes mode. Everything else depends on this.

```js
// svelte.config.js
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  compilerOptions: {
    runes: true,
  },
};
```

After this, `svelte-check` will show errors for all legacy patterns. That's expected.

**Commit**: `config: enable Svelte 5 runes mode`

---

### Layer 0: Types + Constants (1 hour)

The foundation everything else builds on. These files have **zero imports** from the codebase.

#### `lib/constants.ts`

```typescript
// Agent lifecycle states
export const AgentStatus = {
  IDLE: 'idle',
  STARTING: 'starting',
  PLANNING: 'planning',
  RUNNING: 'running',
  DONE: 'done',
  ERROR: 'error',
} as const;
export type AgentStatus = typeof AgentStatus[keyof typeof AgentStatus];

// Planning phases
export const PlanningPhase = {
  GENERATING: 'generating',
  SCORING: 'scoring',
  REFINING: 'refining',
  COMPLETE: 'complete',
} as const;
export type PlanningPhase = typeof PlanningPhase[keyof typeof PlanningPhase];

// Task states
export const TaskStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETE: 'complete',
  FAILED: 'failed',
} as const;
export type TaskStatus = typeof TaskStatus[keyof typeof TaskStatus];

// UI view tabs
export const ViewTab = {
  PROGRESS: 'progress',
  PIPELINE: 'pipeline',
  MEMORY: 'memory',
} as const;
export type ViewTab = typeof ViewTab[keyof typeof ViewTab];

// Button variants
export const ButtonVariant = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  GHOST: 'ghost',
} as const;
export type ButtonVariant = typeof ButtonVariant[keyof typeof ButtonVariant];

// Size scale
export const Size = {
  SM: 'sm',
  MD: 'md',
  LG: 'lg',
} as const;
export type Size = typeof Size[keyof typeof Size];
```

#### `lib/types.ts` (extend existing)

Ensure all interfaces use the const types:

```typescript
import type { AgentStatus, TaskStatus, PlanningPhase } from './constants';

export interface AgentState {
  status: AgentStatus;
  goal: string | null;
  tasks: Task[];
  currentTaskIndex: number;
  // ... etc, all typed
}

export interface Task {
  id: string;
  title: string;
  status: TaskStatus;
  // ...
}
```

**Commit**: `types: add constants and strengthen type definitions`

---

### Layer 1: Utilities (1 hour)

Pure functions with no side effects. Only import from Layer 0.

#### `lib/a11y.ts`

```typescript
/** Trap focus within a container (for modals) */
export function trapFocus(container: HTMLElement): () => void {
  const focusable = container.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }

  container.addEventListener('keydown', handleKeydown);
  first?.focus();
  return () => container.removeEventListener('keydown', handleKeydown);
}

/** Announce to screen readers */
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite') {
  const el = document.createElement('div');
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', priority);
  el.setAttribute('aria-atomic', 'true');
  el.className = 'sr-only';
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1000);
}

/** Generate unique ID for ARIA relationships */
let idCounter = 0;
export function uniqueId(prefix = 'id'): string {
  return `${prefix}-${++idCounter}`;
}
```

#### `lib/format.ts` (if needed)

```typescript
/** Format duration in seconds to human readable */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

/** Format timestamp to relative time */
export function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const diff = now - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
```

**Commit**: `lib: add a11y and formatting utilities`

---

### Layer 2: Stores (2-3 hours)

Reactive state containers. Import from Layers 0-1. All stores become `.svelte.ts` files.

**Order matters**: Migrate stores that have fewer dependencies first.

| Store | Depends On | Complexity |
|-------|------------|------------|
| `layout.svelte.ts` | None | Low |
| `app.svelte.ts` | None | Low |
| `prompts.svelte.ts` | None | Low |
| `project.svelte.ts` | None | Medium |
| `dag.svelte.ts` | types | Medium |
| `agent.svelte.ts` | types, constants, dag | High |

Each store follows this pattern:

```typescript
// stores/layout.svelte.ts
import type { LayoutMode } from '$lib/types';

// Private mutable state
let _mode = $state<LayoutMode>('code');
let _sidebarOpen = $state(true);

// Public readonly getters
export const layout = {
  get mode() { return _mode; },
  get sidebarOpen() { return _sidebarOpen; },
};

// Actions
export function setMode(mode: LayoutMode) { _mode = mode; }
export function toggleSidebar() { _sidebarOpen = !_sidebarOpen; }
```

**Commit**: `stores: migrate all stores to Svelte 5 runes`

---

### Layer 3: Atomic Components (2-3 hours)

Leaf components with **no child components**. Only import from Layers 0-2.

| Component | Lines | Notes |
|-----------|-------|-------|
| `Button.svelte` | 237 | Core interactive element |
| `Logo.svelte` | ~50 | Pure visual |
| `Progress.svelte` | 240 | Needs ARIA progressbar |
| `RisingMotes.svelte` | ~80 | Animation only |
| `PlanningProgress.svelte` | ~80 | Visual indicator |
| `MemoryGraph.svelte` | ~100 | Canvas/SVG |

**Pattern**:
```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { ButtonVariant, Size } from '$lib/constants';
  
  interface Props {
    variant?: ButtonVariant;
    size?: Size;
    disabled?: boolean;
    onclick?: (e: MouseEvent) => void;
    children: Snippet;
  }
  
  let { variant = 'primary', size = 'md', disabled = false, onclick, children }: Props = $props();
</script>
```

**Commit**: `components: migrate atomic components to Svelte 5`

---

### Layer 4: Composite Components (2-3 hours)

Components that **compose atomic components**. Import from Layers 0-3.

| Component | Lines | Contains |
|-----------|-------|----------|
| `Panel.svelte` | ~100 | Container with header |
| `InputBar.svelte` | ~150 | Input + Button |
| `LearningsPanel.svelte` | ~213 | Panel + list items |
| `SavedPrompts.svelte` | 317 | Panel + list + actions |
| `RecentProjects.svelte` | 524 | List + items (consider splitting) |
| `ErrorBoundary.svelte` | ~50 | Wrapper component |

**Commit**: `components: migrate composite components to Svelte 5`

---

### Layer 5: Feature Components (3-4 hours)

Domain-specific components. Import from Layers 0-4.

| Component | Lines | Domain |
|-----------|-------|--------|
| `FileTree.svelte` | 338 | File browser |
| `PlanningPanel.svelte` | ~200 | Planning |
| `CandidateComparison.svelte` | ~200 | Planning |
| `RefinementTimeline.svelte` | ~100 | Planning |
| `DagCanvas.svelte` | 316 | Pipeline |
| `DagNode.svelte` | 270 | Pipeline |
| `DagEdge.svelte` | ~100 | Pipeline |
| `DagDetail.svelte` | 401 | Pipeline (consider splitting) |
| `DagControls.svelte` | ~100 | Pipeline |

Also create new **accessible primitives**:

| New Component | Purpose |
|---------------|---------|
| `Tabs.svelte` | ARIA tablist/tab/tabpanel |
| `Modal.svelte` | Focus trap, aria-modal |

**Commit**: `components: migrate feature components to Svelte 5`

---

### Layer 6: Routes (3-4 hours)

Page-level orchestrators. Import from all layers below.

**Before**: `Project.svelte` is 1527 lines handling everything.

**After**: Extract into `components/project/`:

```
routes/Project.svelte (~150 lines, orchestrator)
├── components/project/ProjectHeader.svelte (~50)
├── components/project/ProjectIdle.svelte (~200)
├── components/project/ProjectWorking.svelte (~200)
├── components/project/ProjectDone.svelte (~150)
├── components/project/ProjectError.svelte (~50)
├── components/project/MemoryView.svelte (~250)
├── components/project/PipelineView.svelte (~100)
└── components/project/FilePreviewModal.svelte (~80)
```

Also split layouts:
```
layouts/BaseLayout.svelte (keep simple)
layouts/CodeLayout.svelte
layouts/NovelLayout.svelte
```

**Commit**: `routes: decompose routes into focused components`

---

### Accessibility Pass (integrated above)

Accessibility is built into each layer, not a separate phase:

| Layer | A11y Work |
|-------|-----------|
| Layer 1 | `trapFocus`, `announce`, `uniqueId` utilities |
| Layer 3 | Button focus states, disabled handling |
| Layer 4 | Panel aria-labelledby |
| Layer 5 | FileTree tree/treeitem roles, Tabs tablist |
| Layer 6 | Page-level aria-live regions |

---

### Validation

```bash
# Zero legacy patterns
grep -r "export let" src --include="*.svelte" | wc -l  # 0
grep -r "createEventDispatcher" src --include="*.svelte" | wc -l  # 0
grep -r "on:click" src --include="*.svelte" | wc -l  # 0

# Runes are used
grep -r "\$state\|\$derived\|\$props" src --include="*.svelte*" | wc -l  # > 50

# No huge components
find src -name "*.svelte" -exec wc -l {} + | awk '$1 > 300 {print}'  # empty

# Layer violations (should find nothing)
# Check that atomics don't import composites, etc.

# Tests pass
pnpm test
pnpm svelte-check
```

---

## Testing Strategy

### Unit Tests

```typescript
// Button.test.ts
import { render, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import Button from './Button.svelte';

describe('Button', () => {
  it('renders with default props', () => {
    const { getByRole } = render(Button, { children: () => 'Click me' });
    expect(getByRole('button')).toHaveTextContent('Click me');
  });
  
  it('calls onclick when clicked', async () => {
    const onclick = vi.fn();
    const { getByRole } = render(Button, { onclick, children: () => 'Click' });
    
    await fireEvent.click(getByRole('button'));
    expect(onclick).toHaveBeenCalledOnce();
  });
  
  it('is disabled when disabled prop is true', () => {
    const { getByRole } = render(Button, { disabled: true, children: () => 'Click' });
    expect(getByRole('button')).toBeDisabled();
  });
  
  it('applies variant class', () => {
    const { getByRole } = render(Button, { variant: 'ghost', children: () => 'Click' });
    expect(getByRole('button')).toHaveClass('ghost');
  });
});
```

### Accessibility Tests

```typescript
// a11y.test.ts
import { render } from '@testing-library/svelte';
import { axe, toHaveNoViolations } from 'jest-axe';
import { describe, it, expect } from 'vitest';

expect.extend(toHaveNoViolations);

describe('Accessibility', () => {
  it('Button has no a11y violations', async () => {
    const { container } = render(Button, { children: () => 'Click' });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
  
  it('Tabs have proper ARIA', async () => {
    const { container, getByRole } = render(Tabs, {
      tabs: [
        { id: 'a', label: 'Tab A' },
        { id: 'b', label: 'Tab B' },
      ],
      activeTab: 'a',
      onchange: () => {},
      children: () => {},
    });
    
    expect(getByRole('tablist')).toBeInTheDocument();
    expect(getByRole('tab', { name: 'Tab A' })).toHaveAttribute('aria-selected', 'true');
    expect(getByRole('tabpanel')).toBeInTheDocument();
    
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

### Keyboard Navigation Tests

```typescript
// keyboard.test.ts
import { render, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import Tabs from './Tabs.svelte';

describe('Tabs keyboard navigation', () => {
  const tabs = [
    { id: 'a', label: 'Tab A' },
    { id: 'b', label: 'Tab B' },
    { id: 'c', label: 'Tab C' },
  ];
  
  it('ArrowRight moves to next tab', async () => {
    const onchange = vi.fn();
    const { getByRole } = render(Tabs, { tabs, activeTab: 'a', onchange, children: () => {} });
    
    const tabA = getByRole('tab', { name: 'Tab A' });
    tabA.focus();
    
    await fireEvent.keyDown(tabA, { key: 'ArrowRight' });
    expect(onchange).toHaveBeenCalledWith('b');
  });
  
  it('ArrowRight wraps from last to first', async () => {
    const onchange = vi.fn();
    const { getByRole } = render(Tabs, { tabs, activeTab: 'c', onchange, children: () => {} });
    
    const tabC = getByRole('tab', { name: 'Tab C' });
    tabC.focus();
    
    await fireEvent.keyDown(tabC, { key: 'ArrowRight' });
    expect(onchange).toHaveBeenCalledWith('a');
  });
  
  it('Home moves to first tab', async () => {
    const onchange = vi.fn();
    const { getByRole } = render(Tabs, { tabs, activeTab: 'c', onchange, children: () => {} });
    
    const tabC = getByRole('tab', { name: 'Tab C' });
    tabC.focus();
    
    await fireEvent.keyDown(tabC, { key: 'Home' });
    expect(onchange).toHaveBeenCalledWith('a');
  });
});
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Svelte 5 adoption | 100% | No `export let`, no `createEventDispatcher`, no `$:` |
| Component size | < 300 lines | Linter rule or manual audit |
| Accessibility | WCAG AA | axe-core audit passes |
| Test coverage | > 70% | Vitest coverage report |
| Type safety | 100% strict | No `any`, no `@ts-ignore` |
| Performance | No regression | Lighthouse score ≥ 90 |
| LOC reduction | ~15-20% | Current ~7400 → target ~6000-6300 via decomposition |
| Max component | ≤ 300 lines | Project.svelte: 1527 → ~150 (orchestrator) |

---

## Rejected Alternatives

These alternatives were considered but rejected for this RFC:

### 1. SvelteKit Migration

**What it is**: Replace current simple router with full SvelteKit framework.

**Rejected because:**
- Much larger scope (routing, SSR, deployment, file-based routing)
- Current simple router is sufficient for Tauri desktop app
- Would require rearchitecting navigation, data loading, and layout system
- Can be a separate RFC if SSR or advanced routing is ever needed

**Recommendation**: Consider for future RFC if we need SSR or web deployment.

### 2. Svelte 4 Compatibility Mode

**What it is**: Keep writing Svelte 4 patterns, defer migration indefinitely.

**Rejected because:**
- Delays inevitable migration (Svelte 4 patterns are deprecated)
- Misses performance benefits of runes
- Creates compounding tech debt
- New developers learn outdated patterns
- Svelte 5 features (snippets, fine-grained reactivity) unavailable

**Recommendation**: Never — tech debt compounds.

### 3. State Library (Zustand/Nanostores)

**What it is**: Adopt an external state management library instead of Svelte 5 runes.

**Rejected because:**
- Svelte 5 runes provide sufficient reactivity for our needs
- Additional dependency adds bundle size (~3-5KB)
- Existing stores work well; migration path to `.svelte.ts` is clear
- Would create pattern inconsistency (some state in library, some in Svelte)

**Recommendation**: Only reconsider if we add complex cross-cutting state requirements.

### 4. Component Library (Skeleton, shadcn-svelte)

**What it is**: Adopt a pre-built component library instead of custom components.

**Rejected because:**
- RFC-061 defines custom "Holy Light" design system
- Component libraries would need heavy customization to match brand
- Adds significant bundle size (~50-100KB)
- We'd still need to migrate their patterns to Svelte 5 anyway

**Recommendation**: Never — design system is core to Sunwell identity.

---

## Implementation Checklist

### Layer -1: Config
- [ ] Enable `runes: true` in svelte.config.js

### Layer 0: Types + Constants
- [ ] Create `lib/constants.ts` (AgentStatus, TaskStatus, PlanningPhase, ViewTab, ButtonVariant, Size)
- [ ] Update `lib/types.ts` to use const types

### Layer 1: Utilities
- [ ] Create `lib/a11y.ts` (trapFocus, announce, uniqueId)
- [ ] Create `lib/format.ts` if needed (formatDuration, formatRelativeTime)

### Layer 2: Stores
- [ ] `stores/layout.svelte.ts`
- [ ] `stores/app.svelte.ts`
- [ ] `stores/prompts.svelte.ts`
- [ ] `stores/project.svelte.ts`
- [ ] `stores/dag.svelte.ts`
- [ ] `stores/agent.svelte.ts`

### Layer 3: Atomic Components
- [ ] Button.svelte
- [ ] Logo.svelte
- [ ] Progress.svelte (add ARIA progressbar)
- [ ] RisingMotes.svelte
- [ ] PlanningProgress.svelte
- [ ] MemoryGraph.svelte

### Layer 4: Composite Components
- [ ] Panel.svelte
- [ ] InputBar.svelte
- [ ] ErrorBoundary.svelte
- [ ] LearningsPanel.svelte
- [ ] SavedPrompts.svelte
- [ ] RecentProjects.svelte (consider splitting)

### Layer 5: Feature Components
- [ ] FileTree.svelte (add tree roles)
- [ ] Tabs.svelte (new, ARIA tablist)
- [ ] Modal.svelte (new, focus trap)
- [ ] PlanningPanel.svelte
- [ ] CandidateComparison.svelte
- [ ] RefinementTimeline.svelte
- [ ] DagCanvas.svelte
- [ ] DagNode.svelte
- [ ] DagEdge.svelte
- [ ] DagDetail.svelte (consider splitting)
- [ ] DagControls.svelte

### Layer 6: Routes
- [ ] Extract `components/project/ProjectHeader.svelte`
- [ ] Extract `components/project/ProjectIdle.svelte`
- [ ] Extract `components/project/ProjectWorking.svelte`
- [ ] Extract `components/project/ProjectDone.svelte`
- [ ] Extract `components/project/ProjectError.svelte`
- [ ] Extract `components/project/MemoryView.svelte`
- [ ] Extract `components/project/PipelineView.svelte`
- [ ] Extract `components/project/FilePreviewModal.svelte`
- [ ] Refactor `routes/Project.svelte` to orchestrator
- [ ] Review `routes/Home.svelte` (351 lines)
- [ ] Review `routes/Preview.svelte` (362 lines)

### Final Validation
- [ ] Zero `export let` in .svelte files
- [ ] Zero `createEventDispatcher` imports
- [ ] Zero `on:click` (use `onclick`)
- [ ] All components < 300 lines
- [ ] `pnpm svelte-check` passes
- [ ] `pnpm test` passes

---

## Evidence Summary

Codebase analysis performed 2026-01-20 to validate claims:

| Claim | Evidence | Verified |
|-------|----------|----------|
| Svelte 5 installed | `package.json:26` — `"svelte": "^5.0.0"` | ✅ |
| Runes not enabled | `svelte.config.js` — missing `compilerOptions.runes` | ✅ |
| Zero runes usage | `grep $state\|$derived\|$props\|$effect` → 0 matches | ✅ |
| 97 legacy patterns | `grep export let\|createEventDispatcher\|$:` → 97 matches across 22 files | ✅ |
| Project.svelte size | `wc -l` → 1527 lines | ✅ |
| 7 components > 300 lines | Project(1527), RecentProjects(524), DagDetail(401), Preview(362), Home(351), FileTree(338), SavedPrompts(317) | ✅ |
| Limited ARIA | `grep role=\|aria-` → 21 matches across 11 files | ✅ |
| Test setup exists | `vitest.config.ts`, `src/test/setup.ts` with Tauri mocks | ✅ |
| Stores use writable | `agent.ts:7` — `import { writable, derived }` | ✅ |

---

## References

- [Svelte 5 Runes Documentation](https://svelte.dev/docs/svelte/runes)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [WAI-ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [Testing Library Svelte](https://testing-library.com/docs/svelte-testing-library/intro/)
- RFC-061: Holy Light Design System
- RFC-043: Sunwell Studio

---

## Appendix: Svelte 5 Migration Cheatsheet

| Svelte 4 | Svelte 5 |
|----------|----------|
| `export let prop` | `let { prop } = $props()` |
| `$: derived = ...` | `let derived = $derived(...)` |
| `$: { sideEffect() }` | `$effect(() => { sideEffect() })` |
| `on:click={handler}` | `onclick={handler}` |
| `createEventDispatcher()` | Callback props |
| `<slot />` | `{@render children()}` |
| `<slot name="x" />` | `{@render x?.()}` |
| `$$props` | `$props()` |
| `$$restProps` | `let { ...rest } = $props()` |
| `bind:this` | `bind:this` (unchanged) |
| `use:action` | `use:action` (unchanged) |
