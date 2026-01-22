# RFC-090: Plan Transparency — Actionable Planning Output

**Status**: Evaluated  
**Author**: Sunwell Team  
**Created**: 2026-01-22  
**Depends On**: RFC-042 (Adaptive Agent), RFC-043 (Sunwell Studio), RFC-055 (Planning View)  
**Confidence**: 94% 🟢

## Summary

Transform `sunwell "goal" --plan` from a minimal summary into an actionable planning interface. Currently outputs just counts ("6 tasks, 4 validation gates") and exits. Should show actual task details, offer to open in Studio's pipeline view, and provide clear next actions.

## Problem

### Current Behavior

```bash
$ sunwell "Create quickstart" --plan
Planning only (--plan)

Plan ready (single_shot)
  • 6 tasks, 4 validation gates
```

The command exits immediately. Users see:
- Task count (6) — but not **what** the tasks are
- Gate count (4) — but not **when** they run
- No way to visualize dependencies
- No option to approve/modify before execution
- No path to the Studio DAG view

### Root Cause

The `PLAN_WINNER` event only includes counts, not the actual data:

```python
# src/sunwell/adaptive/agent.py:567-574
yield AgentEvent(
    EventType.PLAN_WINNER,
    {
        "tasks": len(tasks),      # Just the count
        "gates": len(gates),      # Just the count
        "technique": "harmonic",
    },
)
```

The rich task graph (`self._task_graph`) is populated but never serialized.

### User Impact

| Scenario | Pain |
|---|---|
| Quick sanity check | Can't see if plan is reasonable |
| Complex goal | Can't spot missing tasks before execution |
| Team review | Nothing shareable for approval |
| Debugging | No visibility into planning decisions |

## Goals

1. **Task visibility**: Show actual task IDs, descriptions, and dependencies in `--plan` output
2. **Studio bridge**: Enable one-command path from CLI planning to Studio DAG visualization
3. **Scriptability**: Provide `--json` output for CI/CD and tooling integration
4. **Progressive disclosure**: Compact by default, detailed with `--verbose`

## Non-Goals

- **Plan editing in CLI**: Defer to Studio for interactive editing
- **Plan diffing**: Comparing plans across runs is valuable but out of scope (future RFC)
- **Approval workflows**: Team approval gates are a separate concern
- **Cost estimation**: Token/time predictions belong in `--plan --verbose`, not core output

## Solution

### Enhanced `--plan` Output

```
$ sunwell "Create quickstart" --plan

Planning only (--plan)

Plan ready (single_shot)
  • 6 tasks, 4 validation gates

📋 Tasks
  1. [project-init]    Create project structure        
  2. [user-model]      Define User model               → models/user.py
  3. [post-model]      Define Post model (←1,2)        → models/post.py
  4. [auth-system]     Implement JWT auth (←2)         → auth/jwt.py
  5. [api-routes]      Create API endpoints (←3,4)     → routes/api.py
  6. [readme]          Write README                    → README.md

🔒 Validation Gates
  • [G1] Syntax check     after: 1,2,3,4
  • [G2] Type check       after: 2,3,4
  • [G3] Lint check       after: 5
  • [G4] Runtime test     after: 5,6

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Next steps:
  • sunwell "Create quickstart"                Run now
  • sunwell "Create quickstart" --plan --open  Open in Studio
  • sunwell plan "Create quickstart" -o .      Save plan
```

### New Flags

| Flag | Description |
|------|-------------|
| `--open` | After planning, launch Studio in pipeline view |
| `--verbose` | Show full task descriptions and dependency chains |
| `--json` | Output plan as JSON (for scripting/pipelines) |

### Studio Integration

`--plan --open` workflow:

1. Generate plan (as today)
2. Save plan to `.sunwell/current-plan.json`
3. Launch Studio with `--mode planning --plan <path>`
4. Studio loads plan into DAG store, displays in `DagCanvas`

User can then:
- See critical path highlighted
- Hover nodes to see "would unblock" previews
- Spot bottleneck nodes
- Approve/modify before execution
- Click "Execute" to run

## Design

### Event Schema Changes

Extend `PLAN_WINNER` event to include task details:

```python
class PlanWinnerData(TypedDict, total=False):
    """Data for PLAN_WINNER event."""
    
    # Existing fields
    tasks: int
    gates: int
    technique: str
    selected_candidate_id: str
    total_candidates: int
    
    # NEW: Serialized task list (RFC-090)
    task_list: list[TaskSummary]
    gate_list: list[GateSummary]
    
    
class TaskSummary(TypedDict):
    """Minimal task info for plan display."""
    id: str
    description: str
    depends_on: list[str]
    produces: list[str]  # Artifact paths
    category: str | None
    
    
class GateSummary(TypedDict):
    """Minimal gate info for plan display."""
    id: str
    type: str  # "syntax", "lint", "type", "runtime"
    after_tasks: list[str]
```

### Agent Changes

Update `_single_shot_plan` and `_harmonic_plan` to include task details:

```python
# src/sunwell/adaptive/agent.py

async def _single_shot_plan(self, goal: str, context: dict | None) -> AsyncIterator[AgentEvent]:
    """Single-shot planning with full task visibility."""
    # ... existing discovery code ...
    
    self._task_graph = TaskGraph(tasks=tasks, gates=gates)
    
    yield AgentEvent(
        EventType.PLAN_WINNER,
        {
            "tasks": len(tasks),
            "gates": len(gates),
            "technique": "single_shot",
            # NEW: Include serialized details
            "task_list": [
                {
                    "id": t.id,
                    "description": t.description,
                    "depends_on": list(t.depends_on),
                    "produces": list(t.produces),
                    "category": getattr(t, "category", None),
                }
                for t in tasks
            ],
            "gate_list": [
                {
                    "id": g.id,
                    "type": g.type.value,
                    "after_tasks": [g.after_task_id] if g.after_task_id else [],
                }
                for g in gates
            ],
        },
    )
```

### Renderer Changes

Update the rich renderer to display task details when available:

```python
# src/sunwell/adaptive/renderer.py

def _render_plan(self, data: dict) -> None:
    """Render plan selection with optional task details (RFC-090)."""
    tasks = data.get("tasks", 0)
    gates = data.get("gates", 0)
    technique = data.get("technique", "unknown")
    task_list = data.get("task_list", [])
    
    self.console.print(f"\n📋 [bold]Plan ready[/bold] ({technique})")
    self.console.print(f"   ├─ {tasks} tasks")
    self.console.print(f"   └─ {gates} validation gates")
    
    # RFC-090: Show task details if available
    if task_list:
        self.console.print("\n[bold]Tasks:[/bold]")
        display_count = min(10, len(task_list))  # Truncate at 10
        for i, task in enumerate(task_list[:display_count], 1):
            desc = task.get("description", "")[:40]
            self.console.print(f"   {i}. {desc}")
        if len(task_list) > 10:
            self.console.print(f"   ... and {len(task_list) - 10} more tasks")
```

### CLI Changes

#### Main Entry Point

```python
# src/sunwell/cli/main.py

@click.group(cls=GoalFirstGroup, invoke_without_command=True)
@click.option("--plan", is_flag=True, help="Show plan without executing")
@click.option("--open", "open_studio", is_flag=True, help="Open plan in Studio (with --plan)")
@click.option("--json", "json_output", is_flag=True, help="Output plan as JSON (with --plan)")
@click.option("--model", "-m", help="Override model selection")
# ... other options ...
def main(ctx, plan: bool, open_studio: bool, json_output: bool, model: str | None, ...):
    # ...
    if goal and ctx.invoked_subcommand is None:
        ctx.invoke(
            _run_goal,
            goal=goal,
            dry_run=plan,
            open_studio=open_studio,  # NEW: RFC-090
            json_output=json_output,  # NEW: RFC-090
            model=model,
            # ...
        )
```

#### Enhanced Dry Run Output

```python
# src/sunwell/cli/main.py

async def _async_run_goal(
    goal: str,
    dry_run: bool,
    open_studio: bool,  # NEW: RFC-090
    json_output: bool,  # NEW: RFC-090
    # ...
):
    # ... existing setup ...
    
    if dry_run:
        plan_data = None
        async for event in agent.plan(goal):
            if event.type == EventType.PLAN_WINNER:
                plan_data = event.data
            elif event.type == EventType.ERROR:
                if not json_output:
                    _print_event(event, verbose)
        
        if plan_data:
            # RFC-090: JSON output for scripting
            if json_output:
                import json
                click.echo(json.dumps(plan_data, indent=2))
                return
            
            # Rich output
            console.print("[yellow]Planning only (--plan)[/yellow]\n")
            _print_plan_details(plan_data, verbose)
            
            # Open in Studio if requested
            if open_studio:
                _open_plan_in_studio(plan_data, goal)
        
        return


def _print_plan_details(data: dict, verbose: bool) -> None:
    """Print rich plan details with truncation (RFC-090)."""
    from rich.table import Table
    from rich.panel import Panel
    
    technique = data.get("technique", "unknown")
    tasks = data.get("tasks", 0)
    gates = data.get("gates", 0)
    task_list = data.get("task_list", [])
    gate_list = data.get("gate_list", [])
    
    # Header
    console.print(f"\n[bold]Plan ready[/bold] ({technique})")
    console.print(f"  • {tasks} tasks, {gates} validation gates\n")
    
    # Task list with truncation
    if task_list:
        console.print("[bold]📋 Tasks[/bold]")
        display_limit = len(task_list) if verbose else 10
        for i, task in enumerate(task_list[:display_limit], 1):
            deps = ""
            if task.get("depends_on"):
                if verbose:
                    # Show IDs with --verbose
                    deps = f" (←{','.join(task['depends_on'][:3])})"
                else:
                    # Show numbers by default
                    dep_nums = [
                        str(j + 1) for j, t in enumerate(task_list) 
                        if t["id"] in task["depends_on"]
                    ]
                    deps = f" (←{','.join(dep_nums)})" if dep_nums else ""
            
            produces = ""
            if task.get("produces"):
                produces = f" → {task['produces'][0]}"
            
            console.print(f"  {i}. [{task['id'][:12]:12}] {task['description'][:35]:35}{deps}{produces}")
        
        # Truncation notice
        if not verbose and len(task_list) > 10:
            console.print(f"  [dim]... and {len(task_list) - 10} more tasks (use --verbose to see all)[/dim]")
        console.print()
    
    # Gate list
    if gate_list:
        console.print("[bold]🔒 Validation Gates[/bold]")
        for gate in gate_list:
            after = ", ".join(gate.get("after_tasks", [])[:3])
            console.print(f"  • [{gate['id']}] {gate['type']:12} after: {after}")
        console.print()
    
    # Next steps
    console.print("━" * 50)
    console.print("[bold]💡 Next steps:[/bold]")
    console.print('  • sunwell "..." [dim]Run now[/dim]')
    console.print('  • sunwell "..." --plan --open [dim]Open in Studio[/dim]')
    console.print('  • sunwell plan "..." -o . [dim]Save plan[/dim]')


def _open_plan_in_studio(plan_data: dict, goal: str) -> None:
    """Save plan and open in Studio."""
    import json
    from sunwell.cli.open_cmd import launch_studio
    
    # Ensure .sunwell directory exists
    plan_dir = Path.cwd() / ".sunwell"
    plan_dir.mkdir(exist_ok=True)
    
    # Save plan with goal context
    plan_file = plan_dir / "current-plan.json"
    plan_data["goal"] = goal
    plan_data["created_at"] = datetime.now().isoformat()
    plan_file.write_text(json.dumps(plan_data, indent=2))
    
    console.print(f"\n[cyan]Opening plan in Studio...[/cyan]")
    
    # Launch Studio in planning mode
    launch_studio(
        project=str(Path.cwd()),
        lens="coder",
        mode="planning",
    )
```

### Studio Integration

#### Tauri Backend

Add `--plan` argument support:

```rust
// studio/src-tauri/src/main.rs

#[command]
fn load_plan_file(plan_path: String) -> Result<DagGraph, String> {
    let content = std::fs::read_to_string(&plan_path)
        .map_err(|e| format!("Failed to read plan: {}", e))?;
    
    let plan: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse plan: {}", e))?;
    
    // Convert to DagGraph format
    let graph = plan_to_dag_graph(&plan)?;
    Ok(graph)
}

fn plan_to_dag_graph(plan: &serde_json::Value) -> Result<DagGraph, String> {
    let task_list = plan["task_list"].as_array()
        .ok_or("Missing task_list")?;
    
    let nodes: Vec<DagNode> = task_list.iter().map(|t| {
        DagNode {
            id: t["id"].as_str().unwrap_or("").to_string(),
            title: t["id"].as_str().unwrap_or("").to_string(),
            description: t["description"].as_str().unwrap_or("").to_string(),
            status: "pending".to_string(),
            depends_on: t["depends_on"].as_array()
                .map(|a| a.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                .unwrap_or_default(),
            // ... other fields
        }
    }).collect();
    
    // Build edges from dependencies
    let edges: Vec<DagEdge> = nodes.iter()
        .flat_map(|n| n.depends_on.iter().map(|dep| DagEdge {
            id: format!("{}-{}", dep, n.id),
            source: dep.clone(),
            target: n.id.clone(),
        }))
        .collect();
    
    Ok(DagGraph {
        goal: plan["goal"].as_str().map(String::from),
        nodes,
        edges,
        total_progress: 0,
    })
}
```

#### CLI Args Update

Extend the startup arguments to include plan file:

```rust
// studio/src-tauri/src/main.rs

#[derive(Parser, Debug, Clone)]
#[command(name = "sunwell-studio", about = "AI-native writing environment")]
struct CliArgs {
    #[arg(short, long)]
    project: Option<String>,

    #[arg(short, long)]
    lens: Option<String>,

    #[arg(short, long)]
    mode: Option<String>,

    // NEW: Plan file to load on startup (RFC-090)
    #[arg(long)]
    plan: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct StartupParams {
    pub project: Option<String>,
    pub lens: Option<String>,
    pub mode: Option<String>,
    pub plan: Option<String>,  // NEW
}
```

Register the command in `invoke_handler!`:

```rust
// studio/src-tauri/src/main.rs (in invoke_handler! macro)

.invoke_handler(tauri::generate_handler![
    // ... existing commands ...
    // DAG / Pipeline view (RFC-056)
    dag::get_project_dag,
    dag::execute_dag_node,
    dag::refresh_backlog,
    dag::load_plan_file,  // NEW: RFC-090
    // ...
])
```

#### Auto-Load on Planning Mode

```svelte
<!-- studio/src/routes/Planning.svelte -->

<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { listen } from '@tauri-apps/api/event';
  import { dag, setGraph } from '../stores/dag.svelte';
  import type { DagGraph, StartupParams } from '$lib/types';

  onMount(async () => {
    // Listen for startup params (plan file from CLI)
    const unlisten = await listen<StartupParams>('startup-params', async (event) => {
      if (event.payload.plan) {
        try {
          const graph = await invoke<DagGraph>('load_plan_file', { 
            planPath: event.payload.plan 
          });
          setGraph(graph);
        } catch (e) {
          console.error('Failed to load plan file:', e);
        }
      }
    });
    
    return unlisten;
  });
</script>
```

### launch_studio Update

```python
# src/sunwell/cli/open_cmd.py

def launch_studio(
    project: str, 
    lens: str, 
    mode: str,
    plan_file: str | None = None,  # NEW
) -> None:
    """Launch Sunwell Studio (Tauri app)."""
    args = ["--project", project, "--lens", lens, "--mode", mode]
    
    # NEW: Pass plan file if provided
    if plan_file:
        args.extend(["--plan", plan_file])
    
    # ... existing binary search logic ...
```

## User Experience

### Flow 1: Quick Plan Check

```bash
$ sunwell "Build a forum app" --plan

Planning only (--plan)

Plan ready (single_shot)
  • 8 tasks, 5 validation gates

📋 Tasks
  1. [project-init]    Create project structure        
  2. [user-model]      Define User model               → models/user.py
  3. [post-model]      Define Post model (←1,2)        → models/post.py
  ...

💡 Next steps:
  • sunwell "Build a forum app"                Run now
```

User reviews, confirms plan looks good, runs without `--plan`.

### Flow 2: Open in Studio

```bash
$ sunwell "Build a forum app" --plan --open

Planning only (--plan)
...
Opening plan in Studio...
```

Studio launches with full DAG visualization:
- Nodes colored by status (pending/ready/blocked)
- Critical path highlighted
- Hover shows "would unblock" previews
- "Execute" button to start run

### Flow 3: Save for Later

```bash
$ sunwell plan "Build a forum app" -o forum-plan.json
Plan saved to forum-plan.json

# Later...
$ sunwell open . --plan forum-plan.json
```

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large task lists clutter terminal | Medium | Low | Show max 10 tasks by default; `--verbose` for all |
| Schema change breaks consumers | Low | Medium | Additive only — new fields are optional |
| Studio fails to load malformed plan | Low | Medium | Validate JSON before save; fallback to empty graph |
| Performance regression from serialization | Low | Low | Task objects are small; serialization is O(n) with n < 100 typically |

### Display Limits

- **Default mode**: Show first 10 tasks, then `... and N more tasks`
- **`--verbose`**: Show all tasks with full descriptions
- **`--json`**: Always emit complete data (no truncation)

## Migration

### Phase 1: Event Schema (Non-Breaking)

1. Add `task_list` and `gate_list` to `PlanWinnerData`
2. Add `TaskSummary` and `GateSummary` types
3. Existing consumers ignore new fields

### Phase 2: Agent Emission

1. Update `_single_shot_plan` to include task details
2. Update `_harmonic_plan` to include task details
3. No CLI changes yet — existing output works

### Phase 3: CLI Enhancement

1. Add `_print_plan_details()` function
2. Add `--open` flag to main command
3. Add `_open_plan_in_studio()` function

### Phase 4: Studio Integration

1. Add `--plan` argument handling to Tauri
2. Add `load_plan_file` command
3. Auto-load plan when mode=planning

## Alternatives Considered

### 1. Separate `sunwell plan` Command Only

Keep `--plan` minimal, push users to `sunwell plan` for details.

**Rejected**: Users expect `--plan` to show the plan. Separate command is for advanced options (file input, mermaid output).

### 2. Always Show Full Details

Remove `--verbose` flag, always show everything.

**Rejected**: For simple goals, the full output is overwhelming. Progressive disclosure is better.

### 3. Interactive Plan Editor

After `--plan`, offer inline editing before execution.

**Deferred**: Good idea, but complex. Studio already provides this via GUI. Can add later.

## Success Metrics

| Metric | Target |
|--------|--------|
| `--plan` usage increases | 2x within 1 month |
| Users who `--plan` then execute | > 80% |
| `--plan --open` adoption | > 30% of `--plan` uses |
| Time from plan to execute | < 30 seconds |

## Design Decisions

### Task Truncation
**Decision**: Show first 10 tasks by default, then `... and N more tasks`. Use `--verbose` for complete list.

**Rationale**: 10 tasks fit comfortably in a terminal window without scrolling. Most plans are under 10 tasks; larger plans benefit from Studio visualization anyway.

### Dependency Notation
**Decision**: Use task numbers `(←1,2)` in default output; show IDs `(←user-model)` with `--verbose`.

**Rationale**: Numbers are compact and scannable. IDs are more precise but create visual noise. Progressive disclosure: quick scan vs. detailed analysis.

### Plan Diffing
**Decision**: Defer to future RFC.

**Rationale**: Valuable for incremental execution (RFC-074) but adds complexity. Current scope focuses on visibility, not comparison.

## References

- RFC-042: Adaptive Agent (event system)
- RFC-043: Sunwell Studio (Tauri app)
- RFC-055: Planning View (Studio DAG components)
- RFC-074: Incremental Execution (skip/execute visualization)
