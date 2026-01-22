#!/usr/bin/env python3
"""Verify Thinking Monitor: Can a small model detect when a large model is drifting?

Hypothesis: Detection is easier than generation. A 3B model might not be able to
AVOID professor mode, but it might be able to DETECT it in a 20B model's output.

Test:
1. Generate problematic outputs from 20B (professor mode, digression, hedging)
2. See if 3B can classify the problem
3. Test on partial output (mid-stream detection)
"""

import asyncio
import sys

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


# Examples of problematic thinking patterns
PROBLEMATIC_OUTPUTS = [
    # PROFESSOR MODE - explains before showing
    {
        "label": "professor_mode",
        "output": """Let me explain how to use the Pokemon API. First, it's important to understand 
that APIs, or Application Programming Interfaces, are mechanisms that allow different 
software applications to communicate with each other. The Pokemon API specifically 
provides access to a comprehensive database of Pokemon information. Before we dive into 
the code, let's discuss the fundamental concepts of REST APIs and HTTP methods. 
REST stands for Representational State Transfer, which is an architectural style for 
designing networked applications. When you make a request to an API endpoint...""",
    },
    
    # ON TRACK - code first, concise
    {
        "label": "on_track",
        "output": """```python
import requests

response = requests.get("https://pokeapi.co/api/v2/pokemon/pikachu")
pokemon = response.json()
print(f"Name: {pokemon['name']}, HP: {pokemon['stats'][0]['base_stat']}")
```

This fetches Pikachu's data and prints its name and HP stat.""",
    },
    
    # HEDGING - lots of qualifiers
    {
        "label": "hedging",
        "output": """You might want to consider using the requests library, though there could be 
other options that might work better depending on your specific use case. It's possible 
that you may need to handle errors, perhaps with a try-except block, although this 
might not always be necessary. The API could potentially return different data formats, 
so you might want to check the documentation, which may or may not be up to date...""",
    },
    
    # DIGRESSION - goes off topic
    {
        "label": "digression",
        "output": """To call the Pokemon API, you'll use the requests library. Speaking of libraries, 
Python's package ecosystem is really fascinating. Did you know that PyPI hosts over 
400,000 packages? The history of Python packaging is actually quite interesting - 
it started with distutils, then setuptools came along, and now we have pip, poetry, 
and uv. Oh, and the Pokemon franchise itself started in 1996 with Red and Blue...""",
    },
    
    # OVER_EXPLAINING - repeating the same point
    {
        "label": "over_explaining",
        "output": """To make an API request, you need to use the requests library to send a request 
to the API. The request is sent using the requests.get() function, which sends a GET 
request. When you send this request, the API receives your request and processes it. 
After processing, the API sends back a response to your request. This response contains 
the data you requested when you made your request...""",
    },
    
    # ANOTHER ON_TRACK - different style, still good
    {
        "label": "on_track",
        "output": """**Quick start:**

1. Install: `pip install requests`
2. Fetch a Pokemon:
```python
import requests
data = requests.get("https://pokeapi.co/api/v2/pokemon/25").json()
```
3. Access stats: `data['stats']`

That's it. The API returns JSON with all Pokemon attributes.""",
    },
]


MONITOR_PROMPT = """You are a writing quality monitor. Classify this output into ONE category:

- on_track: Clear, concise, shows code/examples early, no unnecessary explanation
- professor_mode: Explains concepts before showing practical examples, academic tone
- hedging: Uses lots of "might", "could", "perhaps", "possibly" - lacks confidence
- digression: Goes off-topic, includes tangents unrelated to the task
- over_explaining: Repeats the same point multiple ways, redundant

Output to classify:
---
{output}
---

Respond with ONLY the category name (one word): """


PARTIAL_MONITOR_PROMPT = """You are monitoring AI output mid-generation. Based on this PARTIAL output 
(generation is still ongoing), predict if there's a problem developing:

- on_track: Looks good so far
- professor_mode: Starting to explain too much before showing examples
- hedging: Accumulating uncertainty language
- digression: Starting to go off-topic
- over_explaining: Beginning to repeat itself

Partial output (first ~100 words):
---
{output}
---

Respond with ONLY the category name (one word): """


async def test_full_detection(monitor: OllamaModel) -> list[dict]:
    """Test if monitor can classify full outputs correctly."""
    results = []
    
    print("\n" + "=" * 70)
    print("TEST 1: Full Output Detection")
    print("=" * 70)
    
    for example in PROBLEMATIC_OUTPUTS:
        response = await monitor.generate(
            prompt=(Message(role="user", content=MONITOR_PROMPT.format(output=example["output"])),)
        )
        
        predicted = response.content.strip().lower().replace("_", "")
        expected = example["label"].replace("_", "")
        
        # Normalize - sometimes model says "on track" vs "ontrack"
        if "ontrack" in predicted or "on track" in predicted:
            predicted = "ontrack"
        if "professor" in predicted:
            predicted = "professormode"
        if "over" in predicted or "explain" in predicted:
            predicted = "overexplaining"
            
        expected_normalized = expected.replace("_", "")
        correct = predicted == expected_normalized or (
            expected_normalized == "ontrack" and "track" in predicted
        )
        
        status = "✓" if correct else "✗"
        print(f"  {status} Expected: {example['label']:<15} Predicted: {response.content.strip()}")
        
        results.append({
            "expected": example["label"],
            "predicted": response.content.strip(),
            "correct": correct,
        })
    
    return results


async def test_partial_detection(monitor: OllamaModel) -> list[dict]:
    """Test if monitor can detect problems from partial output (first ~100 words)."""
    results = []
    
    print("\n" + "=" * 70)
    print("TEST 2: Partial Output Detection (Early Warning)")
    print("=" * 70)
    
    for example in PROBLEMATIC_OUTPUTS:
        # Take only first ~100 words
        words = example["output"].split()
        partial = " ".join(words[:min(50, len(words))])
        
        response = await monitor.generate(
            prompt=(Message(role="user", content=PARTIAL_MONITOR_PROMPT.format(output=partial)),)
        )
        
        predicted = response.content.strip().lower()
        expected = example["label"]
        
        # More lenient matching for partial
        correct = (
            expected.replace("_", "") in predicted.replace("_", "") or
            (expected == "on_track" and "track" in predicted)
        )
        
        status = "✓" if correct else "✗"
        print(f"  {status} Expected: {example['label']:<15} Predicted: {response.content.strip()}")
        print(f"      Partial: \"{partial[:60]}...\"")
        
        results.append({
            "expected": example["label"],
            "predicted": response.content.strip(),
            "correct": correct,
            "partial_length": len(partial),
        })
    
    return results


async def main():
    monitor_model = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    print(f"Monitor Model: {monitor_model}")
    print("=" * 70)
    print("Testing: Can a small model detect thinking problems in larger model output?")
    
    monitor = OllamaModel(model=monitor_model)
    
    # Test 1: Full output detection
    full_results = await test_full_detection(monitor)
    full_accuracy = sum(1 for r in full_results if r["correct"]) / len(full_results) * 100
    
    # Test 2: Partial output detection (early warning)
    partial_results = await test_partial_detection(monitor)
    partial_accuracy = sum(1 for r in partial_results if r["correct"]) / len(partial_results) * 100
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nFull Output Detection:    {full_accuracy:.0f}% ({sum(1 for r in full_results if r['correct'])}/{len(full_results)})")
    print(f"Partial Output Detection: {partial_accuracy:.0f}% ({sum(1 for r in partial_results if r['correct'])}/{len(partial_results)})")
    
    # Verdict
    print("\n" + "=" * 70)
    if full_accuracy >= 80 and partial_accuracy >= 60:
        print("✅ VERIFIED: Small model CAN detect thinking problems")
        print("   Even with partial output (early warning), detection works.")
    elif full_accuracy >= 80:
        print("⚠️  PARTIAL: Good at full detection, but early warning needs work")
    else:
        print("❌ NOT VERIFIED: Small model struggles to detect problems")
        print("   May need better prompts or larger monitor model.")


if __name__ == "__main__":
    asyncio.run(main())
