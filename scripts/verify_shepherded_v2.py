#!/usr/bin/env python3
"""Verify Shepherded Outcome v2: Does intervention improve the SAME output?

Better test design:
1. Generate output from large model
2. Check if it has a problem
3. IF problem detected: generate corrected version
4. Compare ORIGINAL vs CORRECTED (not two independent generations)

This isolates the intervention effect.
"""

import asyncio
import sys

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


TASK = "Explain the concept of dependency injection and show me how to implement it in Python"


MONITOR_PROMPT = """Classify this output (one word only):
- on_track: Shows code early, concise, practical
- professor_mode: Explains concepts before showing code, academic
- hedging: Uses "might", "could", "perhaps" too much
- digression: Goes off-topic

Output:
{output}

Classification:"""


CORRECTION_PROMPT = """The previous response had a problem: {problem}

For "{problem}":
- professor_mode: You explained too much before showing code. Rewrite showing code FIRST.
- hedging: You were too uncertain. Rewrite with confident, direct statements.
- digression: You went off-topic. Rewrite staying focused on the original task.

Original task: {task}

Rewrite the response, fixing the problem:"""


JUDGE_PROMPT = """Rate this technical tutorial 1-10 for each:

1. CODE_FIRST: Does code appear before lengthy explanations?
2. CONCISION: Is it concise?
3. DIRECTNESS: Confident statements, no hedging?
4. USEFULNESS: Immediately useful to a developer?

Tutorial:
---
{output}
---

Format:
CODE_FIRST: X
CONCISION: X  
DIRECTNESS: X
USEFULNESS: X
TOTAL: XX"""


async def judge(model: OllamaModel, output: str) -> int:
    """Score an output."""
    response = await model.generate(
        prompt=(Message(role="user", content=JUDGE_PROMPT.format(output=output)),)
    )
    
    for line in response.content.split("\n"):
        if "TOTAL:" in line:
            try:
                return int(line.split(":")[-1].strip().split("/")[0].strip())
            except:
                pass
    return 0


async def main():
    worker_model = sys.argv[1] if len(sys.argv) > 1 else "gpt-oss:20b"
    monitor_model = sys.argv[2] if len(sys.argv) > 2 else "llama3.2:3b"
    
    print(f"Worker: {worker_model}")
    print(f"Monitor: {monitor_model}")
    print(f"Task: {TASK}")
    print("=" * 70)
    
    worker = OllamaModel(model=worker_model)
    monitor = OllamaModel(model=monitor_model)
    
    # Step 1: Generate initial output
    print("\n1. Generating initial output...")
    initial_response = await worker.generate(
        prompt=(Message(role="user", content=TASK),)
    )
    initial_output = initial_response.content
    print(f"   Length: {len(initial_output)} chars")
    print(f"   Preview: {initial_output[:200]}...")
    
    # Step 2: Monitor classifies
    print("\n2. Monitor classifying...")
    monitor_response = await monitor.generate(
        prompt=(Message(role="user", content=MONITOR_PROMPT.format(output=initial_output[:500])),)
    )
    classification = monitor_response.content.strip().lower()
    print(f"   Classification: {classification}")
    
    # Determine problem type
    problem = None
    for p in ["professor_mode", "hedging", "digression"]:
        if p.replace("_", "") in classification.replace("_", " ").replace("_", ""):
            problem = p
            break
    
    # Map synonyms
    if not problem:
        if "professor" in classification or "academic" in classification:
            problem = "professor_mode"
        elif "hedge" in classification or "uncertain" in classification:
            problem = "hedging"
        elif "tangent" in classification or "off" in classification:
            problem = "digression"
    
    # Step 3: If problem, generate corrected version
    corrected_output = None
    if problem:
        print(f"\n3. Problem detected: {problem}")
        print("   Generating corrected version...")
        
        corrected_response = await worker.generate(
            prompt=(Message(role="user", content=CORRECTION_PROMPT.format(
                problem=problem, 
                task=TASK
            )),)
        )
        corrected_output = corrected_response.content
        print(f"   Length: {len(corrected_output)} chars")
        print(f"   Preview: {corrected_output[:200]}...")
    else:
        print("\n3. No problem detected - output is on_track")
    
    # Step 4: Judge both
    print("\n4. Judging outputs...")
    initial_score = await judge(worker, initial_output)
    print(f"   Initial score: {initial_score}/40")
    
    if corrected_output:
        corrected_score = await judge(worker, corrected_output)
        print(f"   Corrected score: {corrected_score}/40")
        
        improvement = corrected_score - initial_score
        print(f"\n   Improvement: {'+' if improvement > 0 else ''}{improvement} points")
        
        # Verdict
        print("\n" + "=" * 70)
        if improvement > 0:
            print(f"✅ SHEPHERDING HELPED: +{improvement} points")
            print(f"   Initial: {initial_score}/40 → Corrected: {corrected_score}/40")
        elif improvement == 0:
            print("➖ NO CHANGE: Intervention had no effect")
        else:
            print(f"❌ SHEPHERDING HURT: {improvement} points")
            print("   Correction made output worse")
    else:
        print("\n" + "=" * 70)
        print(f"✅ NO INTERVENTION NEEDED: Output was already on_track ({initial_score}/40)")


if __name__ == "__main__":
    asyncio.run(main())
