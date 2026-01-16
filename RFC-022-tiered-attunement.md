# RFC-022: Tiered Attunement - DORI-Inspired Cognitive Routing

| Field | Value |
|-------|-------|
| **RFC** | 022 |
| **Title** | Tiered Attunement - Confidence-Based Execution with Exemplar Matching |
| **Status** | ✅ Implemented |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-020 (Cognitive Router), RFC-019 (Naaru Architecture) |
| **Implements** | `src/sunwell/routing/tiered_attunement.py` |
| **Inspired By** | prompt-library `docs-orchestrator` (RFC-004 Cognitive Routing) |

---

## Abstract

**Tiered Attunement** enhances RFC-020's CognitiveRouter with techniques proven in DORI's documentation orchestrator:

1. **Tiered Execution** — Fast/Light/Full modes based on confidence and complexity
2. **Few-Shot Exemplars** — Gold-standard routing examples for pattern matching
3. **Self-Verification** — Catch routing errors before dispatch
4. **Anti-Pattern Detection** — Avoid known routing mistakes
5. **Calibrated Confidence** — Explicit scoring rubric (not vibes)

This bridges the gap between Sunwell (portable, IDE-agnostic) and DORI (intelligent, context-aware), giving Sunwell the same routing sophistication while remaining independent of Cursor.

---

## Motivation

### Current State: RFC-020 Attunement

RFC-020 introduced intent-aware routing:

```python
routing = await attunement.route("Review for security issues")
# → {intent: "code_review", lens: "code-reviewer", focus: ["security"], confidence: 0.8}
```

**What's working:**
- ✅ Intent classification
- ✅ Lens selection
- ✅ Focus extraction
- ✅ Basic confidence scoring

**What's missing:**

| Feature | DORI Orchestrator | RFC-020 Attunement |
|---------|-------------------|-------------------|
| Tiered execution | ✅ Tier 0/1/2 | ❌ Single mode |
| Few-shot exemplars | ✅ Gold-standard examples | ❌ None |
| Self-verification | ✅ Pre-dispatch checks | ❌ None |
| Anti-patterns | ✅ Mistake avoidance | ❌ None |
| Calibrated confidence | ✅ Explicit rubric | ⚠️ LLM vibes |

### The DORI Advantage

DORI's orchestrator achieves high routing accuracy through:

1. **Chain-of-Thought Protocol**: 6-step reasoning before every decision
2. **Exemplar Matching**: Compare against known-good routing examples
3. **Confidence Calibration**: Score confidence with explicit criteria, not LLM intuition
4. **Self-Verification**: Check routing decision before executing

These techniques are **model-agnostic** — they work with any LLM.

---

## Architecture

### Tiered Execution Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TIERED ATTUNEMENT                                 │
│                                                                         │
│   Input: "Review auth.py for security"                                  │
│                                                                         │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │  TIER CLASSIFIER                                               │    │
│   │                                                                │    │
│   │  Check patterns:                                               │    │
│   │    - Explicit command? (::review @auth.py --security)  → T0   │    │
│   │    - Clear intent + target? ("review auth.py security") → T1  │    │
│   │    - Ambiguous? ("help with auth")                      → T2   │    │
│   │                                                                │    │
│   │  Check confidence:                                             │    │
│   │    - HIGH (80-100)   → Stay at detected tier                   │    │
│   │    - MEDIUM (50-79)  → Escalate one tier                       │    │
│   │    - LOW (0-49)      → Escalate to T2                          │    │
│   └───────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│              ┌───────────────┼───────────────┐                          │
│              ▼               ▼               ▼                          │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│   │   TIER 0     │  │   TIER 1     │  │   TIER 2     │                 │
│   │   FAST       │  │   LIGHT      │  │   FULL       │                 │
│   │              │  │              │  │              │                 │
│   │ No analysis  │  │ Brief ack    │  │ Full CoT     │                 │
│   │ Direct exec  │  │ Auto-proceed │  │ Confirmation │                 │
│   │ Results only │  │ + Results    │  │ + Details    │                 │
│   └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Tier Behaviors

```yaml
tiers:
  TIER_0_FAST:
    triggers:
      - Explicit shortcut with target
      - HIGH confidence (80+)
      - User passed --fast flag
    behavior:
      show_reasoning: false
      require_confirmation: false
      output: compact
    latency: ~50ms (heuristic only)
    
  TIER_1_LIGHT:
    triggers:
      - Clear natural language intent
      - MEDIUM-HIGH confidence (65+)
      - User passed --light flag
    behavior:
      show_reasoning: false  # Internal only
      require_confirmation: false
      output: standard
    latency: ~200ms (quick LLM check)
    
  TIER_2_FULL:
    triggers:
      - Ambiguous request
      - LOW confidence (<65)
      - Multi-step task detected
      - User passed --full flag
    behavior:
      show_reasoning: true
      require_confirmation: true
      output: detailed
    latency: ~500ms (full CoT reasoning)
```

---

## Few-Shot Exemplar System

### Exemplar Structure

```python
@dataclass
class RoutingExemplar:
    """Gold-standard routing example for pattern matching."""
    
    input: str                    # User request
    context: dict                 # File state, recent activity
    reasoning: str                # Why this routing is correct
    decision: RoutingDecision     # The correct output
    tags: list[str]               # For retrieval: ["security", "review"]

@dataclass  
class RoutingDecision:
    tier: int                     # 0, 1, or 2
    intent: str                   # code_review, testing, etc.
    lens: str                     # code-reviewer, team-qa, etc.
    focus: list[str]              # security, performance, etc.
    confidence: str               # HIGH, MEDIUM, LOW
```

### Exemplar Bank

```yaml
exemplars:
  # --- CODE REVIEW ---
  - input: "review auth.py for security"
    context: {file: "auth.py", exists: true, has_auth_code: true}
    reasoning: |
      Goal: security review | Scope: single file | Clear intent
      File contains auth code, security review is appropriate
    decision:
      tier: 0
      intent: code_review
      lens: code-reviewer
      focus: [security, authentication, injection]
      confidence: HIGH
      
  - input: "check this for bugs"
    context: {file: "utils.py", recently_edited: true}
    reasoning: |
      Goal: find bugs | Scope: single file | AMBIGUOUS
      "bugs" could mean: logic errors, edge cases, security issues
      Default to general code review with broad focus
    decision:
      tier: 1
      intent: code_review
      lens: code-reviewer
      focus: [logic, edge_cases, error_handling]
      confidence: MEDIUM
      
  # --- TESTING ---
  - input: "write tests for the user service"
    context: {file: "user_service.py", test_file_exists: false}
    reasoning: |
      Goal: create tests | Scope: single module | Clear intent
      No existing tests, creation task
    decision:
      tier: 1
      intent: testing
      lens: team-qa
      focus: [unit_tests, coverage, edge_cases]
      confidence: HIGH
      
  # --- DOCUMENTATION ---
  - input: "document this function"
    context: {file: "api.py", cursor_on_function: true}
    reasoning: |
      Goal: add docs | Scope: single function | Clear target
    decision:
      tier: 0
      intent: documentation
      lens: tech-writer
      focus: [docstring, parameters, examples]
      confidence: HIGH
      
  # --- AMBIGUOUS ---
  - input: "help with this code"
    context: {file: "main.py"}
    reasoning: |
      Goal: UNCLEAR | Scope: unclear | No specific ask
      Could be: review, explain, improve, document
      Need clarification or broad analysis
    decision:
      tier: 2
      intent: unknown
      lens: helper
      focus: []
      confidence: LOW
```

### Exemplar Matching Algorithm

```python
async def match_exemplar(task: str, context: dict) -> RoutingExemplar | None:
    """Find the most similar exemplar to guide routing."""
    
    # 1. Embed the task
    task_embedding = await embed(task)
    
    # 2. Find candidate exemplars by tag similarity
    task_tags = extract_tags(task)  # ["security", "review", "auth"]
    candidates = [e for e in EXEMPLARS if overlap(e.tags, task_tags)]
    
    # 3. Rank by embedding similarity
    scored = []
    for exemplar in candidates:
        exemplar_embedding = await embed(exemplar.input)
        score = cosine_similarity(task_embedding, exemplar_embedding)
        scored.append((score, exemplar))
    
    # 4. Return best match if above threshold
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0.75:
        return scored[0][1]
    return None
```

---

## Calibrated Confidence Rubric

Replace LLM "vibes" with explicit scoring:

```yaml
confidence_rubric:
  start: 50  # Base score
  
  add:
    - "+20: Explicit shortcut with target"
    - "+15: Clear action verb (review, test, document)"
    - "+15: Single file explicitly named"
    - "+10: File state matches operation"
    - "+10: Close exemplar match (>0.85 similarity)"
    - "+5: User has used this pattern before"
    
  subtract:
    - "-20: No file context"
    - "-15: Ambiguous verb (fix, help, improve)"
    - "-15: Multiple files mentioned"
    - "-10: Conflicting signals"
    - "-10: No matching exemplar"
    - "-5: First time seeing this pattern"

  thresholds:
    HIGH: 80-100
    MEDIUM: 50-79
    LOW: 0-49
    
  tier_mapping:
    HIGH: "Stay at detected tier"
    MEDIUM: "Proceed with alternatives offered"
    LOW: "Escalate to Tier 2 or clarify"
```

### Confidence Calculation

```python
def calculate_confidence(task: str, context: dict, exemplar_match: float) -> int:
    """Calculate routing confidence with explicit rubric."""
    score = 50  # Base
    
    # Positive signals
    if has_explicit_shortcut(task):
        score += 20
    if has_clear_action_verb(task):
        score += 15
    if context.get("focused_file"):
        score += 15
    if file_state_matches(context):
        score += 10
    if exemplar_match > 0.85:
        score += 10
        
    # Negative signals
    if not context.get("focused_file") and not extract_file(task):
        score -= 20
    if has_ambiguous_verb(task):
        score -= 15
    if count_files_mentioned(task) > 1:
        score -= 15
    if has_conflicting_signals(task):
        score -= 10
    if exemplar_match < 0.5:
        score -= 10
        
    return max(0, min(100, score))
```

---

## Self-Verification Protocol

Before dispatching, verify the routing decision:

```yaml
self_verification:
  checks:
    capability_match:
      question: "Does this lens actually do what the user asked?"
      red_flags:
        - "Lens is for review but user wants generation"
        - "Lens is for testing but user wants documentation"
        
    state_match:
      question: "Does file state match what this task expects?"
      red_flags:
        - "Review on empty file"
        - "Test generation on file with 100% coverage"
        
    scope_match:
      question: "Is scope appropriate?"
      red_flags:
        - "Single-file lens for multi-file request"
        
    confidence_honest:
      question: "Am I actually confident, or guessing?"
      red_flags:
        - "Picked this because nothing else fit"
        - "Multiple lenses could work equally well"

  actions:
    all_pass: proceed
    any_red_flag: 
      if_HIGH: downgrade_to_MEDIUM
      if_MEDIUM: escalate_tier
      if_LOW: clarify_with_user
```

### Implementation

```python
async def verify_routing(decision: RoutingDecision, task: str, context: dict) -> VerificationResult:
    """Self-verify routing decision before dispatch."""
    
    red_flags = []
    
    # Capability match
    lens_capabilities = LENS_CAPABILITIES[decision.lens]
    if decision.intent not in lens_capabilities["handles"]:
        red_flags.append(f"Lens '{decision.lens}' doesn't handle intent '{decision.intent}'")
    
    # State match
    file_state = context.get("file_state", "unknown")
    if decision.intent == "review" and file_state == "empty":
        red_flags.append("Cannot review empty file")
    
    # Scope match
    files_mentioned = count_files_mentioned(task)
    if files_mentioned > 1 and not decision.lens.supports_multi_file:
        red_flags.append("Multi-file request but single-file lens selected")
    
    # Determine action
    if not red_flags:
        return VerificationResult(action="proceed")
    elif len(red_flags) == 1 and decision.confidence == "HIGH":
        return VerificationResult(action="proceed", confidence="MEDIUM", notes=red_flags)
    else:
        return VerificationResult(action="escalate", red_flags=red_flags)
```

---

## Anti-Pattern Detection

Avoid known routing mistakes:

```yaml
anti_patterns:
  review_empty:
    pattern: "intent=review AND file_state=empty"
    mistake: "Routing review request to empty file"
    correction: "Recognize as creation task, not review"
    
  over_orchestration:
    pattern: "task_complexity=trivial AND tier=2"
    mistake: "Full orchestration for single-line change"
    correction: "Tier 0 for trivial tasks"
    
  ambiguity_assumption:
    pattern: "verb=fix AND no_clarification"
    mistake: "Assuming 'fix' means edit directly"
    correction: "Default to review-then-fix pattern"
    
  scope_creep:
    pattern: "single_file_lens AND multi_file_task"
    mistake: "Using single-file lens for multi-file request"
    correction: "Use multi-file workflow or iterate"
```

---

## API Design

### TieredAttunement Class

```python
@dataclass
class TieredAttunement:
    """Enhanced cognitive routing with tiered execution."""
    
    model: Model                          # Tiny LLM for routing
    exemplars: list[RoutingExemplar]      # Gold-standard examples
    confidence_rubric: ConfidenceRubric   # Explicit scoring
    
    async def route(
        self,
        task: str,
        context: dict | None = None,
        tier_override: int | None = None,  # Force specific tier
    ) -> AttunementResult:
        """Route task with tiered execution."""
        
        # 1. Classify tier
        tier = tier_override or self._classify_tier(task, context)
        
        # 2. Match exemplar
        exemplar = await self._match_exemplar(task, context)
        
        # 3. Calculate confidence
        confidence = self._calculate_confidence(task, context, exemplar)
        
        # 4. Route based on tier
        if tier == 0:
            decision = self._route_fast(task, context, exemplar)
        elif tier == 1:
            decision = await self._route_light(task, context, exemplar)
        else:
            decision = await self._route_full(task, context, exemplar)
        
        # 5. Self-verify
        verification = await self._verify(decision, task, context)
        if verification.action == "escalate":
            return await self.route(task, context, tier_override=2)
        
        return AttunementResult(
            decision=decision,
            tier=tier,
            confidence=confidence,
            exemplar_match=exemplar,
            verification=verification,
        )
```

### Usage in Naaru

```python
# In HarmonicSynthesisWorker
async def process_opportunity(self, opp: dict) -> dict | None:
    # Tiered Attunement routing
    if self.attunement and self.config.attunement:
        result = await self.attunement.route(
            task=opp.get("description", ""),
            context={
                "file": opp.get("target_file"),
                "category": opp.get("category"),
            },
        )
        
        # Use routing decision
        routing = result.decision
        
        # Log tier for stats
        self.stats[f"tier_{result.tier}_routes"] = \
            self.stats.get(f"tier_{result.tier}_routes", 0) + 1
    
    # Continue with synthesis using routing decision...
```

---

## Migration Path

### Phase 1: Exemplar System (Week 1)

```python
# Add exemplar matching to existing CognitiveRoutingWorker
class CognitiveRoutingWorker:
    def __init__(self, ...):
        self.exemplars = load_exemplars("routing_exemplars.yaml")
    
    async def _route_task(self, task: str, context: dict) -> dict:
        # Match exemplar first
        exemplar = await self._match_exemplar(task)
        if exemplar and exemplar.confidence == "HIGH":
            return exemplar.decision.to_dict()
        
        # Fall back to LLM routing
        return await self._llm_route(task, context)
```

### Phase 2: Confidence Rubric (Week 2)

```python
# Replace LLM confidence with calibrated scoring
def _calculate_confidence(self, task: str, context: dict) -> int:
    score = 50
    # Apply rubric...
    return score
```

### Phase 3: Tiered Execution (Week 3)

```python
# Add tier classification and tier-specific behaviors
def _classify_tier(self, task: str, context: dict) -> int:
    if self._has_explicit_shortcut(task):
        return 0
    if self._confidence > 65:
        return 1
    return 2
```

### Phase 4: Self-Verification (Week 4)

```python
# Add pre-dispatch verification
async def _verify_routing(self, decision: dict, task: str) -> VerificationResult:
    # Check for red flags...
    pass
```

---

## Benchmarks

### Expected Improvements

| Metric | RFC-020 Baseline | RFC-022 Target |
|--------|------------------|----------------|
| Routing accuracy | 75% | 90% |
| False positive rate | 15% | 5% |
| Avg latency (T0) | 200ms | 50ms |
| Avg latency (T1) | 200ms | 200ms |
| Avg latency (T2) | 200ms | 500ms |
| User corrections needed | 20% | 8% |

### Test Cases

```yaml
test_cases:
  tier_0_accuracy:
    description: "Explicit shortcuts route correctly"
    input: "::review @auth.py --security"
    expected_tier: 0
    expected_lens: "code-reviewer"
    
  exemplar_matching:
    description: "Similar tasks route like exemplars"
    input: "check auth.py for vulnerabilities"
    expected_match: "review auth.py for security"
    expected_similarity: ">0.85"
    
  confidence_calibration:
    description: "Ambiguous tasks get low confidence"
    input: "help with the code"
    expected_confidence: "<50"
    expected_tier: 2
    
  self_verification:
    description: "Red flags trigger escalation"
    input: "review this"
    context: {file_state: "empty"}
    expected_action: "escalate"
```

---

## Appendix: DORI Orchestrator Comparison

| Feature | DORI (prompt-library) | RFC-022 (Sunwell) |
|---------|----------------------|-------------------|
| Platform | Cursor-only | Anywhere |
| Routing target | Documentation rules | Code lenses |
| Tiers | 0/1/2 | 0/1/2 |
| Exemplars | ~20 gold-standard | ~30 gold-standard |
| Confidence rubric | Explicit scoring | Explicit scoring |
| Self-verification | Pre-dispatch checks | Pre-dispatch checks |
| Anti-patterns | ~10 documented | ~10 documented |
| Chain-of-Thought | 6-step protocol | 6-step protocol |

**Key insight**: DORI's routing techniques are model-agnostic. RFC-022 ports them to Sunwell, making intelligent routing available outside Cursor.

---

## References

- RFC-019: Naaru Architecture
- RFC-020: Cognitive Router
- prompt-library RFC-004: Cognitive Routing
- prompt-library `docs-orchestrator` rule
