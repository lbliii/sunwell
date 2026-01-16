#!/usr/bin/env python3
"""Novel Prompting Techniques for Low-B Models.

Combines cutting-edge prompting research with Sunwell's unique features:
- Lenses (personas, heuristics, validators)
- SimulacrumStore (episodic memory)
- MirrorHandler (self-introspection)
- Multi-topology (brain architecture)

Inspired by: https://www.promptingguide.ai/techniques

NOVEL TECHNIQUES:
1. LENS-WEIGHTED SELF-CONSISTENCY - Multiple lenses vote (not just temperature sampling)
2. HEADSPACE-GUIDED COT - Memory-informed chain-of-thought
3. ADAPTIVE LENS SELECTION - Active-prompt but for lens personas
4. KNOWLEDGE DISTILLATION - Big model teaches small model via lens
5. SWARM DEBATE - Multiple lens-personas argue to consensus
6. MIRROR REFLEXION - Self-introspection drives improvement

Usage:
    python examples/novel_techniques.py --technique lens-consistency
    python examples/novel_techniques.py --technique simulacrum-cot
    python examples/novel_techniques.py --technique all
"""

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import GenerateOptions


@dataclass
class TechniqueResult:
    """Results from a technique run."""
    technique: str
    quality_score: float
    model_calls: int
    total_tokens: int
    time_seconds: float
    output: str
    details: dict = field(default_factory=dict)


# Test task
TASK = """Write a Python function to detect SQL injection in user input.
Requirements:
- Check for common SQL injection patterns
- Return (is_safe: bool, reason: str)
- Handle edge cases
Code only:"""


# Simulated lens personas (in production, load from .lens files)
LENS_PERSONAS = {
    "security": {
        "name": "Security Expert",
        "system": "You are a security expert. Focus on attack vectors, edge cases, and defensive coding.",
        "focus": ["injection patterns", "escape sequences", "whitelist vs blacklist"],
    },
    "code_quality": {
        "name": "Code Reviewer", 
        "system": "You are a senior Python developer. Focus on clean, maintainable, idiomatic code.",
        "focus": ["readability", "Pythonic style", "error handling"],
    },
    "testing": {
        "name": "QA Engineer",
        "system": "You are a QA engineer. Focus on testability, edge cases, and failure modes.",
        "focus": ["test coverage", "boundary conditions", "error messages"],
    },
}


async def technique_baseline(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> TechniqueResult:
    """Baseline: Single generation, no techniques."""
    start = time.time()
    
    result = await model.generate(task, options=GenerateOptions(temperature=0.3, max_tokens=1024))
    code = result.content or ""
    tokens = result.usage.total_tokens if result.usage else 0
    
    score = await _judge(judge, code, task)
    
    return TechniqueResult(
        technique="baseline",
        quality_score=score,
        model_calls=1,
        total_tokens=tokens,
        time_seconds=time.time() - start,
        output=code,
    )


async def technique_lens_consistency(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> TechniqueResult:
    """LENS-WEIGHTED SELF-CONSISTENCY (Novel)
    
    Standard self-consistency samples multiple times with different temperatures.
    We sample with different LENS PERSONAS instead - each brings domain expertise.
    
    The key insight: temperature diversity gives random variance,
    lens diversity gives STRUCTURED variance based on domain knowledge.
    """
    start = time.time()
    total_tokens = 0
    
    candidates = []
    
    # Generate with each lens persona
    for lens_id, lens in LENS_PERSONAS.items():
        prompt = f"""{lens['system']}

Focus areas: {', '.join(lens['focus'])}

TASK: {task}"""
        
        result = await model.generate(prompt, options=GenerateOptions(temperature=0.3, max_tokens=1024))
        code = result.content or ""
        tokens = result.usage.total_tokens if result.usage else 0
        total_tokens += tokens
        
        candidates.append({
            "lens": lens_id,
            "lens_name": lens["name"],
            "code": code,
        })
    
    # Have each lens VOTE on all candidates (weighted by expertise)
    vote_prompt = f"""You are evaluating code solutions for: {task}

"""
    for i, c in enumerate(candidates):
        vote_prompt += f"""
SOLUTION {i+1} (from {c['lens_name']}):
```python
{c['code'][:600]}
```
"""
    
    vote_prompt += """
Which solution is BEST? Consider:
- Security (most important for this task)
- Code quality
- Completeness

Respond with just the number (1, 2, or 3):"""
    
    # Get votes from each lens perspective
    votes = []
    for lens_id, lens in LENS_PERSONAS.items():
        vote_result = await model.generate(
            f"{lens['system']}\n\n{vote_prompt}",
            options=GenerateOptions(temperature=0.1, max_tokens=10),
        )
        total_tokens += vote_result.usage.total_tokens if vote_result.usage else 0
        
        try:
            vote = int("".join(c for c in (vote_result.content or "1") if c.isdigit())[:1]) - 1
            vote = max(0, min(vote, len(candidates) - 1))
            votes.append(vote)
        except:
            votes.append(0)
    
    # Majority vote
    from collections import Counter
    winner = Counter(votes).most_common(1)[0][0]
    best_code = candidates[winner]["code"]
    
    score = await _judge(judge, best_code, task)
    
    return TechniqueResult(
        technique="lens-consistency",
        quality_score=score,
        model_calls=len(LENS_PERSONAS) * 2,  # Generate + vote per lens
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        output=best_code,
        details={
            "votes": votes,
            "winner": candidates[winner]["lens_name"],
            "candidates": [c["lens"] for c in candidates],
        },
    )


async def technique_simulacrum_cot(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> TechniqueResult:
    """HEADSPACE-GUIDED CHAIN-OF-THOUGHT (Novel)
    
    Standard CoT adds "Let's think step by step".
    We add MEMORY CONTEXT from past experiences to guide reasoning.
    
    The key insight: past learnings inform current reasoning,
    like how experts draw on experience, not just logic.
    """
    start = time.time()
    total_tokens = 0
    
    # Simulated simulacrum memories (in production, query SimulacrumStore)
    memories = [
        "SQL injection often uses OR 1=1 to bypass authentication",
        "UNION SELECT attacks can exfiltrate data from other tables",
        "Parameterized queries are safer than string concatenation",
        "Don't just blacklist - attackers can bypass with encoding",
        "Consider case variations: SELECT, SeLeCt, etc.",
        "Comments (--) can truncate queries and bypass checks",
    ]
    
    # Build memory-guided CoT prompt
    cot_prompt = f"""RELEVANT KNOWLEDGE FROM EXPERIENCE:
{chr(10).join(f'- {m}' for m in memories)}

TASK: {task}

Let me think through this step by step, applying what I know:

Step 1: What are the main SQL injection patterns I need to detect?
Step 2: How can attackers bypass simple detection?
Step 3: What's the safest approach (whitelist vs blacklist)?
Step 4: How should I structure the return value?

Based on this reasoning, here's my solution:"""
    
    result = await model.generate(cot_prompt, options=GenerateOptions(temperature=0.3, max_tokens=1500))
    code = result.content or ""
    total_tokens += result.usage.total_tokens if result.usage else 0
    
    score = await _judge(judge, code, task)
    
    return TechniqueResult(
        technique="simulacrum-cot",
        quality_score=score,
        model_calls=1,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        output=code,
        details={"memories_used": len(memories)},
    )


async def technique_adaptive_lens(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> TechniqueResult:
    """ADAPTIVE LENS SELECTION (Novel)
    
    Like Active-Prompt selects examples dynamically,
    we SELECT THE BEST LENS for the task automatically.
    
    The key insight: different tasks need different expertise.
    A small model can choose the right lens, then use it.
    """
    start = time.time()
    total_tokens = 0
    
    # Step 1: Analyze task to select best lens
    selection_prompt = f"""Analyze this task and choose the most relevant expert:

TASK: {task}

AVAILABLE EXPERTS:
1. Security Expert - Focus: attack vectors, defensive coding, injection patterns
2. Code Reviewer - Focus: clean code, readability, Python best practices  
3. QA Engineer - Focus: testing, edge cases, error handling

Which expert is MOST relevant for this specific task?
Respond with just the number (1, 2, or 3):"""
    
    select_result = await model.generate(
        selection_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=10),
    )
    total_tokens += select_result.usage.total_tokens if select_result.usage else 0
    
    try:
        selection = int("".join(c for c in (select_result.content or "1") if c.isdigit())[:1])
    except:
        selection = 1
    
    lens_map = {1: "security", 2: "code_quality", 3: "testing"}
    selected_lens = LENS_PERSONAS[lens_map.get(selection, "security")]
    
    # Step 2: Generate with selected lens
    gen_prompt = f"""{selected_lens['system']}

Focus areas: {', '.join(selected_lens['focus'])}

TASK: {task}"""
    
    result = await model.generate(gen_prompt, options=GenerateOptions(temperature=0.3, max_tokens=1024))
    code = result.content or ""
    total_tokens += result.usage.total_tokens if result.usage else 0
    
    score = await _judge(judge, code, task)
    
    return TechniqueResult(
        technique="adaptive-lens",
        quality_score=score,
        model_calls=2,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        output=code,
        details={"selected_lens": selected_lens["name"]},
    )


async def technique_knowledge_distill(
    model: OllamaModel,
    big_model: OllamaModel,
    judge: OllamaModel,
    task: str,
) -> TechniqueResult:
    """KNOWLEDGE DISTILLATION VIA LENS (Novel)
    
    Standard distillation fine-tunes small models on big model outputs.
    We use the big model to GENERATE DOMAIN KNOWLEDGE (like a lens),
    then the small model uses that knowledge for generation.
    
    The key insight: big model as "instant expert lens creator",
    small model as executor with that expertise injected.
    """
    start = time.time()
    total_tokens = 0
    
    # Step 1: Big model generates domain knowledge (like creating a lens)
    knowledge_prompt = f"""You are creating a knowledge guide for a junior developer.

TASK THEY NEED TO SOLVE: {task}

Write 5-7 specific, actionable tips they should know to solve this well.
Focus on domain-specific knowledge, not generic advice.
Be concise - one line per tip:"""
    
    knowledge_result = await big_model.generate(
        knowledge_prompt,
        options=GenerateOptions(temperature=0.3, max_tokens=400),
    )
    knowledge = knowledge_result.content or ""
    total_tokens += knowledge_result.usage.total_tokens if knowledge_result.usage else 0
    
    # Step 2: Small model generates with distilled knowledge
    gen_prompt = f"""EXPERT KNOWLEDGE FOR THIS TASK:
{knowledge}

TASK: {task}

Apply the expert knowledge above to write the solution:"""
    
    result = await model.generate(gen_prompt, options=GenerateOptions(temperature=0.3, max_tokens=1024))
    code = result.content or ""
    total_tokens += result.usage.total_tokens if result.usage else 0
    
    score = await _judge(judge, code, task)
    
    return TechniqueResult(
        technique="knowledge-distill",
        quality_score=score,
        model_calls=2,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        output=code,
        details={"knowledge_preview": knowledge[:200]},
    )


async def technique_swarm_debate(
    model: OllamaModel,
    judge: OllamaModel,
    task: str,
    rounds: int = 2,
) -> TechniqueResult:
    """SWARM DEBATE (Novel) - Inspired by RFC-017 Team Swarm
    
    Multiple lens-personas DEBATE and critique each other,
    converging on a better solution through argument.
    
    The key insight: debate surfaces issues that single generation misses.
    Small models can critique better than they can generate.
    """
    start = time.time()
    total_tokens = 0
    
    # Round 1: Each persona generates initial solution
    solutions = {}
    for lens_id, lens in LENS_PERSONAS.items():
        prompt = f"""{lens['system']}
Focus: {', '.join(lens['focus'])}

TASK: {task}"""
        
        result = await model.generate(prompt, options=GenerateOptions(temperature=0.3, max_tokens=800))
        solutions[lens_id] = result.content or ""
        total_tokens += result.usage.total_tokens if result.usage else 0
    
    # Debate rounds: Each persona critiques others
    for round_num in range(rounds):
        critiques = {}
        
        for critic_id, critic_lens in LENS_PERSONAS.items():
            # Critique other solutions from your perspective
            other_solutions = {k: v for k, v in solutions.items() if k != critic_id}
            
            critique_prompt = f"""{critic_lens['system']}

Review these solutions from your expert perspective:

"""
            for sol_id, sol_code in other_solutions.items():
                critique_prompt += f"""
{LENS_PERSONAS[sol_id]['name']}'s solution:
```python
{sol_code[:400]}
```
"""
            
            critique_prompt += f"""
What SPECIFIC issues do you see? What would you improve?
Be constructive and specific:"""
            
            crit_result = await model.generate(
                critique_prompt,
                options=GenerateOptions(temperature=0.2, max_tokens=300),
            )
            critiques[critic_id] = crit_result.content or ""
            total_tokens += crit_result.usage.total_tokens if crit_result.usage else 0
        
        # Each persona updates their solution based on critiques
        for lens_id, lens in LENS_PERSONAS.items():
            other_critiques = [c for cid, c in critiques.items() if cid != lens_id]
            
            update_prompt = f"""{lens['system']}

Your current solution:
```python
{solutions[lens_id][:500]}
```

Feedback from other experts:
{chr(10).join(other_critiques)}

Update your solution to address valid concerns. Output only the improved code:"""
            
            update_result = await model.generate(
                update_prompt,
                options=GenerateOptions(temperature=0.2, max_tokens=800),
            )
            solutions[lens_id] = update_result.content or solutions[lens_id]
            total_tokens += update_result.usage.total_tokens if update_result.usage else 0
    
    # Final: Vote on best solution after debate
    vote_prompt = "Which solution is best after the debate?\n\n"
    for i, (lens_id, code) in enumerate(solutions.items()):
        vote_prompt += f"{i+1}. {LENS_PERSONAS[lens_id]['name']}:\n```python\n{code[:300]}\n```\n\n"
    vote_prompt += "Respond with just the number:"
    
    vote_result = await model.generate(vote_prompt, options=GenerateOptions(temperature=0.1, max_tokens=10))
    total_tokens += vote_result.usage.total_tokens if vote_result.usage else 0
    
    try:
        winner_idx = int("".join(c for c in (vote_result.content or "1") if c.isdigit())[:1]) - 1
        winner_id = list(solutions.keys())[max(0, min(winner_idx, len(solutions) - 1))]
    except:
        winner_id = "security"
    
    best_code = solutions[winner_id]
    score = await _judge(judge, best_code, task)
    
    return TechniqueResult(
        technique="swarm-debate",
        quality_score=score,
        model_calls=len(LENS_PERSONAS) * (1 + rounds * 2) + 1,
        total_tokens=total_tokens,
        time_seconds=time.time() - start,
        output=best_code,
        details={"rounds": rounds, "winner": LENS_PERSONAS[winner_id]["name"]},
    )


async def _judge(judge: OllamaModel, code: str, task: str) -> float:
    """Score code quality."""
    prompt = f"""Score this code 0-10.

TASK: {task}

CODE:
```python
{code[:1500]}
```

SCORING:
- 0-3: Broken/wrong
- 4-5: Works but incomplete
- 6-7: Good, handles basics
- 8-9: Excellent, handles edge cases
- 10: Production-ready

Your response MUST end with: SCORE: X"""
    
    result = await judge.generate(prompt, options=GenerateOptions(temperature=0.1, max_tokens=300))
    
    import re
    text = result.content or ""
    match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if match:
        return min(10.0, max(0.0, float(match.group(1))))
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
    if numbers:
        return min(10.0, max(0.0, float(numbers[-1])))
    return 5.0


def print_results(results: list[TechniqueResult]):
    """Print comparison."""
    print()
    print("=" * 85)
    print("📊 NOVEL TECHNIQUE COMPARISON")
    print("=" * 85)
    
    results.sort(key=lambda r: r.quality_score, reverse=True)
    
    print(f"\n{'Technique':<20} {'Quality':>8} {'Calls':>6} {'Tokens':>8} {'Time':>8} Details")
    print("-" * 85)
    
    for r in results:
        detail_str = str(r.details)[:30] if r.details else ""
        print(f"{r.technique:<20} {r.quality_score:>7.1f}/10 {r.model_calls:>6} {r.total_tokens:>8} {r.time_seconds:>7.1f}s {detail_str}")
    
    best = results[0]
    baseline = next((r for r in results if r.technique == "baseline"), results[-1])
    
    print()
    print("-" * 85)
    print(f"🏆 Best: {best.technique} ({best.quality_score:.1f}/10)")
    if best.technique != "baseline":
        improvement = best.quality_score - baseline.quality_score
        print(f"   Improvement over baseline: {improvement:+.1f} points")


async def main():
    parser = argparse.ArgumentParser(description="Novel Prompting Techniques")
    parser.add_argument("--technique", default="all",
                       choices=["baseline", "lens-consistency", "simulacrum-cot", 
                               "adaptive-lens", "knowledge-distill", "swarm-debate", "all"])
    parser.add_argument("--model", default="gemma3:1b")
    parser.add_argument("--big-model", default="gemma3:4b")
    parser.add_argument("--judge", default="gemma3:4b")
    args = parser.parse_args()
    
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " 🧪 NOVEL PROMPTING TECHNIQUES FOR LOW-B MODELS".ljust(78) + "║")
    print("║" + " Combining Sunwell features with cutting-edge prompting research".ljust(78) + "║")
    print("╠" + "═" * 78 + "╣")
    print("║" + f" Small: {args.model} | Big: {args.big_model} | Judge: {args.judge}".ljust(78) + "║")
    print("╚" + "═" * 78 + "╝")
    
    small = OllamaModel(model=args.model)
    big = OllamaModel(model=args.big_model)
    judge = OllamaModel(model=args.judge)
    
    techniques = {
        "baseline": lambda: technique_baseline(small, judge, TASK),
        "lens-consistency": lambda: technique_lens_consistency(small, judge, TASK),
        "simulacrum-cot": lambda: technique_simulacrum_cot(small, judge, TASK),
        "adaptive-lens": lambda: technique_adaptive_lens(small, judge, TASK),
        "knowledge-distill": lambda: technique_knowledge_distill(small, big, judge, TASK),
        "swarm-debate": lambda: technique_swarm_debate(small, judge, TASK),
    }
    
    results = []
    
    if args.technique == "all":
        for name, fn in techniques.items():
            print(f"\n🔄 Running {name}...")
            try:
                result = await fn()
                results.append(result)
                print(f"   ✓ Quality: {result.quality_score:.1f}/10")
            except Exception as e:
                print(f"   ✗ Error: {e}")
    else:
        print(f"\n🔄 Running {args.technique}...")
        result = await techniques[args.technique]()
        results.append(result)
    
    print_results(results)
    
    print()
    print("📚 Technique Explanations:")
    print("   lens-consistency  - Self-consistency but with LENS PERSONAS (structured variance)")
    print("   simulacrum-cot     - Chain-of-thought guided by MEMORY (experience-based)")
    print("   adaptive-lens     - Dynamically SELECT best lens for the task")
    print("   knowledge-distill - Big model creates knowledge, small model uses it")
    print("   swarm-debate      - Lens personas DEBATE and critique each other")


if __name__ == "__main__":
    asyncio.run(main())
