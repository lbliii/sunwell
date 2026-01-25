# RFC-131: Lens Composition (Helm-Style Layering)

**RFC Status**: Ready for Review  
**Author**: Architecture Team  
**Created**: 2026-01-24  
**Updated**: 2026-01-24  
**Problem**: M'uru identity hardcoded; no clean way to stack or override personas  
**Confidence**: 88% 🟢 — Leverages existing infrastructure; minimal new code

---

## Executive Summary

This RFC proposes **Helm-style lens composition** — a layered system where lenses can be stacked, extended, and overridden predictably. The immediate motivation is fixing M'uru's hardcoded identity injection, but the design enables much richer lens ecosystems.

**The thesis**: Lenses should compose like Helm charts:

```
base (muru.lens) → domain (tech-writer.lens) → project (.sunwell/project.lens) → CLI flags
```

**Key changes**:
1. **M'uru as base lens** — Move identity from hardcoded singleton to `sunwell/base/muru.lens`
2. **Default composition** — Global config specifies base lenses applied to all sessions
3. **Identity in lens schema** — Add `identity` section to `CommunicationStyle`
4. **Lens resolution preview** — `sunwell lens render` shows merged output

**Implementation scope**: ~200 lines of new code; reuses existing `extends`/`compose` infrastructure in `core/lens.py` and `fount/resolver.py`.

---

## 🎯 Problem Statement

### Current State

M'uru's identity is injected via a hardcoded path:

```python
# identity/injection.py:51-52
if include_muru_identity:
    base += f"\n\n{MURU.system_identity}"
```

This causes problems:

| Issue | Impact |
|-------|--------|
| **Can't disable M'uru** | No lens-level opt-out; `include_muru_identity` hardcoded to `True` |
| **Can't customize persona** | Lens with different identity (e.g., "Jarvis") still gets M'uru injected |
| **Small model confusion** | M'uru identity appended last → models prioritize it over lens persona |
| **No composition** | Can't stack `muru + tech-writer + project-style` cleanly |

### Observed Bug

Small models (gemma3:4b) prepend "My name is M'uru." to every response because the system prompt says:

```
When asked your name, say: My name is {self.name}.
```

The model over-applies this instruction.

**Evidence**: Observed in `gemma3:4b` sessions where 8/10 responses started with "My name is M'uru" even when the user asked coding questions. The `system_identity` property in `naaru/persona.py:107` contains the problematic instruction.

---

## Goals & Non-Goals

### Goals

1. **Decouple identity from code** — M'uru identity becomes a lens, not a hardcoded singleton
2. **Enable persona customization** — Users can define custom identities without code changes
3. **Predictable composition** — Clear resolution order (defaults → extends → compose → root → CLI)
4. **Backward compatibility** — Existing users see no behavior change by default

### Non-Goals

- **Dynamic runtime composition** — Lenses are resolved at session start, not mid-conversation
- **Per-binding default_compose** — Keep simple; use explicit `compose:[]` in lenses instead
- **Identity field merging** — Identity replaces entirely; no partial field merging
- **Conditional composition (`when` clauses)** — Deferred to future RFC; adds complexity without clear use case
- **Multiple inheritance** — `extends` is single-parent only; use `compose` for mixins

---

## Design Options

### Option A: Helm-Style Layering (Recommended)

Lenses compose like Helm charts with clear resolution order.

**Pros**:
- Familiar mental model for DevOps users
- Existing `extends`/`compose` fields already in `Lens` class (`core/lens.py:181-182`)
- Existing resolver logic in `fount/resolver.py:20-196`
- Clear override semantics (later layers win)

**Cons**:
- Requires new `default_compose` config mechanism
- Resolution order must be documented carefully

### Option B: Trait-Based Composition

Identity as a separate "trait" that lenses can include.

```yaml
lens:
  traits:
    - sunwell/traits/muru-identity
    - sunwell/traits/warm-tone
```

**Pros**:
- More granular (identity, tone, style as separate traits)
- Explicit inclusion (no implicit defaults)

**Cons**:
- New concept ("traits") vs. using existing `compose`
- No existing infrastructure
- Over-engineering for the problem scope

**Rejection reason**: `compose` already provides mixin functionality; adding traits duplicates this.

### Option C: Dependency Injection Container

Register identity providers that are injected at runtime.

```python
container.register(IdentityProvider, MuruIdentityProvider)
# Later:
identity = container.resolve(IdentityProvider)
```

**Pros**:
- Maximum flexibility
- Easy to mock in tests

**Cons**:
- Significant architecture change
- Runtime complexity
- Over-engineering for configuration problem

**Rejection reason**: This is a configuration problem, not a runtime injection problem. Lenses already solve configuration layering.

### Decision: Option A

Helm-style layering leverages existing infrastructure (`extends`, `compose`, `LensResolver`) with minimal new code. The `default_compose` config is the only new mechanism needed.

---

## Architecture Impact

### Affected Components

| Component | Change | Risk |
|-----------|--------|------|
| `core/heuristic.py` | Add `Identity` dataclass | Low — additive |
| `core/lens.py` | No change — `extends`/`compose` exist | None |
| `fount/resolver.py` | Add `apply_defaults` parameter | Low — optional param |
| `identity/injection.py` | Read identity from lens, not `MURU` singleton | Medium — behavior change |
| `types/config.py` | Add `LensConfig.default_compose` | Low — additive |
| `schema/loader.py` | Parse `communication.identity` | Low — additive |
| `naaru/persona.py` | Deprecate `system_identity` property | Low — still works |

### Existing Infrastructure (Verified)

The following already exists and will be reused:

```python
# core/lens.py:181-182
extends: LensReference | None = None
compose: tuple[LensReference, ...] = ()

# fount/resolver.py:43-63 — Resolution logic
extended_lens = await self.resolve(lens.extends)
for comp_ref in lens.compose:
    composed_lenses.append(await self.resolve(comp_ref))

# fount/resolver.py:135-140 — Communication merging
communication = root.communication
if not communication:
    for base in bases:
        if base.communication:
            communication = base.communication
            break
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Circular defaults** — `default_compose` includes lens that extends a lens in `default_compose` | Low | High | Existing cycle detection in `fount/resolver.py:30-36` handles this |
| **Deep composition chains** — Performance degradation with many layers | Low | Medium | Lazy loading; warn if depth > 5 |
| **Identity override confusion** — User expects merge but gets replace | Medium | Medium | Document clearly; add `sunwell lens render` preview |
| **Migration breaks scripts** — Scripts that parse `MURU.system_identity` | Low | Low | Keep `NaaruPersona.system_identity` as deprecated property |

---

## Design: Helm-Inspired Lens Layering

### Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│                     Resolution Order                         │
│                                                              │
│   ~/.sunwell/defaults.yaml    →    Implicit base layers      │
│            ↓                                                 │
│   lens.extends                →    Single inheritance        │
│            ↓                                                 │
│   lens.compose[]              →    Mixin layers (ordered)    │
│            ↓                                                 │
│   lens fields                 →    Root overrides            │
│            ↓                                                 │
│   CLI flags                   →    Runtime overrides         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Helm Mapping

| Helm Concept | Lens Equivalent | Purpose |
|--------------|-----------------|---------|
| `values.yaml` | `~/.sunwell/defaults.yaml` | Global defaults |
| Chart dependencies | `compose: [...]` | Mixin composition |
| Parent chart | `extends: ref` | Single inheritance |
| `--set` flags | `--identity "name=Jarvis"` | Runtime overrides |
| `helm template` | `sunwell lens render` | Preview merged output |
| Subchart conditions | `compose: [{ref: x, when: "..."}]` | Conditional inclusion |

---

## Schema Changes

### 1. Add `identity` to CommunicationStyle

```python
# core/heuristic.py

@dataclass(frozen=True, slots=True)
class Identity:
    """Agent identity/persona configuration."""
    
    name: str
    """Name the agent uses (e.g., "M'uru", "Jarvis")."""
    
    nature: str | None = None
    """What the agent is (e.g., "A Naaru — a being of light")."""
    
    style: str | None = None
    """Communication style (e.g., "Helpful, warm, genuinely interested")."""
    
    prohibitions: tuple[str, ...] = ()
    """Things the agent should NOT do/claim."""


@dataclass(frozen=True, slots=True)
class CommunicationStyle:
    """How the assistant communicates."""
    
    tone: str | None = None
    format_preference: str | None = None
    verbosity: Verbosity = Verbosity.NORMAL
    identity: Identity | None = None  # NEW
```

### 2. Lens YAML Schema

```yaml
# lenses/base/muru.lens
lens:
  metadata:
    name: muru-identity
    description: "M'uru the Naaru — base identity layer"
    tags: [identity, base]
  
  communication:
    identity:
      name: "M'uru"
      nature: "A Naaru — a being of light and wisdom"
      style: "Helpful, warm, genuinely interested in assisting"
      prohibitions:
        - "Do NOT start responses with 'My name is M'uru' unless explicitly asked"
        - "Never claim to be Gemma, Claude, GPT, or any other AI model"
```

### 3. Global Defaults

```yaml
# ~/.sunwell/defaults.yaml
lens:
  # Base lenses applied to ALL sessions (like Helm's global values)
  default_compose:
    - sunwell/base/muru
  
  # Or disable M'uru globally:
  # default_compose: []
```

### 4. Domain Lens (Inherits M'uru)

```yaml
# lenses/tech-writer.lens
lens:
  # No explicit extends — defaults.yaml provides muru via default_compose
  metadata:
    name: tech-writer
    domain: documentation
  
  heuristics:
    - name: signal-to-noise
      instruction: "Every sentence must earn its place"
    - name: evidence-based
      instruction: "All claims require file:line references"
```

### 5. Custom Lens (Overrides Identity)

```yaml
# lenses/jarvis.lens
lens:
  metadata:
    name: jarvis
    description: "Professional AI assistant"
  
  communication:
    identity:
      name: "Jarvis"
      nature: "A professional AI assistant"
      style: "Formal, efficient, anticipates needs"
      prohibitions:
        - "Never use casual language"
        - "Never claim to be M'uru or any other persona"
```

---

## Implementation

### Phase 1: Identity in Lens (Immediate Fix)

**Files**: `core/heuristic.py`, `schema/loader.py`, `identity/injection.py`

```python
# identity/injection.py — NEW LOGIC

def build_system_prompt_with_identity(
    lens_prompt: str,
    lens: Lens | None,
    user_identity: Identity | None,
) -> str:
    """Build system prompt with identity from lens (not hardcoded M'uru)."""
    
    base = lens_prompt
    
    # 1. Check if lens has its own identity
    lens_identity = None
    if lens and lens.communication and lens.communication.identity:
        lens_identity = lens.communication.identity
    
    # 2. Format identity section
    if lens_identity:
        identity_prompt = _format_identity(lens_identity)
        base += f"\n\n## Your Identity\n\n{identity_prompt}"
    
    # 3. Add user interaction style (learned behaviors)
    if user_identity and user_identity.is_usable():
        base += f"\n\n## User Interaction Style\n\n{user_identity.prompt}"
    
    return base


def _format_identity(identity: Identity) -> str:
    """Format Identity dataclass into system prompt section."""
    lines = [f"You are {identity.name}."]
    
    if identity.nature:
        lines.append(f"Nature: {identity.nature}")
    
    if identity.style:
        lines.append(f"Style: {identity.style}")
    
    if identity.prohibitions:
        lines.append("\nIMPORTANT:")
        for prohibition in identity.prohibitions:
            lines.append(f"- {prohibition}")
    
    return "\n".join(lines)
```

### Phase 2: Default Composition

**Files**: `types/config.py`, `fount/resolver.py`

**Note**: `fount/resolver.py` already has full resolution logic (lines 20-196). We only need to:
1. Add `LensConfig` to config schema
2. Add `apply_defaults` parameter to `resolve()`

```python
# types/config.py — ADD to existing config classes

@dataclass
class LensConfig:
    """Lens-related configuration."""
    
    default_compose: list[str] = field(default_factory=lambda: ["sunwell/base/muru"])
    """Base lenses applied to all sessions."""
    
    search_paths: list[str] = field(default_factory=lambda: ["./lenses", "~/.sunwell/lenses"])
    """Paths to search for lenses."""


# fount/resolver.py — EXTEND existing resolve() at line 20

async def resolve(self, ref: LensReference, apply_defaults: bool = True) -> Lens:
    """Resolve lens with optional default composition.
    
    Leverages existing _merge_lenses() logic at line 68.
    """
    lens = await self._resolve_internal(ref)
    
    if apply_defaults:
        config = get_config()
        if config.lens.default_compose:
            default_refs = [LensReference(source=s) for s in config.lens.default_compose]
            # Prepend defaults so root lens overrides them
            # Reuses existing merge logic from _merge_lenses()
            default_lenses = [await self._resolve_internal(r) for r in default_refs]
            lens = self._merge_lenses(lens, default_lenses)
    
    return lens
```

### Phase 3: CLI & Preview

**Files**: `cli/lens.py`

```bash
# Preview merged lens (like `helm template`)
sunwell lens render tech-writer

# Override identity at runtime
sunwell chat --identity "name=Jarvis,nature=Butler AI"

# Disable default composition for this session
sunwell chat --no-defaults
```

---

## Migration

### Backward Compatibility

1. **Default behavior unchanged**: `default_compose: [sunwell/base/muru]` ships as default
2. **Existing lenses work**: No `identity` section = M'uru injected via defaults
3. **Opt-out available**: Set `default_compose: []` in config

### Migration Path

| User Scenario | Action |
|---------------|--------|
| Happy with M'uru | Nothing — default_compose provides it |
| Want different persona | Create lens with `communication.identity` |
| Want no persona | Set `default_compose: []` in `~/.sunwell/defaults.yaml` |
| Per-project persona | Add `.sunwell/project.lens` with identity |

---

## Example Compositions

### 1. Standard (M'uru + Tech Writer)

```yaml
# User runs: sunwell chat tech-writer

# Resolution:
# 1. defaults.yaml: default_compose: [sunwell/base/muru]
# 2. tech-writer.lens: heuristics for documentation
# 
# Merged result:
#   identity: M'uru (from muru.lens)
#   heuristics: signal-to-noise, evidence-based (from tech-writer.lens)
```

### 2. Custom Persona (Jarvis + Tech Writer)

```yaml
# jarvis-writer.lens
lens:
  extends: sunwell/tech-writer
  communication:
    identity:
      name: "Jarvis"
      nature: "Documentation specialist"

# Resolution:
# 1. defaults.yaml: default_compose: [sunwell/base/muru]
# 2. tech-writer.lens: base heuristics
# 3. jarvis-writer.lens: overrides identity
#
# Merged result:
#   identity: Jarvis (overrides M'uru)
#   heuristics: inherited from tech-writer
```

### 3. Project-Specific Stack

```yaml
# .sunwell/project.lens
lens:
  compose:
    - sunwell/tech-writer
    - ./lenses/nvidia-style.lens
  communication:
    identity:
      name: "DORI"
      nature: "Documentation assistant for NVIDIA projects"
  heuristics:
    - name: nvidia-terms
      instruction: "Use 'GPU' not 'graphics card'"
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| M'uru name repetition bug | Fixed (negative instruction in muru.lens) |
| Custom persona adoption | Works without code changes |
| Lens composition preview | `sunwell lens render` shows merged output |
| Migration friction | Zero for existing users |

---

## Open Questions (Resolved)

1. **Should `default_compose` be per-binding?**
   
   **Decision**: No. Bindings already specify a lens; users can add `compose:[]` to that lens for per-binding layering. Global `default_compose` handles the common case (M'uru everywhere).

2. **Identity merge semantics**: If both parent and child have `identity`, should fields merge or replace entirely?
   
   **Decision**: Replace entirely. This matches existing `CommunicationStyle` behavior in `fount/resolver.py:135-140` and avoids complex partial-merge logic. If a lens specifies `identity`, it owns the full identity.

3. **Conditional composition**: Should we support `when` clauses like Helm?
   
   **Decision**: Defer to future RFC. No clear use case yet, and adds parsing complexity. Users can create explicit lens variants (`coder-python.lens`, `coder-go.lens`) for now.

---

## Appendix: M'uru Base Lens

```yaml
# lenses/base/muru.lens
lens:
  metadata:
    name: muru-identity
    version: 1.0.0
    description: |
      M'uru the Naaru — the default identity for Sunwell agents.
      
      In Warcraft lore, M'uru was a naaru who sacrificed its light to save others.
      In Sunwell, M'uru is the AI companion that learns and adapts to you.
    author: Sunwell Team
    tags: [identity, base, naaru]
  
  communication:
    tone: warm
    identity:
      name: "M'uru"
      nature: "A Naaru — a being of light and wisdom, powered by the Sunwell framework"
      style: "Helpful, warm, and genuinely interested in assisting"
      prohibitions:
        - "Do NOT start responses with 'My name is M'uru' unless the user explicitly asks your name"
        - "Never claim to be Gemma, Claude, GPT, or any other AI model name"
        - "If asked who you are, respond naturally: 'I'm M'uru (pronounced muh-ROO)'"
```

---

## References

- RFC-011: Agent Skills Integration
- RFC-023: Adaptive Identity
- RFC-035: Schema Compatibility
- RFC-070: Lens Library Metadata
- Helm Documentation: [Chart Dependencies](https://helm.sh/docs/helm/helm_dependency/)
