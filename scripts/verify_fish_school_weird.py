#!/usr/bin/env python3
"""Fish School: Weird Communication Experiments 🐟

Trying orthogonal, non-academic approaches to school coordination.

Experiments:
1. VIBE CHECK: Share emotional state, not content ("confident", "uncertain", "excited")
2. THREE WORDS: Compress entire output to 3 keywords, share those
3. CONTRARIAN: One fish deliberately argues the opposite to find blind spots
4. TEMPERATURE: If neighbor seems "hot" (verbose), you go "cold" (terse)
5. PHEROMONE: Leave single-word markers for next fish ("danger:errors", "safe:types")
"""

import asyncio
import sys
import random

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = [
    "gemma3:1b",
    "llama3.2:1b",
    "qwen2.5:1.5b",
]

TASK = "Write a Python function to reverse a string"


JUDGE_PROMPT = """Rate 1-40:
- Working code? (+10)
- Error handling? (+10)
- Clear? (+10)
- Concise? (+10)

{content}

SCORE:"""


async def judge(model: OllamaModel, content: str) -> int:
    import re
    response = await model.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(content=content)),)
    )
    text = response.content
    match = re.search(r'(\d+)', text)
    if match:
        return min(int(match.group(1)), 40)
    return 20


async def solo_baseline(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """Get baseline solo scores."""
    scores = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite solution:"),)
        )
        score = await judge(judge_model, response.content)
        scores.append(score)
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# EXPERIMENT 1: VIBE CHECK
# Fish share emotional state, not content
# =============================================================================
async def experiment_vibe_check(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """Fish share vibes: confident, uncertain, struggling, excited."""
    print("\n  🎭 VIBE CHECK: Sharing emotional state...")
    
    # Round 1: Generate and extract vibe
    outputs = []
    vibes = []
    
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite solution:"),)
        )
        outputs.append(response.content)
        
        # Extract vibe
        vibe_response = await f.generate(
            prompt=(Message(role="user", content=f"""How do you feel about this solution? One word only:
- confident (it's solid)
- uncertain (might have issues)  
- struggling (this is hard)
- excited (found something cool)

Your solution: {response.content[:200]}...

Your vibe:"""),)
        )
        vibe = vibe_response.content.strip().lower().split()[0] if vibe_response.content else "uncertain"
        vibes.append(vibe)
        print(f"    🐟 {name}: {vibe}")
    
    # Round 2: Generate with vibe context
    print("  Round 2: Regenerating with vibe awareness...")
    vibe_summary = ", ".join(f"Fish {i+1} is {v}" for i, v in enumerate(vibes))
    
    final_outputs = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"""Task: {TASK}

Team vibes: {vibe_summary}

If teammates are uncertain, add more error handling.
If teammates are confident, keep it concise.
If teammates are struggling, simplify.

Write your solution:"""),)
        )
        final_outputs.append(response.content)
    
    scores = [await judge(judge_model, out) for out in final_outputs]
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# EXPERIMENT 2: THREE WORDS
# Compress entire output to 3 keywords
# =============================================================================
async def experiment_three_words(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """Fish share 3-word summaries only."""
    print("\n  📝 THREE WORDS: Extreme compression...")
    
    # Round 1: Generate and compress
    outputs = []
    keywords = []
    
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite solution:"),)
        )
        outputs.append(response.content)
        
        # Compress to 3 words
        compress_response = await f.generate(
            prompt=(Message(role="user", content=f"""Summarize this code in EXACTLY 3 words (what it does):

{response.content[:300]}

Three words:"""),)
        )
        kw = compress_response.content.strip()[:50]
        keywords.append(kw)
        print(f"    🐟 {name}: '{kw}'")
    
    # Round 2: Generate with keyword hints
    print("  Round 2: Regenerating with keyword hints...")
    hint = " | ".join(keywords)
    
    final_outputs = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"""Task: {TASK}

Team hints: {hint}

Combine these ideas into one solution:"""),)
        )
        final_outputs.append(response.content)
    
    scores = [await judge(judge_model, out) for out in final_outputs]
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# EXPERIMENT 3: CONTRARIAN FISH
# One fish deliberately argues the opposite
# =============================================================================
async def experiment_contrarian(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """One fish plays devil's advocate."""
    print("\n  😈 CONTRARIAN: One fish argues the opposite...")
    
    # Fish 1 generates normally
    response1 = await fish[0].generate(
        prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite solution:"),)
    )
    print(f"    🐟 {FISH_MODELS[0]}: Normal solution")
    
    # Fish 2 critiques it
    critique = await fish[1].generate(
        prompt=(Message(role="user", content=f"""This solution has problems. Find 3 issues:

{response1.content[:400]}

Issues:"""),)
    )
    print(f"    😈 {FISH_MODELS[1]}: Critique - {critique.content[:80]}...")
    
    # Fish 3 synthesizes: original + critique = improved
    final = await fish[2].generate(
        prompt=(Message(role="user", content=f"""Task: {TASK}

Original attempt:
{response1.content[:300]}

Critique:
{critique.content[:200]}

Write an improved solution that addresses the critique:"""),)
    )
    print(f"    🐟 {FISH_MODELS[2]}: Synthesized improvement")
    
    score = await judge(judge_model, final.content)
    return score, score  # Only one output


# =============================================================================
# EXPERIMENT 4: TEMPERATURE BALANCING
# If neighbor is verbose, you go terse (and vice versa)
# =============================================================================
async def experiment_temperature(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """Fish balance each other's verbosity."""
    print("\n  🌡️ TEMPERATURE: Balancing verbosity...")
    
    # Round 1: Generate freely
    outputs = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite solution:"),)
        )
        outputs.append(response.content)
        temp = "HOT 🔥" if len(response.content) > 1500 else "COLD ❄️" if len(response.content) < 500 else "WARM 🌤️"
        print(f"    🐟 {name}: {len(response.content)} chars ({temp})")
    
    avg_len = sum(len(o) for o in outputs) / len(outputs)
    
    # Round 2: Balance temperatures
    print(f"  Average length: {avg_len:.0f} chars")
    print("  Round 2: Balancing temperatures...")
    
    final_outputs = []
    for i, (f, name) in enumerate(zip(fish, FISH_MODELS)):
        my_len = len(outputs[i])
        if my_len > avg_len * 1.3:
            instruction = "Your previous answer was too verbose. Rewrite MORE CONCISELY (fewer words)."
        elif my_len < avg_len * 0.7:
            instruction = "Your previous answer was too brief. Add MORE DETAIL (error handling, examples)."
        else:
            instruction = "Your length was good. Refine but keep similar length."
        
        response = await f.generate(
            prompt=(Message(role="user", content=f"""Task: {TASK}

{instruction}

Your solution:"""),)
        )
        final_outputs.append(response.content)
        print(f"    🐟 {name}: {len(response.content)} chars")
    
    scores = [await judge(judge_model, out) for out in final_outputs]
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# EXPERIMENT 5: PHEROMONE TRAILS
# Leave single-word markers for next fish
# =============================================================================
async def experiment_pheromone(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """Fish leave pheromone markers for each other."""
    print("\n  🐜 PHEROMONE: Leaving trail markers...")
    
    pheromones = []
    outputs = []
    
    # Fish generate in sequence, each leaving a pheromone
    for i, (f, name) in enumerate(zip(fish, FISH_MODELS)):
        trail = " → ".join(pheromones) if pheromones else "(you're first)"
        
        response = await f.generate(
            prompt=(Message(role="user", content=f"""Task: {TASK}

Trail from previous fish: {trail}

Write solution. At the end, leave ONE WORD for the next fish indicating what you focused on 
(e.g., "errors", "types", "async", "simple", "robust"):"""),)
        )
        
        outputs.append(response.content)
        
        # Extract pheromone (last word or keyword)
        pheromone = response.content.strip().split()[-1][:15] if response.content else "code"
        pheromones.append(pheromone)
        print(f"    🐟 {name}: left marker '{pheromone}'")
    
    print(f"  Final trail: {' → '.join(pheromones)}")
    
    scores = [await judge(judge_model, out) for out in outputs]
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# MAIN
# =============================================================================
async def main():
    judge_model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    print("🐟 FISH SCHOOL: WEIRD EXPERIMENTS 🐟")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    judge_model = OllamaModel(model=judge_model_name)
    
    # Baseline
    print("\n📍 BASELINE: Solo generation")
    print("-" * 70)
    baseline_avg, baseline_best = await solo_baseline(fish, judge_model)
    print(f"  Solo: avg={baseline_avg:.1f}/40, best={baseline_best}/40")
    
    # Run experiments
    experiments = [
        ("VIBE CHECK", experiment_vibe_check),
        ("THREE WORDS", experiment_three_words),
        ("CONTRARIAN", experiment_contrarian),
        ("TEMPERATURE", experiment_temperature),
        ("PHEROMONE", experiment_pheromone),
    ]
    
    results = []
    for name, func in experiments:
        print(f"\n📍 EXPERIMENT: {name}")
        print("-" * 70)
        try:
            avg, best = await func(fish, judge_model)
            results.append((name, avg, best))
            print(f"\n  Result: avg={avg:.1f}/40, best={best}/40")
        except Exception as e:
            print(f"\n  ❌ Failed: {e}")
            results.append((name, 0, 0))
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 SUMMARY")
    print("=" * 70)
    
    print(f"\n{'Experiment':<20} {'Avg':<10} {'Best':<10} {'vs Baseline':<15}")
    print("-" * 55)
    print(f"{'Solo (baseline)':<20} {baseline_avg:<10.1f} {baseline_best:<10}")
    
    for name, avg, best in results:
        diff = avg - baseline_avg
        indicator = "✅" if diff > 2 else "➖" if diff > -2 else "❌"
        print(f"{name:<20} {avg:<10.1f} {best:<10} {indicator} {'+' if diff > 0 else ''}{diff:.1f}")
    
    # Find winner
    best_exp = max(results, key=lambda x: x[1])
    print(f"\n🏆 Best approach: {best_exp[0]} ({best_exp[1]:.1f}/40)")
    
    if best_exp[1] > baseline_avg:
        print(f"   Beat baseline by +{best_exp[1] - baseline_avg:.1f} points!")
    else:
        print(f"   Baseline solo still wins by {baseline_avg - best_exp[1]:.1f} points")


if __name__ == "__main__":
    asyncio.run(main())
