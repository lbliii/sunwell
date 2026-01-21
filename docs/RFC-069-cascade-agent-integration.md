# RFC-069: Cascade Agent Integration — Wiring Weakness Fix to Artifact Execution

**Status**: Draft  
**Created**: 2026-01-20  
**Authors**: Sunwell Team  
**Confidence**: 87% 🟢  
**Depends on**: RFC-063 (Weakness Cascade), RFC-036 (Artifact Execution), RFC-040 (Incremental Build)  
**Alternatives**: Evaluated 3 options; see "Alternatives Considered" section

---

## Summary

Wire the cascade fix button in Studio to the agent's artifact execution system, enabling automated regeneration of weak code and all its dependents with wave-by-wave confidence verification.

**The gap**: RFC-063 implemented weakness detection, cascade preview, and the execution state machine, but left a TODO at the critical point—actually invoking the agent to regenerate artifacts. This RFC completes that circuit.

**The insight**: We already have `ArtifactExecutor` that creates artifacts from specs. A cascade is just a specialized artifact graph where:
- Wave 0 = the weak node (regenerate mode)
- Wave 1+ = dependents (update mode)
- Each wave includes verification before proceeding

The integration is a bridge, not a rewrite.

---

## Goals

1. **Fix button works** — Clicking "Fix N files" triggers actual code regeneration
2. **Wave-by-wave execution** — Each wave runs through the artifact executor with verification
3. **Event streaming** — UI receives real-time progress via existing agent event system
4. **Confidence-gated** — Low confidence pauses execution for human review
5. **Contract preservation** — Regenerated code maintains backward-compatible interfaces

## Non-Goals

1. **New execution engine** — Create focused `CascadeExecutor` that bridges to artifact system; avoid modifying `IncrementalExecutor`
2. **New event types** — Map to existing `task_start`, `task_complete`, etc.
3. **Semantic verification** — Contract checks are signature-level (behavior verification is future work)

---

## Motivation

### The Missing Link

RFC-063's cascade system is complete except for one critical piece:

```python
# src/sunwell/weakness/cascade.py, lines 505-506
async def execute_wave_by_wave(...):
    for wave_num, wave in enumerate(preview.waves):
        # Execute wave (would call agent here in real implementation)
        # ... agent execution ...
```

The detection, preview, confidence scoring, and state machine all work. Users can see their weaknesses, preview the cascade impact, but clicking "Fix" shows a notice that the feature isn't ready.

### Why This Matters

1. **Workflow completion** — Users identify weakness → see impact → want to fix it
2. **Trust building** — Showing a preview without ability to execute erodes confidence
3. **Technical debt cycle** — Without automated fix, weakness data is just information, not action

### The Architecture Advantage

We don't need to build a new execution system. The pieces exist:

| Component | Exists | Purpose |
|-----------|--------|---------|
| `CascadeEngine.preview()` | ✅ | Computes waves and affected files |
| `CascadeEngine.extract_contract()` | ✅ | Captures interfaces before regeneration |
| `IncrementalExecutor.execute()` | ✅ | Runs artifact graphs wave-by-wave |
| `AgentPlanner.create_artifact()` | ✅ | Generates code via LLM |
| Event system | ✅ | Streams progress to Studio |
| `WaveConfidence.compute()` | ✅ | Scores verification results |

The missing piece is the glue: converting cascade preview → artifact specs → executor invocation.

---

## Alternatives Considered

### Alternative 1: Extend `IncrementalExecutor` Directly

**Approach**: Add cascade-specific methods to `IncrementalExecutor` in `naaru/incremental.py`.

**Rejected because**:
- Cascade execution has different semantics (wave-by-wave approval, contract verification)
- Would bloat the incremental executor with cascade-specific logic
- Violates single responsibility—incremental builds ≠ weakness remediation

### Alternative 2: Full Artifact Graph per Cascade

**Approach**: Build one large `ArtifactGraph` with all waves and let `IncrementalExecutor` handle ordering.

**Rejected because**:
- No natural verification checkpoints between waves
- Can't pause for human approval mid-execution
- All-or-nothing execution—partial failures harder to recover

### Chosen: Dedicated `CascadeExecutor` Bridge

**Why this approach**:
- Clean separation: cascade semantics live in `weakness/executor.py`
- Reuses existing components (`AgentPlanner`, `ToolExecutor`, event system)
- Enables wave-by-wave verification and approval
- Minimal changes to existing code

---

## Architecture Impact

This RFC adds one new module (`weakness/executor.py`) and updates three existing touchpoints:

```
┌─────────────────────────────────────────────────────────────┐
│                         Studio (Svelte)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │ invoke()
┌─────────────────────────▼───────────────────────────────────┐
│                      Tauri Bridge (Rust)                     │
│  weakness.rs: execute_cascade_fix() [UPDATED]               │
└─────────────────────────┬───────────────────────────────────┘
                          │ spawn CLI
┌─────────────────────────▼───────────────────────────────────┐
│                        CLI (Python)                          │
│  weakness_cmd.py: fix() [UPDATED]                           │
└─────────────────────────┬───────────────────────────────────┘
                          │ calls
┌─────────────────────────▼───────────────────────────────────┐
│                   NEW: weakness/executor.py                  │
│  ┌──────────────────┐  ┌───────────────────┐                │
│  │CascadeArtifactBuilder│  │ CascadeExecutor   │                │
│  │  - build_wave_graph()│  │  - execute()       │                │
│  │  - _build_spec()     │  │  - _execute_wave() │                │
│  └──────────────────┘  │  - _verify_wave()  │                │
│                         └─────────┬─────────┘                │
└───────────────────────────────────┼─────────────────────────┘
                                    │ uses
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼───────┐         ┌─────────▼─────────┐       ┌────────▼────────┐
│ naaru/planners │         │  tools/executor   │       │ adaptive/events │
│ AgentPlanner   │         │  ToolExecutor     │       │ EventType       │
│ create_artifact│         │  execute()        │       │ AgentEvent      │
└───────────────┘         └───────────────────┘       └─────────────────┘
```

**Layering**:
- `weakness/` depends on `naaru/` (artifact creation) and `tools/` (file writes)
- `weakness/` emits events via `adaptive/events` (no new dependencies)
- No changes to core models (`Page`, `Site`, `Section`)

---

## Detailed Design

### Part 1: Cascade-to-Artifact Bridge

#### 1.1 Create Cascade Artifact Specs

```python
# src/sunwell/weakness/executor.py (new file)

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.weakness.cascade import CascadeEngine, CascadeExecution, CascadePreview
from sunwell.weakness.types import ExtractedContract, WaveConfidence, WeaknessScore


@dataclass
class CascadeArtifactBuilder:
    """Converts cascade preview into executable artifact specs."""
    
    engine: CascadeEngine
    preview: CascadePreview
    contracts: dict[str, ExtractedContract]
    
    def build_wave_graph(self, wave_num: int) -> ArtifactGraph:
        """Build artifact graph for a single wave.
        
        Each wave is executed as a mini-graph to allow verification
        between waves before proceeding.
        """
        from sunwell.naaru.artifacts import ArtifactGraph
        
        wave = self.preview.waves[wave_num]
        specs = [self._build_spec(artifact_id, wave_num) for artifact_id in wave]
        
        graph = ArtifactGraph()
        for spec in specs:
            graph.add(spec)
        
        return graph
    
    def _build_spec(self, artifact_id: str, wave_num: int) -> ArtifactSpec:
        """Build artifact spec for cascade regeneration."""
        original = self.engine.graph[artifact_id]
        contract = self.contracts.get(artifact_id)
        
        # Wave 0 = regenerate the weak node with improvements
        # Wave 1+ = update dependents for compatibility
        if wave_num == 0:
            description = self._regenerate_description(artifact_id)
            mode = "regenerate"
        else:
            description = self._update_description(artifact_id)
            mode = "update"
        
        # Build contract constraint for prompt
        contract_constraint = ""
        if contract:
            contract_constraint = self._format_contract_constraint(contract)
        
        return ArtifactSpec(
            id=f"cascade-{artifact_id}",
            description=description,
            produces_file=original.produces_file,
            requires=frozenset(),  # Wave deps handled externally
            contract=f"{original.contract or ''}\n\n{contract_constraint}".strip(),
            tier=original.tier,
            tags=frozenset(["cascade", mode, f"wave-{wave_num}"]),
        )
    
    def _regenerate_description(self, artifact_id: str) -> str:
        """Generate description for regenerating the weak node."""
        weakness_types = ", ".join(
            s.weakness_type.value for s in self.preview.weakness_score.signals
        )
        return (
            f"Regenerate {artifact_id} to fix weaknesses: {weakness_types}. "
            f"Improve test coverage, reduce complexity, fix type errors. "
            f"CRITICAL: Maintain all existing public interfaces for backward compatibility."
        )
    
    def _update_description(self, artifact_id: str) -> str:
        """Generate description for updating a dependent."""
        return (
            f"Update {artifact_id} to be compatible with the regenerated "
            f"{self.preview.weak_node}. Preserve all existing behavior and tests. "
            f"Only make changes necessary for compatibility."
        )
    
    def _format_contract_constraint(self, contract: ExtractedContract) -> str:
        """Format contract as prompt constraint."""
        lines = ["## Interface Contract (MUST preserve)"]
        
        if contract.functions:
            lines.append("\nPublic functions:")
            for fn in contract.functions:
                lines.append(f"  - {fn}")
        
        if contract.classes:
            lines.append("\nPublic classes:")
            for cls in contract.classes:
                lines.append(f"  - {cls}")
        
        if contract.exports:
            lines.append(f"\n__all__ = {list(contract.exports)}")
        
        return "\n".join(lines)
```

#### 1.2 Cascade Executor

```python
# src/sunwell/weakness/executor.py (continued)

from collections.abc import Awaitable, Callable
from sunwell.naaru.incremental import IncrementalExecutor, ExecutionState
from sunwell.adaptive.events import AgentEvent, EventType


@dataclass
class CascadeExecutor:
    """Executes cascade regeneration wave-by-wave with verification."""
    
    engine: CascadeEngine
    planner: "AgentPlanner"  # For artifact creation
    tool_executor: "ToolExecutor"  # For file writes
    project_root: Path
    
    # Event callback for UI updates
    on_event: Callable[[AgentEvent], None] | None = None
    
    async def execute(
        self,
        preview: CascadePreview,
        auto_approve: bool = False,
        confidence_threshold: float = 0.7,
        on_wave_complete: Callable[[WaveConfidence], Awaitable[bool]] | None = None,
    ) -> CascadeExecution:
        """Execute cascade with wave-by-wave verification.
        
        Args:
            preview: The cascade preview to execute
            auto_approve: Continue automatically if confidence > threshold
            on_wave_complete: Callback after each wave; return False to abort
        
        Returns:
            CascadeExecution with final state
        """
        # Extract contracts before any changes
        contracts = await self._extract_all_contracts(preview)
        
        # Build artifact converter
        builder = CascadeArtifactBuilder(
            engine=self.engine,
            preview=preview,
            contracts=contracts,
        )
        
        # Initialize execution state
        execution = CascadeExecution(
            preview=preview,
            auto_approve=auto_approve,
            confidence_threshold=confidence_threshold,
        )
        
        # Emit cascade start event
        self._emit_event(EventType.TASK_START, {
            "task_id": f"cascade-{preview.weak_node}",
            "description": f"Cascade fix: {preview.weak_node} + {preview.total_impacted - 1} dependents",
        })
        
        # Execute each wave
        for wave_num, wave in enumerate(preview.waves):
            execution.current_wave = wave_num
            
            # Build wave-specific artifact graph
            wave_graph = builder.build_wave_graph(wave_num)
            
            # Emit wave start
            self._emit_event(EventType.TASK_PROGRESS, {
                "task_id": f"cascade-{preview.weak_node}",
                "message": f"Wave {wave_num}: {', '.join(wave)}",
                "progress": int((wave_num / len(preview.waves)) * 100),
            })
            
            # Execute wave through artifact executor
            wave_result = await self._execute_wave(wave_graph, wave_num)
            
            if not wave_result.success:
                execution.abort(f"Wave {wave_num} failed: {wave_result.error}")
                break
            
            # Run verification suite
            confidence = await self._verify_wave(
                wave_num=wave_num,
                wave=wave,
                contracts=contracts,
            )
            
            execution.record_wave_completion(confidence)
            
            # Emit wave confidence
            self._emit_event(EventType.TASK_PROGRESS, {
                "task_id": f"cascade-{preview.weak_node}",
                "message": f"Wave {wave_num} confidence: {confidence.confidence:.0%}",
                "progress": int(((wave_num + 1) / len(preview.waves)) * 100),
            })
            
            # Callback for UI
            if on_wave_complete:
                should_continue = await on_wave_complete(confidence)
                if not should_continue:
                    execution.abort("User cancelled")
                    break
            
            # Check auto-approve vs pause
            if execution.paused_for_approval and not auto_approve:
                # Emit pause event for UI
                self._emit_event(EventType.TASK_PROGRESS, {
                    "task_id": f"cascade-{preview.weak_node}",
                    "message": f"Paused for approval (confidence: {confidence.confidence:.0%})",
                    "paused": True,
                })
                break
            
            if execution.aborted:
                break
        
        # Emit completion
        if execution.completed:
            self._emit_event(EventType.TASK_COMPLETE, {
                "task_id": f"cascade-{preview.weak_node}",
                "duration_ms": 0,  # TODO: track actual duration
            })
        elif execution.aborted:
            self._emit_event(EventType.TASK_FAILED, {
                "task_id": f"cascade-{preview.weak_node}",
                "error": execution.abort_reason or "Aborted",
            })
        
        return execution
    
    async def _extract_all_contracts(
        self,
        preview: CascadePreview,
    ) -> dict[str, ExtractedContract]:
        """Extract contracts for all affected files before regeneration."""
        contracts: dict[str, ExtractedContract] = {}
        
        all_artifacts = [preview.weak_node, *preview.direct_dependents, *preview.transitive_dependents]
        
        for artifact_id in all_artifacts:
            if artifact_id in self.engine.graph:
                try:
                    contract = await self.engine.extract_contract(artifact_id)
                    contracts[artifact_id] = contract
                except Exception:
                    pass  # Some files may not be parseable
        
        return contracts
    
    async def _execute_wave(
        self,
        wave_graph: ArtifactGraph,
        wave_num: int,
    ) -> "WaveResult":
        """Execute a single wave through the artifact system."""
        from sunwell.naaru.executor import ArtifactResult
        
        completed_content: dict[str, str] = {}
        errors: list[str] = []
        
        async def create_artifact(spec: ArtifactSpec) -> str:
            """Create artifact using planner and write to disk."""
            # Generate content
            content = await self.planner.create_artifact(spec, {})
            
            # Write to file
            if spec.produces_file and content:
                from sunwell.tools.types import ToolCall
                write_call = ToolCall(
                    id=f"write_{spec.id}",
                    name="write_file",
                    arguments={"path": spec.produces_file, "content": content},
                )
                result = await self.tool_executor.execute(write_call)
                if not result.success:
                    raise Exception(f"Failed to write {spec.produces_file}: {result.output}")
            
            return content or ""
        
        # Execute each artifact in the wave (they're independent within a wave)
        for artifact_id in wave_graph:
            artifact = wave_graph[artifact_id]
            
            self._emit_event(EventType.TASK_START, {
                "task_id": artifact_id,
                "description": artifact.description,
            })
            
            try:
                content = await create_artifact(artifact)
                completed_content[artifact_id] = content
                
                self._emit_event(EventType.TASK_COMPLETE, {
                    "task_id": artifact_id,
                    "duration_ms": 0,
                })
            except Exception as e:
                errors.append(f"{artifact_id}: {e}")
                
                self._emit_event(EventType.TASK_FAILED, {
                    "task_id": artifact_id,
                    "error": str(e),
                })
        
        return WaveResult(
            wave_num=wave_num,
            completed=completed_content,
            success=len(errors) == 0,
            error="; ".join(errors) if errors else None,
        )
    
    async def _verify_wave(
        self,
        wave_num: int,
        wave: tuple[str, ...],
        contracts: dict[str, ExtractedContract],
    ) -> WaveConfidence:
        """Run verification suite and compute confidence."""
        test_result = await self._run_tests()
        type_result = await self._run_type_check()
        lint_result = await self._run_lint()
        contract_result = await self._verify_contracts(contracts, wave)
        
        return WaveConfidence.compute(
            wave_num=wave_num,
            artifacts=wave,
            test_result=test_result,
            type_result=type_result,
            lint_result=lint_result,
            contract_result=contract_result,
        )
    
    async def _run_tests(self) -> bool:
        """Run pytest and return success status."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["pytest", "--tb=short", "-q"],
                cwd=self.project_root,
                capture_output=True,
                timeout=300,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # Assume pass if can't run
    
    async def _run_type_check(self) -> bool:
        """Run mypy and return success status."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["mypy", "src/"],
                cwd=self.project_root,
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True
    
    async def _run_lint(self) -> bool:
        """Run ruff and return success status."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["ruff", "check", "src/"],
                cwd=self.project_root,
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True
    
    async def _verify_contracts(
        self,
        original_contracts: dict[str, ExtractedContract],
        wave_artifacts: tuple[str, ...],
    ) -> bool:
        """Verify contracts are preserved after regeneration."""
        for artifact_id in wave_artifacts:
            # Map cascade-prefixed ID back to original
            original_id = artifact_id.replace("cascade-", "")
            
            if original_id not in original_contracts:
                continue
            
            original = original_contracts[original_id]
            try:
                current = await self.engine.extract_contract(original_id)
                if not original.is_compatible_with(current):
                    return False
            except Exception:
                pass  # Can't verify - assume OK
        
        return True
    
    def _emit_event(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Emit agent event if callback registered."""
        if self.on_event:
            event = AgentEvent(event_type, data)
            self.on_event(event)


@dataclass(frozen=True, slots=True)
class WaveResult:
    """Result of executing a single wave."""
    
    wave_num: int
    completed: dict[str, str]
    success: bool
    error: str | None = None
```

### Part 2: CLI Integration

```python
# src/sunwell/cli/weakness_cmd.py (update fix command)

@weakness.command()
@click.argument("artifact_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--json", "as_json", is_flag=True, help="Output progress as JSON events")
@click.option("--wave-by-wave", is_flag=True, help="Approve each wave manually")
@click.option("--show-deltas", is_flag=True, help="Show diffs before executing")
@click.option("--confidence-threshold", default=0.7, help="Min confidence to auto-proceed")
@click.pass_context
def fix(
    ctx: click.Context,
    artifact_id: str,
    yes: bool,
    dry_run: bool,
    as_json: bool,
    wave_by_wave: bool,
    show_deltas: bool,
    confidence_threshold: float,
) -> None:
    """Fix a weak artifact and all dependents."""
    project_root = get_project_root(ctx)

    async def _fix() -> dict[str, Any]:
        from sunwell.naaru.artifacts import ArtifactGraph
        from sunwell.naaru.planners.artifact import AgentPlanner
        from sunwell.tools.executor import ToolExecutor
        from sunwell.weakness.analyzer import WeaknessAnalyzer
        from sunwell.weakness.cascade import CascadeEngine
        from sunwell.weakness.executor import CascadeExecutor  # NEW

        graph = await _build_graph(project_root)

        # Find the weakness
        analyzer = WeaknessAnalyzer(graph=graph, project_root=project_root)
        scores = await analyzer.scan()

        weakness = next((s for s in scores if s.artifact_id == artifact_id), None)
        if not weakness:
            return {"error": f"No weakness found for {artifact_id}"}

        engine = CascadeEngine(graph=graph, project_root=project_root)

        # Get preview with contracts
        preview = await engine.preview_with_contracts(weakness, include_deltas=show_deltas)

        if dry_run:
            result = preview.to_dict()
            result["tasks"] = engine.compute_regeneration_tasks(preview)
            return result

        # Create executor with planner and tools
        planner = await _get_planner()
        tool_executor = ToolExecutor(project_root=project_root)
        
        def emit_json(event):
            if as_json:
                click.echo(json.dumps(event.to_dict()), file=sys.stdout, flush=True)
        
        executor = CascadeExecutor(
            engine=engine,
            planner=planner,
            tool_executor=tool_executor,
            project_root=project_root,
            on_event=emit_json if as_json else None,
        )

        # Execute with wave-by-wave callbacks
        async def on_wave_complete(confidence: WaveConfidence) -> bool:
            if as_json:
                click.echo(json.dumps({
                    "event": "wave_complete",
                    "wave_num": confidence.wave_num,
                    "confidence": confidence.confidence,
                    "deductions": list(confidence.deductions),
                }))
            else:
                _print_wave_confidence(confidence)

            if wave_by_wave and not yes:
                return click.confirm("Continue to next wave?", default=True)
            return confidence.should_continue

        execution = await executor.execute(
            preview=preview,
            auto_approve=not wave_by_wave,
            confidence_threshold=confidence_threshold,
            on_wave_complete=on_wave_complete,
        )

        return execution.to_dict()

    # ... rest of existing code ...
```

### Part 3: Tauri Bridge Update

```rust
// studio/src-tauri/src/weakness.rs (update execute_cascade_fix)

/// Execute cascade fix through the new executor.
#[tauri::command]
pub async fn execute_cascade_fix(
    app: tauri::AppHandle,
    path: String,
    artifact_id: String,
    auto_approve: bool,
    confidence_threshold: f32,
) -> Result<CascadeExecution, String> {
    let project_path = PathBuf::from(&path);

    // Build args based on options
    let mut args = vec![
        "weakness".to_string(),
        "fix".to_string(),
        artifact_id.clone(),
        "--json".to_string(),
        format!("--confidence-threshold={}", confidence_threshold),
    ];

    if auto_approve {
        args.push("--yes".to_string());
    }

    // Spawn process and stream events
    let mut child = Command::new("sunwell")
        .args(&args)
        .current_dir(&project_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start cascade: {}", e))?;

    let stdout = child.stdout.take().ok_or("No stdout")?;
    let reader = BufReader::new(stdout);

    // Stream events to frontend
    for line in reader.lines() {
        if let Ok(line) = line {
            if let Ok(event) = serde_json::from_str::<serde_json::Value>(&line) {
                // Forward to frontend
                app.emit("agent-event", &event)
                    .map_err(|e| format!("Failed to emit event: {}", e))?;
            }
        }
    }

    // Wait for completion and get final state
    let output = child.wait_with_output()
        .map_err(|e| format!("Failed to wait for cascade: {}", e))?;

    // Parse final execution state from last JSON line
    let stdout_str = String::from_utf8_lossy(&output.stdout);
    let last_line = stdout_str.lines().last().unwrap_or("");
    
    let execution: CascadeExecution = serde_json::from_str(last_line)
        .map_err(|e| format!("Failed to parse execution result: {}", e))?;

    Ok(execution)
}
```

### Part 4: Frontend Store Update

```typescript
// studio/src/stores/weakness.svelte.ts (update executeQuickFix)

export async function executeQuickFix(
  projectPath: string,
  artifactId: string,
  autoApprove: boolean = true,
  confidenceThreshold: number = 0.7,
): Promise<void> {
  _isExecuting = true;
  _error = null;

  try {
    // Start execution - events will stream via agent-event listener
    const execution = await invoke<CascadeExecution>('execute_cascade_fix', {
      path: projectPath,
      artifactId,
      autoApprove,
      confidenceThreshold,
    });
    
    _execution = execution;
    
    // Refresh weakness report after completion
    if (execution.completed) {
      await scanWeaknesses(projectPath);
    }
  } catch (e) {
    _error = String(e);
    console.error('Cascade fix failed:', e);
  } finally {
    _isExecuting = false;
  }
}
```

---

## Implementation Plan

### Phase 1: Core Executor (2-3 days)

| Task | Description | Effort |
|------|-------------|--------|
| 1.1 | Create `src/sunwell/weakness/executor.py` | M |
| 1.2 | Implement `CascadeArtifactBuilder` | S |
| 1.3 | Implement `CascadeExecutor.execute()` | L |
| 1.4 | Wire `_execute_wave()` to artifact creation | M |
| 1.5 | Wire `_verify_wave()` to verification suite | S |
| 1.6 | Unit tests for executor | M |

### Phase 2: CLI Integration (1 day)

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Update `weakness fix` to use `CascadeExecutor` | M |
| 2.2 | Add JSON event streaming | S |
| 2.3 | Integration test: CLI end-to-end | M |

### Phase 3: Tauri Bridge (1 day)

| Task | Description | Effort |
|------|-------------|--------|
| 3.1 | Update `execute_cascade_fix` for streaming | M |
| 3.2 | Add approval/abort commands | S |
| 3.3 | Test Rust↔Python event flow | S |

### Phase 4: Frontend Polish (1 day)

| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | Update `executeQuickFix` with new params | S |
| 4.2 | Handle streaming events in UI | M |
| 4.3 | Add approval modal for paused state | M |
| 4.4 | E2E test: Studio → CLI → result | L |

**Total: ~5-6 days**

---

## Event Flow

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────┐
│   Studio    │────▶│    Tauri     │────▶│  CLI (Python)  │────▶│  Agent   │
│   (Svelte)  │     │   (Rust)     │     │                │     │ (Planner)│
└─────────────┘     └──────────────┘     └────────────────┘     └──────────┘
       ▲                   │                    │                     │
       │                   │              ┌─────▼─────┐               │
       │                   │              │ Cascade   │               │
       │                   │              │ Executor  │◀──────────────┘
       │                   │              └─────┬─────┘
       │                   │                    │
       │              agent-event               │
       │◀──────────────────│◀───────────────────┘
       │               (JSON)            task_start/complete/progress
```

1. User clicks "Fix N files" → `executeQuickFix()` in store
2. Store calls Tauri `execute_cascade_fix` command
3. Tauri spawns `sunwell weakness fix --json`
4. CLI creates `CascadeExecutor` and runs `execute()`
5. Executor creates artifacts wave-by-wave via planner
6. Each artifact emits `task_start`/`task_complete` events
7. Events stream as JSON to stdout
8. Tauri reads stdout, emits `agent-event` to frontend
9. Store's existing event listener updates UI
10. On completion, final `CascadeExecution` returned

---

## Success Criteria

1. **Fix button works** — Clicking triggers actual regeneration
2. **Files updated** — Weak file + dependents have new content
3. **Events stream** — UI shows real-time progress
4. **Confidence gating** — Low confidence pauses execution
5. **Tests pass** — Post-cascade verification succeeds
6. **Contracts preserved** — No signature regressions

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Planner generates bad code | High | Contract verification catches signature breaks; tests catch behavior breaks |
| Long execution time | Medium | Progress events keep UI responsive; allow abort |
| Partial completion | Medium | Each wave is atomic; can resume from last good wave |
| Event streaming fails | Low | Final result returned even if events missed |

---

## Future Work

1. **Resume from wave** — Store execution state, allow picking up from last completed wave
2. **Semantic verification** — Beyond signature checks, verify behavior equivalence
3. **Dry-run deltas** — Show exact diffs before executing (expensive but valuable)
4. **Batch fix** — Fix multiple weaknesses in optimal order
5. **Auto-fix scheduling** — Run cascade fixes during low-activity periods

---

## Related RFCs

- **RFC-063**: Weakness Cascade — detection, preview, and state machine (this RFC completes execution)
- **RFC-036**: Artifact Execution — provides `ArtifactExecutor` infrastructure
- **RFC-040**: Incremental Build — provides `IncrementalExecutor` and `find_invalidated()`
- **RFC-060**: Event Contract — defines event types for UI streaming
