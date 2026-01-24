# RFC-123: Convergence Loops — Self-Stabilizing Code Generation

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-042 (Validation Gates), RFC-119 (Event Bus)

## Summary

Enable Sunwell to loop until code stabilizes: after every file write, run gates (lint, types, tests), fix issues, repeat until all pass. This transforms gates from one-shot checkpoints into continuous convergence loops.

## Motivation

### Problem

Current gate execution is **checkpoint-based**:

```
Plan → Task 1 → Task 2 → Task 3 → GATE (lint/type) → Fix once → Continue
```

This has limitations:
- Gates run at predefined points, not after every write
- Fix attempts are limited (max 3), then escalate
- No feedback loop: fix may introduce new errors
- Agent can't "keep trying" until clean

### User Story

> "I want Sunwell to keep iterating until my code passes lint, types, and tests — like a human developer would. Don't stop at 3 attempts; loop until stable or explicitly give up."

### Inspiration

**Hot Module Reloading (HMR)**: Frontend devs get instant feedback on every save. Code either compiles or shows errors immediately. Developers iterate until stable.

**Continuous Integration**: CI runs all checks on every push. If anything fails, you fix and push again. Repeat until green.

**Control Systems**: Feedback loops drive toward equilibrium. Measure → Compare → Adjust → Repeat.

## Goals

1. **Reactive validation**: Run gates after every file write, not just at checkpoints
2. **Convergence guarantee**: Loop until all gates pass or budget exhausted
3. **Parallel checks**: Run lint, types, tests concurrently for speed
4. **Observable progress**: Stream convergence status to Studio
5. **Configurable scope**: User chooses which gates participate

## Non-Goals

- Replace existing gate system (convergence is opt-in layer on top)
- Infinite loops (hard limits on iterations and tokens)
- Auto-fix without agent involvement (agent does the fixing, not tools)

---

## Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CONVERGENCE LOOP                                │
│                                                                      │
│   ┌─────────────┐      ┌─────────────────────────────────────────┐  │
│   │ ToolExecutor│      │           ConvergenceLoop               │  │
│   │             │      │                                         │  │
│   │ write_file  │─────►│  1. Collect changed files               │  │
│   │ edit_file   │ hook │  2. Run gates in parallel               │  │
│   │             │      │  3. If all pass → STABLE                │  │
│   └─────────────┘      │  4. If fail → Agent fixes → goto 1      │  │
│                        │  5. If max iterations → ESCALATE        │  │
│                        └─────────────────────────────────────────┘  │
│                                       │                              │
│                                       ▼                              │
│                        ┌─────────────────────────────────────────┐  │
│                        │         Parallel Gate Runner            │  │
│                        │                                         │  │
│                        │  ┌───────┐ ┌───────┐ ┌───────┐         │  │
│                        │  │ LINT  │ │ TYPE  │ │ TEST  │         │  │
│                        │  │ ruff  │ │ ty    │ │pytest │         │  │
│                        │  └───────┘ └───────┘ └───────┘         │  │
│                        └─────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Model

```python
# sunwell/convergence/types.py

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sunwell.agent.gates import GateType


class ConvergenceStatus(Enum):
    """Status of convergence loop."""
    RUNNING = "running"
    STABLE = "stable"        # All gates pass
    ESCALATED = "escalated"  # Max iterations, needs human
    TIMEOUT = "timeout"      # Time limit exceeded
    CANCELLED = "cancelled"  # User cancelled


@dataclass(frozen=True, slots=True)
class GateCheckResult:
    """Result of a single gate check."""
    gate: GateType
    passed: bool
    errors: tuple[str, ...] = ()
    duration_ms: int = 0
    
    @property
    def error_count(self) -> int:
        return len(self.errors)


@dataclass(frozen=True, slots=True)
class ConvergenceIteration:
    """One iteration of the convergence loop."""
    iteration: int
    gate_results: tuple[GateCheckResult, ...]
    files_changed: tuple[Path, ...]
    duration_ms: int
    
    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.gate_results)
    
    @property
    def total_errors(self) -> int:
        return sum(r.error_count for r in self.gate_results)


@dataclass
class ConvergenceResult:
    """Final result of convergence loop."""
    status: ConvergenceStatus
    iterations: list[ConvergenceIteration] = field(default_factory=list)
    total_duration_ms: int = 0
    tokens_used: int = 0
    
    @property
    def stable(self) -> bool:
        return self.status == ConvergenceStatus.STABLE
    
    @property
    def iteration_count(self) -> int:
        return len(self.iterations)


@dataclass
class ConvergenceConfig:
    """Configuration for convergence behavior."""
    
    # Limits
    max_iterations: int = 5
    max_tokens: int = 50_000
    timeout_seconds: int = 300  # 5 minutes
    
    # Which gates to run
    enabled_gates: frozenset[GateType] = field(default_factory=lambda: frozenset({
        GateType.LINT,
        GateType.TYPE,
    }))
    
    # Optional gates (run but don't block on failure)
    advisory_gates: frozenset[GateType] = field(default_factory=frozenset)
    
    # Debounce: wait for writes to settle before checking
    debounce_ms: int = 200
    
    # Escalation
    escalate_after_same_error: int = 2  # If same error persists N times
```

### Core Implementation

```python
# sunwell/convergence/loop.py

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.events import AgentEvent, EventType
from sunwell.agent.gates import GateType
from sunwell.convergence.types import (
    ConvergenceConfig,
    ConvergenceIteration,
    ConvergenceResult,
    ConvergenceStatus,
    GateCheckResult,
)

if TYPE_CHECKING:
    from sunwell.agent.core import Agent


@dataclass
class ConvergenceLoop:
    """Self-stabilizing code generation loop.
    
    After file writes, runs validation gates in parallel.
    If any fail, agent fixes and loop continues until stable.
    
    Example:
        >>> loop = ConvergenceLoop(config=ConvergenceConfig())
        >>> async for event in loop.run(agent, changed_files):
        ...     print(event)  # Progress events
        >>> print(loop.result.status)  # STABLE or ESCALATED
    """
    
    config: ConvergenceConfig = field(default_factory=ConvergenceConfig)
    result: ConvergenceResult | None = field(default=None, init=False)
    
    # Internal state
    _start_time: float = field(default=0.0, init=False)
    _tokens_used: int = field(default=0, init=False)
    _error_history: dict[str, int] = field(default_factory=dict, init=False)
    
    async def run(
        self,
        agent: Agent,
        initial_files: list[Path],
    ) -> AsyncIterator[AgentEvent]:
        """Run convergence loop until stable or limits hit.
        
        Args:
            agent: Agent instance for fixes
            initial_files: Files to validate initially
            
        Yields:
            AgentEvent for progress tracking
        """
        self._start_time = time.monotonic()
        self._tokens_used = 0
        iterations: list[ConvergenceIteration] = []
        changed_files = set(initial_files)
        
        yield self._event("convergence_start", {
            "files": [str(f) for f in initial_files],
            "gates": [g.value for g in self.config.enabled_gates],
            "max_iterations": self.config.max_iterations,
        })
        
        for iteration_num in range(1, self.config.max_iterations + 1):
            # Check timeout
            if self._check_timeout():
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.TIMEOUT,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                yield self._event("convergence_timeout", {
                    "iterations": iteration_num - 1,
                })
                return
            
            # Check token budget
            if self._tokens_used >= self.config.max_tokens:
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.ESCALATED,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                yield self._event("convergence_budget_exceeded", {
                    "tokens_used": self._tokens_used,
                    "max_tokens": self.config.max_tokens,
                })
                return
            
            yield self._event("convergence_iteration_start", {
                "iteration": iteration_num,
                "files": [str(f) for f in changed_files],
            })
            
            # Run gates in parallel
            iter_start = time.monotonic()
            gate_results = await self._run_gates_parallel(list(changed_files))
            
            iteration = ConvergenceIteration(
                iteration=iteration_num,
                gate_results=tuple(gate_results),
                files_changed=tuple(changed_files),
                duration_ms=int((time.monotonic() - iter_start) * 1000),
            )
            iterations.append(iteration)
            
            yield self._event("convergence_iteration_complete", {
                "iteration": iteration_num,
                "all_passed": iteration.all_passed,
                "total_errors": iteration.total_errors,
                "gate_results": [
                    {"gate": r.gate.value, "passed": r.passed, "errors": r.error_count}
                    for r in gate_results
                ],
            })
            
            # Check if stable
            if iteration.all_passed:
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.STABLE,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                yield self._event("convergence_stable", {
                    "iterations": iteration_num,
                    "duration_ms": self._elapsed_ms(),
                })
                return
            
            # Check for stuck errors (same error repeated)
            if self._check_stuck_errors(gate_results):
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.ESCALATED,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                yield self._event("convergence_stuck", {
                    "iterations": iteration_num,
                    "repeated_errors": list(self._get_stuck_errors()),
                })
                return
            
            # Collect errors for fixing
            all_errors = [
                (r.gate, err) 
                for r in gate_results 
                if not r.passed
                for err in r.errors
            ]
            
            yield self._event("convergence_fixing", {
                "iteration": iteration_num,
                "error_count": len(all_errors),
            })
            
            # Agent fixes errors
            changed_files.clear()
            for gate_type, error in all_errors:
                async for fix_event in agent.fix_error(gate_type, error):
                    yield fix_event
                    
                    # Track files changed by fix
                    if fix_event.type == EventType.TOOL_RESULT:
                        if fix_event.data.get("tool") in ("write_file", "edit_file"):
                            path = Path(fix_event.data.get("path", ""))
                            if path.suffix:  # Valid file
                                changed_files.add(path)
                    
                    # Track tokens
                    if "tokens" in fix_event.data:
                        self._tokens_used += fix_event.data["tokens"]
            
            # Debounce before next iteration
            await asyncio.sleep(self.config.debounce_ms / 1000)
        
        # Max iterations reached
        self.result = ConvergenceResult(
            status=ConvergenceStatus.ESCALATED,
            iterations=iterations,
            total_duration_ms=self._elapsed_ms(),
            tokens_used=self._tokens_used,
        )
        yield self._event("convergence_max_iterations", {
            "iterations": self.config.max_iterations,
        })
    
    async def _run_gates_parallel(
        self,
        files: list[Path],
    ) -> list[GateCheckResult]:
        """Run all enabled gates in parallel."""
        tasks = [
            self._run_single_gate(gate, files)
            for gate in self.config.enabled_gates
        ]
        return await asyncio.gather(*tasks)
    
    async def _run_single_gate(
        self,
        gate: GateType,
        files: list[Path],
    ) -> GateCheckResult:
        """Run a single gate check."""
        start = time.monotonic()
        
        match gate:
            case GateType.LINT:
                passed, errors = await self._check_lint(files)
            case GateType.TYPE:
                passed, errors = await self._check_types(files)
            case GateType.TEST:
                passed, errors = await self._check_tests(files)
            case GateType.SYNTAX:
                passed, errors = await self._check_syntax(files)
            case _:
                passed, errors = True, []
        
        duration = int((time.monotonic() - start) * 1000)
        
        # Track error frequency for stuck detection
        for err in errors:
            err_key = f"{gate.value}:{err[:100]}"
            self._error_history[err_key] = self._error_history.get(err_key, 0) + 1
        
        return GateCheckResult(
            gate=gate,
            passed=passed,
            errors=tuple(errors),
            duration_ms=duration,
        )
    
    async def _check_lint(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Run ruff on files."""
        import subprocess
        
        if not files:
            return True, []
        
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=concise", *[str(f) for f in files]],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, []
            
            errors = [
                line.strip() 
                for line in result.stdout.splitlines() 
                if line.strip()
            ]
            return False, errors
        except Exception as e:
            return False, [str(e)]
    
    async def _check_types(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Run ty (or mypy) on files."""
        import subprocess
        
        if not files:
            return True, []
        
        try:
            # Try ty first (faster)
            result = subprocess.run(
                ["ty", "check", *[str(f) for f in files]],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return True, []
            
            errors = [
                line.strip() 
                for line in result.stdout.splitlines() 
                if line.strip() and "error" in line.lower()
            ]
            return False, errors
        except FileNotFoundError:
            # Fall back to mypy
            try:
                result = subprocess.run(
                    ["mypy", "--no-error-summary", *[str(f) for f in files]],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    return True, []
                
                errors = [
                    line.strip() 
                    for line in result.stdout.splitlines() 
                    if line.strip() and "error" in line.lower()
                ]
                return False, errors
            except Exception as e:
                return False, [str(e)]
        except Exception as e:
            return False, [str(e)]
    
    async def _check_tests(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Run pytest on related test files."""
        import subprocess
        
        # Find related test files
        test_files = [
            f for f in files 
            if "test" in f.name.lower() or f.parent.name == "tests"
        ]
        
        if not test_files:
            return True, []
        
        try:
            result = subprocess.run(
                ["pytest", "-q", "--tb=line", *[str(f) for f in test_files]],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True, []
            
            errors = [
                line.strip() 
                for line in result.stdout.splitlines() 
                if "FAILED" in line or "ERROR" in line
            ]
            return False, errors
        except Exception as e:
            return False, [str(e)]
    
    async def _check_syntax(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Check Python syntax."""
        import py_compile
        
        errors = []
        for f in files:
            if f.suffix == ".py":
                try:
                    py_compile.compile(str(f), doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(str(e))
        
        return len(errors) == 0, errors
    
    def _check_timeout(self) -> bool:
        """Check if timeout exceeded."""
        return self._elapsed_ms() > self.config.timeout_seconds * 1000
    
    def _elapsed_ms(self) -> int:
        """Elapsed time in milliseconds."""
        return int((time.monotonic() - self._start_time) * 1000)
    
    def _check_stuck_errors(self, results: list[GateCheckResult]) -> bool:
        """Check if any error has repeated too many times."""
        for r in results:
            for err in r.errors:
                err_key = f"{r.gate.value}:{err[:100]}"
                if self._error_history.get(err_key, 0) >= self.config.escalate_after_same_error:
                    return True
        return False
    
    def _get_stuck_errors(self) -> list[str]:
        """Get errors that have repeated too many times."""
        return [
            key for key, count in self._error_history.items()
            if count >= self.config.escalate_after_same_error
        ]
    
    def _event(self, event_type: str, data: dict) -> AgentEvent:
        """Create an agent event."""
        return AgentEvent(type=EventType(event_type), data=data)
```

### Hook Integration

Wire convergence into `ToolExecutor`:

```python
# sunwell/tools/executor.py (additions)

@dataclass
class ToolExecutor:
    # ... existing fields ...
    
    # Convergence hook
    on_file_write: Callable[[Path, str], Awaitable[None]] | None = None
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        result = await handler(tool_call.arguments)
        
        # Fire hook after successful file writes
        if result.success and self.on_file_write:
            if tool_call.name == "write_file":
                path = Path(tool_call.arguments["path"])
                await self.on_file_write(path, tool_call.arguments.get("content", ""))
            elif tool_call.name == "edit_file":
                path = Path(tool_call.arguments["path"])
                await self.on_file_write(path, "")  # Content already in file
        
        return result
```

### Agent Integration

Add convergence mode to agent runs:

```python
# sunwell/agent/request.py (additions)

@dataclass
class RunOptions:
    # ... existing fields ...
    
    # Convergence mode
    converge: bool = False
    """Enable convergence loops after file writes."""
    
    convergence_config: ConvergenceConfig | None = None
    """Custom convergence configuration."""
```

```python
# sunwell/agent/core.py (additions)

async def _execute_with_convergence(
    self,
    options: RunOptions,
) -> AsyncIterator[AgentEvent]:
    """Execute with convergence loops enabled."""
    
    config = options.convergence_config or ConvergenceConfig()
    loop = ConvergenceLoop(config=config)
    
    # Track files written during execution
    written_files: list[Path] = []
    
    async def on_write(path: Path, content: str) -> None:
        written_files.append(path)
    
    # Set up hook
    self.tool_executor.on_file_write = on_write
    
    try:
        # Execute tasks normally
        async for event in self._execute_with_gates(options):
            yield event
            
            # After each task batch, run convergence if files changed
            if event.type == EventType.TASK_COMPLETE and written_files:
                async for conv_event in loop.run(self, written_files):
                    yield conv_event
                
                if loop.result and not loop.result.stable:
                    # Escalate if convergence failed
                    yield AgentEvent(
                        EventType.ESCALATE,
                        {"reason": f"Convergence failed: {loop.result.status.value}"},
                    )
                    return
                
                written_files.clear()
    finally:
        self.tool_executor.on_file_write = None
```

### Event Types

Add new events for convergence:

```python
# sunwell/agent/events.py (additions)

class EventType(Enum):
    # ... existing types ...
    
    # Convergence events
    CONVERGENCE_START = "convergence_start"
    """Starting convergence loop."""
    
    CONVERGENCE_ITERATION_START = "convergence_iteration_start"
    """Starting a convergence iteration."""
    
    CONVERGENCE_ITERATION_COMPLETE = "convergence_iteration_complete"
    """Completed a convergence iteration."""
    
    CONVERGENCE_FIXING = "convergence_fixing"
    """Agent is fixing errors."""
    
    CONVERGENCE_STABLE = "convergence_stable"
    """All gates pass, code is stable."""
    
    CONVERGENCE_TIMEOUT = "convergence_timeout"
    """Convergence timed out."""
    
    CONVERGENCE_STUCK = "convergence_stuck"
    """Same error keeps recurring."""
    
    CONVERGENCE_MAX_ITERATIONS = "convergence_max_iterations"
    """Max iterations reached without stability."""
    
    CONVERGENCE_BUDGET_EXCEEDED = "convergence_budget_exceeded"
    """Token budget exhausted."""
```

### CLI Integration

```python
# sunwell/cli/main.py (additions)

@click.option(
    "--converge/--no-converge",
    default=False,
    help="Enable convergence loops (iterate until lint/types pass)",
)
@click.option(
    "--converge-gates",
    default="lint,type",
    help="Gates to include in convergence (comma-separated: lint,type,test)",
)
@click.option(
    "--converge-max",
    default=5,
    type=int,
    help="Maximum convergence iterations",
)
def run(goal: str, converge: bool, converge_gates: str, converge_max: int, ...):
    """Run agent with optional convergence."""
    
    config = None
    if converge:
        gates = frozenset(GateType(g) for g in converge_gates.split(","))
        config = ConvergenceConfig(
            enabled_gates=gates,
            max_iterations=converge_max,
        )
    
    options = RunOptions(
        converge=converge,
        convergence_config=config,
        ...
    )
```

### Studio Integration

Display convergence progress in Observatory:

```svelte
<!-- studio/src/components/observatory/ConvergenceProgress.svelte -->

<script lang="ts">
  import { getAgentState } from '$lib/stores/agent.svelte';
  
  const agent = getAgentState();
  
  $: convergence = agent.convergence;
  $: iterations = convergence?.iterations ?? [];
  $: currentIteration = iterations[iterations.length - 1];
</script>

{#if convergence}
  <div class="convergence-panel">
    <h3>
      🔄 Convergence Loop
      {#if convergence.status === 'stable'}
        <span class="badge success">✓ Stable</span>
      {:else if convergence.status === 'running'}
        <span class="badge running">Iteration {iterations.length}</span>
      {:else}
        <span class="badge warning">{convergence.status}</span>
      {/if}
    </h3>
    
    <div class="iterations">
      {#each iterations as iter}
        <div class="iteration" class:passed={iter.all_passed}>
          <span class="num">#{iter.iteration}</span>
          
          <div class="gates">
            {#each iter.gate_results as gate}
              <span class="gate" class:passed={gate.passed} class:failed={!gate.passed}>
                {gate.gate}
                {#if !gate.passed}
                  ({gate.errors} errors)
                {/if}
              </span>
            {/each}
          </div>
          
          <span class="duration">{iter.duration_ms}ms</span>
        </div>
      {/each}
    </div>
    
    {#if convergence.status === 'stable'}
      <p class="success-message">
        ✅ All gates pass after {iterations.length} iteration(s)
      </p>
    {/if}
  </div>
{/if}
```

---

## Migration Plan

### Phase 1: Core Types & Loop (1 day)

| Task | File | Status |
|------|------|--------|
| Add convergence types | `src/sunwell/convergence/types.py` (new) | ⬜ |
| Implement ConvergenceLoop | `src/sunwell/convergence/loop.py` (new) | ⬜ |
| Add convergence events | `src/sunwell/agent/events.py` | ⬜ |
| Unit tests | `tests/unit/test_convergence.py` | ⬜ |

### Phase 2: Tool Hooks (0.5 days)

| Task | File | Status |
|------|------|--------|
| Add `on_file_write` hook | `src/sunwell/tools/executor.py` | ⬜ |
| Wire hook in execution | `src/sunwell/agent/core.py` | ⬜ |
| Integration tests | `tests/integration/test_convergence.py` | ⬜ |

### Phase 3: CLI & Studio (1 day)

| Task | File | Status |
|------|------|--------|
| Add CLI flags | `src/sunwell/cli/main.py` | ⬜ |
| Add Studio component | `studio/src/components/observatory/ConvergenceProgress.svelte` | ⬜ |
| E2E test | `tests/e2e/test_convergence_cli.py` | ⬜ |

---

## Testing

```python
# tests/unit/test_convergence.py

import pytest
from sunwell.convergence.loop import ConvergenceLoop
from sunwell.convergence.types import ConvergenceConfig, ConvergenceStatus, GateType


class TestConvergenceLoop:
    """Convergence loop unit tests."""
    
    async def test_stable_on_first_try(self, mock_agent):
        """Should return STABLE if all gates pass immediately."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=5,
        )
        loop = ConvergenceLoop(config=config)
        
        # Mock: lint passes
        loop._check_lint = AsyncMock(return_value=(True, []))
        
        events = [e async for e in loop.run(mock_agent, [Path("test.py")])]
        
        assert loop.result.status == ConvergenceStatus.STABLE
        assert loop.result.iteration_count == 1
    
    async def test_converges_after_fix(self, mock_agent):
        """Should converge after agent fixes errors."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=5,
        )
        loop = ConvergenceLoop(config=config)
        
        # Mock: fail first, pass second
        call_count = 0
        async def mock_lint(files):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, ["E501 line too long"]
            return True, []
        
        loop._check_lint = mock_lint
        
        events = [e async for e in loop.run(mock_agent, [Path("test.py")])]
        
        assert loop.result.status == ConvergenceStatus.STABLE
        assert loop.result.iteration_count == 2
    
    async def test_escalates_on_max_iterations(self, mock_agent):
        """Should escalate if max iterations reached."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=3,
        )
        loop = ConvergenceLoop(config=config)
        
        # Mock: always fail
        loop._check_lint = AsyncMock(return_value=(False, ["persistent error"]))
        
        events = [e async for e in loop.run(mock_agent, [Path("test.py")])]
        
        assert loop.result.status == ConvergenceStatus.ESCALATED
        assert loop.result.iteration_count == 3
    
    async def test_detects_stuck_errors(self, mock_agent):
        """Should escalate if same error repeats."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=10,
            escalate_after_same_error=2,
        )
        loop = ConvergenceLoop(config=config)
        
        # Mock: same error every time
        loop._check_lint = AsyncMock(return_value=(False, ["E501 exact same error"]))
        
        events = [e async for e in loop.run(mock_agent, [Path("test.py")])]
        
        assert loop.result.status == ConvergenceStatus.ESCALATED
        assert "stuck" in [e.type.value for e in events]
    
    async def test_parallel_gate_execution(self, mock_agent):
        """Should run multiple gates in parallel."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT, GateType.TYPE}),
            max_iterations=1,
        )
        loop = ConvergenceLoop(config=config)
        
        # Mock both gates
        loop._check_lint = AsyncMock(return_value=(True, []))
        loop._check_types = AsyncMock(return_value=(True, []))
        
        events = [e async for e in loop.run(mock_agent, [Path("test.py")])]
        
        assert loop.result.status == ConvergenceStatus.STABLE
        # Both gates should have been called
        assert loop._check_lint.called
        assert loop._check_types.called
    
    async def test_respects_timeout(self, mock_agent):
        """Should timeout if taking too long."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=100,
            timeout_seconds=1,
        )
        loop = ConvergenceLoop(config=config)
        
        # Mock: slow check
        async def slow_lint(files):
            await asyncio.sleep(2)  # Longer than timeout
            return True, []
        
        loop._check_lint = slow_lint
        
        events = [e async for e in loop.run(mock_agent, [Path("test.py")])]
        
        assert loop.result.status == ConvergenceStatus.TIMEOUT
```

---

## Security Considerations

### Resource Limits

Convergence loops could consume excessive resources. Mitigations:

| Risk | Mitigation |
|------|------------|
| Infinite loops | Hard `max_iterations` cap (default: 5) |
| Token exhaustion | `max_tokens` budget (default: 50k) |
| Time exhaustion | `timeout_seconds` (default: 300s) |
| Stuck errors | `escalate_after_same_error` (default: 2) |

### Subprocess Safety

Gate checks run subprocesses (`ruff`, `ty`, `pytest`). Safeguards:
- 30-60 second timeouts per check
- Only run on files within workspace
- No arbitrary command execution (fixed commands only)

---

## Alternatives Considered

### 1. Async File Watcher

Use `watchfiles` to detect changes externally, trigger convergence.

**Rejected**: Race conditions between agent writes and watcher detection. Hook-based approach is synchronous and predictable.

### 2. Gate-Level Retries Only

Keep convergence within existing gate system (retry at gate, not loop).

**Rejected**: Can't handle cross-gate interactions (lint fix breaks types). Need holistic loop.

### 3. Full Rebuild Each Iteration

Re-run all gates on all files each iteration.

**Rejected**: Too slow. Incremental (only changed files) is better.

---

## Success Metrics

- **Convergence rate**: >80% of runs reach STABLE within 3 iterations
- **Average iterations**: <2 for lint-only, <3 for lint+types
- **Escalation rate**: <10% of convergence attempts
- **Time overhead**: <30% increase vs. non-convergent runs

---

## Open Questions

1. **Test convergence**: Should `pytest` be in default gates? (Slower, but more complete)
2. **Doc convergence**: Should docs rebuild be a gate? (Sphinx/mkdocs)
3. **Cross-file dependencies**: How to handle when fixing A breaks B?

---

## References

- RFC-042: Adaptive Agent (Validation Gates)
- RFC-047: Deep Verification (Semantic gates)
- RFC-119: Unified Event Bus (Event streaming)
- RFC-120: Observability & Debugging (Progress tracking)
