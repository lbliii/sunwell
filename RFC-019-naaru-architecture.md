# RFC-019: Naaru Architecture

| Field | Value |
|-------|-------|
| **RFC** | 019 |
| **Title** | Naaru Architecture - Coordinated Intelligence for Local Models |
| **Status** | Implemented |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-010 (Core), RFC-016 (Autonomous Mode) |
| **Implements** | `src/sunwell/autonomous/naaru.py` |

---

## Abstract

Local LLMs are getting good, but they're bottlenecked: one model, one GPU, one task at a time. The **Naaru** is Sunwell's answer—a coordinated intelligence architecture that maximizes quality and throughput from small local models.

```
The Problem:   GPU sits idle while fetching memories, loading context, validating
The Solution:  Naaru coordinates parallel helpers while the model thinks

              ┌─────────────────┐
              │      NAARU      │  ← Coordinates everything
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared working memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │  ← Parallel helpers
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

### Component Status

| Component | Naaru Name | Current Implementation | Status |
|-----------|------------|------------------------|--------|
| Coordinator | **Naaru** | `SunwellBrain` | ✅ Implemented |
| Working Memory | **Convergence** | `WorkingMemory` | ✅ Implemented |
| Parallel Helpers | **Shards** | `CognitiveHelper` / `CognitiveHelperPool` | ✅ Implemented |
| Multi-Persona Generation | **Harmonic Synthesis** | `_synthesize_with_lens_consistency()` | ✅ Implemented |
| Feedback Loop | **Resonance** | `Resonance` | ✅ Implemented |
| Lightweight Validation | **Tiered Validation** | `LightweightValidator` | ✅ Implemented |

---

## Motivation

### The Local Model Opportunity

Small models (1-4B parameters) are:
- ✅ Free to run
- ✅ Fast inference (5-20 tok/s on consumer GPU)
- ✅ Private (no API calls)
- ❌ Lower quality than large models
- ❌ Single-threaded (GPU busy = everything waits)

### Hypothesis

We hypothesize that combining multiple techniques can significantly improve small model quality:

| Technique | Expected Gain | Cost | Rationale |
|-----------|---------------|------|-----------|
| **Harmonic Synthesis** | Quality improvement | 3x tokens | Structured variance via personas beats random temperature variance |
| **Resonance** | Fewer rejections | Variable | Iterative refinement catches fixable issues |
| **Shards** | Faster wall-clock | Same tokens | CPU work overlaps with GPU generation |
| **Tiered Validation** | Cost reduction | Same quality | Most proposals don't need full LLM judge |

### Early Results

Initial benchmarks show promising but inconclusive results:

```
2026-01-15 Run (n=2 tasks):
- Effect size: -0.23 (small)
- Statistical significance: Not achieved (p=1.0)
- Claim level: "Insufficient evidence"
```

**More trials needed** to establish statistical significance. The architecture is sound; validation requires larger sample sizes.

---

## Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              NAARU                                       │
│                     (Coordinated Intelligence)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SYNTHESIS                    CONVERGENCE                  VALIDATION   │
│  ┌─────────────┐             ┌───────────┐              ┌─────────────┐ │
│  │ Harmonic    │ ──────────▶ │  7 Slots  │ ──────────▶ │   Tiered    │ │
│  │ Generation  │             │  Working  │              │   Verify    │ │
│  │             │             │  Memory   │              │             │ │
│  │ ┌─────────┐ │             └─────┬─────┘              │ ┌─────────┐ │ │
│  │ │Security │ │                   │                    │ │ Quick   │ │ │
│  │ │ Persona │ │                   │                    │ │ Check   │ │ │
│  │ ├─────────┤ │             ┌─────┴─────┐              │ ├─────────┤ │ │
│  │ │ Quality │ │             │           │              │ │Function │ │ │
│  │ │ Persona │ │─────vote───▶│  SHARDS   │              │ │ Gemma   │ │ │
│  │ ├─────────┤ │             │           │              │ ├─────────┤ │ │
│  │ │   QA    │ │             │ ┌───────┐ │              │ │  Full   │ │ │
│  │ │ Persona │ │             │ │Memory │ │              │ │  LLM    │ │ │
│  │ └─────────┘ │             │ │Fetcher│ │              │ └─────────┘ │ │
│  └─────────────┘             │ ├───────┤ │              └─────────────┘ │
│         ▲                    │ │Context│ │                     │        │
│         │                    │ │Preparer│                      │        │
│         │                    │ ├───────┤ │                     │        │
│         │                    │ │ Look  │ │                     │        │
│         │                    │ │ ahead │ │                     │        │
│         │                    │ └───────┘ │                     │        │
│         │                    └───────────┘                     │        │
│         │                                                      │        │
│         │              RESONANCE (Feedback Loop)               │        │
│         └──────────────────────────────────────────────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Harmonic Synthesis ✅

> **Status**: Implemented in `brain.py:684-808` as `_synthesize_with_lens_consistency()`

Instead of generating once, the Naaru generates with **multiple personas** in parallel, then has them vote on the best solution.

```python
# Each persona brings different expertise
personas = {
    "security": "Focus on attack vectors, defensive coding",
    "quality": "Focus on clean, idiomatic, maintainable code",
    "testing": "Focus on testability, edge cases, failure modes",
}

# Generate in parallel (3 outputs)
candidates = await asyncio.gather(*[
    model.generate(f"{persona}\n{task}") 
    for persona in personas.values()
])

# Vote on best (each persona evaluates all candidates)
votes = await asyncio.gather(*[
    model.generate(f"{persona}\nWhich is best? {candidates}")
    for persona in personas.values()
])

# Winner = majority vote
best = candidates[Counter(votes).most_common(1)[0][0]]
```

**Theory**: Standard self-consistency uses temperature sampling for variance. Lens-weighted consistency uses *structured* variance via domain expertise. Each persona catches different issues.

#### 2. Convergence (Working Memory) ✅

> **Status**: Implemented in `cognitive_helpers.py:59-107` as `WorkingMemory`

Like human cognition, the Naaru maintains ~7 active items in working memory:

```python
class Convergence:
    """Shared working memory with limited capacity (7±2 slots)."""
    
    capacity: int = 7
    slots: list[Slot]
    
    async def add(self, item: Slot):
        """Add item, evicting least relevant if at capacity."""
        if len(self.slots) >= self.capacity:
            self.slots.sort(key=lambda s: s.relevance)
            self.slots.pop(0)  # Evict least relevant
        self.slots.append(item)
```

Slots hold pre-fetched context that Shards gather while the model thinks.

#### 3. Shards (Parallel Helpers) ✅

> **Status**: Implemented in `cognitive_helpers.py:111-420` as `CognitiveHelper` and `CognitiveHelperPool`

While the GPU generates tokens, CPU-bound helpers gather context:

| Shard | Job | Runs On |
|-------|-----|---------|
| **Memory Fetcher** | Query HeadspaceStore for relevant memories | CPU |
| **Context Preparer** | Load lens, embed query, find related files | CPU |
| **Quick Checker** | Syntax validation, structural checks | CPU |
| **Lookahead** | Pre-fetch context for next task in queue | CPU |
| **Consolidator** | Store learnings after task completion | CPU |

```python
# While GPU generates current task...
results = await asyncio.gather(
    model.generate(current_task),  # GPU: slow (5-20s)
    shard_pool.prepare(next_task), # CPU: fast (<1s)
)
# When generation completes, next task's context is ready!
```

#### 4. Resonance (Feedback Loop) ⏳

> **Status**: Planned — not yet implemented

Rejected proposals get refined based on judge feedback:

```
Proposal → Judge → Rejected? → Yes → Refine with feedback → Judge again
                      ↓
                      No → Approved!
```

Max 2-3 refinement attempts before final rejection.

**Implementation plan**:
```python
class Resonance:
    """Feedback loop that refines rejected proposals."""
    
    max_attempts: int = 2
    
    async def refine(self, proposal: dict, rejection: dict) -> dict:
        """Generate improved proposal based on rejection feedback."""
        feedback = rejection.get("issues", [])
        prompt = f"""Previous attempt was rejected for:
{chr(10).join(f'- {issue}' for issue in feedback)}

Improve the code to address these issues:
{proposal['diff']}
"""
        return await self.model.generate(prompt)
```

#### 5. Tiered Validation ✅

> **Status**: Implemented in `lightweight_validator.py`

Not every proposal needs a full LLM evaluation:

```
Proposal → [Quick Check] → Syntax error? → Instant reject
                ↓
           [FunctionGemma 270M] → Confident? → Yes → Return verdict
                ↓
                No (uncertain)
                ↓
           [Full LLM Judge] → Return verdict
```

The `LightweightValidator` runs:
1. **Structural checks** (AST parsing, import analysis, docstring detection)
2. **FunctionGemma** tool-calling for quick decisions
3. **Escalation** only for borderline cases (score between 4.0-8.0)

---

## Current Implementation

### File Mapping

| Current File | Naaru Name | Contains |
|--------------|------------|----------|
| `brain.py` | → `naaru.py` | `SunwellBrain`, `SynthesisWorker`, `ValidationWorker` |
| `cognitive_helpers.py` | → `convergence.py` + `shards.py` | `WorkingMemory`, `CognitiveHelper`, `CognitiveHelperPool` |
| `lightweight_validator.py` | (keep) | `LightweightValidator`, structural checks |
| — | `resonance.py` | Feedback loop (to be created) |

### Existing API

```python
# Current usage (brain.py)
from sunwell.autonomous.brain import SunwellBrain

brain = SunwellBrain(
    synth_model=OllamaModel("gemma3:1b"),
    judge_model=OllamaModel("gemma3:4b"),
    use_lens_consistency=True,  # Enables Harmonic Synthesis
)

results = await brain.think(
    goals=["improve error handling"],
    max_time=120,
)
```

---

## Proposed API

After migration, the API becomes:

```python
from sunwell.autonomous import Naaru, NaaruConfig

# Create Naaru with local models
naaru = Naaru(
    synthesis_model=OllamaModel("gemma3:1b"),
    judge_model=OllamaModel("gemma3:4b"),
    config=NaaruConfig(
        harmonic_synthesis=True,     # Enable persona voting
        convergence_capacity=7,      # Working memory slots
        resonance_max_attempts=2,    # Feedback loop retries
        tiered_validation=True,      # Use FunctionGemma
    ),
)

# Think about goals
results = await naaru.illuminate(
    goals=["improve error handling", "add documentation"],
    max_time_seconds=120,
)

print(f"Proposals approved: {results['approved']}")
print(f"Quality average: {results['quality_avg']:.1f}/10")
```

### CLI Integration

```bash
# Run autonomous mode with Naaru
sunwell autonomous --naaru --time 300

# Options
sunwell autonomous --naaru \
    --harmonic          # Enable persona voting
    --convergence 7     # Working memory slots
    --resonance 2       # Max refinement attempts
    --tiered            # Use FunctionGemma validation
```

---

## Benchmarks

### Methodology

Benchmarks use the framework from RFC-018:
- **Task**: SQL injection detection function
- **Models**: gemma3:1b (synthesis), gemma3:4b (judge)
- **Metrics**: Quality score (0-10), approval rate, token usage, wall-clock time

### Current Results

| Run Date | n | Technique | Effect Size | p-value | Claim Level |
|----------|---|-----------|-------------|---------|-------------|
| 2026-01-15 | 2 | Harmonic vs Baseline | -0.23 (small) | 1.0 | Insufficient |

**Interpretation**: Sample size too small for statistical significance. The negative effect size suggests baseline may have performed better in this small sample, but this is likely noise.

### Target Benchmarks

Once sufficient trials are collected (n≥30), we expect to validate:

| Architecture | Target Quality | Target Approval | Tokens | Time |
|--------------|----------------|-----------------|--------|------|
| Baseline (1B) | 5.0/10 | 60% | 200 | 6s |
| + Harmonic | 6.5-7.5/10 | 75-85% | 600 | 18s |
| + Resonance | 7.0-8.0/10 | 85-95% | 800 | 25s |
| + Shards | Same | Same | 800 | **18s** |
| + Tiered | Same | Same | **400** | 15s |

### Running Benchmarks

```bash
# Test Harmonic Synthesis
python examples/novel_techniques.py --technique lens-consistency

# Test full pipeline (when Resonance is implemented)
python examples/brain_demo.py \
    --synth gemma3:1b \
    --judge-model gemma3:4b \
    --lens-consistency \
    --pipeline \
    --time 120

# Run benchmark suite
python benchmark/run.py --category review --output benchmark/results/
```

---

## Migration Path

### Phase 1: Implement Resonance

Create `resonance.py` with feedback loop logic:

```python
# src/sunwell/autonomous/resonance.py
@dataclass
class Resonance:
    max_attempts: int = 2
    model: Any = None
    
    async def refine(self, proposal: dict, rejection: dict) -> dict | None:
        """Refine a rejected proposal based on feedback."""
        ...
```

### Phase 2: Rename Files

```bash
git mv src/sunwell/autonomous/brain.py src/sunwell/autonomous/naaru.py
git mv src/sunwell/autonomous/cognitive_helpers.py src/sunwell/autonomous/convergence.py
# Extract Shard classes to shards.py
```

Symbol renames:
```python
SunwellBrain       → Naaru
WorkingMemory      → Convergence
CognitiveHelper    → Shard
CognitiveHelperPool → ShardPool
_synthesize_with_lens_consistency → harmonize()
_synthesize_pipelined → illuminate_with_shards()
```

### Phase 3: Update API

- Add `NaaruConfig` dataclass
- Rename `think()` → `illuminate()`
- Add `--naaru` CLI flag
- Update imports in dependent modules

### Phase 4: Validate with Benchmarks

Run comprehensive benchmark suite (n≥30) to establish statistical significance for quality claims.

### Phase 5: Default Mode

Make Naaru the default for autonomous mode when local models detected.

---

## Naming Rationale

### Why "Naaru"?

In World of Warcraft lore:
- **Naaru** are beings of pure Light that coordinate and guide
- They work through harmony and convergence of purpose
- They resonate with power, amplifying those they help
- The **Sunwell** was restored by a Naaru (M'uru)

The metaphor fits:
- **Naaru** = The coordinator (not a literal brain)
- **Convergence** = Shared purpose/working memory
- **Shards** = Fragments of the whole working in parallel
- **Resonance** = Feedback that amplifies quality
- **Harmonic** = Multiple voices in alignment
- **Illuminate** = The Naaru's light reveals the best path

---

## Open Questions

1. **Should Harmonic Synthesis use real lenses?** Currently uses hardcoded personas. Could load from `.lens` files for customization.

2. **Optimal Shard count?** Currently 5 types. Profile to determine if more/fewer improves throughput.

3. **Convergence capacity tuning?** 7 is cognitive psychology's number (Miller's Law), but LLMs may benefit from different capacity.

4. **FunctionGemma confidence threshold?** Current: escalate when score between 4.0-8.0. Tune based on false positive/negative rates.

5. **Resonance iteration limit?** 2-3 attempts seems reasonable, but may need tuning per task type.

---

## References

- [Prompting Guide - Self-Consistency](https://www.promptingguide.ai/techniques/consistency)
- [Miller's Law - 7±2 items](https://en.wikipedia.org/wiki/The_Magical_Number_Seven,_Plus_or_Minus_Two)
- [WoW Lore - Naaru](https://wowpedia.fandom.com/wiki/Naaru)
- RFC-010: Sunwell Core
- RFC-016: Autonomous Mode
- RFC-018: Quality Benchmark Framework
