# RFC-072: Surface Primitives & Layout System

**Status**: Draft  
**Created**: 2026-01-21  
**Last Updated**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 92% 🟢  
**Depends on**:
- RFC-043 (Sunwell Studio) — GUI framework
- RFC-061 (Holy Light Design System) — Visual styling

**Depended on by**:
- RFC-075 (Generative Interface) — Routes workspace requests to this system

---

## Summary

Define the **Surface Primitives** — composable UI building blocks — and the **Layout System** that arranges them into workspaces. This RFC answers: "Given a layout specification, how do we render it?"

**Scope clarification**: This RFC handles **rendering** layouts, not **deciding** which layout to use. Intent analysis and interaction routing are handled by RFC-075 (Generative Interface), which sends `WorkspaceSpec` objects to this system.

**Three-domain implementation:**
- 🐍 **Python**: Layout rendering, primitive registration, spec validation
- 🦀 **Rust**: Tauri commands for layout persistence and primitive registry
- 🟠 **Svelte**: Composable primitive components, dynamic layout system

---

## Goals

1. **Comprehensive primitive library** — All UI building blocks needed for code, planning, writing, and data work
2. **Flexible layout arrangements** — Standard, focused, split, and dashboard arrangements
3. **Spec-driven rendering** — Accept `WorkspaceSpec` from RFC-075 and render accordingly
4. **Smooth transitions** — Animate between layouts without jarring reflows
5. **Progressive disclosure** — Core primitives visible, advanced primitives surfaced on demand
6. **Size adaptability** — Each primitive supports multiple size modes (full, split, panel, etc.)

## Non-Goals

1. **Intent analysis** — Deciding WHICH layout to show (that's RFC-075's job)
2. **Goal parsing** — Understanding user input (that's RFC-075's job)
3. **Fully AI-generated components** — Primitives are pre-built; RFC-075 selects them
4. **User-draggable layouts** — Not initially (future: user overrides)
5. **Custom primitive creation by users** — Primitives are shipped with Sunwell

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Input contract** | `WorkspaceSpec` from RFC-075 | Clean separation; this RFC renders, RFC-075 decides |
| **Primitive registry** | Rust-side with Tauri commands | Fast lookup, type-safe, accessible from Python and Svelte |
| **Layout persistence** | Local state + memory recording | Remember successful layouts for RFC-075 to learn from |
| **Fallback rendering** | Always show CodeEditor if spec invalid | Never empty surface; graceful degradation |
| **Transition timing** | 200ms animations | Smooth but not sluggish |
| **Size constraints** | Max 1 primary, 3 secondary, 2 contextual | Prevents UI overload |

---

## Motivation

### Why a Primitive-Based System?

Traditional IDEs have fixed layouts: file tree on left, editor in center, terminal at bottom. This works for code but fails for diverse creative work.

Sunwell supports multiple domains — code, planning, writing, data analysis — each with different UI needs. A primitive-based system allows:

```
Writing workspace:     ProseEditor (full) + Outline (sidebar) + WordCount (widget)
Code workspace:        CodeEditor (full) + FileTree (sidebar) + Terminal (bottom)
Planning workspace:    Kanban (full) + GoalTree (sidebar) + Metrics (widget)
Mixed workspace:       CodeEditor (split) + Kanban (split) + MemoryPane (floating)
```

### Separation from Intent Analysis

RFC-075 (Generative Interface) handles understanding user goals and deciding what to show. This RFC handles the rendering once that decision is made.

```
RFC-075 (Generative Interface)          RFC-072 (This RFC)
─────────────────────────────           ─────────────────────
"write a pirate novel"                  
        │                               
        ▼                               
 Intent Analysis (LLM)                  
        │                               
        ▼                               
 WorkspaceSpec {                        
   primary: ProseEditor      ─────────▶  Render primitives
   secondary: [Outline]                  Arrange in layout
   seed_content: {...}                   Animate transitions
 }                                       
```

This separation means:
- **RFC-072 is deterministic** — Same spec always produces same layout
- **RFC-075 is intelligent** — LLM reasoning about intent
- **Both are testable** — RFC-072 with mock specs, RFC-075 with mock rendering

### Cross-Domain Primitives

Real work spans domains. The primitive system supports mixing:

| Workspace Type | Primitives from Multiple Domains |
|----------------|----------------------------------|
| Code + Planning | CodeEditor + Kanban + TaskList |
| Writing + Research | ProseEditor + Notes + References |
| Data + Code | DataTable + CodeEditor + Chart |
| Review + Memory | DiffView + MemoryPane + Timeline |

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   SURFACE PRIMITIVES & LAYOUT SYSTEM                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              WORKSPACE SPEC (from RFC-075)                       │   │
│  │                                                                  │   │
│  │   {                                                              │   │
│  │     primary: "CodeEditor",                                       │   │
│  │     secondary: ["FileTree", "Terminal"],                         │   │
│  │     arrangement: "standard",                                     │   │
│  │     seed_content: { file: "/src/main.py" }                      │   │
│  │   }                                                              │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     SURFACE RENDERER                             │   │
│  │                                                                  │   │
│  │   1. Validate spec against primitive registry                   │   │
│  │   2. Build primitives with appropriate sizes                    │   │
│  │   3. Apply seed content                                         │   │
│  │   4. Emit SurfaceLayout                                         │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    PRIMITIVE REGISTRY                            │   │
│  │                                                                  │   │
│  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │   │
│  │   │CodeEdit │ │FileTree │ │Terminal │ │  Tests  │              │   │
│  │   └─────────┘ └─────────┘ └─────────┘ └─────────┘              │   │
│  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │   │
│  │   │ Kanban  │ │Timeline │ │  Notes  │ │ Memory  │              │   │
│  │   └─────────┘ └─────────┘ └─────────┘ └─────────┘              │   │
│  │                                                                  │   │
│  │   Each primitive defines: category, sizes, can_be_primary, etc. │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    LAYOUT ARRANGEMENTS                           │   │
│  │                                                                  │   │
│  │   standard:   [sidebar] [   primary   ] [bottom]                │   │
│  │   focused:    [         primary         ]                       │   │
│  │   split:      [  primary  ] [  secondary  ]                     │   │
│  │   dashboard:  [ prim ] [ sec ]                                  │   │
│  │               [ sec  ] [ ctx ]                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Surface Primitives

Composable UI components that can be arranged by the AI:

#### Code Domain

| Primitive | Purpose | Size Options |
|-----------|---------|--------------|
| `CodeEditor` | Edit source files | full, split, minimal |
| `FileTree` | Navigate project structure | sidebar, floating |
| `Terminal` | Run commands, see output | bottom, split, floating |
| `TestRunner` | Execute and view test results | panel, inline |
| `DiffView` | Show code changes | full, split |
| `Preview` | Live preview (web, API docs) | split, floating |
| `Dependencies` | Package/import visualization | sidebar, modal |

#### Planning Domain

| Primitive | Purpose | Size Options |
|-----------|---------|--------------|
| `Kanban` | Task board view | full, compact |
| `Timeline` | Gantt/roadmap view | full, strip |
| `GoalTree` | Hierarchical goals | sidebar, full |
| `TaskList` | Linear task list | panel, inline |
| `Calendar` | Date-based view | full, strip |
| `Metrics` | Progress/velocity | widget, panel |

#### Writing Domain

| Primitive | Purpose | Size Options |
|-----------|---------|--------------|
| `ProseEditor` | Long-form writing | full, split |
| `Outline` | Document structure | sidebar |
| `References` | Citations, links | panel, floating |
| `WordCount` | Stats and metrics | widget |
| `Preview` | Rendered output | split |

#### Data Domain

| Primitive | Purpose | Size Options |
|-----------|---------|--------------|
| `DataTable` | Spreadsheet view | full, panel |
| `Chart` | Visualizations | panel, full |
| `QueryBuilder` | Natural language → query | panel |
| `Summary` | AI-generated insights | widget |

#### Universal (Always Available)

| Primitive | Purpose | Size Options |
|-----------|---------|--------------|
| `MemoryPane` | Decisions, patterns, warnings | sidebar, floating |
| `Input` | Goal/chat input | bottom (fixed) |
| `DAGView` | Execution plan | panel, full |
| `BriefingCard` | Session orientation | widget, toast |

### Lens Affordances

Each lens defines which primitives are relevant for its domain. RFC-075 uses these affordances when building `WorkspaceSpec` objects; this RFC uses them to validate that requested primitives are appropriate.

**Schema extension** for `src/sunwell/core/lens.py`:

```python
# src/sunwell/core/lens.py — add to existing Lens dataclass

@dataclass(frozen=True, slots=True)
class PrimitiveAffordance:
    """A primitive that a lens can surface.
    
    Affordances define which UI primitives are relevant for a lens's domain
    and under what conditions they should be activated.
    """
    
    primitive: str
    """Primitive ID (e.g., "CodeEditor", "Terminal")."""
    
    default_size: str = "panel"
    """Default size: "full", "split", "panel", "sidebar", "widget", "floating"."""
    
    weight: float = 0.5
    """Base relevance weight (0.0-1.0). Higher = more likely to be selected."""
    
    trigger: str | None = None
    """Pipe-separated keywords that activate this primitive (e.g., "test|verify|coverage")."""
    
    mode_hint: str | None = None
    """Hint to switch lens when this primitive is activated (e.g., "coder")."""


@dataclass(frozen=True, slots=True)
class Affordances:
    """Surface affordances for a lens (RFC-072).
    
    Defines which UI primitives should be shown when this lens is active.
    Primitives are categorized by importance:
    - primary: Always shown, core to the domain
    - secondary: Shown when triggered or space permits
    - contextual: Floating/widget elements shown on demand
    """
    
    primary: tuple[PrimitiveAffordance, ...] = ()
    """Always-visible primitives (max 2)."""
    
    secondary: tuple[PrimitiveAffordance, ...] = ()
    """Conditionally-visible primitives (max 3)."""
    
    contextual: tuple[PrimitiveAffordance, ...] = ()
    """Floating/widget primitives (max 2)."""


# Add to Lens dataclass:
@dataclass(slots=True)
class Lens:
    # ... existing fields ...
    
    # RFC-072: Surface affordances
    affordances: Affordances | None = None
    """UI primitives this lens surfaces. None = use domain defaults."""
```

**YAML syntax** for lens files:

```yaml
# lenses/coder.lens (extended)
lens:
  metadata:
    name: "coder"
    domain: "software"
    
  # RFC-072: Surface affordances
  affordances:
    primary:
      - primitive: CodeEditor
        default_size: full
        weight: 1.0
      - primitive: FileTree
        default_size: sidebar
        weight: 0.9
      - primitive: Terminal
        default_size: bottom
        weight: 0.8
        
    secondary:
      - primitive: TestRunner
        default_size: panel
        trigger: "test|coverage|verify"
        weight: 0.7
      - primitive: Preview
        default_size: split
        trigger: "web|api|preview|run"
        weight: 0.6
      - primitive: DiffView
        default_size: split
        trigger: "diff|compare|change"
        weight: 0.5
        
    contextual:
      - primitive: MemoryPane
        trigger: "decision|pattern|before|last time"
        weight: 0.6
      - primitive: Dependencies
        trigger: "import|package|install"
        weight: 0.4

  # Existing heuristics, validators, etc.
  heuristics: [...]
```

```yaml
# lenses/planner.lens
lens:
  metadata:
    name: "planner"
    domain: "planning"
    
  affordances:
    primary:
      - primitive: Kanban
        default_size: full
        weight: 1.0
      - primitive: GoalTree
        default_size: sidebar
        weight: 0.9
        
    secondary:
      - primitive: Timeline
        default_size: full
        trigger: "roadmap|schedule|deadline"
        weight: 0.8
      - primitive: Metrics
        default_size: widget
        trigger: "progress|velocity|status"
        weight: 0.6
      - primitive: TaskList
        default_size: panel
        trigger: "today|next|priority"
        weight: 0.7
        
    contextual:
      - primitive: CodeEditor
        trigger: "implement|code|build"
        mode_hint: "coder"
        weight: 0.5
      - primitive: MemoryPane
        trigger: "decided|failed|learned"
        weight: 0.6
```

### Layout Rendering

The `SurfaceRenderer` receives a `WorkspaceSpec` from RFC-075 and renders it:

```python
# src/sunwell/surface/renderer.py

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SurfacePrimitive:
    """A UI primitive that can be composed into a surface."""
    id: str
    category: str  # "code", "planning", "writing", "data", "universal"
    size: str  # "full", "split", "panel", "sidebar", "widget", "floating"
    props: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SurfaceLayout:
    """A composed arrangement of primitives."""
    primary: SurfacePrimitive
    secondary: tuple[SurfacePrimitive, ...] = ()
    contextual: tuple[SurfacePrimitive, ...] = ()
    arrangement: str = "standard"  # "standard", "focused", "split", "dashboard"


@dataclass(frozen=True, slots=True)
class WorkspaceSpec:
    """Specification received from RFC-075 (Generative Interface).
    
    This is the contract between intent analysis and rendering.
    RFC-075 decides WHAT to show; this RFC decides HOW to show it.
    """
    
    primary: str
    """Primary primitive ID: "CodeEditor", "ProseEditor", "Kanban", etc."""
    
    secondary: tuple[str, ...] = ()
    """Secondary primitive IDs: ("FileTree", "Terminal")"""
    
    contextual: tuple[str, ...] = ()
    """Contextual widget IDs: ("WordCount", "MemoryPane")"""
    
    arrangement: str = "standard"
    """Layout arrangement: "standard", "focused", "split", "dashboard"."""
    
    seed_content: dict[str, Any] | None = None
    """Pre-populated content: {"outline": ["Chapter 1", "Chapter 2"]}"""
    
    primary_props: dict[str, Any] | None = None
    """Props for primary primitive: {"file": "/path/to/file.py"}"""


@dataclass
class SurfaceRenderer:
    """Renders workspace layouts from specs.
    
    Receives WorkspaceSpec from RFC-075 and produces a rendered SurfaceLayout.
    This is a deterministic operation — same spec always produces same layout.
    """
    
    registry: "PrimitiveRegistry"  # Registered primitives and their definitions
    
    def render(self, spec: WorkspaceSpec) -> SurfaceLayout:
        """Render a WorkspaceSpec into a SurfaceLayout.
        
        Args:
            spec: Workspace specification from RFC-075
            
        Returns:
            Rendered layout ready for Svelte
            
        Raises:
            ValueError: If spec contains unknown primitive IDs
        """
        
        # 1. Validate all primitive IDs exist in registry
        self._validate_spec(spec)
        
        # 2. Build primary primitive with appropriate size
        primary = self._build_primitive(
            primitive_id=spec.primary,
            size=self._primary_size_for_arrangement(spec.arrangement),
            props=spec.primary_props or {},
        )
        
        # 3. Build secondary primitives
        secondary = tuple(
            self._build_primitive(
                primitive_id=pid,
                size=self._secondary_size(pid, spec.arrangement),
                props={},
            )
            for pid in spec.secondary[:3]  # Max 3 secondary
        )
        
        # 4. Build contextual primitives
        contextual = tuple(
            self._build_primitive(
                primitive_id=pid,
                size="widget",
                props={},
            )
            for pid in spec.contextual[:2]  # Max 2 contextual
        )
        
        # 5. Apply seed content if provided
        if spec.seed_content:
            primary = self._apply_seed_content(primary, spec.seed_content)
        
        return SurfaceLayout(
            primary=primary,
            secondary=secondary,
            contextual=contextual,
            arrangement=spec.arrangement,
        )
    
    def _validate_spec(self, spec: WorkspaceSpec) -> None:
        """Validate all primitive IDs exist."""
        all_ids = [spec.primary] + list(spec.secondary) + list(spec.contextual)
        
        for pid in all_ids:
            if pid not in self.registry:
                raise ValueError(f"Unknown primitive: {pid}")
    
    def _build_primitive(
        self,
        primitive_id: str,
        size: str,
        props: dict[str, Any],
    ) -> SurfacePrimitive:
        """Build a primitive from registry definition."""
        defn = self.registry[primitive_id]
        
        return SurfacePrimitive(
            id=primitive_id,
            category=defn.category,
            size=size,
            props=props,
        )
    
    def _primary_size_for_arrangement(self, arrangement: str) -> str:
        """Determine primary primitive size based on arrangement."""
        return {
            "standard": "full",
            "focused": "full",
            "split": "split",
            "dashboard": "split",
        }.get(arrangement, "full")
    
    def _secondary_size(self, primitive_id: str, arrangement: str) -> str:
        """Determine secondary primitive size."""
        defn = self.registry[primitive_id]
        
        # Use default from registry, adjusted for arrangement
        if arrangement == "focused":
            return "floating"  # Minimize secondaries in focused mode
        
        return defn.default_size
    
    def _apply_seed_content(
        self,
        primitive: SurfacePrimitive,
        seed: dict[str, Any],
    ) -> SurfacePrimitive:
        """Apply seed content to primitive props."""
        return SurfacePrimitive(
            id=primitive.id,
            category=primitive.category,
            size=primitive.size,
            props={**primitive.props, "seed": seed},
        )


# Default layout when no spec provided or spec is invalid
DEFAULT_LAYOUT = SurfaceLayout(
    primary=SurfacePrimitive(
        id="CodeEditor",
        category="code",
        size="full",
    ),
    secondary=(
        SurfacePrimitive(id="FileTree", category="code", size="sidebar"),
    ),
    contextual=(),
    arrangement="standard",
)


def render_with_fallback(
    renderer: SurfaceRenderer,
    spec: WorkspaceSpec | None,
) -> SurfaceLayout:
    """Render a spec with fallback to default layout.
    
    Ensures the surface is NEVER empty, even on invalid specs.
    """
    if spec is None:
        return DEFAULT_LAYOUT
    
    try:
        return renderer.render(spec)
    except ValueError:
        return DEFAULT_LAYOUT
```

### Layout Persistence

Successful layouts are remembered and influence future compositions:

```python
# src/sunwell/surface/memory.py

@dataclass(frozen=True, slots=True)
class LayoutMemory:
    """Tracks successful layouts for future reference."""
    
    goal_pattern: str  # Normalized goal pattern
    layout: SurfaceLayout
    success_score: float  # 0-1 based on user interaction
    timestamp: str
    project_id: str


async def record_layout_success(
    layout: SurfaceLayout,
    goal: str,
    interaction_metrics: InteractionMetrics,
) -> None:
    """Record a successful layout for future reference."""
    
    # Calculate success based on:
    # - Time spent in layout without switching
    # - Goal completion rate
    # - User didn't manually override
    success_score = calculate_layout_success(interaction_metrics)
    
    if success_score > 0.7:  # Worth remembering
        await memory.store(LayoutMemory(
            goal_pattern=normalize_goal(goal),
            layout=layout,
            success_score=success_score,
            timestamp=now_iso(),
            project_id=project.id,
        ))
```

---

## Rust Implementation

### Primitive Registry

```rust
// studio/src-tauri/src/surface.rs

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Definition of a UI primitive.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrimitiveDef {
    pub id: String,
    pub category: String,
    pub component: String,  // Svelte component name
    pub can_be_primary: bool,
    pub can_be_secondary: bool,
    pub can_be_contextual: bool,
    pub default_size: String,
    pub size_options: Vec<String>,
}

/// A composed surface layout.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurfaceLayout {
    pub primary: SurfacePrimitive,
    pub secondary: Vec<SurfacePrimitive>,
    pub contextual: Vec<SurfacePrimitive>,
    pub arrangement: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurfacePrimitive {
    pub id: String,
    pub category: String,
    pub size: String,
    pub props: HashMap<String, serde_json::Value>,
}

/// Get the primitive registry.
#[tauri::command]
pub fn get_primitive_registry() -> Vec<PrimitiveDef> {
    vec![
        // Code primitives
        PrimitiveDef {
            id: "CodeEditor".into(),
            category: "code".into(),
            component: "CodeEditor".into(),
            can_be_primary: true,
            can_be_secondary: true,
            can_be_contextual: false,
            default_size: "full".into(),
            size_options: vec!["full".into(), "split".into(), "panel".into()],
        },
        PrimitiveDef {
            id: "FileTree".into(),
            category: "code".into(),
            component: "FileTree".into(),
            can_be_primary: false,
            can_be_secondary: true,
            can_be_contextual: false,
            default_size: "sidebar".into(),
            size_options: vec!["sidebar".into(), "floating".into()],
        },
        PrimitiveDef {
            id: "Terminal".into(),
            category: "code".into(),
            component: "Terminal".into(),
            can_be_primary: false,
            can_be_secondary: true,
            can_be_contextual: false,
            default_size: "bottom".into(),
            size_options: vec!["bottom".into(), "split".into(), "floating".into()],
        },
        // Planning primitives
        PrimitiveDef {
            id: "Kanban".into(),
            category: "planning".into(),
            component: "KanbanBoard".into(),
            can_be_primary: true,
            can_be_secondary: true,
            can_be_contextual: false,
            default_size: "full".into(),
            size_options: vec!["full".into(), "compact".into()],
        },
        PrimitiveDef {
            id: "Timeline".into(),
            category: "planning".into(),
            component: "Timeline".into(),
            can_be_primary: true,
            can_be_secondary: true,
            can_be_contextual: false,
            default_size: "full".into(),
            size_options: vec!["full".into(), "strip".into()],
        },
        // Universal primitives
        PrimitiveDef {
            id: "MemoryPane".into(),
            category: "universal".into(),
            component: "MemoryPane".into(),
            can_be_primary: false,
            can_be_secondary: true,
            can_be_contextual: true,
            default_size: "sidebar".into(),
            size_options: vec!["sidebar".into(), "floating".into(), "widget".into()],
        },
        PrimitiveDef {
            id: "DAGView".into(),
            category: "universal".into(),
            component: "DAGView".into(),
            can_be_primary: true,
            can_be_secondary: true,
            can_be_contextual: false,
            default_size: "panel".into(),
            size_options: vec!["panel".into(), "full".into()],
        },
        // ... additional primitives
    ]
}

/// Compose a surface layout for the given goal.
#[tauri::command]
pub async fn compose_surface(
    goal: String,
    project_path: Option<String>,
) -> Result<SurfaceLayout, String> {
    // Call Python CLI for composition logic
    let mut args = vec!["surface", "compose", "--goal", &goal, "--json"];
    
    if let Some(ref path) = project_path {
        args.push("--project");
        args.push(path);
    }
    
    let output = std::process::Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to compose surface: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse surface layout: {}", e))
}

/// Save a layout as successful for future reference.
#[tauri::command]
pub async fn record_layout_success(
    layout: SurfaceLayout,
    goal: String,
    duration_seconds: u64,
    completed: bool,
) -> Result<(), String> {
    let layout_json = serde_json::to_string(&layout)
        .map_err(|e| format!("Failed to serialize layout: {}", e))?;
    
    let output = std::process::Command::new("sunwell")
        .args([
            "surface", "record",
            "--goal", &goal,
            "--layout", &layout_json,
            "--duration", &duration_seconds.to_string(),
            "--completed", &completed.to_string(),
        ])
        .output()
        .map_err(|e| format!("Failed to record layout: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    Ok(())
}
```

### main.rs Registration

Commands must be registered in the Tauri invoke handler:

```rust
// studio/src-tauri/src/main.rs

mod surface;  // Add module declaration

// In invoke_handler:
.invoke_handler(tauri::generate_handler![
    // ... existing commands ...
    
    // Surface (RFC-072)
    surface::get_primitive_registry,
    surface::compose_surface,
    surface::record_layout_success,
])
```

---

## Python CLI Implementation

### Surface Subcommand

The Rust commands call the Python CLI. This module must be created:

```python
# src/sunwell/cli/surface.py
"""Surface composition CLI commands (RFC-072)."""

import asyncio
import json
from pathlib import Path

import click


@click.group()
def surface() -> None:
    """Surface composition commands (RFC-072)."""
    pass


@surface.command("compose")
@click.option("--goal", required=True, help="Goal to compose surface for")
@click.option("--project", default=None, help="Project path")
@click.option("--json", "json_output", is_flag=True, default=True, help="Output as JSON")
def compose(goal: str, project: str | None, json_output: bool) -> None:
    """Compose a surface layout for a goal.
    
    Called by Tauri's compose_surface command.
    """
    asyncio.run(_compose(goal, project, json_output))


async def _compose(goal: str, project_path: str | None, json_output: bool) -> None:
    """Async implementation of surface composition."""
    from sunwell.adaptive.lens_resolver import resolve_lens_for_goal
    from sunwell.memory.store import MemoryStore
    from sunwell.surface.composer import SurfaceComposer
    from sunwell.surface.fallback import compose_with_fallback
    from sunwell.workspace.indexer import CodebaseIndexer
    
    # Build composer with dependencies
    path = Path(project_path) if project_path else Path.cwd()
    memory = MemoryStore.load(path / ".sunwell" / "memory")
    indexer = CodebaseIndexer()
    
    composer = SurfaceComposer(
        lens_resolver=resolve_lens_for_goal,
        memory=memory,
        indexer=indexer,
    )
    
    # Compose with fallback
    layout = await compose_with_fallback(
        composer=composer,
        goal=goal,
        project_path=path,
        last_successful=None,  # Could load from state
    )
    
    # Output JSON for Tauri
    output = {
        "primary": {
            "id": layout.primary.id,
            "category": layout.primary.category,
            "size": layout.primary.size,
            "props": layout.primary.props,
        },
        "secondary": [
            {"id": p.id, "category": p.category, "size": p.size, "props": p.props}
            for p in layout.secondary
        ],
        "contextual": [
            {"id": p.id, "category": p.category, "size": p.size, "props": p.props}
            for p in layout.contextual
        ],
        "arrangement": layout.arrangement,
    }
    
    click.echo(json.dumps(output))


@surface.command("record")
@click.option("--goal", required=True, help="Goal that was active")
@click.option("--layout", required=True, help="Layout JSON")
@click.option("--duration", type=int, required=True, help="Duration in seconds")
@click.option("--completed", type=bool, required=True, help="Whether goal was completed")
def record(goal: str, layout: str, duration: int, completed: bool) -> None:
    """Record a successful layout for future reference.
    
    Called by Tauri's record_layout_success command.
    """
    asyncio.run(_record(goal, layout, duration, completed))


async def _record(goal: str, layout_json: str, duration: int, completed: bool) -> None:
    """Async implementation of layout recording."""
    import json
    from sunwell.memory.store import MemoryStore
    from sunwell.memory.types import Learning, LearningCategory
    
    layout_data = json.loads(layout_json)
    
    # Calculate success score
    # - Longer duration = more successful (up to a point)
    # - Completion = major boost
    base_score = min(duration / 300, 0.5)  # Max 0.5 from duration (5 min cap)
    completion_bonus = 0.4 if completed else 0.0
    success_score = base_score + completion_bonus
    
    if success_score < 0.5:
        return  # Not worth recording
    
    # Store as learning with layout metadata
    memory = MemoryStore.load(Path.cwd() / ".sunwell" / "memory")
    
    learning = Learning.create(
        fact=f"Layout for '{goal}' worked well",
        category=LearningCategory.PATTERN,
        confidence=success_score,
        metadata={
            "type": "layout_success",
            "primitives": [layout_data["primary"]["id"]] + 
                         [p["id"] for p in layout_data.get("secondary", [])] +
                         [p["id"] for p in layout_data.get("contextual", [])],
            "arrangement": layout_data.get("arrangement"),
            "duration_seconds": duration,
            "completed": completed,
        },
    )
    
    memory.add(learning)
    memory.save()
```

### CLI Registration

Register the surface command in main CLI:

```python
# src/sunwell/cli/main.py

from sunwell.cli.surface import surface

# In CLI setup:
cli.add_command(surface)
```

---

## Svelte Implementation

### Surface Store

```typescript
// studio/src/stores/surface.svelte.ts

/**
 * Surface Store — Generative surface composition (RFC-072)
 * 
 * Manages dynamic surface layouts that adapt to goals and context.
 */

import { invoke } from '@tauri-apps/api/core';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface PrimitiveDef {
  id: string;
  category: 'code' | 'planning' | 'writing' | 'data' | 'universal';
  component: string;
  can_be_primary: boolean;
  can_be_secondary: boolean;
  can_be_contextual: boolean;
  default_size: string;
  size_options: string[];
}

export interface SurfacePrimitive {
  id: string;
  category: string;
  size: string;
  props: Record<string, unknown>;
}

export interface SurfaceLayout {
  primary: SurfacePrimitive;
  secondary: SurfacePrimitive[];
  contextual: SurfacePrimitive[];
  arrangement: 'standard' | 'focused' | 'split' | 'dashboard';
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface SurfaceState {
  /** Current layout */
  layout: SurfaceLayout | null;
  
  /** Available primitives */
  registry: PrimitiveDef[];
  
  /** Current goal that generated this layout */
  currentGoal: string | null;
  
  /** Layout start time (for success tracking) */
  layoutStartTime: number | null;
  
  /** Is layout being composed */
  isComposing: boolean;
  
  /** Error state */
  error: string | null;
  
  /** Previous layouts for undo */
  history: SurfaceLayout[];
}

function createInitialState(): SurfaceState {
  return {
    layout: null,
    registry: [],
    currentGoal: null,
    layoutStartTime: null,
    isComposing: false,
    error: null,
    history: [],
  };
}

export let surface = $state<SurfaceState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

/** Get the primary primitive definition */
export const primaryDef = $derived(() => {
  if (!surface.layout) return null;
  return surface.registry.find(p => p.id === surface.layout!.primary.id);
});

/** Get categories present in current layout */
export const activeCategories = $derived(() => {
  if (!surface.layout) return new Set<string>();
  const cats = new Set([surface.layout.primary.category]);
  surface.layout.secondary.forEach(p => cats.add(p.category));
  surface.layout.contextual.forEach(p => cats.add(p.category));
  return cats;
});

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load the primitive registry.
 */
export async function loadRegistry(): Promise<void> {
  try {
    const registry = await invoke<PrimitiveDef[]>('get_primitive_registry');
    surface.registry = registry;
  } catch (e) {
    console.error('Failed to load primitive registry:', e);
  }
}

/**
 * Compose a surface layout for the given goal.
 */
export async function composeSurface(
  goal: string,
  projectPath?: string,
): Promise<SurfaceLayout | null> {
  // Record success of previous layout before switching
  if (surface.layout && surface.currentGoal && surface.layoutStartTime) {
    const duration = Math.floor((Date.now() - surface.layoutStartTime) / 1000);
    await recordSuccess(surface.layout, surface.currentGoal, duration, false);
  }
  
  surface.isComposing = true;
  surface.error = null;
  
  try {
    const layout = await invoke<SurfaceLayout>('compose_surface', {
      goal,
      projectPath: projectPath ?? null,
    });
    
    // Save previous layout to history
    if (surface.layout) {
      surface.history = [surface.layout, ...surface.history.slice(0, 4)];
    }
    
    surface.layout = layout;
    surface.currentGoal = goal;
    surface.layoutStartTime = Date.now();
    
    return layout;
  } catch (e) {
    surface.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to compose surface:', e);
    return null;
  } finally {
    surface.isComposing = false;
  }
}

/**
 * Record layout success metrics.
 */
async function recordSuccess(
  layout: SurfaceLayout,
  goal: string,
  durationSeconds: number,
  completed: boolean,
): Promise<void> {
  try {
    await invoke('record_layout_success', {
      layout,
      goal,
      durationSeconds,
      completed,
    });
  } catch (e) {
    console.error('Failed to record layout success:', e);
  }
}

/**
 * Mark current goal as completed (records success with higher weight).
 */
export async function markGoalCompleted(): Promise<void> {
  if (surface.layout && surface.currentGoal && surface.layoutStartTime) {
    const duration = Math.floor((Date.now() - surface.layoutStartTime) / 1000);
    await recordSuccess(surface.layout, surface.currentGoal, duration, true);
  }
}

/**
 * Manually add/remove a primitive from the current layout.
 */
export function addPrimitive(primitive: SurfacePrimitive, slot: 'secondary' | 'contextual'): void {
  if (!surface.layout) return;
  
  if (slot === 'secondary' && surface.layout.secondary.length < 3) {
    surface.layout = {
      ...surface.layout,
      secondary: [...surface.layout.secondary, primitive],
    };
  } else if (slot === 'contextual' && surface.layout.contextual.length < 2) {
    surface.layout = {
      ...surface.layout,
      contextual: [...surface.layout.contextual, primitive],
    };
  }
}

export function removePrimitive(primitiveId: string): void {
  if (!surface.layout) return;
  
  surface.layout = {
    ...surface.layout,
    secondary: surface.layout.secondary.filter(p => p.id !== primitiveId),
    contextual: surface.layout.contextual.filter(p => p.id !== primitiveId),
  };
}

/**
 * Undo to previous layout.
 */
export function undoLayout(): void {
  if (surface.history.length === 0) return;
  
  const [previous, ...rest] = surface.history;
  surface.layout = previous;
  surface.history = rest;
}

/**
 * Reset surface state.
 */
export function resetSurface(): void {
  Object.assign(surface, createInitialState());
}
```

### Dynamic Surface Renderer

```svelte
<!-- studio/src/components/Surface.svelte -->
<!--
  Surface — Dynamic surface renderer (RFC-072)
  
  Renders the current surface layout with smooth transitions
  between compositions.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { 
    surface,
    loadRegistry,
    composeSurface,
  } from '../stores/surface.svelte';
  
  // Primitive components
  import CodeEditor from './primitives/CodeEditor.svelte';
  import FileTree from './primitives/FileTree.svelte';
  import Terminal from './primitives/Terminal.svelte';
  import TestRunner from './primitives/TestRunner.svelte';
  import Kanban from './primitives/Kanban.svelte';
  import Timeline from './primitives/Timeline.svelte';
  import ProseEditor from './primitives/ProseEditor.svelte';
  import MemoryPane from './primitives/MemoryPane.svelte';
  import DAGView from './primitives/DAGView.svelte';
  // ... other primitives
  
  // Component registry
  const components: Record<string, any> = {
    CodeEditor,
    FileTree,
    Terminal,
    TestRunner,
    KanbanBoard: Kanban,
    Timeline,
    ProseEditor,
    MemoryPane,
    DAGView,
    // ... map all primitives
  };
  
  interface Props {
    initialGoal?: string;
    projectPath?: string;
  }
  
  let { initialGoal, projectPath }: Props = $props();
  
  onMount(async () => {
    await loadRegistry();
    if (initialGoal) {
      await composeSurface(initialGoal, projectPath);
    }
  });
  
  function getComponent(id: string) {
    const def = surface.registry.find(p => p.id === id);
    return def ? components[def.component] : null;
  }
  
  // Arrangement-specific grid classes
  const arrangementClasses: Record<string, string> = {
    standard: 'grid-standard',
    focused: 'grid-focused',
    split: 'grid-split',
    dashboard: 'grid-dashboard',
  };
</script>

<div class="surface" class:composing={surface.isComposing}>
  {#if surface.isComposing}
    <div class="composing-overlay" transition:fade={{ duration: 150 }}>
      <div class="motes"></div>
      <span>Composing surface...</span>
    </div>
  {/if}
  
  {#if surface.layout}
    <div 
      class="surface-grid {arrangementClasses[surface.layout.arrangement]}"
      in:fade={{ duration: 200, delay: 100 }}
    >
      <!-- Primary primitive (always present) -->
      <div class="primary-slot" data-size={surface.layout.primary.size}>
        {#if getComponent(surface.layout.primary.id)}
          <svelte:component 
            this={getComponent(surface.layout.primary.id)}
            {...surface.layout.primary.props}
            size={surface.layout.primary.size}
          />
        {/if}
      </div>
      
      <!-- Secondary primitives (sidebars, panels) -->
      {#if surface.layout.secondary.length > 0}
        <div class="secondary-slots">
          {#each surface.layout.secondary as prim (prim.id)}
            <div 
              class="secondary-slot"
              data-size={prim.size}
              in:fly={{ x: prim.size === 'sidebar' ? -20 : 0, y: prim.size === 'bottom' ? 20 : 0, duration: 200 }}
            >
              {#if getComponent(prim.id)}
                <svelte:component 
                  this={getComponent(prim.id)}
                  {...prim.props}
                  size={prim.size}
                />
              {/if}
            </div>
          {/each}
        </div>
      {/if}
      
      <!-- Contextual primitives (widgets, floating) -->
      {#if surface.layout.contextual.length > 0}
        <div class="contextual-slots">
          {#each surface.layout.contextual as prim (prim.id)}
            <div 
              class="contextual-slot"
              data-size={prim.size}
              in:fly={{ y: -10, duration: 200 }}
            >
              {#if getComponent(prim.id)}
                <svelte:component 
                  this={getComponent(prim.id)}
                  {...prim.props}
                  size={prim.size}
                />
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <div class="empty-surface">
      <p>Enter a goal to begin</p>
    </div>
  {/if}
</div>

<style>
  .surface {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: var(--bg-primary);
  }
  
  .composing-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(13, 13, 13, 0.8);
    z-index: 100;
    color: var(--gold);
  }
  
  .surface-grid {
    display: grid;
    width: 100%;
    height: 100%;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
  }
  
  /* Standard: Primary fills, secondary in sidebar/bottom */
  .grid-standard {
    grid-template-columns: auto 1fr;
    grid-template-rows: 1fr auto;
    grid-template-areas:
      "secondary primary"
      "bottom bottom";
  }
  
  /* Focused: Primary only, minimal secondary */
  .grid-focused {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr;
    grid-template-areas: "primary";
  }
  
  /* Split: Primary and one secondary side-by-side */
  .grid-split {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr;
    grid-template-areas: "primary secondary";
  }
  
  /* Dashboard: Multiple panels in grid */
  .grid-dashboard {
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(2, 1fr);
    grid-template-areas:
      "primary secondary"
      "tertiary contextual";
  }
  
  .primary-slot {
    grid-area: primary;
    min-height: 0;
    overflow: hidden;
    border-radius: var(--radius-lg);
    background: var(--bg-secondary);
  }
  
  .secondary-slots {
    display: contents;
  }
  
  .secondary-slot[data-size="sidebar"] {
    grid-area: secondary;
    width: 280px;
    overflow-y: auto;
  }
  
  .secondary-slot[data-size="bottom"] {
    grid-area: bottom;
    height: 200px;
  }
  
  .secondary-slot[data-size="panel"] {
    grid-area: secondary;
    overflow: auto;
  }
  
  .contextual-slots {
    position: fixed;
    top: var(--spacing-lg);
    right: var(--spacing-lg);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    z-index: 50;
  }
  
  .contextual-slot {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    box-shadow: var(--glow-gold-subtle);
    overflow: hidden;
  }
  
  .contextual-slot[data-size="widget"] {
    width: 240px;
    max-height: 180px;
  }
  
  .contextual-slot[data-size="floating"] {
    width: 320px;
    max-height: 400px;
  }
  
  .empty-surface {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-secondary);
  }
  
  /* Rising motes animation for composing state */
  .motes {
    position: absolute;
    inset: 0;
    background-image: radial-gradient(
      circle at 50% 100%,
      var(--gold) 0%,
      transparent 60%
    );
    opacity: 0.1;
    animation: motes-rise 2s ease-in-out infinite;
  }
  
  @keyframes motes-rise {
    0%, 100% { transform: translateY(0); opacity: 0.1; }
    50% { transform: translateY(-20px); opacity: 0.2; }
  }
</style>
```

---

## Cross-Stack Touchpoints

Complete list of files that need creation or modification across all three domains.

### Summary Table

| Layer | File | Action | Purpose |
|-------|------|--------|---------|
| 🐍 Python | `src/sunwell/surface/__init__.py` | Create | Package init |
| 🐍 Python | `src/sunwell/surface/composer.py` | Create | Composition engine |
| 🐍 Python | `src/sunwell/surface/fallback.py` | Create | Fallback chain |
| 🐍 Python | `src/sunwell/surface/memory.py` | Create | Layout persistence |
| 🐍 Python | `src/sunwell/cli/surface.py` | Create | CLI commands |
| 🐍 Python | `src/sunwell/cli/main.py` | Modify | Register surface command |
| 🐍 Python | `src/sunwell/core/lens.py` | Modify | Add `Affordances` dataclass |
| 🐍 Python | `src/sunwell/schema/loader.py` | Modify | Parse affordances YAML |
| 🐍 Python | `src/sunwell/adaptive/event_schema.py` | Modify | Add surface events (optional) |
| 🦀 Rust | `studio/src-tauri/src/surface.rs` | Create | Types + commands |
| 🦀 Rust | `studio/src-tauri/src/main.rs` | Modify | Register commands + module |
| 🟠 TypeScript | `studio/src/lib/types.ts` | Modify | Add surface types |
| 🟠 Svelte | `studio/src/stores/surface.svelte.ts` | Create | State management |
| 🟠 Svelte | `studio/src/components/Surface.svelte` | Create | Dynamic renderer |
| 🟠 Svelte | `studio/src/components/primitives/*.svelte` | Create | 24 primitive components |

### TypeScript Types

Add to `studio/src/lib/types.ts` for type alignment with Rust:

```typescript
// studio/src/lib/types.ts

// ═══════════════════════════════════════════════════════════════
// SURFACE TYPES (RFC-072)
// ═══════════════════════════════════════════════════════════════

export type PrimitiveCategory = 'code' | 'planning' | 'writing' | 'data' | 'universal';
export type PrimitiveSize = 'full' | 'split' | 'panel' | 'sidebar' | 'widget' | 'floating' | 'bottom';
export type SurfaceArrangement = 'standard' | 'focused' | 'split' | 'dashboard';

export interface PrimitiveDef {
  id: string;
  category: PrimitiveCategory;
  component: string;
  can_be_primary: boolean;
  can_be_secondary: boolean;
  can_be_contextual: boolean;
  default_size: PrimitiveSize;
  size_options: PrimitiveSize[];
}

export interface SurfacePrimitive {
  id: string;
  category: string;
  size: PrimitiveSize;
  props: Record<string, unknown>;
}

export interface SurfaceLayout {
  primary: SurfacePrimitive;
  secondary: SurfacePrimitive[];
  contextual: SurfacePrimitive[];
  arrangement: SurfaceArrangement;
}

// Primitive event for bidirectional communication
export interface PrimitiveEvent {
  primitiveId: string;
  eventType: 'file_edit' | 'terminal_output' | 'test_result' | 'user_action';
  data: Record<string, unknown>;
}
```

### LensLoader Schema Update

The `affordances` field must be parsed from lens YAML:

```python
# src/sunwell/schema/loader.py — add to LensLoader class

from sunwell.core.lens import Affordances, PrimitiveAffordance

def _parse_affordances(self, data: dict[str, Any] | None) -> Affordances | None:
    """Parse affordances section from lens YAML.
    
    Handles the RFC-072 affordances schema:
    
    affordances:
      primary:
        - primitive: CodeEditor
          default_size: full
          weight: 1.0
      secondary:
        - primitive: TestRunner
          trigger: "test|coverage"
          weight: 0.7
    """
    if not data:
        return None
    
    def parse_list(items: list[dict] | None) -> tuple[PrimitiveAffordance, ...]:
        if not items:
            return ()
        return tuple(
            PrimitiveAffordance(
                primitive=item["primitive"],
                default_size=item.get("default_size", "panel"),
                weight=item.get("weight", 0.5),
                trigger=item.get("trigger"),
                mode_hint=item.get("mode_hint"),
            )
            for item in items
        )
    
    return Affordances(
        primary=parse_list(data.get("primary")),
        secondary=parse_list(data.get("secondary")),
        contextual=parse_list(data.get("contextual")),
    )


# In _parse_lens(), add:
affordances=self._parse_affordances(raw.get("affordances")),
```

### Primitive↔Python Communication (IPC)

Active primitives need to communicate state changes back to Python:

```rust
// studio/src-tauri/src/surface.rs — add primitive event handling

/// Event from a primitive to Python.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrimitiveEvent {
    pub primitive_id: String,
    pub event_type: String,  // "file_edit", "terminal_output", "test_result"
    pub data: HashMap<String, serde_json::Value>,
}

/// Emit an event from a primitive.
#[tauri::command]
pub async fn emit_primitive_event(event: PrimitiveEvent) -> Result<(), String> {
    // Route to appropriate handler based on event type
    match event.event_type.as_str() {
        "file_edit" => {
            // Could trigger agent file sync or validation
            log::debug!("File edit from {}: {:?}", event.primitive_id, event.data);
        }
        "terminal_output" => {
            // Could feed terminal output to agent context
            log::debug!("Terminal output from {}", event.primitive_id);
        }
        "test_result" => {
            // Could update memory with test outcomes
            log::debug!("Test result from {}", event.primitive_id);
        }
        _ => {
            log::warn!("Unknown primitive event type: {}", event.event_type);
        }
    }
    Ok(())
}
```

```typescript
// studio/src/stores/surface.svelte.ts — add event emission

/**
 * Emit an event from a primitive component.
 * Called by primitives when they need to communicate state changes.
 */
export async function emitPrimitiveEvent(
  primitiveId: string,
  eventType: 'file_edit' | 'terminal_output' | 'test_result' | 'user_action',
  data: Record<string, unknown>,
): Promise<void> {
  try {
    await invoke('emit_primitive_event', {
      primitiveId,
      eventType,
      data,
    });
  } catch (e) {
    console.error('Failed to emit primitive event:', e);
  }
}
```

### Event Schema (Optional)

For streaming composition feedback, add to event schema:

```python
# src/sunwell/adaptive/event_schema.py — optional addition

class SurfaceComposingData(TypedDict, total=False):
    """Data for surface_composing event (optional progressive feedback)."""
    goal: str
    stage: str  # "parsing", "resolving_lens", "scoring", "selecting"
    progress: int  # 0-100


class SurfaceComposedData(TypedDict, total=False):
    """Data for surface_composed event."""
    goal: str
    arrangement: str
    primary_primitive: str
    secondary_count: int
    contextual_count: int
    composition_ms: int
```

### Primitive Component Interface

All primitive components follow this interface:

```typescript
// studio/src/components/primitives/types.ts

export interface PrimitiveProps {
  /** Primitive size mode */
  size: PrimitiveSize;
  
  /** Callback to emit events back to Python */
  onEvent?: (type: string, data: Record<string, unknown>) => void;
  
  /** Additional props from composition */
  [key: string]: unknown;
}
```

```svelte
<!-- studio/src/components/primitives/CodeEditor.svelte -->
<script lang="ts">
  import type { PrimitiveProps, PrimitiveSize } from './types';
  import { emitPrimitiveEvent } from '../../stores/surface.svelte';
  
  interface Props extends PrimitiveProps {
    file?: string;
    language?: string;
  }
  
  let { size, file, language }: Props = $props();
  
  function handleFileChange(changes: unknown) {
    emitPrimitiveEvent('CodeEditor', 'file_edit', { file, changes });
  }
</script>

<div class="code-editor" data-size={size}>
  <!-- Editor implementation -->
</div>
```

---

## Implementation Plan

### Phase 1: Foundation (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `src/sunwell/surface/` package | High | Small |
| Create `SurfaceComposer` class | High | Medium |
| Create `fallback.py` with default layouts | High | Small |
| Extend `Lens` dataclass with `Affordances` | High | Small |
| Update `LensLoader` to parse affordances | High | Small |
| Create `surface.py` CLI commands | High | Medium |
| Register surface CLI in `main.py` | High | Small |

### Phase 2: Rust Layer (1-2 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `studio/src-tauri/src/surface.rs` | High | Medium |
| Add types: `PrimitiveDef`, `SurfaceLayout`, `SurfacePrimitive` | High | Small |
| Implement `get_primitive_registry` command | High | Small |
| Implement `compose_surface` command (calls Python CLI) | High | Small |
| Implement `record_layout_success` command | Medium | Small |
| Register commands in `main.rs` | High | Small |

### Phase 3: TypeScript/Svelte (3-4 days)

| Task | Priority | Effort |
|------|----------|--------|
| Add surface types to `lib/types.ts` | High | Small |
| Create `surface.svelte.ts` store | High | Medium |
| Create `Surface.svelte` dynamic renderer | High | Large |
| Create primitive components directory structure | High | Small |
| Create core primitives: `CodeEditor`, `FileTree`, `Terminal` | High | Large |
| Create planning primitives: `Kanban`, `Timeline`, `GoalTree` | Medium | Large |
| Add arrangement-specific CSS grids | Medium | Medium |
| Add composition transition animations | Medium | Small |

### Phase 4: Composition Logic (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Implement `extract_triggers()` keyword matching | High | Small |
| Implement primitive scoring algorithm | High | Medium |
| Implement primitive selection with constraints | High | Medium |
| Implement `_analyze_file_types()` | Medium | Small |
| Implement `_get_default_scores()` for domain fallback | Medium | Small |
| Integrate with `MemoryStore` for layout history | Medium | Medium |

### Phase 5: Integration & Polish (1-2 days)

| Task | Priority | Effort |
|------|----------|--------|
| Wire goal input to `composeSurface` | High | Small |
| Add layout success tracking | Medium | Small |
| Implement primitive↔Python IPC (`emit_primitive_event`) | Medium | Medium |
| Add undo/history support | Low | Small |
| Add "why this layout?" tooltip (optional) | Low | Small |

---

## Testing Strategy

### Python Tests

```python
# tests/test_surface_composer.py

@pytest.mark.asyncio
async def test_compose_code_goal():
    """Code goal should produce code-centric layout."""
    composer = SurfaceComposer(...)
    layout = await composer.compose("Build a REST API", project)
    
    assert layout.primary.id == "CodeEditor"
    assert any(p.id == "FileTree" for p in layout.secondary)


@pytest.mark.asyncio
async def test_compose_planning_goal():
    """Planning goal should produce planning-centric layout."""
    composer = SurfaceComposer(...)
    layout = await composer.compose("Plan the next sprint", project)
    
    assert layout.primary.id in ["Kanban", "GoalTree"]


@pytest.mark.asyncio
async def test_cross_domain_goal():
    """Cross-domain goal should include multiple categories."""
    composer = SurfaceComposer(...)
    layout = await composer.compose(
        "Implement the features we planned last week",
        project,
    )
    
    categories = {layout.primary.category}
    categories.update(p.category for p in layout.secondary)
    
    assert len(categories) >= 2  # Code + planning/memory


@pytest.mark.asyncio
async def test_memory_influences_composition():
    """Past successful layouts should influence future compositions."""
    # Setup: record a successful layout
    await memory.store(LayoutMemory(
        goal_pattern="build.*api",
        layout=custom_layout_with_terminal,
        success_score=0.9,
        ...
    ))
    
    # Test: similar goal should favor that layout
    layout = await composer.compose("Build another API", project)
    
    assert any(p.id == "Terminal" for p in layout.secondary)
```

### Frontend Tests

```typescript
// studio/src/stores/surface.svelte.test.ts

describe('surface store', () => {
  beforeEach(() => {
    resetSurface();
  });
  
  it('should compose surface for code goal', async () => {
    await composeSurface('Build a REST API');
    
    expect(surface.layout).not.toBeNull();
    expect(surface.layout?.primary.category).toBe('code');
  });
  
  it('should track layout history', async () => {
    await composeSurface('Build API');
    await composeSurface('Plan features');
    
    expect(surface.history.length).toBe(1);
    expect(surface.history[0].primary.category).toBe('code');
  });
  
  it('should support undo', async () => {
    await composeSurface('Build API');
    const firstLayout = surface.layout;
    await composeSurface('Plan features');
    
    undoLayout();
    
    expect(surface.layout).toEqual(firstLayout);
  });
});
```

---

## Migration Strategy

### From Fixed Modes to Generative Surface

The generative surface doesn't break existing mode-based navigation — it enhances it:

```yaml
migration_path:
  phase_1_parallel:
    - Generative surface available via goal input
    - Traditional mode buttons still work (trigger surface composition with mode-specific goal)
    - Users can opt into "always generate" vs "suggest and confirm"
    
  phase_2_default:
    - Goal input becomes primary interface
    - Mode buttons become "quick presets" that compose a standard layout
    - Composition happens automatically on goal entry
    
  phase_3_full:
    - Mode buttons removed
    - Surface always generates based on context
    - Manual primitive add/remove for power users
```

### Lens Migration

Existing lenses work without `affordances` — they get default affordances based on their `domain`:

```python
def get_default_affordances(domain: str) -> Affordances:
    """Provide default affordances for lenses without explicit definitions."""
    defaults = {
        "software": Affordances(
            primary=[("CodeEditor", 1.0), ("FileTree", 0.9)],
            secondary=[("Terminal", 0.8), ("TestRunner", 0.7)],
        ),
        "documentation": Affordances(
            primary=[("ProseEditor", 1.0), ("Outline", 0.9)],
            secondary=[("Preview", 0.8), ("References", 0.7)],
        ),
        # ... other domains
    }
    return defaults.get(domain, defaults["software"])
```

---

## Performance Considerations

| Operation | Target Latency | Notes |
|-----------|----------------|-------|
| Goal parsing | <50ms | Regex + keyword extraction |
| Lens resolution | <100ms | Cached after first load |
| Memory query | <200ms | Limited to recent entries |
| Primitive scoring | <50ms | Simple arithmetic |
| Layout render | <100ms | Svelte reactive update |
| **Total compose** | **<500ms** | User perceives instant |

**Optimizations:**
- Cache lens affordances after load
- Pre-load primitive components
- Debounce rapid goal changes (300ms)
- Use `requestAnimationFrame` for layout transitions

---

## Security Considerations

1. **Goal injection** — Goals are parsed for keywords, not executed; no shell injection risk
2. **Primitive props** — Props come from composition logic, not user input
3. **Memory queries** — Scoped to current project; no cross-project leakage
4. **Layout persistence** — Stored locally; no sensitive data in layouts

---

## Fallback Behavior

Composition can fail (no lens, no memory, invalid goal). The surface must **never be empty**.

```python
# src/sunwell/surface/fallback.py

# Default layout when composition fails or returns nothing
DEFAULT_LAYOUT = SurfaceLayout(
    primary=SurfacePrimitive(
        id="CodeEditor",
        category="code", 
        size="full",
    ),
    secondary=(
        SurfacePrimitive(id="FileTree", category="code", size="sidebar"),
    ),
    contextual=(),
    arrangement="standard",
)


async def compose_with_fallback(
    composer: SurfaceComposer,
    goal: str,
    project_path: Path,
    last_successful: SurfaceLayout | None = None,
) -> SurfaceLayout:
    """Compose surface with guaranteed non-empty result.
    
    Fallback chain:
    1. Try composition → return if valid
    2. Try last successful layout → return if available
    3. Return domain-specific default
    4. Return universal DEFAULT_LAYOUT
    """
    try:
        layout = await composer.compose(goal, project_path)
        if layout and layout.primary:
            return layout
    except Exception:
        pass  # Fall through to fallback
    
    # Fallback 1: Last successful layout
    if last_successful:
        return last_successful
    
    # Fallback 2: Domain default (based on file types present)
    domain_default = _get_domain_default(project_path)
    if domain_default:
        return domain_default
    
    # Fallback 3: Universal default
    return DEFAULT_LAYOUT


def _get_domain_default(project_path: Path) -> SurfaceLayout | None:
    """Infer domain from project files and return appropriate default."""
    # Quick heuristics based on marker files
    markers = {
        "pyproject.toml": "software",
        "package.json": "software", 
        "docs/": "documentation",
        "mkdocs.yml": "documentation",
        ".kanban": "planning",
    }
    
    for marker, domain in markers.items():
        if (project_path / marker).exists():
            return DOMAIN_DEFAULTS.get(domain)
    
    return None


DOMAIN_DEFAULTS: dict[str, SurfaceLayout] = {
    "software": SurfaceLayout(
        primary=SurfacePrimitive(id="CodeEditor", category="code", size="full"),
        secondary=(SurfacePrimitive(id="FileTree", category="code", size="sidebar"),),
        arrangement="standard",
    ),
    "documentation": SurfaceLayout(
        primary=SurfacePrimitive(id="ProseEditor", category="writing", size="full"),
        secondary=(SurfacePrimitive(id="Outline", category="writing", size="sidebar"),),
        arrangement="standard",
    ),
    "planning": SurfaceLayout(
        primary=SurfacePrimitive(id="Kanban", category="planning", size="full"),
        secondary=(SurfacePrimitive(id="GoalTree", category="planning", size="sidebar"),),
        arrangement="standard",
    ),
}
```

---

## Open Questions

| Question | Current Decision | Rationale |
|----------|------------------|-----------|
| Should users be able to drag primitives? | **Deferred** | RFC-075 handles composition; manual override is future work |
| What if spec contains unknown primitive? | **Fallback to DEFAULT_LAYOUT** | Never show empty surface |
| Should primitives communicate with each other? | **Via events through store** | Loose coupling, testable |
| How to handle very small screens? | **Arrangement collapses to focused** | Mobile-friendly degradation |

---

## Future Extensions

1. **User overrides** — "Always show Terminal for this project"
2. **Team layouts** — Share layout presets across team
3. **Primitive plugins** — Third-party primitives via Fount
4. **Multi-monitor** — Different surfaces on different displays
5. **Primitive state sync** — Primitives share state (e.g., selected file)
6. **Layout presets** — Named layouts users can switch between manually

---

## References

- RFC-043 — Sunwell Studio (GUI framework)
- RFC-061 — Holy Light Design System (visual styling)
- **RFC-075 — Generative Interface (sends WorkspaceSpec to this system)**
- `src/sunwell/surface/renderer.py` — SurfaceRenderer implementation
- `src/sunwell/surface/primitives/` — Primitive component registry
- VISION-universal-creative-platform.md — The adaptive interface vision

---

## Appendix: Full Primitive Registry

| ID | Category | Can Primary | Can Secondary | Can Contextual | Default Size |
|----|----------|-------------|---------------|----------------|--------------|
| CodeEditor | code | ✅ | ✅ | ❌ | full |
| FileTree | code | ❌ | ✅ | ❌ | sidebar |
| Terminal | code | ❌ | ✅ | ❌ | bottom |
| TestRunner | code | ❌ | ✅ | ✅ | panel |
| DiffView | code | ✅ | ✅ | ❌ | split |
| Preview | code | ✅ | ✅ | ❌ | split |
| Dependencies | code | ❌ | ✅ | ❌ | sidebar |
| Kanban | planning | ✅ | ✅ | ❌ | full |
| Timeline | planning | ✅ | ✅ | ❌ | full |
| GoalTree | planning | ✅ | ✅ | ❌ | sidebar |
| TaskList | planning | ❌ | ✅ | ✅ | panel |
| Calendar | planning | ✅ | ✅ | ❌ | full |
| Metrics | planning | ❌ | ✅ | ✅ | widget |
| ProseEditor | writing | ✅ | ✅ | ❌ | full |
| Outline | writing | ❌ | ✅ | ❌ | sidebar |
| References | writing | ❌ | ✅ | ✅ | panel |
| WordCount | writing | ❌ | ❌ | ✅ | widget |
| DataTable | data | ✅ | ✅ | ❌ | full |
| Chart | data | ✅ | ✅ | ❌ | panel |
| QueryBuilder | data | ❌ | ✅ | ❌ | panel |
| Summary | data | ❌ | ❌ | ✅ | widget |
| MemoryPane | universal | ❌ | ✅ | ✅ | sidebar |
| Input | universal | ❌ | ❌ | ❌ | fixed |
| DAGView | universal | ✅ | ✅ | ❌ | panel |
| BriefingCard | universal | ❌ | ❌ | ✅ | widget |
