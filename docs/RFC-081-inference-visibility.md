# RFC-081: Inference Visibility — Real-Time Feedback During Model Generation

**Status**: Implemented  
**Author**: Sunwell Team  
**Created**: 2026-01-21  
**Implemented**: 2026-01-21  
**Depends On**: RFC-042 (Adaptive Agent), RFC-080 (Unified Home Surface)

## Summary

Add real-time visibility into model inference, transforming silent waiting into engaging feedback. When local models like `gpt-oss:20b` take 10-30 seconds to respond, users should see the "beep boop bop" — tokens streaming, thinking revealed, progress animated.

## Problem

### The Wait Problem

Local models provide cost-effective inference but introduce latency:

| Model | Time to First Token | Full Response |
|-------|---------------------|---------------|
| `gemma3:1b` | ~200ms | 1-3s |
| `gpt-oss:20b` | ~2s | 10-30s |
| Cloud GPT-4o | ~500ms | 2-5s |

During these waits, users experience:
- **Uncertainty**: "Is it working? Did it crash?"
- **Boredom**: No feedback = perceived slowness
- **Lost Engagement**: Users switch tabs, lose context

### What Users Want

Users **love** seeing the system work:
- Token streams showing thought forming
- Progress indicators with real metrics
- Thinking blocks revealing reasoning
- Activity animations ("lights blinking")

### Current State

Sunwell has the infrastructure but doesn't use it during agent workflows:

```python
# agent.py:699 — BLOCKING, no feedback
result = await self.model.generate(prompt, options=...)

# ollama.py:292 — EXISTS but unused in agent
async def generate_stream(...) -> AsyncIterator[str]:
    async for chunk in stream:
        yield chunk  # Real-time tokens!
```

## Solution

### Core Principle: Every Wait Gets Feedback

No model call should complete without emitting progress events. Transform:

```
[Task Start] ──────── 15 seconds of nothing ──────── [Task Complete]
```

Into:

```
[Task Start] → [Model Start] → [Tokens...] → [Thinking...] → [Model Complete] → [Task Complete]
```

### New Event Types

```python
# src/sunwell/adaptive/events.py

class EventType(Enum):
    # ... existing events ...
    
    # Inference visibility events (RFC-081)
    MODEL_START = "model_start"
    """Model generation started. Show spinner."""
    
    MODEL_TOKENS = "model_tokens"
    """Batch of tokens received. Update counter/preview."""
    
    MODEL_THINKING = "model_thinking"
    """Detected reasoning content (<think>, Thinking..., etc.)."""
    
    MODEL_COMPLETE = "model_complete"
    """Generation finished. Show metrics."""
    
    MODEL_HEARTBEAT = "model_heartbeat"
    """Periodic heartbeat during long generation."""
```

### Event Data Schemas

```python
@dataclass(frozen=True, slots=True)
class ModelStartData:
    """Data for MODEL_START event."""
    task_id: str
    model: str
    prompt_tokens: int | None = None
    estimated_time_s: float | None = None  # Based on model + prompt size


@dataclass(frozen=True, slots=True)
class ModelTokensData:
    """Data for MODEL_TOKENS event (batched for efficiency)."""
    task_id: str
    tokens: str  # The actual token text
    token_count: int  # Cumulative count
    tokens_per_second: float | None = None


@dataclass(frozen=True, slots=True)
class ModelThinkingData:
    """Data for MODEL_THINKING event."""
    task_id: str
    phase: str  # "think", "critic", "synthesize", "reasoning"
    content: str  # The thinking content
    is_complete: bool = False  # True when thinking block closes


@dataclass(frozen=True, slots=True)
class ModelCompleteData:
    """Data for MODEL_COMPLETE event."""
    task_id: str
    total_tokens: int
    duration_s: float
    tokens_per_second: float
    time_to_first_token_ms: int | None = None
```

### Event Factories

```python
def model_start_event(
    task_id: str,
    model: str,
    prompt_tokens: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model start event (RFC-081)."""
    return AgentEvent(
        EventType.MODEL_START,
        {"task_id": task_id, "model": model, "prompt_tokens": prompt_tokens, **kwargs},
    )


def model_tokens_event(
    task_id: str,
    tokens: str,
    token_count: int,
    tokens_per_second: float | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model tokens event (RFC-081)."""
    return AgentEvent(
        EventType.MODEL_TOKENS,
        {
            "task_id": task_id,
            "tokens": tokens,
            "token_count": token_count,
            "tokens_per_second": tokens_per_second,
            **kwargs,
        },
    )


def model_thinking_event(
    task_id: str,
    phase: str,
    content: str,
    is_complete: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model thinking event (RFC-081)."""
    return AgentEvent(
        EventType.MODEL_THINKING,
        {
            "task_id": task_id,
            "phase": phase,
            "content": content,
            "is_complete": is_complete,
            **kwargs,
        },
    )


def model_complete_event(
    task_id: str,
    total_tokens: int,
    duration_s: float,
    tokens_per_second: float,
    time_to_first_token_ms: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model complete event (RFC-081)."""
    return AgentEvent(
        EventType.MODEL_COMPLETE,
        {
            "task_id": task_id,
            "total_tokens": total_tokens,
            "duration_s": duration_s,
            "tokens_per_second": tokens_per_second,
            "time_to_first_token_ms": time_to_first_token_ms,
            **kwargs,
        },
    )
```

## Agent Integration

### Streaming Task Execution

Replace blocking `generate()` with streaming that emits events:

```python
# src/sunwell/adaptive/agent.py

async def _execute_task(self, task: Task) -> AsyncIterator[AgentEvent]:
    """Execute a single task with inference visibility."""
    from sunwell.models.protocol import GenerateOptions
    
    # Build prompt
    prompt = self._build_task_prompt(task)
    
    # Emit start
    yield model_start_event(
        task_id=task.id,
        model=self.model.model_id,
        prompt_tokens=len(prompt) // 4,  # Rough estimate
    )
    
    # Stream with visibility
    start_time = time()
    first_token_time: float | None = None
    token_buffer: list[str] = []
    token_count = 0
    thinking_buffer: list[str] = []
    in_thinking = False
    
    async for chunk in self.model.generate_stream(
        prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=4000),
    ):
        # Track first token
        if first_token_time is None:
            first_token_time = time()
        
        token_buffer.append(chunk)
        token_count += 1  # Approximate
        
        # Detect thinking blocks
        combined = "".join(token_buffer[-50:])  # Look back
        if "<think>" in combined and not in_thinking:
            in_thinking = True
            thinking_buffer = []
        
        if in_thinking:
            thinking_buffer.append(chunk)
            if "</think>" in combined:
                in_thinking = False
                yield model_thinking_event(
                    task_id=task.id,
                    phase="think",
                    content="".join(thinking_buffer),
                    is_complete=True,
                )
                thinking_buffer = []
        
        # Emit token batches every ~10 tokens or 500ms
        elapsed = time() - start_time
        if token_count % 10 == 0:
            yield model_tokens_event(
                task_id=task.id,
                tokens="".join(token_buffer[-10:]),
                token_count=token_count,
                tokens_per_second=token_count / elapsed if elapsed > 0 else None,
            )
    
    # Emit complete
    duration = time() - start_time
    yield model_complete_event(
        task_id=task.id,
        total_tokens=token_count,
        duration_s=duration,
        tokens_per_second=token_count / duration if duration > 0 else 0,
        time_to_first_token_ms=int((first_token_time - start_time) * 1000) if first_token_time else None,
    )
    
    # Return artifact
    full_response = "".join(token_buffer)
    # ... rest of task completion logic
```

### Thinking Detection Patterns

```python
# src/sunwell/adaptive/thinking.py

import re
from dataclasses import dataclass
from typing import Literal

ThinkingPhase = Literal["think", "critic", "synthesize", "reasoning", "unknown"]

# Patterns for detecting thinking content
THINKING_PATTERNS = {
    "think": (r"<think>", r"</think>"),
    "critic": (r"<critic>", r"</critic>"),
    "synthesize": (r"<synthesize>", r"</synthesize>"),
    "reasoning": (r"Thinking\.\.\.", r"\n\n"),  # gpt-oss style
}


@dataclass
class ThinkingDetector:
    """Detects thinking blocks in streaming output."""
    
    _buffer: str = ""
    _current_phase: ThinkingPhase | None = None
    _phase_content: str = ""
    
    def feed(self, chunk: str) -> list[tuple[ThinkingPhase, str, bool]]:
        """Feed a chunk, return any completed thinking blocks.
        
        Returns:
            List of (phase, content, is_complete) tuples
        """
        self._buffer += chunk
        results: list[tuple[ThinkingPhase, str, bool]] = []
        
        for phase, (open_pat, close_pat) in THINKING_PATTERNS.items():
            # Check for opening
            if self._current_phase is None:
                if re.search(open_pat, self._buffer):
                    self._current_phase = phase
                    self._phase_content = ""
                    # Emit start
                    results.append((phase, "", False))
            
            # Check for closing
            elif self._current_phase == phase:
                match = re.search(close_pat, self._buffer)
                if match:
                    # Extract content
                    self._phase_content = self._buffer[:match.start()]
                    results.append((phase, self._phase_content, True))
                    self._buffer = self._buffer[match.end():]
                    self._current_phase = None
                    self._phase_content = ""
        
        return results
```

## CLI Rendering

### Rich Renderer Updates

```python
# src/sunwell/adaptive/renderer.py

class RichRenderer:
    """Rich-based renderer with inference visibility."""
    
    async def render(self, events: AsyncIterator[AgentEvent]) -> None:
        """Render events with inference visibility."""
        from rich.live import Live
        from rich.spinner import Spinner
        from rich.text import Text
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
        
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.fields[tokens]} tokens"),
            TextColumn("{task.fields[tps]} tok/s"),
        )
        
        with Live(progress, console=self.console, refresh_per_second=10):
            model_task_id = None
            
            async for event in events:
                match event.type:
                    case EventType.MODEL_START:
                        model_task_id = progress.add_task(
                            f"[cyan]🧠 {event.data['model']}[/]",
                            total=None,  # Indeterminate
                            tokens=0,
                            tps="--",
                        )
                    
                    case EventType.MODEL_TOKENS:
                        if model_task_id is not None:
                            progress.update(
                                model_task_id,
                                tokens=event.data["token_count"],
                                tps=f"{event.data['tokens_per_second']:.1f}" if event.data.get("tokens_per_second") else "--",
                            )
                    
                    case EventType.MODEL_THINKING:
                        # Show thinking in dimmed panel
                        if event.data.get("content"):
                            content = event.data["content"][:200] + "..." if len(event.data["content"]) > 200 else event.data["content"]
                            self.console.print(
                                Panel(
                                    Text(content, style="dim"),
                                    title=f"[dim]💭 {event.data['phase']}[/]",
                                    border_style="dim",
                                )
                            )
                    
                    case EventType.MODEL_COMPLETE:
                        if model_task_id is not None:
                            progress.remove_task(model_task_id)
                            model_task_id = None
                        
                        ttft = event.data.get("time_to_first_token_ms")
                        ttft_str = f", TTFT: {ttft}ms" if ttft else ""
                        
                        self.console.print(
                            f"[green]✓[/] Generated {event.data['total_tokens']} tokens "
                            f"in {event.data['duration_s']:.1f}s "
                            f"({event.data['tokens_per_second']:.1f} tok/s{ttft_str})"
                        )
                    
                    # ... handle other events ...
```

## Studio UI (RFC-080 Integration)

### ThinkingBlock Definition

```python
# src/sunwell/interface/blocks.py

from sunwell.interface.primitives import BlockDef, BlockAction

THINKING_BLOCK = BlockDef(
    id="ThinkingBlock",
    category="status",
    component="ThinkingBlock",
    actions=(
        BlockAction(id="expand", label="Show full", icon="↕"),
        BlockAction(id="cancel", label="Cancel", icon="✕"),
    ),
    can_be_primary=False,
    can_be_secondary=True,
    can_be_contextual=True,  # Floats during generation
    default_size="widget",
    contextual_on_home=True,  # Auto-appears when model generating
    refresh_events=("MODEL_START", "MODEL_TOKENS", "MODEL_THINKING", "MODEL_COMPLETE"),
)
```

### Svelte Component

```svelte
<!-- studio/src/components/blocks/ThinkingBlock.svelte -->
<script lang="ts">
  import { spring } from 'svelte/motion';
  import { fade, fly } from 'svelte/transition';
  
  export let model: string = "";
  export let tokens: number = 0;
  export let tokensPerSecond: number | null = null;
  export let elapsed: number = 0;
  export let thinking: string = "";
  export let phase: string = "";
  export let isComplete: boolean = false;
  
  // Animated token counter
  const displayTokens = spring(0, { stiffness: 0.1, damping: 0.5 });
  $: displayTokens.set(tokens);
  
  // Pulse animation while generating
  let pulse = true;
  $: pulse = !isComplete;
</script>

<div 
  class="thinking-block"
  class:complete={isComplete}
  in:fly={{ y: 20, duration: 300 }}
  out:fade={{ duration: 200 }}
>
  <div class="header">
    <div class="model-indicator" class:pulse>
      <span class="brain">🧠</span>
      <span class="model-name">{model}</span>
    </div>
    <div class="metrics">
      <span class="elapsed">{elapsed.toFixed(1)}s</span>
    </div>
  </div>
  
  <div class="progress-bar">
    <div class="fill" style:width="{Math.min(100, tokens / 10)}%"></div>
    <div class="stats">
      <span class="token-count">{Math.round($displayTokens)} tokens</span>
      {#if tokensPerSecond}
        <span class="tps">{tokensPerSecond.toFixed(1)} tok/s</span>
      {/if}
    </div>
  </div>
  
  {#if thinking}
    <div class="thinking-preview" transition:fade>
      <div class="phase-label">{phase}</div>
      <div class="content">{thinking}</div>
    </div>
  {/if}
  
  {#if isComplete}
    <div class="complete-indicator" in:fly={{ y: 10 }}>
      ✓ Complete
    </div>
  {/if}
</div>

<style>
  .thinking-block {
    background: var(--surface-2);
    border-radius: 12px;
    padding: 16px;
    border: 1px solid var(--border);
    transition: border-color 0.2s;
  }
  
  .thinking-block.complete {
    border-color: var(--success);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  
  .model-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }
  
  .brain {
    font-size: 1.2em;
  }
  
  .pulse .brain {
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.7; transform: scale(1.1); }
  }
  
  .progress-bar {
    height: 24px;
    background: var(--surface-3);
    border-radius: 6px;
    overflow: hidden;
    position: relative;
  }
  
  .fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--accent));
    transition: width 0.3s ease-out;
  }
  
  .stats {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 12px;
    font-size: 0.85em;
    font-variant-numeric: tabular-nums;
  }
  
  .thinking-preview {
    margin-top: 12px;
    padding: 12px;
    background: var(--surface-1);
    border-radius: 8px;
    font-size: 0.9em;
    color: var(--text-muted);
    max-height: 100px;
    overflow: hidden;
  }
  
  .phase-label {
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: 4px;
  }
  
  .content {
    font-family: var(--font-mono);
    white-space: pre-wrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .complete-indicator {
    margin-top: 12px;
    color: var(--success);
    font-weight: 600;
    text-align: center;
  }
</style>
```

### Event Bridge (Tauri → Svelte)

```typescript
// studio/src/lib/events/inference.ts

import { writable, type Readable } from 'svelte/store';
import { listen } from '@tauri-apps/api/event';

export interface InferenceState {
  isGenerating: boolean;
  model: string;
  tokens: number;
  tokensPerSecond: number | null;
  elapsed: number;
  thinking: string;
  phase: string;
  ttft: number | null;
}

const initialState: InferenceState = {
  isGenerating: false,
  model: "",
  tokens: 0,
  tokensPerSecond: null,
  elapsed: 0,
  thinking: "",
  phase: "",
  ttft: null,
};

function createInferenceStore(): Readable<InferenceState> & { reset: () => void } {
  const { subscribe, set, update } = writable<InferenceState>(initialState);
  
  let startTime: number | null = null;
  let elapsedInterval: number | null = null;
  
  // Listen for agent events
  listen<any>('agent-event', (event) => {
    const { type, data } = event.payload;
    
    switch (type) {
      case 'model_start':
        startTime = Date.now();
        elapsedInterval = window.setInterval(() => {
          update(s => ({ ...s, elapsed: (Date.now() - startTime!) / 1000 }));
        }, 100);
        update(s => ({
          ...s,
          isGenerating: true,
          model: data.model,
          tokens: 0,
          tokensPerSecond: null,
          elapsed: 0,
          thinking: "",
          phase: "",
        }));
        break;
      
      case 'model_tokens':
        update(s => ({
          ...s,
          tokens: data.token_count,
          tokensPerSecond: data.tokens_per_second,
        }));
        break;
      
      case 'model_thinking':
        update(s => ({
          ...s,
          thinking: data.content,
          phase: data.phase,
        }));
        break;
      
      case 'model_complete':
        if (elapsedInterval) {
          clearInterval(elapsedInterval);
          elapsedInterval = null;
        }
        update(s => ({
          ...s,
          isGenerating: false,
          tokens: data.total_tokens,
          tokensPerSecond: data.tokens_per_second,
          elapsed: data.duration_s,
          ttft: data.time_to_first_token_ms,
        }));
        break;
    }
  });
  
  return {
    subscribe,
    reset: () => {
      if (elapsedInterval) clearInterval(elapsedInterval);
      set(initialState);
    },
  };
}

export const inferenceState = createInferenceStore();
```

## Metrics & Observability

### Inference Metrics Store

Track inference performance for optimization:

```python
# src/sunwell/adaptive/metrics.py

from dataclasses import dataclass, field
from statistics import mean, stdev
from collections import defaultdict


@dataclass
class InferenceMetrics:
    """Track inference performance metrics."""
    
    _samples: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))
    
    def record(
        self,
        model: str,
        duration_s: float,
        tokens: int,
        ttft_ms: int | None = None,
    ) -> None:
        """Record an inference sample."""
        self._samples[model].append({
            "duration_s": duration_s,
            "tokens": tokens,
            "tokens_per_second": tokens / duration_s if duration_s > 0 else 0,
            "ttft_ms": ttft_ms,
        })
    
    def get_model_stats(self, model: str) -> dict:
        """Get statistics for a model."""
        samples = self._samples.get(model, [])
        if not samples:
            return {}
        
        tps_values = [s["tokens_per_second"] for s in samples]
        ttft_values = [s["ttft_ms"] for s in samples if s["ttft_ms"] is not None]
        
        return {
            "sample_count": len(samples),
            "avg_tokens_per_second": mean(tps_values),
            "std_tokens_per_second": stdev(tps_values) if len(tps_values) > 1 else 0,
            "avg_ttft_ms": mean(ttft_values) if ttft_values else None,
            "total_tokens": sum(s["tokens"] for s in samples),
            "total_time_s": sum(s["duration_s"] for s in samples),
        }
    
    def estimate_time(self, model: str, prompt_tokens: int, expected_output: int = 500) -> float | None:
        """Estimate generation time based on historical data."""
        stats = self.get_model_stats(model)
        if not stats or stats["avg_tokens_per_second"] == 0:
            return None
        
        # Estimate: TTFT + output_tokens / tok_per_sec
        ttft_s = (stats.get("avg_ttft_ms") or 1000) / 1000
        generation_s = expected_output / stats["avg_tokens_per_second"]
        return ttft_s + generation_s
```

## Configuration

### User Preferences

```yaml
# .sunwell/config.yaml

inference:
  # Show real-time token streaming
  show_tokens: true
  
  # Show thinking blocks (may contain reasoning)
  show_thinking: true
  
  # Batch size for token events (reduce event spam)
  token_batch_size: 10
  
  # Enable heartbeat during long generations
  heartbeat_enabled: true
  heartbeat_interval_s: 2.0
  
  # Show performance metrics after generation
  show_metrics: true
```

## Migration Path

### Phase 1: Events (This RFC)
1. Add new event types to `events.py`
2. Add event factories
3. Update event schema

### Phase 2: Agent Streaming
1. Add `_execute_task_streaming()` to agent
2. Wire thinking detection
3. Emit events during generation

### Phase 3: CLI Rendering
1. Update `RichRenderer` for new events
2. Add thinking panel rendering
3. Add metrics display

### Phase 4: Studio UI
1. Add `ThinkingBlock` component
2. Add inference state store
3. Wire event bridge

## Model Discovery & Comparison

### The Hidden Benefit

Inference visibility isn't just about reducing perceived wait time — it helps users **discover which models work best for them**.

Generic benchmarks don't account for:
- **Your hardware**: M1 vs M3 vs RTX 4090 vs CPU-only
- **Your tasks**: Code generation vs creative writing vs analysis
- **Your patience**: Some prefer 2s/mediocre, others 20s/excellent

### Empirical Model Comparison

With visibility metrics, users naturally learn:

```
"gpt-oss:20b gives amazing thinking but 15 tok/s on my M2"
"gemma3:4b is 80 tok/s but shallow reasoning"
"I'll use 20b for planning, 4b for simple edits"
```

### Model Comparison Block

Add a `ModelComparisonBlock` to help users choose:

```svelte
<!-- studio/src/components/blocks/ModelComparisonBlock.svelte -->
<script lang="ts">
  import type { ModelMetrics } from '$lib/stores/metrics';
  
  export let models: ModelMetrics[] = [];
</script>

<div class="model-comparison">
  <h3>Your Model Performance</h3>
  
  <table>
    <thead>
      <tr>
        <th>Model</th>
        <th>Speed</th>
        <th>TTFT</th>
        <th>Tasks</th>
        <th>Quality*</th>
      </tr>
    </thead>
    <tbody>
      {#each models as m}
        <tr>
          <td class="model-name">{m.name}</td>
          <td class="metric">{m.avgTokPerSec.toFixed(0)} tok/s</td>
          <td class="metric">{m.avgTtft}ms</td>
          <td class="metric">{m.taskCount}</td>
          <td class="metric">
            {#if m.gatePassRate}
              {(m.gatePassRate * 100).toFixed(0)}%
            {:else}
              --
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
  
  <p class="footnote">*Quality = gate pass rate (syntax, lint, type checks)</p>
</div>
```

### Metrics to Track Per Model

```python
@dataclass
class ModelPerformanceProfile:
    """Accumulated performance profile for a model on this hardware."""
    
    model: str
    hardware: str  # e.g., "Apple M2 Pro 16GB"
    
    # Speed metrics
    samples: int = 0
    total_tokens: int = 0
    total_time_s: float = 0
    avg_tokens_per_second: float = 0
    avg_ttft_ms: float = 0
    
    # Quality metrics (from validation gates)
    tasks_completed: int = 0
    gates_passed: int = 0
    gates_failed: int = 0
    
    @property
    def gate_pass_rate(self) -> float | None:
        """Quality proxy: how often does generated code pass gates?"""
        total = self.gates_passed + self.gates_failed
        return self.gates_passed / total if total > 0 else None
    
    @property
    def quality_speed_score(self) -> float | None:
        """Combined score: quality * speed (higher = better)."""
        if self.gate_pass_rate is None:
            return None
        # Normalize speed to 0-1 range (assuming 100 tok/s is "fast")
        speed_normalized = min(1.0, self.avg_tokens_per_second / 100)
        return self.gate_pass_rate * speed_normalized
```

### Model Recommendations

After enough samples, Sunwell can suggest optimal models:

```python
def recommend_model(
    profiles: dict[str, ModelPerformanceProfile],
    task_type: str,
    user_preference: Literal["speed", "quality", "balanced"] = "balanced",
) -> str:
    """Recommend a model based on user's hardware and preferences."""
    
    candidates = [p for p in profiles.values() if p.samples >= 5]
    if not candidates:
        return "gpt-oss:20b"  # Default until we have data
    
    if user_preference == "speed":
        return max(candidates, key=lambda p: p.avg_tokens_per_second).model
    elif user_preference == "quality":
        return max(candidates, key=lambda p: p.gate_pass_rate or 0).model
    else:  # balanced
        return max(candidates, key=lambda p: p.quality_speed_score or 0).model
```

### "Try This Model" Prompts

When a user's preferred model struggles, suggest alternatives:

```
⚠️ gpt-oss:20b failed gate 2x on this task type (type checking)

💡 On your hardware, gemma3:4b has 92% pass rate for similar tasks
   and runs 4x faster. Try it? [Yes] [No] [Don't ask again]
```

## Success Metrics

| Metric | Target |
|--------|--------|
| Time-to-first-feedback | < 500ms after model start |
| Token update frequency | Every 500ms or 10 tokens |
| Thinking display latency | < 100ms after detection |
| User-reported "feels fast" | > 80% positive |
| Model switch after recommendation | > 30% try suggested model |
| User finds "their" model | > 70% settle on preferred within 1 week |

## Alternatives Considered

### 1. Heartbeat Only (Simpler)
Just emit periodic heartbeats without token detail. Rejected because users want to see actual progress, not just "still alive" signals.

### 2. Full Token Streaming (More Complex)
Stream every single token as an event. Rejected because event overhead would slow rendering. Batching is better.

### 3. Server-Sent Events (SSE)
Use HTTP SSE for streaming. Rejected because we already have the Tauri event system and async iterators work well.

## Open Questions

1. **Token counting accuracy**: Ollama doesn't always report exact token counts. Use estimation?
2. **Thinking privacy**: Should thinking content be filtered for sensitive info before display?
3. **Mobile rendering**: How should ThinkingBlock render on small screens?

## References

- RFC-042: Adaptive Agent (event system foundation)
- RFC-080: Unified Home Surface (Block integration)
- Ollama API docs: https://docs.ollama.com/api/generate
- Rich library: https://rich.readthedocs.io/
