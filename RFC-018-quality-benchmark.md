# RFC-018: Quality Benchmark Framework

| Field | Value |
|-------|-------|
| **RFC** | 018 |
| **Title** | Quality Benchmark Framework |
| **Status** | Draft |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-010 (Core), RFC-011 (Skills) |
| **Integrates** | `examples/llm_benchmark.py` (existing judge infrastructure) |

---

## Abstract

Token savings don't matter if output quality stays the same. RFC-018 establishes a **rigorous benchmark framework** to validate Sunwell's core hypothesis: that selective heuristic retrieval produces measurably better outputs than flat injection or no injection at all.

```
Current State:  "We save 85% tokens" ← Nice, but not the value prop
Goal:           "Output quality improves by X%" ← This is what matters
```

This RFC defines:
1. **Benchmark tasks** across domains (docs, code, analysis)
2. **Evaluation methodology** (blind human eval + LLM-as-judge)
3. **Baselines** to compare against (no system prompt, flat injection, competitor)
4. **Metrics** that capture quality dimensions
5. **Automation** for continuous regression testing

---

## Problem Statement

### The Unvalidated Core Hypothesis

RFC-010 claims Sunwell produces "professional-quality response[s]" via selective heuristic retrieval. The benchmarks in `examples/` measure:

- ✅ Token usage (selective vs flat)
- ✅ Latency (sequential vs parallel vs brain)
- ❌ **Output quality** (does the lens actually help?)

Without quality validation, Sunwell is an optimization for a benefit we haven't proven exists.

### Evidence Gap

| Claim | Evidence |
|-------|----------|
| "Lower token usage" | ✅ Measured: 85% reduction |
| "Higher signal-to-noise" | ⚠️ Assumed, not measured |
| "Better outputs" | ❌ No comparative evaluation |
| "Scales to larger component sets" | ⚠️ Tested with 4 heuristics only |

### What "Better" Means

Quality isn't one-dimensional. Different tasks have different quality signals:

| Task Type | Quality Signals |
|-----------|-----------------|
| **Documentation** | Accuracy, completeness, Diataxis compliance, no fluff |
| **Code Review** | Bug detection rate, false positive rate, actionability |
| **Code Generation** | Correctness, style adherence, test passage |
| **Analysis** | Insight depth, evidence backing, structure |

---

## Solution: Multi-Dimensional Benchmark Suite

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       QUALITY BENCHMARK FRAMEWORK                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         TASK REGISTRY                                │   │
│  │  • Documentation tasks (API ref, tutorial, README)                   │   │
│  │  • Code review tasks (security, style, bugs)                         │   │
│  │  • Code generation tasks (functions, tests, refactors)               │   │
│  │  • Analysis tasks (architecture, performance, design)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       EXECUTION ENGINE                               │   │
│  │                                                                       │   │
│  │   Task ──► [Baseline: No Lens] ──► Output A                          │   │
│  │        ├─► [Baseline: Flat]    ──► Output B                          │   │
│  │        └─► [Sunwell: Selective]──► Output C                          │   │
│  │                                                                       │   │
│  │   Same model, same temperature, same seed (where supported)          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       EVALUATION LAYER                               │   │
│  │                                                                       │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │   │ LLM Judge    │  │ Human Eval   │  │ Deterministic│              │   │
│  │   │ (automated)  │  │ (periodic)   │  │ (code tests) │              │   │
│  │   └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       REPORTING                                      │   │
│  │                                                                       │   │
│  │   • Per-task scores                                                  │   │
│  │   • Aggregate by category                                            │   │
│  │   • Win/loss/tie counts                                              │   │
│  │   • Statistical significance                                         │   │
│  │   • Regression tracking over time                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Benchmark Tasks

### Task Format

```yaml
# benchmark/tasks/docs/api-reference-001.yaml
task:
  id: "docs-api-ref-001"
  category: "documentation"
  subcategory: "api_reference"
  
  prompt: |
    Write API reference documentation for this function:
    
    ```python
    def authenticate(username: str, password: str, mfa_code: str | None = None) -> Token:
        """Authenticate a user and return a session token."""
        ...
    ```
    
    Include: signature, parameters, return value, exceptions, example.
  
  # Source material (optional - for tasks needing context)
  context_files:
    - "fixtures/auth_module.py"
  
  # Which lens should be used
  lens: "tech-writer.lens"
  
  # Evaluation criteria
  evaluation:
    rubric:
      - dimension: "accuracy"
        weight: 0.3
        criteria: "All parameters documented correctly with types"
      - dimension: "completeness"
        weight: 0.25
        criteria: "Includes signature, params, returns, exceptions, example"
      - dimension: "diataxis_compliance"
        weight: 0.2
        criteria: "Follows REFERENCE format (no tutorials, no explanations)"
      - dimension: "signal_to_noise"
        weight: 0.15
        criteria: "No marketing language, every sentence adds information"
      - dimension: "usability"
        weight: 0.1
        criteria: "Copy-paste ready example, clear error conditions"
    
    # Ground truth (optional - for deterministic checks)
    must_contain:
      - "username"
      - "password"
      - "mfa_code"
      - "Token"
      - "```python"
    must_not_contain:
      - "powerful"
      - "flexible"
      - "easy"
      - "robust"
```

### Task Categories

#### 1. Documentation Tasks

| Task ID | Description | Key Rubric Dimensions |
|---------|-------------|----------------------|
| `docs-api-ref-*` | API reference from code | Accuracy, completeness, Diataxis |
| `docs-tutorial-*` | Tutorial from spec | Learning progression, runnable steps |
| `docs-howto-*` | How-to guide | Goal clarity, troubleshooting |
| `docs-readme-*` | Project README | Front-loaded value, quick start |
| `docs-changelog-*` | Changelog entry | User impact, breaking changes |

#### 2. Code Review Tasks

| Task ID | Description | Key Rubric Dimensions |
|---------|-------------|----------------------|
| `review-security-*` | Security vulnerability scan | Detection rate, false positive rate |
| `review-bugs-*` | Bug identification | Correctness, actionability |
| `review-style-*` | Style/readability review | Consistency, explanation quality |
| `review-perf-*` | Performance review | Issue identification, suggestions |

#### 3. Code Generation Tasks

| Task ID | Description | Key Rubric Dimensions |
|---------|-------------|----------------------|
| `code-function-*` | Implement a function | Correctness (tests pass), style |
| `code-test-*` | Write tests for code | Coverage, edge cases |
| `code-refactor-*` | Refactor existing code | Behavior preservation, improvement |

#### 4. Analysis Tasks

| Task ID | Description | Key Rubric Dimensions |
|---------|-------------|----------------------|
| `analysis-arch-*` | Architecture review | Depth, trade-off identification |
| `analysis-design-*` | Design critique | Problem identification, alternatives |

---

## Baselines

Each task is executed against **four conditions**:

### 1. No System Prompt (Bare Model)

```python
# Baseline A: Raw model capability
response = await model.generate(task.prompt)
```

### 2. Flat Injection (All Heuristics)

```python
# Baseline B: Everything injected (current Cursor rules approach)
full_context = lens.to_context()  # All heuristics, all personas, etc.
response = await model.generate(full_context + "\n\n" + task.prompt)
```

### 3. Sunwell Selective Retrieval

```python
# Condition C: Sunwell's approach
retrieval_result = await retriever.retrieve(task.prompt, top_k=3)
selective_context = format_retrieval(retrieval_result)
response = await model.generate(selective_context + "\n\n" + task.prompt)
```

### 4. Competitor Baseline (Optional)

```python
# Baseline D: How would a good system prompt do?
good_prompt = load_competitor_prompt(task.category)  # e.g., OpenAI's best practices
response = await model.generate(good_prompt + "\n\n" + task.prompt)
```

---

## Evaluation Methodology

### Three-Tier Evaluation

#### Tier 1: Deterministic Checks (Automated)

```python
def deterministic_eval(task: Task, output: str) -> dict[str, bool]:
    """Fast, reproducible checks."""
    results = {}
    
    # Must-contain checks
    for term in task.evaluation.must_contain:
        results[f"contains_{term}"] = term.lower() in output.lower()
    
    # Must-not-contain checks
    for term in task.evaluation.must_not_contain:
        results[f"avoids_{term}"] = term.lower() not in output.lower()
    
    # Code execution (for code generation tasks)
    if task.category == "code_generation":
        results["tests_pass"] = run_tests(output, task.test_suite)
        results["lint_clean"] = run_ruff(output)
        results["type_check"] = run_mypy(output)
    
    return results
```

#### Tier 2: LLM-as-Judge (Automated)

```python
async def llm_judge_eval(
    task: Task,
    output_a: str,  # Baseline
    output_b: str,  # Sunwell
    judge_model: str = "gpt-4o",
) -> JudgeResult:
    """Pairwise comparison using strong model as judge."""
    
    judge_prompt = f"""You are evaluating two responses to the same task.
    
Task: {task.prompt[:500]}

Response A:
{output_a[:2000]}

Response B:
{output_b[:2000]}

Evaluate on these dimensions (1-10 scale for each):
{format_rubric(task.evaluation.rubric)}

For each dimension, provide:
1. Score for A (1-10)
2. Score for B (1-10)
3. One-sentence justification

Then provide overall winner: A, B, or TIE.

Respond in JSON format."""

    result = await judge_model.generate(judge_prompt)
    return parse_judge_result(result)
```

**LLM Judge Calibration:**
- Use a strong model (GPT-4o, Claude Opus) as judge
- Randomize A/B order to prevent position bias
- Run each comparison 3x and take majority vote
- Track judge agreement with human eval for calibration

**Judge Calibration Gates (Hard Requirements):**

```yaml
calibration_requirements:
  # Must achieve before trusting LLM judge results
  inter_rater_agreement:
    metric: "Cohen's kappa"
    threshold: 0.6  # Substantial agreement
    sample_size: 50  # Human-judged samples
    
  human_llm_correlation:
    metric: "Spearman's rho"
    threshold: 0.7  # Strong correlation
    recalibrate_if_below: 0.5
    
  position_bias_check:
    max_position_effect: 0.05  # Win rate difference A-first vs B-first
    
  self_preference_check:
    # Judge shouldn't systematically prefer outputs from same model family
    max_family_bias: 0.1
```

If calibration gates fail, human eval frequency must increase until correlation stabilizes.

#### Tier 3: Human Evaluation (Periodic)

```yaml
# Human eval protocol
human_evaluation:
  frequency: "weekly"
  sample_size: 20  # Tasks per evaluation round
  evaluators: 3    # Minimum for inter-rater reliability
  
  protocol:
    - Show task prompt
    - Show outputs A and B (randomized, unlabeled)
    - Ask: "Which is better? A / B / Tie"
    - Ask: "Rate confidence: Low / Medium / High"
    - Ask: "What made you choose?"
  
  metrics:
    - inter_rater_agreement: "Fleiss' kappa"
    - llm_human_correlation: "Spearman's rho"
```

---

## Metrics

### Primary Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| **Win Rate** | `wins / (wins + losses + ties)` | > 50% vs all baselines |
| **Quality Delta** | `mean(sunwell_score) - mean(baseline_score)` | > 0.5 points |
| **Fluff Reduction** | `1 - (sunwell_fluff / baseline_fluff)` | > 50% |
| **Diataxis Compliance** | `correct_type / total` | > 80% |

### Retrieval Quality Metrics

Output quality alone doesn't tell us if retrieval is working. These metrics validate the retrieval layer:

| Metric | Formula | Target |
|--------|---------|--------|
| **Precision@K** | `relevant_retrieved / k` | > 0.7 |
| **Recall** | `relevant_retrieved / total_relevant` | > 0.8 |
| **Relevance Score** | Human-rated 1-5 per retrieved heuristic | > 3.5 avg |

```python
@dataclass
class RetrievalMetrics:
    """Measure retrieval quality independent of generation."""
    
    precision_at_k: float      # Were retrieved heuristics relevant?
    recall: float              # Did we miss critical heuristics?
    avg_relevance: float       # Human-rated quality of retrieved set
    retrieval_latency_ms: int  # Time to retrieve
    
    @classmethod
    async def evaluate(
        cls,
        task: BenchmarkTask,
        retrieved: list[RetrievalResult],
        ground_truth: list[str],  # Expected heuristic IDs
    ) -> "RetrievalMetrics":
        relevant = [r for r in retrieved if r.heuristic_id in ground_truth]
        return cls(
            precision_at_k=len(relevant) / len(retrieved) if retrieved else 0,
            recall=len(relevant) / len(ground_truth) if ground_truth else 1.0,
            avg_relevance=sum(r.relevance_score for r in retrieved) / len(retrieved) if retrieved else 0,
            retrieval_latency_ms=sum(r.latency_ms for r in retrieved),
        )
```

### Retrieval Ablation Tests

Test minimum retrieval depth needed to maintain quality:

| Condition | Description | Question Answered |
|-----------|-------------|-------------------|
| `top_k=1` | Single best heuristic | Minimum viable retrieval? |
| `top_k=3` | Default setting | Baseline |
| `top_k=5` | Expanded retrieval | Diminishing returns? |
| `top_k=all` | Full lens (no retrieval) | Flat injection baseline |

**Key Insight**: If `top_k=1` matches `top_k=5` quality, retrieval is highly effective. If quality scales linearly with k, retrieval precision may be low.

### Secondary Metrics

| Metric | Description |
|--------|-------------|
| **Token Efficiency** | Quality per token (quality_score / tokens_used) |
| **Latency** | Time to first token, total generation time |
| **Consistency** | Std dev of scores across runs |
| **Category Performance** | Win rate per task category |

### Regression Metrics

```yaml
regression_tracking:
  baseline: "v0.1.0"  # First validated release
  
  alerts:
    - metric: "win_rate"
      threshold: -0.05  # Alert if drops 5%
    - metric: "fluff_reduction"
      threshold: -0.10
```

### Statistical Rigor Requirements

All benchmark claims must meet these statistical standards:

```yaml
statistical_requirements:
  sample_sizes:
    per_category: 30      # Minimum tasks per category (docs, review, code)
    total_minimum: 100    # Minimum total benchmark tasks
    per_model: 50         # When comparing across models
    
  significance_testing:
    test: "Mann-Whitney U"       # Non-parametric, doesn't assume normal distribution
    paired_test: "Wilcoxon signed-rank"  # When comparing same task across conditions
    alpha: 0.05                  # p-value threshold
    correction: "Bonferroni"     # For multiple comparisons
    
  effect_size:
    metric: "Cohen's d"
    thresholds:
      small: 0.2
      medium: 0.5      # Minimum for "meaningful improvement" claims
      large: 0.8
    
  confidence_intervals:
    level: 0.95
    method: "bootstrap"  # 1000 resamples
    
  reporting_requirements:
    - "Report exact p-values, not just significance"
    - "Include effect size with confidence intervals"
    - "Show win/loss/tie counts, not just percentages"
    - "Report per-category breakdowns"
```

**Claim Validity Matrix:**

| Claim Level | Requirements |
|-------------|--------------|
| "Suggests improvement" | p < 0.1, d > 0.2 |
| "Shows improvement" | p < 0.05, d > 0.5 |
| "Strong evidence" | p < 0.01, d > 0.8, human eval confirms |

---

## Implementation

### Directory Structure

```
benchmark/
├── tasks/
│   ├── docs/
│   │   ├── api-reference-001.yaml
│   │   ├── api-reference-002.yaml
│   │   └── tutorial-001.yaml
│   ├── review/
│   │   ├── security-001.yaml
│   │   └── bugs-001.yaml
│   └── code/
│       ├── function-001.yaml
│       └── test-001.yaml
├── fixtures/
│   ├── auth_module.py
│   └── config_module.py
├── baselines/
│   ├── competitor_prompts.yaml
│   └── flat_injection_cache/
├── results/
│   ├── 2026-01-16/
│   │   ├── raw_outputs.jsonl
│   │   ├── deterministic_results.json
│   │   ├── llm_judge_results.json
│   │   └── summary.md
│   └── historical/
└── scripts/
    ├── run_benchmark.py
    ├── evaluate.py
    ├── report.py
    └── compare_versions.py
```

### CLI Interface

```bash
# Run full benchmark suite
sunwell benchmark run --model gpt-4o --output results/

# Run specific category
sunwell benchmark run --category docs --model gpt-4o

# Run single task for debugging
sunwell benchmark run --task docs-api-ref-001 --verbose

# Compare two versions
sunwell benchmark compare v0.1.0 v0.2.0

# Generate report
sunwell benchmark report results/2026-01-16/ --format markdown
```

### Core Implementation

```python
# src/sunwell/benchmark/runner.py

@dataclass
class BenchmarkRunner:
    """Execute benchmark tasks across conditions."""
    
    model: ModelProtocol
    lens_loader: LensLoader
    tasks_dir: Path
    output_dir: Path
    
    async def run_task(
        self,
        task: BenchmarkTask,
    ) -> TaskResult:
        """Run a single task against all conditions."""
        
        # Load lens
        lens = self.lens_loader.load(task.lens)
        
        # Create retriever
        embedder = await create_embedder()
        retriever = ExpertiseRetriever(lens=lens, embedder=embedder, top_k=3)
        await retriever.initialize()
        
        outputs = {}
        
        # Baseline A: No system prompt
        outputs["bare"] = await self._generate(
            prompt=task.prompt,
            system="",
        )
        
        # Baseline B: Flat injection
        full_context = lens.to_context()
        outputs["flat"] = await self._generate(
            prompt=task.prompt,
            system=full_context,
        )
        
        # Condition C: Selective retrieval
        result = await retriever.retrieve(task.prompt)
        selective_context = self._format_retrieval(result)
        outputs["selective"] = await self._generate(
            prompt=task.prompt,
            system=selective_context,
        )
        
        return TaskResult(
            task_id=task.id,
            outputs=outputs,
            token_counts=self._count_tokens({
                "bare": task.prompt,
                "flat": full_context + "\n\n" + task.prompt,
                "selective": selective_context + "\n\n" + task.prompt,
            }),
        )
    
    def _count_tokens(self, texts: dict[str, str]) -> dict[str, int]:
        """Count tokens using model-appropriate tokenizer."""
        import tiktoken
        
        # Use cl100k_base for GPT-4/Claude, adjust for other models
        try:
            encoding = tiktoken.encoding_for_model(self.model.model_id)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return {k: len(encoding.encode(v)) for k, v in texts.items()}
    
    async def run_suite(
        self,
        category: str | None = None,
    ) -> BenchmarkResults:
        """Run all tasks in a category or full suite."""
        tasks = self._load_tasks(category)
        results = []
        
        for task in tasks:
            result = await self.run_task(task)
            results.append(result)
        
        return BenchmarkResults(
            timestamp=datetime.now().isoformat(),
            model=self.model.model_id,
            results=results,
        )
```

```python
# src/sunwell/benchmark/evaluator.py

@dataclass
class BenchmarkEvaluator:
    """Evaluate benchmark outputs."""
    
    judge_model: ModelProtocol
    
    async def evaluate(
        self,
        task: BenchmarkTask,
        result: TaskResult,
    ) -> EvaluationResult:
        """Run all evaluation tiers."""
        
        # Tier 1: Deterministic
        deterministic = self._deterministic_eval(task, result)
        
        # Tier 2: LLM Judge (pairwise comparisons)
        judge_results = {}
        
        for baseline in ["bare", "flat"]:
            judge_results[f"selective_vs_{baseline}"] = await self._llm_judge(
                task=task,
                output_a=result.outputs[baseline],
                output_b=result.outputs["selective"],
            )
        
        return EvaluationResult(
            task_id=task.id,
            deterministic=deterministic,
            judge_results=judge_results,
            winner=self._determine_winner(judge_results),
        )
    
    async def _llm_judge(
        self,
        task: BenchmarkTask,
        output_a: str,
        output_b: str,
    ) -> JudgeVerdict:
        """Pairwise LLM evaluation with position randomization."""
        
        # Run 3 times with different orderings
        verdicts = []
        
        for _ in range(3):
            # Randomize order
            if random.random() > 0.5:
                first, second = output_a, output_b
                order = "ab"
            else:
                first, second = output_b, output_a
                order = "ba"
            
            verdict = await self._single_judge_call(task, first, second, order)
            verdicts.append(verdict)
        
        # Majority vote
        return self._aggregate_verdicts(verdicts)
```

---

## Success Criteria

### Phase 1: Infrastructure (Week 1-2)

- [ ] 30 benchmark tasks created (8+ per category)
- [ ] Deterministic evaluation working
- [ ] LLM judge implemented with position randomization
- [ ] Integration with existing `examples/llm_benchmark.py` judge infrastructure
- [ ] First full run completed
- [ ] Retrieval metrics instrumented

**Exit Criteria:**
- Can run `sunwell benchmark run` end-to-end
- Have baseline scores for bare model vs flat injection
- Token counts use proper tokenizer (not word count approximation)

### Phase 2: Initial Validation (Week 3-4)

- [ ] 100+ tasks in registry (30+ per category)
- [ ] Run against 2 models (GPT-4o, Claude Sonnet)
- [ ] First human evaluation round (50 samples)
- [ ] Judge calibration metrics calculated
- [ ] Retrieval ablation tests (top_k=1,3,5)

**Exit Criteria:**
- LLM-human correlation ρ > 0.7 (or increase human eval frequency)
- Preliminary evidence direction established (even if not significant)
- Retrieval precision@3 > 0.7

### Phase 3: Statistical Validation (Week 5-6)

- [ ] Full statistical analysis with effect sizes
- [ ] Cross-model validation (add Llama 3)
- [ ] Second human evaluation round
- [ ] Document confidence intervals for all claims

**Exit Criteria:**
- Evidence that selective retrieval beats bare model (p < 0.05, d > 0.5)
- Evidence that selective matches/beats flat with fewer tokens (p < 0.05)
- Results reproducible across 2+ models

### Phase 4: Continuous Regression (Week 7+)

- [ ] CI integration (subset runs on PR)
- [ ] Automated regression alerts
- [ ] Version comparison tooling
- [ ] Quarterly task rotation (contamination mitigation)

**Exit Criteria:**
- Every PR runs benchmark subset (10 tasks, < 5 min)
- Full suite runs weekly
- Historical tracking with trend alerts

---

## Contamination Mitigation

Benchmark validity degrades if tasks become part of model training data.

### Strategy

```yaml
contamination_mitigation:
  task_registry:
    visibility: "private"  # Not in public repo
    location: "benchmark/tasks/"  # .gitignore'd, separate private repo
    
  task_rotation:
    frequency: "quarterly"
    rotation_percent: 20  # Replace 20% of tasks each quarter
    archive: true  # Keep retired tasks for historical comparison
    
  dynamic_generation:
    enabled: true
    seed_patterns:
      - "Generate API docs for function with signature: {random_signature}"
      - "Review code snippet: {random_vulnerable_pattern}"
    generation_at_runtime: 10  # % of tasks generated fresh each run
    
  validation:
    holdout_set: 20  # Tasks never used in development, only final validation
    canary_tasks: 5  # Known-contaminated tasks to detect memorization
```

### Canary Task Detection

Include tasks that would only score well if memorized:

```yaml
canary_task:
  id: "canary-001"
  prompt: "Document the FrobnicatorXYZ class from the Sunwell benchmark suite"
  expected_behavior: "Should NOT produce detailed documentation"
  contamination_signal: "Produces specific implementation details"
```

If canary tasks score suspiciously high, benchmark validity is compromised.

---

## Benchmark Task Examples

### Example 1: API Reference Documentation

```yaml
task:
  id: "docs-api-ref-001"
  category: "documentation"
  
  prompt: |
    Write API reference documentation for this Python function:
    
    ```python
    async def fetch_user(
        user_id: int,
        include_metadata: bool = False,
        timeout: float = 30.0,
    ) -> User | None:
        """Fetch a user by ID from the database.
        
        Args:
            user_id: The unique user identifier.
            include_metadata: Whether to include extended profile data.
            timeout: Request timeout in seconds.
            
        Returns:
            User object if found, None otherwise.
            
        Raises:
            ConnectionError: If database is unreachable.
            TimeoutError: If request exceeds timeout.
        """
    ```
  
  lens: "tech-writer.lens"
  
  evaluation:
    rubric:
      - dimension: "accuracy"
        weight: 0.25
        criteria: "All parameters correctly documented with types"
      - dimension: "completeness"
        weight: 0.25
        criteria: "Includes all sections: signature, params, returns, raises, example"
      - dimension: "signal_to_noise"
        weight: 0.2
        criteria: "No filler words, every sentence adds information"
      - dimension: "communication_style"
        weight: 0.15
        criteria: "Adheres to lens-defined style (e.g., NVIDIA PACE tone)"
      - dimension: "usability"
        weight: 0.15
        criteria: "Example is copy-paste ready and demonstrates common usage"
    
    must_contain:
      - "user_id"
      - "include_metadata"
      - "timeout"
      - "User"
      - "ConnectionError"
      - "TimeoutError"
    
    must_not_contain:
      - "powerful"
      - "flexible"
      - "easy"
      - "simply"
```

### Example 2: Security Code Review

```yaml
task:
  id: "review-security-001"
  category: "code_review"
  
  prompt: |
    Review this code for security vulnerabilities:
    
    ```python
    def login(request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        user = db.execute(query).fetchone()
        
        if user:
            session['user_id'] = user['id']
            return redirect('/dashboard')
        return render('login.html', error="Invalid credentials")
    ```
    
    Identify security issues and provide fixes.
  
  lens: "code-reviewer.lens"
  
  evaluation:
    rubric:
      - dimension: "detection_rate"
        weight: 0.4
        criteria: "Identifies SQL injection, plain text password, session fixation"
      - dimension: "actionability"
        weight: 0.3
        criteria: "Provides concrete fixes, not just warnings"
      - dimension: "false_positive_rate"
        weight: 0.2
        criteria: "Doesn't flag non-issues as vulnerabilities"
      - dimension: "explanation_quality"
        weight: 0.1
        criteria: "Explains WHY each issue is dangerous"
    
    must_contain:
      - "SQL injection"
      - "parameterized"
    
    ground_truth_issues:
      - "SQL injection via string interpolation"
      - "Plain text password comparison"
      - "No CSRF protection"
```

---

## Lens Testing Strategy

### Within-Lens Validation (Primary)

Test whether the correct lens improves task performance:

```yaml
within_lens_tests:
  - lens: "tech-writer.lens"
    tasks: ["docs-api-ref-*", "docs-tutorial-*", "docs-readme-*"]
    hypothesis: "Tech writer lens improves documentation quality"
    
  - lens: "code-reviewer.lens"
    tasks: ["review-security-*", "review-bugs-*", "review-style-*"]
    hypothesis: "Code reviewer lens improves review quality"
```

### Cross-Lens Validation (Sanity Check)

Test whether using the wrong lens hurts performance:

```yaml
cross_lens_tests:
  - task_category: "documentation"
    conditions:
      - lens: "tech-writer.lens"   # Correct
      - lens: "code-reviewer.lens" # Wrong
      - lens: null                 # No lens
    hypothesis: "Wrong lens performs worse than correct lens"
```

**Expected Results:**
- Correct lens > No lens (validates lens value)
- Correct lens > Wrong lens (validates retrieval relevance)
- Wrong lens ≈ No lens (wrong heuristics don't help)

If wrong lens beats correct lens, retrieval or lens design needs review.

---

## Open Questions → Resolutions

| # | Question | Resolution |
|---|----------|------------|
| 1 | **Judge Model Selection** | Use different model family than generation to avoid self-bias. Track family bias in calibration. If correlation with human eval drops, adjust. |
| 2 | **Human Eval Frequency** | Start weekly. If LLM-human ρ > 0.8 for 4 consecutive weeks, reduce to biweekly. Increase if correlation drops below 0.6. |
| 3 | **Task Contamination** | Resolved: See "Contamination Mitigation" section. Private registry + quarterly rotation + canary tasks. |
| 4 | **Multi-Model Aggregation** | Report per-model breakdowns as primary. Aggregate only when trends are consistent (>2 models agree). No geometric mean—too lossy. |
| 5 | **Lens Specificity** | Both: within-lens (correct lens for task) AND cross-lens (wrong lens as control). See "Lens Testing Strategy" above. |
| 6 | **Persona Adherence** | Implement as a "Stress Test" layer. Specialized tasks include a `target_persona` field. Rubric dimension: "Persona Adherence" (e.g., did the Expert persona actually find edge cases?). |
| 7 | **Multi-Turn Tasks** | Introduce in Phase 5. Use `MemoryNode` to preserve context. Evaluated at turn N and aggregated for session quality score. |

### Remaining Open Questions

1. **Retrieval Threshold Tuning**: What similarity threshold should trigger "no relevant heuristics found"? Start with 0.7, tune based on retrieval metrics.

---

## References

- [LLM-as-Judge](https://arxiv.org/abs/2306.05685) - Judging LLM-as-a-Judge paper
- [MT-Bench](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge) - Multi-turn benchmark methodology
- [AlpacaEval](https://github.com/tatsu-lab/alpaca_eval) - Automated LLM evaluation
- RFC-010: Sunwell Core Architecture
- RFC-011: Agent Skills Integration

---

## Dependencies

```toml
# Add to pyproject.toml [project.optional-dependencies]
benchmark = [
    "tiktoken>=0.5.0",      # Accurate token counting
    "scipy>=1.10.0",        # Statistical tests (Mann-Whitney, Wilcoxon)
    "numpy>=1.24.0",        # Bootstrap confidence intervals
    "ruff>=0.2.0",          # Deterministic linting checks
    "mypy>=1.8.0",          # Deterministic type checks
]
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-16 | Initial draft |
| 2026-01-16 | Added retrieval metrics, statistical rigor, contamination mitigation, lens testing strategy |
| 2026-01-16 | Fixed symbol naming, added static analysis to deterministic tier, resolved persona/multi-turn questions |