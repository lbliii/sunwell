#!/usr/bin/env python3
"""Test on a GENUINELY hard problem: Expression parser with operator precedence.

Task: Parse and evaluate "2 + 3 * 4" → 14 (not 20)

This requires:
- Tokenization
- Operator precedence (* before +)
- Parentheses handling
- Recursive descent or shunting yard

1B models WILL struggle with this because:
1. Multiple interacting algorithms
2. Edge cases galore
3. Order of operations is counterintuitive
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

TASK = """Write a Python function `evaluate(expr: str) -> float` that evaluates arithmetic expressions.

Requirements:
- Support: +, -, *, /
- Respect operator precedence: * and / before + and -
- Support parentheses: (2 + 3) * 4 = 20
- Handle whitespace
- Handle negative numbers in parentheses: (-3)

Examples:
- evaluate("2 + 3") → 5
- evaluate("2 + 3 * 4") → 14  (NOT 20!)
- evaluate("(2 + 3) * 4") → 20
- evaluate("10 / 2 - 1") → 4
- evaluate("2 * 3 + 4 * 5") → 26

Do NOT use eval(). Implement the parsing yourself.
"""

# Test cases with expected outputs
TEST_CASES = [
    ("2 + 3", 5.0),
    ("2 - 3", -1.0),
    ("2 * 3", 6.0),
    ("6 / 2", 3.0),
    ("2 + 3 * 4", 14.0),      # Precedence!
    ("2 * 3 + 4", 10.0),      # Precedence!
    ("(2 + 3) * 4", 20.0),    # Parentheses
    ("10 / 2 - 1", 4.0),
    ("2 * 3 + 4 * 5", 26.0),  # Multiple ops
    ("(1 + 2) * (3 + 4)", 21.0),
    ("10 - 2 * 3", 4.0),      # Tricky precedence
    ("100", 100.0),           # Just a number
    (" 1 + 1 ", 2.0),         # Whitespace
]


def test_solution(code: str) -> tuple[int, int, list]:
    """Run tests and count passes."""
    # Check for eval() cheating
    if 'eval(' in code and 'evaluate' not in code:
        return 0, len(TEST_CASES), ["Uses eval() - not allowed"]
    
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return 0, len(TEST_CASES), [f"Exec error: {e}"]
    
    if 'evaluate' not in namespace:
        funcs = [k for k, v in namespace.items() if callable(v) and not k.startswith('_')]
        if funcs:
            namespace['evaluate'] = namespace[funcs[0]]
        else:
            return 0, len(TEST_CASES), ["No function found"]
    
    func = namespace['evaluate']
    passed = 0
    failed = []
    
    for expr, expected in TEST_CASES:
        try:
            result = func(expr)
            if abs(float(result) - expected) < 0.001:
                passed += 1
            else:
                failed.append(f"  '{expr}': got {result}, expected {expected}")
        except Exception as e:
            failed.append(f"  '{expr}': error {e}")
    
    return passed, len(TEST_CASES), failed[:5]


async def solo_generation(fish: list) -> list[tuple[str, int, int]]:
    """Each fish writes solution alone."""
    results = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"{TASK}\n\nWrite the complete function. No eval():"),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        passed, total, failed = test_solution(code)
        results.append((name, passed, total, code))
        print(f"    🐟 {name}: {passed}/{total} tests passed")
        if failed and passed < total:
            print(f"       {failed[0]}")
    
    return results


async def collective_specialists(fish: list) -> tuple[str, int, int]:
    """Specialists: tokenizer, parser, evaluator."""
    print("\n  👷 SPECIALISTS: tokenizer → parser → evaluator")
    
    # Fish 1: Write tokenizer
    tok_response = await fish[0].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

Step 1: Write a tokenizer function that converts "2 + 3 * 4" into tokens: [2, '+', 3, '*', 4]
Handle numbers (including multi-digit), operators (+,-,*,/), and parentheses.
Just the tokenizer function.
"""),)
    )
    tokenizer = tok_response.content
    print(f"    🐟 {FISH_MODELS[0]} (tokenizer): wrote tokenizer")
    
    # Fish 2: Write parser with precedence
    parse_response = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

Here's a tokenizer:
{tokenizer[:800]}

Step 2: Write the main evaluate() function that:
1. Uses a tokenizer
2. Handles operator precedence (* and / before + and -)
3. Handles parentheses

Use recursive descent or shunting yard algorithm.
Write the COMPLETE solution including tokenizer.
"""),)
    )
    parser_code = parse_response.content
    match = re.search(r'```python\n(.*?)```', parser_code, re.DOTALL)
    if match:
        parser_code = match.group(1)
    print(f"    🐟 {FISH_MODELS[1]} (parser): wrote parser")
    
    # Fish 3: Fix and polish
    fix_response = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
{TASK}

Here's an implementation:
```python
{parser_code}
```

Check it handles:
- "2 + 3 * 4" → 14 (precedence)
- "(2 + 3) * 4" → 20 (parentheses)
- Whitespace

Fix any bugs and output the complete corrected function.
"""),)
    )
    final_code = fix_response.content
    match = re.search(r'```python\n(.*?)```', final_code, re.DOTALL)
    if match:
        final_code = match.group(1)
    print(f"    🐟 {FISH_MODELS[2]} (fixer): polished")
    
    passed, total, failed = test_solution(final_code)
    if failed:
        print(f"    Failed: {failed[0]}")
    
    return final_code, passed, total


async def collective_ensemble_iterate(fish: list) -> tuple[str, int, int]:
    """Generate, test, iterate on failures."""
    print("\n  🔄 ENSEMBLE + ITERATE: Generate, test, fix failures")
    
    # All fish write
    best_code = None
    best_passed = 0
    
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"{TASK}\n\nComplete function, no eval():"),)
        )
        code = response.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        passed, total, failed = test_solution(code)
        print(f"    🐟 {name}: {passed}/{total}")
        
        if passed > best_passed:
            best_passed = passed
            best_code = code
    
    # Iterate: show failures to fish and ask to fix
    if best_passed < len(TEST_CASES):
        print(f"\n    📍 Iteration: {len(TEST_CASES) - best_passed} tests failing, attempting fix...")
        
        _, _, failures = test_solution(best_code)
        
        for f, name in zip(fish, FISH_MODELS):
            response = await f.generate(
                prompt=(Message(role="user", content=f"""
{TASK}

This solution passes {best_passed}/{len(TEST_CASES)} tests:
```python
{best_code}
```

It FAILS on these:
{chr(10).join(failures)}

The key issue is usually OPERATOR PRECEDENCE: * and / must be evaluated before + and -.
"2 + 3 * 4" should be 14, not 20.

Fix the bug and output the complete corrected function.
"""),)
            )
            code = response.content
            match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
            if match:
                code = match.group(1)
            
            passed, total, _ = test_solution(code)
            if passed > best_passed:
                print(f"    🐟 {name}: improved {best_passed}→{passed}!")
                best_passed = passed
                best_code = code
    
    return best_code, best_passed, len(TEST_CASES)


async def main():
    print("🧪 HARD PROBLEM: Expression Parser with Operator Precedence")
    print("=" * 70)
    print(f"This requires: tokenization, precedence, parentheses")
    print(f"Test cases: {len(TEST_CASES)}")
    print(f"Key test: '2 + 3 * 4' must equal 14, NOT 20")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    
    # Solo
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
    
    # Ensemble + Iterate
    print("\n📍 COLLECTIVE: Ensemble + Iterate")
    print("-" * 70)
    _, passed, total = await collective_ensemble_iterate(fish)
    collective_results.append(("ENSEMBLE+ITER", passed))
    print(f"\n  Score: {passed}/{total}")
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
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
    
    if best_collective[1] > solo_best:
        print(f"\n🎉 COLLECTIVE (+{best_collective[1] - solo_best}) beats SOLO!")
        print(f"   Worth the extra compute: YES")
    elif best_collective[1] == solo_best:
        print(f"\n➖ Collective matches solo")
        print(f"   Worth the extra compute: MAYBE (for reliability)")
    else:
        print(f"\n❌ Solo still better")
        print(f"   This task may be too hard for collective 1B approach")


if __name__ == "__main__":
    asyncio.run(main())
