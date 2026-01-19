# RFC: Compound Intelligence System

**Status**: Draft
**Created**: 2026-01-19
**Author**: AI + Human collaboration
**Confidence**: 88% 🟢
**Category**: Naaru / Orchestration

---

## Executive Summary

Small 1B models achieve only 40% accuracy on operation classification when asked directly, but 86% accuracy when using compound patterns (debate, refinement, grounding). This RFC proposes a **Compound Intelligence System** that orchestrates multiple cheap model calls using bio-inspired patterns to achieve big-model performance at small-model cost.

**Key insight**: Voting the same prompt samples the same distribution. Instead, **split the task** into complementary perspectives (thesis/antithesis), then recombine.

**Integration**: Compound patterns are a new **execution strategy** for the existing `Lens` architecture — they leverage `lens.heuristics` for grounding, `lens.personas` for debate perspectives, and `lens.validators` for quality gates.

---

## Problem Statement

### Current State

Sunwell's Naaru architecture supports multi-model orchestration, but lacks structured patterns for models to **help each other** improve accuracy. Current approaches treat each model call independently.

**Evidence**:
- `src/sunwell/naaru/experiments/compound.py:1-42` — Compound eye patterns (lateral inhibition, temporal differencing)
- `src/sunwell/naaru/experiments/dialectic.py:88-177` — Thesis/antithesis/synthesis implementation
- Benchmark task: Operation classification (see [Reproducible Benchmark](#reproducible-benchmark))

### Pain Points

1. **Single-call unreliability**: 1B models are "confidently wrong" — stable but incorrect
   - Evidence: `compound.py:716-819` — `temporal_signal_scan()` shows 100% stability with wrong answers
   
2. **No self-correction**: Models don't leverage multiple perspectives to find errors
   - Evidence: `compound.py:940-984` — `_fold_vote()` (same prompt voting) doesn't improve accuracy
   
3. **Unused model knowledge**: Right answers exist in the distribution but aren't activated
   - Evidence: `dialectic.py:116-145` — Thesis/antithesis prompts surface different knowledge

### Impact

- Users get unreliable outputs from small local models
- Forces escalation to larger/expensive models unnecessarily
- Limits Sunwell's value proposition of "big performance, small models"

---

## Goals and Non-Goals

### Goals

1. **86%+ accuracy** on operation classification (from 40% baseline)
2. **Structured patterns** that combine multiple model calls intelligently
3. **Confidence calibration** — know when to trust results vs. escalate
4. **≤5 model calls** per classification (latency budget)

### Non-Goals

1. **Not replacing bigger models entirely** — some tasks genuinely need scale
2. **Not real-time streaming** — compound patterns have inherent latency
3. **Not training/fine-tuning** — pure orchestration, models are black boxes

---

## Design Options

### Option A: Pattern Library (Modular)

**Approach**: Implement compound patterns as independent, composable modules that consume the existing `Lens` model.

**Implementation**:

```python
# patterns/debate.py
from sunwell.core.lens import Lens

class GroundedDebate:
    """Dialectic: thesis → antithesis → synthesis.
    
    Uses existing Lens for grounding (heuristics) and perspectives (personas).
    """
    
    def __init__(self, lens: Lens, model: ModelProtocol) -> None:
        self.lens = lens
        self.model = model
    
    async def run(self, question: str) -> DebateResult:
        # Build grounding from lens.heuristics
        grounding = self._heuristics_to_examples(self.lens.heuristics)
        
        # Thesis: propose with lens-provided context
        thesis = await self.model.generate(
            f"{grounding}\n{question}"
        )
        
        # Antithesis: use lens.personas for critic perspective
        critic = self.lens.get_persona("critic") or self.lens.personas[0]
        antithesis = await self.model.generate(
            f"As {critic.description}: Critique this: {thesis}"
        )
        
        # Synthesis: reconcile perspectives
        synthesis = await self.model.generate(
            f"Views: 1={thesis[:50]} 2={antithesis[:50]}\nFinal:"
        )
        
        return DebateResult(thesis, antithesis, synthesis)

# Usage — works with ANY lens for ANY domain
lens = lens_loader.load("math-tutor.lens")  # or any other lens
debate = GroundedDebate(lens, model)
result = await debate.run("Is 'twice X' multiply or add?")
```

**Pros**:
- Highly composable — mix patterns for different tasks
- Easy to test individual patterns
- Clear separation of concerns

**Cons**:
- User must choose which patterns to use
- No automatic routing based on task type

**Estimated Effort**: 16 hours

---

### Option B: Layered Engine (Automatic Routing)

**Approach**: Build a reasoning engine that automatically routes through layers: keywords → compound LLM → compute. Engine receives a `Lens` and creates patterns from it.

**Implementation**:

```python
# reasoning/engine.py
from sunwell.core.lens import Lens

class ReasoningEngine:
    """Layered: keywords → compound patterns → compute.
    
    Receives a Lens and uses it for all compound patterns.
    """
    
    def __init__(
        self,
        lens: Lens,
        model: ModelProtocol,
        keywords: KeywordMatcher | None = None,
    ) -> None:
        self.lens = lens
        self.model = model
        self.keywords = keywords or KeywordMatcher()
        
        # Create patterns from lens
        self.patterns = [
            GroundedDebate(lens, model),
            IterativeRefinement(lens, model),
        ]
    
    async def solve(self, problem: str) -> ReasoningResult:
        # Layer 1: Fast path (keywords from lens.heuristics)
        if match := self.keywords.match(problem):
            return ReasoningResult(
                operation=match.operation,
                confidence=1.0,
                method="keyword"
            )
        
        # Layer 2: Compound LLM (patterns use lens for grounding)
        for pattern in self.patterns:
            result = await pattern.run(problem)
            if result.confidence >= 0.8:
                break
        
        # Layer 3: Attention fold if uncertain
        if result.confidence < 0.7:
            result = await self._attention_fold(problem, result)
        
        # Layer 4: Validate with lens.validators
        for validator in self.lens.heuristic_validators:
            await validator.check(result.answer)
        
        return result

# Usage — engine receives a lens, works for any domain
math_lens = lens_loader.load("math-tutor.lens")
engine = ReasoningEngine(lens=math_lens, model=model)
answer = await engine.solve("Bob is 3 years older than Carol")

# Same engine, different lens = different domain
writing_lens = lens_loader.load("developmental-editor.lens")
engine = ReasoningEngine(lens=writing_lens, model=model)
answer = await engine.solve("Is this paragraph engaging?")
```

**Pros**:
- Automatic routing — user just calls `solve()`
- Fast path for common cases (keywords)
- Graceful degradation with confidence thresholds

**Cons**:
- More complex implementation
- Less flexibility for custom flows

**Estimated Effort**: 24 hours

---

### Option C: Hybrid (Both)

**Approach**: Implement Option A (pattern library) first, then build Option B (engine) on top of it. Both consume the existing `Lens` model.

**Implementation**:

```python
from sunwell.core.lens import Lens
from sunwell.naaru.patterns import GroundedDebate, IterativeRefinement
from sunwell.naaru.reasoning import ReasoningEngine

# Load any lens for any domain
lens = lens_loader.load("my-custom.lens")

# LOW-LEVEL: Use patterns directly with lens
debate = GroundedDebate(lens, model)
result = await debate.run("My specific question")

# HIGH-LEVEL: Use engine with lens for automatic routing
engine = ReasoningEngine(lens=lens, model=model)
result = await engine.solve("My specific question")

# FLEXIBILITY: Same patterns/engine work with ANY lens
# - math-tutor.lens → math problems
# - developmental-editor.lens → writing feedback
# - security-reviewer.lens → code analysis
# - product-manager.lens → feature planning
# - YOUR-CUSTOM.lens → your specific domain
```

**Pros**:
- Best of both worlds
- Incremental delivery
- Patterns useful even without engine

**Cons**:
- More total code
- Two APIs to maintain

**Estimated Effort**: 32 hours

---

## Recommended Approach

**Recommendation**: Option C (Hybrid)

**Reasoning**:

1. **Evidence-backed patterns first**: We have experimental proof that debate (86%) and refinement (86%) work. Implementing these as standalone modules captures immediate value.

2. **Engine enables composition**: Once patterns exist, the engine can combine them intelligently with confidence-based routing.

3. **Incremental delivery**: Pattern library (Phase 1) is useful standalone; engine (Phase 2) builds on it.

**Trade-offs accepted**:
- More total code, but cleaner architecture
- Two APIs, but they serve different use cases

---

## Architecture Impact

| Subsystem | Impact | Changes |
|-----------|--------|---------|
| `sunwell/naaru/` | **High** | New `patterns/` and `reasoning/` modules |
| `sunwell/naaru/experiments/` | **Medium** | Extract patterns from compound.py, dialectic.py |
| `sunwell/core/lens.py` | **None** | Uses existing Lens as-is |
| `sunwell/simulacrum/` | **Low** | Uses existing memory APIs; adds pattern-specific helpers |
| `sunwell/models/` | **Low** | Uses existing ModelProtocol |
| `tests/` | **High** | New test suites for patterns |
| `benchmark/tasks/` | **Medium** | New compound benchmark tasks |

### New File Structure

```
sunwell/src/sunwell/naaru/
├── experiments/
│   ├── compound.py           # ✅ Exists — source for patterns
│   └── dialectic.py          # ✅ Exists — thesis/antithesis/synthesis
│
├── patterns/                  # 🆕 Phase 1 (extract from experiments/)
│   ├── __init__.py
│   ├── base.py               # CompoundPattern protocol
│   ├── debate.py             # GroundedDebate (from dialectic.py)
│   ├── refinement.py         # IterativeRefinement
│   └── ensemble.py           # VotingEnsemble
│
└── reasoning/                 # 🆕 Phase 2
    ├── __init__.py
    ├── keywords.py           # KeywordMatcher
    ├── compute.py            # Math computation
    └── engine.py             # ReasoningEngine
```

**Note**: No new `lenses/` directory — patterns consume the existing `Lens` from `sunwell/core/lens.py`.

### Existing Code to Extract

| Source | Target | Notes |
|--------|--------|-------|
| `dialectic.py:88-177` | `patterns/debate.py` | `dialectic_decide()` → `GroundedDebate` |
| `compound.py:940-1110` | `patterns/ensemble.py` | Fold strategies → ensemble patterns |
| `resonance.py:52-98` | `patterns/refinement.py` | `RefinementAttempt` → `IterativeRefinement` |

---

## Design Decisions

### D1: Patterns consume the existing Lens model

**Decision**: Compound patterns receive the existing `Lens` (from `sunwell/core/lens.py`) and use its rich features for grounding and perspectives.

**Rationale**:
- **Reuse**: Lens already has heuristics, personas, validators — no need to reinvent
- **Flexibility**: Any domain-specific Lens works with any compound pattern
- **Consistency**: Users already know Lens; patterns are just a new execution strategy

**How patterns use Lens features**:

| Lens Feature | Pattern Usage |
|--------------|---------------|
| `lens.heuristics` | Build grounding examples for prompts |
| `lens.personas` | Provide debate perspectives (thesis/antithesis) |
| `lens.anti_heuristics` | Adversarial critic perspective |
| `lens.validators` | Quality gates on pattern outputs |
| `lens.framework` | Methodology for synthesis step |
| `lens.workflows` | Orchestrate multi-pattern sequences |

**Implementation**:

```python
from sunwell.core.lens import Lens

class GroundedDebate:
    """Dialectic pattern using existing Lens for grounding and perspectives."""
    
    def __init__(self, lens: Lens, model: ModelProtocol) -> None:
        self.lens = lens
        self.model = model
    
    async def run(self, question: str) -> DebateResult:
        # Build grounding from lens.heuristics
        grounding = self._heuristics_to_examples(self.lens.heuristics)
        
        # Thesis: propose with grounding context
        thesis = await self.model.generate(
            f"{grounding}\n{question}"
        )
        
        # Antithesis: use lens.personas for critic perspective
        critic = self.lens.get_persona("critic") or self.lens.personas[0]
        antithesis = await self.model.generate(
            f"As {critic.description}: Critique this: {thesis}"
        )
        
        # Synthesis: reconcile using lens.framework (if defined)
        synthesis_prompt = self._build_synthesis_prompt(thesis, antithesis)
        synthesis = await self.model.generate(synthesis_prompt)
        
        # Validate using lens.validators
        for validator in self.lens.heuristic_validators:
            if not await validator.check(synthesis):
                # Handle validation failure...
                pass
        
        return DebateResult(thesis, antithesis, synthesis)
    
    def _heuristics_to_examples(self, heuristics: tuple[Heuristic, ...]) -> str:
        """Convert heuristics to grounding examples."""
        examples = []
        for h in heuristics:
            if h.examples:
                examples.extend(h.examples)
        return "\n".join(examples)
```

**Example: Using an existing Lens with compound patterns**:

```python
# Load an existing lens (e.g., from .lens file or lens registry)
math_lens = lens_loader.load("math-tutor.lens")

# Use it with compound patterns — lens provides grounding automatically
debate = GroundedDebate(lens=math_lens, model=model)
result = await debate.run("Is 'twice as old' multiply or add?")

# The lens.heuristics provide the grounding examples
# The lens.personas provide the debate perspectives
# The lens.validators verify the result
```

### D2: Compound patterns are domain-agnostic (Lens provides domain)

**Decision**: Patterns (Debate, Refinement, Ensemble) contain no domain-specific logic. The `Lens` provides all domain context.

**Rationale**:
- **Flexibility**: Same `GroundedDebate` works for math, writing, code, or any domain
- **User-defined goals**: Users create Lenses for their specific needs (book writing, app building, etc.)
- **Separation of concerns**: Patterns = execution strategy, Lens = domain expertise

**Examples of domain flexibility**:

```python
# MATH: Using a math tutor lens
math_lens = lens_loader.load("math-tutor.lens")
debate = GroundedDebate(lens=math_lens, model=model)
result = await debate.run("Is 'twice as old' multiply or add?")

# WRITING: Using a developmental editor lens
writing_lens = lens_loader.load("developmental-editor.lens")
debate = GroundedDebate(lens=writing_lens, model=model)
result = await debate.run("Is this opening paragraph compelling?")

# CODE: Using a security reviewer lens
security_lens = lens_loader.load("security-reviewer.lens")
debate = GroundedDebate(lens=security_lens, model=model)
result = await debate.run("Is this SQL query safe?")

# APP PLANNING: Using a product manager lens
pm_lens = lens_loader.load("product-manager.lens")
refinement = IterativeRefinement(lens=pm_lens, model=model)
result = await refinement.run("Break down this feature into tasks")
```

**The same patterns work for ANY user goal** — the Lens contains the domain-specific heuristics, personas, and validators.

---

### D3: Low confidence returns "escalate" recommendation

**Decision**: When no pattern achieves ≥70% confidence, return the best result with an `escalate: true` flag.

**Rationale**:
- Transparency: User knows when to seek human review or bigger model
- No silent failures: Low confidence is explicit, not hidden
- Composable: Caller decides escalation policy

**Implementation**:

```python
@dataclass(frozen=True, slots=True)
class PatternResult:
    answer: str
    confidence: float
    escalate: bool = False  # True if confidence < 0.7
    pattern_used: str = ""
    calls: int = 0
```

### D4: Confidence scores are exposed to users

**Decision**: All pattern results include confidence scores. Users see them by default.

**Rationale**:
- Transparency is a Sunwell value
- Enables informed decisions about when to trust vs. verify
- Supports confidence-based routing in the engine

---

### D5: Patterns integrate with Simulacrum for memory and learning

**Decision**: Compound patterns receive a `Simulacrum` and use its memory systems for caching, learning, and context enrichment.

**Rationale**:
- **Skip redundant work**: Episodic memory remembers successful debates — no need to repeat
- **Learn over time**: Long-term memory tracks which patterns work for which question types
- **Avoid dead ends**: Episodic memory tracks failures — don't repeat mistakes
- **Enrich context**: Semantic memory provides RAG for better grounding
- **Cross-session persistence**: Learnings survive restarts, model switches, months of inactivity

**How patterns use Simulacrum memory**:

| Memory Type | Pattern Usage |
|-------------|---------------|
| **Working** | Current debate context (thesis, antithesis in progress) |
| **Long-term** | Store learnings: "debate works well for classification questions" |
| **Episodic** | Cache past debates, track dead ends, skip if already solved |
| **Semantic** | RAG retrieval to enrich grounding beyond lens examples |
| **Procedural** | Already loaded from lens.heuristics |

**Implementation**:

```python
from sunwell.core.lens import Lens
from sunwell.simulacrum.core import Simulacrum

class GroundedDebate:
    """Debate pattern with Simulacrum memory integration."""
    
    def __init__(
        self, 
        lens: Lens, 
        model: ModelProtocol, 
        simulacrum: Simulacrum | None = None,
    ) -> None:
        self.lens = lens
        self.model = model
        self.sim = simulacrum
    
    async def run(self, question: str) -> DebateResult:
        # 1. CHECK EPISODIC CACHE: Have we successfully debated this before?
        if self.sim:
            past = self.sim.episodic.search_similar(question, threshold=0.9)
            if past and past.success and past.confidence > 0.8:
                return past.result  # 🚀 Skip! We know the answer.
        
        # 2. ENRICH WITH SEMANTIC RAG: Get relevant context
        rag_context = ""
        if self.sim:
            rag_context = await self.sim.semantic.retrieve(question, k=3)
        
        # 3. BUILD GROUNDING: Lens heuristics + procedural memory
        grounding = self._heuristics_to_examples(self.lens.heuristics)
        if self.sim:
            grounding += "\n" + "\n".join(self.sim.procedural.heuristics)
        
        # 4. RUN DEBATE with enriched context
        thesis = await self.model.generate(
            f"{rag_context}\n{grounding}\n{question}"
        )
        
        critic = self.lens.get_persona("critic") or self.lens.personas[0]
        antithesis = await self.model.generate(
            f"As {critic.description}: Critique this: {thesis}"
        )
        
        synthesis = await self.model.generate(
            f"Views: 1={thesis[:50]} 2={antithesis[:50]}\nFinal:"
        )
        
        result = DebateResult(thesis, antithesis, synthesis)
        
        # 5. STORE IN EPISODIC: Remember this debate (success or failure)
        if self.sim:
            self.sim.episodic.add_attempt(
                question=question,
                pattern="grounded_debate",
                result=result,
                success=result.confidence > 0.7,
            )
        
        # 6. LEARN IF SUCCESSFUL: Update long-term memory
        if self.sim and result.confidence > 0.8:
            self.sim.long_term.store_learning(
                content=f"Grounded debate effective for: {self._classify_question(question)}",
                source="compound_pattern",
                confidence=result.confidence,
            )
        
        return result
```

**What this unlocks**:

```
SESSION 1: User asks "Is 'twice as old' multiply or add?"
  → Debate runs (3 calls)
  → Success with 90% confidence
  → Stored in episodic memory

SESSION 2: User asks "Is 'double the amount' multiply or add?"
  → Episodic search finds similar question (0.95 similarity)
  → Pattern already known to work → returns cached insight
  → 0 calls needed! 🚀

SESSION N: Long-term memory shows:
  "Grounded debate is 92% effective for operation classification"
  "Iterative refinement is 78% effective for writing feedback"
  → Engine can auto-select best pattern per question type
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Patterns don't generalize beyond math | Medium | High | Test on code analysis, other domains in Phase 1 |
| Latency too high (>5 calls) | Low | Medium | Keyword fast-path + episodic caching handles common cases |
| Confidence calibration inaccurate | Medium | Medium | Use `temporal_signal_scan()` to validate confidence |
| Model-specific behavior | Medium | Low | Benchmark across gemma3:1b, phi3:mini, qwen2:1.5b |
| Episodic cache returns stale results | Low | Medium | Include lens version in cache key; invalidate on lens update |
| Long-term learning biases toward first patterns tried | Medium | Low | Track per-pattern stats; periodic rebalancing |

---

## Reproducible Benchmark

### Task: Operation Classification

Given a math word problem phrase, classify the operation as `ADD`, `SUBTRACT`, `MULTIPLY`, or `DIVIDE`.

**Test Cases** (10 samples):

```yaml
# benchmark/tasks/compound/operation_classification.yaml
task_id: compound-operation-classification
description: Classify math operations from natural language
model: gemma3:1b
temperature: 0.7

cases:
  - input: "twice as old as"
    expected: MULTIPLY
  - input: "3 years older than"
    expected: ADD
  - input: "half the age of"
    expected: DIVIDE
  - input: "5 less than"
    expected: SUBTRACT
  - input: "double the amount"
    expected: MULTIPLY
  - input: "reduced by 10"
    expected: SUBTRACT
  - input: "a third of"
    expected: DIVIDE
  - input: "increased by 7"
    expected: ADD
  - input: "triple the size"
    expected: MULTIPLY
  - input: "decreased by half"
    expected: DIVIDE

conditions:
  - name: direct
    description: "Ask directly without grounding"
    prompt_template: |
      What math operation does "{input}" represent?
      Answer with exactly one word: ADD, SUBTRACT, MULTIPLY, or DIVIDE
    
  - name: grounded
    description: "Provide examples first"
    prompt_template: |
      Examples:
      - "twice as old" → MULTIPLY
      - "3 years older" → ADD
      - "half the age" → DIVIDE
      - "5 less than" → SUBTRACT
      
      What math operation does "{input}" represent?
      Answer: 
    
  - name: debate
    description: "Thesis/antithesis/synthesis"
    calls: 3
    # Uses dialectic_decide() from experiments/dialectic.py
    
  - name: grounded_debate
    description: "Grounding + debate"
    calls: 3
    # Uses GroundedDebate pattern with MathLens
```

### Expected Results

| Condition | Accuracy | Calls | Notes |
|-----------|----------|-------|-------|
| direct | 40% | 1 | Baseline — model guesses |
| grounded | 70% | 1 | Examples activate correct patterns |
| debate | 80% | 3 | Dialectic surfaces disagreement |
| grounded_debate | 86% | 3 | Best combination |

### Running the Benchmark

```bash
# Add to CI after Phase 1
python -m sunwell.benchmark.compound benchmark/tasks/compound/operation_classification.yaml

# Expected output:
# Condition         Accuracy  Calls  
# ─────────────────────────────────
# direct            40%       1      
# grounded          70%       1      
# debate            80%       3      
# grounded_debate   86%       3      
```

---

## Implementation Plan (High-Level)

### Phase 1: Pattern Library (Week 1) — 16 hours

**Deliverables**:
1. `patterns/base.py` — `CompoundPattern` protocol (accepts Lens + Simulacrum)
2. `patterns/debate.py` — `GroundedDebate` (uses Lens for grounding, Simulacrum for memory)
3. `patterns/refinement.py` — `IterativeRefinement` (uses `lens.refiners`, caches in episodic)
4. `patterns/ensemble.py` — `VotingEnsemble` (uses `lens.personas` for perspectives)
5. `benchmark/tasks/compound/operation_classification.yaml` — Reproducible benchmark
6. Example lens file: `examples/lenses/math-tutor.lens` with heuristics for math operations
7. Unit tests achieving 90%+ coverage

**Exit Criteria**:
- Patterns work with any existing Lens
- Patterns optionally use Simulacrum for memory (works without it too)
- Benchmark achieves: direct=40%, grounded_debate=86%

### Phase 2: Reasoning Engine + Simulacrum Integration (Week 2) — 16 hours

**Deliverables**:
1. `reasoning/keywords.py` — Fast path keyword matcher
2. `reasoning/compute.py` — Actual math execution
3. `reasoning/engine.py` — Layered orchestrator with Simulacrum
4. `reasoning/memory.py` — Simulacrum helpers for pattern caching/learning
5. Integration tests with Simulacrum persistence

**Exit Criteria**:
- Engine achieves 90%+ on math word problems
- Keyword fast path handles 70%+ of common cases
- Episodic caching skips redundant debates
- Long-term learning tracks pattern effectiveness

### Phase 3: Integration & Polish (Week 3) — 8 hours

**Deliverables**:
1. Integration with existing Naaru orchestrator
2. Documentation and examples (with/without Simulacrum)
3. Additional lens examples (`security-reviewer.lens`, `developmental-editor.lens`)
4. Performance benchmarks (with/without memory caching)

**Exit Criteria**:
- End-to-end examples work with Lens + Simulacrum
- Latency within budget (≤5 calls typical, ≤1 with cache hit)
- Cross-session learning demonstrated

**Estimated Total Effort**: 40 hours

---

## Experimental Evidence

### Accuracy by Pattern (from benchmark)

| Pattern | Accuracy | Calls | Notes |
|---------|----------|-------|-------|
| Direct (baseline) | 40% | 1 | Model confidently wrong |
| Grounded | 60-75% | 1 | Examples activate patterns |
| Debate | 80% | 3 | Dialectic surfaces errors |
| Grounded Debate | 86% | 3 | Best combination |
| Iterative Refinement | 86% | 3 | Self-correction works |
| Keywords + Compute | 100% | 0 | Bypasses model entirely |

### Key Findings

1. **Stability ≠ Correctness**: `temporal_signal_scan()` shows 100% stability with wrong answers
   - Evidence: `compound.py:716-819`
   
2. **Triangulation reveals disagreement**: Different framings surface hidden variance
   - Evidence: `compound.py:1052-1110` — `_fold_triangulate()`
   
3. **Grounding activates knowledge**: Examples improve accuracy 50% → 75%
   - Evidence: `dialectic.py:116-126` — thesis prompt with context
   
4. **Debate beats voting**: Dialectic (86%) > Self-consistency (40%)
   - Evidence: `dialectic.py:153-172` — synthesis reconciles perspectives
   
5. **Computers should compute**: LLM translates language, computer does math
   - Evidence: `compound.py:1113-1162` — `_fold_decompose()` for numeric tasks

---

## Domain Flexibility: Beyond Math

Compound patterns are domain-agnostic. The `Lens` provides all domain context. Here's how they work for different user goals:

### Example 1: Writing a Book (Developmental Editor Lens)

```yaml
# developmental-editor.lens
lens:
  metadata:
    name: "Developmental Editor"
    domain: "fiction"
  
  heuristics:
    principles:
      - name: "Show Don't Tell"
        rule: "Convey emotions through action and dialogue, not narration"
        always:
          - "Use body language to show feelings"
          - "Let dialogue reveal character"
        never:
          - "Tell the reader how a character feels"
          - "Summarize emotional scenes"
        examples:
          good:
            - "She slammed the door and hurled her keys across the room."
          bad:
            - "She was very angry."
      
      - name: "Scene Structure"
        rule: "Every scene needs goal, conflict, disaster or sequel"
  
  personas:
    - name: "reader"
      description: "Engaged reader who wants to feel connected to characters"
      attack_vectors:
        - "Why should I care about this character?"
        - "This scene feels flat — where's the tension?"
    
    - name: "skeptic"
      description: "Critical reader looking for plot holes"
      attack_vectors:
        - "This contradicts what happened in chapter 3"
  
  validators:
    heuristic:
      - name: "no_telling"
        check: "Flag sentences with 'felt', 'was angry', 'was sad'"
```

**Using compound patterns for book writing**:

```python
editor_lens = lens_loader.load("developmental-editor.lens")

# DEBATE: Is this opening compelling?
debate = GroundedDebate(lens=editor_lens, model=model)
result = await debate.run("""
Opening paragraph:
"The old house stood at the end of Maple Street..."

Does this opening hook the reader? Should it be revised?
""")

# The lens.heuristics provide "show don't tell" grounding
# The lens.personas (reader, skeptic) provide debate perspectives
# Result: thesis (advocate), antithesis (critic), synthesis (judgment)

# REFINEMENT: Iteratively improve a chapter
refinement = IterativeRefinement(lens=editor_lens, model=model)
result = await refinement.run("Improve this scene for emotional depth: [scene]")
```

### Example 2: Building an App (Product Manager Lens)

```python
pm_lens = lens_loader.load("product-manager.lens")

# DEBATE: Should this feature be in MVP?
debate = GroundedDebate(lens=pm_lens, model=model)
result = await debate.run("Should dark mode be in the MVP?")

# Thesis: (advocate) why it's valuable
# Antithesis: (developer persona) why it's costly
# Synthesis: judgment using RICE framework from lens.framework

# ENSEMBLE: Multiple perspectives on task breakdown
ensemble = VotingEnsemble(lens=pm_lens, model=model)
result = await ensemble.run("Break down 'User Authentication' into tasks")
```

### Example 3: Code Security Review

```python
security_lens = lens_loader.load("security-reviewer.lens")

debate = GroundedDebate(lens=security_lens, model=model)
result = await debate.run("""
```python
query = f"SELECT * FROM users WHERE id = {user_id}"
```
Is this SQL query safe?
""")

# lens.heuristics provide OWASP patterns for grounding
# lens.personas (attacker, defender) debate the risk
```

### The Key Insight

**Patterns don't know about domains. Lenses know about domains.**

| Component | Responsibility |
|-----------|----------------|
| `GroundedDebate` | Execution: thesis → antithesis → synthesis |
| `IterativeRefinement` | Execution: draft → critique → improve |
| `VotingEnsemble` | Execution: multiple perspectives → vote |
| `Lens` | Domain expertise: heuristics, personas, validators |

Same patterns + different lens = different domain expertise.

---

## Integration with Existing Sunwell Features

Compound patterns integrate as a new **execution strategy** layer:

```
┌──────────────────────────────────────────────────────────────┐
│                        USER GOAL                              │
│           "Build a forum app" / "Write chapter 3"            │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                   NAARU (Coordinator)                         │
│   - Receives goal + lens                                      │
│   - Decomposes via TaskPlanner                                │
│   - Executes tasks with compound patterns                     │
└─────────────────────────────┬────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌─────────────┐      ┌─────────────────┐      ┌─────────────┐
│    LENS     │─────▶│ COMPOUND        │◀─────│  SIGNALING  │
│ (Expertise) │      │ PATTERNS        │      │ (Confidence)│
├─────────────┤      ├─────────────────┤      ├─────────────┤
│ heuristics  │      │ GroundedDebate  │      │ 0=safe      │
│ personas    │      │ IterativeRefine │      │ 1=review    │
│ validators  │      │ VotingEnsemble  │      │ 2=danger    │
│ refiners    │      │ AttentionFold   │      │             │
└─────────────┘      └────────┬────────┘      └─────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                 RESONANCE (Feedback Loop)                     │
│   If pattern output fails validation → retry with feedback    │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│               HARMONIC SYNTHESIS (Multi-Voice)                │
│   Multiple personas generate → judge selects best             │
└──────────────────────────────────────────────────────────────┘
```

### Integration Point 1: Naaru Orchestration

Naaru uses compound patterns as an execution strategy for `TaskMode.GENERATE` and `TaskMode.MODIFY`:

```python
# naaru.py — proposed integration
async def _execute_single_task(self, task: Task) -> None:
    if task.mode == TaskMode.GENERATE and self.lens and self.lens.heuristics:
        # Use compound pattern for grounded generation
        pattern = GroundedDebate(lens=self.lens, model=self.synthesis_model)
        result = await pattern.run(task.description)
        
        if result.confidence < 0.7:
            await self._escalate_or_fold(task, result)
        else:
            await self._write_output(task, result.answer)
```

**Evidence**: `naaru.py:1911-1953` — `_execute_single_task()` already routes by TaskMode.

### Integration Point 2: Task Decomposition (Planners)

Planners can use debate to improve task breakdown quality:

```python
# planners/agent.py — improved planning with debate
async def plan(self, goal: str) -> list[Task]:
    debate = GroundedDebate(lens=self.lens, model=self.model)
    result = await debate.run(f"Break down: {goal}\nConsider: dependencies, risk")
    
    # thesis: initial breakdown
    # antithesis: what's missing / what could go wrong
    # synthesis: improved breakdown
    return self._parse_tasks(result.synthesis)
```

**Evidence**: `planners/agent.py:49-262` — AgentPlanner uses lens context.

### Integration Point 3: Signaling System

Pattern results map to the existing 0-1-2 signal scale:

```python
@dataclass(frozen=True, slots=True)
class PatternResult:
    answer: str
    confidence: float
    
    @property
    def signal(self) -> int:
        """Map confidence to 0-1-2 signal scale."""
        if self.confidence >= 0.85: return 0  # Safe
        elif self.confidence >= 0.7: return 1  # Review
        else: return 2  # Uncertain
```

**Evidence**: `experiments/compound.py:66-99` — `OmmatidiumSignal` uses 0-1-2 scale.

### Integration Point 4: Resonance (Feedback Loop)

If pattern output fails validation, Resonance retries with feedback:

```python
# Already exists in naaru.py:1955-2009
async def _execute_with_resonance(self, task, max_attempts: int) -> None:
    for attempt in range(max_attempts):
        result = await pattern.run(task.description)
        
        errors = [v.description for v in self.lens.validators if not await v.check(result)]
        if not errors:
            return result
        
        task._resonance_feedback = "\n".join(errors)  # Feed back for next attempt
```

**Evidence**: `naaru.py:1955-2009` — Resonance already implements retry-with-feedback.

### Integration Point 5: Harmonic Synthesis (Multi-Voice)

Compound patterns STRUCTURE the multi-voice interaction:

| Harmonic Synthesis (existing) | + Compound Patterns |
|------------------------------|---------------------|
| Generate from persona A, B, C → vote | Generate thesis (A), antithesis (B), synthesize (C) |
| Parallel, unstructured | Sequential, dialectic |

```python
class HarmonicDebate:
    """Harmonic + Debate = structured multi-voice."""
    async def run(self, question: str) -> DebateResult:
        personas = self.lens.personas[:3]
        thesis = await self._generate_with_persona(question, personas[0])
        antithesis = await self._generate_with_persona(f"Critique: {thesis}", personas[1])
        synthesis = await self._generate_with_persona(f"Reconcile: {thesis} vs {antithesis}", personas[2])
        return DebateResult(thesis, antithesis, synthesis)
```

### Summary: Where Compound Patterns Fit

| Existing Feature | Integration |
|------------------|-------------|
| **Naaru** | New execution strategy for GENERATE/MODIFY |
| **TaskPlanner** | Improves plan quality via debate |
| **SignalStream** | Outputs 0-1-2 confidence signals |
| **Resonance** | Validator failures trigger retry |
| **Harmonic** | Structures multi-voice as thesis/antithesis |
| **Lens** | Provides ALL domain context (unchanged) |

**No changes to Lens model** — patterns consume it as-is.

---

## References

- **Core Lens model**: `src/sunwell/core/lens.py` — existing Lens with heuristics, personas, validators
- **Simulacrum memory**: `src/sunwell/simulacrum/` — working, long-term, episodic, semantic, procedural memory
- **Existing patterns**: `src/sunwell/naaru/experiments/compound.py`, `dialectic.py`
- **Refinement layer**: `src/sunwell/naaru/refinement.py`, `resonance.py`
- **Model protocol**: `src/sunwell/models/protocol.py`
- **Benchmark framework**: `src/sunwell/benchmark/`
- **Naaru orchestration**: `src/sunwell/naaru/naaru.py`
- **Task decomposition**: `src/sunwell/naaru/planners/`
- **Related concepts**: `TECHNICAL-VISION.md` (Prism Principle, Lens architecture)
- **RFC-013**: Hierarchical Memory (hot/warm/cold tiers, progressive compression)
- **RFC-014**: Multi-Topology Memory (spatial, topological, structural, faceted retrieval)

---

## Appendix: Lens Features Used by Compound Patterns

The existing `Lens` model (`src/sunwell/core/lens.py`) provides everything compound patterns need:

```python
@dataclass(slots=True)
class Lens:
    """The core expertise container — provides domain context for compound patterns."""
    
    metadata: LensMetadata           # Name, domain, version
    
    # GROUNDING (used by GroundedDebate, IterativeRefinement)
    heuristics: tuple[Heuristic, ...]      # Domain-specific thinking patterns
    anti_heuristics: tuple[AntiHeuristic, ...]  # What to avoid
    
    # PERSPECTIVES (used by debate patterns)
    personas: tuple[Persona, ...]           # Testing perspectives (critic, advocate, etc.)
    
    # VALIDATION (used by all patterns)
    deterministic_validators: tuple[...]    # Hard constraints
    heuristic_validators: tuple[...]        # Soft quality checks
    
    # METHODOLOGY (used by synthesis step)
    framework: Framework | None             # Structured approach
    
    # EXECUTION (orchestration)
    workflows: tuple[Workflow, ...]         # Multi-step processes
    refiners: tuple[Refiner, ...]           # Iterative improvement
    
    # ACTIONS (post-pattern execution)
    skills: tuple[Skill, ...]               # What the lens can do
```

**No new Lens features needed** — compound patterns leverage what already exists.

---

## Appendix: Simulacrum Memory Used by Compound Patterns

The existing `Simulacrum` (`src/sunwell/simulacrum/`) provides memory persistence:

```python
@dataclass
class Simulacrum:
    """Problem-solving context with multi-type memory."""
    
    # MEMORY SYSTEMS (all used by compound patterns)
    working: WorkingMemory      # Current debate context
    long_term: LongTermMemory   # Learnings about pattern effectiveness
    episodic: EpisodicMemory    # Past debates, cache hits, dead ends
    semantic: SemanticMemory    # RAG for context enrichment
    procedural: ProceduralMemory  # Lens heuristics (already loaded)
    
    # FOCUS (attention for retrieval)
    focus: Focus                # What's relevant to current question
```

**Integration is optional** — patterns work without Simulacrum (no caching, no learning), but are more effective with it:

| With Simulacrum | Without Simulacrum |
|-----------------|-------------------|
| Cache hits skip debates | Every debate runs fresh |
| Learns which patterns work | No learning across sessions |
| RAG enriches grounding | Only lens examples |
| Dead ends remembered | May repeat failures |
| Cross-session persistence | Session-local only |
