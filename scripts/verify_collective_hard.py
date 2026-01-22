#!/usr/bin/env python3
"""Test collective intelligence on a HARD problem that 1B models struggle with.

Task: Validate balanced brackets - requires:
- Stack-based state tracking
- Multiple bracket types: (), [], {}
- Proper nesting
- Edge case handling

This is genuinely hard for 1B models because:
1. Requires multi-step reasoning
2. Must track state across characters
3. Multiple interacting rules
4. Many edge cases
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

TASK = """Write a Python function `is_balanced(s: str) -> bool` that returns True if the 
string has balanced brackets: (), [], {}. Handle nested and interleaved brackets.

Examples:
- is_balanced("()") → True
- is_balanced("([])") → True
- is_balanced("([)]") → False  (interleaved wrong)
- is_balanced("((())") → False (unclosed)
- is_balanced("") → True
- is_balanced("{[()]}") → True
"""

# Actual test cases to verify correctness
TEST_CASES = [
    ("()", True),
    ("[]", True),
    ("{}", True),
    ("([])", True),
    ("{[()]}", True),
    ("([)]", False),  # Interleaved - tricky!
    ("((())", False),  # Unclosed
    ("", True),
    ("(", False),
    (")", False),
    ("({[]})", True),
    ("))((", False),
    ("[({})]", True),
    ("[{]}", False),  # Interleaved
    ("((()))()", True),
]


def test_solution(code: str) -> tuple[int, int, list]:
    """Actually run the code and count passing tests."""
    # Create a namespace and exec the code
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return 0, len(TEST_CASES), [f"Exec error: {e}"]
    
    if 'is_balanced' not in namespace:
        # Try to find any function that might work
        funcs = [k for k, v in namespace.items() if callable(v) and not k.startswith('_')]
        if funcs:
            namespace['is_balanced'] = namespace[funcs[0]]
        else:
            return 0, len(TEST_CASES), ["No function found"]
    
    func = namespace['is_balanced']
    passed = 0
    failed = []
    
    for input_str, expected in TEST_CASES:
        try:
            result = func(input_str)
            if result == expected:
                passed += 1
            else:
                failed.append(f"  {input_str!r}: got {result}, expected {expected}")
        except Exception as e:
            failed.append(f"  {input_str!r}: error {e}")
    
    return passed, len(TEST_CASES), failed[:5]  # Limit failed output


async def solo_generation(fish: list) -> list[tuple[str, int, int]]:
    """Each fish writes solution alone."""
    results = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"{TASK}\n\nWrite the complete function. Code only, no explanation:"),)
        )
        code = response.content
        # Extract code block
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        passed, total, _ = test_solution(code)
        results.append((name, passed, total))
        print(f"    🐟 {name}: {passed}/{total} tests passed")
    
    return results


async def collective_specialists(fish: list) -> tuple[str, int, int]:
    """Specialists: one does structure, one does logic, one does edge cases."""
    print("\n  👷 SPECIALISTS approach...")
    
    # Fish 1: Design the approach (pseudocode/structure)
    design_response = await fish[0].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

First, describe the APPROACH in 2-3 bullet points. What data structure? What algorithm?
Then write the function SIGNATURE only (def line).
"""),)
    )
    design = design_response.content
    print(f"    🐟 {FISH_MODELS[0]} (design): {design.split(chr(10))[0][:50]}...")
    
    # Fish 2: Write the core logic
    logic_response = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

A teammate suggested this approach:
{design[:500]}

Now write the COMPLETE function with this approach. Focus on the main logic.
"""),)
    )
    logic_code = logic_response.content
    match = re.search(r'```python\n(.*?)```', logic_code, re.DOTALL)
    if match:
        logic_code = match.group(1)
    print(f"    🐟 {FISH_MODELS[1]} (logic): wrote implementation")
    
    # Fish 3: Review and fix edge cases
    review_response = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

Here's a draft implementation:
```python
{logic_code}
```

Check for edge cases: empty string, single bracket, interleaved brackets like "([)]".
Output the FIXED complete function.
"""),)
    )
    final_code = review_response.content
    match = re.search(r'```python\n(.*?)```', final_code, re.DOTALL)
    if match:
        final_code = match.group(1)
    print(f"    🐟 {FISH_MODELS[2]} (review): fixed edge cases")
    
    passed, total, failed = test_solution(final_code)
    if failed:
        print(f"    Failed cases: {failed[0]}")
    
    return final_code, passed, total


async def collective_ensemble(fish: list) -> tuple[str, int, int]:
    """All fish write, test each, pick best, iterate."""
    print("\n  🎯 ENSEMBLE approach...")
    
    # All fish write
    codes = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"{TASK}\n\nWrite the complete function:"),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        codes.append(code)
    
    # Test each
    results = []
    for code, name in zip(codes, FISH_MODELS):
        passed, total, _ = test_solution(code)
        results.append((code, passed, name))
        print(f"    🐟 {name}: {passed}/{total}")
    
    # Pick best
    best_code, best_passed, best_name = max(results, key=lambda x: x[1])
    print(f"\n    🏆 Best: {best_name} ({best_passed}/15)")
    
    # Have others try to improve
    if best_passed < len(TEST_CASES):
        print("    Round 2: Others try to fix...")
        for f, name in zip(fish, FISH_MODELS):
            response = await f.generate(
                prompt=(Message(role="user", content=f"""
{TASK}

Here's a solution that passes {best_passed}/{len(TEST_CASES)} tests:
```python
{best_code}
```

It might fail on edge cases like "([)]" (interleaved) or "((())" (unclosed).
Fix it and output the complete corrected function.
"""),)
            )
            code = response.content
            match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
            if match:
                code = match.group(1)
            
            passed, total, _ = test_solution(code)
            if passed > best_passed:
                best_code, best_passed, best_name = code, passed, f"{name}(improved)"
                print(f"    🐟 {name}: improved to {passed}/{total}!")
    
    return best_code, best_passed, len(TEST_CASES)


async def collective_debate(fish: list) -> tuple[str, int, int]:
    """Fish debate and synthesize best parts."""
    print("\n  💬 DEBATE approach...")
    
    # All fish write
    solutions = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"{TASK}\n\nWrite the complete function:"),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        solutions.append((name, code))
        print(f"    🐟 {name}: wrote solution")
    
    # One fish synthesizes
    synthesizer = fish[2]  # qwen tends to be most capable
    
    synthesis_prompt = f"""
{TASK}

Three programmers wrote solutions:

Solution A ({solutions[0][0]}):
```python
{solutions[0][1]}
```

Solution B ({solutions[1][0]}):
```python
{solutions[1][1]}
```

Solution C ({solutions[2][0]}):
```python
{solutions[2][1]}
```

Analyze what each got right and wrong. Then write the BEST combined solution.
"""
    
    response = await synthesizer.generate(
        prompt=(Message(role="user", content=synthesis_prompt),)
    )
    final_code = response.content
    match = re.search(r'```python\n(.*?)```', final_code, re.DOTALL)
    if match:
        final_code = match.group(1)
    print(f"    🐟 {FISH_MODELS[2]} (synthesizer): combined solutions")
    
    passed, total, failed = test_solution(final_code)
    if failed:
        print(f"    Failed cases: {failed[0]}")
    
    return final_code, passed, total


async def main():
    print("🧪 HARD PROBLEM: Balanced Brackets")
    print("=" * 70)
    print(f"This requires: stack state, multiple bracket types, edge cases")
    print(f"Test cases: {len(TEST_CASES)}")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    
    # Solo baseline
    print("\n📍 SOLO: Each fish alone")
    print("-" * 70)
    solo_results = await solo_generation(fish)
    solo_best = max(r[1] for r in solo_results)
    solo_avg = sum(r[1] for r in solo_results) / len(solo_results)
    print(f"\n  Solo: avg={solo_avg:.1f}/{len(TEST_CASES)}, best={solo_best}/{len(TEST_CASES)}")
    
    collective_results = []
    
    # Specialists
    print("\n📍 COLLECTIVE: Specialists")
    print("-" * 70)
    _, passed, total = await collective_specialists(fish)
    collective_results.append(("SPECIALISTS", passed))
    print(f"\n  Score: {passed}/{total}")
    
    # Ensemble
    print("\n📍 COLLECTIVE: Ensemble")
    print("-" * 70)
    _, passed, total = await collective_ensemble(fish)
    collective_results.append(("ENSEMBLE", passed))
    print(f"\n  Score: {passed}/{total}")
    
    # Debate
    print("\n📍 COLLECTIVE: Debate")
    print("-" * 70)
    _, passed, total = await collective_debate(fish)
    collective_results.append(("DEBATE", passed))
    print(f"\n  Score: {passed}/{total}")
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS: Can collective solve what solo cannot?")
    print("=" * 70)
    
    print(f"\n{'Mode':<15} {'Passed':<15} {'vs Solo Best':<15}")
    print("-" * 45)
    print(f"{'Solo (best)':<15} {solo_best}/{len(TEST_CASES):<13}")
    
    for name, passed in collective_results:
        diff = passed - solo_best
        if diff > 0:
            indicator = f"✅ +{diff} tests"
        elif diff == 0:
            indicator = "➖ same"
        else:
            indicator = f"❌ {diff} tests"
        print(f"{name:<15} {passed}/{len(TEST_CASES):<13} {indicator}")
    
    best_collective = max(collective_results, key=lambda x: x[1])
    
    print(f"\n🏆 Best collective: {best_collective[0]} ({best_collective[1]}/{len(TEST_CASES)})")
    
    if best_collective[1] > solo_best:
        improvement = best_collective[1] - solo_best
        print(f"   🎉 COLLECTIVE SOLVES {improvement} MORE TEST CASES than any solo fish!")
        print(f"   This represents capability BEYOND individual models.")
    elif best_collective[1] == len(TEST_CASES):
        print(f"   🎉 COLLECTIVE ACHIEVED PERFECT SCORE!")
    else:
        print(f"   Solo still competitive on this task.")
    
    # Cost analysis
    print(f"\n💰 COST ANALYSIS:")
    print(f"   Solo attempts: 3 generations")
    print(f"   Collective: ~6-9 generations (varies by mode)")
    print(f"   If collective passes {best_collective[1] - solo_best} more tests, worth 2-3x compute?")


if __name__ == "__main__":
    asyncio.run(main())
