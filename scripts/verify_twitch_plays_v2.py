#!/usr/bin/env python3
"""Twitch Plays Code v2: Specialist roles instead of line-by-line chaos.

Key insight from Twitch Plays Pokemon:
- "Democracy mode" (voting) works better than "anarchy mode" (random)
- But even better: give each player a specialized role

Approach:
1. SPECIALISTS: Each fish writes a specific part (signature, body, docstring)
2. CONSENSUS BUILDER: Fish generate, then vote on best combination
3. ITERATIVE POLISH: One fish writes, others vote to accept/reject/revise
"""

import asyncio
import sys
import re

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = [
    "gemma3:1b",
    "llama3.2:1b",
    "qwen2.5:1.5b",
]

TASK = "Write a Python function to reverse a string"


JUDGE_PROMPT = """Rate this Python code 0-40 points.

Criteria (10 pts each):
- CORRECT: Does it actually work?
- COMPLETE: Is the function complete and callable?
- CLEAR: Is it readable and well-named?
- CONCISE: No unnecessary code?

Code:
```python
{code}
```

Give score as: SCORE: X/40"""


async def judge(model: OllamaModel, code: str) -> int:
    response = await model.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(code=code)),)
    )
    match = re.search(r'SCORE:\s*(\d+)', response.content, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 40)
    match = re.search(r'(\d+)/40', response.content)
    if match:
        return min(int(match.group(1)), 40)
    return 15  # Default if parsing fails


# =============================================================================
# MODE 1: SPECIALISTS - Each fish has a role
# =============================================================================
async def mode_specialists(fish: list, judge_model: OllamaModel) -> tuple[str, int]:
    """Each fish specializes: signature, body, polish."""
    print("\n  👷 SPECIALISTS: Each fish owns a part...")
    
    # Fish 1: Write just the function signature
    signature_response = await fish[0].generate(
        prompt=(Message(role="user", content=f"""
Task: {TASK}

Write ONLY the function signature line (def ...:). No body, no docstring.
Just one line like: def function_name(args):
"""),)
    )
    signature = signature_response.content.strip().split('\n')[0]
    if not signature.startswith('def'):
        signature = 'def reverse_string(s):'
    print(f"    🐟 {FISH_MODELS[0]} (signature): {signature}")
    
    # Fish 2: Write the function body
    body_response = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
Task: {TASK}

Function signature: {signature}

Write ONLY the function body (indented lines under the signature). No signature, just the return statement.
"""),)
    )
    body = body_response.content.strip()
    # Clean up body - ensure proper indentation
    body_lines = []
    for line in body.split('\n'):
        line = line.strip()
        if line and not line.startswith('def') and not line.startswith('```'):
            if not line.startswith('    '):
                line = '    ' + line
            body_lines.append(line)
    body = '\n'.join(body_lines[:3]) if body_lines else '    return s[::-1]'
    print(f"    🐟 {FISH_MODELS[1]} (body): {body.split(chr(10))[0]}...")
    
    # Fish 3: Add docstring or polish
    polish_response = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
Here's a function:

{signature}
{body}

Add a one-line docstring. Output the COMPLETE function with docstring.
"""),)
    )
    
    # Extract the polished code
    polished = polish_response.content
    # Try to extract code block
    code_match = re.search(r'```python\n(.*?)```', polished, re.DOTALL)
    if code_match:
        polished = code_match.group(1)
    print(f"    🐟 {FISH_MODELS[2]} (polish): added docstring")
    
    # Fallback: combine parts
    if 'def' not in polished:
        polished = f'{signature}\n    """Reverse a string."""\n{body}'
    
    print(f"\n  Final code:")
    for line in polished.split('\n')[:5]:
        print(f"    {line}")
    
    score = await judge(judge_model, polished)
    return polished, score


# =============================================================================
# MODE 2: BUILD-VOTE-BUILD - Iterative with voting
# =============================================================================
async def mode_build_vote_build(fish: list, judge_model: OllamaModel) -> tuple[str, int]:
    """One builds, all vote, iterate."""
    print("\n  🗳️ BUILD-VOTE-BUILD: Iterative with voting...")
    
    # Round 1: All fish write full solution
    candidates = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite the complete Python function:"),)
        )
        code = response.content
        # Extract code block if present
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        candidates.append(code)
        print(f"    🐟 {name}: {code.split(chr(10))[0][:40]}...")
    
    # Judge scores each candidate
    scores = []
    for code in candidates:
        score = await judge(judge_model, code)
        scores.append(score)
    
    # Pick best
    best_idx = scores.index(max(scores))
    best_code = candidates[best_idx]
    print(f"\n    🏆 Best candidate: {FISH_MODELS[best_idx]} ({scores[best_idx]}/40)")
    
    # Round 2: Ask others to improve the best
    print(f"\n    Round 2: Others try to improve...")
    improved_candidates = [best_code]  # Keep original
    
    for i, (f, name) in enumerate(zip(fish, FISH_MODELS)):
        if i == best_idx:
            continue
        response = await f.generate(
            prompt=(Message(role="user", content=f"""
Here's a function for: {TASK}

```python
{best_code}
```

Can you improve it? If yes, output the improved version. If it's already good, output it unchanged.
"""),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        improved_candidates.append(code)
        print(f"    🐟 {name}: proposed improvement")
    
    # Judge all improved versions
    improved_scores = []
    for code in improved_candidates:
        score = await judge(judge_model, code)
        improved_scores.append(score)
    
    # Pick final best
    final_idx = improved_scores.index(max(improved_scores))
    final_code = improved_candidates[final_idx]
    final_score = improved_scores[final_idx]
    
    print(f"\n  Final code ({final_score}/40):")
    for line in final_code.split('\n')[:4]:
        print(f"    {line}")
    
    return final_code, final_score


# =============================================================================
# MODE 3: ENSEMBLE VOTE - All write, majority elements win
# =============================================================================
async def mode_ensemble(fish: list, judge_model: OllamaModel) -> tuple[str, int]:
    """All fish write, combine common elements."""
    print("\n  🎯 ENSEMBLE: Combine common patterns...")
    
    # All fish write
    solutions = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite a complete Python function. Code only:"),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        solutions.append(code)
        print(f"    🐟 {name}: wrote solution")
    
    # Analyze: what do they have in common?
    print("\n    Analyzing common patterns...")
    
    # Check: do they all use slice notation?
    uses_slice = sum(1 for s in solutions if '[::-1]' in s)
    uses_loop = sum(1 for s in solutions if 'for' in s.lower())
    
    print(f"    - Uses [::-1]: {uses_slice}/3")
    print(f"    - Uses loop: {uses_loop}/3")
    
    # Build consensus solution based on majority patterns
    if uses_slice >= 2:
        approach = "slice"
    elif uses_loop >= 2:
        approach = "loop"
    else:
        approach = "slice"  # Default
    
    # Have judge pick best implementation of that approach
    best_of_approach = None
    best_score = 0
    for code in solutions:
        if (approach == "slice" and '[::-1]' in code) or \
           (approach == "loop" and 'for' in code.lower()):
            score = await judge(judge_model, code)
            if score > best_score:
                best_score = score
                best_of_approach = code
    
    if not best_of_approach:
        best_of_approach = solutions[0]
        best_score = await judge(judge_model, best_of_approach)
    
    print(f"\n  Final code (consensus on {approach}):")
    for line in best_of_approach.split('\n')[:4]:
        print(f"    {line}")
    
    return best_of_approach, best_score


# =============================================================================
# BASELINE
# =============================================================================
async def solo_baseline(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    scores = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite the complete function:"),)
        )
        score = await judge(judge_model, response.content)
        scores.append(score)
        print(f"    🐟 {name}: {score}/40")
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# MAIN
# =============================================================================
async def main():
    judge_model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    print("🎮 TWITCH PLAYS CODE v2 🎮")
    print("=" * 70)
    print(f"Players: {', '.join(FISH_MODELS)}")
    print(f"Task: {TASK}")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    judge_model = OllamaModel(model=judge_model_name)
    
    # Baseline
    print("\n📍 BASELINE: Solo generation")
    print("-" * 70)
    baseline_avg, baseline_best = await solo_baseline(fish, judge_model)
    print(f"\n  Solo: avg={baseline_avg:.1f}/40, best={baseline_best}/40")
    
    results = []
    
    print("\n📍 MODE: SPECIALISTS")
    print("-" * 70)
    _, score = await mode_specialists(fish, judge_model)
    results.append(("SPECIALISTS", score))
    print(f"  Score: {score}/40")
    
    print("\n📍 MODE: BUILD-VOTE-BUILD")
    print("-" * 70)
    _, score = await mode_build_vote_build(fish, judge_model)
    results.append(("BUILD-VOTE", score))
    print(f"  Score: {score}/40")
    
    print("\n📍 MODE: ENSEMBLE")
    print("-" * 70)
    _, score = await mode_ensemble(fish, judge_model)
    results.append(("ENSEMBLE", score))
    print(f"  Score: {score}/40")
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    print(f"\n{'Mode':<20} {'Score':<10} {'vs Solo Best':<15}")
    print("-" * 45)
    print(f"{'Solo (best)':<20} {baseline_best:<10}")
    
    for name, score in results:
        diff = score - baseline_best
        indicator = "✅" if diff > 0 else "➖" if diff >= -2 else "❌"
        print(f"{name:<20} {score:<10} {indicator} {'+' if diff > 0 else ''}{diff}")
    
    best_mode = max(results, key=lambda x: x[1])
    print(f"\n🏆 Best collective mode: {best_mode[0]} ({best_mode[1]}/40)")
    
    if best_mode[1] > baseline_best:
        improvement = ((best_mode[1] - baseline_best) / baseline_best) * 100
        print(f"   🎉 COLLECTIVE BEATS SOLO by +{improvement:.0f}%!")
    elif best_mode[1] == baseline_best:
        print("   ➖ Collective matches solo")
    else:
        print("   Solo still wins")


if __name__ == "__main__":
    asyncio.run(main())
