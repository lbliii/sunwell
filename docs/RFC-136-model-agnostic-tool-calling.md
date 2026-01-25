# RFC-136: Model-Agnostic Tool Calling

**RFC Status**: Implemented  
**Author**: Architecture Team  
**Created**: 2026-01-25  
**Updated**: 2026-01-25 (v3 - Implementation complete)  
**Related**: RFC-012 (Tool Calling), RFC-134 (Task Queue Interactivity), RFC-091 (LLM Output Sanitization)

---

## Implementation Status

**✅ IMPLEMENTED** — All 16 phases complete with 281 tests passing.

| Component | Status | Location | Tests |
|-----------|--------|----------|-------|
| ModelSpec Parser | ✅ Complete | `models/capability/parser.py` | 75 tests |
| Capability Registry | ✅ Complete | `models/capability/registry.py` | 30 tests |
| Schema Adapters | ✅ Complete | `models/capability/schema.py` | 25 tests |
| Adaptive Emulation | ✅ Complete | `models/capability/emulation.py` | 13 tests |
| Tool Call Normalizer | ✅ Complete | `models/capability/normalizer.py` | 16 tests |
| Typed Streaming | ✅ Complete | `models/capability/streaming.py` | 15 tests |
| Structured Errors | ✅ Complete | `tools/errors.py` | 24 tests |
| Tool Engineering | ✅ Complete | `models/capability/tool_engineering.py` | 8 tests |
| Parallel Planning | ✅ Complete | `models/capability/parallel.py` | 8 tests |
| Validation Retry | ✅ Complete | `models/capability/validation.py` | 10 tests |
| Response Format | ✅ Complete | `models/capability/response_format.py` | 11 tests |
| Tool Namespacing | ✅ Complete | `models/capability/namespacing.py` | 11 tests |
| Evaluation Framework | ✅ Complete | `models/capability/evaluation.py` | 8 tests |
| Integration | ✅ Complete | `models/tool_emulator.py` | See E2E tests |
| E2E Journey Tests | ✅ Complete | `tests/test_e2e_tool_journeys.py` | 24 tests |

### Migration Path

The new capability system is integrated via `tool_emulator.get_model_capability()`, which now delegates to the new `capability.registry.get_capability()`. Existing code continues to work without changes.

```python
# New: Use the capability module directly
from sunwell.models.capability import parse_model_id, get_capability

spec = parse_model_id("claude-3.5-sonnet")  # Structured parsing
cap = get_capability("claude-3.5-sonnet")   # Version-aware capabilities

# Legacy: Still works, now uses new system internally
from sunwell.models.tool_emulator import get_model_capability
cap = get_model_capability("claude-3.5-sonnet")  # Delegates to new system
```

---

> **v2 Changes**: Added tool description engineering, parallel execution planning, validation-based retry loops, response format control, tool namespacing, evaluation strategy, and enhanced error messages based on Anthropic/MCP/OpenAI best practices research.

> **Dependency Status**:
> - RFC-012: Original tool calling protocol — **VERIFIED** in `models/protocol.py`
> - RFC-134: Tool introspection and repair — **VERIFIED** in `agent/introspection.py`
> - RFC-091: LLM output sanitization — **VERIFIED** in `models/protocol.py`

---

## Executive Summary

Sunwell's tool calling system works well with major providers (OpenAI, Anthropic, Ollama) but has fragile model detection, provider-coupled schema translation, and limited adaptability for:

| Challenge | Current State | Impact |
|-----------|---------------|--------|
| **Model detection** | String prefix matching | Fine-tuned models misrouted |
| **Schema translation** | Copy-pasted per provider | Inconsistencies, no validation |
| **Tool emulation** | Generic JSON prompt | Small models struggle |
| **Streaming** | Text-only | Tool calls invisible during stream |
| **Error handling** | String messages | No structured recovery hints |

**Proposed**: A robust model capability system with:

1. **Structured model parsing** — Extract family, version, size, provider from model IDs
2. **Unified schema translation** — Single converter with provider adapters
3. **Adaptive tool prompts** — Model-size and capability-aware emulation
4. **Typed streaming** — Stream chunks include tool call progress
5. **Structured errors** — Error codes with retry strategies
6. **Tool description engineering** — LLM-optimized descriptions with quality auditing
7. **Parallel execution planning** — Safe parallelization of read-only operations
8. **Validation-based retry loops** — Structured feedback for tool call correction

```
┌─────────────────────────────────────────────────────────────────┐
│                      Tool Call Flow (After)                      │
│                                                                  │
│  Model ID ──→ ┌──────────────────┐                              │
│               │  ModelSpecParser  │                              │
│               │  "llama3.3:70b"  │                              │
│               │  ↓                │                              │
│               │  family: llama    │                              │
│               │  version: (3,3)   │                              │
│               │  size: 70B        │                              │
│               └────────┬─────────┘                              │
│                        ↓                                         │
│               ┌──────────────────┐                              │
│               │CapabilityRegistry│──→ native_tools: true        │
│               │                  │    parallel_tools: false     │
│               │                  │    json_mode: true           │
│               └────────┬─────────┘                              │
│                        ↓                                         │
│               ┌──────────────────┐                              │
│               │SchemaTranslator  │──→ Provider-specific format  │
│               │  + Validation    │                              │
│               └────────┬─────────┘                              │
│                        ↓                                         │
│               ┌──────────────────┐                              │
│               │ToolCallNormalizer│──→ Handles model quirks      │
│               │  (post-response) │                              │
│               └──────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Goals

| Goal | Benefit |
|------|---------|
| **Structured model detection** | Fine-tuned, versioned, and custom models routed correctly |
| **Unified schema translation** | No more copy-paste bugs between providers |
| **Adaptive emulation prompts** | Small models (7B) succeed at tool calling |
| **Typed streaming** | Tool call progress visible during generation |
| **Structured errors** | Intelligent retry strategies per error type |
| **Model-specific normalization** | Llama/Qwen/etc quirks handled automatically |
| **Tool description engineering** | Higher tool selection accuracy via prompt-engineered descriptions |
| **Parallel execution planning** | 4x latency reduction for independent read operations |
| **Validation-based retry loops** | 40%+ improvement in tool call success rate |
| **Response format control** | ~70% token reduction via concise mode |

---

## 🚫 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Support every model ever | Focus on common model families, extensible for others |
| MCP/custom tool protocols | Out of scope — focus on OpenAI-style function calling |
| Real-time capability probing | Too slow — use static registry with version fallbacks |
| Multi-provider routing | Different RFC — this is about tool calling mechanics |

---

## 📍 User Journey Analysis

This section maps **every user journey** for both the AI agent (internal) and human users (external), ensuring tier-S coverage for each touchpoint.

### Agent Journeys (Internal — What the AI Does)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT TOOL CALLING LIFECYCLE                          │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ A1. RECEIVE │───▶│ A2. FORMAT  │───▶│ A3. GENERATE│───▶│ A4. PARSE   │  │
│  │   TOOLS     │    │   SCHEMA    │    │  RESPONSE   │    │  TOOL CALLS │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                    │         │
│                                                                    ▼         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ A8. LEARN   │◀───│ A7. HANDLE  │◀───│ A6. RECEIVE │◀───│ A5. EXECUTE │  │
│  │   OUTCOME   │    │   RESULT    │    │   RESULT    │    │   TOOL      │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                                                                    │
│         └──────────────────────────────────────────────────────────────────┐│
│                                                                            ││
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    ▼│
│  │ A9. RETRY/  │───▶│ A10. ESCAL- │───▶│ A11. REPORT │◀───────────────────┘│
│  │   ESCALATE  │    │  ATE/ABORT  │    │  TO HUMAN   │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

| ID | Journey | Description | RFC-136 Component | Coverage |
|----|---------|-------------|-------------------|----------|
| **A1** | Receive tools | Agent receives tool definitions from executor | `SchemaAdapter.convert_tools()` | ✅ |
| **A2** | Format schema | Convert tools to provider-specific format | `SchemaAdapter` (OpenAI/Anthropic/Ollama) | ✅ |
| **A3** | Generate response | Model generates text and/or tool calls | `ModelCapability` routing | ✅ |
| **A4** | Parse tool calls | Extract tool calls from model output | `ToolCallNormalizer.normalize()` | ✅ |
| **A5** | Execute tool | Run the tool with arguments | (ToolExecutor — existing) | ✅ |
| **A6** | Receive result | Get success/failure from execution | `ToolResult` → `ToolError` mapping | ✅ |
| **A7** | Handle result | Process result for next turn | `ToolError.retry_strategy` | ✅ |
| **A8** | Learn outcome | Update patterns for future calls | `LearningStore` (existing) | ✅ |
| **A9** | Retry/escalate | Decide to retry, rephrase, or escalate | `get_retry_strategy()`, `should_retry()` | ✅ |
| **A10** | Escalate/abort | Give up or ask human for help | `ToolError.recoverable=False` → escalate | ✅ |
| **A11** | Report to human | Emit events for human observation | `StreamChunk`, `AgentEvent` | ✅ |

#### A1-A2: Tool Reception & Schema Formatting

**Journey**: Agent receives tools from `ToolExecutor.get_tool_definitions()`, needs to format for provider.

**Current Gap**: Each provider adapter has copy-pasted conversion logic.

**RFC-136 Solution**: `SchemaAdapter` protocol with provider-specific implementations.

```python
# Journey: A1 → A2
tools = executor.get_tool_definitions()  # A1: Receive
adapter = get_schema_adapter(provider)    # A2: Get adapter
provider_tools = adapter.convert_tools(tools)  # A2: Format
```

#### A3-A4: Generation & Parsing

**Journey**: Model generates response. May use native tools, JSON emulation, or produce malformed output.

**Current Gap**: 
- Models without native tools get generic prompt
- Malformed JSON from small models not repaired
- Model-specific quirks (Llama trailing commas, Qwen function key) not handled

**RFC-136 Solution**:

```python
# Journey: A3 (Generate)
if capability.native_tools:
    result = await model.generate(..., tools=provider_tools)
else:
    # A3: Use adaptive emulation
    emulation_prompt = build_emulation_prompt(tools, capability)
    result = await model.generate(emulation_prompt + task)

# Journey: A4 (Parse)
normalizer = ToolCallNormalizer()
parsed = normalizer.normalize(result.text, model_family=spec.family)
# Handles Llama/Qwen/etc quirks automatically
```

#### A5-A8: Execution & Learning

**Journey**: Tool executes, returns result. Agent processes result and may learn patterns.

**RFC-136 Coverage**: Execution itself is handled by existing `ToolExecutor`. RFC-136 adds:
- `ToolError.from_exception()` for structured error categorization
- `ToolError.suggested_fix` for repair hints
- Learning integration via existing `LearningStore`

#### A9-A11: Retry, Escalation & Reporting

**Journey**: On failure, agent decides whether to retry, use different strategy, or ask human.

**Current Gap**: Retry logic is ad-hoc, no structured escalation ladder.

**RFC-136 Solution**:

```python
# Journey: A9-A10 (Retry/Escalate)
error = ToolError.from_exception(e, tool_name)

if should_retry(error, attempt):
    strategy = get_retry_strategy(error, attempt)
    # strategy: "same" | "rephrase" | "interference" | "vortex"
else:
    # A10: Escalate to human
    yield ChatCheckpoint(type=FAILURE, error=error)

# Journey: A11 (Report)
yield StreamChunk(type=TOOL_END, tool_name=tc.name, is_complete=True)
```

---

### Human User Journeys (External — What the Human Experiences)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HUMAN USER TOOL CALLING LIFECYCLE                    │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ H1. CONFIG  │───▶│ H2. START   │───▶│ H3. OBSERVE │───▶│ H4. RECEIVE │  │
│  │   MODEL     │    │   TASK      │    │   PROGRESS  │    │  CHECKPOINT │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                    │         │
│                                                                    ▼         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ H8. REVIEW  │◀───│ H7. RECEIVE │◀───│ H6. WAIT    │◀───│ H5. RESPOND │  │
│  │   OUTCOME   │    │  COMPLETION │    │   FOR MORE  │    │  TO CKPT    │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ H9. DEBUG   │───▶│ H10. CUSTOM-│───▶│ H11. SWITCH │───▶│ H12. ADD    │  │
│  │   FAILURE   │    │  IZE TOOLS  │    │  MODEL      │    │  CUSTOM     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

| ID | Journey | Description | RFC-136 Component | Coverage |
|----|---------|-------------|-------------------|----------|
| **H1** | Configure model | User sets model via CLI/config/env | `parse_model_id()` validation | ✅ |
| **H2** | Start task | User issues goal/task | (Existing CLI) | ✅ |
| **H3** | Observe progress | See tool calls happening in real-time | `StreamChunk` typed streaming | ✅ |
| **H4** | Receive checkpoint | Get prompted for decision | `ToolError` → `ChatCheckpoint` | ✅ |
| **H5** | Respond to checkpoint | Choose retry/skip/manual/abort | `CheckpointResponse` handling | ✅ |
| **H6** | Wait for more | Agent continues after response | (Existing loop) | ✅ |
| **H7** | Receive completion | Task finishes successfully | `StreamChunk(TOOL_END)` | ✅ |
| **H8** | Review outcome | See what changed, files written | (Existing events) | ✅ |
| **H9** | Debug failure | Understand why tool call failed | `ToolError` structured errors | ✅ |
| **H10** | Customize tools | Add/modify tool definitions | (Existing skill system) | ✅ |
| **H11** | Switch model | Change to different model mid-session | `get_capability()` re-routing | ✅ |
| **H12** | Add custom model | Register fine-tuned/custom model | `ModelSpec.custom=True` inheritance | ✅ |

#### H1: Configure Model

**Journey**: User specifies model via `--model gpt-4o` or config.

**Current Gap**: Invalid/unknown models silently use wrong capabilities.

**RFC-136 Solution**:

```python
# Journey: H1 (Configure)
spec = parse_model_id(user_model_input)

if spec.family == "unknown":
    console.print(f"[warning] Unknown model '{user_model_input}', using JSON emulation")
    
if spec.custom:
    console.print(f"[info] Custom model detected, inheriting {spec.family} capabilities")
```

#### H3: Observe Progress

**Journey**: User wants to see what's happening during tool calling.

**Current Gap**: Streaming shows text only, tool calls invisible until complete.

**RFC-136 Solution**:

```python
# Journey: H3 (Observe)
async for chunk in model.generate_stream_typed(prompt, tools):
    if chunk.type == StreamChunkType.TOOL_START:
        console.print(f"[tool] Calling {chunk.tool_name}...")
    elif chunk.type == StreamChunkType.TOOL_ARGS:
        console.print(f"[tool]   args: {chunk.partial_args[:50]}...")
    elif chunk.type == StreamChunkType.TOOL_END:
        console.print(f"[tool] ✓ {chunk.tool_name} complete")
    elif chunk.type == StreamChunkType.TEXT:
        console.print(chunk.content, end="")
```

#### H9: Debug Failure

**Journey**: Tool call failed, user wants to understand why.

**Current Gap**: Error is just a string like "Error: FileNotFoundError: foo.py"

**RFC-136 Solution**:

```python
# Journey: H9 (Debug)
error = ToolError.from_exception(e, "write_file")

# Rich error display
console.print(f"[error] Tool '{error.code.value}' error:")
console.print(f"  Message: {error.message}")
console.print(f"  Recoverable: {error.recoverable}")
if error.suggested_fix:
    console.print(f"  Suggestion: {error.suggested_fix}")
console.print(f"  Retry strategy: {error.retry_strategy}")
```

#### H11-H12: Switch/Add Models

**Journey**: User wants to use different or custom model.

**Current Gap**: 
- Switching mid-session doesn't re-route capabilities
- Custom models get no capabilities

**RFC-136 Solution**:

```python
# Journey: H11 (Switch)
# User: /model ollama/llama3.3:70b
new_spec = parse_model_id("ollama/llama3.3:70b")
new_capability = get_capability("ollama/llama3.3:70b")
console.print(f"Switched to {new_spec.family} v{new_spec.version}")
console.print(f"  Native tools: {new_capability.native_tools}")
console.print(f"  Parallel tools: {new_capability.parallel_tools}")

# Journey: H12 (Add custom)
# User's fine-tuned model: mycompany/llama3-ft
spec = parse_model_id("mycompany/llama3-ft")
# spec.custom=True, spec.family="llama", spec.version=(3,)
# Inherits Llama 3 capabilities automatically
```

---

### Edge Case Journeys

| ID | Journey | Description | RFC-136 Coverage |
|----|---------|-------------|------------------|
| **E1** | Model refuses tool call | Model outputs text instead of calling tool | `ToolCallNormalizer` + self-correction fallback |
| **E2** | Malformed JSON | Small model outputs invalid JSON | `_repair_json()` in normalizer |
| **E3** | Wrong tool name | Model hallucinates tool that doesn't exist | Pre-execution validation (existing introspection) |
| **E4** | Parallel call on non-parallel model | Model tries parallel but can't | `capability.parallel_tools` check |
| **E5** | Reasoning model during thinking | o1/R1 shouldn't call tools while thinking | `capability.supports_tool_choice_required=False` |
| **E6** | Context overflow | Too many tools for context window | `optimize_tool_definitions()` (see below) |
| **E7** | Provider rate limit | Hit API rate limit | `ToolError(code=RATE_LIMIT)` |
| **E8** | Network failure | Connection lost mid-stream | `ToolError(code=NETWORK)` |

#### E6: Context Overflow (NEW — Gap Identified)

**Journey**: User has 50 tools but model only has 8K context.

**Current Gap**: No handling — just sends all tools and hopes.

**RFC-136 Addition** (to be added):

```python
def optimize_tool_definitions(
    tools: tuple[Tool, ...],
    capability: ModelCapability,
    task_hint: str | None = None,
) -> tuple[Tool, ...]:
    """Optimize tool set for available context.
    
    Strategies:
    1. Truncate descriptions if context_window < 8K
    2. Remove optional parameters for simple tasks
    3. Prioritize tools matching task_hint
    4. Limit to top N tools if still too many
    
    Args:
        tools: All available tools
        capability: Model capabilities (for context_window)
        task_hint: Optional task description for prioritization
        
    Returns:
        Optimized tool set that fits context
    """
    if capability.context_window is None or capability.context_window >= 32000:
        return tools  # Plenty of room
    
    # Estimate tokens per tool (name + description + params)
    def estimate_tokens(tool: Tool) -> int:
        return len(tool.name) + len(tool.description) // 4 + len(str(tool.parameters)) // 4
    
    # Budget: 20% of context for tools
    tool_budget = capability.context_window // 5
    
    # Sort by relevance to task_hint if provided
    if task_hint:
        tools = _sort_by_relevance(tools, task_hint)
    
    # Greedily select tools within budget
    selected = []
    used_tokens = 0
    for tool in tools:
        tokens = estimate_tokens(tool)
        if used_tokens + tokens <= tool_budget:
            selected.append(tool)
            used_tokens += tokens
        else:
            break
    
    return tuple(selected)
```

---

### Journey Coverage Matrix

| Journey Type | Total | Covered | Gap |
|--------------|-------|---------|-----|
| **Agent Internal (A1-A11)** | 11 | 11 | 0 |
| **Human External (H1-H12)** | 12 | 12 | 0 |
| **Edge Cases (E1-E8)** | 8 | 7 | 1 (E6 added above) |
| **Total** | 31 | 30 | 1 → 0 |

✅ **All journeys now have tier-S coverage.**

---

## 🏗️ Technical Design

### 1. Structured Model Parsing

Replace brittle string matching with structured parsing.

```python
# src/sunwell/models/capability/parser.py

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Parsed model specification.
    
    Examples:
        "gpt-4o" → family="gpt", version=(4,), variant="o"
        "claude-3.5-sonnet" → family="claude", version=(3,5), variant="sonnet"
        "llama3.3:70b" → family="llama", version=(3,3), size=70_000_000_000
        "ollama/qwen3:32b" → family="qwen", version=(3,), size=32B, provider="ollama"
        "mycompany/llama3-ft-v2" → family="llama", version=(3,), org="mycompany", custom=True
    """
    family: str
    version: tuple[int, ...] = ()
    variant: str | None = None
    size: int | None = None  # Parameter count in billions
    provider: str | None = None  # ollama, openai, anthropic, together, etc.
    org: str | None = None  # Organization prefix
    custom: bool = False  # Fine-tuned or custom model


# Compiled regex patterns for O(1) matching
_PATTERNS = {
    # OpenAI: gpt-4o, gpt-4-turbo, o1-preview
    "openai": re.compile(
        r"^(?P<family>gpt|o\d+)(?:-(?P<version>[\d.]+))?(?:-(?P<variant>\w+))?$"
    ),
    # Anthropic: claude-3.5-sonnet, claude-3-opus
    "anthropic": re.compile(
        r"^(?P<family>claude)(?:-(?P<version>[\d.]+))?(?:-(?P<variant>\w+))?$"
    ),
    # Llama: llama3.3:70b, llama3.1-8b, meta-llama/Llama-3.3-70B-Instruct
    "llama": re.compile(
        r"^(?:(?P<org>[\w-]+)/)?(?P<family>llama|Llama)[\s-]?(?P<version>[\d.]+)"
        r"(?:[:-](?P<size>\d+)[Bb])?(?:-(?P<variant>\w+))?$"
    ),
    # Qwen: qwen2.5, qwen3:32b
    "qwen": re.compile(
        r"^(?P<family>qwen)(?P<version>[\d.]+)?(?:[:-](?P<size>\d+)[Bb])?$"
    ),
    # Mistral: mistral-large, mixtral-8x7b
    "mistral": re.compile(
        r"^(?P<family>mistral|mixtral)(?:-(?P<variant>\w+))?(?:-(?P<size>[\dx\d]+)[Bb])?$"
    ),
    # Gemini: gemini-2.0-flash, gemini-1.5-pro
    "gemini": re.compile(
        r"^(?P<family>gemini)(?:-(?P<version>[\d.]+))?(?:-(?P<variant>\w+))?$"
    ),
    # DeepSeek: deepseek-r1, deepseek-v3
    "deepseek": re.compile(
        r"^(?P<family>deepseek)(?:-(?P<variant>[rv]\d+))?$"
    ),
}


def parse_model_id(model_id: str) -> ModelSpec:
    """Parse a model ID into structured components.
    
    Handles:
    - Provider prefixes (ollama/, together/)
    - Version numbers (3.5, 3.3, 4)
    - Size suffixes (:70b, -8b)
    - Variants (sonnet, turbo, instruct)
    - Custom/fine-tuned models
    
    Args:
        model_id: Raw model identifier from configuration
        
    Returns:
        ModelSpec with parsed components
    """
    original = model_id
    provider = None
    org = None
    
    # Extract provider prefix (ollama/, together/)
    if "/" in model_id:
        parts = model_id.split("/", 1)
        if parts[0].lower() in ("ollama", "together", "anyscale", "fireworks", "groq"):
            provider = parts[0].lower()
            model_id = parts[1]
        elif not parts[0].startswith("meta") and not parts[0].startswith("mistral"):
            # Organization prefix (mycompany/model)
            org = parts[0]
            model_id = parts[1]
    
    # Normalize for matching
    model_lower = model_id.lower()
    
    # Try each pattern
    for family_hint, pattern in _PATTERNS.items():
        match = pattern.match(model_id) or pattern.match(model_lower)
        if match:
            groups = match.groupdict()
            
            # Parse version
            version_str = groups.get("version", "")
            version = tuple(int(x) for x in version_str.split(".") if x.isdigit()) if version_str else ()
            
            # Parse size
            size_str = groups.get("size", "")
            size = _parse_size(size_str) if size_str else None
            
            return ModelSpec(
                family=groups.get("family", family_hint).lower(),
                version=version,
                variant=groups.get("variant"),
                size=size,
                provider=provider,
                org=org,
                custom=org is not None and org not in ("meta", "mistralai", "google"),
            )
    
    # Unknown model — extract what we can
    return ModelSpec(
        family=_extract_family(model_id),
        provider=provider,
        org=org,
        custom=True,  # Assume custom if unknown
    )


def _parse_size(size_str: str) -> int | None:
    """Parse size string to parameter count.
    
    Examples:
        "70" → 70_000_000_000
        "8x7" → 56_000_000_000 (MoE)
        "1.5" → 1_500_000_000
    """
    if not size_str:
        return None
    
    # Handle MoE format (8x7)
    if "x" in size_str.lower():
        parts = size_str.lower().split("x")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) * int(parts[1]) * 1_000_000_000
    
    # Handle decimal (1.5b)
    try:
        return int(float(size_str) * 1_000_000_000)
    except ValueError:
        return None


def _extract_family(model_id: str) -> str:
    """Extract family name from unknown model ID."""
    # Remove common suffixes
    clean = re.sub(r"[-_]?(instruct|chat|base|v\d+|ft|tuned).*$", "", model_id, flags=re.I)
    # Take first word-like segment
    match = re.match(r"^[a-zA-Z]+", clean)
    return match.group(0).lower() if match else "unknown"
```

### 2. Capability Registry with Version Awareness

```python
# src/sunwell/models/capability/registry.py

from dataclasses import dataclass
from typing import Callable

from sunwell.models.capability.parser import ModelSpec, parse_model_id


@dataclass(frozen=True, slots=True)
class ModelCapability:
    """Capabilities for intelligent routing and adaptation."""
    
    native_tools: bool = False
    """Model supports structured tool/function calling."""
    
    parallel_tools: bool = False
    """Model can call multiple tools in one turn."""
    
    tool_streaming: bool = False
    """Model supports streaming tool call arguments."""
    
    json_mode: bool = False
    """Model has reliable JSON output mode."""
    
    reasoning: bool = False
    """Model supports extended thinking (o1, DeepSeek-R1, etc.)."""
    
    max_output_tokens: int | None = None
    context_window: int | None = None
    
    # Tool calling quirks
    needs_tool_schema_strict: bool = False
    """Anthropic-style strict schema validation."""
    
    tool_result_in_user_message: bool = False
    """Anthropic: tool results go in user message, not tool role."""
    
    supports_tool_choice_required: bool = True
    """Model supports tool_choice: required."""
    
    emulation_style: str = "json"
    """For non-native: 'json', 'xml', or 'markdown'."""


# Version-aware capability matchers
CapabilityMatcher = Callable[[ModelSpec], ModelCapability | None]


def _match_gpt(spec: ModelSpec) -> ModelCapability | None:
    """Match GPT family capabilities."""
    if spec.family != "gpt":
        return None
    
    # GPT-4o and later
    if spec.version >= (4,) and spec.variant == "o":
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            max_output_tokens=16384,
            context_window=128000,
        )
    
    # GPT-4 Turbo
    if spec.version >= (4,) and spec.variant == "turbo":
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=4096,
            context_window=128000,
        )
    
    # GPT-4 base
    if spec.version >= (4,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            max_output_tokens=8192,
            context_window=8192,
        )
    
    # GPT-3.5
    if spec.version >= (3, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=4096,
            context_window=16385,
        )
    
    return None


def _match_o_series(spec: ModelSpec) -> ModelCapability | None:
    """Match OpenAI o1/o3 reasoning models."""
    if not spec.family.startswith("o") or not spec.family[1:].isdigit():
        return None
    
    return ModelCapability(
        native_tools=True,
        parallel_tools=True,
        reasoning=True,
        max_output_tokens=100000,
        context_window=200000,
        # o1 doesn't support tool_choice: required during reasoning
        supports_tool_choice_required=False,
    )


def _match_claude(spec: ModelSpec) -> ModelCapability | None:
    """Match Claude family capabilities."""
    if spec.family != "claude":
        return None
    
    # Claude 4 (Opus 4, Sonnet 4)
    if spec.version >= (4,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            reasoning=True,
            max_output_tokens=64000,
            context_window=200000,
            needs_tool_schema_strict=True,
            tool_result_in_user_message=True,
        )
    
    # Claude 3.5 (Sonnet, Haiku)
    if spec.version >= (3, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            max_output_tokens=8192,
            context_window=200000,
            needs_tool_schema_strict=True,
            tool_result_in_user_message=True,
        )
    
    # Claude 3 (Opus, Sonnet, Haiku)
    if spec.version >= (3,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            max_output_tokens=4096,
            context_window=200000,
            needs_tool_schema_strict=True,
            tool_result_in_user_message=True,
        )
    
    return None


def _match_llama(spec: ModelSpec) -> ModelCapability | None:
    """Match Llama family capabilities."""
    if spec.family != "llama":
        return None
    
    # Llama 3.3 (70B+)
    if spec.version >= (3, 3):
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,  # Llama struggles with parallel
            json_mode=True,
            max_output_tokens=8192,
            context_window=128000,
        )
    
    # Llama 3.1/3.2
    if spec.version >= (3, 1):
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            max_output_tokens=8192,
            context_window=128000,
        )
    
    # Llama 3.0
    if spec.version >= (3,):
        size = spec.size or 8_000_000_000
        if size >= 70_000_000_000:
            return ModelCapability(
                native_tools=True,
                parallel_tools=False,
                max_output_tokens=4096,
                context_window=8192,
            )
        else:
            # Smaller Llama 3 models need emulation
            return ModelCapability(
                native_tools=False,
                json_mode=True,
                emulation_style="json",
            )
    
    # Llama 2 and earlier
    return ModelCapability(
        native_tools=False,
        emulation_style="json",
    )


def _match_qwen(spec: ModelSpec) -> ModelCapability | None:
    """Match Qwen family capabilities."""
    if spec.family != "qwen":
        return None
    
    # Qwen 3
    if spec.version >= (3,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            reasoning=True,
            max_output_tokens=8192,
            context_window=128000,
        )
    
    # Qwen 2.5
    if spec.version >= (2, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            max_output_tokens=8192,
            context_window=32768,
        )
    
    # Older Qwen
    return ModelCapability(
        native_tools=False,
        json_mode=True,
        emulation_style="json",
    )


def _match_mistral(spec: ModelSpec) -> ModelCapability | None:
    """Match Mistral/Mixtral family capabilities."""
    if spec.family not in ("mistral", "mixtral"):
        return None
    
    # Mistral Large
    if spec.variant == "large":
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=8192,
            context_window=128000,
        )
    
    # Mixtral
    if spec.family == "mixtral":
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            max_output_tokens=4096,
            context_window=32768,
        )
    
    # Base Mistral
    return ModelCapability(
        native_tools=True,
        parallel_tools=False,
        max_output_tokens=4096,
        context_window=32768,
    )


def _match_gemini(spec: ModelSpec) -> ModelCapability | None:
    """Match Gemini family capabilities."""
    if spec.family != "gemini":
        return None
    
    # Gemini 2.0
    if spec.version >= (2,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            reasoning=True,
            max_output_tokens=8192,
            context_window=1000000,
        )
    
    # Gemini 1.5
    if spec.version >= (1, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=8192,
            context_window=1000000,
        )
    
    return None


def _match_deepseek(spec: ModelSpec) -> ModelCapability | None:
    """Match DeepSeek family capabilities."""
    if spec.family != "deepseek":
        return None
    
    # DeepSeek R1 (reasoning)
    if spec.variant == "r1":
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            reasoning=True,
            max_output_tokens=8192,
            context_window=64000,
        )
    
    # DeepSeek V3
    if spec.variant == "v3":
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            max_output_tokens=8192,
            context_window=64000,
        )
    
    return None


# Models that don't support native tools
_NO_NATIVE_TOOLS = frozenset({
    "gemma", "phi", "codellama", "starcoder", "yi", "falcon",
})


def _match_no_tools(spec: ModelSpec) -> ModelCapability | None:
    """Match models known to not support native tools."""
    if spec.family in _NO_NATIVE_TOOLS:
        return ModelCapability(
            native_tools=False,
            emulation_style="json",
        )
    return None


# Ordered list of matchers (first match wins)
_MATCHERS: list[CapabilityMatcher] = [
    _match_o_series,
    _match_gpt,
    _match_claude,
    _match_llama,
    _match_qwen,
    _match_mistral,
    _match_gemini,
    _match_deepseek,
    _match_no_tools,
]


def get_capability(model_id: str) -> ModelCapability:
    """Get capabilities for a model ID.
    
    Uses structured parsing + version-aware matchers for accurate routing.
    
    Args:
        model_id: Raw model identifier
        
    Returns:
        ModelCapability with appropriate settings
    """
    spec = parse_model_id(model_id)
    
    for matcher in _MATCHERS:
        result = matcher(spec)
        if result is not None:
            return result
    
    # Unknown model — conservative defaults
    # Custom/fine-tuned models inherit base model capabilities
    if spec.custom and spec.family != "unknown":
        # Try to match the base family
        base_spec = ModelSpec(family=spec.family, version=spec.version)
        for matcher in _MATCHERS:
            result = matcher(base_spec)
            if result is not None:
                return result
    
    # Truly unknown — assume no native tools, use JSON emulation
    return ModelCapability(
        native_tools=False,
        emulation_style="json",
    )
```

### 3. Unified Schema Translator

```python
# src/sunwell/models/capability/schema.py

from dataclasses import dataclass
from typing import Literal, Protocol

from sunwell.models.protocol import Tool


class SchemaAdapter(Protocol):
    """Protocol for provider-specific schema conversion."""
    
    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        """Convert Sunwell tools to provider format."""
        ...
    
    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        """Convert tool_choice to provider format."""
        ...


@dataclass(frozen=True, slots=True)
class OpenAISchemaAdapter:
    """OpenAI function calling schema format.
    
    Research Insight: OpenAI's strict mode achieves 100% schema accuracy
    vs ~40% without. Enable by default for reliable tool calling.
    """
    
    strict_mode: bool = True
    """Enable strict schema validation (100% vs ~40% accuracy)."""
    
    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": self._validate_schema(t.parameters),
                    **({"strict": True} if self.strict_mode else {}),
                },
            }
            for t in tools
        ]
    
    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        if choice is None or isinstance(choice, dict):
            return choice
        if choice in ("auto", "none", "required"):
            return choice
        # Force specific tool
        return {"type": "function", "function": {"name": choice}}
    
    def _validate_schema(self, schema: dict) -> dict:
        """Validate and normalize JSON Schema for OpenAI."""
        # Ensure required fields
        if "type" not in schema:
            schema = {"type": "object", **schema}
        return schema


@dataclass(frozen=True, slots=True)
class AnthropicSchemaAdapter:
    """Anthropic tool schema format."""
    
    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": self._strict_schema(t.parameters),
            }
            for t in tools
        ]
    
    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> dict | None:
        if choice is None:
            return None
        if isinstance(choice, dict):
            return choice
        if choice == "auto":
            return {"type": "auto"}
        if choice == "none":
            return None  # Anthropic: don't send tools
        if choice == "required":
            return {"type": "any"}
        # Force specific tool
        return {"type": "tool", "name": choice}
    
    def _strict_schema(self, schema: dict) -> dict:
        """Ensure schema meets Anthropic's strict requirements."""
        result = dict(schema)
        
        # Must have type: object at root
        if result.get("type") != "object":
            result["type"] = "object"
        
        # Must have properties
        if "properties" not in result:
            result["properties"] = {}
        
        # additionalProperties should be false for strict mode
        result["additionalProperties"] = False
        
        return result


@dataclass(frozen=True, slots=True)
class OllamaSchemaAdapter:
    """Ollama tool schema format (OpenAI-compatible with quirks)."""
    
    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description[:500],  # Ollama truncates
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]
    
    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        if choice is None or isinstance(choice, dict):
            return choice
        if choice in ("auto", "none", "required"):
            return choice
        return {"type": "function", "function": {"name": choice}}


def get_schema_adapter(provider: str) -> SchemaAdapter:
    """Get the appropriate schema adapter for a provider.
    
    Args:
        provider: Provider name (openai, anthropic, ollama, etc.)
        
    Returns:
        SchemaAdapter for the provider
    """
    adapters: dict[str, SchemaAdapter] = {
        "openai": OpenAISchemaAdapter(),
        "anthropic": AnthropicSchemaAdapter(),
        "ollama": OllamaSchemaAdapter(),
        "together": OpenAISchemaAdapter(),
        "groq": OpenAISchemaAdapter(),
        "fireworks": OpenAISchemaAdapter(),
    }
    return adapters.get(provider, OpenAISchemaAdapter())
```

### 4. Adaptive Tool Emulation Prompts

```python
# src/sunwell/models/capability/emulation.py

from sunwell.models.capability.registry import ModelCapability
from sunwell.models.protocol import Tool


def format_tool_descriptions(tools: tuple[Tool, ...], compact: bool = False) -> str:
    """Format tools for prompt injection.
    
    Args:
        tools: Available tools
        compact: If True, use minimal format for small contexts
        
    Returns:
        Formatted tool descriptions
    """
    lines = []
    for tool in tools:
        if compact:
            # Minimal format for small models
            params = tool.parameters.get("properties", {})
            param_names = ", ".join(params.keys())
            lines.append(f"- {tool.name}({param_names}): {tool.description[:80]}")
        else:
            # Full format
            lines.append(f"### {tool.name}")
            lines.append(tool.description)
            params = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])
            if params:
                lines.append("Parameters:")
                for name, schema in params.items():
                    req = " (required)" if name in required else ""
                    desc = schema.get("description", "")[:60]
                    lines.append(f"  - {name}{req}: {desc}")
            lines.append("")
    return "\n".join(lines)


# Prompts optimized for different model capabilities
_STANDARD_PROMPT = """You have access to tools. When you need to use a tool, output ONLY a JSON block:

```json
{{"tool": "tool_name", "arguments": {{"arg1": "value1"}}}}
```

Available tools:
{tool_descriptions}

RULES:
1. Output ONLY the JSON block when calling a tool - no other text
2. For code tasks, use write_file tool - do NOT output code directly
3. After tool execution, you'll see the result and can continue
"""

_COMPACT_PROMPT = """Tools available. Call with JSON:
{{"tool": "NAME", "arguments": {{...}}}}

{tool_descriptions}

Output ONLY JSON when calling tools."""

_PARALLEL_PROMPT = """You have access to tools. You can call multiple tools in one response.

When calling tools, output JSON blocks (one per tool):

```json
{{"tool": "tool1", "arguments": {{...}}}}
```

```json
{{"tool": "tool2", "arguments": {{...}}}}
```

Available tools:
{tool_descriptions}
"""

_XML_PROMPT = """You have access to tools. When calling a tool, use this format:

<tool_call>
<name>tool_name</name>
<arguments>
<arg1>value1</arg1>
<arg2>value2</arg2>
</arguments>
</tool_call>

Available tools:
{tool_descriptions}
"""


def build_emulation_prompt(
    tools: tuple[Tool, ...],
    capability: ModelCapability,
    task_hint: str | None = None,
) -> str:
    """Build a model-appropriate tool emulation prompt.
    
    Adapts prompt complexity based on:
    - Context window size
    - Parallel tool support
    - Preferred emulation style
    
    Args:
        tools: Available tools
        capability: Model capabilities
        task_hint: Optional hint about task complexity
        
    Returns:
        Formatted prompt for tool emulation
    """
    # Determine if we need compact format
    compact = (
        capability.context_window is not None
        and capability.context_window < 8192
    )
    
    tool_descriptions = format_tool_descriptions(tools, compact=compact)
    
    # Select prompt template
    if capability.emulation_style == "xml":
        template = _XML_PROMPT
    elif capability.parallel_tools:
        template = _PARALLEL_PROMPT
    elif compact:
        template = _COMPACT_PROMPT
    else:
        template = _STANDARD_PROMPT
    
    return template.format(tool_descriptions=tool_descriptions)


def optimize_tool_definitions(
    tools: tuple[Tool, ...],
    capability: ModelCapability,
    task_hint: str | None = None,
) -> tuple[Tool, ...]:
    """Optimize tool set for available context (Journey E6).
    
    When models have limited context windows, we need to:
    1. Prioritize tools relevant to the task
    2. Truncate verbose descriptions
    3. Remove optional parameters if needed
    4. Limit total tool count
    
    Args:
        tools: All available tools
        capability: Model capabilities (for context_window)
        task_hint: Optional task description for prioritization
        
    Returns:
        Optimized tool set that fits context
    """
    context_window = capability.context_window or 128000
    
    # Plenty of room — no optimization needed
    if context_window >= 32000:
        return tools
    
    def estimate_tokens(tool: Tool) -> int:
        """Estimate token count for a tool definition."""
        return len(tool.name) + len(tool.description) // 4 + len(str(tool.parameters)) // 4
    
    # Budget: 20% of context for tools
    tool_budget = context_window // 5
    
    # Sort by relevance if task_hint provided
    if task_hint:
        task_lower = task_hint.lower()
        
        def relevance_score(tool: Tool) -> float:
            score = 0.0
            # Name match
            if tool.name.lower() in task_lower:
                score += 10.0
            # Description overlap
            desc_words = set(tool.description.lower().split())
            task_words = set(task_lower.split())
            overlap = len(desc_words & task_words)
            score += overlap * 0.5
            return score
        
        tools = tuple(sorted(tools, key=relevance_score, reverse=True))
    
    # Greedily select tools within budget
    selected: list[Tool] = []
    used_tokens = 0
    
    for tool in tools:
        tokens = estimate_tokens(tool)
        
        # Try truncating description for small contexts
        if context_window < 8192 and tokens > 200:
            truncated = Tool(
                name=tool.name,
                description=tool.description[:200] + "...",
                parameters=tool.parameters,
            )
            tokens = estimate_tokens(truncated)
            tool = truncated
        
        if used_tokens + tokens <= tool_budget:
            selected.append(tool)
            used_tokens += tokens
        else:
            break
    
    return tuple(selected)
```

### 5. Typed Streaming with Tool Awareness

```python
# src/sunwell/models/capability/streaming.py

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class StreamChunkType(Enum):
    """Types of chunks in a tool-aware stream."""
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_ARGS = "tool_args"
    TOOL_END = "tool_end"
    THINKING = "thinking"


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A typed chunk from tool-aware streaming.
    
    Provides visibility into tool calling during streaming,
    rather than hiding tool calls until generation completes.
    """
    
    type: StreamChunkType
    """What kind of content this chunk contains."""
    
    content: str | None = None
    """Text content (for TEXT and THINKING chunks)."""
    
    tool_name: str | None = None
    """Tool being called (for TOOL_* chunks)."""
    
    tool_call_id: str | None = None
    """Unique ID for this tool call."""
    
    partial_args: str | None = None
    """Partial JSON arguments (for TOOL_ARGS chunks)."""
    
    is_complete: bool = False
    """For TOOL_END: whether arguments are complete."""


class ToolStreamParser:
    """Parse streaming response into typed chunks.
    
    Handles incremental JSON parsing for tool call arguments.
    """
    
    def __init__(self) -> None:
        self._buffer = ""
        self._in_tool_call = False
        self._current_tool_id: str | None = None
        self._current_tool_name: str | None = None
        self._args_buffer = ""
    
    def feed(self, raw_chunk: str) -> list[StreamChunk]:
        """Feed a raw chunk and return typed chunks.
        
        Args:
            raw_chunk: Raw text from model stream
            
        Returns:
            List of typed StreamChunks (may be empty)
        """
        chunks: list[StreamChunk] = []
        self._buffer += raw_chunk
        
        # Check for tool call start patterns
        if not self._in_tool_call:
            # Look for JSON tool call pattern
            if '{"tool"' in self._buffer or "```json" in self._buffer:
                text_before = self._buffer.split('{"tool"')[0].split("```json")[0]
                if text_before.strip():
                    chunks.append(StreamChunk(
                        type=StreamChunkType.TEXT,
                        content=text_before,
                    ))
                self._in_tool_call = True
                self._current_tool_id = f"stream_{id(self)}"
                self._args_buffer = ""
                chunks.append(StreamChunk(
                    type=StreamChunkType.TOOL_START,
                    tool_call_id=self._current_tool_id,
                ))
                self._buffer = self._buffer[len(text_before):]
        
        if self._in_tool_call:
            # Accumulate args
            self._args_buffer += self._buffer
            self._buffer = ""
            
            # Try to extract tool name
            if self._current_tool_name is None and '"tool"' in self._args_buffer:
                import re
                match = re.search(r'"tool"\s*:\s*"([^"]+)"', self._args_buffer)
                if match:
                    self._current_tool_name = match.group(1)
            
            # Emit partial args
            if self._args_buffer:
                chunks.append(StreamChunk(
                    type=StreamChunkType.TOOL_ARGS,
                    tool_name=self._current_tool_name,
                    tool_call_id=self._current_tool_id,
                    partial_args=self._args_buffer,
                ))
            
            # Check for tool call end (closing brace + optional fence)
            if self._args_buffer.rstrip().endswith("}") or self._args_buffer.rstrip().endswith("```"):
                chunks.append(StreamChunk(
                    type=StreamChunkType.TOOL_END,
                    tool_name=self._current_tool_name,
                    tool_call_id=self._current_tool_id,
                    is_complete=True,
                ))
                self._in_tool_call = False
                self._current_tool_id = None
                self._current_tool_name = None
                self._args_buffer = ""
        else:
            # Regular text
            if self._buffer:
                chunks.append(StreamChunk(
                    type=StreamChunkType.TEXT,
                    content=self._buffer,
                ))
                self._buffer = ""
        
        return chunks
```

### 6. Structured Tool Errors

```python
# src/sunwell/tools/errors.py

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ToolErrorCode(Enum):
    """Categorized tool error codes for intelligent handling."""
    
    VALIDATION = "validation"
    """Bad arguments (missing, wrong type, invalid format)."""
    
    PERMISSION = "permission"
    """Path security, trust level insufficient."""
    
    NOT_FOUND = "not_found"
    """File, resource, or tool not found."""
    
    TIMEOUT = "timeout"
    """Operation timed out."""
    
    RATE_LIMIT = "rate_limit"
    """Rate limit exceeded."""
    
    MODEL_REFUSAL = "model_refusal"
    """Model refused to call tool or provided invalid call."""
    
    EXECUTION = "execution"
    """Runtime error during tool execution."""
    
    NETWORK = "network"
    """Network-related failure (for web tools)."""


@dataclass(frozen=True, slots=True)
class ToolError:
    """Structured tool execution error with recovery hints.
    
    Enables intelligent retry strategies based on error type.
    """
    
    code: ToolErrorCode
    """Categorized error code."""
    
    message: str
    """Human-readable error message."""
    
    recoverable: bool
    """Whether this error might succeed on retry."""
    
    retry_strategy: Literal["same", "rephrase", "escalate", "abort"] | None = None
    """Suggested retry approach:
    - same: Retry with identical arguments (transient error)
    - rephrase: Have model try different arguments
    - escalate: Use more capable strategy (interference/vortex)
    - abort: Don't retry, escalate to user
    """
    
    suggested_fix: str | None = None
    """Specific suggestion for fixing the error."""
    
    details: dict | None = None
    """Additional error context."""
    
    @classmethod
    def from_exception(cls, e: Exception, tool_name: str) -> "ToolError":
        """Create ToolError from a Python exception.
        
        Maps exception types to error codes and recovery strategies.
        
        Research Insight: Error responses should steer agents toward
        better behavior with specific, actionable guidance.
        """
        if isinstance(e, FileNotFoundError):
            return cls(
                code=ToolErrorCode.NOT_FOUND,
                message=str(e),
                recoverable=True,
                retry_strategy="rephrase",
                # Actionable multi-step guidance per MCP research
                suggested_fix=(
                    "File not found. Try:\n"
                    "1. Use list_files to see available files in the directory\n"
                    "2. Check if path is relative vs absolute\n"
                    "3. Verify the parent directory exists"
                ),
            )
        
        if isinstance(e, PermissionError):
            return cls(
                code=ToolErrorCode.PERMISSION,
                message=str(e),
                recoverable=False,
                retry_strategy="abort",
                suggested_fix=(
                    "Permission denied. This path may be:\n"
                    "• Outside the workspace directory\n"
                    "• A protected system file\n"
                    "• Blocked by security policy"
                ),
            )
        
        if isinstance(e, TimeoutError):
            return cls(
                code=ToolErrorCode.TIMEOUT,
                message=f"Tool {tool_name} timed out",
                recoverable=True,
                retry_strategy="same",
                suggested_fix=(
                    "Operation timed out. Try:\n"
                    "1. Break into smaller operations\n"
                    "2. Use more specific filters/parameters\n"
                    "3. Check if the resource is responding"
                ),
            )
        
        if "rate limit" in str(e).lower():
            return cls(
                code=ToolErrorCode.RATE_LIMIT,
                message=str(e),
                recoverable=True,
                retry_strategy="same",
                suggested_fix=(
                    "Rate limited. The operation will be retried automatically.\n"
                    "Consider batching similar operations to reduce API calls."
                ),
            )
        
        # Check for network-related errors
        error_str = str(e).lower()
        if any(word in error_str for word in ["connection", "network", "dns", "socket"]):
            return cls(
                code=ToolErrorCode.NETWORK,
                message=str(e),
                recoverable=True,
                retry_strategy="same",
                suggested_fix=(
                    "Network error. This is usually transient.\n"
                    "The operation will be retried automatically."
                ),
            )
        
        # Default: execution error
        return cls(
            code=ToolErrorCode.EXECUTION,
            message=str(e),
            recoverable=True,
            retry_strategy="escalate",
            suggested_fix=(
                f"Tool '{tool_name}' failed unexpectedly.\n"
                "Consider trying with different parameters or an alternative approach."
            ),
            details={"exception_type": type(e).__name__},
        )


def should_retry(error: ToolError, attempt: int, max_attempts: int = 3) -> bool:
    """Determine if a tool call should be retried.
    
    Args:
        error: The error that occurred
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum retry attempts
        
    Returns:
        True if should retry
    """
    if not error.recoverable:
        return False
    
    if attempt >= max_attempts:
        return False
    
    if error.retry_strategy == "abort":
        return False
    
    return True


def get_retry_strategy(error: ToolError, attempt: int) -> str:
    """Get the appropriate retry strategy based on error and attempt.
    
    Escalates strategy as attempts increase.
    
    Args:
        error: The error that occurred
        attempt: Current attempt number
        
    Returns:
        Strategy name: "same", "rephrase", "interference", "vortex"
    """
    if error.retry_strategy == "same":
        return "same"
    
    if error.retry_strategy == "rephrase":
        if attempt == 1:
            return "rephrase"
        if attempt == 2:
            return "interference"
        return "vortex"
    
    if error.retry_strategy == "escalate":
        if attempt == 1:
            return "same"
        if attempt == 2:
            return "interference"
        return "vortex"
    
    return "same"
```

### 7. Model-Specific Tool Call Normalization

```python
# src/sunwell/models/capability/normalizer.py

import json
import re
from dataclasses import dataclass

from sunwell.models.protocol import ToolCall


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Result of tool call normalization."""
    
    tool_calls: tuple[ToolCall, ...]
    """Normalized tool calls."""
    
    repairs: tuple[str, ...]
    """Repairs made during normalization."""
    
    remaining_text: str
    """Text not part of tool calls."""


class ToolCallNormalizer:
    """Normalize tool calls from different model formats.
    
    Handles model-specific quirks:
    - Llama: Extra whitespace, inconsistent JSON
    - Qwen: Sometimes uses 'function' key instead of 'tool'
    - Small models: Nested arguments, missing fields
    """
    
    # Patterns for extracting tool calls
    _JSON_BLOCK = re.compile(
        r'```(?:json)?\s*\n?(\{[^`]+\})\s*\n?```',
        re.DOTALL,
    )
    _INLINE_JSON = re.compile(
        r'\{["\'](?:tool|function)["\']:\s*["\'][^}]+\}',
        re.DOTALL,
    )
    
    def normalize(
        self,
        response_text: str,
        model_family: str | None = None,
    ) -> NormalizationResult:
        """Normalize tool calls from model response.
        
        Args:
            response_text: Raw model response text
            model_family: Model family for family-specific handling
            
        Returns:
            NormalizationResult with parsed tool calls
        """
        tool_calls: list[ToolCall] = []
        repairs: list[str] = []
        remaining = response_text
        
        # Extract JSON blocks
        for match in self._JSON_BLOCK.finditer(response_text):
            json_str = match.group(1)
            tc, repair = self._parse_tool_json(json_str, model_family)
            if tc:
                tool_calls.append(tc)
                repairs.extend(repair)
                remaining = remaining.replace(match.group(0), "", 1)
        
        # Extract inline JSON
        for match in self._INLINE_JSON.finditer(remaining):
            json_str = match.group(0)
            tc, repair = self._parse_tool_json(json_str, model_family)
            if tc:
                tool_calls.append(tc)
                repairs.extend(repair)
                remaining = remaining.replace(match.group(0), "", 1)
        
        return NormalizationResult(
            tool_calls=tuple(tool_calls),
            repairs=tuple(repairs),
            remaining_text=remaining.strip(),
        )
    
    def _parse_tool_json(
        self,
        json_str: str,
        model_family: str | None,
    ) -> tuple[ToolCall | None, list[str]]:
        """Parse a JSON string into a ToolCall.
        
        Handles model-specific quirks and repairs common issues.
        """
        repairs: list[str] = []
        
        # Clean up common issues
        json_str = json_str.strip()
        
        # Llama: Often adds trailing commas
        if model_family == "llama":
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            if json_str != json_str.strip():
                repairs.append("Removed trailing commas (Llama quirk)")
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to repair common JSON errors
            repaired = self._repair_json(json_str)
            if repaired:
                repairs.append("Repaired malformed JSON")
                try:
                    data = json.loads(repaired)
                except json.JSONDecodeError:
                    return None, repairs
            else:
                return None, repairs
        
        # Extract tool name
        tool_name = data.get("tool") or data.get("function") or data.get("name")
        if not tool_name:
            return None, repairs
        
        if "function" in data and "tool" not in data:
            repairs.append("Mapped 'function' key to 'tool' (Qwen quirk)")
        
        # Extract arguments
        args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
        
        if "args" in data and "arguments" not in data:
            repairs.append("Mapped 'args' key to 'arguments'")
        
        # Handle nested arguments (small model quirk)
        if "arguments" in args:
            repairs.append("Unnested double-wrapped arguments")
            args = args["arguments"]
        
        # Generate ID
        tool_id = f"normalized_{hash(json_str) % 10000}"
        
        return ToolCall(id=tool_id, name=tool_name, arguments=args), repairs
    
    def _repair_json(self, json_str: str) -> str | None:
        """Attempt to repair malformed JSON.
        
        Common repairs:
        - Single quotes → double quotes
        - Unquoted keys
        - Trailing commas
        """
        repaired = json_str
        
        # Single quotes to double quotes
        repaired = re.sub(r"'([^']*)'", r'"\1"', repaired)
        
        # Unquoted keys
        repaired = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', repaired)
        
        # Trailing commas
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
        
        return repaired if repaired != json_str else None
```

### 8. Tool Description Engineering

> **Research Insight**: Per Anthropic, "We spent more time optimizing our tools than the overall prompt" on SWE-bench. Tool descriptions are prompts to the model.

```python
# src/sunwell/models/capability/tool_engineering.py

from dataclasses import dataclass
from sunwell.models.protocol import Tool


@dataclass(frozen=True, slots=True)
class ToolDescriptionQuality:
    """Quality metrics for tool descriptions.
    
    Based on Anthropic/MCP guidance: treat tool descriptions like
    onboarding docs for a new team member.
    """
    
    has_example_usage: bool = False
    """Description includes usage example (e.g., 'e.g.', 'example:')."""
    
    has_edge_cases: bool = False
    """Description mentions edge cases or warnings."""
    
    has_input_format: bool = False
    """Description specifies expected input format."""
    
    has_clear_boundaries: bool = False
    """Description clarifies when NOT to use this tool."""
    
    params_unambiguous: bool = False
    """Parameter names are specific (user_id not user)."""
    
    @property
    def score(self) -> float:
        """Quality score from 0.0 to 1.0."""
        checks = [
            self.has_example_usage,
            self.has_edge_cases,
            self.has_input_format,
            self.has_clear_boundaries,
            self.params_unambiguous,
        ]
        return sum(checks) / len(checks)


def audit_tool_description(tool: Tool) -> ToolDescriptionQuality:
    """Audit a tool's description for LLM-friendliness.
    
    Per Anthropic: "Put yourself in the model's shoes. Is it obvious
    how to use this tool based on the description and parameters?"
    
    Args:
        tool: Tool to audit
        
    Returns:
        ToolDescriptionQuality with audit results
    """
    desc = tool.description.lower()
    params = tool.parameters.get("properties", {})
    
    # Check for example usage
    has_example = any(
        marker in desc 
        for marker in ["example", "e.g.", "for instance", "such as", "like:"]
    )
    
    # Check for edge case documentation
    has_edges = any(
        marker in desc
        for marker in ["note:", "warning:", "caution:", "important:", "edge case"]
    )
    
    # Check for input format specification
    has_format = any(
        marker in desc
        for marker in ["format:", "must be", "should be", "expects", "accepts"]
    )
    
    # Check for clear boundaries
    has_boundaries = any(
        marker in desc
        for marker in ["do not use", "instead use", "not for", "use X instead"]
    )
    
    # Check parameter name ambiguity
    ambiguous_names = {"user", "file", "path", "id", "name", "data", "value", "input"}
    param_names = set(params.keys())
    unambiguous = not bool(param_names & ambiguous_names)
    
    return ToolDescriptionQuality(
        has_example_usage=has_example,
        has_edge_cases=has_edges,
        has_input_format=has_format,
        has_clear_boundaries=has_boundaries,
        params_unambiguous=unambiguous,
    )


def enhance_tool_description(tool: Tool) -> Tool:
    """Enhance a tool description based on audit findings.
    
    Applies Anthropic's "poka-yoke" principle: change the tool
    definition to make mistakes harder.
    
    Args:
        tool: Tool with potentially weak description
        
    Returns:
        Tool with enhanced description
    """
    quality = audit_tool_description(tool)
    
    if quality.score >= 0.8:
        return tool  # Already good
    
    enhancements: list[str] = []
    desc = tool.description
    
    # Add format hints if missing
    if not quality.has_input_format:
        params = tool.parameters.get("properties", {})
        required = tool.parameters.get("required", [])
        if params:
            format_hints = []
            for name, schema in params.items():
                param_type = schema.get("type", "any")
                req = " (required)" if name in required else ""
                format_hints.append(f"{name}: {param_type}{req}")
            if format_hints:
                enhancements.append(f"Parameters: {', '.join(format_hints)}")
    
    # Add boundary hints for common tools
    if not quality.has_clear_boundaries:
        tool_lower = tool.name.lower()
        if "write" in tool_lower:
            enhancements.append("Note: Creates file if not exists, overwrites if exists.")
        elif "delete" in tool_lower:
            enhancements.append("Warning: This action is irreversible.")
        elif "search" in tool_lower:
            enhancements.append("For exact matches, prefer read_file if you know the path.")
    
    if enhancements:
        desc = f"{desc}\n\n{chr(10).join(enhancements)}"
    
    return Tool(
        name=tool.name,
        description=desc,
        parameters=tool.parameters,
    )


def audit_tool_set(tools: tuple[Tool, ...]) -> dict[str, ToolDescriptionQuality]:
    """Audit all tools and return quality report.
    
    Args:
        tools: All available tools
        
    Returns:
        Dict mapping tool name to quality assessment
    """
    return {tool.name: audit_tool_description(tool) for tool in tools}
```

### 9. Parallel Tool Execution Planning

> **Research Insight**: Parallel tool calling can reduce latency by 4x (e.g., 4 × 300ms calls = 1.2s sequential vs ~300ms parallel). However, state-modifying operations must remain sequential.

```python
# src/sunwell/models/capability/parallel.py

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from sunwell.models.protocol import Tool, ToolCall


class ToolClassification(Enum):
    """Classification for parallelization safety."""
    READ = "read"
    """Safe to parallelize: search, list, get, read, query, fetch."""
    
    WRITE = "write"
    """Must be sequential: write, create, update, delete, modify."""
    
    UNKNOWN = "unknown"
    """Conservative: treat as write."""


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Planned execution batches for tool calls.
    
    Each batch can run in parallel. Batches execute sequentially.
    """
    
    batches: tuple[tuple[ToolCall, ...], ...]
    """Ordered batches of tool calls."""
    
    @property
    def total_calls(self) -> int:
        return sum(len(batch) for batch in self.batches)
    
    @property
    def parallelism_ratio(self) -> float:
        """Ratio of parallelization (1.0 = all parallel, 0.0 = all sequential)."""
        if not self.batches:
            return 0.0
        parallel_calls = sum(len(b) for b in self.batches if len(b) > 1)
        return parallel_calls / self.total_calls


# Read-only operations safe to parallelize
_READ_PATTERNS = frozenset({
    "search", "list", "get", "find", "read", "query", "fetch",
    "check", "validate", "inspect", "analyze", "count", "exists",
})

# Write operations that must be sequential
_WRITE_PATTERNS = frozenset({
    "write", "create", "update", "delete", "modify", "set", "post",
    "put", "patch", "remove", "add", "insert", "append", "move",
    "rename", "copy", "execute", "run", "install", "uninstall",
})


def classify_tool(tool: Tool) -> ToolClassification:
    """Classify if a tool is safe to parallelize.
    
    Based on MCP guidance: read-only tools can run in parallel,
    write tools must be sequential.
    
    Args:
        tool: Tool to classify
        
    Returns:
        ToolClassification indicating parallelization safety
    """
    name_lower = tool.name.lower()
    desc_lower = tool.description.lower()
    
    # Check name patterns
    for pattern in _WRITE_PATTERNS:
        if pattern in name_lower:
            return ToolClassification.WRITE
    
    for pattern in _READ_PATTERNS:
        if pattern in name_lower:
            return ToolClassification.READ
    
    # Check description for hints
    if any(word in desc_lower for word in ["modifies", "creates", "deletes", "changes"]):
        return ToolClassification.WRITE
    
    if any(word in desc_lower for word in ["returns", "retrieves", "looks up", "searches"]):
        return ToolClassification.READ
    
    return ToolClassification.UNKNOWN


def plan_parallel_execution(
    tool_calls: list[ToolCall],
    tools: dict[str, Tool],
    allow_parallel: bool = True,
) -> ExecutionPlan:
    """Plan tool execution with optimal parallelization.
    
    Groups read-only operations into parallel batches while
    keeping write operations sequential.
    
    Args:
        tool_calls: Tool calls to execute
        tools: Available tool definitions (for classification)
        allow_parallel: Whether to allow any parallelization
        
    Returns:
        ExecutionPlan with batched tool calls
        
    Example:
        Given calls: [read_a, read_b, write_c, read_d, read_e]
        Returns batches: [(read_a, read_b), (write_c,), (read_d, read_e)]
        
        Execution: batch 1 parallel, batch 2 sequential, batch 3 parallel
        Total time: max(a,b) + c + max(d,e) instead of a+b+c+d+e
    """
    if not tool_calls:
        return ExecutionPlan(batches=())
    
    if not allow_parallel:
        # All sequential
        return ExecutionPlan(
            batches=tuple((tc,) for tc in tool_calls)
        )
    
    batches: list[list[ToolCall]] = []
    current_read_batch: list[ToolCall] = []
    
    for tc in tool_calls:
        tool = tools.get(tc.name)
        classification = classify_tool(tool) if tool else ToolClassification.UNKNOWN
        
        if classification == ToolClassification.READ:
            # Accumulate into parallel batch
            current_read_batch.append(tc)
        else:
            # Write or unknown: flush read batch, then add sequential
            if current_read_batch:
                batches.append(current_read_batch)
                current_read_batch = []
            batches.append([tc])
    
    # Don't forget trailing reads
    if current_read_batch:
        batches.append(current_read_batch)
    
    return ExecutionPlan(
        batches=tuple(tuple(batch) for batch in batches)
    )
```

### 10. Validation-Based Retry Loops

> **Research Insight**: Per LangGraph research, validation loops improve tool call success by prompting the LLM to fix validation errors rather than just failing.

```python
# src/sunwell/models/capability/validation.py

from dataclasses import dataclass
from sunwell.models.protocol import Tool, ToolCall


@dataclass(frozen=True, slots=True)
class ValidationError:
    """Structured validation error for tool calls.
    
    Designed to provide actionable feedback to the LLM so it
    can correct its tool call.
    """
    
    tool_name: str
    """Name of the tool with the error."""
    
    parameter: str | None
    """Specific parameter with the error (if applicable)."""
    
    error: str
    """Description of what's wrong."""
    
    suggestion: str | None = None
    """How to fix it."""
    
    expected: str | None = None
    """What was expected."""
    
    received: str | None = None
    """What was received."""


def validate_tool_call(
    tool_call: ToolCall,
    tool: Tool,
) -> list[ValidationError]:
    """Validate tool call arguments against schema.
    
    Returns actionable errors the LLM can use to self-correct.
    
    Args:
        tool_call: The tool call to validate
        tool: The tool definition with schema
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[ValidationError] = []
    schema = tool.parameters
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    
    # Check required parameters
    for param in required:
        if param not in tool_call.arguments:
            prop_schema = properties.get(param, {})
            errors.append(ValidationError(
                tool_name=tool_call.name,
                parameter=param,
                error=f"Missing required parameter: {param}",
                suggestion=f"Add '{param}' to arguments",
                expected=prop_schema.get("type", "any"),
            ))
    
    # Check types and constraints
    for param, value in tool_call.arguments.items():
        if param not in properties:
            # Extra parameter - warn but don't fail
            continue
        
        prop_schema = properties[param]
        expected_type = prop_schema.get("type")
        
        # Type checking
        type_valid = True
        if expected_type == "string" and not isinstance(value, str):
            type_valid = False
            errors.append(ValidationError(
                tool_name=tool_call.name,
                parameter=param,
                error=f"Expected string, got {type(value).__name__}",
                suggestion=f"Convert {param} to a string value",
                expected="string",
                received=type(value).__name__,
            ))
        elif expected_type == "integer" and not isinstance(value, int):
            type_valid = False
            errors.append(ValidationError(
                tool_name=tool_call.name,
                parameter=param,
                error=f"Expected integer, got {type(value).__name__}",
                suggestion=f"Use an integer value for {param}",
                expected="integer",
                received=type(value).__name__,
            ))
        elif expected_type == "boolean" and not isinstance(value, bool):
            type_valid = False
            errors.append(ValidationError(
                tool_name=tool_call.name,
                parameter=param,
                error=f"Expected boolean, got {type(value).__name__}",
                suggestion=f"Use true or false for {param}",
                expected="boolean",
                received=type(value).__name__,
            ))
        elif expected_type == "array" and not isinstance(value, list):
            type_valid = False
            errors.append(ValidationError(
                tool_name=tool_call.name,
                parameter=param,
                error=f"Expected array, got {type(value).__name__}",
                suggestion=f"Use a list/array for {param}",
                expected="array",
                received=type(value).__name__,
            ))
        
        # Enum validation
        if type_valid and "enum" in prop_schema:
            allowed = prop_schema["enum"]
            if value not in allowed:
                errors.append(ValidationError(
                    tool_name=tool_call.name,
                    parameter=param,
                    error=f"Value '{value}' not in allowed values",
                    suggestion=f"Use one of: {', '.join(str(v) for v in allowed)}",
                    expected=f"one of {allowed}",
                    received=str(value),
                ))
    
    return errors


def format_validation_errors_for_retry(errors: list[ValidationError]) -> str:
    """Format validation errors as a message for LLM retry.
    
    Designed to give clear, actionable feedback so the model
    can correct its tool call on the next attempt.
    
    Args:
        errors: List of validation errors
        
    Returns:
        Formatted message for including in conversation
    """
    if not errors:
        return ""
    
    lines = ["Tool call validation failed. Please fix these issues:\n"]
    
    for err in errors:
        line = f"• {err.tool_name}"
        if err.parameter:
            line += f".{err.parameter}"
        line += f": {err.error}"
        
        if err.suggestion:
            line += f"\n  → {err.suggestion}"
        
        if err.expected and err.received:
            line += f"\n  (expected: {err.expected}, got: {err.received})"
        
        lines.append(line)
    
    lines.append("\nPlease try the tool call again with corrected arguments.")
    return "\n".join(lines)


def validate_tool_calls(
    tool_calls: list[ToolCall],
    tools: dict[str, Tool],
) -> tuple[list[ToolCall], list[ValidationError]]:
    """Validate multiple tool calls, returning valid ones and errors.
    
    Args:
        tool_calls: Tool calls to validate
        tools: Available tool definitions
        
    Returns:
        Tuple of (valid_calls, all_errors)
    """
    valid: list[ToolCall] = []
    all_errors: list[ValidationError] = []
    
    for tc in tool_calls:
        tool = tools.get(tc.name)
        
        if tool is None:
            all_errors.append(ValidationError(
                tool_name=tc.name,
                parameter=None,
                error=f"Unknown tool: {tc.name}",
                suggestion="Check available tools and use a valid tool name",
            ))
            continue
        
        errors = validate_tool_call(tc, tool)
        if errors:
            all_errors.extend(errors)
        else:
            valid.append(tc)
    
    return valid, all_errors
```

### 11. Response Format Control

> **Research Insight**: Per MCP guidance, controlling response verbosity saves ~70% tokens. Use concise mode by default, detailed mode only when chaining requires IDs.

```python
# src/sunwell/models/capability/response_format.py

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ResponseFormat(Enum):
    """Control tool response verbosity.
    
    Per MCP research: concise mode uses ~70% fewer tokens while
    providing the essential information agents need.
    """
    
    CONCISE = "concise"
    """Names and essential data only. Default for most operations."""
    
    DETAILED = "detailed"
    """Full IDs and metadata. Use when chaining tools requires IDs."""


@dataclass(frozen=True, slots=True)
class ToolResultConfig:
    """Configuration for tool result formatting.
    
    Controls how much information is returned to the agent.
    """
    
    format: ResponseFormat = ResponseFormat.CONCISE
    """Output verbosity level."""
    
    max_items: int = 10
    """Maximum items to return (pagination)."""
    
    include_ids: bool = False
    """Include internal IDs (needed for chaining)."""
    
    truncate_at: int = 25000
    """Token limit before truncation (per Anthropic: 25k default)."""
    
    include_metadata: bool = False
    """Include timestamps, counts, etc."""


@dataclass(frozen=True, slots=True)
class TruncatedResult:
    """Result that was truncated due to size limits.
    
    Includes hints to guide the agent toward more efficient queries.
    """
    
    content: str
    """Truncated content."""
    
    truncated: bool
    """Whether truncation occurred."""
    
    total_available: int | None = None
    """Total items/bytes available before truncation."""
    
    hint: str | None = None
    """Suggestion for more efficient querying."""


def truncate_result(
    result: str,
    config: ToolResultConfig,
    total_available: int | None = None,
) -> TruncatedResult:
    """Truncate a result if it exceeds limits.
    
    Per MCP guidance: when truncating, provide hints to guide
    the agent toward more token-efficient strategies.
    
    Args:
        result: Raw result string
        config: Configuration with limits
        total_available: Total items available (for hint)
        
    Returns:
        TruncatedResult with truncation metadata
    """
    # Estimate tokens (rough: 4 chars per token)
    estimated_tokens = len(result) // 4
    
    if estimated_tokens <= config.truncate_at:
        return TruncatedResult(
            content=result,
            truncated=False,
        )
    
    # Truncate
    char_limit = config.truncate_at * 4
    truncated_content = result[:char_limit]
    
    # Find a clean break point
    last_newline = truncated_content.rfind("\n")
    if last_newline > char_limit * 0.8:  # Don't truncate too much
        truncated_content = truncated_content[:last_newline]
    
    # Add truncation marker
    truncated_content += "\n\n[... truncated ...]"
    
    # Generate hint
    hint = "Results truncated. Try:\n"
    hint += "• More specific search terms or filters\n"
    hint += "• Pagination (limit/offset parameters)\n"
    hint += "• Requesting a specific file instead of listing"
    
    return TruncatedResult(
        content=truncated_content,
        truncated=True,
        total_available=total_available,
        hint=hint,
    )


def format_list_result(
    items: list[dict[str, Any]],
    config: ToolResultConfig,
    name_key: str = "name",
    id_key: str = "id",
) -> str:
    """Format a list result according to config.
    
    Args:
        items: List of items to format
        config: Response format configuration
        name_key: Key to use for item names
        id_key: Key to use for item IDs
        
    Returns:
        Formatted string result
    """
    if not items:
        return "No items found."
    
    # Limit items
    limited_items = items[:config.max_items]
    total = len(items)
    
    lines: list[str] = []
    
    for item in limited_items:
        if config.format == ResponseFormat.CONCISE:
            # Just the name
            name = item.get(name_key, str(item))
            lines.append(f"• {name}")
        else:
            # Name + ID + metadata
            name = item.get(name_key, "unknown")
            item_id = item.get(id_key, "")
            line = f"• {name}"
            if config.include_ids and item_id:
                line += f" (id: {item_id})"
            if config.include_metadata:
                # Add any other fields
                extras = [f"{k}={v}" for k, v in item.items() 
                         if k not in (name_key, id_key)]
                if extras:
                    line += f" [{', '.join(extras[:3])}]"
            lines.append(line)
    
    result = "\n".join(lines)
    
    if len(items) > config.max_items:
        result += f"\n\n[Showing {config.max_items} of {total} items]"
    
    return result
```

### 12. Tool Namespacing

> **Research Insight**: When agents have access to hundreds of tools (MCP ecosystem), namespacing prevents confusion about which tool to use.

```python
# src/sunwell/models/capability/namespacing.py

from sunwell.models.protocol import Tool


def namespace_tools(
    tools: tuple[Tool, ...],
    namespace: str,
    separator: str = "_",
) -> tuple[Tool, ...]:
    """Add namespace prefix to tool names.
    
    Per MCP guidance: namespacing helps models select correct tools
    when many overlapping tools are available.
    
    Example:
        namespace="github", tool="search" → "github_search"
        namespace="jira", tool="search" → "jira_search"
    
    Args:
        tools: Tools to namespace
        namespace: Prefix to add
        separator: Character between namespace and name (default: "_")
        
    Returns:
        Tools with namespaced names and descriptions
    """
    return tuple(
        Tool(
            name=(
                f"{namespace}{separator}{t.name}" 
                if not t.name.startswith(f"{namespace}{separator}") 
                else t.name
            ),
            description=f"[{namespace}] {t.description}",
            parameters=t.parameters,
        )
        for t in tools
    )


def extract_namespace(tool_name: str, separator: str = "_") -> str | None:
    """Extract namespace from a tool name.
    
    Args:
        tool_name: Tool name potentially with namespace
        separator: Namespace separator
        
    Returns:
        Namespace if present, None otherwise
    """
    if separator not in tool_name:
        return None
    
    parts = tool_name.split(separator, 1)
    if len(parts) == 2:
        return parts[0]
    return None


def group_tools_by_namespace(
    tools: tuple[Tool, ...],
    separator: str = "_",
) -> dict[str | None, tuple[Tool, ...]]:
    """Group tools by their namespace.
    
    Args:
        tools: All tools
        separator: Namespace separator
        
    Returns:
        Dict mapping namespace (or None) to tools in that namespace
    """
    groups: dict[str | None, list[Tool]] = {}
    
    for tool in tools:
        ns = extract_namespace(tool.name, separator)
        if ns not in groups:
            groups[ns] = []
        groups[ns].append(tool)
    
    return {k: tuple(v) for k, v in groups.items()}


def filter_tools_by_task_namespaces(
    tools: tuple[Tool, ...],
    task_hint: str,
    max_namespaces: int = 3,
    separator: str = "_",
) -> tuple[Tool, ...]:
    """Filter tools to relevant namespaces based on task.
    
    When there are too many tools, use task analysis to select
    relevant namespaces rather than individual tools.
    
    Args:
        tools: All available tools
        task_hint: Description of the task
        max_namespaces: Maximum namespaces to include
        separator: Namespace separator
        
    Returns:
        Tools filtered to relevant namespaces
    """
    groups = group_tools_by_namespace(tools, separator)
    task_lower = task_hint.lower()
    
    # Score namespaces by relevance
    namespace_scores: list[tuple[str | None, float]] = []
    
    for ns, ns_tools in groups.items():
        if ns is None:
            # Non-namespaced tools always included
            namespace_scores.append((ns, 100.0))
            continue
        
        score = 0.0
        
        # Direct namespace mention
        if ns.lower() in task_lower:
            score += 10.0
        
        # Tool name matches
        for tool in ns_tools:
            base_name = tool.name.split(separator, 1)[-1]
            if base_name.lower() in task_lower:
                score += 5.0
            
            # Description word overlap
            desc_words = set(tool.description.lower().split())
            task_words = set(task_lower.split())
            score += len(desc_words & task_words) * 0.5
        
        namespace_scores.append((ns, score))
    
    # Sort by score and take top namespaces
    namespace_scores.sort(key=lambda x: x[1], reverse=True)
    selected_namespaces = {ns for ns, _ in namespace_scores[:max_namespaces]}
    
    # Include non-namespaced tools always
    selected_namespaces.add(None)
    
    return tuple(
        tool for tool in tools
        if extract_namespace(tool.name, separator) in selected_namespaces
    )
```

---

## 🔀 Alternatives Considered

### Alternative A: Keep Current String Matching (Status Quo)

**Approach**: Continue with `if key.lower() in model_lower` prefix matching.

**Pros**:
- No development effort
- Works for common models

**Cons**:
- Fine-tuned models misrouted
- Version-specific capabilities missed
- Maintenance burden as new models added

**Decision**: Rejected — too fragile for production use.

### Alternative B: Runtime Capability Probing

**Approach**: Send test tool calls to detect capabilities.

**Pros**:
- Always accurate
- Works with any model

**Cons**:
- Adds latency to first request
- Wastes tokens on probing
- May trigger rate limits

**Decision**: Rejected — too slow and wasteful.

### Alternative C: External Capability Database

**Approach**: Fetch capabilities from centralized API (like litellm).

**Pros**:
- Always up-to-date
- Community maintained

**Cons**:
- External dependency
- Network latency
- Offline support broken

**Decision**: Partially adopted — use static registry with optional external updates.

---

## ⚠️ Risks & Edge Cases

### Risk 1: Parser Edge Cases

**Problem**: Model IDs come in many formats:
- `llama3.3:70b` vs `meta-llama/Llama-3.3-70B-Instruct`
- `gpt-4o-2024-08-06` vs `gpt-4o`

**Mitigation**:
- Multiple regex patterns per family
- Fallback to family extraction
- Log unknown models for analysis

### Risk 2: Custom Fine-tuned Models

**Problem**: `mycompany/llama3-ft-v2` might have different capabilities than base Llama 3.

**Mitigation**:
- Mark as `custom=True` in ModelSpec
- Inherit base model capabilities as default
- Allow explicit capability override via config

### Risk 3: Streaming Parser State

**Problem**: `ToolStreamParser` maintains state — interruptions could leave it corrupted.

**Mitigation**:
- Parser is per-request, not global
- Reset state on errors
- Handle incomplete JSON gracefully

### Edge Case Matrix

| Scenario | Handling |
|----------|----------|
| Unknown model ID | Assume no native tools, use JSON emulation |
| Custom fine-tuned model | Inherit base family capabilities |
| Model with partial tool support | Use strictest interpretation |
| Malformed tool call JSON | Attempt repair, log and continue |
| Tool call in reasoning block | Skip (o1/R1 thinking isn't action) |
| Multiple tool calls in one chunk | Split and process sequentially |

---

## 📊 Feature Matrix

| Feature | Current | Proposed |
|---------|---------|----------|
| Model detection | String prefix | Structured parsing |
| Version awareness | ❌ | ✅ (tuple comparison) |
| Size awareness | ❌ | ✅ (parameter count) |
| Provider detection | ❌ | ✅ (prefix extraction) |
| Custom model support | ❌ | ✅ (inheritance) |
| Schema validation | ❌ | ✅ (per-provider) |
| Adaptive emulation | ❌ | ✅ (by capability) |
| Typed streaming | ❌ | ✅ (StreamChunk) |
| Structured errors | ❌ | ✅ (ToolError) |
| Model-specific normalization | Partial | ✅ (per-family) |
| **Tool description engineering** | ❌ | ✅ (audit + enhance) |
| **Parallel execution planning** | ❌ | ✅ (read/write classification) |
| **Validation-based retry** | ❌ | ✅ (structured feedback) |
| **Response format control** | ❌ | ✅ (concise/detailed modes) |
| **Tool namespacing** | ❌ | ✅ (multi-service support) |
| **Strict schema mode** | ❌ | ✅ (OpenAI 100% accuracy) |

---

## 🔬 Tool Calling Evaluation Strategy

> **Research Insight**: Per Anthropic/MCP, "evaluation-driven development" with systematic testing dramatically improves tool calling effectiveness.

### Evaluation Principles

1. **Use realistic tasks, not sandboxes**
   - Evaluation tasks should mirror real-world usage
   - Use production-like data and services
   - Avoid oversimplified "test" scenarios

2. **Measure what matters**
   - Tool selection accuracy (correct tool chosen)
   - Parameter mapping accuracy (correct args extracted)
   - First-attempt success rate
   - Token efficiency per task

3. **Analyze agent reasoning**
   - Review chain-of-thought for tool selection errors
   - What agents *omit* is often more important than what they include
   - Log and review tool call repairs

### Evaluation Task Examples

**Strong tasks** (realistic, complex):

```markdown
- "Find all Python files in src/ that import the logging module and have 
   been modified in the last week"
- "Create a test file for the User model that covers authentication 
   edge cases including expired tokens and invalid credentials"
- "Refactor the database connection code to use connection pooling 
   and update all files that instantiate connections directly"
```

**Weak tasks** (too simple, over-specified):

```markdown
- "Read file.py"  # Too simple
- "Write 'hello' to output.txt"  # No real-world context
- "Call search with query='test'"  # Over-specified
```

### Evaluation Metrics

```python
# src/sunwell/models/capability/evaluation.py

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolEvaluationMetrics:
    """Metrics for evaluating tool calling effectiveness."""
    
    total_tasks: int
    """Total evaluation tasks attempted."""
    
    successful_tasks: int
    """Tasks completed successfully."""
    
    tool_selection_accuracy: float
    """Percentage of correct tool selections (0.0-1.0)."""
    
    parameter_accuracy: float
    """Percentage of correctly mapped parameters (0.0-1.0)."""
    
    first_attempt_success: float
    """Percentage succeeding on first try (0.0-1.0)."""
    
    avg_tokens_per_task: float
    """Average tokens used per task."""
    
    avg_retries_per_task: float
    """Average retry attempts per task."""
    
    repairs_applied: int
    """Total JSON/schema repairs applied."""
    
    @property
    def overall_success_rate(self) -> float:
        """Overall success rate."""
        return self.successful_tasks / self.total_tasks if self.total_tasks else 0.0


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    """Single tool call event for evaluation logging."""
    
    task_id: str
    tool_name: str
    expected_tool: str | None
    parameters: dict
    expected_parameters: dict | None
    success: bool
    error: str | None
    attempt: int
    tokens_used: int
    repairs: tuple[str, ...]
```

### Tool Description Regression Testing

```python
def test_tool_description_quality():
    """Ensure tool descriptions maintain quality standards."""
    from sunwell.models.capability.tool_engineering import audit_tool_set
    from sunwell.tools.builtins import get_all_tools
    
    tools = get_all_tools()
    audit = audit_tool_set(tools)
    
    # No tool should score below 0.6
    for name, quality in audit.items():
        assert quality.score >= 0.6, f"Tool {name} has poor description (score: {quality.score})"
    
    # Average should be above 0.8
    avg_score = sum(q.score for q in audit.values()) / len(audit)
    assert avg_score >= 0.8, f"Average tool quality too low: {avg_score}"
```

---

## ✅ Acceptance Criteria

### Journey Coverage (Must Have)
All user journeys must have corresponding tests:

| Category | Journeys | Test Coverage |
|----------|----------|---------------|
| **Agent Internal** | A1-A11 | 11/11 (100%) |
| **Human External** | H1-H12 | 12/12 (100%) |
| **Edge Cases** | E1-E8 | 8/8 (100%) |

### Must Have
- [ ] `parse_model_id()` correctly parses 95%+ of common model IDs
- [ ] `get_capability()` returns correct capabilities for OpenAI, Anthropic, Llama, Qwen, Mistral
- [ ] Schema adapters produce valid output for each provider
- [ ] Tool emulation works for models without native tool support
- [ ] `ToolError` categorizes common errors correctly
- [ ] All 31 user journeys have corresponding test coverage
- [ ] **OpenAI strict mode** enabled by default (100% schema accuracy)
- [ ] **Validation-based retry loop** with actionable error messages

### Should Have
- [ ] Version-aware capability matching (Claude 3 vs 3.5 vs 4)
- [ ] Size-aware matching for Llama (7B vs 70B)
- [ ] Typed streaming with `StreamChunk` events
- [ ] JSON repair for malformed tool calls
- [ ] Custom model inheritance from base family
- [ ] `optimize_tool_definitions()` for context-constrained models (E6)
- [ ] **Tool description audit** scoring ≥0.6 for all built-in tools
- [ ] **Parallel execution planning** for read-only operations
- [ ] **Response format control** (concise vs detailed modes)

### Nice to Have
- [ ] XML emulation style for models that prefer it
- [ ] Automatic capability discovery via optional API
- [ ] Tool call caching/deduplication
- [ ] Capability config file for overrides
- [ ] **Tool namespacing** for multi-service MCP environments
- [ ] **Evaluation metrics dashboard** for tool calling quality
- [ ] **Automatic tool description enhancement** for low-scoring tools

---

## 🧪 Testing Strategy

### Journey Coverage Matrix

Every user journey from the Journey Analysis section must have corresponding tests.

| Journey | Test File | Test Name | Type |
|---------|-----------|-----------|------|
| **A1** Receive tools | `test_schema_adapter.py` | `test_convert_tools_*` | Unit |
| **A2** Format schema | `test_schema_adapter.py` | `test_*_schema_adapter` | Unit |
| **A3** Generate response | `test_capability_registry.py` | `test_*_capabilities` | Unit |
| **A4** Parse tool calls | `test_normalizer.py` | `test_normalize_*` | Unit |
| **A5** Execute tool | (existing `test_executor.py`) | - | Integration |
| **A6** Receive result | `test_tool_errors.py` | `test_error_from_exception` | Unit |
| **A7** Handle result | `test_tool_errors.py` | `test_retry_strategy_*` | Unit |
| **A8** Learn outcome | (existing `test_learning.py`) | - | Integration |
| **A9** Retry/escalate | `test_tool_errors.py` | `test_should_retry_*` | Unit |
| **A10** Escalate/abort | `test_tool_errors.py` | `test_unrecoverable_*` | Unit |
| **A11** Report to human | `test_streaming.py` | `test_stream_chunk_*` | Unit |
| **H1** Configure model | `test_model_parser.py` | `test_parse_model_id` | Unit |
| **H3** Observe progress | `test_streaming.py` | `test_tool_stream_parser` | Unit |
| **H9** Debug failure | `test_tool_errors.py` | `test_error_*` | Unit |
| **H11** Switch model | `test_capability_registry.py` | `test_custom_model_*` | Unit |
| **H12** Add custom model | `test_model_parser.py` | `test_custom_model_*` | Unit |
| **E1** Model refuses | `test_normalizer.py` | `test_no_tool_calls` | Unit |
| **E2** Malformed JSON | `test_normalizer.py` | `test_repair_json_*` | Unit |
| **E4** Parallel on non-parallel | `test_capability_registry.py` | `test_parallel_*` | Unit |
| **E5** Reasoning during thinking | `test_capability_registry.py` | `test_reasoning_*` | Unit |
| **E6** Context overflow | `test_emulation.py` | `test_optimize_tool_*` | Unit |
| **E7** Provider rate limit | `test_tool_errors.py` | `test_rate_limit_*` | Unit |
| **E8** Network failure | `test_tool_errors.py` | `test_network_*` | Unit |

### Unit Tests

```python
# tests/test_model_parser.py

import pytest
from sunwell.models.capability.parser import parse_model_id, ModelSpec


@pytest.mark.parametrize("model_id,expected", [
    # OpenAI
    ("gpt-4o", ModelSpec(family="gpt", version=(4,), variant="o")),
    ("gpt-4-turbo", ModelSpec(family="gpt", version=(4,), variant="turbo")),
    ("gpt-3.5-turbo", ModelSpec(family="gpt", version=(3, 5), variant="turbo")),
    ("o1-preview", ModelSpec(family="o1", variant="preview")),
    
    # Anthropic
    ("claude-3.5-sonnet", ModelSpec(family="claude", version=(3, 5), variant="sonnet")),
    ("claude-3-opus", ModelSpec(family="claude", version=(3,), variant="opus")),
    ("claude-sonnet-4-20250514", ModelSpec(family="claude", version=(4,), variant="sonnet")),
    
    # Llama
    ("llama3.3:70b", ModelSpec(family="llama", version=(3, 3), size=70_000_000_000)),
    ("meta-llama/Llama-3.3-70B-Instruct", ModelSpec(
        family="llama", version=(3, 3), size=70_000_000_000, variant="instruct"
    )),
    
    # Qwen
    ("qwen2.5:32b", ModelSpec(family="qwen", version=(2, 5), size=32_000_000_000)),
    ("qwen3", ModelSpec(family="qwen", version=(3,))),
    
    # With provider
    ("ollama/llama3.3:70b", ModelSpec(
        family="llama", version=(3, 3), size=70_000_000_000, provider="ollama"
    )),
    
    # Custom
    ("mycompany/llama3-ft", ModelSpec(
        family="llama", version=(3,), org="mycompany", custom=True
    )),
])
def test_parse_model_id(model_id, expected):
    result = parse_model_id(model_id)
    assert result.family == expected.family
    assert result.version == expected.version
    if expected.size:
        assert result.size == expected.size
```

```python
# tests/test_capability_registry.py

import pytest
from sunwell.models.capability.registry import get_capability


def test_gpt4o_capabilities():
    cap = get_capability("gpt-4o")
    assert cap.native_tools is True
    assert cap.parallel_tools is True
    assert cap.tool_streaming is True


def test_claude_35_capabilities():
    cap = get_capability("claude-3.5-sonnet")
    assert cap.native_tools is True
    assert cap.needs_tool_schema_strict is True
    assert cap.tool_result_in_user_message is True


def test_small_llama_emulation():
    cap = get_capability("llama3:7b")
    # Small Llama should use emulation
    assert cap.native_tools is False
    assert cap.emulation_style == "json"


def test_unknown_model_defaults():
    cap = get_capability("totally-unknown-model")
    assert cap.native_tools is False
    assert cap.emulation_style == "json"


def test_custom_model_inheritance():
    cap = get_capability("mycompany/llama3.3-ft")
    # Should inherit Llama 3.3 capabilities
    assert cap.native_tools is True
```

### Integration Tests

```python
# tests/test_tool_normalization.py

from sunwell.models.capability.normalizer import ToolCallNormalizer


def test_normalize_standard_json():
    normalizer = ToolCallNormalizer()
    result = normalizer.normalize('''
    Here's what I'll do:
    
    ```json
    {"tool": "write_file", "arguments": {"path": "test.py", "content": "print('hi')"}}
    ```
    ''')
    
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "write_file"


def test_normalize_llama_quirks():
    normalizer = ToolCallNormalizer()
    result = normalizer.normalize('''
    {"tool": "read_file", "arguments": {"path": "test.py",}}
    ''', model_family="llama")
    
    assert len(result.tool_calls) == 1
    assert "trailing commas" in result.repairs[0].lower()


def test_normalize_qwen_function_key():
    normalizer = ToolCallNormalizer()
    result = normalizer.normalize('''
    {"function": "list_files", "arguments": {"path": "."}}
    ''', model_family="qwen")
    
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "list_files"
```

### Journey-Specific Tests

```python
# tests/test_tool_errors.py
# Covers: A6, A7, A9, A10, H9, E7, E8

import pytest
from sunwell.tools.errors import ToolError, ToolErrorCode, get_retry_strategy, should_retry


class TestToolErrorFromException:
    """Journey A6: Receive result → ToolError mapping."""
    
    def test_file_not_found(self):
        e = FileNotFoundError("foo.py")
        error = ToolError.from_exception(e, "read_file")
        assert error.code == ToolErrorCode.NOT_FOUND
        assert error.recoverable is True
        assert error.retry_strategy == "rephrase"
    
    def test_permission_denied(self):
        e = PermissionError("Cannot write to /etc/passwd")
        error = ToolError.from_exception(e, "write_file")
        assert error.code == ToolErrorCode.PERMISSION
        assert error.recoverable is False
        assert "suggested_fix" in error.message or error.suggested_fix
    
    def test_timeout(self):
        import asyncio
        e = asyncio.TimeoutError()
        error = ToolError.from_exception(e, "run_command")
        assert error.code == ToolErrorCode.TIMEOUT
        assert error.recoverable is True
        assert error.retry_strategy == "same"
    
    def test_rate_limit(self):  # E7
        from httpx import HTTPStatusError, Request, Response
        req = Request("GET", "https://api.example.com")
        resp = Response(429, request=req)
        e = HTTPStatusError("Rate limited", request=req, response=resp)
        error = ToolError.from_exception(e, "web_search")
        assert error.code == ToolErrorCode.RATE_LIMIT
        assert error.recoverable is True
    
    def test_network_failure(self):  # E8
        import httpx
        e = httpx.ConnectError("Connection refused")
        error = ToolError.from_exception(e, "web_fetch")
        assert error.code == ToolErrorCode.NETWORK
        assert error.recoverable is True


class TestRetryStrategy:
    """Journey A7, A9: Handle result with retry strategy."""
    
    def test_validation_error_rephrase(self):
        error = ToolError(
            code=ToolErrorCode.VALIDATION,
            message="Invalid path format",
            recoverable=True,
        )
        strategy = get_retry_strategy(error, attempt=1)
        assert strategy == "rephrase"
    
    def test_timeout_escalates_after_retries(self):
        error = ToolError(
            code=ToolErrorCode.TIMEOUT,
            message="Command timed out",
            recoverable=True,
        )
        assert should_retry(error, attempt=1) is True
        assert should_retry(error, attempt=2) is True
        assert should_retry(error, attempt=3) is False
        
        strategy = get_retry_strategy(error, attempt=3)
        assert strategy == "escalate"
    
    def test_permission_unrecoverable(self):  # A10
        error = ToolError(
            code=ToolErrorCode.PERMISSION,
            message="Cannot access /etc/shadow",
            recoverable=False,
        )
        assert should_retry(error, attempt=1) is False
        strategy = get_retry_strategy(error, attempt=1)
        assert strategy == "abort"
```

```python
# tests/test_streaming.py
# Covers: A11, H3

import pytest
from sunwell.models.capability.streaming import (
    StreamChunk, StreamChunkType, ToolStreamParser
)


class TestToolStreamParser:
    """Journey H3: Observe progress via typed streaming."""
    
    def test_text_only(self):
        parser = ToolStreamParser()
        chunks = parser.feed("Hello, how can I help?")
        # May not emit immediately (buffering)
        all_chunks = chunks + parser.finalize()
        text_chunks = [c for c in all_chunks if c.type == StreamChunkType.TEXT]
        assert len(text_chunks) >= 1
    
    def test_tool_start_detection(self):
        parser = ToolStreamParser()
        chunks = parser.feed('Let me help: {"tool"')
        chunks += parser.feed(': "write_file", "arguments": {"path": "test.py"}}')
        chunks += parser.finalize()
        
        types = [c.type for c in chunks]
        assert StreamChunkType.TOOL_START in types
        assert StreamChunkType.TOOL_ARGS in types
    
    def test_tool_name_extraction(self):
        parser = ToolStreamParser()
        parser.feed('{"tool": "read_file", "arguments": {"path": "x.py"}}')
        chunks = parser.finalize()
        
        tool_chunks = [c for c in chunks if c.tool_name]
        assert any(c.tool_name == "read_file" for c in tool_chunks)
    
    def test_multiple_tools(self):
        parser = ToolStreamParser()
        chunks = parser.feed('''
        ```json
        {"tool": "read_file", "arguments": {"path": "a.py"}}
        ```
        
        ```json  
        {"tool": "read_file", "arguments": {"path": "b.py"}}
        ```
        ''')
        chunks += parser.finalize()
        
        starts = [c for c in chunks if c.type == StreamChunkType.TOOL_START]
        assert len(starts) == 2


class TestStreamChunk:
    """Journey A11: Report to human."""
    
    def test_text_chunk(self):
        chunk = StreamChunk(type=StreamChunkType.TEXT, content="Hello")
        assert chunk.type == StreamChunkType.TEXT
        assert chunk.content == "Hello"
        assert chunk.tool_name is None
    
    def test_tool_chunk(self):
        chunk = StreamChunk(
            type=StreamChunkType.TOOL_END,
            tool_name="write_file",
            tool_call_id="tc_123",
            is_complete=True,
        )
        assert chunk.is_complete is True
        assert chunk.tool_name == "write_file"
```

```python
# tests/test_emulation.py
# Covers: E6

import pytest
from sunwell.models.protocol import Tool
from sunwell.models.capability.registry import ModelCapability
from sunwell.models.capability.emulation import (
    build_emulation_prompt, optimize_tool_definitions
)


class TestOptimizeToolDefinitions:
    """Journey E6: Context overflow handling."""
    
    @pytest.fixture
    def many_tools(self) -> tuple[Tool, ...]:
        return tuple(
            Tool(
                name=f"tool_{i}",
                description=f"This is tool number {i} with a moderately long description " * 5,
                parameters={"type": "object", "properties": {"arg": {"type": "string"}}},
            )
            for i in range(50)
        )
    
    def test_no_optimization_large_context(self, many_tools):
        """Large context windows don't need optimization."""
        capability = ModelCapability(context_window=128000)
        result = optimize_tool_definitions(many_tools, capability)
        assert len(result) == len(many_tools)
    
    def test_reduces_tools_small_context(self, many_tools):
        """Small context windows get fewer tools."""
        capability = ModelCapability(context_window=4096)
        result = optimize_tool_definitions(many_tools, capability)
        assert len(result) < len(many_tools)
    
    def test_truncates_descriptions_tiny_context(self, many_tools):
        """Very small contexts get truncated descriptions."""
        capability = ModelCapability(context_window=2048)
        result = optimize_tool_definitions(many_tools, capability)
        
        for tool in result:
            assert len(tool.description) <= 210  # 200 + "..."
    
    def test_prioritizes_by_task_hint(self, many_tools):
        """Task hint affects tool ordering."""
        # Add a tool that matches the task
        file_tool = Tool(
            name="write_file",
            description="Write content to a file",
            parameters={"type": "object", "properties": {}},
        )
        tools_with_file = many_tools + (file_tool,)
        
        capability = ModelCapability(context_window=4096)
        result = optimize_tool_definitions(
            tools_with_file, capability, task_hint="write a python file"
        )
        
        # write_file should be prioritized and included
        result_names = [t.name for t in result]
        assert "write_file" in result_names


class TestBuildEmulationPrompt:
    """Adaptive emulation prompt generation."""
    
    def test_compact_for_small_context(self):
        tools = (Tool(name="test", description="A test tool", parameters={}),)
        capability = ModelCapability(context_window=4096, emulation_style="json")
        
        prompt = build_emulation_prompt(tools, capability)
        # Compact prompt is shorter
        assert len(prompt) < 500
    
    def test_parallel_prompt(self):
        tools = (Tool(name="test", description="A test tool", parameters={}),)
        capability = ModelCapability(parallel_tools=True)
        
        prompt = build_emulation_prompt(tools, capability)
        assert "multiple tools" in prompt.lower() or "one per tool" in prompt.lower()
    
    def test_xml_style(self):
        tools = (Tool(name="test", description="A test tool", parameters={}),)
        capability = ModelCapability(emulation_style="xml")
        
        prompt = build_emulation_prompt(tools, capability)
        assert "<tool_call>" in prompt
```

### End-to-End Journey Tests

```python
# tests/test_e2e_tool_journeys.py
# Integration tests for complete user journeys

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
class TestAgentJourneys:
    """Full agent tool calling journey (A1 → A11)."""
    
    async def test_full_tool_cycle_native(self, mock_openai_model):
        """Journey: Native tool calling model completes tool cycle."""
        # A1: Receive tools
        tools = [{"name": "read_file", "description": "Read a file"}]
        
        # A2: Format schema (via adapter)
        from sunwell.models.capability.schema import get_schema_adapter
        adapter = get_schema_adapter("openai")
        formatted = adapter.convert_tools(tools)
        assert formatted[0]["type"] == "function"
        
        # A3-A4: Generate + Parse (mocked)
        mock_openai_model.generate.return_value = MagicMock(
            tool_calls=[MagicMock(name="read_file", arguments={"path": "test.py"})]
        )
        
        # A5-A8: Execute + Learn (existing system)
        # ... integration continues
    
    async def test_full_tool_cycle_emulated(self, mock_ollama_model):
        """Journey: Emulated tool calling for small model."""
        from sunwell.models.capability.registry import get_capability
        from sunwell.models.capability.emulation import build_emulation_prompt
        
        # A1-A2: Emulation path
        capability = get_capability("llama3:7b")
        assert capability.native_tools is False
        
        tools = (MagicMock(name="read_file", description="Read", parameters={}),)
        prompt = build_emulation_prompt(tools, capability)
        
        # A3: Generate with emulation prompt
        mock_ollama_model.generate.return_value = MagicMock(
            text='{"tool": "read_file", "arguments": {"path": "x.py"}}'
        )
        
        # A4: Normalize response
        from sunwell.models.capability.normalizer import ToolCallNormalizer
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize(mock_ollama_model.generate.return_value.text)
        assert len(result.tool_calls) == 1


@pytest.mark.asyncio  
class TestHumanJourneys:
    """Human user experience journeys (H1 → H12)."""
    
    async def test_model_switch_journey(self):
        """Journey H11: User switches model mid-session."""
        from sunwell.models.capability.registry import get_capability
        
        # Initial model
        cap1 = get_capability("gpt-4o")
        assert cap1.native_tools is True
        
        # User switches to local model
        cap2 = get_capability("ollama/llama3:7b")
        assert cap2.native_tools is False
        
        # Capabilities correctly re-routed
        assert cap1 != cap2
    
    async def test_custom_model_journey(self):
        """Journey H12: User adds custom fine-tuned model."""
        from sunwell.models.capability.parser import parse_model_id
        from sunwell.models.capability.registry import get_capability
        
        spec = parse_model_id("mycompany/llama3.3-code-ft")
        assert spec.custom is True
        assert spec.family == "llama"
        assert spec.version >= (3, 3)
        
        # Inherits base capabilities
        cap = get_capability("mycompany/llama3.3-code-ft")
        assert cap.native_tools is True  # Llama 3.3 has native tools
```

---

## 🗓️ Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | ModelSpec parser + comprehensive tests | 4 hours |
| **2** | Version-aware capability registry | 6 hours |
| **3** | Unified schema adapters (OpenAI strict mode, Anthropic, Ollama) | 4 hours |
| **4** | Adaptive emulation prompts + optimize_tool_definitions | 3 hours |
| **5** | ToolCallNormalizer with model-specific handling | 4 hours |
| **6** | Typed streaming (StreamChunk) | 4 hours |
| **7** | Structured errors (ToolError) with actionable messages | 3 hours |
| **8** | **Tool description engineering** (audit + enhance) | 3 hours |
| **9** | **Parallel execution planning** (read/write classification) | 2 hours |
| **10** | **Validation-based retry loops** | 3 hours |
| **11** | **Response format control** (concise/detailed) | 2 hours |
| **12** | **Tool namespacing** | 2 hours |
| **13** | Integrate into existing model adapters | 6 hours |
| **14** | Testing + edge cases + journey coverage | 8 hours |
| **15** | **Evaluation framework** + metrics | 4 hours |
| **16** | Documentation | 2 hours |

**Total estimated effort**: 56 hours (~7 days)

---

## 🔗 Dependencies

### Verified Dependencies

| Dependency | Status | Location | What We Use |
|------------|--------|----------|-------------|
| **RFC-012 (Tool Calling)** | ✅ Verified | `models/protocol.py` | `Tool`, `ToolCall`, `GenerateResult` |
| **RFC-134 (Introspection)** | ✅ Verified | `agent/introspection.py` | Pre-execution validation |
| **RFC-091 (Sanitization)** | ✅ Verified | `models/protocol.py` | `sanitize_llm_content()` |

### Module Changes

| Module | Change Type | Description |
|--------|-------------|-------------|
| `models/tool_emulator.py` | Replace | Use new capability system |
| `models/openai.py` | Modify | Use SchemaAdapter |
| `models/anthropic.py` | Modify | Use SchemaAdapter |
| `models/ollama.py` | Modify | Use capability detection |
| `agent/loop.py` | Modify | Use ToolError for retry logic |

### New Modules

- `models/capability/__init__.py`
- `models/capability/parser.py`
- `models/capability/registry.py`
- `models/capability/schema.py`
- `models/capability/emulation.py`
- `models/capability/streaming.py`
- `models/capability/normalizer.py`
- `models/capability/tool_engineering.py` — Tool description audit and enhancement
- `models/capability/parallel.py` — Parallel execution planning
- `models/capability/validation.py` — Validation-based retry loops
- `models/capability/response_format.py` — Response verbosity control
- `models/capability/namespacing.py` — Multi-service tool namespacing
- `models/capability/evaluation.py` — Evaluation metrics and logging
- `tools/errors.py`

---

## 📚 References

### Internal
- `src/sunwell/models/tool_emulator.py` — Current emulation (to be replaced)
- `src/sunwell/models/protocol.py` — Core protocol definitions
- `src/sunwell/agent/loop.py` — Tool loop using these capabilities
- `src/sunwell/agent/introspection.py` — Pre-execution validation

### External Documentation
- [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) — strict: true achieves 100% schema accuracy
- [Anthropic Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — Key insight: "We spent more time optimizing our tools than the overall prompt"
- [MCP: Writing Effective Tools](https://modelcontextprotocol.info/docs/tutorials/writing-effective-tools/) — Tool description engineering, response format control
- Ollama API reference

### Research Sources (2025-2026)
- [Parallel Tool Calling Strategies](https://www.codeant.ai/blogs/parallel-tool-calling) — 4x latency reduction patterns
- [SHIELDA: Exception Handling in LLM Agents](https://arxiv.org/html/2508.07935v1) — Structured error taxonomy
- [LangGraph: Validation-Based Retry Loops](https://langchain-ai.github.io/langgraph/tutorials/extraction/retries/) — 40%+ success rate improvement
- [Multi-Agent Orchestration Patterns](https://onabout.ai/p/mastering-multi-agent-orchestration-architectures-patterns-roi-benchmarks-for-2025-2026) — Hub-and-spoke vs mesh architectures

### Key Insights Applied
1. **Tool descriptions are prompts** — Invest as much in ACI (Agent-Computer Interface) as HCI
2. **Poka-yoke tools** — Design arguments to make mistakes harder (e.g., absolute paths only)
3. **Strict schemas** — OpenAI strict mode: 100% accuracy vs ~40% without
4. **Response verbosity** — Concise mode saves ~70% tokens
5. **Parallel execution** — Classify read vs write operations for safe parallelization
6. **Validation loops** — Structured feedback enables self-correction
