# RFC-077: Fast Classifier — JSON Prompts for Small Model Classification

**Status**: Draft  
**Author**: AI-assisted  
**Created**: 2026-01-21  
**Related**: RFC-030 (Unified Router), RFC-073 (Reasoned Decisions)

## Summary

Formalize the "JSON prompt pattern" for small model classification into a reusable `FastClassifier` component. This pattern—already proven in `UnifiedRouter`—enables 1-3B models to reliably classify inputs at ~1s per call, 10-25x faster than tool-calling approaches.

**Key insight**: Small models can't follow tool schemas, but CAN output structured JSON when the format is explicit in the prompt.

## Motivation

### The Problem

RFC-073 (Reasoned Decisions) initially used tool-calling for structured output:

```python
# Tool-calling approach (qwen3:8b)
result = await model.generate(prompt, tools=[decide_severity], tool_choice="required")
# Time: ~30s, works only with 7B+ models
```

Testing revealed small models (1-3B) fail at tool-calling:
- **qwen2.5:1.5b**: Returns wrong argument names
- **llama3.2:3b**: Mangles JSON-in-JSON
- **gemma3:1b**: Doesn't support tools at all

But they ALL succeed with explicit JSON prompts:

```python
# JSON prompt approach (llama3.2:3b)
prompt = '''Assess severity. Respond with ONLY JSON.
{"severity": "critical"|"high"|"medium"|"low", "confidence": 0.0-1.0}
JSON:'''
# Time: ~1s, works with all models
```

### Benchmark Results

| Model | Tool-calling | JSON Prompt | Speedup |
|-------|-------------|-------------|---------|
| qwen3:8b | 30s ✅ | 8s ✅ | 3.8x |
| llama3.2:3b | ❌ fails | 1.3s ✅ | ∞ |
| qwen2.5:1.5b | ❌ fails | 1.7s ✅ | ∞ |
| gemma3:1b | ❌ no support | 1.2s ✅ | ∞ |

### Accuracy on Classification Tasks

| Model | Avg Time | Accuracy (3 tests) |
|-------|----------|-------------------|
| **llama3.2:3b** | **1.3s** | **100%** |
| qwen2.5:1.5b | 1.7s | 100% |
| gemma3:1b | 1.2s | 67% |

**Winner**: llama3.2:3b — fast AND accurate for constrained classification.

### Existing Usage

This pattern is already used in:
- `routing/unified.py` — 8 classifications in one prompt (~1.7s)
- `runtime/model_router.py` — complexity classification

But it's not reusable. Each implementation has its own prompt templates and parsing logic.

## Design

### The Pattern

```
[Clear task] + [Exact JSON format] + [Constrained options] = Reliable results
```

Three requirements:
1. **Clear task**: "Assess severity" not "Given the context, please evaluate..."
2. **Exact format**: Show the literal JSON structure expected
3. **Constrained options**: `"critical"|"high"|"medium"|"low"` not open-ended

### FastClassifier API

```python
from sunwell.reasoning import FastClassifier, SEVERITY_TEMPLATE

# Create classifier with small model
classifier = FastClassifier(model=OllamaModel("llama3.2:3b"))

# Option 1: Use pre-built templates
result = await classifier.classify_with_template(
    SEVERITY_TEMPLATE,
    {"signal_type": "fixme", "content": "race condition", "file_path": "cache.py"}
)
# result.value = "critical"
# result.confidence = 0.8
# result.rationale = "Race conditions can cause data corruption..."

# Option 2: Convenience methods
severity = await classifier.severity("fixme", "race condition", "cache.py")  # "critical"
complexity = await classifier.complexity("Refactor auth system")  # "complex"
is_dangerous = await classifier.yes_no("Is deleting migrations dangerous?")  # True

# Option 3: Custom classification
result = await classifier.classify(
    task="Categorize this error",
    context={"error_type": "TimeoutError", "message": "Connection failed"},
    options=["transient", "permanent", "unknown"],
    output_key="category",
)
```

### Pre-built Templates

| Template | Use Case | Options |
|----------|----------|---------|
| `SEVERITY_TEMPLATE` | Code signals, bugs | critical/high/medium/low |
| `COMPLEXITY_TEMPLATE` | Task routing | trivial/standard/complex |
| `INTENT_TEMPLATE` | User request type | code/explain/debug/chat/search/review |
| `RISK_TEMPLATE` | Action safety | safe/moderate/dangerous/forbidden |
| `BINARY_TEMPLATE` | Yes/no questions | true/false |
| `SCORE_TEMPLATE` | 1-10 scoring | 1-10 |

### When to Use FastClassifier vs Reasoner

| Scenario | Tool | Why |
|----------|------|-----|
| Simple classification | FastClassifier | 1s, small model OK |
| Yes/no decision | FastClassifier | Constrained output |
| Enum selection | FastClassifier | Limited options |
| Complex reasoning | Reasoner | Needs context assembly |
| Multi-step logic | Reasoner | Tool-calling for structure |
| Uncertain → escalate | Both | Start fast, escalate if low confidence |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastClassifier                           │
├─────────────────────────────────────────────────────────────┤
│  Templates          │  Convenience Methods  │  Custom       │
│  ─────────────      │  ──────────────────   │  ──────       │
│  SEVERITY_TEMPLATE  │  .severity()          │  .classify()  │
│  COMPLEXITY_TEMPLATE│  .complexity()        │               │
│  INTENT_TEMPLATE    │  .intent()            │               │
│  RISK_TEMPLATE      │  .risk()              │               │
│  BINARY_TEMPLATE    │  .yes_no()            │               │
│  SCORE_TEMPLATE     │  .score()             │               │
├─────────────────────────────────────────────────────────────┤
│                    Small Model (1-3B)                       │
│                    llama3.2:3b recommended                  │
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. adaptive/signals.py — Signal Extraction ✅ DONE

**Current**: Batch LLM extraction (one call, ~2.4s)
**Added**: `FastSignalChecker` for individual quick checks (~1s each)

```python
from sunwell.adaptive.signals import FastSignalChecker

checker = FastSignalChecker(model=small_model)

# Quick safety gate before execution (1s)
if await checker.is_dangerous("Delete all user data"):
    raise UserConfirmationRequired("This could cause data loss")

# Quick complexity check for routing (1s)
if await checker.is_complex("Refactor the auth system"):
    return "HARMONIC"  # Use multi-candidate planning
```

**Key insight**: Batch extraction (extract_signals) is faster for full signals (~2.4s).
FastSignalChecker is better for **individual gates** when you only need 1-2 checks.

**Benchmark results**:
| Check | Time | Result |
|-------|------|--------|
| is_dangerous("Delete all data") | 1.2s | True ✅ |
| is_dangerous("Fix typo") | 1.0s | False ✅ |
| is_complex("Refactor auth") | 0.7s | True ✅ |

### 2. guardrails/classifier.py — Risk Classification ✅ DONE

**Current**: Pattern matching only
**Added**: `SmartActionClassifier` with LLM fallback for edge cases

```python
from sunwell.guardrails.classifier import SmartActionClassifier

classifier = SmartActionClassifier(model=small_model)

# Pattern match first, LLM fallback for unknowns
result = await classifier.classify_smart(action)
```

**Benchmark results**:
| Action | Pattern Risk | LLM Risk | Time |
|--------|-------------|----------|------|
| deploy (k8s/deployment.yaml) | moderate | safe | 2.2s |
| data_migrate (python migrate.py --prod) | moderate | moderate | 1.1s |
| api_call (external/payment.py) | moderate | moderate | 1.5s |

**Benefit**: LLM provides context-aware assessment for novel action types

### 3. weakness/analyzer.py — Weakness Prioritization ✅ DONE

**Current**: Static tool scores
**Added**: `SmartWeaknessAnalyzer` with LLM-based severity ranking

```python
from sunwell.weakness.analyzer import SmartWeaknessAnalyzer

analyzer = SmartWeaknessAnalyzer(
    graph=artifact_graph,
    project_root=Path("."),
    model=small_model,
)

# LLM-ranked weaknesses
scores = await analyzer.scan_smart()

# Goal-aware prioritization
auth_weaknesses = await analyzer.prioritize_for_goal(
    "improve test coverage for auth", top_n=10
)
```

**Features**:
- `scan_smart()`: Re-ranks top 20 weaknesses by LLM severity assessment
- `prioritize_for_goal()`: Filters weaknesses relevant to a specific goal

**Benefit**: Context-aware prioritization based on actual impact, not just metrics

### 4. naaru/discernment.py — Validation Tier Selection ✅ DONE

**Current**: Tool-calling with FunctionGemma (5s+, requires tool support)
**Added**: FastClassifier mode using JSON prompts (~1s, works with 1-3B models)

```python
from sunwell.naaru.discernment import Discernment

# RFC-077: Use FastClassifier (default)
discerner = Discernment(use_fast_classifier=True)

# Or legacy tool-calling mode
discerner = Discernment(use_fast_classifier=False)
```

**Benchmark results**:
| Mode | Model | Time | Tool Support Required |
|------|-------|------|----------------------|
| FastClassifier | llama3.2:3b | ~1s | No ✅ |
| Tool-calling | functiongemma | ~5s | Yes |

**Benefit**: 5x faster validation, works with more models

### 5. routing/unified.py — Refactor to Use FastClassifier

**Current**: Custom prompt and parsing
**With FastClassifier**:

```python
# Create combined routing template
ROUTING_TEMPLATE = ClassificationTemplate(
    name="routing",
    prompt_template=UNIFIED_ROUTER_PROMPT,  # Existing prompt
    output_key="intent",
    options=("code", "explain", "debug", "chat", "search", "review"),
)

# Use FastClassifier's parsing
async def _compute_decision(self, request: str, context: dict) -> RoutingDecision:
    result = await self.classifier.classify_with_template(
        ROUTING_TEMPLATE, 
        {"request": request, "context": json.dumps(context)}
    )
    return self._build_decision(result)
```

**Benefit**: Shared parsing logic, easier to maintain

## Implementation Plan

### Phase 1: Core FastClassifier ✅ DONE

- [x] Create `sunwell/reasoning/fast_classifier.py`
- [x] Define `ClassificationResult` dataclass
- [x] Define `ClassificationTemplate` for reusable templates
- [x] Implement core `classify()` and `classify_with_template()`
- [x] Add convenience methods: `severity()`, `complexity()`, `intent()`, `risk()`, `yes_no()`, `score()`
- [x] Add pre-built templates: `SEVERITY_TEMPLATE`, `COMPLEXITY_TEMPLATE`, etc.
- [x] Export from `sunwell.reasoning`

### Phase 2: Integration ✅ DONE

- [x] **adaptive/signals.py**: Added `FastSignalChecker` for quick individual checks
- [x] **guardrails/classifier.py**: Added `SmartActionClassifier` with LLM fallback
- [x] **weakness/analyzer.py**: Added `SmartWeaknessAnalyzer` with LLM prioritization
- [x] **naaru/discernment.py**: Added `use_fast_classifier` mode (default: True)

### Phase 3: Optimization

- [ ] Add batch classification (`batch_classify()`)
- [ ] Add caching layer (hash prompt → result)
- [ ] Add confidence-based escalation (low confidence → bigger model)
- [ ] Benchmark and tune recommended model selection

## Metrics

### Speed Targets

| Classification | Target | Current |
|----------------|--------|---------|
| Single classification | < 2s | 1.1s ✅ |
| Batch of 5 | < 6s | 5.5s ✅ |
| Routing decision | < 2s | 1.7s ✅ |

### Accuracy Targets

| Task | Target | Current |
|------|--------|---------|
| Severity classification | > 90% | 100% (3 tests) |
| Complexity classification | > 85% | 80% (5 tests) |
| Intent classification | > 90% | TBD |

## Risks and Mitigations

### Risk: Model Availability

**Problem**: User might not have llama3.2:3b installed
**Mitigation**: `get_recommended_model()` function + fallback chain:
```python
FALLBACK_CHAIN = ["llama3.2:3b", "qwen2.5:1.5b", "gemma3:1b"]
```

### Risk: Prompt Sensitivity

**Problem**: Small changes to prompt can break parsing
**Mitigation**: 
- Extensive test suite for each template
- Version templates and track breaking changes
- Shared parsing logic in FastClassifier

### Risk: Accuracy Degradation

**Problem**: Small models may misclassify edge cases
**Mitigation**:
- Confidence scoring (low confidence → escalate)
- Calibration tracking (like RFC-073)
- Fallback to larger model for critical decisions

## Future Work

### Confidence-Based Escalation

```python
result = await classifier.severity(...)
if result.confidence < 0.7:
    # Escalate to Reasoner with full context
    result = await reasoner.decide(DecisionType.SEVERITY_ASSESSMENT, ...)
```

### Learning from Corrections

Track when FastClassifier results are corrected:
```python
await classifier.record_correction(
    template=SEVERITY_TEMPLATE,
    context={...},
    predicted="medium",
    actual="critical",
)
# Use for prompt tuning and model selection
```

### Multi-Model Ensemble

For critical decisions, run multiple small models and vote:
```python
results = await classifier.ensemble_classify(
    template=SEVERITY_TEMPLATE,
    context={...},
    models=["llama3.2:3b", "qwen2.5:1.5b", "gemma3:1b"],
)
# Returns majority vote with confidence
```

## Conclusion

The JSON prompt pattern is already proven in UnifiedRouter. FastClassifier formalizes it into a reusable component that can be applied across Sunwell wherever we need fast, reliable classification.

**Key benefits**:
- **10-25x faster** than tool-calling
- **Works with 1-3B models** (cheaper, faster to load)
- **Reusable templates** reduce duplication
- **Graceful degradation** with confidence scoring

The pattern embodies Sunwell's philosophy: **offload monkey work to smaller models, save the big guns for real reasoning**.
