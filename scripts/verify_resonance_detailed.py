#!/usr/bin/env python3
"""Show detailed resonance refinement - WHAT changed."""

import asyncio
from sunwell.planning.naaru.resonance import Resonance, ResonanceConfig


TEST_CASES = [
    {
        "name": "Minimal function",
        "code": "def add(a, b): return a + b",
    },
    {
        "name": "No error handling",
        "code": "def divide(a, b): return a / b",
    },
]


async def main():
    from sunwell.models.ollama import OllamaModel
    model = OllamaModel(model="llama3.2:3b")

    resonance = Resonance(
        model=model,
        config=ResonanceConfig(max_attempts=1, max_tokens=512),
    )

    for test in TEST_CASES:
        print("=" * 70)
        print(f"TEST: {test['name']}")
        print("=" * 70)

        print("\n📝 ORIGINAL CODE:")
        print("-" * 40)
        print(test["code"])
        print("-" * 40)

        proposal = {
            "proposal_id": test["name"],
            "diff": test["code"],
            "summary": {"category": "code_quality"},
        }
        rejection = {
            "issues": ["Missing docstring", "No type hints", "No error handling"],
            "score": 2.0,
        }

        result = await resonance.refine(proposal, rejection)

        print("\n✨ REFINED CODE:")
        print("-" * 40)
        print(result.refined_code)
        print("-" * 40)
        print()


if __name__ == "__main__":
    asyncio.run(main())
