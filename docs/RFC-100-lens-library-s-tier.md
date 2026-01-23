# RFC-100: Lens Library S-Tier — From Functional to Gorgeous

**Status**: Evaluated  
**Author**: Lawrence Lane  
**Created**: 2026-01-23  
**Target Version**: v1.x  
**Confidence**: 92% 🟢

---

## Summary

Elevate the Lens Library page and its component ecosystem from functional to S-tier quality. Currently, the library provides correct CRUD, filtering, and versioning — but lacks visual hierarchy, motion, discovery features, and the "magical" feel that distinguishes S-tier components.

**Goal**: When a user opens the Lens Library, they should feel like they're browsing a curated collection of powerful expertise containers — not a generic admin panel. Every interaction should reinforce the "Holy Light" aesthetic with purposeful motion, smart discovery, and delightful micro-interactions.

---

## Goals and Non-Goals

### Goals

1. **Visual Hierarchy** — Featured lenses, power indicators, scannable card design
2. **Motion & Delight** — Staggered entrances, hover motes, loading skeletons
3. **Discovery** — Related lenses, usage sparklines, smart search suggestions
4. **Interaction Polish** — Keyboard navigation, hover previews, context menus
5. **Editor Elevation** — Syntax highlighting, real-time validation, diff view
6. **Empty State Magic** — Illustrated, actionable empty states

### Non-Goals

1. **Functional changes** — CRUD, versioning, forking already work
2. **New lens capabilities** — This is UI polish, not lens runtime features
3. **Sharing/collaboration** — Separate RFC for lens distribution
4. **Mobile responsiveness** — Desktop-first for now

---

## Motivation

### Problem Statement

The Lens Library has correct functionality but generic presentation:

| Issue | Current State | Impact |
|-------|---------------|--------|
| **Uniform cards** | All lenses look identical | Can't prioritize visually |
| **Static rendering** | No entrance animations | Feels lifeless |
| **No discovery** | Filter-only browsing | Users don't explore |
| **Plain editor** | Textarea for YAML | Hard to edit without errors |
| **Bland empty states** | Text-only "No lenses" | Feels unfinished |
| **No hover intelligence** | Click-to-preview only | Slow exploration |

### Why This Matters

- **Lenses are a core differentiator** — They're what makes Sunwell adaptable to different domains
- **Library is high-traffic** — Users visit frequently to switch expertise
- **First-party showcase** — Built-in lenses should demonstrate quality
- **Competitive signal** — AI tools with generic UI feel untrustworthy

### User Stories

1. **Explorer**: "I want to browse lenses visually and see which ones are powerful at a glance"
2. **Power User**: "I want keyboard shortcuts and context menus for fast operations"
3. **Creator**: "I want a proper code editor with validation when editing my lens"
4. **Beginner**: "I want recommendations for which lens to try based on my task"

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LENS COMPONENTS                                                             │
│                                                                             │
│   LensLibrary.svelte ─────── Full browser with grid, detail, editor views  │
│         │                                                                   │
│         ├── LensPicker.svelte ─── Modal for quick selection                 │
│         │                                                                   │
│         └── LensBadge.svelte ──── Active lens indicator                     │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ STORE                                                                       │
│                                                                             │
│   lensLibrary.svelte.ts ─── State management (entries, filter, detail)      │
│         │                                                                   │
│         └── Tauri invokes: get_lens_library, get_lens_detail, fork_lens...  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ DATA MODEL                                                                  │
│                                                                             │
│   LensLibraryEntry {                                                        │
│     name, domain, version, description,                                     │
│     heuristics_count, skills_count, tags,                                   │
│     source: 'builtin' | 'user',                                             │
│     is_default, is_editable, version_count                                  │
│   }                                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Current views**:
- `library` — Grid of cards with filtering
- `detail` — Full lens info with heuristics list
- `editor` — Plain textarea for YAML
- `versions` — Version history with rollback

---

## Backend Impact

Discovery features require Rust backend changes to return additional data.

### Required Tauri Command Changes

| Command | Current Return | New Fields | Effort |
|---------|----------------|------------|--------|
| `get_lens_library` | `LensLibraryEntry[]` | `top_heuristics`, `last_used` | 2h |
| `get_lens_detail` | `LensDetail` | (no change) | — |

### Data Model Extensions (Rust)

```rust
// src-tauri/src/lens.rs — Extend LensLibraryEntry
#[derive(Serialize, Clone)]
pub struct LensLibraryEntry {
    // ... existing fields
    
    /// Top 3 heuristics for hover preview (pre-computed)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_heuristics: Option<Vec<HeuristicSummary>>,
    
    /// Last time this lens was activated (ISO 8601)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_used: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct HeuristicSummary {
    pub name: String,
    pub priority: f32,
}
```

### Usage Tracking (Local-only)

Store lens activation timestamps in the existing user config directory:

```rust
// ~/.sunwell/usage.json
{
  "lens_activations": {
    "coder": ["2026-01-20T10:00:00Z", "2026-01-21T14:30:00Z", ...],
    "tech-writer": ["2026-01-19T09:00:00Z", ...]
  }
}
```

**Privacy**: All tracking is local-only. No data leaves the device.

---

## Technical Design

### 1. Visual Hierarchy — Featured Section & Power Indicators

#### A. Featured Lenses Section

Add a hero section at the top for recommended/default lenses:

```svelte
<!-- LensLibrary.svelte — Add before lens-grid -->
{#if !lensLibrary.filter.search && lensLibrary.filter.source === 'all'}
  <section class="featured-section" in:fly={{ y: -20, duration: 300 }}>
    <h3 class="section-title">
      <span class="section-icon">✨</span>
      Recommended
    </h3>
    <div class="featured-grid">
      {#each featuredLenses as lens, i}
        <LensHeroCard 
          {lens} 
          style="--index: {i}"
          onclick={() => selectLens(lens)}
        />
      {/each}
    </div>
  </section>
{/if}
```

```typescript
// Computed: Get featured lenses (default + most used)
const featuredLenses = $derived.by(() => {
  const featured: LensLibraryEntry[] = [];
  
  // Always include default
  const defaultLens = lensLibrary.entries.find(e => e.is_default);
  if (defaultLens) featured.push(defaultLens);
  
  // Add top by heuristics count (proxy for "power")
  const byPower = [...lensLibrary.entries]
    .filter(e => !e.is_default)
    .sort((a, b) => b.heuristics_count - a.heuristics_count)
    .slice(0, 2);
  
  return [...featured, ...byPower];
});
```

#### B. Power Indicator on Cards

Visual border indicating lens "power" (heuristics + skills density):

```css
.lens-card {
  --power: calc(var(--heuristics-count, 5) / 15); /* Normalized 0-1 */
  border-left: 3px solid;
  border-left-color: color-mix(
    in oklch,
    var(--ui-gold-pale) calc(100% - var(--power) * 100%),
    var(--ui-gold) calc(var(--power) * 100%)
  );
}

/* Glow for high-power lenses */
.lens-card[data-power="high"] {
  box-shadow: var(--glow-gold-subtle);
}
```

```svelte
<div 
  class="lens-card"
  data-power={entry.heuristics_count > 8 ? 'high' : 'normal'}
  style="--heuristics-count: {entry.heuristics_count}"
>
```

#### C. View Mode Toggle (Grid/List)

```svelte
<div class="view-toggle">
  <button 
    class="toggle-btn"
    class:active={viewMode === 'grid'}
    onclick={() => viewMode = 'grid'}
    title="Grid view"
  >
    ⊞
  </button>
  <button 
    class="toggle-btn"
    class:active={viewMode === 'list'}
    onclick={() => viewMode = 'list'}
    title="List view"
  >
    ≡
  </button>
</div>
```

---

### 2. Motion & Magical Effects

#### A. Staggered Card Entrance

```css
.lens-card {
  animation: cardReveal 0.4s ease-out backwards;
  animation-delay: calc(var(--index) * 50ms);
}

@keyframes cardReveal {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
```

```svelte
{#each filteredEntries as entry, i (entry.path)}
  <div 
    class="lens-card"
    style="--index: {i}"
    in:fly={{ y: 12, duration: 300, delay: i * 50 }}
  >
```

#### B. Micro-Motes on Hover

Subtle golden sparkles when hovering cards:

```svelte
<!-- New component: LensCardMotes.svelte -->
<script lang="ts">
  let motes = $state<Array<{ id: number; x: number; y: number; delay: number }>>([]);
  let moteId = 0;
  
  export function spawnMotes(e: MouseEvent) {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Spawn 3-5 motes around cursor
    const count = 3 + Math.floor(Math.random() * 3);
    const newMotes = Array.from({ length: count }, (_, i) => ({
      id: moteId++,
      x: x + (Math.random() - 0.5) * 40,
      y: y + (Math.random() - 0.5) * 20,
      delay: i * 50,
    }));
    
    motes = [...motes, ...newMotes];
    
    // Clean up after animation
    setTimeout(() => {
      motes = motes.filter(m => !newMotes.includes(m));
    }, 1000);
  }
</script>

<div class="mote-container">
  {#each motes as mote (mote.id)}
    <span 
      class="micro-mote"
      style="--x: {mote.x}px; --y: {mote.y}px; --delay: {mote.delay}ms"
    >✦</span>
  {/each}
</div>

<style>
  .mote-container {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }
  
  .micro-mote {
    position: absolute;
    left: var(--x);
    top: var(--y);
    font-size: 10px;
    color: var(--ui-gold);
    text-shadow: var(--glow-gold-subtle);
    opacity: 0;
    animation: moteRise 0.8s ease-out forwards;
    animation-delay: var(--delay);
  }
  
  @keyframes moteRise {
    0% { opacity: 0; transform: translateY(0) scale(0.5); }
    20% { opacity: 0.9; }
    100% { opacity: 0; transform: translateY(-25px) scale(0); }
  }
  
  @media (prefers-reduced-motion: reduce) {
    .micro-mote { animation: none; }
  }
</style>
```

#### C. Loading Skeleton

```svelte
{#if lensLibrary.isLoading}
  <div class="lens-grid skeleton">
    {#each Array(6) as _, i}
      <div class="skeleton-card" style="--index: {i}">
        <div class="skeleton-header">
          <div class="skeleton-icon shimmer"></div>
          <div class="skeleton-title shimmer"></div>
        </div>
        <div class="skeleton-body shimmer"></div>
        <div class="skeleton-tags">
          <div class="skeleton-tag shimmer"></div>
          <div class="skeleton-tag shimmer"></div>
        </div>
      </div>
    {/each}
  </div>
{/if}
```

```css
.skeleton-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  animation: skeletonPulse 1.5s ease-in-out infinite;
  animation-delay: calc(var(--index) * 100ms);
}

.shimmer {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 0%,
    var(--bg-secondary) 50%,
    var(--bg-tertiary) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
}

.skeleton-title {
  height: 20px;
  width: 60%;
  border-radius: var(--radius-sm);
}

.skeleton-body {
  height: 40px;
  width: 100%;
  border-radius: var(--radius-sm);
  margin: var(--space-3) 0;
}

.skeleton-tag {
  height: 20px;
  width: 50px;
  border-radius: var(--radius-full);
}
```

---

### 3. Interaction Design

#### A. Hover Preview Popover

Show lens heuristics on hover (delayed 300ms):

```svelte
<script lang="ts">
  let previewLens = $state<LensLibraryEntry | null>(null);
  let previewTimeout: ReturnType<typeof setTimeout>;
  
  function schedulePreview(lens: LensLibraryEntry) {
    previewTimeout = setTimeout(() => {
      previewLens = lens;
    }, 300);
  }
  
  function cancelPreview() {
    clearTimeout(previewTimeout);
    previewLens = null;
  }
</script>

<div 
  class="lens-card"
  onmouseenter={() => schedulePreview(entry)}
  onmouseleave={cancelPreview}
>
  <!-- card content -->
  
  {#if previewLens?.name === entry.name}
    <div class="preview-popover" in:fly={{ y: 8, duration: 150 }}>
      <div class="preview-header">
        <span class="preview-title">Top Heuristics</span>
      </div>
      <ul class="preview-heuristics">
        {#each entry.heuristics?.slice(0, 3) ?? [] as h}
          <li>
            <span 
              class="priority-dot" 
              style="--priority: {h.priority}"
            ></span>
            {h.name}
          </li>
        {/each}
      </ul>
      <div class="preview-actions">
        <Button size="sm" variant="ghost" onclick={() => quickTest(entry)}>
          ⚡ Quick Test
        </Button>
      </div>
    </div>
  {/if}
</div>
```

```css
.preview-popover {
  position: absolute;
  top: calc(100% + var(--space-2));
  left: 50%;
  transform: translateX(-50%);
  width: 280px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  box-shadow: var(--shadow-lg), var(--glow-gold-subtle);
  z-index: var(--z-dropdown);
}

.preview-popover::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
  width: 12px;
  height: 12px;
  background: var(--bg-elevated);
  border-top: 1px solid var(--border-default);
  border-left: 1px solid var(--border-default);
}

.priority-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: color-mix(
    in oklch,
    var(--ui-gold-pale) calc(100% - var(--priority) * 100%),
    var(--radiant-gold) calc(var(--priority) * 100%)
  );
  margin-right: var(--space-2);
}
```

#### B. Keyboard Navigation

```svelte
<script lang="ts">
  let focusIndex = $state(-1);
  let searchInputRef: HTMLInputElement;
  
  function handleKeydown(e: KeyboardEvent) {
    const entries = filteredEntries;
    
    switch (e.key) {
      case 'j':
      case 'ArrowDown':
        e.preventDefault();
        focusIndex = Math.min(focusIndex + 1, entries.length - 1);
        break;
      case 'k':
      case 'ArrowUp':
        e.preventDefault();
        focusIndex = Math.max(focusIndex - 1, 0);
        break;
      case '/':
        e.preventDefault();
        searchInputRef?.focus();
        break;
      case 'Enter':
        if (focusIndex >= 0) {
          selectLens(entries[focusIndex]);
        }
        break;
      case 'Escape':
        focusIndex = -1;
        searchInputRef?.blur();
        break;
      case 'f':
        if (e.metaKey || e.ctrlKey) return; // Don't capture browser find
        if (focusIndex >= 0) {
          e.preventDefault();
          handleForkClick(entries[focusIndex].name);
        }
        break;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="lens-grid" role="listbox" aria-label="Lens library">
  {#each filteredEntries as entry, i (entry.path)}
    <div 
      class="lens-card"
      class:keyboard-focus={focusIndex === i}
      role="option"
      aria-selected={focusIndex === i}
      tabindex={focusIndex === i ? 0 : -1}
    >
```

```css
.lens-card.keyboard-focus {
  outline: 2px solid var(--ui-gold);
  outline-offset: 2px;
  box-shadow: var(--glow-gold);
}
```

#### C. Context Menu

```svelte
<script lang="ts">
  let contextMenu = $state<{ visible: boolean; x: number; y: number; lens: LensLibraryEntry | null }>({
    visible: false,
    x: 0,
    y: 0,
    lens: null,
  });
  
  function showContextMenu(e: MouseEvent, lens: LensLibraryEntry) {
    e.preventDefault();
    contextMenu = {
      visible: true,
      x: e.clientX,
      y: e.clientY,
      lens,
    };
  }
  
  function hideContextMenu() {
    contextMenu = { ...contextMenu, visible: false };
  }
</script>

<svelte:window onclick={hideContextMenu} />

<div 
  class="lens-card"
  oncontextmenu={(e) => showContextMenu(e, entry)}
>

{#if contextMenu.visible && contextMenu.lens}
  <div 
    class="context-menu"
    style="top: {contextMenu.y}px; left: {contextMenu.x}px"
    in:fly={{ y: -8, duration: 100 }}
  >
    <button class="menu-item" onclick={() => selectLens(contextMenu.lens!)}>
      <span class="menu-icon">👁</span> View Details
    </button>
    <button class="menu-item" onclick={() => handleForkClick(contextMenu.lens!.name)}>
      <span class="menu-icon">🔱</span> Fork
    </button>
    {#if contextMenu.lens.is_editable}
      <button class="menu-item" onclick={() => handleEditClick(contextMenu.lens!)}>
        <span class="menu-icon">✏️</span> Edit
      </button>
    {/if}
    <hr class="menu-divider" />
    {#if !contextMenu.lens.is_default}
      <button class="menu-item" onclick={() => setDefaultLens(contextMenu.lens!.name)}>
        <span class="menu-icon">⭐</span> Set as Default
      </button>
    {/if}
    <button class="menu-item" onclick={() => exportLens(contextMenu.lens!)}>
      <span class="menu-icon">📤</span> Export
    </button>
  </div>
{/if}
```

```css
.context-menu {
  position: fixed;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  min-width: 180px;
  padding: var(--space-1);
  z-index: var(--z-dropdown);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.menu-item:hover {
  background: var(--accent-hover);
  color: var(--text-primary);
}

.menu-divider {
  border: none;
  border-top: 1px solid var(--border-subtle);
  margin: var(--space-1) 0;
}
```

---

### 4. Discovery Features

#### A. Usage Sparkline

Track and display lens usage over time:

```typescript
// Add to LensLibraryEntry type
interface LensLibraryEntry {
  // ... existing fields
  usage_history?: number[]; // Last 7 days of usage counts
  last_used?: string;       // ISO timestamp
}
```

```svelte
<!-- New component: LensSparkline.svelte -->
<script lang="ts">
  interface Props {
    data: number[];
    width?: number;
    height?: number;
  }
  
  let { data, width = 50, height = 16 }: Props = $props();
  
  const points = $derived(() => {
    if (!data.length) return '';
    const max = Math.max(...data, 1);
    const step = width / (data.length - 1);
    return data
      .map((v, i) => `${i * step},${height - (v / max) * height}`)
      .join(' ');
  });
</script>

<svg 
  class="sparkline"
  viewBox="0 0 {width} {height}"
  width={width}
  height={height}
>
  <polyline
    fill="none"
    stroke="var(--ui-gold)"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    points={points}
  />
</svg>

<style>
  .sparkline {
    display: block;
  }
</style>
```

```svelte
<!-- In lens-card meta section -->
<div class="lens-meta">
  {#if entry.usage_history?.length}
    <span class="meta-item" title="Activity">
      <LensSparkline data={entry.usage_history} />
    </span>
  {/if}
</div>
```

#### B. Similar Lenses in Detail View

```svelte
<!-- In detail view, after main content -->
{#if lensLibrary.detail}
  <section class="similar-section">
    <h3>Similar Expertise</h3>
    <div class="similar-grid">
      {#each getSimilarLenses(lensLibrary.detail) as similar}
        <button 
          class="mini-lens-card"
          onclick={() => selectLens(similar)}
        >
          <span class="mini-icon">{getDomainIcon(similar.domain)}</span>
          <span class="mini-name">{similar.name}</span>
          <span class="mini-count">{similar.heuristics_count} heuristics</span>
        </button>
      {/each}
    </div>
  </section>
{/if}
```

```typescript
function getSimilarLenses(lens: LensDetail): LensLibraryEntry[] {
  return lensLibrary.entries
    .filter(e => 
      e.name !== lens.name && 
      (e.domain === lens.domain || 
       e.tags.some(t => lens.tags?.includes(t)))
    )
    .slice(0, 4);
}
```

#### C. Smart Search Suggestions

```svelte
<script lang="ts">
  const searchSuggestions = $derived.by(() => {
    if (!lensLibrary.filter.search || lensLibrary.filter.search.length < 2) return [];
    
    const q = lensLibrary.filter.search.toLowerCase();
    const suggestions = new Set<string>();
    
    // Suggest from names
    for (const entry of lensLibrary.entries) {
      if (entry.name.toLowerCase().includes(q)) {
        suggestions.add(entry.name);
      }
      // Suggest from domains
      if (entry.domain?.toLowerCase().includes(q)) {
        suggestions.add(`domain:${entry.domain}`);
      }
      // Suggest from tags
      for (const tag of entry.tags) {
        if (tag.toLowerCase().includes(q)) {
          suggestions.add(`tag:${tag}`);
        }
      }
    }
    
    return Array.from(suggestions).slice(0, 5);
  });
</script>

<div class="search-wrapper">
  <input
    type="text"
    placeholder="Search lenses... (press /)"
    class="search-input"
    bind:this={searchInputRef}
    value={lensLibrary.filter.search}
    oninput={(e) => setFilter({ search: e.currentTarget.value })}
  />
  
  {#if searchSuggestions.length > 0}
    <div class="search-suggestions" in:fly={{ y: -8, duration: 100 }}>
      {#each searchSuggestions as suggestion}
        <button 
          class="suggestion"
          onclick={() => setFilter({ search: suggestion })}
        >
          🔍 {suggestion}
        </button>
      {/each}
    </div>
  {/if}
</div>
```

---

### 5. Editor Elevation

#### A. Syntax Highlighting with CodeMirror

Replace the plain textarea with a proper code editor:

```bash
pnpm add @codemirror/view @codemirror/state @codemirror/lang-yaml @codemirror/theme-one-dark
```

```svelte
<!-- New component: LensEditor.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { EditorView, basicSetup } from 'codemirror';
  import { yaml } from '@codemirror/lang-yaml';
  import { EditorState } from '@codemirror/state';
  
  interface Props {
    value: string;
    onchange: (value: string) => void;
    readonly?: boolean;
  }
  
  let { value, onchange, readonly = false }: Props = $props();
  
  let container: HTMLDivElement;
  let view: EditorView;
  
  // Holy Light theme for CodeMirror
  const holyLightTheme = EditorView.theme({
    '&': {
      backgroundColor: 'var(--bg-primary)',
      color: 'var(--text-primary)',
      fontSize: 'var(--text-sm)',
      fontFamily: 'var(--font-mono)',
    },
    '.cm-content': {
      caretColor: 'var(--ui-gold)',
    },
    '.cm-cursor': {
      borderLeftColor: 'var(--ui-gold)',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(201, 162, 39, 0.05)',
    },
    '.cm-selectionBackground': {
      backgroundColor: 'rgba(201, 162, 39, 0.2)',
    },
    '.cm-gutters': {
      backgroundColor: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border-subtle)',
      color: 'var(--text-tertiary)',
    },
    '.cm-lineNumbers .cm-gutterElement': {
      paddingRight: 'var(--space-3)',
    },
  }, { dark: true });
  
  onMount(() => {
    view = new EditorView({
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          yaml(),
          holyLightTheme,
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              onchange(update.state.doc.toString());
            }
          }),
          EditorState.readOnly.of(readonly),
        ],
      }),
      parent: container,
    });
    
    return () => view.destroy();
  });
  
  // Sync external value changes
  $effect(() => {
    if (view && value !== view.state.doc.toString()) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: value },
      });
    }
  });
</script>

<div class="lens-editor-wrapper">
  <div class="editor-container" bind:this={container}></div>
</div>

<style>
  .lens-editor-wrapper {
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
  .editor-container {
    min-height: 400px;
  }
  
  .editor-container :global(.cm-editor) {
    height: 100%;
    min-height: 400px;
  }
  
  .editor-container :global(.cm-scroller) {
    font-family: var(--font-mono);
  }
</style>
```

#### B. Real-time Validation Panel

```svelte
<script lang="ts">
  interface ValidationError {
    line: number;
    message: string;
    severity: 'error' | 'warning';
  }
  
  const validationErrors = $derived.by(() => {
    const errors: ValidationError[] = [];
    
    try {
      // Basic YAML structure validation
      const lines = editedContent.split('\n');
      let hasLens = false;
      let hasMetadata = false;
      let hasHeuristics = false;
      
      lines.forEach((line, i) => {
        if (line.startsWith('lens:')) hasLens = true;
        if (line.includes('metadata:')) hasMetadata = true;
        if (line.includes('heuristics:')) hasHeuristics = true;
        
        // Check for tab characters (YAML doesn't like tabs)
        if (line.includes('\t')) {
          errors.push({
            line: i + 1,
            message: 'Use spaces instead of tabs',
            severity: 'error',
          });
        }
      });
      
      if (!hasLens) {
        errors.push({ line: 1, message: 'Missing "lens:" root key', severity: 'error' });
      }
      if (!hasMetadata) {
        errors.push({ line: 1, message: 'Missing "metadata:" section', severity: 'warning' });
      }
      if (!hasHeuristics) {
        errors.push({ line: 1, message: 'Missing "heuristics:" section', severity: 'warning' });
      }
    } catch (e) {
      errors.push({ line: 1, message: `Parse error: ${e}`, severity: 'error' });
    }
    
    return errors;
  });
</script>

<div class="editor-layout">
  <div class="editor-pane">
    <LensEditor 
      value={editedContent}
      onchange={(v) => editedContent = v}
    />
  </div>
  
  <aside class="validation-pane">
    <h4>Validation</h4>
    {#if validationErrors.length === 0}
      <div class="validation-ok">
        <span class="ok-icon">✓</span>
        Valid lens structure
      </div>
    {:else}
      <ul class="validation-errors">
        {#each validationErrors as error}
          <li class="validation-error {error.severity}">
            <span class="error-line">Line {error.line}</span>
            <span class="error-message">{error.message}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </aside>
</div>
```

---

### 6. Empty & Loading States

#### A. Illustrated Empty State

```svelte
{#if filteredEntries.length === 0 && !lensLibrary.isLoading}
  <div class="empty-state" in:fade>
    <div class="empty-illustration">
      <SparkleField width="200px" height="80px" density={0.02} />
      <span class="empty-orb">🔮</span>
    </div>
    
    {#if lensLibrary.filter.search}
      <h3>No lenses match "{lensLibrary.filter.search}"</h3>
      <p>Try a different search term or clear filters</p>
      <Button 
        variant="secondary"
        onclick={() => setFilter({ search: '', source: 'all', domain: null })}
      >
        Clear Filters
      </Button>
    {:else}
      <h3>No Lenses Yet</h3>
      <p>Lenses give Sunwell specialized expertise for different tasks</p>
      <div class="empty-actions">
        <Button variant="primary" onclick={createFirstLens}>
          ✨ Create Your First Lens
        </Button>
        <Button variant="ghost" onclick={browseCommunityLenses}>
          Browse Examples
        </Button>
      </div>
    {/if}
  </div>
{/if}
```

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-12);
  animation: fadeIn 0.3s ease;
}

.empty-illustration {
  position: relative;
  width: 200px;
  height: 120px;
  margin-bottom: var(--space-6);
}

.empty-orb {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 48px;
  animation: orbFloat 3s ease-in-out infinite;
}

@keyframes orbFloat {
  0%, 100% { transform: translate(-50%, -50%) translateY(0); }
  50% { transform: translate(-50%, -50%) translateY(-8px); }
}

.empty-state h3 {
  font-size: var(--text-xl);
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}

.empty-state p {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0 0 var(--space-6);
  max-width: 400px;
}

.empty-actions {
  display: flex;
  gap: var(--space-3);
}
```

---

## New Components

| Component | Purpose | Complexity |
|-----------|---------|------------|
| `LensHeroCard.svelte` | Featured lens with large visual presence | Medium |
| `LensCardMotes.svelte` | Hover sparkle effect | Low |
| `LensSparkline.svelte` | Usage activity chart | Low |
| `LensEditor.svelte` | CodeMirror-based YAML editor | High |
| `LensQuickPreview.svelte` | Hover popover with heuristics | Medium |
| `LensContextMenu.svelte` | Right-click actions | Medium |

---

## Implementation Plan

### Phase 1: Foundation (2 days) — 12h

| Task | Effort | Description |
|------|--------|-------------|
| Staggered card entrance | 2h | Add `--index` CSS variables, Svelte transitions |
| Loading skeleton | 2h | Shimmer cards during fetch |
| Keyboard navigation | 3h | j/k/Enter/Escape handlers, focus state |
| View mode toggle | 1h | Grid/list switch |
| Power indicator | 2h | Border color based on heuristics |
| Empty state illustration | 2h | Floating orb with sparkle field |

### Phase 2: Motion & Interactions (2 days) — 12h

| Task | Effort | Description |
|------|--------|-------------|
| Micro-motes on hover | 3h | Subtle golden sparkles |
| Hover preview popover | 4h | Delayed preview with heuristics |
| Context menu | 3h | Right-click actions |
| Featured section | 2h | Hero cards at top |

### Phase 3: Discovery (1 day) — 6h

| Task | Effort | Description |
|------|--------|-------------|
| Search suggestions | 2h | Autocomplete from names/tags/domains |
| Similar lenses | 2h | Related lenses in detail view |
| Usage sparkline | 2h | Activity visualization |

### Phase 4: Editor Elevation (2 days) — 12h

| Task | Effort | Description |
|------|--------|-------------|
| CodeMirror integration | 4h | Replace textarea, lazy-load on editor view |
| Holy Light theme | 2h | Syntax colors using `--syntax-*` tokens |
| Real-time validation | 3h | Structure checking sidebar |
| Diff view | 3h | Compare versions visually |

### Phase 5: Backend Integration (0.5 days) — 4h

| Task | Effort | Description |
|------|--------|-------------|
| Extend `get_lens_library` | 2h | Add `top_heuristics`, `last_used` fields |
| Local usage tracking | 2h | Write/read `~/.sunwell/usage.json` |

**Total**: ~46 hours across 8 days

---

## Success Criteria

### Quantitative

- [ ] Card entrance animation < 500ms total for 20 cards
- [ ] Hover preview appears within 300ms
- [ ] Keyboard navigation covers all primary actions
- [ ] 0 hardcoded color values in components
- [ ] Editor syntax highlighting for all YAML constructs
- [ ] CodeMirror lazy-loaded (not in initial bundle)
- [ ] All text passes WCAG AA contrast (4.5:1 minimum)

### Qualitative

- [ ] "Featured" section draws attention to key lenses
- [ ] Power users can operate entirely with keyboard
- [ ] Empty state feels intentional, not broken
- [ ] Sparkle effects feel magical, not distracting
- [ ] Editor feels professional, not hacked together
- [ ] Screen reader announces lens names and states correctly

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CodeMirror bundle size | Medium | Medium | Lazy-load editor only when needed |
| Motion causes motion sickness | Low | High | Respect `prefers-reduced-motion` |
| Hover preview obscures cards | Medium | Low | Careful popover positioning, dismiss on scroll |
| Keyboard conflicts with global shortcuts | Low | Medium | Use non-conflicting keys (j/k not ctrl+*) |
| Motes feel gimmicky | Medium | Low | Keep subtle, test with users |

---

## Design Decisions

### 1. Usage Tracking → Local-only (Option A)

**Decision**: Track lens activations locally in `~/.sunwell/usage.json`.

**Rationale**:
- No privacy concerns — data never leaves device
- Simple implementation — just append timestamps
- Aligns with Sunwell's "local-first" philosophy
- Sparklines become a lightweight feature, not a tracking system

### 2. Editor Library → CodeMirror 6 (not Monaco)

**Decision**: Use CodeMirror 6 for the lens editor.

**Rationale**:
- **Bundle size**: ~150KB (CodeMirror) vs ~2MB+ (Monaco)
- **Theming**: CSS-based theming integrates with Holy Light design system
- **YAML support**: First-class `@codemirror/lang-yaml` package
- **Lazy loading**: Easy to code-split since it's ESM-native
- Monaco's VS Code familiarity doesn't outweigh the 10x+ bundle cost

**Lazy loading strategy**:
```typescript
// Only load CodeMirror when editor view is opened
const LensEditor = lazy(() => import('./LensEditor.svelte'));
```

### 3. Featured Lens Selection → Algorithmic (Option A)

**Decision**: Default lens + top 2 by heuristics count.

**Rationale**:
- No manual curation overhead
- "Power" (heuristics count) is a meaningful proxy for lens depth
- Automatically surfaces best built-in lenses
- Can evolve to include "recently used" in v2

---

## Accessibility

### Keyboard Navigation

Full keyboard support is a core goal, not an afterthought.

| Requirement | Implementation |
|-------------|----------------|
| Focus visible | `outline: 2px solid var(--ui-gold)` on focused card |
| Focus order | Natural DOM order, enhanced with `tabindex` |
| Skip link | Not needed (single-page component) |
| Screen reader | `role="listbox"`, `role="option"`, `aria-selected` |

### ARIA Attributes

```svelte
<!-- Lens grid -->
<div 
  class="lens-grid" 
  role="listbox" 
  aria-label="Lens library"
  aria-activedescendant={focusIndex >= 0 ? `lens-${filteredEntries[focusIndex].name}` : undefined}
>
  {#each filteredEntries as entry, i (entry.path)}
    <div 
      id="lens-{entry.name}"
      class="lens-card"
      role="option"
      aria-selected={focusIndex === i}
      aria-label="{entry.name}: {entry.description}"
    >
```

### Reduced Motion

All animations respect `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
  .lens-card { animation: none; }
  .micro-mote { animation: none; }
  .empty-orb { animation: none; }
}
```

Already defined in `variables.css:260-266` — sets `--motion-intensity: 0`.

### Color Contrast

All text meets WCAG AA contrast ratios:
- Primary text (`#e5e5e5` on `#0d0d0d`): 13.5:1 ✅
- Secondary text (`#a8a8a8` on `#0d0d0d`): 8.5:1 ✅
- Gold accent (`#c9a227` on `#0d0d0d`): 7.2:1 ✅

---

## References

### Evidence Sources

| Reference | Location | What It Provides |
|-----------|----------|------------------|
| LensLibrary.svelte | `studio/src/components/LensLibrary.svelte` | Current implementation |
| LensPicker.svelte | `studio/src/components/LensPicker.svelte` | Modal selection UI |
| lensLibrary.svelte.ts | `studio/src/stores/lensLibrary.svelte.ts` | State management |
| coder.lens | `lenses/coder.lens` | Example lens structure |
| variables.css | `studio/src/styles/variables.css` | Holy Light design tokens |
| SparkleField | `studio/src/components/ui/SparkleField.svelte` | Reusable particle effect |

### Related RFCs

- [RFC-064](RFC-064-lens-system.md) — Original lens system design
- [RFC-070](RFC-070-lens-library.md) — Lens library browser
- [RFC-097](RFC-097-studio-ux-elevation.md) — S-tier quality rubric

---

## Appendix A: Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `j` / `↓` | Next card |
| `k` / `↑` | Previous card |
| `Enter` | Select focused card |
| `Escape` | Clear focus / close popover |
| `f` | Fork focused lens |
| `e` | Edit focused lens (if editable) |
| `d` | Set focused lens as default |

---

## Appendix B: CSS Variable Additions

```css
/* Add to global.css */

/* Lens-specific tokens */
--lens-power-low: var(--ui-gold-pale);
--lens-power-medium: var(--ui-gold-soft);
--lens-power-high: var(--ui-gold);

/* Animation timing */
--card-stagger: 50ms;
--preview-delay: 300ms;
--mote-duration: 800ms;

/* Skeleton */
--skeleton-base: var(--bg-tertiary);
--skeleton-highlight: var(--bg-secondary);
```

---

## Appendix C: Data Model Extensions

```typescript
// Extend LensLibraryEntry for discovery features
interface LensLibraryEntry {
  // ... existing fields
  
  // Discovery (Phase 3)
  usage_history?: number[];    // Last 7 days of usage
  last_used?: string;          // ISO timestamp
  popularity_rank?: number;    // For sorting by popularity
  
  // Preview (Phase 2)
  top_heuristics?: Array<{     // Pre-computed for hover preview
    name: string;
    priority: number;
  }>;
}
```
