#!/usr/bin/env python3
"""Verify lens composition changes model behavior.

Demonstrates that loading different lenses produces measurably
different outputs for the same prompt.
"""

import asyncio
from pathlib import Path

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message
from sunwell.schema.loader import LensLoader


LENSES_DIR = Path(__file__).parent.parent / "lenses"
TEST_PROMPT = "Review this code and suggest improvements:\n\ndef add(a, b): return a + b"


async def main():
    loader = LensLoader()
    model = OllamaModel(model="llama3.2:3b")

    # Load two different lenses
    tech_writer = loader.load(LENSES_DIR / "tech-writer.lens")
    coder = loader.load(LENSES_DIR / "coder.lens")

    print("=" * 70)
    print("LENS COMPOSITION VERIFICATION")
    print("=" * 70)
    print(f"\nPrompt: {TEST_PROMPT[:50]}...")

    # Get contexts
    tw_context = tech_writer.to_context()
    coder_context = coder.to_context()

    print(f"\n📝 Tech-Writer context length: {len(tw_context)} chars")
    print(f"💻 Coder context length: {len(coder_context)} chars")

    # Show context differences
    print("\n--- Tech-Writer Heuristics ---")
    for h in tech_writer.heuristics[:3]:
        print(f"  • {h.name}: {h.rule[:50]}...")

    print("\n--- Coder Heuristics ---")
    for h in coder.heuristics[:3]:
        print(f"  • {h.name}: {h.rule[:50]}...")

    # Generate with each lens using Message tuples
    print("\n" + "=" * 70)
    print("GENERATING WITH TECH-WRITER LENS")
    print("=" * 70)

    tw_messages = (
        Message(role="system", content=f"You are an expert assistant. Apply these principles:\n\n{tw_context}"),
        Message(role="user", content=TEST_PROMPT),
    )
    tw_response = await model.generate(prompt=tw_messages)
    print(tw_response.content[:500])

    print("\n" + "=" * 70)
    print("GENERATING WITH CODER LENS")
    print("=" * 70)

    coder_messages = (
        Message(role="system", content=f"You are an expert assistant. Apply these principles:\n\n{coder_context}"),
        Message(role="user", content=TEST_PROMPT),
    )
    coder_response = await model.generate(prompt=coder_messages)
    print(coder_response.content[:500])

    # Compare
    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)

    tw_text = tw_response.content.lower()
    coder_text = coder_response.content.lower()

    # Look for lens-specific patterns
    tw_keywords = ["documentation", "docstring", "reader", "clarity", "diataxis"]
    coder_keywords = ["type", "error", "test", "refactor", "performance"]

    tw_matches = sum(1 for kw in tw_keywords if kw in tw_text)
    coder_matches = sum(1 for kw in coder_keywords if kw in coder_text)

    print(f"\nTech-Writer response doc keywords: {tw_matches}/{len(tw_keywords)}")
    print(f"Coder response code keywords: {coder_matches}/{len(coder_keywords)}")

    # Verify they're different
    if tw_response.content != coder_response.content:
        print("\n✅ VERIFIED: Different lenses produce different outputs")
    else:
        print("\n⚠️ WARNING: Outputs identical (may need longer generation)")

    print(f"\nResponse length difference: {abs(len(tw_response.content) - len(coder_response.content))} chars")


if __name__ == "__main__":
    asyncio.run(main())
