#!/usr/bin/env python3
"""Verify lens produces BETTER output than bare model on complex task.

Generates the same tutorial twice:
1. Bare model (no lens)
2. Model + tech-writer lens

Then uses a judge to score both on professional criteria.
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

JUDGE_PROMPT = """You are a senior technical writer evaluating documentation quality.

Score this tutorial on a 1-10 scale for each criterion. Be harsh - a professional would be.

## Criteria

1. **STRUCTURE** (1-10): Does it have progressive disclosure? Logical flow? Clear sections?
2. **ACCURACY** (1-10): Are the code examples correct? Would they actually work?
3. **AUDIENCE** (1-10): Is it approachable for the stated audience? Not too basic, not too advanced?
4. **STYLE** (1-10): Signal-to-noise ratio? Active voice? Concrete over abstract?
5. **COMPLETENESS** (1-10): Prerequisites? Next steps? Error handling?

## Tutorial to Evaluate

{content}

## Your Evaluation

For each criterion, give a score and ONE sentence explaining why. Then give a total score (sum of all 5).

Format:
STRUCTURE: X/10 - reason
ACCURACY: X/10 - reason
AUDIENCE: X/10 - reason
STYLE: X/10 - reason
COMPLETENESS: X/10 - reason
TOTAL: XX/50
"""


async def generate_tutorial(model: OllamaModel, task: str, lens_context: str | None) -> str:
    """Generate a tutorial with or without lens."""
    if lens_context:
        messages = (
            Message(role="system", content=f"You are an expert technical writer. Apply these principles:\n\n{lens_context}"),
            Message(role="user", content=task),
        )
    else:
        messages = (
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content=task),
        )
    
    response = await model.generate(prompt=messages)
    return response.content


async def judge_tutorial(model: OllamaModel, content: str) -> str:
    """Have a judge evaluate the tutorial."""
    messages = (
        Message(role="user", content=JUDGE_PROMPT.format(content=content)),
    )
    response = await model.generate(prompt=messages)
    return response.content


def parse_score(judge_output: str) -> int | None:
    """Extract total score from judge output."""
    import re
    match = re.search(r"TOTAL:\s*(\d+)/50", judge_output)
    if match:
        return int(match.group(1))
    return None


async def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    judge_model_name = sys.argv[2] if len(sys.argv) > 2 else model_name
    
    print("=" * 70)
    print("LENS VS BARE MODEL: COMPLEX TASK VERIFICATION")
    print("=" * 70)
    print(f"\nGenerator model: {model_name}")
    print(f"Judge model: {judge_model_name}")
    print(f"\nTask: Pokemon API Getting Started Tutorial")

    loader = LensLoader()
    generator = OllamaModel(model=model_name)
    judge = OllamaModel(model=judge_model_name)

    # Load tech-writer lens
    tech_writer = loader.load(LENSES_DIR / "tech-writer.lens")
    lens_context = tech_writer.to_context()

    # Generate with bare model
    print("\n" + "=" * 70)
    print("GENERATING: BARE MODEL (no lens)")
    print("=" * 70)
    bare_tutorial = await generate_tutorial(generator, TASK, lens_context=None)
    print(f"\nGenerated {len(bare_tutorial)} chars")
    
    # Generate with lens
    print("\n" + "=" * 70)
    print("GENERATING: TECH-WRITER LENS")
    print("=" * 70)
    lens_tutorial = await generate_tutorial(generator, TASK, lens_context=lens_context)
    print(f"\nGenerated {len(lens_tutorial)} chars")

    # Judge both
    print("\n" + "=" * 70)
    print("JUDGING: BARE MODEL OUTPUT")
    print("=" * 70)
    bare_judgment = await judge_tutorial(judge, bare_tutorial)
    bare_score = parse_score(bare_judgment)
    print(bare_judgment)

    print("\n" + "=" * 70)
    print("JUDGING: TECH-WRITER LENS OUTPUT")
    print("=" * 70)
    lens_judgment = await judge_tutorial(judge, lens_tutorial)
    lens_score = parse_score(lens_judgment)
    print(lens_judgment)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nBare model score:      {bare_score}/50" if bare_score else "\nBare model score:      Could not parse")
    print(f"Tech-writer lens score: {lens_score}/50" if lens_score else "Tech-writer lens score: Could not parse")
    
    if bare_score and lens_score:
        diff = lens_score - bare_score
        pct = (diff / bare_score * 100) if bare_score > 0 else 0
        print(f"\nDifference: {diff:+d} ({pct:+.1f}%)")
        
        if lens_score > bare_score:
            print("\n✅ VERIFIED: Tech-writer lens produces BETTER output")
        elif lens_score == bare_score:
            print("\n⚠️ TIE: No measurable difference")
        else:
            print("\n❌ UNEXPECTED: Bare model scored higher")

    # Save outputs for inspection
    output_dir = Path(__file__).parent.parent / "benchmark" / "results" / "lens_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    (output_dir / "bare_tutorial.md").write_text(bare_tutorial)
    (output_dir / "lens_tutorial.md").write_text(lens_tutorial)
    (output_dir / "bare_judgment.txt").write_text(bare_judgment)
    (output_dir / "lens_judgment.txt").write_text(lens_judgment)
    
    print(f"\nOutputs saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
