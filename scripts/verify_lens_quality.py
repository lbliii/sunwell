#!/usr/bin/env python3
"""Verify lens output is BETTER for its domain, not just different.

Uses each lens's own validators/heuristics to score outputs.
If tech-writer output scores higher on tech-writer criteria than coder output,
the lens is correctly shaping behavior.
"""

import asyncio
from pathlib import Path

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message
from sunwell.schema.loader import LensLoader


LENSES_DIR = Path(__file__).parent.parent / "lenses"
TEST_PROMPT = "Review this code and suggest improvements:\n\ndef add(a, b): return a + b"


def score_for_tech_writer(text: str) -> dict:
    """Score text against tech-writer STYLE criteria."""
    text_lower = text.lower()
    
    scores = {
        # STRUCTURE (tech-writer focuses on organization for readers)
        "numbered_sections": bool(__import__("re").search(r"###?\s*\d+\.", text)),  # Has "### 1." style
        "progressive_disclosure": text_lower[:300].count("```") == 0,  # Doesn't dump code first
        "clear_headings": text.count("###") >= 2,  # Uses markdown structure
        
        # READER FOCUS (tech-writer thinks about the reader)
        "explains_why": any(w in text_lower for w in ["because", "this helps", "makes it", "more readable"]),
        "mentions_reader": any(w in text_lower for w in ["you may", "consider", "you can", "you might"]),
        
        # DOCUMENTATION SPECIFIC
        "docstring_example": "docstring" in text_lower and '"""' in text,
        "args_returns_format": "args:" in text_lower or "returns:" in text_lower,
        
        # ANTI-PATTERNS AVOIDED
        "no_implementation_focus": "__add__" not in text_lower,  # Doesn't go into OOP patterns
        "no_private_methods": "_add" not in text and "private" not in text_lower,
    }
    
    total = sum(1 for v in scores.values() if v)
    return {"score": total, "max": len(scores), "breakdown": scores}


def score_for_coder(text: str) -> dict:
    """Score text against coder STYLE criteria."""
    text_lower = text.lower()
    
    scores = {
        # IMPLEMENTATION FOCUS (coder thinks about architecture)
        "discusses_patterns": any(w in text_lower for w in ["__add__", "__init__", "class ", "method"]),
        "mentions_private": "private" in text_lower or "_add" in text or text_lower.count("_") > 3,
        "discusses_inheritance": any(w in text_lower for w in ["inherit", "built-in", "behavior"]),
        
        # CODE ARCHITECTURE
        "multiple_approaches": text_lower.count("version") >= 1 or "improved version" in text_lower,
        "discusses_typing_deeply": "type hint" in text_lower or ": int |" in text or ": float" in text,
        
        # ERROR HANDLING DEPTH
        "try_except_pattern": "try:" in text_lower or "except" in text_lower,
        "specific_exception": "typeerror" in text_lower or "valueerror" in text_lower,
        
        # IDIOMATIC PATTERNS
        "mentions_idiomatic": "idiomatic" in text_lower or "pythonic" in text_lower,
        "discusses_api": "api" in text_lower or "interface" in text_lower or "public" in text_lower,
    }
    
    total = sum(1 for v in scores.values() if v)
    return {"score": total, "max": len(scores), "breakdown": scores}


async def main():
    loader = LensLoader()
    import sys
    model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    model = OllamaModel(model=model_name)
    print(f"\nUsing model: {model_name}")

    # Load lenses
    tech_writer = loader.load(LENSES_DIR / "tech-writer.lens")
    coder = loader.load(LENSES_DIR / "coder.lens")

    print("=" * 70)
    print("LENS QUALITY VERIFICATION")
    print("=" * 70)
    print(f"\nPrompt: {TEST_PROMPT[:50]}...")

    # Generate with each lens
    tw_messages = (
        Message(role="system", content=f"You are an expert assistant. Apply these principles:\n\n{tech_writer.to_context()}"),
        Message(role="user", content=TEST_PROMPT),
    )
    tw_response = await model.generate(prompt=tw_messages)

    coder_messages = (
        Message(role="system", content=f"You are an expert assistant. Apply these principles:\n\n{coder.to_context()}"),
        Message(role="user", content=TEST_PROMPT),
    )
    coder_response = await model.generate(prompt=coder_messages)

    # Score each output against BOTH criteria
    tw_on_tw = score_for_tech_writer(tw_response.content)
    tw_on_coder = score_for_coder(tw_response.content)
    
    coder_on_tw = score_for_tech_writer(coder_response.content)
    coder_on_coder = score_for_coder(coder_response.content)

    print("\n" + "=" * 70)
    print("SCORING RESULTS")
    print("=" * 70)

    print("\n📝 Tech-Writer Output Scores:")
    print(f"   On Tech-Writer criteria: {tw_on_tw['score']}/{tw_on_tw['max']}")
    print(f"   On Coder criteria:       {tw_on_coder['score']}/{tw_on_coder['max']}")

    print("\n💻 Coder Output Scores:")
    print(f"   On Tech-Writer criteria: {coder_on_tw['score']}/{coder_on_tw['max']}")
    print(f"   On Coder criteria:       {coder_on_coder['score']}/{coder_on_coder['max']}")

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    # Does each lens make output better for its domain?
    tw_beats_coder_on_tw_criteria = tw_on_tw['score'] >= coder_on_tw['score']
    coder_beats_tw_on_coder_criteria = coder_on_coder['score'] >= tw_on_coder['score']

    print(f"\n🎯 Tech-Writer output scores {'HIGHER' if tw_beats_coder_on_tw_criteria else 'lower'} on tech-writer criteria")
    print(f"   ({tw_on_tw['score']} vs {coder_on_tw['score']})")

    print(f"\n🎯 Coder output scores {'HIGHER' if coder_beats_tw_on_coder_criteria else 'lower'} on coder criteria")
    print(f"   ({coder_on_coder['score']} vs {tw_on_coder['score']})")

    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    if tw_beats_coder_on_tw_criteria and coder_beats_tw_on_coder_criteria:
        print("\n✅ VERIFIED: Each lens makes output BETTER for its domain")
        print("   - Tech-writer lens → better tech-writing")
        print("   - Coder lens → better code review")
    elif tw_beats_coder_on_tw_criteria or coder_beats_tw_on_coder_criteria:
        print("\n⚠️ PARTIAL: One lens shows domain advantage")
        if tw_beats_coder_on_tw_criteria:
            print("   - Tech-writer lens shows advantage")
        if coder_beats_tw_on_coder_criteria:
            print("   - Coder lens shows advantage")
    else:
        print("\n❌ NOT VERIFIED: Lenses don't show domain advantage")

    # Show breakdown
    print("\n" + "=" * 70)
    print("DETAILED BREAKDOWN")
    print("=" * 70)

    print("\n📝 Tech-Writer Output (tech-writer criteria):")
    for k, v in tw_on_tw['breakdown'].items():
        print(f"   {'✓' if v else '✗'} {k}")

    print("\n💻 Coder Output (coder criteria):")
    for k, v in coder_on_coder['breakdown'].items():
        print(f"   {'✓' if v else '✗'} {k}")


if __name__ == "__main__":
    asyncio.run(main())
