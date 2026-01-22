# RFC: Cloud Model Parity for Core CLI Flows

**Status**: Implemented  
**Created**: 2026-01-22  
**Author**: AI Assistant  
**Confidence**: 91% 🟢  
**Category**: CLI  

---

## Executive Summary

Core CLI workflows (`sunwell`, `sunwell backlog run`, `sunwell verify`) instantiate `OllamaModel` directly, bypassing the existing `create_model()` helper and `model.default_provider` config. This RFC proposes aligning these commands with the established pattern already used by `sunwell chat`, `sunwell skill`, `sunwell apply`, and `sunwell ask` — adding `--provider` flags and routing through `create_model()`.

---

## Problem Statement

### Current State

The primary goal execution path and other core CLI flows create `OllamaModel` directly, ignoring `model.default_provider` and the existing OpenAI/Anthropic adapters.

**Evidence**:
- `src/sunwell/cli/main.py:225-238` — `OllamaModel` is constructed directly for goal execution.
- `src/sunwell/cli/backlog_cmd.py:294-309` — backlog execution constructs `OllamaModel`.
- `src/sunwell/cli/verify_cmd.py:87-99` — verification constructs `OllamaModel`.

### Existing Pattern (Not Applied)

Multiple CLI commands already support `--provider` + `--model` flags:

| Command | Provider Flag | Model Flag | Evidence |
|---------|---------------|------------|----------|
| `sunwell chat` | `--provider/-p` | `--model/-m` | `cli/chat.py:67-68` |
| `sunwell skill exec` | `--provider/-p` | `--model/-m` | `cli/skill.py:117-118` |
| `sunwell apply` | `--provider/-p` | `--model/-m` | `cli/apply.py:39-40` |
| `sunwell ask` | `--provider/-p` | `--model/-m` | `cli/ask.py:33-34` |
| `sunwell bind` | `--provider/-p` | `--model/-m` | `cli/bind.py:39-40` |

### Infrastructure (Already Exists)

- **Adapters**: `src/sunwell/models/openai.py` (259 lines), `src/sunwell/models/anthropic.py` (271 lines)
- **Helper**: `src/sunwell/cli/helpers.py:69-91` — `create_model()` supports openai, anthropic, ollama, mock
- **Config**: `src/sunwell/types/config.py:68-79` — `ModelConfig` with `default_provider`, `default_model`

### Pain Points

1. **Inconsistency**: Core commands lack `--provider` flag that secondary commands have.
2. **Config ignored**: `model.default_provider` and `model.default_model` are defined but unused in core flows.
3. **Hardcoded defaults**: Users must modify code to use cloud models for goal execution.

### Impact

Users cannot select cloud models for the most common CLI flows (`sunwell "goal"`, `sunwell verify`) without modifying code, even when adapters and config fields are available.

---

## Goals and Non-Goals

### Goals

1. Add `--provider` flag to `sunwell`, `sunwell backlog run`, and `sunwell verify`.
2. Fall back to `model.default_provider` and `model.default_model` from config when no CLI override.
3. Route all model creation through `create_model()` helper.
4. Align core CLI with existing pattern in chat/skill/apply/ask commands.

### Non-Goals

1. Add new providers beyond OpenAI, Anthropic, and Ollama.
2. Change model routing logic in chat, apply, or skill flows (already correct).
3. Introduce compatibility shims for legacy config fields.

---

## Design Options

### Option A: Inline Provider Selection per CLI Command

**Approach**: In each CLI command, read config and call `create_model()` inline.

```python
from sunwell.config import get_config
from sunwell.cli.helpers import create_model

cfg = get_config()
provider = provider_override or cfg.model.default_provider
model_name = model_override or cfg.model.default_model
llm = create_model(provider, model_name)
```

**Pros**: Minimal refactor; touches only the affected command files.  
**Cons**: Repeats selection logic in 3+ files.

**Estimated Effort**: 4-6 hours

---

### Option B: Add Shared Helper `resolve_model()`

**Approach**: Add a helper in `cli/helpers.py` that resolves provider/model from config and optional CLI overrides.

```python
def resolve_model(
    provider_override: str | None = None,
    model_override: str | None = None,
):
    """Resolve model from CLI overrides or config defaults."""
    cfg = get_config()
    provider = provider_override or cfg.model.default_provider
    model_name = model_override or cfg.model.default_model
    return create_model(provider, model_name)
```

**Pros**: Single point of truth; easy to extend.  
**Cons**: Adds one new helper (7-10 lines).

**Estimated Effort**: 6-8 hours

---

### Option C: Add `--provider` Flag to Core Commands (B + CLI Surface)

**Approach**: Extend Option B with explicit `--provider` flags on core commands, matching existing pattern.

```python
@click.option("--provider", "-p", default=None, 
              type=click.Choice(["openai", "anthropic", "ollama"]),
              help="Model provider (default: from config)")
@click.option("--model", "-m", help="Override model selection")
def command(provider: str | None, model: str | None) -> None:
    llm = resolve_model(provider, model)
```

**Pros**: Explicit user control; consistent with `chat`/`skill`/`apply`/`ask`.  
**Cons**: CLI surface grows; needs docstring updates.

**Estimated Effort**: 8-10 hours

---

## Recommended Approach

**Recommendation**: Option C (B + CLI Surface)

**Reasoning**:

1. **Pattern already established**: 5+ commands use `--provider/-p` + `--model/-m` flags.  
   **Evidence**: `cli/chat.py:67-68`, `cli/skill.py:117-118`, `cli/apply.py:39-40`

2. **Infrastructure exists**: `create_model()` supports all providers.  
   **Evidence**: `cli/helpers.py:69-91`

3. **Config ready**: `ModelConfig.default_provider` exists.  
   **Evidence**: `types/config.py:72`

4. **User expectation**: If `sunwell chat --provider anthropic` works, users expect `sunwell --provider anthropic` to work.

**Trade-offs accepted**: Additional CLI flags (consistent with existing pattern).

---

## Architecture Impact

| Subsystem | Impact | Changes |
|-----------|--------|---------|
| `cli/helpers.py` | Low | Add `resolve_model()` helper (~10 lines) |
| `cli/main.py` | Medium | Replace `OllamaModel`, add `--provider` flag |
| `cli/backlog_cmd.py` | Medium | Replace `OllamaModel`, add `--provider` to `run` |
| `cli/verify_cmd.py` | Medium | Replace `OllamaModel`, add `--provider` flag |
| `cli/agent/run.py` | Medium | Add `--provider` flag, use `resolve_model()` |
| `cli/agent/resume.py` | Medium | Add `--provider`/`--model` flags |
| `cli/naaru_cmd.py` | Medium | Add `--provider`/`--model` to process, run, illuminate |
| `cli/plan_cmd.py` | Medium | Add `--provider` flag |
| `cli/reason.py` | Medium | Add `--provider` flag to decide |
| `cli/project_cmd.py` | Medium | Add `--provider` flag to analyze |
| `cli/weakness_cmd.py` | Medium | Add `--provider` flag to fix |
| `cli/interface_cmd.py` | Medium | Add `--provider` flag to process |
| `studio/src-tauri/src/agent.rs` | Medium | Pass `--provider`/`--model` to subprocess |
| `studio/src-tauri/src/commands.rs` | Medium | Add provider/model params to Tauri commands |
| `studio/src-tauri/src/naaru.rs` | Medium | Add provider/model to ProcessInput |
| `studio/src/stores/settings.svelte.ts` | Low | New settings store for provider preference |
| `studio/src/stores/agent.svelte.ts` | Low | Accept provider/model in runGoal |
| `studio/src/components/ProviderSelector.svelte` | Low | New dropdown component |
| `studio/src/components/project/IdleState.svelte` | Low | Add ProviderSelector |
| `studio/src/components/project/DoneState.svelte` | Low | Use settings provider |
| `tests/` | Medium | Add CLI tests for provider selection |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Misconfigured provider leads to runtime error | M | M | `create_model()` already validates and exits with clear error |
| Users don't know about `--provider` | L | L | Add to `--help` output; consistent with other commands |
| API key not set for cloud provider | M | M | Model adapters raise clear `ImportError` / auth errors |

---

## Open Questions (Resolved)

### Q1: Should `--provider` be added to `sunwell backlog execute` and `sunwell backlog autonomous`?

**Recommendation**: Yes for `execute`, defer `autonomous` for now.

**Reasoning**:
- `execute` runs goals directly → needs provider selection
- `autonomous` has complex orchestration → separate RFC if needed
- Keep scope focused on the 3 core paths

### Q2: Should `model.default_provider` apply to `sunwell verify` by default?

**Recommendation**: Yes, use config defaults with CLI override.

**Reasoning**:
- Verification is a core flow users run frequently
- Consistent behavior across all core commands
- Users who want Ollama can set `model.default_provider: ollama` in config

---

## Implementation Plan

### Phase 1: Add `resolve_model()` Helper (2 hours)

**Tasks**:
1. Add `resolve_model(provider_override, model_override)` to `cli/helpers.py`
2. Unit test: verify fallback to config defaults
3. Unit test: verify CLI override takes precedence

**Commit**: `cli: add resolve_model helper for provider/model selection`

### Phase 2: Update Core CLI Commands (4-6 hours)

**Task 2.1**: Update `sunwell` goal execution
- Add `--provider/-p` flag to `cli/main.py:61-73`
- Replace `OllamaModel` construction with `resolve_model()` at lines 225-238
- **Commit**: `cli: add --provider flag to goal execution`

**Task 2.2**: Update `sunwell backlog run`
- Add `--provider/-p` flag to `backlog_cmd.py` `run` command
- Replace `OllamaModel` construction at lines 294-309
- **Commit**: `cli: add --provider flag to backlog run`

**Task 2.3**: Update `sunwell verify`
- Add `--provider/-p` flag to `verify_cmd.py:32-36`
- Replace `OllamaModel` construction at lines 87-99
- **Commit**: `cli: add --provider flag to verify`

### Phase 3: Integration Tests (2-3 hours)

**Tasks**:
1. Test: `sunwell --provider openai "goal"` uses OpenAI
2. Test: `sunwell --provider anthropic "goal"` uses Anthropic
3. Test: Config-only selection (no CLI flag) uses `model.default_provider`
4. Test: `--model` override works with each provider

**Commit**: `tests: add provider selection integration tests`

### Phase 4: Documentation (1 hour)

**Tasks**:
1. Update `--help` docstrings for each command
2. Add example to README or CLI reference

**Commit**: `docs: document --provider flag for core commands`

**Estimated Total Effort**: 10-12 hours

---

## Test Requirements

**Gap identified**: No existing tests for `create_model()` or provider selection.

**Required tests**:

```python
# tests/test_cli_helpers.py
def test_create_model_openai():
    """create_model('openai', 'gpt-4o') returns OpenAIModel."""
    
def test_create_model_anthropic():
    """create_model('anthropic', 'claude-sonnet-4-20250514') returns AnthropicModel."""
    
def test_create_model_ollama():
    """create_model('ollama', 'gemma3:4b') returns OllamaModel."""

def test_resolve_model_uses_config_defaults():
    """resolve_model() with no args uses config.model.default_provider."""

def test_resolve_model_cli_override_takes_precedence():
    """resolve_model(provider='anthropic') ignores config default."""
```

---

## Success Criteria

- [x] `sunwell --provider openai "goal"` uses OpenAI adapter
- [x] `sunwell --provider anthropic "goal"` uses Anthropic adapter  
- [x] `sunwell verify --provider openai file.py` works
- [x] `sunwell backlog run --provider anthropic` works
- [x] Config-only: setting `model.default_provider: anthropic` makes it the default
- [x] All existing `--model` flag behavior preserved
- [x] Tests pass for all provider combinations (`tests/cli/test_cli_helpers.py`)
- [x] Studio Rust backend passes `--provider` and `--model` flags
- [x] Studio Svelte has provider selection UI

---

## References

**Evidence (verified)**:
- `src/sunwell/cli/main.py:61-66` — existing `--model` flag
- `src/sunwell/cli/main.py:225-238` — hardcoded `OllamaModel`
- `src/sunwell/cli/backlog_cmd.py:294-309` — hardcoded `OllamaModel`
- `src/sunwell/cli/verify_cmd.py:87-99` — hardcoded `OllamaModel`
- `src/sunwell/cli/helpers.py:69-91` — `create_model()` helper
- `src/sunwell/cli/chat.py:67-68` — existing `--provider` pattern
- `src/sunwell/cli/skill.py:117-118` — existing `--provider` pattern
- `src/sunwell/cli/apply.py:39-40` — existing `--provider` pattern
- `src/sunwell/cli/ask.py:33-34` — existing `--provider` pattern
- `src/sunwell/models/openai.py` — OpenAI adapter (259 lines)
- `src/sunwell/models/anthropic.py` — Anthropic adapter (271 lines)
- `src/sunwell/types/config.py:68-79` — `ModelConfig` definition
