#!/usr/bin/env python3
"""Twitch Plays Code: Multiple tiny models collectively write code one step at a time.

Inspired by Twitch Plays Pokemon — thousands of people voting on next move.

Modes:
1. DEMOCRACY: Each fish proposes next line, majority vote wins
2. ANARCHY: Random fish writes next line (chaos mode)
3. CONSENSUS: Only proceed if all fish agree on direction

The key insight: Even with "dumb" individual moves, collective progress emerges.
"""

import asyncio
import sys
import random
from collections import Counter

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


FISH_MODELS = [
    "gemma3:1b",
    "llama3.2:1b",  
    "qwen2.5:1.5b",
]

TASK = "Write a Python function to reverse a string"

MAX_LINES = 8  # Build code line by line


NEXT_LINE_PROMPT = """Continue this Python code. Write ONLY ONE LINE.

Task: {task}

```python
{code_so_far}
```

Write the next line (just code, no explanation). If the function is complete, write DONE."""


VOTE_PROMPT = """Which line is better for this code? Reply with just A or B.

Task: {task}

Code so far:
```python
{code_so_far}
```

Option A: {option_a}
Option B: {option_b}

Better option (A or B):"""


JUDGE_PROMPT = """Rate this code 1-40:
- Correct? (+10)
- Complete? (+10)
- Clear? (+10)
- Concise? (+10)

```python
{code}
```

SCORE:"""


async def judge(model: OllamaModel, code: str) -> int:
    import re
    response = await model.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(code=code)),)
    )
    match = re.search(r'(\d+)', response.content)
    return min(int(match.group(1)), 40) if match else 20


async def get_next_line(model: OllamaModel, task: str, code_so_far: str) -> str:
    """Ask a fish for the next line of code."""
    response = await model.generate(
        prompt=(Message(role="user", content=NEXT_LINE_PROMPT.format(
            task=task,
            code_so_far=code_so_far or "# Start here"
        )),)
    )
    
    # Extract just the line (not explanation)
    text = response.content.strip()
    
    # If it contains "DONE", we're finished
    if "DONE" in text.upper():
        return "DONE"
    
    # Get first non-empty line that looks like code
    for line in text.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('```'):
            # Remove markdown artifacts
            line = line.replace('`', '').strip()
            if line:
                return line
    
    return text.split('\n')[0].strip()


# =============================================================================
# MODE 1: DEMOCRACY - Vote on each line
# =============================================================================
async def mode_democracy(fish: list, judge_model: OllamaModel) -> tuple[str, int]:
    """Fish vote on each line. Majority wins."""
    print("\n  🗳️ DEMOCRACY MODE: Voting on each line...")
    
    code_lines = []
    
    for step in range(MAX_LINES):
        code_so_far = '\n'.join(code_lines)
        
        # Each fish proposes a line
        proposals = []
        for f, name in zip(fish, FISH_MODELS):
            line = await get_next_line(f, TASK, code_so_far)
            proposals.append(line)
            print(f"    [{step+1}] 🐟 {name}: {line[:50]}")
        
        # Check if any fish says DONE (but need at least 2 lines)
        if any("DONE" in p.upper() for p in proposals) and len(code_lines) >= 2:
            print(f"    [{step+1}] 🏁 Fish voted DONE (after {len(code_lines)} lines)")
            break
        elif any("DONE" in p.upper() for p in proposals):
            print(f"    [{step+1}] ⏳ Fish want DONE but need more lines, ignoring...")
            # Remove DONE proposals and pick from rest
            proposals = [p for p in proposals if "DONE" not in p.upper()]
            if not proposals:
                continue
        
        # Vote: most common proposal wins (simple majority)
        # Normalize proposals for comparison
        normalized = [p.strip().lower() for p in proposals]
        winner_idx = 0
        
        # If all different, pick randomly
        if len(set(normalized)) == len(normalized):
            winner_idx = random.randint(0, len(proposals) - 1)
            print(f"    [{step+1}] 🎲 No majority, random pick: {FISH_MODELS[winner_idx]}")
        else:
            # Find most common
            counts = Counter(normalized)
            most_common = counts.most_common(1)[0][0]
            winner_idx = normalized.index(most_common)
            print(f"    [{step+1}] ✓ Majority: {proposals[winner_idx][:40]}")
        
        code_lines.append(proposals[winner_idx])
    
    final_code = '\n'.join(code_lines)
    print(f"\n  Final code ({len(code_lines)} lines):")
    for line in code_lines:
        print(f"    {line}")
    
    score = await judge(judge_model, final_code)
    return final_code, score


# =============================================================================
# MODE 2: ANARCHY - Random fish writes each line
# =============================================================================
async def mode_anarchy(fish: list, judge_model: OllamaModel) -> tuple[str, int]:
    """Random fish writes each line. Pure chaos."""
    print("\n  🔥 ANARCHY MODE: Random fish each turn...")
    
    code_lines = []
    
    for step in range(MAX_LINES):
        code_so_far = '\n'.join(code_lines)
        
        # Random fish writes
        idx = random.randint(0, len(fish) - 1)
        f = fish[idx]
        name = FISH_MODELS[idx]
        
        line = await get_next_line(f, TASK, code_so_far)
        print(f"    [{step+1}] 🐟 {name}: {line[:50]}")
        
        if "DONE" in line.upper():
            print(f"    [{step+1}] 🏁 Fish says DONE")
            break
        
        code_lines.append(line)
    
    final_code = '\n'.join(code_lines)
    print(f"\n  Final code ({len(code_lines)} lines):")
    for line in code_lines:
        print(f"    {line}")
    
    score = await judge(judge_model, final_code)
    return final_code, score


# =============================================================================
# MODE 3: RELAY - Each fish writes one line in sequence
# =============================================================================
async def mode_relay(fish: list, judge_model: OllamaModel) -> tuple[str, int]:
    """Fish take turns in order. Like a relay race."""
    print("\n  🏃 RELAY MODE: Fish take turns in sequence...")
    
    code_lines = []
    
    for step in range(MAX_LINES):
        code_so_far = '\n'.join(code_lines)
        
        # Rotate through fish
        idx = step % len(fish)
        f = fish[idx]
        name = FISH_MODELS[idx]
        
        line = await get_next_line(f, TASK, code_so_far)
        print(f"    [{step+1}] 🐟 {name}: {line[:50]}")
        
        if "DONE" in line.upper():
            print(f"    [{step+1}] 🏁 Fish says DONE")
            break
        
        code_lines.append(line)
    
    final_code = '\n'.join(code_lines)
    print(f"\n  Final code ({len(code_lines)} lines):")
    for line in code_lines:
        print(f"    {line}")
    
    score = await judge(judge_model, final_code)
    return final_code, score


# =============================================================================
# BASELINE: Single fish writes everything
# =============================================================================
async def solo_baseline(fish: list, judge_model: OllamaModel) -> tuple[float, int]:
    """Each fish writes complete solution alone."""
    scores = []
    for f, name in zip(fish, FISH_MODELS):
        response = await f.generate(
            prompt=(Message(role="user", content=f"Task: {TASK}\n\nWrite the complete function:"),)
        )
        score = await judge(judge_model, response.content)
        scores.append(score)
    return sum(scores) / len(scores), max(scores)


# =============================================================================
# MAIN
# =============================================================================
async def main():
    judge_model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    
    print("🎮 TWITCH PLAYS CODE 🎮")
    print("=" * 70)
    print(f"Players: {', '.join(FISH_MODELS)}")
    print(f"Task: {TASK}")
    print("=" * 70)
    
    fish = [OllamaModel(model=name) for name in FISH_MODELS]
    judge_model = OllamaModel(model=judge_model_name)
    
    # Baseline
    print("\n📍 BASELINE: Solo generation")
    print("-" * 70)
    baseline_avg, baseline_best = await solo_baseline(fish, judge_model)
    print(f"  Solo: avg={baseline_avg:.1f}/40, best={baseline_best}/40")
    
    # Run modes
    results = []
    
    print("\n📍 MODE: DEMOCRACY")
    print("-" * 70)
    _, score = await mode_democracy(fish, judge_model)
    results.append(("DEMOCRACY", score))
    print(f"  Score: {score}/40")
    
    print("\n📍 MODE: ANARCHY")
    print("-" * 70)
    _, score = await mode_anarchy(fish, judge_model)
    results.append(("ANARCHY", score))
    print(f"  Score: {score}/40")
    
    print("\n📍 MODE: RELAY")
    print("-" * 70)
    _, score = await mode_relay(fish, judge_model)
    results.append(("RELAY", score))
    print(f"  Score: {score}/40")
    
    # Summary
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    print(f"\n{'Mode':<15} {'Score':<10} {'vs Solo Best':<15}")
    print("-" * 40)
    print(f"{'Solo (best)':<15} {baseline_best:<10}")
    
    for name, score in results:
        diff = score - baseline_best
        indicator = "✅" if diff > 0 else "➖" if diff >= -5 else "❌"
        print(f"{name:<15} {score:<10} {indicator} {'+' if diff > 0 else ''}{diff}")
    
    # Winner
    best_mode = max(results, key=lambda x: x[1])
    print(f"\n🏆 Best collective mode: {best_mode[0]} ({best_mode[1]}/40)")
    
    if best_mode[1] > baseline_best:
        print("   🎉 COLLECTIVE BEATS SOLO!")
    elif best_mode[1] >= baseline_best - 5:
        print("   ➖ Collective roughly matches solo")
    else:
        print("   Solo still wins")


if __name__ == "__main__":
    asyncio.run(main())
