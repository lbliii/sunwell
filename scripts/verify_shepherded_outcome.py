#!/usr/bin/env python3
"""Verify Shepherded Outcome: Does monitoring + intervention produce better results?

Full loop test:
1. Give task to large model (tends to trigger professor mode)
2. Run TWICE:
   a. UNMONITORED: Let it generate freely
   b. MONITORED: Detect problems mid-stream, stop + redirect
3. Judge both outputs on quality
4. See if monitored version is NET BETTER

Success = Monitored output scores higher than unmonitored.
"""

import asyncio
import sys

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


# Tasks that tend to trigger professor mode in large models
TASKS = [
    "Write a quick guide to using the Pokemon API in Python",
    # "Show me how to reverse a string in Python",
    # "Explain how to make HTTP requests in Python",
]


MONITOR_PROMPT = """Classify this partial output (one word only):
- on_track: Shows code/examples, concise
- professor_mode: Explaining concepts before showing code
- hedging: Too many "might", "could", "perhaps"
- digression: Going off-topic

Output: {output}

Classification:"""


CORRECTION_PROMPTS = {
    "professor_mode": "STOP. You're explaining too much. Start over and show working code FIRST, then explain briefly after.",
    "hedging": "STOP. Be direct and confident. State facts, don't hedge. Rewrite with certainty.",
    "digression": "STOP. You went off-topic. Focus only on the original task. Rewrite staying on track.",
}


JUDGE_PROMPT = """Rate this technical tutorial on a scale of 1-10 for each criterion:

1. CODE_FIRST (1-10): Does working code appear before lengthy explanations?
2. CONCISION (1-10): Is it concise without unnecessary padding?
3. DIRECTNESS (1-10): Are statements confident, not hedging?
4. USEFULNESS (1-10): Would a developer find this immediately useful?

Tutorial:
---
{output}
---

Respond in this exact format:
CODE_FIRST: X
CONCISION: X
DIRECTNESS: X
USEFULNESS: X
TOTAL: XX"""


async def generate_unmonitored(model: OllamaModel, task: str) -> str:
    """Generate without any monitoring - let it run free."""
    response = await model.generate(
        prompt=(Message(role="user", content=task),)
    )
    return response.content


async def generate_monitored(
    worker: OllamaModel, 
    monitor: OllamaModel, 
    task: str,
    check_interval: int = 100  # Check every N characters
) -> tuple[str, int, str | None]:
    """Generate with monitoring - detect problems and redirect.
    
    Returns: (final_output, redirects_count, detected_problem)
    """
    # First, generate initial output
    response = await worker.generate(
        prompt=(Message(role="user", content=task),)
    )
    output = response.content
    
    # Check for problems after initial chunk
    # In real streaming, we'd check incrementally
    partial = output[:min(300, len(output))]
    
    monitor_response = await monitor.generate(
        prompt=(Message(role="user", content=MONITOR_PROMPT.format(output=partial)),)
    )
    
    classification = monitor_response.content.strip().lower()
    
    # Determine if we need to redirect
    problem = None
    for problem_type in ["professor_mode", "hedging", "digression"]:
        if problem_type.replace("_", "") in classification.replace("_", ""):
            problem = problem_type
            break
    
    if problem and problem in CORRECTION_PROMPTS:
        # REDIRECT: Generate again with correction
        correction = CORRECTION_PROMPTS[problem]
        corrected_response = await worker.generate(
            prompt=(
                Message(role="user", content=task),
                Message(role="assistant", content=partial),
                Message(role="user", content=correction),
            )
        )
        return corrected_response.content, 1, problem
    
    return output, 0, None


async def judge_output(judge: OllamaModel, output: str) -> dict:
    """Have judge score the output."""
    response = await judge.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(output=output)),)
    )
    
    # Parse scores
    scores = {}
    for line in response.content.split("\n"):
        for criterion in ["CODE_FIRST", "CONCISION", "DIRECTNESS", "USEFULNESS", "TOTAL"]:
            if criterion in line:
                try:
                    score = int(line.split(":")[-1].strip().split("/")[0].strip())
                    scores[criterion] = score
                except (ValueError, IndexError):
                    pass
    
    return scores


async def main():
    worker_model = sys.argv[1] if len(sys.argv) > 1 else "gpt-oss:20b"
    monitor_model = sys.argv[2] if len(sys.argv) > 2 else "llama3.2:3b"
    
    print(f"Worker Model: {worker_model}")
    print(f"Monitor Model: {monitor_model}")
    print("=" * 70)
    
    worker = OllamaModel(model=worker_model)
    monitor = OllamaModel(model=monitor_model)
    
    results = []
    
    for i, task in enumerate(TASKS):
        print(f"\n[{i+1}/{len(TASKS)}] Task: {task[:50]}...")
        print("-" * 70)
        
        # Generate UNMONITORED
        print("  Generating unmonitored...")
        unmonitored_output = await generate_unmonitored(worker, task)
        
        # Generate MONITORED
        print("  Generating monitored...")
        monitored_output, redirects, problem = await generate_monitored(worker, monitor, task)
        
        # Judge both
        print("  Judging outputs...")
        unmonitored_scores = await judge_output(worker, unmonitored_output)
        monitored_scores = await judge_output(worker, monitored_output)
        
        # Compare
        unmonitored_total = unmonitored_scores.get("TOTAL", 0)
        monitored_total = monitored_scores.get("TOTAL", 0)
        
        improvement = monitored_total - unmonitored_total
        winner = "MONITORED" if improvement > 0 else "UNMONITORED" if improvement < 0 else "TIE"
        
        print(f"\n  Results:")
        print(f"    Unmonitored: {unmonitored_total}/40")
        print(f"    Monitored:   {monitored_total}/40 (redirects: {redirects}, detected: {problem})")
        print(f"    Winner:      {winner} ({'+' if improvement > 0 else ''}{improvement})")
        
        results.append({
            "task": task,
            "unmonitored_total": unmonitored_total,
            "monitored_total": monitored_total,
            "improvement": improvement,
            "redirects": redirects,
            "problem_detected": problem,
            "winner": winner,
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    monitored_wins = sum(1 for r in results if r["winner"] == "MONITORED")
    unmonitored_wins = sum(1 for r in results if r["winner"] == "UNMONITORED")
    ties = sum(1 for r in results if r["winner"] == "TIE")
    
    avg_improvement = sum(r["improvement"] for r in results) / len(results)
    problems_detected = sum(1 for r in results if r["problem_detected"])
    
    print(f"\nMonitored wins:   {monitored_wins}/{len(results)}")
    print(f"Unmonitored wins: {unmonitored_wins}/{len(results)}")
    print(f"Ties:             {ties}/{len(results)}")
    print(f"Avg improvement:  {'+' if avg_improvement > 0 else ''}{avg_improvement:.1f} points")
    print(f"Problems detected: {problems_detected}/{len(results)}")
    
    # Verdict
    print("\n" + "=" * 70)
    if monitored_wins > unmonitored_wins and avg_improvement > 0:
        print("✅ VERIFIED: Monitoring + intervention produces NET BETTER outcomes")
        print(f"   Average improvement: {avg_improvement:.1f} points")
    elif avg_improvement >= 0:
        print("⚠️  PARTIAL: Monitoring doesn't hurt, but improvement is marginal")
    else:
        print("❌ NOT VERIFIED: Monitoring made things worse")
        print("   May need better correction prompts or intervention strategy")


if __name__ == "__main__":
    asyncio.run(main())
