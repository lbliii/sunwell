#!/usr/bin/env python3
"""Low-B Model Optimization Strategies.

Explores clever techniques to maximize quality from small local models:

1. ENSEMBLE VOTING: 3x 1B runs → 4B picks best
2. SELF-CRITIQUE: 1B generates → 1B critiques → 1B refines
3. BEST-OF-N: Generate N versions, pick by heuristics
4. SPECULATIVE: 1B drafts → 4B only fixes issues
5. CONSENSUS: Multiple runs, majority vote on structure

Usage:
    python examples/lowb_strategies.py --strategy ensemble
    python examples/lowb_strategies.py --strategy self-critique
    python examples/lowb_strategies.py --strategy best-of-n
    python examples/lowb_strategies.py --strategy speculative
    python examples/lowb_strategies.py --strategy all  # Compare all
"""

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import GenerateOptions


@dataclass
class StrategyResult:
    """Results from a strategy run."""
    strategy: str
    model_calls: int
    total_tokens: int
    time_seconds: float
    quality_score: float
    output: str
    details: dict = field(default_factory=dict)


# Sample tasks for testing (easy vs hard)
EASY_TASK = """Write a Python function that validates email addresses.
Requirements:
- Use regex for validation
- Return True/False
- Handle edge cases (empty, None)
Code only:"""

HARD_TASK = """Write a Python class for a thread-safe LRU cache with TTL.
Requirements:
- Max capacity with LRU eviction
- Entries expire after TTL seconds  
- get(key) and set(key, value, ttl=None)
- Thread-safe with locks
- O(1) operations using OrderedDict
Code only:"""

SAMPLE_TASK = HARD_TASK  # Default to hard task


async def strategy_baseline(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
    verbose: bool = False,
) -> StrategyResult:
    """Baseline: Single generation from 1B model."""
    start = time.time()
    
    result = await model.generate(
        task,
        options=GenerateOptions(temperature=0.3, max_tokens=1024),  # More tokens for complete code
    )
    
    code = result.content or ""
    tokens = result.usage.total_tokens if result.usage else 0
    
    # Judge the output
    if verbose:
        print(f"\n   [GENERATED CODE] ({len(code)} chars, {tokens} tokens):\n{code}")
    score = await _judge_code(judge, code, task, verbose=verbose)
    
    return StrategyResult(
        strategy="baseline",
        model_calls=1,
        total_tokens=tokens,
        time_seconds=time.time() - start,
        quality_score=score,
        output=code,
    )


async def strategy_ensemble(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
    n_candidates: int = 3,
) -> StrategyResult:
    """ENSEMBLE: Generate N candidates with different temps, judge picks best.
    
    The key insight: small models have high variance. By sampling multiple
    times, we increase the chance of hitting a good output.
    """
    start = time.time()
    total_tokens = 0
    
    # Generate candidates with different temperatures
    temps = [0.2, 0.4, 0.6][:n_candidates]
    candidates = []
    
    for temp in temps:
        result = await model.generate(
            task,
            options=GenerateOptions(temperature=temp, max_tokens=512),
        )
        code = result.content or ""
        tokens = result.usage.total_tokens if result.usage else 0
        total_tokens += tokens
        candidates.append({"code": code, "temp": temp})
    
    # Have the judge pick the best one
    picker_prompt = f"""You are selecting the BEST code solution from {len(candidates)} candidates.

TASK: {task}

"""
    for i, c in enumerate(candidates):
        picker_prompt += f"""
CANDIDATE {i+1}:
```python
{c['code'][:500]}
```
"""
    
    picker_prompt += """
Which candidate is BEST? Consider correctness, completeness, and code quality.
Respond with ONLY the number (1, 2, or 3):"""
    
    pick_result = await judge.generate(
        picker_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=10),
    )
    total_tokens += pick_result.usage.total_tokens if pick_result.usage else 0
    
    # Parse selection
    try:
        pick_text = pick_result.content or "1"
        pick_num = int("".join(c for c in pick_text if c.isdigit())[:1]) - 1
        pick_num = max(0, min(pick_num, len(candidates) - 1))
    except:
        pick_num = 0
    
    best_code = candidates[pick_num]["code"]
    score = await _judge_code(judge, best_code, task)
    
    return StrategyResult(
        strategy="ensemble",
        model_calls=n_candidates + 1,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        quality_score=score,
        output=best_code,
        details={"picked": pick_num + 1, "temps": temps},
    )


async def strategy_self_critique(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> StrategyResult:
    """SELF-CRITIQUE: Generate → Critique → Refine (all with same small model).
    
    The key insight: small models can identify issues better than they can
    avoid them in the first place. Separate generation from evaluation.
    """
    start = time.time()
    total_tokens = 0
    
    # Step 1: Generate initial code
    result = await model.generate(
        task,
        options=GenerateOptions(temperature=0.3, max_tokens=512),
    )
    initial_code = result.content or ""
    total_tokens += result.usage.total_tokens if result.usage else 0
    
    # Step 2: Self-critique
    critique_prompt = f"""Review this code and list SPECIFIC issues to fix:

```python
{initial_code}
```

List 3 specific issues (or say "No issues" if perfect):"""
    
    critique_result = await model.generate(
        critique_prompt,
        options=GenerateOptions(temperature=0.2, max_tokens=256),
    )
    critique = critique_result.content or ""
    total_tokens += critique_result.usage.total_tokens if critique_result.usage else 0
    
    # Step 3: Refine based on critique (if issues found)
    if "no issues" not in critique.lower():
        refine_prompt = f"""Fix the following issues in this code:

ORIGINAL CODE:
```python
{initial_code}
```

ISSUES TO FIX:
{critique}

Write the FIXED code only:"""
        
        refine_result = await model.generate(
            refine_prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=512),
        )
        final_code = refine_result.content or initial_code
        total_tokens += refine_result.usage.total_tokens if refine_result.usage else 0
    else:
        final_code = initial_code
    
    score = await _judge_code(judge, final_code, task)
    
    return StrategyResult(
        strategy="self-critique",
        model_calls=3,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        quality_score=score,
        output=final_code,
        details={"critique": critique[:200]},
    )


async def strategy_best_of_n(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
    n: int = 5,
) -> StrategyResult:
    """BEST-OF-N: Generate N versions, pick by simple heuristics (no judge call).
    
    The key insight: we can use cheap heuristics to filter candidates
    before expensive LLM judging. Length, syntax, keyword presence.
    """
    start = time.time()
    total_tokens = 0
    
    # Generate N candidates
    candidates = []
    for i in range(n):
        result = await model.generate(
            task,
            options=GenerateOptions(temperature=0.3 + i * 0.1, max_tokens=512),
        )
        code = result.content or ""
        total_tokens += result.usage.total_tokens if result.usage else 0
        
        # Score by cheap heuristics
        heuristic_score = _heuristic_score(code, task)
        candidates.append({"code": code, "score": heuristic_score})
    
    # Pick best by heuristics (no LLM call!)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best_code = candidates[0]["code"]
    
    # Final judge score
    score = await _judge_code(judge, best_code, task)
    
    return StrategyResult(
        strategy="best-of-n",
        model_calls=n,  # Judge call is separate
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        quality_score=score,
        output=best_code,
        details={
            "heuristic_scores": [c["score"] for c in candidates],
            "picked_heuristic_score": candidates[0]["score"],
        },
    )


async def strategy_speculative(
    draft_model: OllamaModel,
    fix_model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> StrategyResult:
    """SPECULATIVE: 1B drafts fast, 4B only fixes issues (not full rewrite).
    
    The key insight: 4B is expensive. Use 1B for bulk generation,
    4B only for targeted fixes. Like speculative decoding but for quality.
    """
    start = time.time()
    total_tokens = 0
    
    # Step 1: Fast draft with 1B
    draft_result = await draft_model.generate(
        task,
        options=GenerateOptions(temperature=0.3, max_tokens=512),
    )
    draft = draft_result.content or ""
    total_tokens += draft_result.usage.total_tokens if draft_result.usage else 0
    
    # Step 2: 4B identifies and fixes specific issues (not full rewrite)
    fix_prompt = f"""Review this code and make MINIMAL fixes. Don't rewrite, just fix issues.

ORIGINAL:
```python
{draft}
```

If the code is good, output it unchanged. Otherwise, output the fixed version.
Code only:"""
    
    fix_result = await fix_model.generate(
        fix_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=512),
    )
    fixed = fix_result.content or draft
    total_tokens += fix_result.usage.total_tokens if fix_result.usage else 0
    
    # Check if 4B made changes
    changed = draft.strip() != fixed.strip()
    
    score = await _judge_code(judge, fixed, task)
    
    return StrategyResult(
        strategy="speculative",
        model_calls=2,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        quality_score=score,
        output=fixed,
        details={"changed_by_4b": changed},
    )


def _heuristic_score(code: str, task: str) -> float:
    """Cheap heuristic scoring without LLM calls.
    
    Looks for:
    - Reasonable length (not too short/long)
    - Contains expected keywords
    - Has function definition
    - Has return statement
    - No obvious errors
    """
    score = 0.0
    
    # Length check (20-500 chars is reasonable for this task)
    length = len(code)
    if 20 < length < 500:
        score += 2.0
    elif length > 10:
        score += 1.0
    
    # Contains function definition
    if "def " in code:
        score += 2.0
    
    # Contains return
    if "return " in code:
        score += 1.5
    
    # Task-specific keywords
    task_lower = task.lower()
    if "email" in task_lower and ("@" in code or "email" in code.lower()):
        score += 1.0
    if "regex" in task_lower and ("re." in code or "import re" in code):
        score += 1.5
    
    # Has docstring or comment
    if '"""' in code or "'''" in code or "#" in code:
        score += 0.5
    
    # Penalty for obvious errors
    if "error" in code.lower() and "error" not in task.lower():
        score -= 1.0
    if code.count("def ") > 3:  # Too many functions = probably confused
        score -= 1.0
    
    return max(0, score)


async def _judge_code(judge: OllamaModel, code: str, task: str, verbose: bool = False) -> float:
    """Get quality score from judge model with detailed criteria."""
    prompt = f"""Score this Python code on a 0-10 scale.

TASK: {task}

CODE:
```python
{code}
```

SCORING RUBRIC:
- 0-2: Broken/doesn't work
- 3-4: Works but has major issues
- 5-6: Functional but incomplete
- 7-8: Good, handles edge cases
- 9-10: Excellent, production-ready

Think step by step:
1. Does it solve the task? (required for 5+)
2. Does it handle edge cases? (required for 7+)
3. Is it well-structured? (required for 8+)

Your response MUST end with a line: SCORE: X
Where X is a number from 0-10."""
    
    result = await judge.generate(
        prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=200),
    )
    
    try:
        text = result.content or ""
        if verbose:
            print(f"\n   [JUDGE RESPONSE]:\n{text}")
        # Look for "SCORE: X" pattern
        import re
        match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if match:
            score = min(10.0, max(0.0, float(match.group(1))))
            if verbose:
                print(f"   [PARSED SCORE]: {score}")
            return score
        # Fallback: find any number
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        if numbers:
            score = min(10.0, max(0.0, float(numbers[-1])))
            if verbose:
                print(f"   [FALLBACK SCORE from numbers {numbers}]: {score}")
            return score
        return 5.0
    except Exception as e:
        if verbose:
            print(f"   [JUDGE ERROR]: {e}")
        return 5.0


def print_results(results: list[StrategyResult]):
    """Print comparison table."""
    print()
    print("=" * 80)
    print("📊 STRATEGY COMPARISON")
    print("=" * 80)
    
    # Sort by quality score
    results.sort(key=lambda r: r.quality_score, reverse=True)
    
    print(f"\n{'Strategy':<15} {'Quality':>8} {'Calls':>6} {'Tokens':>8} {'Time':>8}")
    print("-" * 50)
    
    for r in results:
        print(f"{r.strategy:<15} {r.quality_score:>7.1f}/10 {r.model_calls:>6} {r.total_tokens:>8} {r.time_seconds:>7.1f}s")
    
    # Find best
    best = results[0]
    baseline = next((r for r in results if r.strategy == "baseline"), results[-1])
    
    print()
    print("-" * 50)
    print(f"🏆 Best: {best.strategy} ({best.quality_score:.1f}/10)")
    if best.strategy != "baseline":
        improvement = best.quality_score - baseline.quality_score
        print(f"   Improvement over baseline: {improvement:+.1f} points")
    
    # Show details
    if best.details:
        print(f"   Details: {best.details}")


async def main():
    """Run strategy comparison."""
    parser = argparse.ArgumentParser(description="Low-B Model Optimization Strategies")
    parser.add_argument("--strategy", default="all", 
                       choices=["baseline", "ensemble", "self-critique", "best-of-n", "speculative", "all"])
    parser.add_argument("--model", default="gemma3:1b", help="Small model (default: gemma3:1b)")
    parser.add_argument("--big-model", default="gemma3:4b", help="Bigger model for speculative (default: gemma3:4b)")
    parser.add_argument("--judge", default="qwen3:8b", help="Judge model (default: qwen3:8b)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show judge reasoning")
    parser.add_argument("--easy", action="store_true", help="Use easy task (email validation)")
    args = parser.parse_args()
    
    # Select task
    task = EASY_TASK if args.easy else HARD_TASK
    
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " 🧪 LOW-B MODEL OPTIMIZATION STRATEGIES".ljust(68) + "║")
    print("║" + " Maximizing quality from small local models".ljust(68) + "║")
    print("╠" + "═" * 68 + "╣")
    task_name = "easy (email)" if args.easy else "hard (LRU cache)"
    print("║" + f" Small Model: {args.model}".ljust(68) + "║")
    print("║" + f" Big Model: {args.big_model}".ljust(68) + "║")
    print("║" + f" Judge: {args.judge}".ljust(68) + "║")
    print("║" + f" Task: {task_name}".ljust(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Initialize models
    small = OllamaModel(model=args.model)
    big = OllamaModel(model=args.big_model)
    judge = OllamaModel(model=args.judge)
    
    results = []
    
    strategies = {
        "baseline": lambda: strategy_baseline(small, judge, task, verbose=args.verbose),
        "ensemble": lambda: strategy_ensemble(small, judge, task),
        "self-critique": lambda: strategy_self_critique(small, judge, task),
        "best-of-n": lambda: strategy_best_of_n(small, judge, task),
        "speculative": lambda: strategy_speculative(small, big, judge, task),
    }
    
    if args.strategy == "all":
        for name, fn in strategies.items():
            print(f"\n🔄 Running {name}...")
            result = await fn()
            results.append(result)
            print(f"   ✓ Quality: {result.quality_score:.1f}/10")
    else:
        print(f"\n🔄 Running {args.strategy}...")
        result = await strategies[args.strategy]()
        results.append(result)
    
    print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
