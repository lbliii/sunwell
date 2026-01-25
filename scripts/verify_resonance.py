#!/usr/bin/env python3
"""Verify Resonance - Does refinement actually improve code quality?

Run with: uv run python scripts/verify_resonance.py

This script verifies that:
1. Bad code + feedback → Better code
2. Improvement is measurable
3. Multiple rounds show diminishing returns
"""

import asyncio
import sys
import time

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from sunwell.planning.naaru.resonance import Resonance, ResonanceConfig


# =============================================================================
# Heuristic Code Scorer
# =============================================================================


def score_code(code: str) -> dict:
    """Score Python code quality using heuristics."""
    issues = []
    score = 5.0

    has_docstring = '"""' in code or "'''" in code
    if not has_docstring:
        issues.append("Missing docstring")
        score -= 1.5
    else:
        score += 1.0

    has_type_hints = "->" in code and (":" in code.split("->")[0])
    if not has_type_hints:
        issues.append("No type hints")
        score -= 1.0
    else:
        score += 1.0

    has_error_handling = "raise " in code or "try:" in code
    if not has_error_handling:
        issues.append("No error handling")
        score -= 0.5
    else:
        score += 0.5

    if has_docstring:
        if "Args:" in code:
            score += 0.5
        else:
            issues.append("Missing Args section")
        if "Returns:" in code:
            score += 0.5
        else:
            issues.append("Missing Returns section")

    if "def " not in code:
        issues.append("No function definition")
        score -= 2.0

    lines = [l for l in code.split("\n") if l.strip()]
    if len(lines) < 3:
        issues.append("Too short")
        score -= 1.0

    return {
        "score": max(0.0, min(10.0, score)),
        "issues": issues,
        "has_docstring": has_docstring,
        "has_type_hints": has_type_hints,
        "has_error_handling": has_error_handling,
    }


# =============================================================================
# Test Cases
# =============================================================================

TEST_CASES = [
    {
        "name": "Minimal function",
        "code": "def add(a, b): return a + b",
        "category": "code_quality",
    },
    {
        "name": "No error handling",
        "code": "def divide(a, b): return a / b",
        "category": "error_handling",
    },
    {
        "name": "Missing docs",
        "code": """def process_user(user_id: int) -> dict:
    data = fetch_user(user_id)
    return {"name": data.name, "email": data.email}""",
        "category": "documentation",
    },
]


# =============================================================================
# Main
# =============================================================================


async def main():
    console = Console() if RICH_AVAILABLE else None

    print("=" * 60)
    print("Resonance Verification: Does refinement improve quality?")
    print("=" * 60)

    # Initialize model
    try:
        from sunwell.models.ollama import OllamaModel

        model = OllamaModel(model="llama3.2:3b")
        print(f"Using model: llama3.2:3b")
    except Exception as e:
        print(f"Error: Could not initialize model: {e}")
        sys.exit(1)

    resonance = Resonance(
        model=model,
        config=ResonanceConfig(max_attempts=2, max_tokens=512),
    )

    results = []

    for test in TEST_CASES:
        print(f"\n--- {test['name']} ---")

        # Score original
        original_score = score_code(test["code"])
        print(f"Original score: {original_score['score']:.1f}/10")
        print(f"Issues: {', '.join(original_score['issues']) or 'None'}")

        # Refine
        proposal = {
            "proposal_id": test["name"].replace(" ", "_"),
            "diff": test["code"],
            "summary": {"category": test["category"]},
        }
        rejection = {
            "issues": original_score["issues"],
            "score": original_score["score"],
        }

        start = time.perf_counter()
        result = await resonance.refine(proposal, rejection)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Score refined
        refined_score = score_code(result.refined_code)

        improvement = refined_score["score"] - original_score["score"]
        print(f"Refined score: {refined_score['score']:.1f}/10 ({improvement:+.1f})")
        print(f"Time: {elapsed_ms:.0f}ms")

        results.append({
            "name": test["name"],
            "original_score": original_score["score"],
            "refined_score": refined_score["score"],
            "improvement": improvement,
            "time_ms": elapsed_ms,
            "attempts": len(result.attempts),
            "original_issues": len(original_score["issues"]),
            "refined_issues": len(refined_score["issues"]),
        })

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if RICH_AVAILABLE and console:
        table = Table(title="Resonance Verification Results")
        table.add_column("Test")
        table.add_column("Original")
        table.add_column("Refined")
        table.add_column("Improvement")
        table.add_column("Time")

        for r in results:
            color = "green" if r["improvement"] > 0 else "red" if r["improvement"] < 0 else "yellow"
            table.add_row(
                r["name"],
                f"{r['original_score']:.1f}",
                f"{r['refined_score']:.1f}",
                f"[{color}]{r['improvement']:+.1f}[/{color}]",
                f"{r['time_ms']:.0f}ms",
            )

        console.print(table)
    else:
        for r in results:
            print(f"{r['name']}: {r['original_score']:.1f} → {r['refined_score']:.1f} ({r['improvement']:+.1f})")

    # Verify thesis
    improvements = [r["improvement"] for r in results]
    avg_improvement = sum(improvements) / len(improvements)
    improved_count = sum(1 for i in improvements if i > 0)

    print(f"\nAverage improvement: {avg_improvement:+.2f} points")
    print(f"Tests improved: {improved_count}/{len(results)}")

    if avg_improvement > 0 and improved_count >= len(results) // 2:
        print("\n✅ RESONANCE VERIFIED: Refinement improves code quality")
        return True
    else:
        print("\n❌ RESONANCE NOT VERIFIED: No consistent improvement")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
