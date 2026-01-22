#!/usr/bin/env python3
"""Yes-And with STRICT interface preservation.

Key fix: Tell each fish EXACTLY what interface to preserve.
"""

import asyncio
import re
import time

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = ["gemma3:1b", "llama3.2:1b", "qwen2.5:1.5b"]


def test_solution(code: str) -> tuple[int, list, list]:
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return 0, [], [f"Exec: {e}"]
    
    if 'URLShortener' not in namespace:
        return 0, [], ["No class"]
    
    passed, failed = [], []
    
    try:
        s = namespace['URLShortener']()
        
        # Test 1: shorten
        try:
            c = s.shorten("https://a.com")
            if c and len(str(c)) >= 4:
                passed.append("shorten")
            else:
                failed.append(f"shorten: {c}")
        except Exception as e:
            failed.append(f"shorten: {e}")
        
        # Test 2: resolve
        try:
            s2 = namespace['URLShortener']()
            c = s2.shorten("https://b.com")
            if s2.resolve(c) == "https://b.com":
                passed.append("resolve")
            else:
                failed.append("resolve: wrong url")
        except Exception as e:
            failed.append(f"resolve: {e}")
        
        # Test 3: unknown → None
        try:
            if namespace['URLShortener']().resolve("XXX") is None:
                passed.append("unknown→None")
            else:
                failed.append("unknown: not None")
        except Exception as e:
            failed.append(f"unknown: {e}")
        
        # Test 4: clicks
        try:
            s4 = namespace['URLShortener']()
            c = s4.shorten("https://c.com")
            s4.resolve(c)
            s4.resolve(c)
            if s4.get_clicks(c) >= 2:
                passed.append("clicks")
            else:
                failed.append("clicks: wrong count")
        except Exception as e:
            failed.append(f"clicks: {e}")
        
        # Test 5: unique codes
        try:
            s5 = namespace['URLShortener']()
            c1, c2 = s5.shorten("https://d.com"), s5.shorten("https://e.com")
            if c1 != c2:
                passed.append("unique")
            else:
                failed.append("unique: same codes")
        except Exception as e:
            failed.append(f"unique: {e}")
        
        # Test 6: stats
        try:
            s6 = namespace['URLShortener']()
            s6.shorten("https://f.com")
            s6.shorten("https://g.com")
            st = s6.stats()
            if isinstance(st, dict) and st.get('total_urls', 0) >= 2:
                passed.append("stats")
            else:
                failed.append(f"stats: {st}")
        except Exception as e:
            failed.append(f"stats: {e}")
            
    except Exception as e:
        failed.append(f"Init: {e}")
    
    return len(passed), passed, failed


# The key: EXPLICIT interface contract
INTERFACE_CONTRACT = """
CRITICAL: The class MUST have this EXACT interface (no extra parameters!):

class URLShortener:
    def __init__(self):  # NO PARAMETERS
        ...
    
    def shorten(self, url: str) -> str:
        ...
    
    def resolve(self, code: str) -> str | None:
        ...
    
    def get_clicks(self, code: str) -> int:
        ...
    
    def stats(self) -> dict:
        ...
"""


async def yes_and_strict(fish: list) -> tuple[int, str]:
    """Yes-And with strict interface enforcement."""
    print("\n  🔒 YES-AND STRICT: Explicit interface contract")
    
    # Fish 1: Basic storage - STRICT interface
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}

Write URLShortener with JUST shorten() and resolve() working.
- shorten(url) → generates 6-char code, stores mapping
- resolve(code) → returns URL or None

Leave get_clicks() and stats() as stubs (return 0 and {{}}).
"""),)
    )
    code = r1.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    s1, p1, f1 = test_solution(code)
    print(f"    Fish 1 (basic): {s1}/6 → {p1}")
    if f1 and s1 < 3:
        print(f"       Failed: {f1[0]}")
    
    # Fish 2: YES, AND... add click tracking
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}

Here's URLShortener with shorten/resolve working:
```python
{code}
```

YES, AND... make get_clicks() work:
- Track clicks when resolve() is called
- get_clicks(code) returns the count

DO NOT change __init__ signature. DO NOT change shorten/resolve behavior.
Just ADD click tracking.
"""),)
    )
    code = r2.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    s2, p2, f2 = test_solution(code)
    print(f"    Fish 2 (+clicks): {s2}/6 → {p2}")
    if f2 and s2 < 4:
        print(f"       Failed: {f2[0]}")
    
    # Fish 3: YES, AND... add stats
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}

Here's URLShortener with shorten/resolve/get_clicks working:
```python
{code}
```

YES, AND... make stats() work:
- Return {{'total_urls': N, 'total_clicks': N}}

DO NOT change any existing method signatures or behavior.
Just implement stats().
"""),)
    )
    code = r3.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    s3, p3, f3 = test_solution(code)
    print(f"    Fish 3 (+stats): {s3}/6 → {p3}")
    if f3:
        print(f"       Failed: {f3[:2]}")
    
    return s3, code


async def traditional_best_of_n(fish: list) -> tuple[int, str]:
    """Traditional: generate N, pick best."""
    print("\n  📝 BEST-OF-N: Generate 3, pick best")
    
    best_score, best_code = 0, ""
    
    for f, name in zip(fish, FISH_MODELS):
        r = await f.generate(
            prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}

Implement the complete URLShortener class with ALL methods working.
"""),)
        )
        code = r.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        score, passed, _ = test_solution(code)
        print(f"    🐟 {name}: {score}/6 → {passed}")
        
        if score > best_score:
            best_score, best_code = score, code
    
    return best_score, best_code


async def hybrid_approach(fish: list) -> tuple[int, str]:
    """Hybrid: Best-of-N for base, Yes-And to improve."""
    print("\n  🔀 HYBRID: Best-of-N base, Yes-And improve")
    
    # Phase 1: Best-of-N for base
    print("    Phase 1: Generate bases...")
    bases = []
    for f, name in zip(fish, FISH_MODELS):
        r = await f.generate(
            prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}
Write URLShortener with shorten() and resolve() working.
Leave get_clicks() returning 0 and stats() returning {{}}.
"""),)
        )
        code = r.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        score, passed, _ = test_solution(code)
        bases.append((name, code, score, passed))
        print(f"      {name}: {score}/6")
    
    # Pick best base
    best_base = max(bases, key=lambda x: x[2])
    code = best_base[1]
    print(f"    Best base: {best_base[0]} ({best_base[2]}/6)")
    
    # Phase 2: Yes-And to add features
    print("    Phase 2: Yes-And to add features...")
    
    # Add clicks
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}
```python
{code}
```
YES, AND... implement get_clicks(). Track calls to resolve().
DO NOT change existing methods.
"""),)
    )
    code = r2.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    s2, p2, _ = test_solution(code)
    print(f"      +clicks: {s2}/6")
    
    # Add stats
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
{INTERFACE_CONTRACT}
```python
{code}
```
YES, AND... implement stats(). Return {{'total_urls': N, 'total_clicks': N}}.
DO NOT change existing methods.
"""),)
    )
    code = r3.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    s3, p3, f3 = test_solution(code)
    print(f"      +stats: {s3}/6 → {p3}")
    
    return s3, code


async def main():
    print("🔒 YES-AND WITH STRICT INTERFACE")
    print("=" * 70)
    print("Hypothesis: Yes-And fails when fish modify interfaces")
    print("Fix: Explicit contract preservation")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    
    results = []
    
    # Best-of-N
    print("\n📍 APPROACH 1: Best-of-N")
    print("-" * 70)
    score, _ = await traditional_best_of_n(fish)
    results.append(("Best-of-N", score))
    
    # Yes-And Strict
    print("\n📍 APPROACH 2: Yes-And Strict")
    print("-" * 70)
    score, _ = await yes_and_strict(fish)
    results.append(("Yes-And Strict", score))
    
    # Hybrid
    print("\n📍 APPROACH 3: Hybrid (Best-of-N → Yes-And)")
    print("-" * 70)
    score, _ = await hybrid_approach(fish)
    results.append(("Hybrid", score))
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    for name, score in sorted(results, key=lambda x: -x[1]):
        bar = "█" * score + "░" * (6 - score)
        marker = "🥇" if score == max(r[1] for r in results) else "  "
        print(f"{marker} {name:<20} {score}/6 {bar}")
    
    best = max(results, key=lambda x: x[1])
    print(f"\n🏆 Winner: {best[0]} with {best[1]}/6 features")


if __name__ == "__main__":
    asyncio.run(main())
