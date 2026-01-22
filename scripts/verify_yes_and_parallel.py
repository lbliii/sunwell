#!/usr/bin/env python3
"""Yes-And on a PARALLEL problem (multiple independent requirements).

Task: URL Shortener class with 6 INDEPENDENT features:
1. Generate short codes
2. Store URL mappings
3. Retrieve original URLs
4. Handle collisions
5. Track click counts
6. Expire old links (TTL)

Each feature is independent — perfect for parallel Yes-And.
"""

import asyncio
import re
import time

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = ["gemma3:1b", "llama3.2:1b", "qwen2.5:1.5b"]

FULL_TASK = """
Implement a URLShortener class with these features:
1. shorten(url) → returns a short code (6 chars)
2. resolve(code) → returns original URL or None
3. Collision handling (if code exists, generate new one)
4. Click tracking: get_clicks(code) → int
5. TTL: shorten(url, ttl_seconds=N) expires after N seconds
6. stats() → dict with total URLs, total clicks

Example:
    s = URLShortener()
    code = s.shorten("https://example.com")
    url = s.resolve(code)  # "https://example.com"
    s.resolve(code)  # increments click count
    s.get_clicks(code)  # 2
"""


def test_solution(code: str) -> tuple[int, list, list]:
    """Test each feature independently."""
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return 0, [], [f"Exec: {e}"]
    
    if 'URLShortener' not in namespace:
        return 0, [], ["No URLShortener class"]
    
    passed, failed = [], []
    
    try:
        s = namespace['URLShortener']()
        
        # Test 1: Basic shorten
        try:
            code1 = s.shorten("https://a.com")
            if code1 and len(str(code1)) >= 4:
                passed.append("shorten")
            else:
                failed.append(f"shorten: got {code1}")
        except Exception as e:
            failed.append(f"shorten: {e}")
        
        # Test 2: Resolve
        try:
            s2 = namespace['URLShortener']()
            c = s2.shorten("https://b.com")
            result = s2.resolve(c)
            if result == "https://b.com":
                passed.append("resolve")
            else:
                failed.append(f"resolve: got {result}")
        except Exception as e:
            failed.append(f"resolve: {e}")
        
        # Test 3: Unknown code returns None
        try:
            s3 = namespace['URLShortener']()
            result = s3.resolve("XXXXXX")
            if result is None:
                passed.append("unknown→None")
            else:
                failed.append(f"unknown: got {result}")
        except Exception as e:
            failed.append(f"unknown: {e}")
        
        # Test 4: Click tracking
        try:
            s4 = namespace['URLShortener']()
            c = s4.shorten("https://c.com")
            s4.resolve(c)
            s4.resolve(c)
            clicks = s4.get_clicks(c)
            if clicks >= 2:
                passed.append("clicks")
            else:
                failed.append(f"clicks: got {clicks}")
        except Exception as e:
            failed.append(f"clicks: {e}")
        
        # Test 5: Multiple URLs get different codes
        try:
            s5 = namespace['URLShortener']()
            c1 = s5.shorten("https://d.com")
            c2 = s5.shorten("https://e.com")
            if c1 != c2:
                passed.append("unique codes")
            else:
                failed.append(f"unique: both got {c1}")
        except Exception as e:
            failed.append(f"unique: {e}")
        
        # Test 6: Stats
        try:
            s6 = namespace['URLShortener']()
            s6.shorten("https://f.com")
            s6.shorten("https://g.com")
            stats = s6.stats()
            if isinstance(stats, dict) and stats.get('total_urls', 0) >= 2:
                passed.append("stats")
            else:
                failed.append(f"stats: got {stats}")
        except Exception as e:
            failed.append(f"stats: {e}")
        
        # Test 7: TTL (if supported)
        try:
            s7 = namespace['URLShortener']()
            c = s7.shorten("https://h.com", ttl_seconds=1)
            time.sleep(1.5)
            result = s7.resolve(c)
            if result is None:
                passed.append("TTL")
            else:
                # TTL not implemented or not working, not a failure
                pass
        except TypeError:
            # TTL parameter not supported
            pass
        except Exception as e:
            pass  # TTL is bonus
            
    except Exception as e:
        failed.append(f"Init: {e}")
    
    return len(passed), passed, failed


async def traditional_approach(fish: list) -> tuple[int, str]:
    """Write full solution, then fix."""
    print("\n  📝 TRADITIONAL: Write everything at once")
    
    best_score = 0
    best_code = ""
    
    for f, name in zip(fish, FISH_MODELS):
        r = await f.generate(
            prompt=(Message(role="user", content=f"{FULL_TASK}\n\nWrite the complete class:"),)
        )
        code = r.content
        match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
        if match:
            code = match.group(1)
        
        score, passed, failed = test_solution(code)
        print(f"    🐟 {name}: {score}/6 ({', '.join(passed)})")
        
        if score > best_score:
            best_score = score
            best_code = code
    
    return best_score, best_code


async def yes_and_sequential(fish: list) -> tuple[int, str]:
    """Yes-And: Each fish adds ONE feature."""
    print("\n  🎭 YES-AND SEQUENTIAL: Each fish adds a feature")
    
    # Fish 1: Basic storage
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content="""
Write a simple URLShortener class with JUST:
- shorten(url) → generates a 6-char code
- resolve(code) → returns the original URL

Keep it minimal. We'll add more features later.
"""),)
    )
    code = r1.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    score, passed, _ = test_solution(code)
    print(f"    Fish 1 (basic): {score}/6 → {passed}")
    
    # Fish 2: YES, AND... add click tracking
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
Here's a working URLShortener:
```python
{code}
```

YES, AND... extend it to ALSO track clicks:
- Each call to resolve() increments a counter
- get_clicks(code) → returns click count

Keep shorten() and resolve() working. Just ADD click tracking.
"""),)
    )
    code = r2.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    score, passed, _ = test_solution(code)
    print(f"    Fish 2 (+clicks): {score}/6 → {passed}")
    
    # Fish 3: YES, AND... add stats
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
Here's URLShortener with basic ops and click tracking:
```python
{code}
```

YES, AND... extend it to ALSO have stats:
- stats() → returns {{'total_urls': N, 'total_clicks': N}}
- resolve() returns None for unknown codes

Keep everything working. Just ADD the stats method.
"""),)
    )
    code = r3.content
    match = re.search(r'```python\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1)
    score, passed, failed = test_solution(code)
    print(f"    Fish 3 (+stats): {score}/6 → {passed}")
    if failed:
        print(f"       Failed: {failed[:2]}")
    
    return score, code


async def yes_and_parallel(fish: list) -> tuple[int, str]:
    """Yes-And Parallel: Each fish specializes, then merge."""
    print("\n  🎭 YES-AND PARALLEL: Each fish owns one feature")
    
    BASE = '''
class URLShortener:
    def __init__(self):
        self.urls = {}  # code -> url
'''
    
    features = []
    
    # Fish 1: Code generation
    r1 = await fish[0].generate(
        prompt=(Message(role="user", content=f"""
```python
{BASE}
```

YES, AND... add shorten(url) that:
- Generates a unique 6-character code
- Stores the mapping
- Returns the code

Just this one method.
"""),)
    )
    code1 = r1.content
    match = re.search(r'```python\n(.*?)```', code1, re.DOTALL)
    if match:
        code1 = match.group(1)
    s1, p1, _ = test_solution(code1)
    features.append(("shorten", code1, s1))
    print(f"    Fish 1 (shorten): {s1}/6")
    
    # Fish 2: Resolution + clicks
    r2 = await fish[1].generate(
        prompt=(Message(role="user", content=f"""
```python
{BASE}
        self.clicks = {{}}  # code -> count
```

YES, AND... add:
- resolve(code) → returns URL or None
- get_clicks(code) → returns click count
- resolve increments click count

Just these methods.
"""),)
    )
    code2 = r2.content
    match = re.search(r'```python\n(.*?)```', code2, re.DOTALL)
    if match:
        code2 = match.group(1)
    s2, p2, _ = test_solution(code2)
    features.append(("resolve+clicks", code2, s2))
    print(f"    Fish 2 (resolve+clicks): {s2}/6")
    
    # Fish 3: Stats
    r3 = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
```python
{BASE}
        self.clicks = {{}}
```

YES, AND... add:
- stats() → {{'total_urls': len(self.urls), 'total_clicks': sum(self.clicks.values())}}

Just this method.
"""),)
    )
    code3 = r3.content
    match = re.search(r'```python\n(.*?)```', code3, re.DOTALL)
    if match:
        code3 = match.group(1)
    features.append(("stats", code3, 0))
    print(f"    Fish 3 (stats): added")
    
    # Combine
    r_combine = await fish[2].generate(
        prompt=(Message(role="user", content=f"""
Three programmers each added features to URLShortener:

Feature 1 (shorten):
```python
{features[0][1]}
```

Feature 2 (resolve + clicks):
```python
{features[1][1]}
```

Feature 3 (stats):
```python
{features[2][1]}
```

YES, AND... combine ALL features into one complete class.
Make sure all methods work together.
"""),)
    )
    combined = r_combine.content
    match = re.search(r'```python\n(.*?)```', combined, re.DOTALL)
    if match:
        combined = match.group(1)
    score, passed, failed = test_solution(combined)
    print(f"    Combined: {score}/6 → {passed}")
    if failed:
        print(f"       Failed: {failed[:2]}")
    
    return score, combined


async def main():
    print("🎭 YES-AND: PARALLEL REQUIREMENTS")
    print("=" * 70)
    print("Task: URLShortener with 6 independent features")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    
    results = []
    
    # Traditional
    print("\n📍 APPROACH 1: Traditional")
    print("-" * 70)
    score, _ = await traditional_approach(fish)
    results.append(("Traditional", score))
    
    # Yes-And Sequential
    print("\n📍 APPROACH 2: Yes-And Sequential")
    print("-" * 70)
    score, _ = await yes_and_sequential(fish)
    results.append(("Yes-And Seq", score))
    
    # Yes-And Parallel
    print("\n📍 APPROACH 3: Yes-And Parallel")
    print("-" * 70)
    score, _ = await yes_and_parallel(fish)
    results.append(("Yes-And Par", score))
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    print(f"\n{'Approach':<20} {'Features':<15}")
    print("-" * 35)
    for name, score in results:
        bar = "█" * score + "░" * (6 - score)
        indicator = "🥇" if score == max(r[1] for r in results) else "  "
        print(f"{indicator} {name:<18} {score}/6 {bar}")
    
    best = max(results, key=lambda x: x[1])
    worst = min(results, key=lambda x: x[1])
    
    if best[1] > worst[1]:
        print(f"\n✅ {best[0]} wins by +{best[1] - worst[1]} features!")
    else:
        print(f"\n➖ All approaches tied at {best[1]}/6")


if __name__ == "__main__":
    asyncio.run(main())
