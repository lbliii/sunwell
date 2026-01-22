# RFC-091: LLM Output Sanitization — Defense Against Control Characters

**Status**: Implemented  
**Author**: Sunwell Team  
**Created**: 2026-01-22  
**Revised**: 2026-01-22  
**Depends On**: RFC-012 (Tool Calling Protocol)

> **Revision Notes**: Updated with accurate file counts (5 Rust files, not 10+), added existing Python sanitization in `inference.py`, added risks section, resolved open questions, added Unicode preservation tests.

## Summary

Establish a systematic approach to sanitizing LLM outputs at the source, preventing control characters from propagating through the system and causing JSON parsing failures in the Rust frontend.

**Scope**: Full stack — Python (models), Rust (Tauri backend), Svelte (frontend)

## Problem

### Current Failure Mode

LLM responses occasionally contain control characters (`\u0000`-`\u001F`) that break JSON parsing:

```
Failed to parse analysis result: control character (\u0000-\u001F) found while 
parsing a string at line 21 column 0
```

This causes:
- Project overview pages failing to load
- Pipeline views showing empty
- Agent events being dropped
- Silent data corruption in memory stores

### Root Cause Analysis

```
LLM Provider (Ollama/OpenAI/Anthropic)
    ↓
Raw response with potential control chars
    ↓
GenerateResult.content (unsanitized)
    ↓
JSON serialization in CLI --json output
    ↓
Rust serde_json::from_str() FAILS ❌
```

Control characters enter through:
1. **Model artifacts**: Some models emit escape sequences
2. **Training data leakage**: Code snippets with embedded chars
3. **Tool output parsing**: Raw subprocess output included in context
4. **Copy-paste in prompts**: Users paste text with hidden chars

### Current Workarounds (Scattered)

**Rust (6 files with sanitization, 3 files missing it)**:

Files with `sanitize_json_string` (28 usages):
- `util.rs:14-18` — Core `sanitize_json_string()` function
- `agent.rs` — AgentEvent parsing (3 call sites)
- `dag.rs` — DAG state parsing (3 call sites)
- `naaru.rs` — Naaru event parsing (4 call sites)
- `memory.rs` — Memory store parsing (14 call sites)
- `commands.rs:1611` — ProjectAnalysis (1 inline sanitization)

Files **missing** sanitization (5 call sites at risk):
- `weakness.rs` — Agent events/execution results (2 call sites) ⚠️
- `briefing.rs` — Briefing JSON with LLM summaries (1 call site)
- `commands.rs:1005,1019` — Decision/failure logs (2 call sites)

**Python (1 file)**: Partial sanitization exists in goal inference:

```python
# src/sunwell/project/inference.py:14-16
def _sanitize_text(text: str) -> str:
    """Remove control characters from LLM output (keeps printable + newlines/tabs)."""
    return "".join(c for c in text if not (ord(c) < 32 and c not in "\n\r\t"))
```

This uses the **exact same logic** we need, but is isolated to one module.

**Rust sanitization code**:

```rust
// util.rs - applied to every JSON parse
pub fn sanitize_json_string(input: &str) -> String {
    input
        .chars()
        .filter(|c| !c.is_control() || *c == '\n' || *c == '\r' || *c == '\t')
        .collect()
}
```

**Problems**:
1. **O(n) overhead** on every Rust parse, even when 99%+ are clean
2. **Defense-in-depth, not prevention**: Chars still reach disk
3. **Scattered implementation**: 5 Rust files + 1 Python file with duplicate logic
4. **No streaming support**: Chunks aren't sanitized
5. **No single source of truth**: `inference.py` has its own copy of sanitization logic

## Proposal

### Design Principle: Sanitize Once at Source

```
LLM Provider Response
    ↓
sanitize_llm_content() ← SANITIZE HERE (once)
    ↓
GenerateResult.content (clean)
    ↓
JSON serialization (always valid)
    ↓
Rust serde_json::from_str() ✓
```

### Implementation

#### 1. Add Sanitization Helper to Protocol

```python
# src/sunwell/models/protocol.py

def sanitize_llm_content(text: str | None) -> str | None:
    """Remove control characters from LLM output.
    
    Preserves newlines, carriage returns, and tabs which are valid
    in JSON strings and needed for code formatting.
    
    Applied once at the model layer, not on every read.
    """
    if text is None:
        return None
    return "".join(
        c for c in text 
        if not (ord(c) < 32 and c not in "\n\r\t")
    )
```

#### 2. Apply in Each Model's generate()

```python
# src/sunwell/models/ollama.py

async def generate(self, prompt, *, tools=None, tool_choice=None, options=None) -> GenerateResult:
    # ... existing code ...
    
    message = response.choices[0].message
    content = sanitize_llm_content(message.content)  # ← ADD
    
    return GenerateResult(
        content=content,  # Now guaranteed clean
        model=self.model,
        # ...
    )
```

Same pattern for:
- `OpenAIModel.generate()`
- `AnthropicModel.generate()`
- `OllamaModel._generate_native()`

#### 3. Streaming Sanitization

```python
# src/sunwell/models/ollama.py

async def generate_stream(self, prompt, *, tools=None, options=None):
    async for chunk in self._generate_stream_openai(prompt, options=options):
        yield sanitize_llm_content(chunk) or ""  # ← ADD
```

#### 4. Tool Call Argument Sanitization

Tool arguments can also contain control chars:

```python
# In generate() after parsing tool calls
tool_calls = tuple(
    ToolCall(
        id=tc.id,
        name=tc.function.name,
        arguments=_sanitize_dict_values(json.loads(tc.function.arguments)),
    )
    for tc in message.tool_calls
)

def _sanitize_dict_values(d: dict) -> dict:
    """Recursively sanitize string values in a dict."""
    return {
        k: (sanitize_llm_content(v) if isinstance(v, str)
            else _sanitize_dict_values(v) if isinstance(v, dict)
            else [_sanitize_dict_values(i) if isinstance(i, dict) 
                  else sanitize_llm_content(i) if isinstance(i, str) 
                  else i for i in v] if isinstance(v, list)
            else v)
        for k, v in d.items()
    }
```

#### 5. Rust: Lazy Sanitization as Fallback

Keep Rust sanitization but make it lazy:

```rust
// src/util.rs

pub fn parse_json_safe<T: DeserializeOwned>(json_str: &str) -> Result<T, serde_json::Error> {
    // Fast path: try direct parse (99% of cases after Python fix)
    match serde_json::from_str(json_str) {
        Ok(v) => Ok(v),
        Err(e) if e.to_string().contains("control character") => {
            // Slow path: sanitize and retry
            serde_json::from_str(&sanitize_json_string(json_str))
        }
        Err(e) => Err(e),
    }
}
```

### Migration Path

1. **Phase 1**: Add `sanitize_llm_content()` to `protocol.py`
2. **Phase 1.5**: Consolidate existing `_sanitize_text()` from `inference.py` → import from `protocol.py`
3. **Phase 2**: Apply to OllamaModel (most common provider)
4. **Phase 3**: Apply to OpenAI, Anthropic, Mock models
5. **Phase 4**: Apply to all streaming methods
6. **Phase 5**: Update Rust to lazy sanitization (try-then-sanitize)
7. **Phase 6**: Add telemetry to track sanitization frequency

### Telemetry

Track how often sanitization is needed:

```python
# In sanitize_llm_content()
if text != sanitized:
    logger.debug(
        "Sanitized control chars from LLM output",
        original_len=len(text),
        sanitized_len=len(sanitized),
        chars_removed=len(text) - len(sanitized),
    )
```

This helps identify problematic models or prompts.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Double sanitization (Python + Rust) during transition | Medium | Low (perf only) | Rust lazy sanitization means double-sanitize is rare; remove after monitoring |
| Unicode corruption (emoji, CJK chars) | Low | High | Add explicit tests for Unicode preservation; our filter only removes `0x00-0x1F` except `\n\r\t` |
| Streaming latency increase | Low | Medium | Sanitization is O(chunk_size), typically <100 chars; benchmark shows negligible |
| Missed sanitization points | Medium | Medium | Consolidate to single function, grep for direct `.content` access |

## Alternatives Considered

### 1. Sanitize Only in GenerateResult

**Rejected**: Would require changing the frozen dataclass, and wouldn't help with streaming.

### 2. Sanitize in JSON Serialization Layer

**Rejected**: Too late - data already stored with control chars.

### 3. Use json.dumps with ensure_ascii=True

**Rejected**: Escapes all non-ASCII, making output unreadable.

### 4. Sanitize in Each Consumer

**Rejected**: Current approach - scattered, easy to miss locations.

## Performance Analysis

### Before (Current)
- **Every JSON parse**: O(n) sanitization in Rust (where applied)
- **Allocation**: New string per parse
- **Files with sanitization**: 6 Rust files (28 call sites)
- **Files missing sanitization**: 3 Rust files (5 call sites at risk)

### After (Proposed)
- **LLM response**: O(n) sanitization (once per generation)
- **JSON parse**: O(1) direct parse (99% of cases)
- **Allocation**: One string at generation time

### Benchmarks (Estimated)

| Scenario | Before | After | Speedup |
|----------|--------|-------|---------|
| Parse clean 1KB JSON | ~50µs | ~10µs | 5x |
| Parse clean 10KB JSON | ~500µs | ~100µs | 5x |
| Parse dirty 1KB JSON | ~50µs | ~60µs | 0.8x |
| Streaming 100 chunks | ~5ms | ~5ms | 1x |

Net positive: Vast majority of parses are clean.

## Testing Strategy

### Unit Tests

```python
# tests/test_sanitization.py

def test_sanitize_preserves_valid_content():
    text = "Hello\nWorld\tTab"
    assert sanitize_llm_content(text) == text

def test_sanitize_removes_null():
    text = "Hello\x00World"
    assert sanitize_llm_content(text) == "HelloWorld"

def test_sanitize_removes_control_chars():
    text = "Hello\x01\x02\x03World"
    assert sanitize_llm_content(text) == "HelloWorld"

def test_sanitize_none():
    assert sanitize_llm_content(None) is None

def test_sanitize_preserves_unicode():
    """Ensure emoji, CJK, and other Unicode are preserved."""
    text = "Hello 🚀 世界 مرحبا"
    assert sanitize_llm_content(text) == text

def test_sanitize_preserves_extended_ascii():
    """Characters >= 0x20 (space) should be preserved."""
    text = "Café résumé naïve"
    assert sanitize_llm_content(text) == text
```

### Integration Tests

```python
# tests/integration/test_llm_sanitization.py

async def test_ollama_sanitizes_output():
    model = OllamaModel("gemma3:1b")
    # Prompt that might trigger control chars
    result = await model.generate("Output raw bytes: \\x00\\x01")
    assert "\x00" not in result.text
    assert "\x01" not in result.text
```

### Property Tests

```python
# tests/test_sanitization_properties.py

from hypothesis import given, strategies as st

@given(st.text())
def test_sanitized_output_is_json_safe(text):
    sanitized = sanitize_llm_content(text)
    # Should never raise
    json.dumps({"content": sanitized})
```

## Files Changed

### Python (Source Fix)

| File | Change |
|------|--------|
| `models/protocol.py` | Add `sanitize_llm_content()` (canonical location) |
| `models/ollama.py` | Apply to `generate()`, `generate_stream()` |
| `models/openai.py` | Apply to `generate()`, `generate_stream()` |
| `models/anthropic.py` | Apply to `generate()`, `generate_stream()` |
| `models/mock.py` | Apply to `generate()` for test parity |
| `project/inference.py` | Remove `_sanitize_text()`, import from `protocol` |

### Rust (Lazy Fallback)

**Already using sanitization (migrate to lazy)**:

| File | Call Sites | Change |
|------|------------|--------|
| `util.rs` | 2 | Update `parse_json_safe()` to try-then-sanitize |
| `agent.rs` | 3 | Replace `sanitize_json_string` + `from_str` with `parse_json_safe` |
| `dag.rs` | 3 | Replace `sanitize_json_string` + `from_str` with `parse_json_safe` |
| `naaru.rs` | 4 | Replace `sanitize_json_string` + `from_str` with `parse_json_safe` |
| `memory.rs` | 14 | Replace `sanitize_json_string` + `from_str` with `parse_json_safe` |
| `commands.rs` | 1 | Has inline sanitization at line 1611; migrate to `parse_json_safe` |

**Missing sanitization (add `parse_json_safe`)**:

| File | Call Sites | Risk | Change |
|------|------------|------|--------|
| `weakness.rs` | 2 | **HIGH** — Parses agent events/execution results | Add `parse_json_safe` |
| `briefing.rs` | 1 | **MEDIUM** — Parses briefing (may contain LLM summaries) | Add `parse_json_safe` |
| `commands.rs` | 2 | **MEDIUM** — Parses decision/failure logs (lines 1005, 1019) | Add `parse_json_safe` |

**Safe to skip (static/config data)**:

| File | Call Sites | Reason |
|------|------------|--------|
| `workspace.rs` | 2 | Parses workspace config (user-created JSON) |
| `heuristic_detect.rs` | 1 | Parses `package.json` (static file) |
| `commands.rs` | 2 | Parses checkpoint/run JSON (internal format, lines 521, 1253) |
| `run_analysis.rs` | 1 | Test code only |

### Svelte (No Changes Needed)

| File | Status | Reason |
|------|--------|--------|
| `patterns.svelte.ts` | ✅ Safe | Parses localStorage (user patterns, no LLM content) |

All Svelte `JSON.parse` calls handle user-generated data, not LLM output. LLM content arrives via Tauri IPC as already-parsed objects.

## Success Metrics

1. **Zero control char errors** in Studio after deployment
2. **< 1% of LLM responses** require sanitization (via telemetry)
3. **No performance regression** in JSON parsing benchmarks

## Design Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Log when sanitization removes chars? | **Yes** (debug level) | Helps identify problematic prompts/models; low overhead |
| MockModel sanitization? | **Yes** | Test parity ensures tests catch issues real models would hit |
| Config flag to disable? | **No** | Adds complexity without clear benefit; telemetry suffices for debugging |

## Timeline

- **Day 1**: Implement `protocol.py` helper + OllamaModel + consolidate `inference.py`
- **Day 2**: OpenAI, Anthropic, Mock models + streaming methods
- **Day 3**: Rust lazy `parse_json_safe()` + migrate existing 6 files
- **Day 4**: Add `parse_json_safe` to missing files (`weakness.rs`, `briefing.rs`, `commands.rs` logs)
- **Day 5**: Testing + telemetry
- **Day 6**: Monitor in production, verify zero control char errors

## References

- [JSON Spec on Control Characters](https://www.json.org/json-en.html)
- [serde_json Error Types](https://docs.rs/serde_json/latest/serde_json/error/enum.Category.html)
- RFC-012: Tool Calling Protocol (defines GenerateResult)
