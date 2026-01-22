#!/usr/bin/env python3
"""Test if fewer heuristics = better results.

Hypothesis: 5K chars of context might overwhelm the model.
Test: Use only top 3 heuristics vs full lens.
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

JUDGE_PROMPT = """You are a senior technical writer. Score this tutorial 1-10 for each:

1. STRUCTURE: Progressive disclosure? Logical flow?
2. ACCURACY: Would the code work?
3. AUDIENCE: Right level for the stated audience?
4. STYLE: Signal-to-noise? Concise?
5. COMPLETENESS: Prerequisites? Next steps?

Tutorial:
{content}

Format:
STRUCTURE: X/10
ACCURACY: X/10
AUDIENCE: X/10
STYLE: X/10
COMPLETENESS: X/10
TOTAL: XX/50
"""


async def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    loader = LensLoader()
    model = OllamaModel(model=model_name)
    lens = loader.load(LENSES_DIR / "tech-writer.lens")

    # Full context
    full_context = lens.to_context()
    
    # Pruned context: only top 3 heuristics
    top3 = sorted(lens.heuristics, key=lambda h: h.priority, reverse=True)[:3]
    pruned_context = lens.to_context(components=[h.name for h in top3])

    print(f"Model: {model_name}")
    print(f"Full context: {len(full_context)} chars")
    print(f"Pruned context: {len(pruned_context)} chars ({100 - len(pruned_context)/len(full_context)*100:.0f}% smaller)")
    print()

    # Test both
    for name, context in [("FULL LENS", full_context), ("PRUNED (top 3)", pruned_context)]:
        print(f"--- {name} ---")
        
        messages = (
            Message(role="system", content=f"You are an expert technical writer.\n\n{context}"),
            Message(role="user", content=TASK),
        )
        response = await model.generate(prompt=messages)
        
        # Judge
        judge_messages = (Message(role="user", content=JUDGE_PROMPT.format(content=response.content)),)
        judgment = await model.generate(prompt=judge_messages)
        
        # Extract total
        import re
        match = re.search(r"TOTAL:\s*(\d+)/50", judgment.content)
        score = int(match.group(1)) if match else "?"
        
        print(f"Output: {len(response.content)} chars")
        print(f"Score: {score}/50")
        print()


if __name__ == "__main__":
    asyncio.run(main())
