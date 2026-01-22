#!/usr/bin/env python3
"""Analyze: WHY did the ensemble get 3/13 when solo got 0/13?

Hypothesis:
A) True emergence: Collective produced something no individual could
B) Lucky fish: One fish got 3/13 and ensemble just picked it
C) Iteration helped: Feedback loop improved someone's solution
"""

import asyncio
import re

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = ["gemma3:1b", "llama3.2:1b", "qwen2.5:1.5b"]

TASK = """Write a Python function `evaluate(expr: str) -> float` that evaluates arithmetic expressions.
Support: +, -, *, /. Respect precedence: * and / before + and -. Support parentheses.
Do NOT use eval()."""

TEST_CASES = [
    ("2 + 3", 5.0),
    ("2 - 3", -1.0),
    ("2 * 3", 6.0),
    ("6 / 2", 3.0),
    ("2 + 3 * 4", 14.0),
    ("2 * 3 + 4", 10.0),
    ("(2 + 3) * 4", 20.0),
    ("10 / 2 - 1", 4.0),
    ("2 * 3 + 4 * 5", 26.0),
    ("(1 + 2) * (3 + 4)", 21.0),
    ("10 - 2 * 3", 4.0),
    ("100", 100.0),
    (" 1 + 1 ", 2.0),
]


def test_solution(code: str) -> tuple[int, list, list]:
    """Test and return passed count, passed tests, failed tests."""
    if 'eval(' in code and 'evaluate' not in code:
        return 0, [], ["Uses eval()"]
    
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return 0, [], [f"Exec error: {e}"]
    
    if 'evaluate' not in namespace:
        funcs = [k for k, v in namespace.items() if callable(v) and not k.startswith('_')]
        if funcs:
            namespace['evaluate'] = namespace[funcs[0]]
        else:
            return 0, [], ["No function found"]
    
    func = namespace['evaluate']
    passed_tests = []
    failed_tests = []
    
    for expr, expected in TEST_CASES:
        try:
            result = func(expr)
            if abs(float(result) - expected) < 0.001:
                passed_tests.append(f"✓ '{expr}' = {result}")
            else:
                failed_tests.append(f"✗ '{expr}': got {result}, expected {expected}")
        except Exception as e:
            failed_tests.append(f"✗ '{expr}': {e}")
    
    return len(passed_tests), passed_tests, failed_tests


async def main():
    print("🔍 ANALYZING ENSEMBLE SUCCESS")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    
    # Generate from each fish and analyze
    print("\n📍 PHASE 1: What did each fish produce alone?")
    print("-" * 70)
    
    solutions = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"{TASK}\n\nWrite the complete function:"),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        passed, passed_tests, failed_tests = test_solution(code)
        solutions.append((name, code, passed, passed_tests, failed_tests))
        
        print(f"\n🐟 {name}: {passed}/13")
        if passed > 0:
            print(f"   Passed: {', '.join(passed_tests[:3])}")
        if failed_tests:
            print(f"   Failed: {failed_tests[0]}")
    
    # Find best
    best = max(solutions, key=lambda x: x[2])
    print(f"\n📍 PHASE 1 RESULT: Best fish = {best[0]} ({best[2]}/13)")
    
    if best[2] > 0:
        print("\n🔎 ANALYSIS: The 'ensemble' didn't create emergence.")
        print("   One fish (probably gemma) got lucky and produced a partial solution.")
        print("   Ensemble = Best-of-N selection, NOT collective synthesis.")
    
    # Let's try TRUE collective: combine knowledge
    print("\n" + "=" * 70)
    print("📍 PHASE 2: Can we achieve TRUE collective improvement?")
    print("-" * 70)
    
    # Approach: Show each fish ALL solutions and ask to synthesize
    all_solutions_text = ""
    for name, code, passed, _, _ in solutions:
        all_solutions_text += f"\n{name} ({passed}/13):\n```python\n{code}\n```\n"
    
    print("\nAsking each fish to synthesize from ALL solutions...")
    
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"""
{TASK}

Three attempts were made. Analyze what each got RIGHT and WRONG:
{all_solutions_text}

Now write a BETTER solution that combines the best ideas from all three.
The key is operator precedence: "2 + 3 * 4" must equal 14, not 20.
"""),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        passed, passed_tests, failed_tests = test_solution(code)
        print(f"   🐟 {name} synthesized: {passed}/13")
        if passed > best[2]:
            print(f"      ✨ IMPROVED by {passed - best[2]}!")
    
    # Try pair programming
    print("\n" + "=" * 70)
    print("📍 PHASE 3: Pair programming approach")
    print("-" * 70)
    
    # Fish 1 writes, Fish 2 reviews, Fish 3 fixes
    print("\nFish 1 writes → Fish 2 reviews → Fish 3 fixes...")
    
    # Fish 1 writes
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content=f"{TASK}\n\nWrite a first attempt:"),)
    )
    code1 = r1.content
    match = re.search(r'```python\n(.*?)```', code1, re.DOTALL)
    if match:
        code1 = match.group(1)
    p1, _, f1 = test_solution(code1)
    print(f"   🐟 {FISH_MODELS[0]} wrote: {p1}/13")
    
    # Fish 2 reviews
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

Review this code:
```python
{code1}
```

It gets {p1}/13 tests. Failures: {f1[:3]}
Identify bugs and write a CORRECTED version.
"""),)
    )
    code2 = r2.content
    match = re.search(r'```python\n(.*?)```', code2, re.DOTALL)
    if match:
        code2 = match.group(1)
    p2, _, f2 = test_solution(code2)
    print(f"   🐟 {FISH_MODELS[1]} reviewed: {p2}/13")
    
    # Fish 3 fixes
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

Two attempts:
Attempt 1 ({p1}/13): {f1[:2]}
Attempt 2 ({p2}/13): {f2[:2]}

```python
{code2}
```

Focus on operator precedence: * and / must happen BEFORE + and -.
Write the FINAL fixed version.
"""),)
    )
    code3 = r3.content
    match = re.search(r'```python\n(.*?)```', code3, re.DOTALL)
    if match:
        code3 = match.group(1)
    p3, pt3, f3 = test_solution(code3)
    print(f"   🐟 {FISH_MODELS[2]} fixed: {p3}/13")
    if pt3:
        print(f"      Passed: {pt3[:3]}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY: What worked?")
    print("=" * 70)
    
    print(f"""
    Phase 1 (Solo best):      {best[2]}/13
    Phase 2 (Synthesis):      Varied (check above)
    Phase 3 (Pair program):   {p3}/13
    
    Conclusion:
    - If Phase 2/3 > Phase 1: TRUE collective emergence
    - If Phase 2/3 = Phase 1: Just best-of-N selection
    - If Phase 2/3 < Phase 1: Collective is worse (noise)
    """)


if __name__ == "__main__":
    asyncio.run(main())
