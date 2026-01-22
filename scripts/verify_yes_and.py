#!/usr/bin/env python3
"""Test the "Yes, And" improv principle for collective coding.

Instead of: "Here's code, FIX the bugs"
Try: "Here's code, ADD this capability"

The key: Don't negate, EXTEND. Each fish ADDS without breaking.
"""

import asyncio
import re

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = ["gemma3:1b", "llama3.2:1b", "qwen2.5:1.5b"]

TASK_FULL = """Write evaluate(expr: str) -> float that handles +, -, *, / with precedence and parentheses."""

TEST_CASES = [
    ("2 + 3", 5.0),
    ("2 - 3", -1.0),
    ("2 * 3", 6.0),
    ("6 / 2", 3.0),
    ("2 + 3 * 4", 14.0),
    ("2 * 3 + 4", 10.0),
    ("(2 + 3) * 4", 20.0),
    ("10 / 2 - 1", 4.0),
    ("100", 100.0),
]


def test_solution(code: str) -> tuple[int, list, list]:
    if 'eval(' in code and 'evaluate' not in code:
        return 0, [], ["Uses eval()"]
    
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return 0, [], [f"Exec: {e}"]
    
    if 'evaluate' not in namespace:
        funcs = [k for k, v in namespace.items() if callable(v) and not k.startswith('_')]
        if funcs:
            namespace['evaluate'] = namespace[funcs[0]]
        else:
            return 0, [], ["No function"]
    
    func = namespace['evaluate']
    passed, failed = [], []
    
    for expr, expected in TEST_CASES:
        try:
            result = func(expr)
            if abs(float(result) - expected) < 0.001:
                passed.append(f"'{expr}'={result}")
            else:
                failed.append(f"'{expr}': {result}!={expected}")
        except Exception as e:
            failed.append(f"'{expr}': {e}")
    
    return len(passed), passed, failed


async def traditional_review(fish: list) -> int:
    """Traditional: write → review → fix (what we tried before)"""
    print("\n  📝 TRADITIONAL: Write → Review → Fix")
    
    # Fish 1 writes
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content=f"{TASK_FULL}\n\nWrite the function:"),)
    )
    code = r1.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    p1, _, f1 = test_solution(code)
    print(f"    Fish 1 wrote: {p1}/9")
    
    # Fish 2 reviews/fixes
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
{TASK_FULL}

Here's code that gets {p1}/9. FIX the bugs:
```python
{code}
```
"""),)
    )
    code = r2.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    p2, _, _ = test_solution(code)
    print(f"    Fish 2 fixed: {p2}/9")
    
    return max(p1, p2)


async def yes_and_additive(fish: list) -> int:
    """Yes-And: Each fish ADDS a feature, never removes"""
    print("\n  🎭 YES-AND: Each fish ADDS without negating")
    
    # Fish 1: Start simple - just handle single numbers
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content="""
Write a SIMPLE evaluate(expr) that handles just:
- Single numbers: evaluate("42") → 42
- Addition: evaluate("2 + 3") → 5

Keep it simple. We'll add more later.
"""),)
    )
    code = r1.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    p1, passed1, _ = test_solution(code)
    print(f"    Fish 1 (numbers, +): {p1}/9 → {passed1[:2]}")
    
    # Fish 2: YES, AND... add subtraction and multiplication
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
Here's a working evaluate() for numbers and addition:
```python
{code}
```

YES, AND... extend it to ALSO handle:
- Subtraction: "2 - 3" → -1
- Multiplication: "2 * 3" → 6

Keep the existing + handling. Just ADD the new operators.
Output the complete extended function.
"""),)
    )
    code = r2.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    p2, passed2, _ = test_solution(code)
    print(f"    Fish 2 (+ -, *): {p2}/9 → {passed2[:3]}")
    
    # Fish 3: YES, AND... add division and precedence
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
Here's evaluate() that handles +, -, *:
```python
{code}
```

YES, AND... extend it to ALSO handle:
- Division: "6 / 2" → 3
- Operator precedence: "2 + 3 * 4" should equal 14, not 20
  (multiply before add)

Keep everything working. Just ADD division and fix precedence.
Output the complete extended function.
"""),)
    )
    code = r3.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    p3, passed3, failed3 = test_solution(code)
    print(f"    Fish 3 (+ /, precedence): {p3}/9 → {passed3[:4]}")
    if failed3:
        print(f"       Failed: {failed3[0]}")
    
    return p3


async def yes_and_parallel(fish: list) -> int:
    """Yes-And Parallel: Each fish adds ONE thing, combine"""
    print("\n  🎭 YES-AND PARALLEL: Each fish adds one feature")
    
    BASE_CODE = '''
def evaluate(expr):
    """Evaluate arithmetic expression."""
    expr = expr.replace(" ", "")
    # TODO: implement
    return float(expr) if expr.isdigit() else 0
'''
    
    additions = []
    
    # Fish 1: Add basic operators
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content=f"""
Here's a stub:
```python
{BASE_CODE}
```

YES, AND... make it handle + and - operators.
"2 + 3" → 5, "5 - 2" → 3
Output the complete function.
"""),)
    )
    code1 = r1.content
    match = re.search(r'```python\n(.*?)```', code1, re.DOTALL)
    if match:
        code1 = match.group(1)
    p1, _, _ = test_solution(code1)
    additions.append(("add/sub", code1, p1))
    print(f"    Fish 1 (+,-): {p1}/9")
    
    # Fish 2: Add multiplication/division
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
Here's a stub:
```python
{BASE_CODE}
```

YES, AND... make it handle * and / operators with correct precedence.
"2 * 3" → 6, "6 / 2" → 3, "2 + 3 * 4" → 14
Output the complete function.
"""),)
    )
    code2 = r2.content
    match = re.search(r'```python\n(.*?)```', code2, re.DOTALL)
    if match:
        code2 = match.group(1)
    p2, _, _ = test_solution(code2)
    additions.append(("mul/div", code2, p2))
    print(f"    Fish 2 (*,/): {p2}/9")
    
    # Fish 3: Add parentheses
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
Here's a stub:
```python
{BASE_CODE}
```

YES, AND... make it handle parentheses for grouping.
"(2 + 3) * 4" → 20, "(1 + 2)" → 3
Output the complete function.
"""),)
    )
    code3 = r3.content
    match = re.search(r'```python\n(.*?)```', code3, re.DOTALL)
    if match:
        code3 = match.group(1)
    p3, _, _ = test_solution(code3)
    additions.append(("parens", code3, p3))
    print(f"    Fish 3 (()): {p3}/9")
    
    # Pick best as base, have another fish combine
    best = max(additions, key=lambda x: x[2])
    print(f"\n    Best single: {best[0]} ({best[2]}/9)")
    
    # Ask one fish to combine all features
    r_combine = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
Three programmers each added a feature to evaluate():

Fish 1 (+,-):
```python
{additions[0][1]}
```

Fish 2 (*,/ with precedence):
```python
{additions[1][1]}
```

Fish 3 (parentheses):
```python
{additions[2][1]}
```

YES, AND... combine ALL their work into one complete function.
Keep all features: +, -, *, /, precedence, parentheses.
"""),)
    )
    combined = r_combine.content
    match = re.search(r'```python\n(.*?)```', combined, re.DOTALL)
    if match:
        combined = match.group(1)
    p_combined, passed_c, failed_c = test_solution(combined)
    print(f"    Combined: {p_combined}/9")
    if passed_c:
        print(f"       Passed: {passed_c[:3]}")
    
    return p_combined


async def main():
    print("🎭 YES-AND IMPROV EXPERIMENT")
    print("=" * 70)
    print("Rule: Each fish ADDS to previous work, never negates")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    
    results = []
    
    # Traditional
    print("\n📍 APPROACH 1: Traditional (write → fix)")
    print("-" * 70)
    score = await traditional_review(fish)
    results.append(("Traditional", score))
    
    # Yes-And Sequential
    print("\n📍 APPROACH 2: Yes-And Sequential")
    print("-" * 70)
    score = await yes_and_additive(fish)
    results.append(("Yes-And Seq", score))
    
    # Yes-And Parallel
    print("\n📍 APPROACH 3: Yes-And Parallel + Combine")
    print("-" * 70)
    score = await yes_and_parallel(fish)
    results.append(("Yes-And Par", score))
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS: Does 'Yes-And' beat 'Fix It'?")
    print("=" * 70)
    
    print(f"\n{'Approach':<20} {'Score':<10}")
    print("-" * 30)
    for name, score in results:
        indicator = "🥇" if score == max(r[1] for r in results) else "  "
        print(f"{indicator} {name:<18} {score}/9")
    
    best = max(results, key=lambda x: x[1])
    if "Yes-And" in best[0]:
        print(f"\n✅ YES-AND WINS! Additive > Corrective")
    else:
        print(f"\n❌ Traditional still better here")


if __name__ == "__main__":
    asyncio.run(main())
