# RFC-080: Unified Home Surface — One Input, Infinite Possibilities

**Status**: Draft  
**Created**: 2026-01-21  
**Last Updated**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 90% 🟢  
**Supersedes**: None (integrates RFC-072, RFC-075, RFC-078, RFC-079)  
**Depends on**:
- RFC-061 (Holy Light Design System) — Visual styling
- RFC-072 (Surface Primitives) — Workspace primitives and layout system **(Blocks extend this)**
- RFC-075 (Generative Interface) — Intent analysis and routing **(Reuses InteractionRouter)**
- RFC-078 (Primitive & Provider Roadmap) — Data providers **(Shared by Blocks and Primitives)**
- RFC-079 (Project Intent Analyzer) — Project understanding

---

## Summary

Replace the fragmented Home experience (project creation input vs. Chat Mode) with a **unified input surface** that intelligently routes every input to the right experience. One text field handles everything: project creation, queries, actions, and conversations.

**The magic**: Type anything → AI understands intent → beautiful response materializes.

**Key insight**: Introduce **Blocks** — lightweight surface elements with embedded actions. Blocks can appear anywhere: Home, workspace sidebars, floating overlays. They share infrastructure with RFC-072 Primitives but are optimized for quick information and actions.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                         ✦  SUNWELL  ✦                          │
│                                                                 │
│         ╭───────────────────────────────────────────╮          │
│         │  What would you like to create?           │          │
│         ╰───────────────────────────────────────────╯          │
│                                                                 │
│    "build a pirate game"     → workspace materializes          │
│    "show my habits"          → habits surface slides in        │
│    "add milk to groceries"   → toast confirms action           │
│    "what's on my calendar?"  → calendar unfolds below          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Goals

1. **One input, universal routing** — Every interaction starts from the same place
2. **Intelligent intent detection** — Workspace vs. view vs. action vs. conversation
3. **Tetris-style surface composition** — Primitives flow and snap into beautiful arrangements
4. **Wow-worthy aesthetics** — Animations, transitions, ambient effects that delight
5. **Zero new buttons** — The input bar IS the interface; UI elements emerge from intent
6. **Progressive reveal** — Simple by default, complexity surfaces when needed

## Non-Goals

1. **Voice input** — Text-first for now; voice is future work
2. **Multi-surface management** — Focus on single unified surface first
3. **Custom primitive creation** — Pre-built primitives only
4. **Offline-first** — Assumes LLM availability for intent analysis

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Input location** | Centered on Home, persists across views | Single entry point, always accessible |
| **Intent analysis** | LLM-powered (IntentAnalyzer from RFC-075) | Handles ambiguity, natural language |
| **Routing** | Reuse existing `InteractionRouter` | No duplication; RFC-075 already implements this |
| **Surface rendering** | Tetris layout system | Beautiful, dynamic, memorable |
| **Transition timing** | 300ms spring physics | Snappy but organic |
| **Block persistence** | Blocks stay until dismissed | Users control when to clear |
| **Block actions** | Embedded in `BlockDef` | Each block carries its own actions |
| **Chat Mode** | Removed — unified into Home | No split experiences |

---

## Block-First Philosophy

**Everything on the Home surface is a Block.**

Blocks are Home-optimized primitives. They share DNA with RFC-072 workspace primitives (same registry pattern, same layout engine, same providers) but are tuned for quick information display and embedded actions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BLOCK-FIRST PRINCIPLE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WRONG MENTAL MODEL:              RIGHT MENTAL MODEL:                       │
│  ─────────────────────           ────────────────────                       │
│                                                                             │
│  • Home has "views"              • Home has Blocks                          │
│  • Views display data            • Blocks display data + expose actions     │
│  • Navigation is separate        • Navigation is a Block (or just type it) │
│  • Actions are separate          • Actions are embedded in Blocks           │
│                                                                             │
│  Result: Fragmented UX           Result: Unified, composable surface        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Block Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| **Data Blocks** | Display provider data with quick actions | HabitsBlock, CalendarBlock, ProjectsBlock |
| **Action Blocks** | Quick actions without data display | QuickActionsBlock |
| **Conversation Blocks** | AI responses | ConversationBlock |
| **Workspace Blocks** | Transition to full workspace | WorkspaceBlock (triggers Project view) |

### Block vs. Primitive

| Aspect | Blocks (RFC-080) | Primitives (RFC-072) |
|--------|------------------|----------------------|
| **Purpose** | Information + quick actions | Full creation tools |
| **Complexity** | Low (cards, widgets) | High (editors, boards) |
| **Typical size** | Widget/panel | Full/split/panel |
| **Actions** | External (via ActionExecutor) | Internal (editor commands) |
| **Data** | Provider-fetched | User-created content |
| **Where** | **Anywhere** — Home, workspace sidebars, floating overlays | Primarily workspace |

**Key insight**: Blocks and Primitives are both **Surface Elements**. They differ in complexity, not in where they can live.

### Promotion Path

Blocks can **escalate** to Primitives when more power is needed:

```
HabitsBlock (widget)    →  "edit habit details"  →  HabitsManager (primitive)
CalendarBlock (widget)  →  "plan my week"        →  Calendar (primitive)  
ProjectsBlock (widget)  →  "open project"        →  Full Workspace
```

### Where Blocks Can Appear

Blocks are **universal surface elements** — they can appear anywhere in the surface system:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BLOCK PLACEMENT OPTIONS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. HOME SURFACE (inline below input)                                       │
│     "show my habits" → HabitsBlock materializes                             │
│                                                                             │
│  2. HOME CONTEXTUAL (always visible based on context)                       │
│     ProjectsBlock always shown if projects exist                            │
│     HabitsBlock shown in morning if habits configured                       │
│                                                                             │
│  3. WORKSPACE SECONDARY SLOT                                                │
│     GitBlock in sidebar while coding                                        │
│     CalendarBlock showing today's meetings                                  │
│                                                                             │
│  4. WORKSPACE CONTEXTUAL (floating)                                         │
│     ConversationBlock as floating assistant                                 │
│     NotificationsBlock as overlay                                           │
│                                                                             │
│  5. DASHBOARD ARRANGEMENT                                                   │
│     Multiple blocks in a grid layout                                        │
│     "Show me my day" → Calendar + Habits + Projects blocks                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Example: Workspace with Block in sidebar**

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────┬───────────────────────────┐   │
│  │                             │ FileTree (primitive)      │   │
│  │    CodeEditor               ├───────────────────────────┤   │
│  │    (primitive)              │ ┌───────────────────────┐ │   │
│  │                             │ │ GitBlock              │ │   │
│  │                             │ │ ○ main (2 ahead)      │ │   │
│  │                             │ │ ┌──────┐ ┌──────┐    │ │   │
│  │                             │ │ │Commit│ │ Push │    │ │   │
│  │                             │ │ └──────┘ └──────┘    │ │   │
│  │                             │ └───────────────────────┘ │   │
│  └─────────────────────────────┴───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        ↑ Primitive                        ↑ Block in secondary slot
```

---

## Motivation

### The Current Split Experience

Today's Sunwell has two distinct entry points:

1. **Home InputBar** → Always assumes project creation → Goes to Project view
2. **Chat Mode** → Uses IntentAnalyzer → Can route to workspace/view/action/conversation

This creates confusion:
- "Should I use Chat Mode or the main input?"
- "Why do I need to switch modes to ask about my habits?"
- "The app feels like two different products"

### The Unified Vision

One input that understands context:

```
User types: "build a todo app"
→ IntentAnalyzer: workspace intent (high confidence)
→ Lens picker appears
→ Workspace materializes with CodeEditor, FileTree, Terminal

User types: "show my habits"
→ IntentAnalyzer: view intent, type: habits
→ Habits surface slides up from bottom
→ Beautiful habit cards with streaks, completion rings

User types: "remind me to call mom at 5pm"
→ IntentAnalyzer: action intent, type: create_reminder
→ Reminder created
→ Confirmation toast with undo option

User types: "what's the best way to learn Rust?"
→ IntentAnalyzer: conversation intent
→ Response surfaces below input
→ Optional follow-up input appears
```

### Why "Tetris" Layouts?

Traditional layouts are rigid grids. Tetris layouts are:

- **Fluid** — Blocks adapt to content, not vice versa
- **Satisfying** — Elements snap into place with physics-based animations
- **Memorable** — Unique arrangements for different contexts
- **Delightful** — Micro-interactions that spark joy

The same Tetris engine powers both Home blocks and workspace primitives.

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     UNIFIED HOME SURFACE (RFC-080)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      INPUT BAR (Always Visible)                   │   │
│  │                                                                   │   │
│  │   ╭─────────────────────────────────────────────────────────╮    │   │
│  │   │  ✦  What would you like to create?                      │    │   │
│  │   ╰─────────────────────────────────────────────────────────╯    │   │
│  └────────────────────────────┬──────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              INTERACTION ROUTER (RFC-075 — reused)               │   │
│  │                                                                   │   │
│  │   IntentAnalyzer.analyze("show my habits")                       │   │
│  │   → {type: "view", view_type: "habits", confidence: 0.95}        │   │
│  │   InteractionRouter.route(analysis)                              │   │
│  │   → BlockOutput or WorkspaceOutput                               │   │
│  └────────────────────────────┬──────────────────────────────────────┘   │
│                               │                                         │
│           ┌───────────────────┼───────────────────┐                     │
│           ▼                   ▼                   ▼                     │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│   │  WORKSPACE   │   │    BLOCK     │   │   ACTION     │               │
│   │              │   │              │   │              │               │
│   │  Full tetris │   │  Inline      │   │  Toast +     │               │
│   │  layout with │   │  block       │   │  subtle      │               │
│   │  primitives  │   │  below input │   │  feedback    │               │
│   │              │   │              │   │              │               │
│   │  → Project   │   │  Stays on    │   │  Stays on    │               │
│   │    view      │   │  Home        │   │  Home        │               │
│   └──────────────┘   └──────────────┘   └──────────────┘               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    SHARED INFRASTRUCTURE                          │   │
│  │                                                                   │   │
│  │   Providers (RFC-078)  │  Tetris Layout  │  Holy Light (RFC-061) │   │
│  │   habits, calendar...  │  spring physics │  design tokens        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Block Type Definitions

```python
# src/sunwell/surface/blocks.py (NEW)

from dataclasses import dataclass
from sunwell.surface.types import PrimitiveSize

@dataclass(frozen=True, slots=True)
class BlockAction:
    """An action that a block can perform."""
    id: str                      # "complete", "skip", "open"
    label: str                   # "+1", "Skip", "Open"
    icon: str | None = None      # "✓", "→", "▶"
    requires_selection: bool = False  # Does it need an item selected?

@dataclass(frozen=True, slots=True)
class BlockDef:
    """Definition of a block — usable anywhere in the surface system.
    
    Blocks are lightweight surface elements with embedded actions and provider binding.
    They share the same registry pattern and slot system as RFC-072 PrimitiveDef.
    """
    id: str
    """Unique identifier (e.g., "HabitsBlock", "ProjectsBlock")."""
    
    category: str
    """Category: "data", "actions", "conversation", "workspace"."""
    
    component: str
    """Svelte component name to render."""
    
    provider: str | None = None
    """RFC-078 provider to bind: "habits", "calendar", "contacts", etc."""
    
    actions: tuple[BlockAction, ...] = ()
    """Actions this block can perform (displayed as buttons)."""
    
    # Slot capabilities — same as PrimitiveDef!
    can_be_primary: bool = False
    """Whether this block can fill the main area (rare for blocks)."""
    
    can_be_secondary: bool = True
    """Whether this block can appear in sidebars/panels."""
    
    can_be_contextual: bool = True
    """Whether this block can float/overlay."""
    
    default_size: PrimitiveSize = "widget"
    """Default size: "widget", "panel", "full"."""
    
    contextual_on_home: bool = False
    """Whether this block auto-appears on Home based on context."""
    
    refresh_events: tuple[str, ...] = ()
    """Events that trigger data refresh."""


# Example block definitions
DEFAULT_BLOCKS = [
    BlockDef(
        id="HabitsBlock",
        category="data",
        component="HabitsBlock",
        provider="habits",
        actions=(
            BlockAction(id="complete", label="+1", icon="✓"),
            BlockAction(id="skip", label="Skip today", icon="→"),
        ),
        can_be_secondary=True,       # Can appear in workspace sidebar
        can_be_contextual=True,      # Can float
        contextual_on_home=True,     # Auto-shows on Home in morning
        refresh_events=("habit_completed", "habit_created"),
    ),
    BlockDef(
        id="ProjectsBlock",
        category="data",
        component="ProjectsBlock",
        provider="projects",
        actions=(
            BlockAction(id="open", label="Open", icon="▶", requires_selection=True),
            BlockAction(id="resume", label="Resume", requires_selection=True),
            BlockAction(id="archive", label="Archive", requires_selection=True),
        ),
        contextual_on_home=True,     # Always shows on Home if projects exist
    ),
    BlockDef(
        id="CalendarBlock",
        category="data",
        component="CalendarBlock",
        provider="calendar",
        actions=(
            BlockAction(id="add_event", label="+ Event", icon="📅"),
        ),
        can_be_secondary=True,       # Can appear in workspace sidebar
        contextual_on_home=True,     # Shows on Home if events today
    ),
    BlockDef(
        id="GitBlock",
        category="data",
        component="GitBlock",
        provider="git",
        actions=(
            BlockAction(id="commit", label="Commit", icon="✓"),
            BlockAction(id="push", label="Push", icon="↑"),
            BlockAction(id="pull", label="Pull", icon="↓"),
        ),
        can_be_secondary=True,       # Ideal for workspace sidebar
        can_be_contextual=False,     # Not a floating block
        contextual_on_home=False,    # Only shows when requested
    ),
    BlockDef(
        id="ConversationBlock",
        category="conversation",
        component="ConversationBlock",
        actions=(
            BlockAction(id="follow_up", label="Ask more"),
            BlockAction(id="dismiss", label="Dismiss", icon="✕"),
        ),
        can_be_contextual=True,      # Perfect for floating assistant
    ),
]
```

### Routing (Reuses RFC-075)

**No new router needed.** The existing `InteractionRouter` from RFC-075 already handles all routing:

```python
# Existing: src/sunwell/interface/router.py (already implemented)
# Just call it from the frontend

from sunwell.interface.router import process_goal, InteractionRouter
from sunwell.interface.analyzer import IntentAnalyzer

# Process user input through existing pipeline
async def handle_home_input(goal: str) -> ViewOutput | ActionOutput | ...:
    """Route Home input through existing RFC-075 infrastructure."""
    return await process_goal(goal, analyzer, router)
```

The frontend interprets the output type and renders the appropriate block:

| Router Output | Frontend Action |
|---------------|-----------------|
| `ViewOutput` | Render data block (HabitsBlock, CalendarBlock, etc.) |
| `ActionOutput` | Show toast confirmation |
| `ConversationOutput` | Render ConversationBlock |
| `WorkspaceOutput` | Show lens picker → navigate to Project view |
| `HybridOutput` | Toast + data block |

### Tetris Layout System

The tetris system arranges blocks with organic, physics-based placement:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      TETRIS LAYOUT PRINCIPLES                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. GOLDEN SECTIONS                                                     │
│     Primary content uses φ (1.618) proportions                          │
│                                                                         │
│     ┌────────────────────────────┬─────────────────┐                   │
│     │                            │                 │                   │
│     │        PRIMARY             │   SECONDARY     │   φ ratio         │
│     │        (61.8%)             │   (38.2%)       │                   │
│     │                            │                 │                   │
│     └────────────────────────────┴─────────────────┘                   │
│                                                                         │
│  2. SNAP ZONES                                                          │
│     Blocks gravitate to natural positions                               │
│                                                                         │
│     ╭───────╮ ╭─────────────────────────────────────╮                  │
│     │ SIDE  │ │                                     │                  │
│     │ BAR   │ │           MAIN CONTENT              │                  │
│     │       │ │                                     │                  │
│     ╰───────╯ ├─────────────────────────────────────┤                  │
│               │        CONTEXTUAL STRIP             │                  │
│               ╰─────────────────────────────────────╯                  │
│                                                                         │
│  3. FLUID ADAPTATION                                                    │
│     Layouts breathe based on content                                    │
│                                                                         │
│     Few habits:           Many habits:                                  │
│     ╭─────────────╮       ╭─────────────────────────╮                  │
│     │ ○ Exercise  │       │ ○ Exercise  ○ Reading   │                  │
│     │ ○ Reading   │       │ ○ Meditate  ○ Journal   │                  │
│     ╰─────────────╯       │ ○ Water     ○ Walk      │                  │
│                           ╰─────────────────────────╯                  │
│                                                                         │
│  4. SPRING PHYSICS                                                      │
│     Elements animate with natural easing                                │
│                                                                         │
│     position = spring(target, {                                        │
│       stiffness: 300,                                                  │
│       damping: 30,                                                     │
│       mass: 1                                                          │
│     })                                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Block Surface Components

New Svelte components for inline block rendering:

```svelte
<!-- studio/src/components/home/BlockSurface.svelte -->
<script lang="ts">
  /**
   * BlockSurface — Renders blocks inline on Home
   * 
   * Tetris-style animated surface that appears below the input.
   * Blocks are Home-optimized primitives with embedded actions.
   */
  
  import { fly, scale } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  import HabitsBlock from './blocks/HabitsBlock.svelte';
  import ContactsBlock from './blocks/ContactsBlock.svelte';
  import CalendarBlock from './blocks/CalendarBlock.svelte';
  import FilesBlock from './blocks/FilesBlock.svelte';
  import ProjectsBlock from './blocks/ProjectsBlock.svelte';
  import GitBlock from './blocks/GitBlock.svelte';
  import BookmarksBlock from './blocks/BookmarksBlock.svelte';
  import GenericBlock from './blocks/GenericBlock.svelte';
  
  interface Props {
    blockType: string;
    blockData: Record<string, any>;
    response?: string;
    onDismiss?: () => void;
    onAction?: (actionId: string, itemId?: string) => void;
  }
  
  let { blockType, blockData, response, onDismiss, onAction }: Props = $props();
  
  // Spring animation for height
  let surfaceHeight = spring(0, { stiffness: 300, damping: 30 });
  
  const blockComponents: Record<string, any> = {
    habits: HabitsBlock,
    contacts: ContactsBlock,
    calendar: CalendarBlock,
    files: FilesBlock,
    projects: ProjectsBlock,
    git_status: GitBlock,
    git_log: GitBlock,
    git_branches: GitBlock,
    bookmarks: BookmarksBlock,
  };
  
  $effect(() => {
    // Animate to appropriate height based on content
    const contentHeight = calculateHeight(blockType, blockData);
    surfaceHeight.set(contentHeight);
  });
  
  function calculateHeight(type: string, data: Record<string, any>): number {
    // Dynamic height based on content
    const itemCount = data.habits?.length || 
                      data.contacts?.length || 
                      data.events?.length || 
                      data.files?.length || 
                      data.items?.length || 
                      0;
    const baseHeight = 120;
    const itemHeight = 64;
    return Math.min(baseHeight + (itemCount * itemHeight), 600);
  }
  
  function handleAction(actionId: string, itemId?: string) {
    onAction?.(actionId, itemId);
  }
</script>

<div 
  class="block-surface"
  style:height="{$surfaceHeight}px"
  in:fly={{ y: 50, duration: 300 }}
  out:scale={{ start: 0.95, duration: 200 }}
>
  {#if response}
    <div class="response-header">
      <p class="response-text">{response}</p>
      <button class="dismiss-btn" onclick={onDismiss}>✕</button>
    </div>
  {/if}
  
  <div class="block-content">
    {#if blockComponents[blockType]}
      <svelte:component 
        this={blockComponents[blockType]} 
        data={blockData} 
        {onAction}
      />
    {:else}
      <GenericBlock type={blockType} data={blockData} />
    {/if}
  </div>
</div>

<style>
  .block-surface {
    position: relative;
    margin-top: var(--space-6);
    background: linear-gradient(
      180deg,
      rgba(255, 215, 0, 0.03) 0%,
      rgba(10, 10, 10, 0.95) 100%
    );
    border: 1px solid rgba(255, 215, 0, 0.15);
    border-radius: var(--radius-xl);
    overflow: hidden;
    backdrop-filter: blur(20px);
    
    /* Golden glow */
    box-shadow: 
      0 4px 24px rgba(0, 0, 0, 0.4),
      0 0 60px rgba(255, 215, 0, 0.08),
      inset 0 1px 0 rgba(255, 215, 0, 0.1);
  }
  
  .response-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: var(--space-4);
    border-bottom: 1px solid rgba(255, 215, 0, 0.1);
  }
  
  .response-text {
    color: var(--text-secondary);
    font-size: var(--text-sm);
    margin: 0;
    flex: 1;
  }
  
  .dismiss-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
    
    &:hover {
      color: var(--gold);
      background: rgba(255, 215, 0, 0.1);
    }
  }
  
  .block-content {
    padding: var(--space-4);
    overflow-y: auto;
    max-height: calc(100% - 60px);
  }
</style>
```

### Habits Block Component

```svelte
<!-- studio/src/components/home/blocks/HabitsBlock.svelte -->
<script lang="ts">
  /**
   * HabitsBlock — Beautiful habit tracker with embedded actions
   * 
   * Shows habit cards with:
   * - Completion rings (animated)
   * - Streak flames
   * - Quick-complete buttons (BlockAction: "complete")
   * 
   * This is a Block, not a View — it has embedded actions.
   */
  
  import { fly, scale } from 'svelte/transition';
  import { tweened } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  
  interface Habit {
    id: string;
    name: string;
    streak: number;
    completed_today: number;
    target: number;
    is_complete: boolean;
    color?: string;
    icon?: string;
  }
  
  interface Props {
    data: {
      habits: Habit[];
      habit_count: number;
      complete_count: number;
      incomplete_count: number;
    };
    onAction?: (actionId: string, habitId?: string) => void;
  }
  
  let { data, onAction }: Props = $props();
  
  function handleComplete(habitId: string) {
    onAction?.('complete', habitId);
  }
  
  function handleSkip(habitId: string) {
    onAction?.('skip', habitId);
  }
  
  function getCompletionPercent(habit: Habit): number {
    return Math.min((habit.completed_today / habit.target) * 100, 100);
  }
  
  function getStreakEmoji(streak: number): string {
    if (streak >= 30) return '🔥';
    if (streak >= 7) return '✨';
    if (streak >= 3) return '⭐';
    return '';
  }
</script>

<div class="habits-view">
  <header class="habits-header">
    <h3 class="habits-title">Today's Habits</h3>
    <div class="habits-summary">
      <span class="complete-count">{data.complete_count}</span>
      <span class="separator">/</span>
      <span class="total-count">{data.habit_count}</span>
      <span class="label">complete</span>
    </div>
  </header>
  
  <div class="habits-grid">
    {#each data.habits as habit, i (habit.id)}
      <div 
        class="habit-card"
        class:complete={habit.is_complete}
        in:fly={{ y: 20, delay: i * 50, duration: 300 }}
      >
        <div class="habit-ring">
          <svg viewBox="0 0 36 36" class="circular-chart">
            <path
              class="circle-bg"
              d="M18 2.0845
                 a 15.9155 15.9155 0 0 1 0 31.831
                 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              class="circle"
              stroke-dasharray="{getCompletionPercent(habit)}, 100"
              d="M18 2.0845
                 a 15.9155 15.9155 0 0 1 0 31.831
                 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
          <span class="habit-icon">{habit.icon || '○'}</span>
        </div>
        
        <div class="habit-info">
          <span class="habit-name">{habit.name}</span>
          <span class="habit-progress">
            {habit.completed_today}/{habit.target}
            {#if habit.streak > 0}
              <span class="streak">
                {getStreakEmoji(habit.streak)} {habit.streak}d
              </span>
            {/if}
          </span>
        </div>
        
        {#if !habit.is_complete}
          <button class="quick-complete" onclick={() => handleComplete(habit.id)}>+1</button>
        {:else}
          <span class="check-mark">✓</span>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .habits-view {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  
  .habits-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .habits-title {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .habits-summary {
    display: flex;
    align-items: baseline;
    gap: var(--space-1);
    font-size: var(--text-sm);
  }
  
  .complete-count {
    color: var(--gold);
    font-weight: 700;
    font-size: var(--text-xl);
  }
  
  .separator {
    color: var(--text-tertiary);
  }
  
  .total-count {
    color: var(--text-secondary);
    font-weight: 500;
  }
  
  .label {
    color: var(--text-tertiary);
    margin-left: var(--space-1);
  }
  
  .habits-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: var(--space-3);
  }
  
  .habit-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 215, 0, 0.1);
    border-radius: var(--radius-lg);
    transition: all 0.2s ease;
    
    &:hover {
      background: rgba(255, 215, 0, 0.05);
      border-color: rgba(255, 215, 0, 0.2);
      transform: translateY(-2px);
    }
    
    &.complete {
      opacity: 0.7;
    }
  }
  
  .habit-ring {
    position: relative;
    width: 44px;
    height: 44px;
    flex-shrink: 0;
  }
  
  .circular-chart {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  
  .circle-bg {
    fill: none;
    stroke: rgba(255, 215, 0, 0.1);
    stroke-width: 3;
  }
  
  .circle {
    fill: none;
    stroke: var(--gold);
    stroke-width: 3;
    stroke-linecap: round;
    transition: stroke-dasharray 0.6s ease;
  }
  
  .habit-icon {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: var(--text-lg);
  }
  
  .habit-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
  }
  
  .habit-name {
    color: var(--text-primary);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .habit-progress {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .streak {
    color: var(--gold);
    font-weight: 500;
  }
  
  .quick-complete {
    padding: var(--space-2) var(--space-3);
    background: rgba(255, 215, 0, 0.1);
    border: 1px solid rgba(255, 215, 0, 0.3);
    border-radius: var(--radius-md);
    color: var(--gold);
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    
    &:hover {
      background: rgba(255, 215, 0, 0.2);
      transform: scale(1.05);
    }
  }
  
  .check-mark {
    color: var(--success);
    font-size: var(--text-xl);
    font-weight: bold;
  }
</style>
```

### Updated Home.svelte

```svelte
<!-- studio/src/routes/Home.svelte (updated) -->
<script lang="ts">
  import { untrack } from 'svelte';
  import Logo from '../components/Logo.svelte';
  import InputBar from '../components/InputBar.svelte';
  import BlockSurface from '../components/home/BlockSurface.svelte';
  import ActionToast from '../components/home/ActionToast.svelte';
  import ConversationBlock from '../components/home/blocks/ConversationBlock.svelte';
  import ProjectsBlock from '../components/home/blocks/ProjectsBlock.svelte';
  import RisingMotes from '../components/RisingMotes.svelte';
  import MouseMotes from '../components/MouseMotes.svelte';
  import LensPicker from '../components/LensPicker.svelte';
  import { goToProject } from '../stores/app.svelte';
  import { project, openProject } from '../stores/project.svelte';
  import { routeInput, homeState, clearResponse, executeBlockAction } from '../stores/home.svelte';
  import { runGoal } from '../stores/agent.svelte';
  
  let inputValue = $state('');
  let inputBar: InputBar;
  let isProcessing = $state(false);
  
  // Lens picker state (for workspace intents)
  let showLensPicker = $state(false);
  let pendingGoal = $state<string | null>(null);
  let pendingWorkspaceSpec = $state<any>(null);
  
  async function handleSubmit(goal: string) {
    if (!goal || isProcessing) return;
    
    isProcessing = true;
    inputValue = '';
    
    try {
      // Route through existing InteractionRouter (RFC-075)
      const response = await routeInput(goal);
      
      if (response.route === 'workspace') {
        // Show lens picker for workspace creation
        pendingGoal = goal;
        pendingWorkspaceSpec = response.workspace_spec;
        showLensPicker = true;
      }
      // Other routes (block, action, conversation) are handled
      // by the home store and rendered via reactive state
      
    } finally {
      isProcessing = false;
    }
  }
  
  async function handleLensConfirm(lensName: string | null, autoSelect: boolean) {
    if (!pendingGoal) return;
    
    const workspacePath = await runGoal(pendingGoal, undefined, lensName, autoSelect);
    if (workspacePath) {
      await openProject(workspacePath);
      goToProject();
    }
    
    pendingGoal = null;
    pendingWorkspaceSpec = null;
    showLensPicker = false;
  }
  
  function handleDismissBlock() {
    clearResponse();
  }
  
  async function handleBlockAction(actionId: string, itemId?: string) {
    // Execute action through ActionExecutor (RFC-075)
    await executeBlockAction(actionId, itemId);
  }
</script>

<MouseMotes spawnRate={30} maxParticles={20}>
  {#snippet children()}
    <div class="home">
      <RisingMotes />
      
      <!-- Logo and Input -->
      <header class="hero">
        <Logo size="large" />
        <h1 class="tagline">What would you like to create?</h1>
        <InputBar
          bind:this={inputBar}
          bind:value={inputValue}
          placeholder="Build a pirate game, show my habits, remind me at 5pm..."
          onsubmit={handleSubmit}
          loading={isProcessing}
        />
      </header>
      
      <!-- Dynamic Block Surface (Tetris layout) -->
      {#if homeState.response}
        {#if homeState.response.route === 'view'}
          <BlockSurface
            blockType={homeState.response.view_type}
            blockData={homeState.response.view_data}
            response={homeState.response.response}
            onDismiss={handleDismissBlock}
            onAction={handleBlockAction}
          />
        {:else if homeState.response.route === 'action'}
          <ActionToast
            actionType={homeState.response.action_type}
            success={homeState.response.success}
            message={homeState.response.response}
          />
        {:else if homeState.response.route === 'conversation'}
          <ConversationBlock
            message={homeState.response.response}
            mode={homeState.response.conversation_mode}
            onAction={handleBlockAction}
          />
        {:else if homeState.response.route === 'hybrid'}
          <ActionToast
            actionType={homeState.response.action_type}
            success={homeState.response.success}
            message={homeState.response.response}
          />
          <BlockSurface
            blockType={homeState.response.view_type}
            blockData={homeState.response.view_data}
            onAction={handleBlockAction}
          />
        {/if}
      {/if}
      
      <!-- Contextual Blocks (always shown based on context) -->
      <section class="contextual-blocks" class:collapsed={homeState.response}>
        <ProjectsBlock 
          data={{ projects: project.discovered, project_count: project.discovered.length }}
          onAction={handleBlockAction}
        />
      </section>
      
      <footer class="version">v0.1.0</footer>
    </div>
  {/snippet}
</MouseMotes>

<!-- Lens Picker Modal -->
<LensPicker
  isOpen={showLensPicker}
  onClose={() => { showLensPicker = false; pendingGoal = null; }}
  onConfirm={handleLensConfirm}
/>

<style>
  .home {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-8);
    background: radial-gradient(
      ellipse at center top,
      rgba(255, 215, 0, 0.08) 0%,
      transparent 50%
    );
  }
  
  .hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
    margin-top: 15vh;
    text-align: center;
  }
  
  .tagline {
    font-size: var(--text-xl);
    font-weight: 400;
    color: var(--text-secondary);
    margin: 0;
  }
  
  /* Contextual blocks — always shown based on user context */
  .contextual-blocks {
    width: 100%;
    max-width: 600px;
    margin-top: var(--space-8);
    transition: all 0.3s ease;
    
    &.collapsed {
      margin-top: var(--space-4);
      opacity: 0.5;
      transform: scale(0.95);
    }
  }
  
  .version {
    position: fixed;
    bottom: var(--space-4);
    right: var(--space-4);
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
</style>
```

---

## Tetris Animation System

### Spring Physics Configuration

```typescript
// studio/src/lib/tetris.ts

/**
 * Tetris Layout System — Spring physics and snap zones
 */

import { spring, tweened } from 'svelte/motion';
import { cubicOut, elasticOut } from 'svelte/easing';

export const SPRING_CONFIGS = {
  // Snappy but organic
  default: { stiffness: 300, damping: 30 },
  
  // Quick response for small elements
  quick: { stiffness: 400, damping: 25 },
  
  // Smooth for large surface changes
  smooth: { stiffness: 200, damping: 35 },
  
  // Bouncy for celebratory moments
  bouncy: { stiffness: 500, damping: 15 },
} as const;

export const GOLDEN_RATIO = 1.618;

/**
 * Calculate tetris snap zones based on viewport
 */
export function calculateSnapZones(viewport: { width: number; height: number }) {
  const primaryWidth = viewport.width / GOLDEN_RATIO;
  const secondaryWidth = viewport.width - primaryWidth;
  
  return {
    primary: { x: 0, width: primaryWidth, height: viewport.height },
    sidebar: { x: primaryWidth, width: secondaryWidth, height: viewport.height * 0.7 },
    bottom: { x: primaryWidth, y: viewport.height * 0.7, width: secondaryWidth, height: viewport.height * 0.3 },
  };
}

/**
 * Stagger delay for list items (tetris cascade effect)
 */
export function staggerDelay(index: number, base = 50): number {
  return index * base;
}

/**
 * Entrance animations for blocks
 */
export const ENTRANCE_ANIMATIONS = {
  slideUp: { y: 50, duration: 300 },
  slideLeft: { x: -30, duration: 250 },
  slideRight: { x: 30, duration: 250 },
  scaleIn: { start: 0.9, duration: 200 },
  fadeIn: { duration: 150 },
} as const;
```

---

## Block ↔ Primitive Synergy

**Blocks and Primitives are both Surface Elements.** They share the same infrastructure and can coexist in the same layout:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SHARED INFRASTRUCTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    PROVIDERS (RFC-078)                                │ │
│  │                                                                       │ │
│  │   habits, calendar, contacts, files, git, bookmarks, projects...     │ │
│  │                                                                       │ │
│  │   Block: HabitsBlock.render(await habits.list_habits())              │ │
│  │   Primitive: Calendar.render(await calendar.get_events())            │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    TETRIS LAYOUT ENGINE                               │ │
│  │                                                                       │ │
│  │   Spring physics, snap zones, golden ratio, staggered animations     │ │
│  │                                                                       │ │
│  │   Blocks: BlockLayout with widget-sized elements                     │ │
│  │   Primitives: SurfaceLayout with full/split/panel elements           │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    HOLY LIGHT DESIGN SYSTEM (RFC-061)                 │ │
│  │                                                                       │ │
│  │   Same design tokens, same animations, same visual language          │ │
│  │   Blocks and Primitives feel like the same product                   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    REGISTRY PATTERN                                   │ │
│  │                                                                       │ │
│  │   BlockRegistry.get("HabitsBlock")   // Home blocks                  │ │
│  │   PrimitiveRegistry.get("Calendar")  // Workspace primitives         │ │
│  │   Same lookup, validation, category filtering                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mixed Layouts: Primitives + Blocks Together

A workspace can contain both primitives and blocks:

```python
# Example: Coding workspace with GitBlock in sidebar
SurfaceLayout(
    primary=SurfacePrimitive(id="CodeEditor", ...),      # Primitive
    secondary=(
        SurfacePrimitive(id="FileTree", ...),            # Primitive
        SurfaceBlock(id="GitBlock", ...),                # Block!
    ),
    contextual=(
        SurfaceBlock(id="ConversationBlock", ...),       # Floating block!
    ),
    arrangement="standard",
)
```

The renderer doesn't care whether an element is a Primitive or Block — it just places them according to their size and slot.

### Shared Type Hierarchy (Optional Future)

```python
# Possible unification (not required for MVP)
@dataclass(frozen=True, slots=True)
class SurfaceElementDef:
    """Base for both primitives and blocks."""
    id: str
    category: str
    component: str
    default_size: PrimitiveSize
    can_be_primary: bool
    can_be_secondary: bool
    can_be_contextual: bool

class PrimitiveDef(SurfaceElementDef):
    """Workspace primitive — full creation tools."""
    # No actions field — complex internal state
    pass

class BlockDef(SurfaceElementDef):
    """Block — lightweight with embedded actions."""
    actions: tuple[BlockAction, ...] = ()
    provider: str | None = None
    contextual_on_home: bool = False
```

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Intent misclassification** | User gets wrong response type | Medium | Fallback to conversation; "Did you mean...?" prompt |
| **Animation performance** | Jank on low-end devices | Low | Progressive enhancement; reduce particles on slow devices |
| **Provider latency** | Slow block rendering | Medium | Optimistic UI; skeleton loaders; cache recent data |
| **Block action failures** | User confusion | Low | Clear error toasts; undo support where possible |
| **LLM unavailability** | App unusable | Low | Graceful fallback to keyword matching for common intents |
| **User mental model** | "Where's Chat Mode?" | Medium | Onboarding tooltip; input placeholder hints |

### Fallback Chain

```
Intent Analysis Failed?
  → Try keyword matching ("show habits" → HabitsBlock)
  → Still failed? Show conversation: "I'm not sure what you meant. Try..."
  
Block Render Failed?
  → Show error state with retry button
  → Log to telemetry for improvement
  
Action Execution Failed?
  → Toast with error message
  → Undo not available (action never completed)
```

---

## Design Alternatives Considered

### Option A: Enhance Interface.svelte to be Home (Rejected)

**Approach**: Make the existing Interface.svelte (Chat Mode) the default Home experience.

**Pros**:
- Less new code; builds on existing InterfaceOutput component
- Conversation-first UX

**Cons**:
- Interface.svelte is conversation-oriented, not block-oriented
- Would require significant refactoring to support contextual blocks
- Loses the clean "one input" aesthetic

**Decision**: Rejected — merging into Home.svelte is cleaner.

### Option B: Keep Chat Mode as Separate Route (Rejected)

**Approach**: Keep Home for projects, Chat Mode for everything else.

**Pros**:
- No migration risk
- Clear separation of concerns

**Cons**:
- Perpetuates the split experience problem
- Users must know which mode to use
- Two codepaths to maintain

**Decision**: Rejected — the whole point is unification.

### Option C: Unified Home with Block System (Selected) ✅

**Approach**: Single Home surface with blocks that materialize from intent.

**Pros**:
- One mental model for users
- Blocks are composable and reusable
- Shares infrastructure with RFC-072 primitives
- Clean, magical UX

**Cons**:
- Requires new BlockDef type system
- More upfront work

**Decision**: Selected — best long-term UX.

---

## Implementation Plan

### Phase 1: Block Infrastructure (2 days)
- [ ] Create `BlockDef` and `BlockAction` types in `src/sunwell/surface/blocks.py`
- [ ] Create `BlockRegistry` (mirrors `PrimitiveRegistry`)
- [ ] Update `SurfaceRenderer` to handle blocks in secondary/contextual slots
- [ ] Create `home.svelte.ts` store for state management
- [ ] Wire up existing `InteractionRouter` to frontend

### Phase 2: Block Components (3 days)
- [ ] Create `BlockSurface.svelte` container
- [ ] Implement `HabitsBlock.svelte` with completion rings + actions
- [ ] Implement `ContactsBlock.svelte` with avatar cards + actions
- [ ] Implement `CalendarBlock.svelte` with timeline + actions
- [ ] Implement `ProjectsBlock.svelte` (replaces RecentProjects)
- [ ] Implement `GitBlock.svelte` for status/log/branches
- [ ] Implement `ConversationBlock.svelte` for dialogue

### Phase 3: Home Integration (2 days)
- [ ] Update `Home.svelte` with unified routing via existing `InteractionRouter`
- [ ] Add `ActionToast.svelte` for action feedback
- [ ] Implement contextual blocks (ProjectsBlock always shown)
- [ ] Remove Chat Mode button and Interface.svelte route

### Phase 4: Tetris Polish (2 days)
- [ ] Implement spring physics system in `tetris.ts`
- [ ] Add staggered entrance animations
- [ ] Golden ratio layout calculations
- [ ] Ambient glow effects
- [ ] Micro-interactions (hover, focus, active)

### Phase 5: Testing & Refinement (1 day)
- [ ] Integration tests for block rendering
- [ ] Test block actions execute correctly
- [ ] Visual regression tests
- [ ] Performance profiling
- [ ] Edge case handling (empty states, errors)

**Total: ~10 days**

---

## Success Criteria

1. **One input handles all** — No Chat Mode button needed
2. **Intent routing accuracy** — >90% correct classification
3. **Smooth animations** — 60fps transitions, no jank
4. **Delightful aesthetics** — Users say "wow" on first use
5. **Fast response** — <500ms from input to surface
6. **Beautiful views** — Habits, contacts, calendar render gorgeously

---

## Related RFCs

- **RFC-061**: Holy Light Design System — Visual foundation (shared by blocks and primitives)
- **RFC-072**: Surface Primitives — Workspace primitives (blocks extend this pattern)
- **RFC-075**: Generative Interface — Intent analysis and routing (reused, not duplicated)
- **RFC-078**: Primitive & Provider Roadmap — Data providers (shared by blocks and primitives)
- **RFC-079**: Project Intent Analyzer — Project understanding

### Key Integration Points

```
RFC-075 (IntentAnalyzer + InteractionRouter)
    │
    ├── "workspace" intent → RFC-072 Primitives + RFC-080 Blocks → Project View
    │                              │                    │
    │                              │                    └── Blocks in secondary/contextual slots
    │                              └── Primitives in primary/secondary slots
    │
    └── "view/action/conversation" intent → RFC-080 Blocks → Home Surface
                                                    │
                                                    └── Data from RFC-078 Providers
```

**Blocks are universal** — they appear on Home as inline responses AND in workspaces as sidebar widgets.

---

## Appendix: Block Type Registry

All supported block types and their components:

| Block Type | Component | Data Shape | Actions |
|------------|-----------|------------|---------|
| `habits` | `HabitsBlock` | `{habits: Habit[], complete_count, habit_count}` | `complete`, `skip` |
| `contacts` | `ContactsBlock` | `{contacts: Contact[], contact_count, all_tags}` | `call`, `message`, `email` |
| `calendar` | `CalendarBlock` | `{events: Event[], start, end}` | `add_event`, `rsvp` |
| `list` | `ListBlock` | `{items: Item[], list_name}` | `check`, `add`, `delete` |
| `notes` | `NotesBlock` | `{notes: Note[], mode}` | `open`, `create` |
| `files` | `FilesBlock` | `{files: FileInfo[], path, file_count}` | `open`, `preview` |
| `projects` | `ProjectsBlock` | `{projects: Project[], project_count}` | `open`, `resume`, `archive` |
| `git_status` | `GitBlock` | `{branch, files, is_clean}` | `stage`, `commit`, `push` |
| `git_log` | `GitBlock` | `{commits: Commit[]}` | `checkout`, `revert` |
| `git_branches` | `GitBlock` | `{local, remote, current}` | `checkout`, `create`, `delete` |
| `bookmarks` | `BookmarksBlock` | `{bookmarks: Bookmark[], all_tags}` | `open`, `delete`, `tag` |
| `search` | `SearchBlock` | `{results: SearchResult[], query}` | `open` |
| `conversation` | `ConversationBlock` | `{message: string, mode}` | `follow_up`, `dismiss` |

### Block Placement Capabilities

| Block | Home (contextual) | Home (explicit) | Workspace Secondary | Floating |
|-------|-------------------|-----------------|---------------------|----------|
| `ProjectsBlock` | ✅ Always | ✅ | ❌ | ❌ |
| `HabitsBlock` | ✅ Morning | ✅ | ✅ | ✅ |
| `CalendarBlock` | ✅ If events | ✅ | ✅ | ✅ |
| `GitBlock` | ❌ | ✅ | ✅ | ❌ |
| `ContactsBlock` | ❌ | ✅ | ✅ | ✅ |
| `ConversationBlock` | ❌ | ✅ | ❌ | ✅ |
| `ListBlock` | ❌ | ✅ | ✅ | ✅ |

### Contextual Appearance Rules (Home)

| Block | `contextual_on_home` | Appears When |
|-------|----------------------|--------------|
| `ProjectsBlock` | ✅ | Always (if projects exist) |
| `HabitsBlock` | ✅ | Morning hours (6am-12pm) if habits configured |
| `CalendarBlock` | ✅ | If upcoming events in next 24 hours |
| All others | ❌ | Only when explicitly requested via input |
