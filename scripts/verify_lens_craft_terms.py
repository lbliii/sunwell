#!/usr/bin/env python3
"""Test if professional craft terminology improves lens effectiveness.

Compares:
- Original tech-writer lens (abstract principles)
- Refined lens (professional terminology like BLUF, Diataxis, progressive disclosure)
"""

import asyncio
import sys
from pathlib import Path

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message
from sunwell.schema.loader import LensLoader


LENSES_DIR = Path(__file__).parent.parent / "lenses"

TASK = """Write a getting started tutorial for using the Pokemon API (pokeapi.co) in Python.

The tutorial should help a developer who knows Python but has never used this API.

Include:
- What the API offers
- How to make requests
- A practical example (get a Pokemon's stats)
- Common gotchas
"""

JUDGE_PROMPT = """You are a senior technical writer evaluating documentation.

Score this tutorial 1-10 for each criterion (be harsh):

1. BLUF: Does it state the key point upfront? Or bury the lede?
2. STRUCTURE: Progressive disclosure? Logical layers?
3. CLARITY: Active voice? Concise? No fluff?
4. CODE_FIRST: Working examples before explanation?
5. DIATAXIS: Is it clearly a TUTORIAL (not reference or explanation mixed in)?

Tutorial:
{content}

Format exactly:
BLUF: X/10 - reason
STRUCTURE: X/10 - reason
CLARITY: X/10 - reason  
CODE_FIRST: X/10 - reason
DIATAXIS: X/10 - reason
TOTAL: XX/50
"""


async def test_lens(model: OllamaModel, lens_path: Path, lens_name: str) -> dict:
    """Test a lens and return results."""
    loader = LensLoader()
    lens = loader.load(lens_path)
    context = lens.to_context()
    
    # Generate
    messages = (
        Message(role="system", content=f"You are an expert technical writer.\n\n{context}"),
        Message(role="user", content=TASK),
    )
    response = await model.generate(prompt=messages)
    
    # Judge
    judge_messages = (Message(role="user", content=JUDGE_PROMPT.format(content=response.content)),)
    judgment = await model.generate(prompt=judge_messages)
    
    # Parse score
    import re
    match = re.search(r"TOTAL:\s*(\d+)/50", judgment.content)
    score = int(match.group(1)) if match else None
    
    return {
        "name": lens_name,
        "context_length": len(context),
        "output_length": len(response.content),
        "score": score,
        "judgment": judgment.content,
        "output": response.content,
    }


async def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    model = OllamaModel(model=model_name)
    
    print("=" * 70)
    print("CRAFT TERMINOLOGY LENS TEST")
    print("=" * 70)
    print(f"Model: {model_name}")
    print()

    # Test both lenses
    results = []
    
    for lens_file, lens_name in [
        ("tech-writer.lens", "ORIGINAL (abstract principles)"),
        ("tech-writer-refined.lens", "REFINED (craft terminology)"),
    ]:
        print(f"Testing: {lens_name}...")
        result = await test_lens(model, LENSES_DIR / lens_file, lens_name)
        results.append(result)
        print(f"  Context: {result['context_length']} chars")
        print(f"  Output: {result['output_length']} chars")
        print(f"  Score: {result['score']}/50")
        print()

    # Compare
    print("=" * 70)
    print("COMPARISON")
    print("=" * 70)
    
    original = results[0]
    refined = results[1]
    
    print(f"\n{'Metric':<25} {'Original':<15} {'Refined':<15} {'Diff':<10}")
    print("-" * 65)
    print(f"{'Context (chars)':<25} {original['context_length']:<15} {refined['context_length']:<15} {refined['context_length'] - original['context_length']:+d}")
    print(f"{'Output (chars)':<25} {original['output_length']:<15} {refined['output_length']:<15} {refined['output_length'] - original['output_length']:+d}")
    
    if original['score'] and refined['score']:
        diff = refined['score'] - original['score']
        pct = (diff / original['score'] * 100) if original['score'] > 0 else 0
        print(f"{'Score':<25} {original['score']:<15} {refined['score']:<15} {diff:+d} ({pct:+.1f}%)")
        
        if refined['score'] > original['score']:
            print(f"\n✅ REFINED LENS WINS by {diff} points ({pct:+.1f}%)")
        elif refined['score'] == original['score']:
            print(f"\n⚠️ TIE")
        else:
            print(f"\n❌ ORIGINAL LENS WINS")

    # Show judgments
    print("\n" + "=" * 70)
    print("ORIGINAL LENS JUDGMENT")
    print("=" * 70)
    print(original['judgment'])
    
    print("\n" + "=" * 70)
    print("REFINED LENS JUDGMENT")
    print("=" * 70)
    print(refined['judgment'])


if __name__ == "__main__":
    asyncio.run(main())
