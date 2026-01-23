# RFC-097: Studio UX Elevation — S-Tier Component Quality

**Status**: Implemented  
**Author**: Lawrence Lane  
**Created**: 2026-01-22  
**Target Version**: v1.x  
**Confidence**: 90% 🟢

---

## Summary

Systematic audit and elevation of all Studio components across all three layers (Python, Rust, Svelte) to S-tier quality. Every touchpoint should embody the Holy Light design system with consistent tokens, polished micro-interactions, proper typography, and syntax highlighting.

**Goal**: When someone opens Studio, the quality should be immediately apparent — not generic, not "AI slop," but distinctively crafted. This requires coordination across:

- **Svelte** — UI components (51 total: 23 primitives, 19 blocks, 9 pages)
- **Rust** — Tauri commands, event bridge, native window chrome
- **Python** — Event payloads, data richness for UI rendering

---

## Goals and Non-Goals

### Goals

1. **Audit all 51 components** against a defined quality rubric
2. **Establish S-tier criteria** — what makes a component "gorgeous"
3. **Fix design token inconsistencies** — no more hardcoded colors
4. **Add syntax highlighting** with Shiki + Holy Light theme
5. **Polish micro-interactions** — hover, focus, transitions, animations
6. **Create component gallery** — visual testing surface for all components
7. **Enrich event payloads** — Python events include UI hints for richer rendering
8. **Native window polish** — Tauri window chrome matches Holy Light aesthetic

### Non-Goals

1. **Functional changes** — This is visual/UX polish, not new features
2. **Accessibility overhaul** — Separate RFC (though we'll fix obvious issues)
3. **Mobile responsiveness** — Desktop-first for now
4. **Performance optimization** — Separate concern (except Shiki lazy-loading)

---

## Motivation

### Problem Statement

Studio has accumulated inconsistencies across all three layers:

| Layer | Issue | Example | Impact |
|-------|-------|---------|--------|
| **Svelte** | Hardcoded colors | `ThinkingBlock.svelte:116` uses `rgba(99, 102, 241, 0.1)` (purple) | Breaks visual coherence |
| **Svelte** | Placeholder primitives | `Metrics.svelte` — 48 lines, shows static "0" | Looks unfinished |
| **Svelte** | No syntax highlighting | `CodeEditor.svelte:31-36` — plain `<textarea>` | Code looks flat |
| **Svelte** | Undefined CSS fallbacks | `ThinkingBlock` uses `--surface-1/2/3` (not defined) | Unpredictable rendering |
| **Rust** | Event types as strings | `agent.rs:141` — `event_type: String` | No type safety for UI mapping |
| **Python** | Sparse event data | Events lack UI hints (icons, severity, suggested actions) | Frontend guesses presentation |

### Why This Matters

- **First impressions** — Users judge quality in seconds
- **Trust** — Polished UI signals competent engineering
- **Differentiation** — Avoids "AI slop" aesthetic that plagues AI tools
- **Cohesion** — Holy Light design system exists but isn't fully applied

---

## Architecture: Three-Layer Event Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PYTHON (sunwell)                                                            │
│                                                                             │
│   AgentEvent { type, data, timestamp }                                      │
│         │                                                                   │
│         │  NDJSON stdout                                                    │
│         ▼                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ RUST (Tauri)                                                                │
│                                                                             │
│   AgentBridge::run_goal() → parses NDJSON → app.emit("agent-event", event)  │
│         │                                                                   │
│         │  Tauri IPC                                                        │
│         ▼                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ SVELTE (Studio)                                                             │
│                                                                             │
│   listen("agent-event") → store.update() → <ThinkingBlock/> renders        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key insight**: UX quality requires coordination across all three layers. A beautiful `ThinkingBlock` needs rich event data from Python, type-safe bridging in Rust, and proper tokens in Svelte.

---

## S-Tier Quality Rubric

Every component must pass these criteria:

### 1. Design Token Compliance (Required)

```yaml
colors:
  - Uses CSS variables from variables.css
  - No hardcoded hex values
  - Semantic color usage (--success, --error, not raw green/red)

spacing:
  - Uses --space-* scale
  - Consistent padding/margin patterns
  - No magic numbers (12px, 16px → --space-3, --space-4)

typography:
  - Uses --font-* family variables
  - Uses --text-* size scale
  - Appropriate font for context (mono for code, serif for prose, sans for UI)
```

### 2. Visual Hierarchy (Required)

```yaml
levels:
  - Primary: Most important element is immediately clear
  - Secondary: Supporting information is visible but subordinate
  - Tertiary: Metadata/timestamps are present but unobtrusive

techniques:
  - Size contrast (headings vs body)
  - Weight contrast (bold for emphasis)
  - Color contrast (--text-primary vs --text-tertiary)
  - Spatial grouping (related items clustered)
```

### 3. Micro-Interactions (Required)

```yaml
hover:
  - Every interactive element has hover state
  - Transitions use --transition-* variables
  - Hover reveals additional affordances (not just color change)

focus:
  - Visible focus ring for keyboard navigation
  - Uses --border-emphasis or glow effect
  - Focus order is logical

active:
  - Pressed state is distinct from hover
  - Provides immediate feedback

loading:
  - Shimmer or pulse animation during async operations
  - Progress indication when duration is known
```

### 4. Motion & Animation (Recommended)

```yaml
entrance:
  - Components fade/slide in on mount
  - Staggered animation for lists
  - Uses Svelte transitions (fade, fly, scale)

feedback:
  - Success/error states animate
  - Numbers count up (like demo improvement %)
  - Progress bars have shimmer effect

ambient:
  - Subtle pulse on active/generating states
  - Sparkle effects reserved for magical moments
  - Respects prefers-reduced-motion
```

### 5. Typography Excellence (Recommended)

```yaml
fonts:
  --font-mono: Code, technical data, metrics
  --font-sans: UI labels, buttons, navigation
  --font-serif: Prose, quotes, elegant text

hierarchy:
  - H1: --text-3xl, --font-serif (rare, page titles)
  - H2: --text-2xl, --font-sans (section headers)
  - H3: --text-lg, --font-mono (component headers)
  - Body: --text-base
  - Meta: --text-sm or --text-xs, --text-tertiary
```

### 6. Code Display (New Requirement)

```yaml
syntax_highlighting:
  - All code blocks use Shiki tokenizer
  - Holy Light theme colors applied
  - Line numbers optional (default off)
  - Copy button on hover

tokens:
  --syntax-keyword: #c9a227    # Gold — control flow
  --syntax-function: #e8c84a   # Bright gold — callables
  --syntax-string: #a8d4a0     # Soft green — literals
  --syntax-number: #f0b866     # Warm amber — numerics
  --syntax-comment: #525252    # Tertiary — faded
  --syntax-type: #d4b046       # Gold text — annotations
  --syntax-builtin: #7eb8da    # Cool blue — contrast
  --syntax-decorator: #b8a0d4  # Soft purple — decorators
```

---

## Component Audit

### Current State (51 Components)

#### Primitives (23)

| Component | Token Compliance | Hierarchy | Interactions | Motion | Status |
|-----------|-----------------|-----------|--------------|--------|--------|
| BriefingCard | ✅ | ✅ | ✅ | ✅ | **S-Tier** |
| Calendar | ✅ | ✅ | ✅ | ❌ | Good |
| Chart | ⚠️ | ❌ | ❌ | ❌ | **Placeholder** |
| CodeEditor | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| DAGView | ✅ | ✅ | ✅ | ⚠️ | Good |
| DataTable | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| Dependencies | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| DiffView | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| GoalTree | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| KanbanBoard | ✅ | ✅ | ⚠️ | ⚠️ | Acceptable |
| MemoryPane | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| Metrics | ⚠️ | ❌ | ❌ | ❌ | **Placeholder** |
| Outline | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| Preview | ✅ | ✅ | ✅ | ⚠️ | Good |
| ProseEditor | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| QueryBuilder | ⚠️ | ❌ | ❌ | ❌ | **Placeholder** |
| References | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| Summary | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| TaskList | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| Terminal | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| TestRunner | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| Timeline | ✅ | ✅ | ✅ | ❌ | Good |
| WordCount | ✅ | ✅ | ❌ | ❌ | Acceptable |

**Summary**: 1 S-Tier, 4 Good, 10 Acceptable, 5 Needs Work, 3 Placeholder

#### Blocks (19)

| Component | Token Compliance | Hierarchy | Interactions | Motion | Status |
|-----------|-----------------|-----------|--------------|--------|--------|
| BookmarksBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| CalendarBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| ContactsBlock | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| ConversationBlock | ✅ | ✅ | ✅ | ⚠️ | Good |
| ConversationLayout | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| DiataxisBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| FilesBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| GenericBlock | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| GitBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| HabitsBlock | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| ListBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| ModelComparisonBlock | ✅ | ✅ | ✅ | ✅ | **S-Tier** |
| NotesBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| ProjectsBlock | ✅ | ✅ | ✅ | ✅ | **S-Tier** |
| SearchBlock | ✅ | ⚠️ | ⚠️ | ❌ | **Needs work** |
| SkillsBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| ThinkingBlock | ❌ | ✅ | ✅ | ✅ | **Fix tokens** |
| ValidationBlock | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| WorkflowPanel | ✅ | ✅ | ⚠️ | ⚠️ | Good |

**Summary**: 2 S-Tier, 2 Good, 10 Acceptable, 4 Needs Work, 1 Fix Tokens

#### Pages (9)

| Component | Token Compliance | Hierarchy | Interactions | Motion | Status |
|-----------|-----------------|-----------|--------------|--------|--------|
| Demo | ✅ | ✅ | ✅ | ✅ | **S-Tier** |
| Home | ✅ | ✅ | ✅ | ✅ | **S-Tier** |
| Interface | ✅ | ⚠️ | ⚠️ | ❌ | **Needs work** |
| Library | ✅ | ⚠️ | ❌ | ❌ | **Needs work** |
| Planning | ✅ | ✅ | ⚠️ | ⚠️ | Good |
| Preview | ✅ | ✅ | ⚠️ | ❌ | Acceptable |
| Project | ✅ | ✅ | ⚠️ | ⚠️ | Good |
| Projects | ✅ | ✅ | ✅ | ⚠️ | Good |
| Writer | ✅ | ✅ | ⚠️ | ❌ | Acceptable |

**Summary**: 2 S-Tier, 3 Good, 2 Acceptable, 2 Needs Work

### Priority Tiers

**Tier 1: High Visibility (Fix First)**
- `ThinkingBlock` — Visible during every generation, uses hardcoded purple colors
- `CodeEditor` — Primary code interaction, no syntax highlighting
- `Interface` — Main workspace, needs polish

**Tier 2: Placeholders (Implement Properly)**
- `Metrics` — Currently 48 lines, shows static "0"
- `Chart` — 50 lines, shows "No chart data"
- `QueryBuilder` — Minimal implementation

**Tier 3: Polish (Enhance)**
- All "Acceptable" and "Needs Work" components
- Add motion, improve interactions

**Tier 4: Maintain**
- S-Tier components (Home, Demo, ProjectsBlock, ModelComparisonBlock, BriefingCard)
- Keep as reference implementations

---

## Technical Design

### 1. Python: Event Payload Enrichment

Current events lack UI hints. Enrich payloads to support richer rendering.

```python
# sunwell/adaptive/events.py — Add UI hints to events

@dataclass(frozen=True, slots=True)
class EventUIHints:
    """UI rendering hints for frontend."""
    
    icon: str | None = None          # Suggested icon (emoji or name)
    severity: str = "info"           # "info", "warning", "error", "success"
    progress: float | None = None    # 0.0-1.0 for progress indicators
    dismissible: bool = True         # Can user dismiss this?
    highlight_code: bool = False     # Should code in data be syntax highlighted?


# Example: Enrich task_start event
def task_start_event(task_id: str, description: str, **kwargs: Any) -> AgentEvent:
    """Create a task_start event with UI hints."""
    return AgentEvent(
        type=EventType.TASK_START,
        data={
            "task_id": task_id,
            "description": description,
            "ui_hints": {
                "icon": "⚡",
                "severity": "info",
                "progress": None,
            },
            **kwargs,
        },
    )
```

### 2. Rust: Type-Safe Event Bridging

Current `agent.rs` uses `String` for event types in `AgentEvent` (line 141). Note: A typed `EventType` enum already exists (lines 22-135) but isn't used in deserialization — this design adds a UI-enrichment layer on top.

```rust
// studio/src-tauri/src/agent.rs — Enhanced event handling (ADD, don't replace AgentEvent)

/// UI-enriched event for frontend
#[derive(Debug, Clone, Serialize)]
pub struct UIEvent {
    #[serde(flatten)]
    pub event: AgentEvent,
    /// Computed UI hints based on event type
    pub ui: UIHints,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct UIHints {
    pub icon: Option<String>,
    pub severity: String,
    pub animation: Option<String>,
}

impl From<&AgentEvent> for UIHints {
    fn from(event: &AgentEvent) -> Self {
        match event.event_type.as_str() {
            "task_start" => UIHints {
                icon: Some("⚡".into()),
                severity: "info".into(),
                animation: Some("pulse".into()),
            },
            "task_complete" => UIHints {
                icon: Some("✓".into()),
                severity: "success".into(),
                animation: Some("fade-in".into()),
            },
            "error" => UIHints {
                icon: Some("✗".into()),
                severity: "error".into(),
                animation: Some("shake".into()),
            },
            "model_tokens" | "model_thinking" => UIHints {
                icon: Some("🧠".into()),
                severity: "info".into(),
                animation: Some("pulse".into()),
            },
            _ => UIHints::default(),
        }
    }
}

// In event processing loop:
let ui_event = UIEvent {
    ui: UIHints::from(&event),
    event,
};
let _ = app.emit("agent-event", &ui_event);
```

### 3. Svelte: Syntax Highlighting with Shiki

#### Design Options

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A: Build-time** | Pre-highlight static code during build | Faster runtime, smaller JS bundle | Not viable — all Studio code is dynamic agent output |
| **B: Runtime lazy-load** | Load Shiki on first code block | Handles dynamic content, single implementation | ~2MB grammar bundle, initial load delay |

**Decision**: Option B (runtime lazy-loading). All code in Studio is dynamic from agents, so build-time highlighting isn't viable. Bundle size mitigated by:
1. Lazy-loading only on first code block render
2. Loading only needed language grammars (8 languages, not all 200+)

```bash
pnpm add shiki
```

```typescript
// lib/syntax.ts — Lazy-loaded Shiki with Holy Light theme
import type { Highlighter } from 'shiki';

let highlighter: Highlighter | null = null;
let loading: Promise<Highlighter> | null = null;

// Holy Light theme definition (canonical source)
export const holyLightTheme = {
  name: 'holy-light',
  type: 'dark' as const,
  colors: {
    'editor.background': '#0d0d0d',
    'editor.foreground': '#e5e5e5',
  },
  tokenColors: [
    { scope: 'keyword', settings: { foreground: '#c9a227' } },
    { scope: 'entity.name.function', settings: { foreground: '#e8c84a' } },
    { scope: 'string', settings: { foreground: '#a8d4a0' } },
    { scope: 'constant.numeric', settings: { foreground: '#f0b866' } },
    { scope: 'comment', settings: { foreground: '#525252', fontStyle: 'italic' } },
    { scope: 'entity.name.type', settings: { foreground: '#d4b046' } },
    { scope: 'support.function', settings: { foreground: '#7eb8da' } },
    { scope: 'entity.name.decorator', settings: { foreground: '#b8a0d4' } },
    { scope: 'variable', settings: { foreground: '#e5e5e5' } },
    { scope: 'punctuation', settings: { foreground: '#a8a8a8' } },
  ],
};

export async function getHighlighterInstance(): Promise<Highlighter> {
  if (highlighter) return highlighter;
  
  if (!loading) {
    loading = import('shiki').then(async ({ getHighlighter }) => {
      highlighter = await getHighlighter({
        themes: [holyLightTheme],
        langs: ['python', 'typescript', 'javascript', 'bash', 'json', 'yaml', 'rust', 'svelte'],
      });
      return highlighter;
    });
  }
  
  return loading;
}

export async function highlight(code: string, lang: string): Promise<string> {
  const hl = await getHighlighterInstance();
  return hl.codeToHtml(code, { lang, theme: 'holy-light' });
}
```

### 4. Fix ThinkingBlock Tokens

Map undefined variables to Holy Light tokens:

```diff
// studio/src/components/blocks/ThinkingBlock.svelte

<style>
  .thinking-block {
-   background: var(--surface-2, #1a1a2e);
+   background: var(--bg-secondary);
    border-radius: 12px;
-   padding: 16px;
+   padding: var(--space-4);
-   border: 1px solid var(--border, #2d2d44);
+   border: 1px solid var(--border-default);
    transition: border-color 0.2s, box-shadow 0.2s;
-   font-family: var(--font-sans, system-ui, sans-serif);
+   font-family: var(--font-sans);
  }
  
  .thinking-block:not(.complete) {
-   box-shadow: 0 0 20px rgba(99, 102, 241, 0.1);
+   box-shadow: var(--glow-gold-subtle);
  }
  
  .thinking-block.complete {
-   border-color: var(--success, #10b981);
+   border-color: var(--success);
  }
  
  .model-indicator {
    display: flex;
    align-items: center;
-   gap: 8px;
+   gap: var(--space-2);
    font-weight: 600;
-   color: var(--text, #e2e8f0);
+   color: var(--text-primary);
  }
  
  .model-name {
    font-size: 0.9em;
-   color: var(--text-muted, #94a3b8);
+   color: var(--text-secondary);
  }
  
  .progress-bar {
-   height: 28px;
+   height: var(--space-6);
-   background: var(--surface-3, #252538);
+   background: var(--bg-tertiary);
-   border-radius: 8px;
+   border-radius: var(--radius-md);
    overflow: hidden;
    position: relative;
  }
  
  .fill {
    height: 100%;
-   background: linear-gradient(90deg, var(--primary, #6366f1), var(--accent, #8b5cf6));
+   background: var(--gradient-progress);
    transition: width 0.3s ease-out;
-   border-radius: 8px;
+   border-radius: var(--radius-md);
  }
  
  .thinking-preview {
-   margin-top: 12px;
+   margin-top: var(--space-3);
-   padding: 12px;
+   padding: var(--space-3);
-   background: var(--surface-1, #0f0f1a);
+   background: var(--bg-primary);
-   border-radius: 8px;
+   border-radius: var(--radius-md);
-   border: 1px solid var(--border, #2d2d44);
+   border: 1px solid var(--border-subtle);
  }
</style>
```

### 5. Add Syntax Tokens to variables.css (NEW)

> **Note**: These tokens do not currently exist in `variables.css`. This section defines new CSS custom properties to be added.

```css
/* studio/src/styles/variables.css — Add after typography section */

/* ═══════════════════════════════════════════════════════════════
   SYNTAX HIGHLIGHTING (Holy Light theme) — NEW
   ═══════════════════════════════════════════════════════════════ */
--syntax-keyword: #c9a227;      /* Gold — control flow (if, def, return) */
--syntax-function: #e8c84a;     /* Bright gold — callable names */
--syntax-string: #a8d4a0;       /* Soft green — string literals */
--syntax-number: #f0b866;       /* Warm amber — numeric literals */
--syntax-comment: #525252;      /* Tertiary — faded comments */
--syntax-type: #d4b046;         /* Gold text — type annotations */
--syntax-builtin: #7eb8da;      /* Cool blue — builtins (contrast accent) */
--syntax-decorator: #b8a0d4;    /* Soft purple — decorators */
--syntax-variable: #e5e5e5;     /* Primary text — variables */
--syntax-punctuation: #a8a8a8;  /* Secondary — brackets, commas */
```

### 6. Tauri Window Chrome (Native Polish)

```rust
// studio/src-tauri/src/main.rs — Enhanced window setup

.setup(move |app| {
    let window = app.get_webview_window("main").unwrap();
    
    // Holy Light window chrome
    #[cfg(target_os = "macos")]
    {
        use tauri::TitleBarStyle;
        window.set_title_bar_style(TitleBarStyle::Overlay)?;
        // Vibrancy for depth (requires tauri-plugin-vibrancy)
    }
    
    // Set minimum size for quality
    window.set_min_size(Some(tauri::LogicalSize::new(1024.0, 768.0)))?;
    
    // ... rest of setup
})
```

### 7. Component Gallery Page

New route: `routes/Gallery.svelte` (accessible at `/gallery`)

> **Design Decision**: Gallery is a development/QA tool, not user-facing. Consider gating behind a dev flag or moving to `/dev/gallery` in production builds.

```svelte
<!--
  Gallery — Component showcase for visual testing
  
  Displays all primitives and blocks with various states.
  Used for visual regression testing and design review.
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  
  // Import all primitives dynamically
  const primitives = import.meta.glob('../components/primitives/*.svelte');
  const blocks = import.meta.glob('../components/blocks/*.svelte');
  
  const categories = [
    { 
      name: 'Code', 
      icon: '💻',
      components: ['CodeEditor', 'Terminal', 'DiffView', 'Preview', 'TestRunner'] 
    },
    { 
      name: 'Planning', 
      icon: '📋',
      components: ['KanbanBoard', 'Timeline', 'TaskList', 'GoalTree', 'DAGView'] 
    },
    { 
      name: 'Writing', 
      icon: '✍️',
      components: ['ProseEditor', 'Outline', 'References', 'WordCount'] 
    },
    { 
      name: 'Data', 
      icon: '📊',
      components: ['DataTable', 'Chart', 'Metrics', 'Summary', 'QueryBuilder'] 
    },
    {
      name: 'Blocks',
      icon: '🧱',
      components: ['ThinkingBlock', 'ConversationBlock', 'ProjectsBlock', 'ValidationBlock']
    },
  ];
  
  let activeCategory = $state(categories[0]);
  let activeComponent = $state(categories[0].components[0]);
  
  // Quality rubric checklist
  const rubric = [
    { id: 'tokens', label: 'Token Compliance', desc: 'Uses CSS variables, no hardcoded colors' },
    { id: 'hierarchy', label: 'Visual Hierarchy', desc: 'Clear primary/secondary/tertiary levels' },
    { id: 'interactions', label: 'Micro-Interactions', desc: 'Hover, focus, active states' },
    { id: 'motion', label: 'Motion', desc: 'Entrance animations, feedback' },
    { id: 'typography', label: 'Typography', desc: 'Correct font families and scale' },
  ];
  
  let checks = $state<Record<string, boolean>>({});
</script>

<div class="gallery" in:fade>
  <aside class="sidebar">
    <h1 class="gallery-title">Component Gallery</h1>
    <p class="gallery-subtitle">Visual testing surface for S-tier quality</p>
    
    {#each categories as category}
      <div class="category" in:fly={{ x: -20, delay: categories.indexOf(category) * 50 }}>
        <button 
          class="category-header"
          class:active={activeCategory === category}
          onclick={() => { activeCategory = category; activeComponent = category.components[0]; }}
        >
          <span class="category-icon">{category.icon}</span>
          <span class="category-name">{category.name}</span>
          <span class="category-count">{category.components.length}</span>
        </button>
        
        {#if activeCategory === category}
          <div class="component-list" in:fly={{ y: -10 }}>
            {#each category.components as component}
              <button 
                class="component-btn"
                class:active={activeComponent === component}
                onclick={() => activeComponent = component}
              >
                {component}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </aside>
  
  <main class="preview">
    <header class="preview-header">
      <h2 class="component-name">{activeComponent}</h2>
      <div class="component-status">
        <!-- Status badge based on audit -->
      </div>
    </header>
    
    <div class="component-frame">
      <!-- Dynamic component rendering with mock data -->
      <div class="frame-placeholder">
        Component preview: {activeComponent}
      </div>
    </div>
    
    <section class="quality-section">
      <h3>Quality Rubric</h3>
      <div class="rubric-grid">
        {#each rubric as item}
          <label class="rubric-item">
            <input 
              type="checkbox" 
              bind:checked={checks[item.id]}
            />
            <span class="rubric-label">{item.label}</span>
            <span class="rubric-desc">{item.desc}</span>
          </label>
        {/each}
      </div>
      
      <div class="score">
        Score: {Object.values(checks).filter(Boolean).length} / {rubric.length}
      </div>
    </section>
  </main>
</div>

<style>
  .gallery {
    display: grid;
    grid-template-columns: 280px 1fr;
    height: 100vh;
    background: var(--bg-primary);
  }
  
  .sidebar {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-subtle);
    padding: var(--space-4);
    overflow-y: auto;
  }
  
  .gallery-title {
    font-family: var(--font-serif);
    font-size: var(--text-2xl);
    color: var(--text-gold);
    margin: 0 0 var(--space-1);
  }
  
  .gallery-subtitle {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0 0 var(--space-6);
  }
  
  .category {
    margin-bottom: var(--space-2);
  }
  
  .category-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .category-header:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .category-header.active {
    background: var(--accent-hover);
    border-color: var(--border-default);
    color: var(--text-gold);
  }
  
  .category-count {
    margin-left: auto;
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .component-list {
    padding-left: var(--space-8);
  }
  
  .component-btn {
    width: 100%;
    text-align: left;
    padding: var(--space-1) var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .component-btn:hover {
    color: var(--text-primary);
    background: var(--bg-tertiary);
  }
  
  .component-btn.active {
    color: var(--text-gold);
    background: var(--accent-hover);
  }
  
  .preview {
    padding: var(--space-6);
    overflow-y: auto;
  }
  
  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
  }
  
  .component-name {
    font-family: var(--font-mono);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0;
  }
  
  .component-frame {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    min-height: 400px;
    padding: var(--space-4);
    margin-bottom: var(--space-6);
  }
  
  .frame-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .quality-section h3 {
    font-size: var(--text-lg);
    color: var(--text-primary);
    margin: 0 0 var(--space-4);
  }
  
  .rubric-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .rubric-item {
    display: grid;
    grid-template-columns: auto 1fr;
    grid-template-rows: auto auto;
    gap: var(--space-1) var(--space-2);
    padding: var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
  }
  
  .rubric-item input {
    grid-row: span 2;
    accent-color: var(--accent);
  }
  
  .rubric-label {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .rubric-desc {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .score {
    margin-top: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    color: var(--text-gold);
  }
</style>
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1) — 14h

| Task | Layer | Effort | Description |
|------|-------|--------|-------------|
| Add Shiki | Svelte | 2h | Install, configure lazy-loading in `lib/syntax.ts` |
| Create CodeBlock | Svelte | 3h | New component with Holy Light theme |
| Add syntax tokens | Svelte | 1h | Define `--syntax-*` in `variables.css` |
| Fix ThinkingBlock | Svelte | 2h | Replace hardcoded colors with tokens |
| Add UIHints to events | Python | 2h | Enrich event payloads with UI hints |
| Type-safe event bridge | Rust | 2h | Add `UIEvent` wrapper in `agent.rs` |
| Create Gallery route | Svelte | 2h | Basic component showcase page |

### Phase 2: Tier 1 Components (Week 2) — 12h

| Task | Layer | Effort | Description |
|------|-------|--------|-------------|
| Elevate CodeEditor | Svelte | 4h | Integrate CodeBlock, add interactions |
| Polish Interface page | Svelte | 4h | Visual hierarchy, transitions |
| Enrich model events | Python | 2h | Add richer data to `MODEL_TOKENS`, `MODEL_THINKING` |
| Window chrome polish | Rust | 2h | macOS titlebar, minimum size, vibrancy |

### Phase 3: Placeholders (Week 3) — 14h

| Task | Layer | Effort | Description |
|------|-------|--------|-------------|
| Implement Metrics | Svelte | 4h | Real metric display, animations |
| Implement Chart | Svelte | 6h | SVG-based charting with Holy Light colors |
| Implement QueryBuilder | Svelte | 4h | Proper filter/query UI |

### Phase 4: Polish Pass (Week 4) — 10h

| Task | Layer | Effort | Description |
|------|-------|--------|-------------|
| Add transitions | Svelte | 4h | Entrance animations, hover states |
| Typography audit | Svelte | 2h | Ensure font usage is consistent |
| Interaction audit | Svelte | 4h | Focus states, loading states |

**Total**: ~50 hours across 4 weeks

---

## Success Criteria

### Quantitative

- [ ] 100% of components pass Token Compliance (0 hardcoded hex values)
- [ ] 100% of interactive elements have hover/focus states
- [ ] All code displays use syntax highlighting (Shiki)
- [ ] Python events include `ui_hints` for all visibility-related events
- [ ] Rust `agent.rs` uses type-safe `UIEvent` wrapper

### Qualitative

- [ ] Gallery page shows all 51 components in one place
- [ ] Non-designer can identify quality improvement in A/B comparison
- [ ] Screenshots look professional, not template-y
- [ ] Consistent "Holy Light" aesthetic across all three layers
- [ ] ThinkingBlock uses gold (not purple) during generation

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Shiki bundle size (~2MB grammars) | High | Medium | Lazy-load on first code block, only needed languages |
| Breaking existing styles | Medium | High | Use Gallery for visual regression testing |
| Scope creep into functionality | Medium | Medium | Strict "visual only" constraint, defer features |
| Cross-layer coordination overhead | Medium | Low | Clear interfaces (event schemas), incremental rollout |
| Python/Rust sync drift | Low | Medium | Document event schema in `schemas/agent-events.schema.json` |

---

## Open Questions

Questions to resolve during implementation:

1. **Gallery visibility**: Should `/gallery` be hidden in production builds? Options:
   - Dev-only route (compile-time flag)
   - Hidden but accessible (no nav link)
   - Always visible (useful for users to explore components)

2. **Shiki grammar loading**: Load all 8 languages upfront, or lazy-load per-language?
   - Upfront: Simpler, ~800KB total for 8 languages
   - Per-language: Smaller initial load, more complexity

3. **UIHints source of truth**: Should UI hints come from Python (canonical) or Rust (faster iteration)?
   - Current design: Python emits hints, Rust can augment
   - Alternative: Rust owns all UI mapping, Python just emits raw events

---

## Appendix A: Holy Light Syntax Theme

Visual reference for the syntax highlighting colors:

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  def divide(a: float, b: float) -> float:                              │
│  ─── ────── ─  ─────  ─  ─────     ─────                               │
│   │    │    │    │    │    │         │                                 │
│   │    │    │    │    │    │         └─ type (#d4b046)                 │
│   │    │    │    │    │    └─ type (#d4b046)                           │
│   │    │    │    │    └─ variable (#e5e5e5)                            │
│   │    │    │    └─ type (#d4b046)                                     │
│   │    │    └─ variable (#e5e5e5)                                      │
│   │    └─ function (#e8c84a)                                           │
│   └─ keyword (#c9a227)                                                 │
│                                                                        │
│      """Divide two numbers."""                                         │
│      ───────────────────────                                           │
│                │                                                       │
│                └─ string (#a8d4a0)                                     │
│                                                                        │
│      if b == 0:                                                        │
│      ── ─    ─                                                         │
│       │ │    │                                                         │
│       │ │    └─ number (#f0b866)                                       │
│       │ └─ variable (#e5e5e5)                                          │
│       └─ keyword (#c9a227)                                             │
│                                                                        │
│          raise ZeroDivisionError("Cannot divide by zero")              │
│          ─────  ────────────────  ──────────────────────               │
│            │           │                    │                          │
│            │           │                    └─ string (#a8d4a0)        │
│            │           └─ builtin (#7eb8da)                            │
│            └─ keyword (#c9a227)                                        │
│                                                                        │
│      # This is a comment                                               │
│      ───────────────────                                               │
│               │                                                        │
│               └─ comment (#525252, italic)                             │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: CSS Variable Mapping

ThinkingBlock uses undefined variables. Here's the mapping:

| Old Variable | → | Holy Light Token |
|--------------|---|------------------|
| `--surface-1` | → | `--bg-primary` |
| `--surface-2` | → | `--bg-secondary` |
| `--surface-3` | → | `--bg-tertiary` |
| `--primary` | → | `--accent` (or `--gradient-progress` for gradients) |
| `--accent` | → | `--ui-gold-soft` |
| `--text` | → | `--text-primary` |
| `--text-muted` | → | `--text-secondary` |
| `--border` | → | `--border-default` |
| `--success` | → | `--success` ✅ (already correct) |

---

## References

### Evidence Sources

| Reference | Location | What It Provides |
|-----------|----------|------------------|
| variables.css | `studio/src/styles/variables.css:1-285` | Holy Light design tokens |
| ThinkingBlock | `studio/src/components/blocks/ThinkingBlock.svelte:105-255` | Hardcoded colors to fix |
| CodeEditor | `studio/src/components/primitives/CodeEditor.svelte:31-36` | Plain textarea (no highlighting) |
| Metrics | `studio/src/components/primitives/Metrics.svelte` | 48-line placeholder |
| Chart | `studio/src/components/primitives/Chart.svelte` | 50-line placeholder |
| agent.rs | `studio/src-tauri/src/agent.rs:137-145` | Event type definitions |
| events.py | `src/sunwell/adaptive/events.py:44-344` | Python event schema |
| Home.svelte | `studio/src/routes/Home.svelte` | S-tier reference implementation |
| Demo.svelte | `studio/src/routes/Demo.svelte` | S-tier reference (RFC-095) |

### Related RFCs

- [RFC-072](RFC-072-block-primitives.md) — Original primitive definitions
- [RFC-080](RFC-080-unified-home.md) — Home surface design
- [RFC-081](RFC-081-inference-visibility.md) — ThinkingBlock design
- [RFC-095](RFC-095-demo-command.md) — Demo UI design (syntax highlighting example)
