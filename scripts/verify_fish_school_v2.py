#!/usr/bin/env python3
"""Fish School v2: Signal-based coordination (like real fish)

Key insight: Real fish don't share "thoughts" — they share MOVEMENT SIGNALS.
- Fish sees neighbor turn → turns too
- Fish doesn't read neighbor's mind

New approach:
1. All fish generate independently
2. Monitor classifies each: on_track or drifting
3. If ANY fish is drifting → send correction signal to ALL
4. Fish that were on_track reinforce, drifters correct
5. Best output selected (not combined)
"""

import asyncio
import sys

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = [
    "gemma3:1b",
    "llama3.2:1b",
    "qwen2.5:1.5b",
]

TASK = "Write a Python function to fetch data from an API and handle errors gracefully"


CLASSIFY_PROMPT = """Classify this code output (one word):
- on_track: Shows working code, handles errors, concise
- drifting: Too much explanation, missing error handling, or off-topic

Output:
{output}

Classification:"""


CORRECTION_SIGNAL = """SIGNAL: Some team members are drifting off-track.
Focus on: working code, error handling, conciseness.
No lengthy explanations. Show the code first."""


FISH_PROMPT_INITIAL = """Task: {task}

Write a focused solution. Code first, brief explanation after."""


FISH_PROMPT_CORRECTED = """Task: {task}

{signal}

Write a focused solution. Code first, brief explanation after."""


JUDGE_PROMPT = """Rate this code 1-40:
- Working code? (+10)
- Error handling? (+10)  
- Clear? (+10)
- Concise? (+10)

Code:
{content}

SCORE:"""


async def judge(model: OllamaModel, content: str) -> int:
    """Judge rates the output."""
    import re
    
    response = await model.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(content=content)),)
    )
    
    text = response.content
    
    # Try to find score
    match = re.search(r'SCORE[:\s]*(\d+)', text, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 40)
    
    match = re.search(r'(\d+)/40', text)
    if match:
        return min(int(match.group(1)), 40)
    
    numbers = [int(n) for n in re.findall(r'\d+', text) if int(n) <= 40]
    if numbers:
        return max(numbers)
    
    return 20


async def classify(model: OllamaModel, output: str) -> str:
    """Classify if output is on_track or drifting."""
    response = await model.generate(
        prompt=(Message(role="user", content=CLASSIFY_PROMPT.format(output=output[:500])),)
    )
    
    text = response.content.lower()
    if "drift" in text:
        return "drifting"
    return "on_track"


async def main():
    judge_model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    print("🐟 FISH SCHOOL v2: Signal-Based Coordination 🐟")
    print("=" * 70)
    print(f"School: {', '.join(FISH_MODELS)}")
    print(f"Judge: {judge_model_name}")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    judge_model = OllamaModel(model=judge_model_name)
    monitor = OllamaModel(model="llama3.2:3b")  # Use 3B as monitor
    
    # =========================================================================
    # PHASE 1: Solo baseline
    # =========================================================================
    print("\n📍 PHASE 1: Solo Generation (baseline)")
    print("-" * 70)
    
    solo_outputs = []
    solo_scores = []
    
    for f, name in zip(fish, FISH_MODELS):
        print(f"  🐟 {name}...")
        response = await f.generate(
            prompt=(Message(role="user", content=FISH_PROMPT_INITIAL.format(task=TASK)),)
        )
        output = response.content
        score = await judge(judge_model, output)
        solo_outputs.append(output)
        solo_scores.append(score)
        print(f"     Score: {score}/40")
    
    avg_solo = sum(solo_scores) / len(solo_scores)
    best_solo = max(solo_scores)
    best_solo_idx = solo_scores.index(best_solo)
    print(f"\n  Average: {avg_solo:.1f}/40, Best: {best_solo}/40 ({FISH_MODELS[best_solo_idx]})")
    
    # =========================================================================
    # PHASE 2: School with signal coordination
    # =========================================================================
    print("\n📍 PHASE 2: School with Signal Coordination")
    print("-" * 70)
    
    # Round 1: Generate
    print("  Round 1: Initial generation...")
    round1_outputs = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=FISH_PROMPT_INITIAL.format(task=TASK)),)
        )
        round1_outputs.append(response.content)
        print(f"    🐟 {name}: {len(response.content)} chars")
    
    # Classify each fish's output
    print("\n  Classifying outputs...")
    classifications = []
    for i, output in enumerate(round1_outputs):
        cls = await classify(monitor, output)
        classifications.append(cls)
        print(f"    🐟 {FISH_MODELS[i]}: {cls}")
    
    # Check if any fish is drifting
    drifters = sum(1 for c in classifications if c == "drifting")
    
    if drifters > 0:
        print(f"\n  ⚠️  {drifters}/{len(fish)} fish drifting! Sending correction signal...")
        
        # Round 2: All fish regenerate with correction signal
        print("  Round 2: Regenerating with correction signal...")
        school_outputs = []
        for f, name in zip(fish, FISH_MODELS):
            response = await f.generate(
                prompt=(Message(role="user", content=FISH_PROMPT_CORRECTED.format(
                    task=TASK,
                    signal=CORRECTION_SIGNAL
                )),)
            )
            school_outputs.append(response.content)
            print(f"    🐟 {name}: {len(response.content)} chars")
    else:
        print(f"\n  ✓ All fish on_track! No correction needed.")
        school_outputs = round1_outputs
    
    # Judge school outputs
    print("\n  Judging school outputs...")
    school_scores = []
    for i, output in enumerate(school_outputs):
        score = await judge(judge_model, output)
        school_scores.append(score)
        print(f"    🐟 {FISH_MODELS[i]}: {score}/40")
    
    avg_school = sum(school_scores) / len(school_scores)
    best_school = max(school_scores)
    best_school_idx = school_scores.index(best_school)
    
    # =========================================================================
    # RESULTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    print(f"\n{'Metric':<25} {'Solo':<12} {'School':<12} {'Change':<12}")
    print("-" * 60)
    print(f"{'Average':<25} {avg_solo:<12.1f} {avg_school:<12.1f} {'+' if avg_school > avg_solo else ''}{avg_school - avg_solo:.1f}")
    print(f"{'Best individual':<25} {best_solo:<12} {best_school:<12} {'+' if best_school > best_solo else ''}{best_school - best_solo}")
    print(f"{'Best model (solo)':<25} {FISH_MODELS[best_solo_idx]}")
    print(f"{'Best model (school)':<25} {FISH_MODELS[best_school_idx]}")
    
    improvement = avg_school - avg_solo
    print("\n" + "=" * 70)
    if improvement > 1:
        print(f"✅ SCHOOL SIGNAL EFFECT: +{improvement:.1f} points")
        print("   Correction signal improved drifting fish!")
    elif improvement > -1:
        print(f"➖ NEUTRAL: {improvement:.1f} points")
        print("   Signal coordination had minimal effect")
    else:
        print(f"❌ SIGNAL HURT: {improvement:.1f} points")


if __name__ == "__main__":
    asyncio.run(main())
