# RFC-064: Lens Management — Expertise Selection for Projects

**Status**: Draft  
**Created**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 88% 🟢  
**Depends on**: 
- RFC-042 (Adaptive Agent) — execution engine  
- RFC-043 (Sunwell Studio) — GUI framework  
- RFC-061 (Holy Light Design System) — visual styling

---

## Summary

Connect Sunwell's lens system to project execution and provide UI for browsing, selecting, and managing lenses. Currently, lenses are a powerful feature used only by CLI commands (`chat`, `apply`, `ask`) — the main agent flow and Studio UI have no lens integration.

**Key changes:**
- Wire lens discovery into agent execution (auto-selection based on goal)
- Add `--lens` flag to agent CLI for explicit lens override
- Pass lens selection through Tauri commands
- Frontend lens picker before project start
- Lens browser panel with preview
- Per-project lens memory

**Three-domain implementation:**
- 🐍 **Python**: Integrate `LensDiscovery` into `AdaptiveAgent`, add CLI flags
- 🦀 **Rust**: Add lens-related Tauri commands and state
- 🟠 **Svelte**: Lens picker modal, browser panel, and project lens display

---

## Motivation

### The Gap

Lenses are Sunwell's expertise containers — heuristics, communication style, validators, and skills that shape how the AI approaches a domain. They're sophisticated:

```yaml
# lenses/coder.lens
lens:
  metadata:
    name: "Python Coder"
    domain: "software"
  heuristics:
    - name: "Type Safety First"
      rule: "Use type hints throughout, prefer strict typing"
      always: ["Add type hints to all function signatures"]
      never: ["Use `Any` except at boundaries"]
```

**But they're disconnected from the main flow:**

| Pathway | Uses Lenses? |
|---------|--------------|
| `sunwell chat coder` | ✅ Yes |
| `sunwell apply coder.lens "prompt"` | ✅ Yes |
| `sunwell "Build a forum app"` | ❌ No |
| Studio: "Build a forum app" | ❌ No |

The primary use cases — quick goals and Studio — get no lens expertise.

### What's Already Built (But Unused)

**1. LensDiscovery** (`src/sunwell/naaru/expertise/discovery.py`)

```python
DOMAIN_LENS_MAP = {
    Domain.DOCUMENTATION: ["tech-writer.lens", "team-writer.lens"],
    Domain.CODE: ["coder.lens", "team-dev.lens"],
    Domain.REVIEW: ["code-reviewer.lens", "team-qa.lens"],
    # ...
}

discovery = LensDiscovery()
lenses = await discovery.discover("code")  # Returns [coder.lens, team-dev.lens]
```

**2. UnifiedRouter** (`src/sunwell/routing/unified.py`)

Already suggests lenses in routing decisions:
```json
{
  "intent": "code",
  "lens": "coder",
  "confidence": 0.85
}
```

**3. Complete Lens Model** (`src/sunwell/core/lens.py`)

```python
@dataclass(slots=True)
class Lens:
    metadata: LensMetadata
    heuristics: tuple[Heuristic, ...]
    communication: CommunicationStyle | None
    quality_policy: QualityPolicy
    # ...
    
    def to_context(self) -> str:
        """Convert lens to context injection format."""
```

### Why This Matters

1. **Quality consistency** — Lenses encode patterns that produce better output
2. **Domain expertise** — A tech-writer lens produces better docs than a generic prompt
3. **User control** — Power users want to choose/customize their lens
4. **Composability** — Lenses can extend and compose (inheritance model)
5. **Memory alignment** — Simulacrum learnings should be lens-aware

### Non-Goals

This RFC explicitly **does not** cover:

1. **Lens editing UI** — Creating or modifying lenses in Studio is deferred to a future RFC
2. **Lens marketplace/registry** — Fount integration for browsing/installing community lenses is out of scope
3. **Multi-lens composition at runtime** — Applying multiple lenses simultaneously requires design work not included here
4. **Dynamic lens switching mid-execution** — Changing lens during a run is complex and deferred
5. **Lens versioning/pinning** — Locking a project to a specific lens version is a future enhancement
6. **Lens effectiveness analytics** — Tracking which lenses produce best results is out of scope

---

## Design

### Alternative Approaches Considered

#### Option A: Auto-Lens Only (Rejected)

Only wire up automatic lens selection — no user choice, no explicit `--lens` flag.

**Pros:**
- Simpler implementation
- "Just works" UX

**Cons:**
- No user override when auto-detection is wrong
- Power users can't pre-select their preferred lens
- No project-level defaults

**Verdict**: Rejected because user control is essential for domain experts.

#### Option B: Lens Picker at Route-Time (Rejected)

Show lens picker when UnifiedRouter detects ambiguity (low confidence).

**Pros:**
- Only interrupts when needed
- Fewer clicks for confident routes

**Cons:**
- Unpredictable UX (sometimes asks, sometimes doesn't)
- Harder to test
- Users can't preview lens options before starting

**Verdict**: Rejected because predictable UX is better than "smart" UX.

#### Option C: Lens Selection Before Goal Entry (Selected)

User can optionally select lens before entering goal, with auto-detect as default.

**Pros:**
- Predictable UX
- User always in control
- Auto-detect is zero-friction default
- Lens preview available

**Cons:**
- Extra step for users who always want auto-detect (mitigated: auto-detect is default)

**Verdict**: Selected as the best balance of control and simplicity.

### Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LENS FLOW                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [User Goal]                                                            │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │ Auto-Detect │ OR  │ User Picks  │ OR  │ Project     │               │
│  │ (Router)    │     │ (UI Picker) │     │ Default     │               │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘               │
│         │                   │                   │                       │
│         └─────────┬─────────┴─────────┬─────────┘                       │
│                   ▼                                                     │
│          ┌───────────────┐                                              │
│          │ Lens Selected │                                              │
│          └───────┬───────┘                                              │
│                  │                                                      │
│         ┌────────┴────────┐                                             │
│         ▼                 ▼                                             │
│  ┌─────────────┐  ┌─────────────┐                                       │
│  │ Agent uses  │  │ UI shows    │                                       │
│  │ lens.to_    │  │ active lens │                                       │
│  │ context()   │  │ badge       │                                       │
│  └─────────────┘  └─────────────┘                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Python: Lens Integration into Agent

#### 1. Add `--lens` Flag to Agent CLI

```python
# src/sunwell/cli/agent/run.py

@click.command()
@click.argument("goal")
@click.option(
    "--lens", "-l",
    default=None,
    help="Lens to apply (name or path, e.g. 'coder' or './custom.lens')",
)
@click.option(
    "--auto-lens/--no-auto-lens",
    default=True,
    help="Auto-select lens based on goal (default: enabled)",
)
def run(goal: str, lens: str | None, auto_lens: bool, ...):
    ...
```

#### 2. Resolve Lens in Agent Flow

```python
# src/sunwell/adaptive/lens_resolver.py

from dataclasses import dataclass
from pathlib import Path

from sunwell.core.lens import Lens
from sunwell.naaru.expertise.classifier import classify_domain
from sunwell.naaru.expertise.discovery import LensDiscovery
from sunwell.routing.unified import UnifiedRouter


@dataclass(frozen=True, slots=True)
class LensResolution:
    """Result of lens resolution."""
    lens: Lens | None
    source: str  # "explicit", "auto", "project_default", "none"
    confidence: float
    reason: str


async def resolve_lens_for_goal(
    goal: str,
    explicit_lens: str | None = None,
    project_path: Path | None = None,
    auto_select: bool = True,
    router: UnifiedRouter | None = None,
) -> LensResolution:
    """Resolve which lens to use for a goal.
    
    Priority:
    1. Explicit lens (--lens flag or UI selection)
    2. Project default (from .sunwell/config.yaml)
    3. Auto-select based on goal analysis
    4. None (no lens applied)
    
    Args:
        goal: The user's goal/task
        explicit_lens: User-specified lens name or path
        project_path: Project directory for finding project default
        auto_select: Whether to auto-select if no explicit lens
        router: Optional UnifiedRouter for intelligent selection
        
    Returns:
        LensResolution with lens and metadata
    """
    discovery = LensDiscovery()
    
    # 1. Explicit lens
    if explicit_lens:
        lens = await _load_lens(explicit_lens, discovery)
        if lens:
            return LensResolution(
                lens=lens,
                source="explicit",
                confidence=1.0,
                reason=f"User specified: {explicit_lens}",
            )
        return LensResolution(
            lens=None,
            source="explicit",
            confidence=0.0,
            reason=f"Could not load lens: {explicit_lens}",
        )
    
    # 2. Project default
    if project_path:
        config_path = project_path / ".sunwell" / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            if default_lens := config.get("default_lens"):
                lens = await _load_lens(default_lens, discovery)
                if lens:
                    return LensResolution(
                        lens=lens,
                        source="project_default",
                        confidence=0.95,
                        reason=f"Project default: {default_lens}",
                    )
    
    # 3. Auto-select
    if auto_select:
        # Use router if available for intelligent selection
        if router:
            decision = await router.route(goal)
            if decision.lens:
                lens = await _load_lens(decision.lens, discovery)
                if lens:
                    return LensResolution(
                        lens=lens,
                        source="auto",
                        confidence=decision.confidence,
                        reason=f"Router selected: {decision.lens} ({decision.reasoning})",
                    )
        
        # Fallback to domain classification
        domain = await classify_domain(goal)
        lenses = await discovery.discover(domain, max_lenses=1)
        if lenses:
            return LensResolution(
                lens=lenses[0],
                source="auto",
                confidence=0.8,
                reason=f"Domain {domain.value}: {lenses[0].metadata.name}",
            )
    
    # 4. No lens
    return LensResolution(
        lens=None,
        source="none",
        confidence=1.0,
        reason="No lens applied",
    )


async def _load_lens(name_or_path: str, discovery: LensDiscovery) -> Lens | None:
    """Load a lens by name or path.
    
    Error handling:
    - Returns None for missing files (graceful degradation)
    - Returns None for parse errors (logged, not raised)
    - Path traversal is prevented by search_path containment check
    """
    import logging
    
    from sunwell.core.types import LensReference
    from sunwell.fount.client import FountClient
    from sunwell.fount.resolver import LensResolver
    from sunwell.schema.loader import LensLoader
    
    log = logging.getLogger(__name__)
    
    # Check if it's a path
    if name_or_path.endswith(".lens") or "/" in name_or_path:
        path = Path(name_or_path)
        if not path.exists():
            # Try standard locations
            for search_path in discovery.search_paths:
                candidate = search_path / name_or_path
                if candidate.exists():
                    path = candidate
                    break
        
        if path.exists():
            # Security: Ensure path is within allowed search paths
            resolved = path.resolve()
            in_search_path = any(
                str(resolved).startswith(str(sp.resolve()))
                for sp in discovery.search_paths
            )
            if not in_search_path:
                log.warning(f"Lens path outside search paths: {path}")
                return None
            
            source = str(path)
            if not source.startswith("/"):
                source = f"./{source}"
            
            try:
                fount = FountClient()
                loader = LensLoader(fount_client=fount)
                resolver = LensResolver(loader=loader)
                ref = LensReference(source=source)
                return await resolver.resolve(ref)
            except Exception as e:
                log.warning(f"Failed to load lens {name_or_path}: {e}")
                return None
    
    # Try by name
    for search_path in discovery.search_paths:
        path = search_path / f"{name_or_path}.lens"
        if path.exists():
            return await _load_lens(str(path), discovery)
    
    log.debug(f"Lens not found: {name_or_path}")
    return None
```

#### 3. Apply Lens Context in Agent

```python
# src/sunwell/adaptive/agent.py (modified)

@dataclass
class AdaptiveAgent:
    model: ModelProtocol
    tool_executor: Any = None
    cwd: Path | None = None
    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    
    # NEW: Lens configuration
    lens: Lens | None = None
    """Active lens for expertise injection."""
    
    auto_lens: bool = True
    """Whether to auto-select lens if none provided."""
    
    async def run(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute goal with optional lens expertise."""
        start_time = time()
        
        # Resolve lens if not already set
        if self.lens is None and self.auto_lens:
            from sunwell.adaptive.lens_resolver import resolve_lens_for_goal
            
            resolution = await resolve_lens_for_goal(
                goal=goal,
                project_path=self.cwd,
                auto_select=True,
            )
            
            if resolution.lens:
                self.lens = resolution.lens
                yield AgentEvent(
                    EventType.LENS_SELECTED,
                    {
                        "name": resolution.lens.metadata.name,
                        "source": resolution.source,
                        "confidence": resolution.confidence,
                        "reason": resolution.reason,
                    },
                )
        
        # Build system context with lens
        system_context = self._build_system_context(goal, context)
        
        # ... rest of execution
    
    def _build_system_context(
        self,
        goal: str,
        context: dict[str, Any] | None,
    ) -> str:
        """Build system prompt with lens expertise."""
        parts = []
        
        # Lens expertise
        if self.lens:
            parts.append(self.lens.to_context())
            parts.append("")  # Blank line separator
        
        # Goal and context
        parts.append(f"GOAL: {goal}")
        if context:
            parts.append(f"CONTEXT: {context}")
        
        return "\n".join(parts)
```

#### 4. Add New Event Type

```python
# src/sunwell/adaptive/events.py (add to EventType enum)

class EventType(Enum):
    # ... existing events ...
    
    # Lens events (RFC-064)
    LENS_SELECTED = "lens_selected"
    LENS_CHANGED = "lens_changed"
```

#### 5. List Available Lenses Command

```python
# src/sunwell/cli/lens.py (new file)

"""CLI commands for lens management (RFC-064)."""

import asyncio
import json

import click
from rich.console import Console
from rich.table import Table

from sunwell.naaru.expertise.discovery import LensDiscovery

console = Console()


@click.group()
def lens() -> None:
    """Lens management commands."""
    pass


@lens.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list(json_output: bool) -> None:
    """List all available lenses."""
    asyncio.run(_list_lenses(json_output))


async def _list_lenses(json_output: bool) -> None:
    """List available lenses."""
    discovery = LensDiscovery()
    
    lenses_data = []
    
    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue
        
        for lens_path in search_path.glob("*.lens"):
            try:
                lens = await discovery._load_lens(lens_path)
                if lens:
                    lenses_data.append({
                        "name": lens.metadata.name,
                        "domain": lens.metadata.domain,
                        "version": str(lens.metadata.version),
                        "description": lens.metadata.description,
                        "path": str(lens_path),
                        "heuristics_count": len(lens.heuristics),
                        "skills_count": len(lens.skills),
                    })
            except Exception:
                continue
    
    if json_output:
        print(json.dumps(lenses_data, indent=2))
        return
    
    table = Table(title="Available Lenses")
    table.add_column("Name", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Description")
    table.add_column("Heuristics", justify="right")
    table.add_column("Path", style="dim")
    
    for lens in lenses_data:
        table.add_row(
            lens["name"],
            lens["domain"] or "-",
            (lens["description"] or "-")[:40],
            str(lens["heuristics_count"]),
            lens["path"],
        )
    
    console.print(table)


@lens.command()
@click.argument("lens_name")
def show(lens_name: str) -> None:
    """Show details of a specific lens."""
    asyncio.run(_show_lens(lens_name))


async def _show_lens(lens_name: str) -> None:
    """Show lens details."""
    from sunwell.adaptive.lens_resolver import _load_lens
    
    discovery = LensDiscovery()
    lens = await _load_lens(lens_name, discovery)
    
    if not lens:
        console.print(f"[red]Lens not found: {lens_name}[/red]")
        return
    
    console.print(f"[bold]Lens: {lens.metadata.name}[/bold]")
    console.print(f"Version: {lens.metadata.version}")
    console.print(f"Domain: {lens.metadata.domain or 'general'}")
    if lens.metadata.description:
        console.print(f"\n{lens.metadata.description}")
    
    if lens.heuristics:
        console.print(f"\n[bold]Heuristics ({len(lens.heuristics)}):[/bold]")
        for h in lens.heuristics[:5]:  # Show first 5
            console.print(f"  • {h.name}: {h.rule[:60]}...")
        if len(lens.heuristics) > 5:
            console.print(f"  ... and {len(lens.heuristics) - 5} more")
    
    if lens.communication:
        console.print(f"\n[bold]Communication Style:[/bold] {lens.communication.style}")
    
    if lens.skills:
        console.print(f"\n[bold]Skills ({len(lens.skills)}):[/bold]")
        for s in lens.skills:
            console.print(f"  • {s.name}")
```

---

### Rust: Tauri Commands and State

#### 1. Lens Types

```rust
// studio/src-tauri/src/lens.rs (new file)

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;

/// Lens summary for UI display
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensSummary {
    pub name: String,
    pub domain: Option<String>,
    pub version: String,
    pub description: Option<String>,
    pub path: String,
    pub heuristics_count: usize,
    pub skills_count: usize,
}

/// Lens detail for preview
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensDetail {
    pub name: String,
    pub domain: Option<String>,
    pub version: String,
    pub description: Option<String>,
    pub author: Option<String>,
    pub heuristics: Vec<HeuristicSummary>,
    pub communication_style: Option<String>,
    pub skills: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeuristicSummary {
    pub name: String,
    pub rule: String,
    pub priority: f32,
}

/// Project lens configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ProjectLensConfig {
    pub default_lens: Option<String>,
    pub auto_select: bool,
}

impl ProjectLensConfig {
    pub fn load(project_path: &std::path::Path) -> Self {
        let config_path = project_path.join(".sunwell/config.yaml");
        if config_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&config_path) {
                if let Ok(config) = serde_yaml::from_str::<serde_yaml::Value>(&content) {
                    return Self {
                        default_lens: config.get("default_lens")
                            .and_then(|v| v.as_str())
                            .map(String::from),
                        auto_select: config.get("auto_lens")
                            .and_then(|v| v.as_bool())
                            .unwrap_or(true),
                    };
                }
            }
        }
        Self::default()
    }
    
    pub fn save(&self, project_path: &std::path::Path) -> Result<(), String> {
        let config_path = project_path.join(".sunwell/config.yaml");
        
        // Load existing config or create new
        let mut config: serde_yaml::Value = if config_path.exists() {
            let content = std::fs::read_to_string(&config_path)
                .map_err(|e| e.to_string())?;
            serde_yaml::from_str(&content).unwrap_or(serde_yaml::Value::Mapping(Default::default()))
        } else {
            serde_yaml::Value::Mapping(Default::default())
        };
        
        // Update lens fields
        if let serde_yaml::Value::Mapping(ref mut map) = config {
            if let Some(lens) = &self.default_lens {
                map.insert(
                    serde_yaml::Value::String("default_lens".into()),
                    serde_yaml::Value::String(lens.clone()),
                );
            } else {
                map.remove(&serde_yaml::Value::String("default_lens".into()));
            }
            map.insert(
                serde_yaml::Value::String("auto_lens".into()),
                serde_yaml::Value::Bool(self.auto_select),
            );
        }
        
        // Ensure directory exists
        if let Some(parent) = config_path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        
        let yaml = serde_yaml::to_string(&config).map_err(|e| e.to_string())?;
        std::fs::write(&config_path, yaml).map_err(|e| e.to_string())?;
        
        Ok(())
    }
}
```

#### 2. Tauri Commands

```rust
// studio/src-tauri/src/commands.rs (add to existing)

use crate::lens::{LensDetail, LensSummary, ProjectLensConfig};

/// List all available lenses.
#[tauri::command]
pub async fn list_lenses() -> Result<Vec<LensSummary>, String> {
    // Call Python CLI for lens listing
    let output = std::process::Command::new("sunwell")
        .args(["lens", "list", "--json"])
        .output()
        .map_err(|e| format!("Failed to list lenses: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let json_str = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&json_str)
        .map_err(|e| format!("Failed to parse lens list: {}", e))
}

/// Get details of a specific lens.
#[tauri::command]
pub async fn get_lens_detail(name: String) -> Result<LensDetail, String> {
    // Call Python CLI for lens details
    let output = std::process::Command::new("sunwell")
        .args(["lens", "show", &name, "--json"])
        .output()
        .map_err(|e| format!("Failed to get lens: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let json_str = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&json_str)
        .map_err(|e| format!("Failed to parse lens detail: {}", e))
}

/// Get project lens configuration.
#[tauri::command]
pub async fn get_project_lens_config(path: String) -> Result<ProjectLensConfig, String> {
    let project_path = std::path::PathBuf::from(&path);
    Ok(ProjectLensConfig::load(&project_path))
}

/// Set project default lens.
#[tauri::command]
pub async fn set_project_lens(
    path: String,
    lens_name: Option<String>,
    auto_select: bool,
) -> Result<(), String> {
    let project_path = std::path::PathBuf::from(&path);
    let config = ProjectLensConfig {
        default_lens: lens_name,
        auto_select,
    };
    config.save(&project_path)
}

/// Run goal with explicit lens selection.
#[tauri::command]
pub async fn run_goal_with_lens(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    goal: String,
    project_path: Option<String>,
    lens: Option<String>,
    auto_lens: bool,
) -> Result<RunGoalResult, String> {
    // ... existing workspace resolution ...
    
    // Build agent args
    let mut args = vec!["agent", "run", "--json", "--strategy", "harmonic"];
    
    if let Some(ref lens_name) = lens {
        args.push("--lens");
        args.push(lens_name);
    }
    
    if !auto_lens {
        args.push("--no-auto-lens");
    }
    
    args.push(&goal);
    
    // Start agent with lens args
    let mut agent = state.agent.lock().map_err(|e| e.to_string())?;
    agent.run_goal_with_args(app, &args, &workspace_path)?;
    
    // ... rest of existing logic ...
}
```

#### 3. Update Agent Bridge

```rust
// studio/src-tauri/src/agent.rs (modify run_goal)

impl AgentBridge {
    /// Run a goal with optional lens specification.
    pub fn run_goal_with_args(
        &mut self,
        app: AppHandle,
        args: &[&str],
        project_path: &Path,
    ) -> Result<(), String> {
        if self.running.load(Ordering::SeqCst) {
            return Err("Agent already running".to_string());
        }

        let mut child = Command::new("sunwell")
            .args(args)
            .current_dir(project_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start agent: {}", e))?;

        // ... rest unchanged ...
    }
}
```

#### 4. Register Commands

```rust
// studio/src-tauri/src/main.rs (add to invoke_handler)

.invoke_handler(tauri::generate_handler![
    // ... existing commands ...
    commands::list_lenses,
    commands::get_lens_detail,
    commands::get_project_lens_config,
    commands::set_project_lens,
    commands::run_goal_with_lens,
])
```

---

### Svelte: Frontend Components

#### 1. Types

```typescript
// studio/src/lib/types.ts (add)

// ═══════════════════════════════════════════════════════════════
// LENS TYPES (RFC-064)
// ═══════════════════════════════════════════════════════════════

export interface LensSummary {
  name: string;
  domain: string | null;
  version: string;
  description: string | null;
  path: string;
  heuristics_count: number;
  skills_count: number;
}

export interface HeuristicSummary {
  name: string;
  rule: string;
  priority: number;
}

export interface LensDetail {
  name: string;
  domain: string | null;
  version: string;
  description: string | null;
  author: string | null;
  heuristics: HeuristicSummary[];
  communication_style: string | null;
  skills: string[];
}

export interface ProjectLensConfig {
  default_lens: string | null;
  auto_select: boolean;
}

export interface LensSelection {
  lens: string | null;       // null = auto-select
  autoSelect: boolean;
}
```

#### 2. Lens Store

```typescript
// studio/src/stores/lens.svelte.ts (new file)

/**
 * Lens Store — Expertise Management (RFC-064)
 * 
 * Manages lens state: available lenses, selection, and project defaults.
 */

import { invoke } from '@tauri-apps/api/core';
import type { LensSummary, LensDetail, ProjectLensConfig, LensSelection } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface LensState {
  /** All available lenses */
  available: LensSummary[];
  
  /** Currently selected lens for next run */
  selection: LensSelection;
  
  /** Active lens during execution (from agent events) */
  activeLens: string | null;
  
  /** Lens detail being previewed */
  previewLens: LensDetail | null;
  
  /** Loading states */
  isLoading: boolean;
  isLoadingDetail: boolean;
  
  /** Error state */
  error: string | null;
}

function createLensState(): LensState {
  return {
    available: [],
    selection: { lens: null, autoSelect: true },
    activeLens: null,
    previewLens: null,
    isLoading: false,
    isLoadingDetail: false,
    error: null,
  };
}

export let lens = $state<LensState>(createLensState());

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load all available lenses.
 */
export async function loadLenses(): Promise<void> {
  lens.isLoading = true;
  lens.error = null;
  
  try {
    const lenses = await invoke<LensSummary[]>('list_lenses');
    lens.available = lenses;
  } catch (e) {
    lens.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to load lenses:', e);
  } finally {
    lens.isLoading = false;
  }
}

/**
 * Load details for a specific lens.
 */
export async function loadLensDetail(name: string): Promise<void> {
  lens.isLoadingDetail = true;
  
  try {
    const detail = await invoke<LensDetail>('get_lens_detail', { name });
    lens.previewLens = detail;
  } catch (e) {
    console.error('Failed to load lens detail:', e);
    lens.previewLens = null;
  } finally {
    lens.isLoadingDetail = false;
  }
}

/**
 * Clear lens preview.
 */
export function clearLensPreview(): void {
  lens.previewLens = null;
}

/**
 * Select a lens for the next run.
 */
export function selectLens(lensName: string | null, autoSelect: boolean = false): void {
  lens.selection = {
    lens: lensName,
    autoSelect: autoSelect || lensName === null,
  };
}

/**
 * Set the active lens (called from agent events).
 */
export function setActiveLens(name: string | null): void {
  lens.activeLens = name;
}

/**
 * Load project lens config.
 */
export async function loadProjectLensConfig(projectPath: string): Promise<ProjectLensConfig> {
  try {
    return await invoke<ProjectLensConfig>('get_project_lens_config', { path: projectPath });
  } catch (e) {
    console.error('Failed to load project lens config:', e);
    return { default_lens: null, auto_select: true };
  }
}

/**
 * Save project lens config.
 */
export async function saveProjectLensConfig(
  projectPath: string,
  lensName: string | null,
  autoSelect: boolean,
): Promise<void> {
  try {
    await invoke('set_project_lens', {
      path: projectPath,
      lensName,
      autoSelect,
    });
  } catch (e) {
    console.error('Failed to save project lens config:', e);
  }
}

/**
 * Get lens by domain (for auto-suggestions).
 */
export function getLensByDomain(domain: string): LensSummary | undefined {
  return lens.available.find(l => l.domain === domain);
}

/**
 * Reset lens state.
 */
export function resetLensState(): void {
  lens.selection = { lens: null, autoSelect: true };
  lens.activeLens = null;
  lens.previewLens = null;
}

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

/**
 * Get the currently selected lens summary.
 */
export function getSelectedLensSummary(): LensSummary | undefined {
  if (!lens.selection.lens) return undefined;
  return lens.available.find(l => l.name === lens.selection.lens);
}

/**
 * Get lenses grouped by domain.
 */
export function getLensesByDomain(): Map<string, LensSummary[]> {
  const grouped = new Map<string, LensSummary[]>();
  
  for (const l of lens.available) {
    const domain = l.domain || 'general';
    const existing = grouped.get(domain) || [];
    grouped.set(domain, [...existing, l]);
  }
  
  return grouped;
}
```

#### 3. Lens Picker Modal

```svelte
<!-- studio/src/components/LensPicker.svelte (new file) -->
<!--
  LensPicker — Lens selection modal (RFC-064)
  
  Allows user to select a lens before starting a project.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  import { 
    lens, 
    loadLenses, 
    loadLensDetail, 
    selectLens,
    clearLensPreview,
    getLensesByDomain,
  } from '../stores/lens.svelte';
  
  interface Props {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (lensName: string | null, autoSelect: boolean) => void;
  }
  
  let { isOpen, onClose, onConfirm }: Props = $props();
  
  let selectedLens = $state<string | null>(null);
  let autoSelect = $state(true);
  let searchQuery = $state('');
  
  // Load lenses when modal opens
  $effect(() => {
    if (isOpen && lens.available.length === 0) {
      loadLenses();
    }
  });
  
  // Filter lenses by search
  const filteredLenses = $derived(() => {
    if (!searchQuery) return lens.available;
    const q = searchQuery.toLowerCase();
    return lens.available.filter(l => 
      l.name.toLowerCase().includes(q) ||
      (l.domain?.toLowerCase().includes(q)) ||
      (l.description?.toLowerCase().includes(q))
    );
  });
  
  const groupedLenses = $derived(() => {
    const grouped = new Map<string, typeof lens.available>();
    for (const l of filteredLenses()) {
      const domain = l.domain || 'general';
      const existing = grouped.get(domain) || [];
      grouped.set(domain, [...existing, l]);
    }
    return grouped;
  });
  
  function handleSelect(name: string) {
    selectedLens = name;
    autoSelect = false;
    loadLensDetail(name);
  }
  
  function handleAutoSelect() {
    selectedLens = null;
    autoSelect = true;
    clearLensPreview();
  }
  
  function handleConfirm() {
    onConfirm(selectedLens, autoSelect);
    onClose();
  }
  
  function handleClose() {
    clearLensPreview();
    onClose();
  }
</script>

<Modal {isOpen} onClose={handleClose} title="Select Expertise">
  <div class="lens-picker">
    <!-- Search -->
    <div class="search-section">
      <input
        type="text"
        placeholder="Search lenses..."
        bind:value={searchQuery}
        class="search-input"
      />
    </div>
    
    <!-- Auto-select option -->
    <button
      class="lens-option auto-option"
      class:selected={autoSelect}
      onclick={handleAutoSelect}
    >
      <div class="lens-icon">✨</div>
      <div class="lens-info">
        <div class="lens-name">Auto-detect</div>
        <div class="lens-description">Let Sunwell choose based on your goal</div>
      </div>
      {#if autoSelect}
        <div class="check-mark">✓</div>
      {/if}
    </button>
    
    <!-- Lens list -->
    <div class="lens-list">
      {#if lens.isLoading}
        <div class="loading-state">Loading lenses...</div>
      {:else if lens.error}
        <div class="error-state">{lens.error}</div>
      {:else}
        {#each [...groupedLenses()] as [domain, lenses]}
          <div class="domain-group">
            <div class="domain-header">{domain}</div>
            {#each lenses as l}
              <button
                class="lens-option"
                class:selected={selectedLens === l.name}
                onclick={() => handleSelect(l.name)}
              >
                <div class="lens-icon">{getDomainIcon(l.domain)}</div>
                <div class="lens-info">
                  <div class="lens-name">{l.name}</div>
                  <div class="lens-description">
                    {l.description || `${l.heuristics_count} heuristics`}
                  </div>
                </div>
                {#if selectedLens === l.name}
                  <div class="check-mark">✓</div>
                {/if}
              </button>
            {/each}
          </div>
        {/each}
      {/if}
    </div>
    
    <!-- Preview panel -->
    {#if lens.previewLens}
      <div class="lens-preview">
        <div class="preview-header">
          <h3>{lens.previewLens.name}</h3>
          <span class="version">v{lens.previewLens.version}</span>
        </div>
        {#if lens.previewLens.description}
          <p class="preview-description">{lens.previewLens.description}</p>
        {/if}
        {#if lens.previewLens.heuristics.length > 0}
          <div class="preview-section">
            <h4>Heuristics</h4>
            <ul class="heuristics-list">
              {#each lens.previewLens.heuristics.slice(0, 3) as h}
                <li>
                  <strong>{h.name}</strong>
                  <span>{h.rule}</span>
                </li>
              {/each}
              {#if lens.previewLens.heuristics.length > 3}
                <li class="more">+{lens.previewLens.heuristics.length - 3} more</li>
              {/if}
            </ul>
          </div>
        {/if}
        {#if lens.previewLens.communication_style}
          <div class="preview-section">
            <h4>Communication</h4>
            <p>{lens.previewLens.communication_style}</p>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Actions -->
    <div class="actions">
      <Button variant="ghost" onclick={handleClose}>Cancel</Button>
      <Button variant="primary" onclick={handleConfirm}>
        {autoSelect ? 'Use Auto-detect' : `Use ${selectedLens}`}
      </Button>
    </div>
  </div>
</Modal>

<script context="module">
  function getDomainIcon(domain: string | null): string {
    const icons: Record<string, string> = {
      'software': '💻',
      'code': '💻',
      'documentation': '📝',
      'review': '🔍',
      'test': '🧪',
      'general': '🔮',
    };
    return icons[domain || 'general'] || '🔮';
  }
</script>

<style>
  .lens-picker {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    min-width: 400px;
    max-height: 70vh;
  }
  
  .search-section {
    padding: 0 var(--spacing-sm);
  }
  
  .search-input {
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-sm);
  }
  
  .search-input:focus {
    outline: none;
    border-color: var(--gold);
    box-shadow: 0 0 0 2px var(--gold-glow);
  }
  
  .lens-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  
  .domain-group {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  
  .domain-header {
    font-size: var(--font-xs);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: var(--spacing-sm) var(--spacing-md);
  }
  
  .lens-option {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
    width: 100%;
  }
  
  .lens-option:hover {
    background: var(--bg-hover);
    border-color: var(--border-default);
  }
  
  .lens-option.selected {
    background: var(--gold-surface);
    border-color: var(--gold);
  }
  
  .auto-option {
    background: var(--bg-secondary);
  }
  
  .lens-icon {
    font-size: 1.5rem;
  }
  
  .lens-info {
    flex: 1;
    min-width: 0;
  }
  
  .lens-name {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .lens-description {
    font-size: var(--font-sm);
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .check-mark {
    color: var(--gold);
    font-weight: bold;
  }
  
  .lens-preview {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
  }
  
  .preview-header {
    display: flex;
    align-items: baseline;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-sm);
  }
  
  .preview-header h3 {
    margin: 0;
    font-size: var(--font-md);
  }
  
  .version {
    font-size: var(--font-xs);
    color: var(--text-tertiary);
  }
  
  .preview-description {
    font-size: var(--font-sm);
    color: var(--text-secondary);
    margin-bottom: var(--spacing-md);
  }
  
  .preview-section h4 {
    font-size: var(--font-xs);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: var(--spacing-xs);
  }
  
  .heuristics-list {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: var(--font-sm);
  }
  
  .heuristics-list li {
    padding: var(--spacing-xs) 0;
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .heuristics-list li:last-child {
    border-bottom: none;
  }
  
  .heuristics-list li strong {
    color: var(--text-primary);
    display: block;
  }
  
  .heuristics-list li span {
    color: var(--text-secondary);
  }
  
  .heuristics-list .more {
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-sm);
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--border-subtle);
  }
  
  .loading-state,
  .error-state {
    padding: var(--spacing-lg);
    text-align: center;
    color: var(--text-secondary);
  }
  
  .error-state {
    color: var(--error);
  }
</style>
```

#### 4. Lens Badge Component

```svelte
<!-- studio/src/components/LensBadge.svelte (new file) -->
<!--
  LensBadge — Shows active lens during execution (RFC-064)
-->
<script lang="ts">
  import { lens } from '../stores/lens.svelte';
  
  interface Props {
    size?: 'sm' | 'md';
    showAuto?: boolean;
  }
  
  let { size = 'md', showAuto = true }: Props = $props();
  
  const displayName = $derived(() => {
    if (lens.activeLens) return lens.activeLens;
    if (lens.selection.autoSelect && showAuto) return 'Auto';
    if (lens.selection.lens) return lens.selection.lens;
    return null;
  });
</script>

{#if displayName()}
  <div class="lens-badge" class:sm={size === 'sm'}>
    <span class="icon">🔮</span>
    <span class="name">{displayName()}</span>
  </div>
{/if}

<style>
  .lens-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-xs) var(--spacing-sm);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    font-size: var(--font-sm);
    color: var(--text-secondary);
  }
  
  .lens-badge.sm {
    padding: 2px var(--spacing-xs);
    font-size: var(--font-xs);
  }
  
  .icon {
    font-size: 0.9em;
  }
  
  .name {
    font-weight: 500;
  }
</style>
```

#### 5. Update Home Screen

```svelte
<!-- studio/src/routes/Home.svelte (add lens picker integration) -->
<script lang="ts">
  // ... existing imports ...
  import LensPicker from '../components/LensPicker.svelte';
  import { lens, selectLens, loadLenses } from '../stores/lens.svelte';
  
  // ... existing state ...
  let showLensPicker = $state(false);
  let pendingGoal = $state<string | null>(null);
  
  // Load lenses on mount
  onMount(() => {
    loadLenses();
  });
  
  async function handleSubmit(e: CustomEvent<{ value: string }>) {
    const goal = e.detail.value.trim();
    if (!goal) return;
    
    // Show lens picker before starting
    pendingGoal = goal;
    showLensPicker = true;
  }
  
  async function handleLensConfirm(lensName: string | null, autoSelect: boolean) {
    if (!pendingGoal) return;
    
    selectLens(lensName, autoSelect);
    
    // Run with lens selection
    await invoke('run_goal_with_lens', {
      goal: pendingGoal,
      projectPath: null,
      lens: lensName,
      autoLens: autoSelect,
    });
    
    goToProject();
    pendingGoal = null;
  }
  
  function handleLensPickerClose() {
    showLensPicker = false;
    pendingGoal = null;
  }
</script>

<!-- ... existing template ... -->

<!-- Add lens picker modal -->
<LensPicker
  isOpen={showLensPicker}
  onClose={handleLensPickerClose}
  onConfirm={handleLensConfirm}
/>
```

#### 6. Handle Lens Events

```typescript
// studio/src/stores/agent.svelte.ts (add to handleAgentEvent)

export function handleAgentEvent(event: AgentEvent): void {
  switch (event.type) {
    // ... existing cases ...
    
    case 'lens_selected':
      // Import at top: import { setActiveLens } from './lens.svelte';
      setActiveLens(event.data.name);
      agent.learnings = [
        ...agent.learnings,
        `Using lens: ${event.data.name} (${event.data.reason})`,
      ];
      break;
      
    case 'lens_changed':
      setActiveLens(event.data.name);
      break;
  }
}
```

---

## Implementation Plan

### Phase 1: Python Backend (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Add `lens_resolver.py` module | High | Medium |
| Add `--lens` and `--no-auto-lens` flags to agent CLI | High | Small |
| Integrate lens resolution into `AdaptiveAgent` | High | Medium |
| Add `LENS_SELECTED` event type | High | Small |
| Create `sunwell lens list` command | Medium | Small |
| Create `sunwell lens show` command | Medium | Small |
| Add `--json` output to lens commands | Medium | Small |

### Phase 2: Rust Backend (1-2 days)

| Task | Priority | Effort |
|------|----------|--------|
| Add `lens.rs` module with types | High | Small |
| Add `list_lenses` command | High | Small |
| Add `get_lens_detail` command | High | Small |
| Add `run_goal_with_lens` command | High | Medium |
| Add project lens config load/save | Medium | Small |
| Update agent bridge for lens args | High | Small |

### Phase 3: Svelte Frontend (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Add lens types to `types.ts` | High | Small |
| Create `lens.svelte.ts` store | High | Medium |
| Create `LensPicker.svelte` modal | High | Medium |
| Create `LensBadge.svelte` component | Medium | Small |
| Integrate lens picker into Home | High | Small |
| Handle `lens_selected` events | High | Small |
| Add lens badge to project header | Medium | Small |
| Add lens settings to project config | Low | Medium |

### Phase 4: Polish (1 day)

| Task | Priority | Effort |
|------|----------|--------|
| Keyboard shortcuts for lens picker | Low | Small |
| Lens search/filter UX improvements | Medium | Small |
| Lens usage analytics/history | Low | Medium |
| Documentation | Medium | Small |

---

## Event Schema Addition

```typescript
// Add to src/sunwell/adaptive/event_schema.py

LENS_SELECTED_SCHEMA = {
    "type": "object",
    "required": ["name", "source", "confidence", "reason"],
    "properties": {
        "name": {"type": "string", "description": "Lens name"},
        "source": {
            "type": "string",
            "enum": ["explicit", "auto", "project_default", "none"],
            "description": "How the lens was selected",
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "description": "Selection rationale"},
    },
}
```

---

## Configuration Schema

### Project Config (`.sunwell/config.yaml`)

```yaml
# Lens configuration (RFC-064)
default_lens: coder          # Lens to use by default
auto_lens: true              # Allow auto-detection to override

# Other project settings...
model: gemma3:4b
trust_level: workspace
```

### Global Config (`~/.sunwell/config.yaml`)

```yaml
# Global lens preferences (RFC-064)
lens:
  search_paths:
    - ~/.sunwell/lenses
    - ./lenses
  default: null              # Global default (overridden by project)
  auto_select: true          # Enable auto-selection globally
```

---

## Testing Strategy

### Python Tests

```python
# tests/test_lens_resolver.py

import pytest
from pathlib import Path
from sunwell.adaptive.lens_resolver import resolve_lens_for_goal, _load_lens


@pytest.mark.asyncio
async def test_explicit_lens():
    """Explicit lens should be used."""
    result = await resolve_lens_for_goal(
        goal="Write documentation",
        explicit_lens="tech-writer",
    )
    assert result.source == "explicit"
    assert result.lens is not None
    assert result.lens.metadata.name == "Technical Writer"


@pytest.mark.asyncio
async def test_explicit_lens_not_found():
    """Explicit lens that doesn't exist returns confidence 0."""
    result = await resolve_lens_for_goal(
        goal="Write documentation",
        explicit_lens="nonexistent-lens",
    )
    assert result.source == "explicit"
    assert result.lens is None
    assert result.confidence == 0.0
    assert "Could not load" in result.reason


@pytest.mark.asyncio
async def test_auto_select_code():
    """Code goals should auto-select coder lens."""
    result = await resolve_lens_for_goal(
        goal="Build a REST API with authentication",
        auto_select=True,
    )
    assert result.source == "auto"
    assert result.lens is not None
    assert "coder" in result.lens.metadata.name.lower()


@pytest.mark.asyncio
async def test_auto_select_documentation():
    """Documentation goals should auto-select writer lens."""
    result = await resolve_lens_for_goal(
        goal="Write getting started guide for new users",
        auto_select=True,
    )
    assert result.source == "auto"
    assert result.lens is not None
    assert "writer" in result.lens.metadata.name.lower()


@pytest.mark.asyncio
async def test_no_lens_when_disabled():
    """No lens when auto_select is False and no explicit."""
    result = await resolve_lens_for_goal(
        goal="Do something",
        auto_select=False,
    )
    assert result.source == "none"
    assert result.lens is None


@pytest.mark.asyncio
async def test_project_default_lens(tmp_path: Path):
    """Project default lens should be used when set."""
    # Create project config
    config_dir = tmp_path / ".sunwell"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("default_lens: coder\n")
    
    result = await resolve_lens_for_goal(
        goal="Do something",
        project_path=tmp_path,
    )
    assert result.source == "project_default"
    assert result.lens is not None


@pytest.mark.asyncio
async def test_priority_explicit_over_project():
    """Explicit lens takes priority over project default."""
    result = await resolve_lens_for_goal(
        goal="Write docs",
        explicit_lens="tech-writer",
        project_path=Path("/fake/project"),  # Has coder as default
    )
    assert result.source == "explicit"
    assert "writer" in result.lens.metadata.name.lower()


@pytest.mark.asyncio
async def test_confidence_threshold():
    """Resolution confidence should reflect source."""
    explicit = await resolve_lens_for_goal(goal="x", explicit_lens="coder")
    auto = await resolve_lens_for_goal(goal="Build API", auto_select=True)
    none = await resolve_lens_for_goal(goal="x", auto_select=False)
    
    assert explicit.confidence == 1.0  # Explicit is certain
    assert auto.confidence >= 0.7      # Auto should be confident
    assert none.confidence == 1.0       # "No lens" is also certain
```

### Frontend Tests

```typescript
// studio/src/stores/lens.svelte.test.ts

import { describe, it, expect, vi } from 'vitest';
import { lens, selectLens, resetLensState } from './lens.svelte';

describe('lens store', () => {
  beforeEach(() => {
    resetLensState();
  });
  
  it('should start with auto-select enabled', () => {
    expect(lens.selection.autoSelect).toBe(true);
    expect(lens.selection.lens).toBeNull();
  });
  
  it('should select explicit lens', () => {
    selectLens('coder', false);
    expect(lens.selection.lens).toBe('coder');
    expect(lens.selection.autoSelect).toBe(false);
  });
  
  it('should reset to auto-select', () => {
    selectLens('coder', false);
    selectLens(null, true);
    expect(lens.selection.lens).toBeNull();
    expect(lens.selection.autoSelect).toBe(true);
  });
});
```

---

## Security Considerations

1. **Lens file validation** — Only load `.lens` files from configured search paths
2. **No code execution** — Lenses contain heuristics, not executable code
3. **Path traversal** — Sanitize lens paths to prevent directory traversal
4. **Trust levels** — Skills within lenses inherit project trust level

---

## Performance Considerations

### Lens Resolution Latency

Lens resolution adds overhead to goal execution:

| Operation | Expected Latency | Mitigation |
|-----------|------------------|------------|
| Explicit lens load | ~5-15ms | Single disk read, cached |
| Project config check | ~2-5ms | Filesystem stat |
| Auto-select (router) | ~100-300ms | Model inference (if router used) |
| Auto-select (domain) | ~10-50ms | Keyword classification only |

**Mitigation strategies:**

1. **Lazy resolution** — Don't resolve until `agent.run()` is called
2. **Resolution caching** — Cache `LensResolution` per (goal_hash, project_path)
3. **Router optional** — Fall back to fast domain classification if router unavailable
4. **Pre-warming** — Studio can pre-load available lenses list at startup

### Context Size Impact

Lenses add context to the system prompt via `lens.to_context()`:

| Lens Type | Typical Context Size | Impact |
|-----------|---------------------|--------|
| Minimal (helper) | ~200-500 tokens | Negligible |
| Standard (coder) | ~800-1500 tokens | Moderate |
| Full (team-dev) | ~1500-3000 tokens | Significant |

**Mitigation strategies:**

1. **Selective injection** — Only inject relevant heuristics (not all)
2. **Compression** — Use concise prompt fragments in `to_context()`
3. **Budget awareness** — Check `AdaptiveBudget.is_low` before injecting full context

### Memory Footprint

Loaded `Lens` objects are lightweight (~10-50KB each). With caching:

- **LensDiscovery cache**: ~9 lenses × 50KB = ~450KB max
- **Studio lens list**: ~9 summaries × 1KB = ~9KB

No concern for memory pressure.

---

## Backward Compatibility

**No breaking changes.** This RFC is purely additive.

| Component | Before RFC-064 | After RFC-064 | Breaking? |
|-----------|----------------|---------------|-----------|
| `sunwell agent run "goal"` | No lens | Auto-lens (can disable) | No — adds capability |
| `sunwell "goal"` (shorthand) | No lens | Auto-lens | No — adds capability |
| `AdaptiveAgent()` | No lens attribute | `lens: Lens | None = None` | No — new optional field |
| `.sunwell/config.yaml` | No lens fields | Optional `default_lens`, `auto_lens` | No — new optional fields |
| Studio goal entry | Direct execution | Lens picker (auto-select default) | No — same default behavior |

**Migration path:**
- Existing CLI scripts: Work unchanged (auto-lens enabled by default)
- Existing projects: Work unchanged (no config required)
- Users who don't want lenses: Use `--no-auto-lens` flag

## Migration

No migration steps required. Existing projects continue to work without lenses. The new functionality is additive:

- CLI: `--lens` flag is optional; `--no-auto-lens` to disable
- Studio: Lens picker can be skipped (defaults to auto-select)
- Projects: `.sunwell/config.yaml` lens fields are optional

---

## Future Extensions

1. **Lens marketplace** — Browse and install community lenses from Fount
2. **Lens editor** — Create/edit lenses in Studio UI
3. **Lens inheritance visualization** — Show extends/compose relationships
4. **Lens effectiveness tracking** — Track which lenses produce best results
5. **Dynamic lens switching** — Change lens mid-execution based on context
6. **Multi-lens composition** — Apply multiple lenses simultaneously

---

## Design Decisions

These questions were raised and resolved during RFC development:

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should lens selection persist in session history? | **Yes** — include in Simulacrum DAG | Enables replay, debugging, and lens effectiveness tracking |
| Should we show lens heuristics during execution? | **Deferred** — not in v1 | Focus on core integration first; heuristics panel is future enhancement |
| Lens versioning in projects? | **Deferred** — not in v1 | No breaking changes expected; versioning is future enhancement |
| Auto-lens confidence threshold? | **0.7** (match `QualityPolicy.min_confidence` default) | Below 0.7 confidence, use domain classification fallback instead of router |
| What if UnifiedRouter unavailable? | **Fall back to domain classification** | `classify_domain()` → `LensDiscovery.discover()` works without router |
| How does lens interact with NaaruConfig? | **Separate concern** — lens on AdaptiveAgent, not Naaru | Agent owns expertise (lens); Naaru owns planning. Clean separation. |

## Open Questions (Post-Implementation)

1. **Lens effectiveness metrics** — How do we measure if a lens improved output quality?
2. **Lens recommendation engine** — Can we suggest lenses based on project history?
3. **Lens inheritance UI** — How should Studio visualize extends/compose relationships?

---

## References

- `lenses/*.lens` — Existing lens files
- `src/sunwell/core/lens.py` — Lens data model
- `src/sunwell/naaru/expertise/discovery.py` — LensDiscovery implementation
- `src/sunwell/routing/unified.py` — UnifiedRouter with lens suggestion
- RFC-011 — Agent Skills (skills within lenses)
- RFC-039 — Expertise-Aware Planning
