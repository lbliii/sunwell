# RFC-020: Cognitive Router - Intent-Aware Routing with Tiny LLMs

| Field | Value |
|-------|-------|
| **RFC** | 020 |
| **Title** | Cognitive Router - IDE-Agnostic Intelligence via Tiny LLM Routing |
| **Status** | ✅ Implemented |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-010 (Core), RFC-019 (Naaru Architecture) |
| **Implements** | `src/sunwell/routing/cognitive_router.py` |

---

## Abstract

The **CognitiveRouter** introduces a tiny LLM (270M-500M parameters) as the "thinking" layer that sits between raw task input and the retrieval system. Instead of relying solely on embedding similarity, the router performs:

1. **Intent Classification** — What kind of task is this? (audit, review, generate, explain)
2. **Lens Selection** — Which lens(es) should handle this?
3. **Focus Extraction** — What specific aspects matter? (security, performance, style)
4. **Confidence Scoring** — How certain is the routing decision?
5. **Parameter Tuning** — Adjust `top_k`, `threshold` based on task complexity

This makes Sunwell a **portable DORI** — all the intelligent routing of a Cursor-based orchestrator, but running anywhere: CLI, VS Code, Neovim, CI pipelines, or embedded in other tools.

---

## Motivation

### The DORI Pattern (Cursor-Locked)

DORI uses rule-based routing:
- Pattern matching on commands (`::a` → audit)
- Trigger phrases in `.mdc` files
- Contextual module loading based on file types

**Limitation**: This only works inside Cursor where the rule system runs.

### The Sunwell Pattern (Currently)

Current `ExpertiseRetriever` uses pure embedding similarity:
- Embed the query
- Find cosine-similar heuristics
- Return top-k

**Limitation**: No intent understanding, no confidence, no adaptive behavior.

### The Gap

| Feature | DORI | Sunwell Today | Goal |
|---------|------|---------------|------|
| Intent Classification | ✅ Rules | ❌ None | ✅ Tiny LLM |
| Lens Selection | ✅ Manual | ❌ Single lens | ✅ Multi-lens |
| Focus Extraction | ✅ Patterns | ❌ None | ✅ LLM reasoning |
| Confidence Scoring | ⚠️ Tier-based | ❌ None | ✅ LLM confidence |
| Parameter Tuning | ❌ Static | ❌ Static | ✅ Adaptive |
| IDE-Agnostic | ❌ Cursor only | ✅ Anywhere | ✅ Anywhere |

---

## Architecture

### Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              NAARU                                        │
│                                                                          │
│  ┌────────────────────┐                                                  │
│  │   USER TASK        │                                                  │
│  │   "Review for      │                                                  │
│  │    security"       │                                                  │
│  └─────────┬──────────┘                                                  │
│            │                                                             │
│            ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │              COGNITIVE ROUTER (New Shard)                    │        │
│  │  ┌─────────────────────────────────────────────────────────┐│        │
│  │  │ Tiny LLM (FunctionGemma 270M / Phi-3-mini 500M)         ││        │
│  │  │                                                          ││        │
│  │  │ Input:  "Review for security"                            ││        │
│  │  │ Output: {                                                 ││        │
│  │  │   intent: "code_review",                                  ││        │
│  │  │   lens: "code-reviewer",                                  ││        │
│  │  │   focus: ["security", "injection", "auth"],               ││        │
│  │  │   complexity: "moderate",                                 ││        │
│  │  │   top_k: 5,                                               ││        │
│  │  │   confidence: 0.92                                        ││        │
│  │  │ }                                                         ││        │
│  │  └─────────────────────────────────────────────────────────┘│        │
│  └─────────────────────────────────────────────────────────────┘        │
│            │                                                             │
│            ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │              EXPERTISE RETRIEVER (Enhanced)                  │        │
│  │                                                              │        │
│  │  - Load specified lens ("code-reviewer")                     │        │
│  │  - Use focus terms to boost similarity ("security")          │        │
│  │  - Use adjusted top_k from router                            │        │
│  │  - Return heuristics with relevance scores                   │        │
│  └─────────────────────────────────────────────────────────────┘        │
│            │                                                             │
│            ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │              SYNTHESIS MODEL                                 │        │
│  │  (with selectively retrieved heuristics)                     │        │
│  └─────────────────────────────────────────────────────────────┘        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component: CognitiveRouter

```python
@dataclass
class RoutingDecision:
    """Output from the CognitiveRouter."""
    intent: str                    # Primary intent classification
    lens: str                      # Selected lens file
    secondary_lenses: list[str]   # Additional lenses to merge
    focus: list[str]              # Key topics to boost in retrieval
    complexity: str               # simple | moderate | complex
    top_k: int                    # Suggested retrieval count
    threshold: float              # Minimum relevance threshold
    confidence: float             # Router's confidence (0-1)
    reasoning: str                # Brief explanation (for debugging)


class CognitiveRouter:
    """Intent-aware routing using a tiny LLM.
    
    The router is the "thinking" layer that decides:
    - What kind of task is this?
    - Which lens should handle it?
    - What to focus on during retrieval?
    - How many heuristics to retrieve?
    
    This replaces DORI's rule-based routing with a learned,
    adaptive approach that works anywhere.
    """
    
    def __init__(
        self,
        router_model: ModelProtocol,   # Tiny LLM (270M-500M)
        available_lenses: list[str],   # List of available lens files
        intent_taxonomy: dict | None,  # Optional: predefined intents
    ):
        self.model = router_model
        self.lenses = available_lenses
        self.taxonomy = intent_taxonomy or DEFAULT_INTENT_TAXONOMY
    
    async def route(self, task: str, context: dict | None = None) -> RoutingDecision:
        """Route a task to the appropriate lens and retrieval parameters."""
        
        prompt = self._build_routing_prompt(task, context)
        response = await self.model.generate(prompt)
        return self._parse_response(response)
    
    def _build_routing_prompt(self, task: str, context: dict | None) -> str:
        """Build a structured prompt for the router model."""
        return f"""You are a task router. Analyze the task and decide how to handle it.

AVAILABLE LENSES:
{chr(10).join(f'- {lens}' for lens in self.lenses)}

INTENT TAXONOMY:
- code_review: Reviewing existing code for issues
- code_generation: Writing new code
- documentation: Creating or improving docs
- analysis: Understanding code behavior
- refactoring: Improving code structure
- testing: Writing or improving tests
- debugging: Finding and fixing bugs

TASK:
{task}

{f'CONTEXT: {context}' if context else ''}

OUTPUT (JSON):
{{
  "intent": "<primary intent>",
  "lens": "<lens filename>",
  "secondary_lenses": ["<additional lens>", ...],
  "focus": ["<topic1>", "<topic2>", ...],
  "complexity": "simple|moderate|complex",
  "top_k": <3-10>,
  "threshold": <0.2-0.5>,
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>"
}}"""
```

### Integration with ExpertiseRetriever

The `ExpertiseRetriever` accepts the routing decision:

```python
class ExpertiseRetriever:
    async def retrieve_with_routing(
        self,
        query: str,
        routing: RoutingDecision,
    ) -> RetrievalResult:
        """Retrieve with routing hints from CognitiveRouter."""
        
        # Boost query with focus terms
        boosted_query = f"{query} {' '.join(routing.focus)}"
        
        # Retrieve with adjusted parameters
        return await self.retrieve(
            boosted_query,
            top_k=routing.top_k,
            threshold=routing.threshold,
        )
```

### Integration with Naaru

Add `CognitiveRouter` as a new Shard type:

```python
class HelperType(Enum):
    MEMORY_FETCHER = "memory_fetcher"
    CONTEXT_PREPARER = "context_preparer"
    QUICK_CHECKER = "quick_checker"
    LOOKAHEAD = "lookahead"
    CONSOLIDATOR = "consolidator"
    COGNITIVE_ROUTER = "cognitive_router"  # NEW


class CognitiveRouterShard(CognitiveHelper):
    """Shard that runs the CognitiveRouter."""
    
    def __init__(
        self,
        router_model: ModelProtocol,
        available_lenses: list[str],
        working_memory: WorkingMemory,
    ):
        super().__init__(
            helper_type=HelperType.COGNITIVE_ROUTER,
            working_memory=working_memory,
        )
        self.router = CognitiveRouter(router_model, available_lenses)
    
    async def run(self, task: dict, context: dict | None = None) -> dict:
        """Route the task and store decision in working memory."""
        
        description = task.get("description", "")
        decision = await self.router.route(description, context)
        
        # Store in working memory
        slot = WorkingMemorySlot(
            id="routing_decision",
            content=decision,
            relevance=1.0,  # Highest relevance
            source=HelperType.COGNITIVE_ROUTER,
        )
        await self.working_memory.add(slot)
        
        return asdict(decision)
```

---

## Why Tiny LLM?

### Model Options

| Model | Size | Latency | Quality | Use Case |
|-------|------|---------|---------|----------|
| **FunctionGemma** | 270M | ~50ms | Good | Tool calling, structured output |
| **Phi-3-mini** | 500M | ~100ms | Very good | Reasoning, multi-step |
| **Qwen2.5-0.5B** | 500M | ~100ms | Very good | JSON output, instruction following |
| **Gemma3:1b** | 1B | ~200ms | Excellent | Complex routing |

### Why Not Embedding Only?

Embedding similarity answers: "What is semantically similar?"
LLM routing answers: "What should I do with this?"

Example:
```
Task: "Make this code faster"

Embedding only:
  - Retrieves heuristics mentioning "speed", "fast", "performance"
  - Misses: "caching", "memoization", "algorithm complexity" (different words, same intent)

LLM routing:
  - Intent: "performance_optimization"
  - Focus: ["caching", "algorithms", "io", "memory", "concurrency"]
  - Retrieves comprehensive performance heuristics
```

### Why Not Large LLM?

Cost vs value:
- Large LLM (7B+): 500ms-2s for routing decision
- Tiny LLM (270M): 50-100ms for routing decision

The routing decision doesn't need reasoning power of a 7B model. A tiny model can:
1. Classify intent (multi-class classification)
2. Select from enumerated options (lens list)
3. Extract keywords (focus terms)
4. Estimate complexity (simple heuristics)

Save the large model for actual generation.

---

## Comparison: DORI vs CognitiveRouter

### DORI (Rule-Based)

```yaml
# .cursor/rules/commands/audit/RULE.mdc
---
description: Validate documentation against source code
globs: ["docs/**/*.md"]
triggers: ["::a", "audit", "validate"]
---

# When triggered:
1. Match pattern "::a" or "audit"
2. Load validation modules
3. Execute predefined steps
```

**Pros**: Fast, predictable, no LLM needed
**Cons**: IDE-locked, rigid patterns, manual maintenance

### CognitiveRouter (LLM-Based)

```python
# No config files needed - learns from task content
routing = await router.route("Check if this doc matches the API")
# → intent: "audit"
# → lens: "docs-audit"
# → focus: ["api", "accuracy", "drift"]
# → confidence: 0.94
```

**Pros**: IDE-agnostic, adaptive, handles novel tasks
**Cons**: Requires tiny LLM, small latency overhead

### Hybrid Potential

For maximum performance, combine both:

```python
class HybridRouter:
    """Use rules first, LLM as fallback."""
    
    def __init__(self, rules: list[Rule], llm_router: CognitiveRouter):
        self.rules = rules
        self.llm = llm_router
    
    async def route(self, task: str) -> RoutingDecision:
        # Try rule matching first (fast path)
        for rule in self.rules:
            if rule.matches(task):
                return rule.to_routing_decision()
        
        # Fall back to LLM (handles novel cases)
        return await self.llm.route(task)
```

---

## Implementation Plan

### Phase 1: Core Router

1. Create `src/sunwell/routing/cognitive_router.py`
2. Define `RoutingDecision` dataclass
3. Implement `CognitiveRouter` class
4. Add FunctionGemma as default router model

### Phase 2: Retriever Integration

1. Add `retrieve_with_routing()` to `ExpertiseRetriever`
2. Implement query boosting with focus terms
3. Support multi-lens retrieval and merging

### Phase 3: Naaru Integration

1. Add `COGNITIVE_ROUTER` to `HelperType`
2. Create `CognitiveRouterShard`
3. Integrate routing into `Naaru.illuminate()` pipeline

### Phase 4: CLI Integration

```bash
# Auto-route based on task
sunwell run "Review this code for security" --auto-route

# See routing decision
sunwell route "Review this code for security"
# Output:
# Intent: code_review
# Lens: code-reviewer
# Focus: security, injection, auth
# Confidence: 0.92
```

### Phase 5: Benchmarking

Extend RFC-018 benchmark framework:
1. Add routing accuracy metrics
2. Compare against rule-based baseline (DORI patterns)
3. Measure latency impact vs quality improvement

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Routing Accuracy** | >90% | % of tasks routed to correct lens |
| **Focus Precision** | >80% | % of focus terms that improve retrieval |
| **Latency Overhead** | <100ms | Time added by routing step |
| **Confidence Calibration** | ECE <0.1 | Expected calibration error |
| **IDE Independence** | 100% | Works in CLI, VS Code, Neovim, CI |

---

## Future Extensions

### Multi-Agent Routing

When tasks require multiple capabilities:
```
Task: "Write tests for this security-critical function"
Router output:
  - Agent 1: code-reviewer (security analysis)
  - Agent 2: team-qa (test generation)
  - Coordination: sequential (security first, then tests)
```

### Learning from Feedback

The router can improve by observing outcomes:
```python
# After task completion
await router.learn(
    task=task,
    routing_decision=decision,
    outcome_quality=8.5,  # Judge score
)
```

### Rule Compilation

Frequently successful routing patterns can be compiled into rules:
```python
# If same task pattern routes identically 10+ times
# with >8.0 quality outcomes, create a fast-path rule
router.compile_rule(
    pattern="security review",
    decision=RoutingDecision(intent="code_review", lens="code-reviewer", ...)
)
```

---

## References

- RFC-019: Naaru Architecture
- RFC-018: Quality Benchmark Framework
- [DORI Orchestrator](https://docs.dori.dev/orchestrator)
- [FunctionGemma Paper](https://arxiv.org/abs/...) (tool-calling optimized)
- [Phi-3 Technical Report](https://arxiv.org/abs/2404.14219)
