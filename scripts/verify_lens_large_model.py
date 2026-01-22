#!/usr/bin/env python3
"""Test lens optimized for large model weaknesses."""

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

JUDGE_PROMPT = """You are evaluating technical documentation. Score 1-10 for each:

1. CODE_FIRST: Does working code appear BEFORE explanation?
2. CONCISION: Is every sentence essential? No padding?
3. DIRECTNESS: Direct claims, no hedging (might, could, perhaps)?
4. STRUCTURE: Parallel options shown together? Good flow?
5. SCOPE: Focused on one thing? No tangents?

Tutorial:
{content}

Format:
CODE_FIRST: X/10 - reason
CONCISION: X/10 - reason
DIRECTNESS: X/10 - reason
STRUCTURE: X/10 - reason
SCOPE: X/10 - reason
TOTAL: XX/50
"""


async def test_lens(model: OllamaModel, lens_path: Path) -> tuple[int | None, int, int]:
    """Test a lens, return (score, context_len, output_len)."""
    loader = LensLoader()
    lens = loader.load(lens_path)
    context = lens.to_context()
    
    messages = (
        Message(role="system", content=f"You are an expert technical writer.\n\n{context}"),
        Message(role="user", content=TASK),
    )
    response = await model.generate(prompt=messages)
    
    judge_messages = (Message(role="user", content=JUDGE_PROMPT.format(content=response.content)),)
    judgment = await model.generate(prompt=judge_messages)
    
    import re
    match = re.search(r"TOTAL:\s*(\d+)/50", judgment.content)
    score = int(match.group(1)) if match else None
    
    return score, len(context), len(response.content), judgment.content


async def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "gpt-oss:20b"
    model = OllamaModel(model=model_name)
    
    print(f"Model: {model_name}")
    print("=" * 70)
    
    lenses = [
        ("tech-writer.lens", "Original"),
        ("tech-writer-refined.lens", "Refined (craft terms)"),
        ("tech-writer-large-model.lens", "Large Model Optimized"),
    ]
    
    results = []
    for lens_file, name in lenses:
        print(f"\nTesting: {name}...")
        score, ctx_len, out_len, judgment = await test_lens(model, LENSES_DIR / lens_file)
        results.append((name, score, ctx_len, out_len, judgment))
        print(f"  Context: {ctx_len:,} chars")
        print(f"  Output: {out_len:,} chars")
        print(f"  Score: {score}/50")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Lens':<30} {'Context':<12} {'Output':<12} {'Score':<10}")
    print("-" * 64)
    for name, score, ctx_len, out_len, _ in results:
        print(f"{name:<30} {ctx_len:<12,} {out_len:<12,} {score if score else '?'}/50")
    
    # Show judgments
    for name, score, _, _, judgment in results:
        print(f"\n{'=' * 70}")
        print(f"{name} JUDGMENT")
        print("=" * 70)
        print(judgment)


if __name__ == "__main__":
    asyncio.run(main())
