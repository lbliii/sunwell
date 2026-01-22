#!/usr/bin/env python3
"""Fish School AI: Can multiple tiny models self-correct through mutual observation?

Hypothesis: Like a school of fish, multiple 1B models observing each other's outputs
can collectively produce better results than any individual, through local correction rules.

Architecture:
1. N tiny models generate in parallel
2. After each "chunk", they see neighbors' outputs
3. Simple rules: If neighbor drifting → adjust your course
4. Collective output assembled from best chunks

Biological parallel:
- SEPARATION: Don't repeat what neighbor said
- ALIGNMENT: Stay on same topic as neighbors  
- COHESION: Converge toward consensus quality
"""

import asyncio
import sys

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


# Our school of fish (tiny models)
FISH_MODELS = [
    "gemma3:1b",
    "llama3.2:1b",
    "qwen2.5:1.5b",
]

TASK = "Write a Python function to fetch data from an API and handle errors gracefully"


FISH_PROMPT = """You are part of a team writing code together. 

Task: {task}

{neighbor_context}

Write your contribution (one focused paragraph or code block). Be concise and useful."""


NEIGHBOR_CONTEXT_TEMPLATE = """Your teammates have written:
---
{snippets}
---
Build on their work. Don't repeat what they said. Add something new and useful."""


JUDGE_PROMPT = """Rate this code/explanation. Give a score from 1-40.

Criteria:
- Does it show working code? (+10)
- Does it handle errors? (+10)
- Is it clear and readable? (+10)
- Is it concise without fluff? (+10)

Content:
---
{content}
---

Think step by step, then give your final score.
SCORE: [number]/40"""


async def fish_generate(model: OllamaModel, task: str, neighbor_outputs: list[str]) -> str:
    """Single fish generates, aware of neighbors."""
    if neighbor_outputs:
        snippets = "\n\n".join(f"Teammate {i+1}: {out[:200]}..." 
                               for i, out in enumerate(neighbor_outputs) if out)
        neighbor_context = NEIGHBOR_CONTEXT_TEMPLATE.format(snippets=snippets)
    else:
        neighbor_context = "You're starting. Set a good foundation."
    
    response = await model.generate(
        prompt=(Message(role="user", content=FISH_PROMPT.format(
            task=task,
            neighbor_context=neighbor_context
        )),)
    )
    return response.content


async def solo_generate(model: OllamaModel, task: str) -> str:
    """Single fish generates alone (baseline)."""
    response = await model.generate(
        prompt=(Message(role="user", content=f"Task: {task}\n\nWrite a complete solution:"),)
    )
    return response.content


async def judge(model: OllamaModel, content: str) -> int:
    """Judge rates the output."""
    import re
    
    response = await model.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(content=content)),)
    )
    
    # Extract score - look for patterns like "SCORE: 25/40" or just "25/40" or "Score: 25"
    text = response.content
    
    # Try SCORE: pattern first
    match = re.search(r'SCORE[:\s]+(\d+)', text, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 40)
    
    # Try X/40 pattern
    match = re.search(r'(\d+)/40', text)
    if match:
        return min(int(match.group(1)), 40)
    
    # Try any number after "total" or "score"
    match = re.search(r'(?:total|score)[:\s]+(\d+)', text, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 40)
    
    # Last resort: find largest number that's <= 40
    numbers = [int(n) for n in re.findall(r'\d+', text) if int(n) <= 40]
    if numbers:
        return max(numbers)
    
    return 20  # Default middle score


async def main():
    judge_model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    print("🐟 FISH SCHOOL AI EXPERIMENT 🐟")
    print("=" * 70)
    print(f"School members: {', '.join(FISH_MODELS)}")
    print(f"Judge: {judge_model_name}")
    print(f"Task: {TASK}")
    print("=" * 70)
    
    # Initialize models
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    judge_model = OllamaModel(model=judge_model_name)
    
    # =========================================================================
    # PHASE 1: Solo generation (baseline)
    # =========================================================================
    print("\n📍 PHASE 1: Solo Generation (each fish alone)")
    print("-" * 70)
    
    solo_outputs = []
    solo_scores = []
    
    for i, (f, name) in enumerate(zip(fish, FISH_MODELS)):
        print(f"  🐟 {name} generating solo...")
        output = await solo_generate(f, TASK)
        score = await judge(judge_model, output)
        solo_outputs.append(output)
        solo_scores.append(score)
        print(f"     Score: {score}/40")
        print(f"     Preview: {output[:100].replace(chr(10), ' ')}...")
    
    avg_solo = sum(solo_scores) / len(solo_scores)
    best_solo = max(solo_scores)
    print(f"\n  Solo average: {avg_solo:.1f}/40")
    print(f"  Solo best: {best_solo}/40")
    
    # =========================================================================
    # PHASE 2: School generation (fish see each other)
    # =========================================================================
    print("\n📍 PHASE 2: School Generation (fish see neighbors)")
    print("-" * 70)
    
    school_outputs = [""] * len(fish)
    
    # Round 1: Each fish generates, seeing nothing yet
    print("  Round 1: Initial generation...")
    tasks = [fish_generate(f, TASK, []) for f in fish]
    round1 = await asyncio.gather(*tasks)
    for i, out in enumerate(round1):
        school_outputs[i] = out
        print(f"    🐟 {FISH_MODELS[i]}: {len(out)} chars")
    
    # Round 2: Each fish generates, seeing round 1 outputs
    print("  Round 2: Seeing neighbors, adding more...")
    tasks = []
    for i, f in enumerate(fish):
        # Each fish sees OTHER fish's outputs (not its own)
        neighbors = [school_outputs[j] for j in range(len(fish)) if j != i]
        tasks.append(fish_generate(f, TASK, neighbors))
    
    round2 = await asyncio.gather(*tasks)
    for i, out in enumerate(round2):
        school_outputs[i] += "\n\n" + out
        print(f"    🐟 {FISH_MODELS[i]}: +{len(out)} chars")
    
    # Combine school outputs
    combined_school = "\n\n---\n\n".join(
        f"Contribution from {name}:\n{out}" 
        for name, out in zip(FISH_MODELS, school_outputs)
    )
    
    # Judge individual school outputs
    print("\n  Judging individual school contributions...")
    school_scores = []
    for i, out in enumerate(school_outputs):
        score = await judge(judge_model, out)
        school_scores.append(score)
        print(f"    🐟 {FISH_MODELS[i]}: {score}/40")
    
    avg_school = sum(school_scores) / len(school_scores)
    best_school = max(school_scores)
    
    # Judge combined output
    print("\n  Judging combined school output...")
    combined_score = await judge(judge_model, combined_school)
    print(f"    Combined: {combined_score}/40")
    
    # =========================================================================
    # RESULTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    print(f"\n{'Metric':<30} {'Solo':<15} {'School':<15} {'Change':<15}")
    print("-" * 70)
    print(f"{'Average individual':<30} {avg_solo:<15.1f} {avg_school:<15.1f} {'+' if avg_school > avg_solo else ''}{avg_school - avg_solo:.1f}")
    print(f"{'Best individual':<30} {best_solo:<15} {best_school:<15} {'+' if best_school > best_solo else ''}{best_school - best_solo}")
    print(f"{'Combined output':<30} {'N/A':<15} {combined_score:<15}")
    
    # Verdict
    print("\n" + "=" * 70)
    improvement = avg_school - avg_solo
    if improvement > 2:
        print(f"✅ SCHOOL EFFECT VERIFIED: +{improvement:.1f} points average improvement")
        print("   Fish seeing neighbors produced better individual outputs!")
    elif improvement > 0:
        print(f"⚠️  MARGINAL IMPROVEMENT: +{improvement:.1f} points")
        print("   School helped slightly, but effect is small")
    else:
        print(f"❌ NO SCHOOL EFFECT: {improvement:.1f} points")
        print("   Fish didn't benefit from seeing neighbors")
    
    if combined_score > best_solo:
        print(f"\n✅ COMBINED OUTPUT BEAT BEST SOLO: {combined_score} > {best_solo}")
        print("   The whole is greater than the sum of its parts!")


if __name__ == "__main__":
    asyncio.run(main())
