# RFC: Cloud Model Parity for Core CLI Flows

**Status**: Draft  
**Created**: 2026-01-22  
**Author**: AI Assistant  
**Confidence**: 82% 🟡  
**Category**: CLI  

---

## Executive Summary

Core CLI workflows currently instantiate `OllamaModel` directly even though OpenAI and
Anthropic adapters exist and `model.default_provider` is configurable. This RFC proposes
routing model selection through the existing `create_model()` helper and config defaults
so cloud models are first-class across goal execution, backlog execution, and verification.

---

## Problem Statement

### Current State

The primary goal execution path and other core CLI flows create `OllamaModel` directly,
ignoring `model.default_provider` and the existing OpenAI/Anthropic adapters.

**Evidence**:
- `src/sunwell/cli/main.py:225-238` - `OllamaModel` is constructed directly for goal execution.
- `src/sunwell/cli/backlog_cmd.py:294-309` - backlog execution constructs `OllamaModel`.
- `src/sunwell/cli/verify_cmd.py:87-99` - verification constructs `OllamaModel`.
- `src/sunwell/models/openai.py:1-37` - OpenAI adapter exists.
- `src/sunwell/models/anthropic.py:1-37` - Anthropic adapter exists.
- `src/sunwell/types/config.py:68-79` - config defines `model.default_provider` and `model.default_model`.
- `src/sunwell/cli/helpers.py:69-91` - `create_model()` supports openai/anthropic/ollama.

### Pain Points
- Cloud adapters exist but core CLI paths do not use them.  
  **Evidence**: `src/sunwell/models/openai.py:1-37`, `src/sunwell/cli/main.py:225-238`
- `model.default_provider` and `model.default_model` are not used for core flows.  
  **Evidence**: `src/sunwell/types/config.py:68-79`, `src/sunwell/cli/main.py:225-238`

### Impact

Users cannot select cloud models for the most common CLI flows without modifying code,
even when adapters and config fields are available.

---

## Goals and Non-Goals

### Goals
1. Use `model.default_provider` and `model.default_model` for goal execution, backlog,
   and verification when no CLI override is provided.
2. Allow explicit provider/model selection for these flows without code changes.
3. Keep model creation centralized through the existing `create_model()` helper.

### Non-Goals
1. Add new providers beyond OpenAI, Anthropic, and Ollama.
2. Change model routing logic in chat, apply, or skill flows.
3. Introduce compatibility shims for legacy config fields.

---

## Design Options

### Option A: Inline Provider Selection per CLI Command

**Approach**: In each CLI command, use `get_config()` to read
`cfg.model.default_provider` and `cfg.model.default_model`, then call `create_model()`.

**Implementation**:
```python
from sunwell.config import get_config
from sunwell.cli.helpers import create_model

cfg = get_config()
provider = cfg.model.default_provider
model_name = cfg.model.default_model
llm = create_model(provider, model_name)
```

**Pros**:
- Minimal refactor; touches only the affected command files.

**Cons**:
- Repeats selection logic in multiple files.

**Estimated Effort**: 4-6 hours

---

### Option B: Centralize Selection in `cli.helpers`

**Approach**: Add a helper in `cli/helpers.py` that resolves provider/model from config
and optional CLI overrides, then use it in the three core flows.

**Implementation**:
```python
from sunwell.config import get_config
from sunwell.cli.helpers import create_model

cfg = get_config()
provider = override_provider or cfg.model.default_provider
model_name = override_model or cfg.model.default_model
llm = create_model(provider, model_name)
```

**Pros**:
- Single point of truth for model selection in CLI.
- Easy to extend if new flags are added.

**Cons**:
- Introduces a new helper that must be kept in sync with config semantics.

**Estimated Effort**: 6-8 hours

---

### Option C: Add `--provider` to Core CLI and Use `create_model()`

**Approach**: Extend `sunwell` (goal execution), `sunwell backlog run`,
and `sunwell verify` with a `--provider` flag, then call `create_model()`
using provider + model override.

**Implementation**:
```python
@click.option("--provider", type=click.Choice(["openai", "anthropic", "ollama"]))
@click.option("--model", "-m")
def command(provider: str | None, model: str | None) -> None:
    cfg = get_config()
    provider = provider or cfg.model.default_provider
    model_name = model or cfg.model.default_model
    llm = create_model(provider, model_name)
```

**Pros**:
- Explicit, user-facing control.
- Aligns with existing `--model` flag in `sunwell`.  
  **Evidence**: `src/sunwell/cli/main.py:61-66`

**Cons**:
- CLI surface area grows; needs documentation updates.

**Estimated Effort**: 8-10 hours

---

## Recommended Approach

**Recommendation**: Option B + Option C

**Reasoning**:
1. `create_model()` already supports cloud providers; centralizing selection ensures
   it is used consistently.  
   **Evidence**: `src/sunwell/cli/helpers.py:69-91`
2. The top-level CLI already exposes `--model`, so adding `--provider` is consistent.  
   **Evidence**: `src/sunwell/cli/main.py:61-66`

**Trade-offs accepted**:
- Additional CLI flags and a new helper function.

---

## Architecture Impact

| Subsystem | Impact | Changes |
|-----------|--------|---------|
| `src/sunwell/cli/` | Medium | Replace direct `OllamaModel` usage, add `--provider` flag |
| `src/sunwell/config.py` | Low | No schema changes; read existing defaults |
| `tests/` | Medium | Add CLI tests for provider selection |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Misconfigured provider leads to runtime error | M | M | Validate provider against allowed choices before model creation |
| Hidden dependency on Ollama-only features | M | L | Keep `--provider` opt-in; default still works |

---

## Open Questions

- [ ] Should `--provider` be added to `sunwell backlog execute` and `sunwell backlog autonomous`?
- [ ] Should `model.default_provider` apply to `sunwell verify` by default, or require explicit opt-in?

---

## Implementation Plan (High-Level)

### Phase 1: Selection Helper
- Add a CLI helper that resolves provider/model from config + overrides.

### Phase 2: Core CLI Adoption
- Update `sunwell` goal execution, backlog run, and verification to use the helper.

### Phase 3: CLI Surface + Tests
- Add `--provider` flag to the three commands.
- Add tests for provider selection and fallback behavior.

**Estimated Total Effort**: 10-14 hours

---

## References

- **Evidence**:
  - `src/sunwell/cli/main.py:61-66`
  - `src/sunwell/cli/main.py:225-238`
  - `src/sunwell/cli/backlog_cmd.py:294-309`
  - `src/sunwell/cli/verify_cmd.py:87-99`
  - `src/sunwell/cli/helpers.py:69-91`
  - `src/sunwell/models/openai.py:1-37`
  - `src/sunwell/models/anthropic.py:1-37`
  - `src/sunwell/types/config.py:68-79`
