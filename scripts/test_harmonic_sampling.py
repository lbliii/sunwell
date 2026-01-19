#!/usr/bin/env python3
"""Test Harmonic Sampling - zero-cost diversity via sampling parameters.

Instead of multiple prompts with different personas, we use:
- Same prompt for all candidates
- Different temperature/top_p/seed combinations
- Heuristic selection (no LLM judge)

This achieves perspective diversity at ZERO extra prompt token cost.
"""

import asyncio
import time
from dataclasses import dataclass

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import GenerateOptions


@dataclass
class SamplingConfig:
    """Sampling parameters for a candidate."""
    name: str
    temperature: float


# Sampling configurations for diversity
# Temperature is the primary driver of output diversity
SAMPLING_CONFIGS = [
    SamplingConfig("conservative", temperature=0.3),  # Focused, deterministic
    SamplingConfig("balanced", temperature=0.7),      # Standard
    SamplingConfig("creative", temperature=1.0),      # Exploratory, diverse
]


def heuristic_score(text: str, task_type: str = "general") -> float:
    """Score a candidate using heuristics (no LLM needed)."""
    score = 0.0
    
    # Length (prefer complete responses, but not rambling)
    words = len(text.split())
    if words < 50:
        score -= 2.0  # Too short
    elif words < 200:
        score += words * 0.01  # Reward completeness
    elif words < 500:
        score += 2.0  # Good length
    else:
        score += 1.5  # Slightly penalize very long
    
    # Structure
    score += text.count('\n\n') * 0.3  # Paragraph breaks
    score += min(text.count('```'), 3) * 1.0  # Code blocks (cap at 3)
    score += min(text.count('- '), 10) * 0.2  # Bullet points
    score += min(text.count('1.'), 5) * 0.2  # Numbered lists
    
    # Quality signals
    if '```python' in text or '```' in text:
        score += 1.0  # Has code
    if 'def ' in text or 'class ' in text:
        score += 0.5  # Has function/class definition
    
    # Negative signals
    score -= text.count('TODO') * 0.5
    score -= text.count('...') * 0.3
    score -= text.lower().count('i think') * 0.2  # Hedging
    score -= text.lower().count('maybe') * 0.2
    
    # Completion signals
    if text.strip().endswith(('.', '```', ')')):
        score += 0.5  # Ends cleanly
    
    return score


async def harmonic_sampling(
    model: OllamaModel,
    prompt: str,
    configs: list[SamplingConfig] | None = None,
) -> tuple[str, dict]:
    """Generate diverse candidates via sampling, select best by heuristic."""
    
    configs = configs or SAMPLING_CONFIGS
    
    start_time = time.perf_counter()
    
    # Generate all candidates in parallel
    async def generate_candidate(config: SamplingConfig) -> tuple[str, str, int, float]:
        t0 = time.perf_counter()
        result = await model.generate(
            prompt,
            options=GenerateOptions(
                temperature=config.temperature,
                max_tokens=1024,
            ),
        )
        elapsed = time.perf_counter() - t0
        tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
        return config.name, result.text, tokens, elapsed
    
    results = await asyncio.gather(*[generate_candidate(c) for c in configs])
    
    # Score each candidate
    candidates = []
    for name, text, tokens, elapsed in results:
        score = heuristic_score(text)
        candidates.append({
            "name": name,
            "text": text,
            "tokens": tokens,
            "time": elapsed,
            "score": score,
        })
    
    # Select best
    best = max(candidates, key=lambda c: c["score"])
    
    total_time = time.perf_counter() - start_time
    total_tokens = sum(c["tokens"] for c in candidates)
    
    return best["text"], {
        "candidates": candidates,
        "winner": best["name"],
        "winner_score": best["score"],
        "total_tokens": total_tokens,
        "total_time": total_time,
        "prompt_overhead": 0,  # Zero extra prompt tokens!
    }


async def main() -> None:
    """Test Harmonic Sampling vs traditional approaches."""
    model = OllamaModel(model="gemma3:1b")
    
    test_prompts = [
        {
            "name": "Code generation",
            "prompt": "Write a Python function to validate an email address.",
        },
        {
            "name": "Design decision",
            "prompt": "Should a startup use microservices or monolith? Justify your choice.",
        },
        {
            "name": "Creative",
            "prompt": "Write a tagline for a meditation app targeting busy executives.",
        },
    ]
    
    print("=" * 70)
    print("🎲 HARMONIC SAMPLING TEST")
    print("=" * 70)
    print()
    print("Zero-cost diversity: Same prompt, different sampling parameters")
    print()
    
    for test in test_prompts:
        print(f"\n{'='*70}")
        print(f"Task: {test['name']}")
        print("=" * 70)
        
        output, metrics = await harmonic_sampling(model, test["prompt"])
        
        print(f"\nCandidates:")
        for c in metrics["candidates"]:
            winner_marker = " ← WINNER" if c["name"] == metrics["winner"] else ""
            print(f"  {c['name']:<12} | score={c['score']:>5.1f} | {c['tokens']:>4} tok | {c['time']:.1f}s{winner_marker}")
        
        print(f"\nMetrics:")
        print(f"  Total tokens: {metrics['total_tokens']}")
        print(f"  Prompt overhead: {metrics['prompt_overhead']} (ZERO!)")
        print(f"  Total time: {metrics['total_time']:.1f}s")
        
        print(f"\nWinning output ({metrics['winner']}):")
        print("-" * 40)
        print(output[:500] + "..." if len(output) > 500 else output)
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("Harmonic Sampling achieves diversity with:")
    print("  ✅ ZERO extra prompt tokens")
    print("  ✅ No persona engineering")
    print("  ✅ No LLM judge needed")
    print("  ✅ Heuristic selection is instant")
    print()
    print("Cost: Only the completion tokens for N candidates")
    print("      (which run in parallel, so latency ≈ 1x)")


if __name__ == "__main__":
    asyncio.run(main())
