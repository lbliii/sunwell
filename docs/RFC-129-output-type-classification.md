# RFC-129: Output Type Classification — Chat vs Code vs File

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-042 (Signals), RFC-032 (Task Types)  
**Confidence**: 90% 🟢

## Summary

Classify user goals by **output type** (chat/code/file/mixed) at the signals stage, propagate through planning, and execute with appropriate prompts and output handling. Currently, execution assumes all tasks produce files—conversational queries like "explain this repo" generate content that's silently discarded.

## Motivation

### Problem

User runs:
```bash
sunwell "explain this repo"
```

What happens:
1. ✅ Signals extracted (complexity=YES, needs_tools=YES)
2. ✅ Planning completes (1 task created)
3. ✅ Model generates 448 tokens
4. ❌ Content discarded (`target_path` is None)
5. ❌ User sees nothing

**Root cause**: The system has no concept of output type. It assumes:
- All tasks produce files
- Content without `target_path` is an error state

### Evidence

```python
# core.py:851-864 - Content only written if target_path exists
if result_text and task.target_path:
    path.write_text(result_text)  # ✅ Written
    artifact = Artifact(...)
else:
    artifact = None  # ❌ 448 tokens → /dev/null
```

```python
# core.py:806 - Fallback always assumes GENERATE
task = Task(id="main", description=goal, mode=TaskMode.GENERATE)
```

```python
# core.py:1015-1021 - Prompt always assumes code generation
prompt = """Generate code for this task:
...
Output ONLY the code (no explanation, no markdown fences):"""
```

### User Stories

> "I asked Sunwell to explain the codebase and it said 'Complete' but showed me nothing."

> "When I ask 'what does this function do', I expect an answer, not a file."

> "Sometimes I want code, sometimes I want explanation. Sunwell should know the difference."

### The Gap

| What Exists | What's Missing |
|-------------|----------------|
| `complexity` signal | `output_type` signal |
| `TaskMode.RESEARCH` | Nobody sets it |
| `task.mode` field | Execution ignores it |
| `TASK_OUTPUT` event (bridge fix) | Proper classification |

---

## Goals

1. **Classify at signals stage**: Detect output type before planning
2. **Set appropriate TaskMode**: Planner uses classification
3. **Execute differently**: Different prompts and output handling per mode
4. **Display properly**: Console output for chat, file writes for code

## Non-Goals

- Support streaming chat (future work)
- Multi-modal outputs in single task
- User override flags (--output-type=chat)

---

## Design

### 1. Extend AdaptiveSignals

```python
# sunwell/agent/signals.py

@dataclass(frozen=True, slots=True)
class AdaptiveSignals:
    # Existing signals...
    complexity: Literal["YES", "NO", "MAYBE"] = "MAYBE"
    needs_tools: Literal["YES", "NO"] = "NO"
    is_ambiguous: Literal["YES", "NO", "MAYBE"] = "NO"
    is_dangerous: Literal["YES", "NO"] = "NO"
    is_epic: Literal["YES", "NO", "MAYBE"] = "NO"
    confidence: float = 0.5
    domain: str = "general"
    
    # NEW: Output type classification
    output_type: Literal["code", "chat", "file", "mixed"] = "code"
    """Expected output type:
    - code: Generate code to write to files (default)
    - chat: Conversational response to display
    - file: Non-code file operations (docs, configs)
    - mixed: Multiple output types needed
    """
```

### 2. Update Signal Extraction Prompt

```python
# In EXTRACT_SIGNALS_PROMPT, add:

OUTPUT_TYPE (one of: code, chat, file, mixed):
- code: User wants code generated and saved to files
  Examples: "build a REST API", "add auth middleware", "create a CLI"
- chat: User wants information/explanation displayed
  Examples: "explain this repo", "what does X do", "help me understand"
- file: User wants non-code files (docs, configs)
  Examples: "write a README", "update the config"
- mixed: Multiple output types
  Examples: "explain and then implement", "document and fix"

Respond with your classification.
```

### 3. Map output_type → TaskMode

```python
# sunwell/agent/signals.py

OUTPUT_TYPE_TO_MODE: dict[str, TaskMode] = {
    "code": TaskMode.GENERATE,
    "chat": TaskMode.RESEARCH,  # RESEARCH = no side effects
    "file": TaskMode.GENERATE,
    "mixed": TaskMode.COMPOSITE,
}
```

### 4. Planner Uses Classification

```python
# sunwell/naaru/planners/harmonic.py (and other planners)

async def plan(self, goal: str, signals: AdaptiveSignals, ...) -> TaskGraph:
    mode = OUTPUT_TYPE_TO_MODE.get(signals.output_type, TaskMode.GENERATE)
    
    # Set target_path only for code/file modes
    target_path = None
    if signals.output_type in ("code", "file"):
        target_path = self._infer_target_path(goal)
    
    task = Task(
        id="main",
        description=goal,
        mode=mode,
        target_path=target_path,
    )
```

### 5. Execute Based on Mode

```python
# sunwell/agent/core.py

async def _execute_task_streaming(self, task: Task) -> AsyncIterator[AgentEvent]:
    # Choose prompt based on mode
    if task.mode == TaskMode.RESEARCH:
        prompt = f"""Answer this question about the codebase:

QUESTION: {task.description}

{learnings_context}

Respond directly and helpfully:"""
    else:
        prompt = f"""Generate code for this task:

TASK: {task.description}

{learnings_context}

Output ONLY the code:"""
    
    # ... streaming logic ...
    
    # Handle output based on mode
    if task.mode == TaskMode.RESEARCH:
        # Always emit for display
        yield task_output_event(task.id, result_text)
    elif result_text and task.target_path:
        # Write to file
        path.write_text(result_text)
```

### 6. Event Flow

```
User: "explain this repo"
  ↓
Signals: output_type="chat", needs_tools=YES
  ↓
Planner: mode=RESEARCH, target_path=None
  ↓
Executor: Uses chat prompt, emits TASK_OUTPUT
  ↓
Renderer: Displays content to console
```

```
User: "build a REST API"
  ↓
Signals: output_type="code", needs_tools=YES
  ↓
Planner: mode=GENERATE, target_path="api/"
  ↓
Executor: Uses code prompt, writes files
  ↓
Renderer: Shows file creation progress
```

---

## Implementation Plan

### Phase 1: Signal Classification (1 day)

1. Add `output_type` field to `AdaptiveSignals`
2. Update `EXTRACT_SIGNALS_PROMPT` 
3. Parse output_type in `extract_signals()`
4. Add tests for classification

**Files**:
- `sunwell/agent/signals.py`
- `tests/agent/test_signals.py`

### Phase 2: Planner Integration (1 day)

1. Create `OUTPUT_TYPE_TO_MODE` mapping
2. Update `HarmonicPlanner` to set mode from signals
3. Update fallback task creation in `core.py`
4. Add tests

**Files**:
- `sunwell/naaru/planners/harmonic.py`
- `sunwell/agent/core.py`
- `tests/naaru/test_harmonic_planner.py`

### Phase 3: Execution Branching (1 day)

1. Update `_execute_task_streaming` to branch on mode
2. Different prompts for RESEARCH vs GENERATE
3. Use `task.mode` not `task.target_path` for output decisions
4. Remove bridge fix (target_path heuristic)

**Files**:
- `sunwell/agent/core.py`
- `tests/agent/test_core.py`

### Phase 4: Integration Testing (0.5 day)

1. End-to-end test: "explain this repo" → console output
2. End-to-end test: "build X" → file writes
3. Mixed mode handling

**Files**:
- `tests/integration/test_output_types.py`

---

## Alternatives Considered

### 1. Keyword Detection (Rejected)

```python
if any(word in goal.lower() for word in ["explain", "what", "help"]):
    output_type = "chat"
```

**Why rejected**: Fragile. "Help me build an API" should be code, not chat.

### 2. User Flag (Deferred)

```bash
sunwell "explain this" --output=chat
```

**Why deferred**: Good for power users but shouldn't be required. Auto-classification is the right default.

### 3. target_path Heuristic (Current Bridge)

```python
if result_text and not task.target_path:
    yield task_output_event(...)
```

**Why replaced**: Works but is backwards—inferring type from absence of path rather than classifying upfront.

---

## Migration Path

1. **Phase 1-2**: Add classification, doesn't change behavior yet
2. **Phase 3**: Switch to mode-based execution
3. **Cleanup**: Remove `target_path` heuristic from bridge fix

The bridge fix (checking `target_path`) remains backward-compatible during migration.

---

## Success Criteria

1. ✅ `sunwell "explain this repo"` shows explanation in console
2. ✅ `sunwell "build a REST API"` writes files
3. ✅ Signal extraction includes `output_type` field
4. ✅ `TaskMode.RESEARCH` is actually used
5. ✅ No content silently discarded

---

## Open Questions

1. **Streaming chat**: Should RESEARCH mode stream tokens to console in real-time?
2. **Mixed mode**: How to handle "explain then implement"—two tasks?
3. **Tool use in chat**: Should RESEARCH tasks use read_file etc. to answer?

---

## References

- RFC-042: Adaptive Signals — base signal extraction
- RFC-032: Task Types — defines TaskMode enum
- RFC-081: Inference Visibility — model event streaming
- `sunwell/agent/signals.py:27-100` — AdaptiveSignals definition
- `sunwell/naaru/types.py:44-56` — TaskMode enum
