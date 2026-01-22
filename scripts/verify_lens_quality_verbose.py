#!/usr/bin/env python3
"""Show actual outputs to understand lens quality differences."""

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

    tech_writer = loader.load(LENSES_DIR / "tech-writer.lens")
    coder = loader.load(LENSES_DIR / "coder.lens")

    # Tech-writer
    tw_messages = (
        Message(role="system", content=f"You are an expert assistant. Apply these principles:\n\n{tech_writer.to_context()}"),
        Message(role="user", content=TEST_PROMPT),
    )
    tw_response = await model.generate(prompt=tw_messages)

    # Coder
    coder_messages = (
        Message(role="system", content=f"You are an expert assistant. Apply these principles:\n\n{coder.to_context()}"),
        Message(role="user", content=TEST_PROMPT),
    )
    coder_response = await model.generate(prompt=coder_messages)

    print("=" * 70)
    print("TECH-WRITER LENS OUTPUT")
    print("=" * 70)
    print(tw_response.content)
    
    print("\n" + "=" * 70)
    print("CODER LENS OUTPUT")
    print("=" * 70)
    print(coder_response.content)


if __name__ == "__main__":
    asyncio.run(main())
