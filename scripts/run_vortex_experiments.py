#!/usr/bin/env python3
"""Run the vortex experiments to test emergent intelligence primitives.

Usage:
    python scripts/run_vortex_experiments.py --model qwen2.5-coder:1.5b

This runs a quick suite of experiments to test the hypothesis that
combining primitives creates emergent capability.
"""

import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sunwell.models.ollama import OllamaModel


async def run_interference_test(model):
    """Test 1: Does agreement predict accuracy?"""
    from sunwell.experiments.interference import (
        interference_scan,
        format_interference_report,
    )
    
    print("\n" + "="*60)
    print("EXPERIMENT 1: INTERFERENCE PATTERNS")
    print("="*60)
    print("Hypothesis: Agreement between perspectives predicts confidence")
    print()
    
    tasks = [
        # High agreement expected
        ("What is 2 + 2?", "4", "trivial"),
        ("Is 'Bob is 3 years older' addition or subtraction?", "addition", "easy"),
        # Medium agreement expected  
        ("What does 'twice as many' mean: add or multiply?", "multiply", "medium"),
        # Low agreement expected (ambiguous)
        ("Is 'not bad' positive or negative sentiment?", "neutral", "ambiguous"),
    ]
    
    results = []
    for task, expected, difficulty in tasks:
        print(f"Task ({difficulty}): {task[:50]}...")
        result = await interference_scan(task, model, n_perspectives=5)
        
        correct = (
            result.consensus_answer and 
            expected.lower() in result.consensus_answer.lower()
        )
        
        print(f"  Agreement: {result.agreement_score:.1%}")
        print(f"  Consensus: {result.consensus_answer}")
        print(f"  Correct: {'✓' if correct else '✗'}")
        print(f"  Pattern: {result.interference_pattern}")
        print()
        
        results.append({
            "task": task,
            "difficulty": difficulty,
            "agreement": result.agreement_score,
            "correct": correct,
            "pattern": result.interference_pattern,
        })
    
    # Correlation check
    high_agree = [r for r in results if r["agreement"] >= 0.6]
    low_agree = [r for r in results if r["agreement"] < 0.6]
    
    high_acc = sum(1 for r in high_agree if r["correct"]) / len(high_agree) if high_agree else 0
    low_acc = sum(1 for r in low_agree if r["correct"]) / len(low_agree) if low_agree else 0
    
    print("--- INTERFERENCE SUMMARY ---")
    print(f"High agreement accuracy: {high_acc:.1%} ({len(high_agree)} tasks)")
    print(f"Low agreement accuracy:  {low_acc:.1%} ({len(low_agree)} tasks)")
    
    if high_acc > low_acc:
        print("✓ Agreement correlates with accuracy!")
    else:
        print("✗ No clear correlation (need more data)")
    
    return results


async def run_resonance_test(model):
    """Test 2: Does iterative feedback improve quality?"""
    from sunwell.experiments.resonance_amp import (
        resonance_experiment,
        format_resonance_report,
        plot_resonance_curve,
    )
    
    print("\n" + "="*60)
    print("EXPERIMENT 2: RESONANCE AMPLIFICATION")
    print("="*60)
    print("Hypothesis: Iterative feedback improves quality")
    print()
    
    task = "Explain why Python uses indentation for blocks instead of braces."
    
    print(f"Task: {task}")
    print("Running 4 refinement iterations...")
    print()
    
    result = await resonance_experiment(
        task=task,
        model=model,
        max_iterations=4,
        judge_mode="constructive",
    )
    
    print(format_resonance_report(result))
    print()
    print("Quality curve:")
    print(plot_resonance_curve(result))
    
    print()
    print("--- RESONANCE SUMMARY ---")
    print(f"Pattern: {result.pattern}")
    print(f"Total improvement: {result.total_improvement:+.1%}")
    print(f"Effective iterations: {result.effective_iterations}")
    
    if result.total_improvement > 0.05:
        print("✓ Resonance amplifies quality!")
    elif result.total_improvement > 0:
        print("~ Modest improvement from resonance")
    else:
        print("✗ No improvement from resonance")
    
    return {
        "pattern": result.pattern,
        "improvement": result.total_improvement,
        "peak_iteration": result.peak_iteration,
    }


async def run_gradient_test(model):
    """Test 3: Does solving easy parts first help hard parts?"""
    from sunwell.experiments.gradient import (
        gradient_flow_solve,
        format_gradient_report,
    )
    
    print("\n" + "="*60)
    print("EXPERIMENT 3: GRADIENT FLOW")
    print("="*60)
    print("Hypothesis: Solving easy subtasks first improves hard ones")
    print()
    
    goal = "Design a simple user authentication system with login, logout, and password reset"
    
    print(f"Goal: {goal}")
    print("Decomposing and solving with gradient flow...")
    print()
    
    result = await gradient_flow_solve(goal, model)
    
    print(format_gradient_report(result))
    
    print()
    print("--- GRADIENT SUMMARY ---")
    print(f"Gradient confidence: {result.gradient_accuracy:.1%}")
    print(f"Baseline confidence: {result.baseline_accuracy:.1%}")
    print(f"Improvement: {result.improvement:+.1%}")
    
    if result.improvement > 0.05:
        print("✓ Gradient flow helps!")
    elif result.improvement > 0:
        print("~ Modest improvement from gradient")
    else:
        print("✗ No improvement from gradient")
    
    return {
        "gradient_score": result.gradient_accuracy,
        "baseline_score": result.baseline_accuracy,
        "improvement": result.improvement,
    }


async def run_mini_vortex_test(model):
    """Test 4: Quick vortex test (interference + resonance combined)."""
    from sunwell.experiments.interference import interference_scan, should_escalate
    from sunwell.experiments.dialectic import dialectic_decide
    
    print("\n" + "="*60)
    print("EXPERIMENT 4: MINI VORTEX (Interference + Dialectic)")
    print("="*60)
    print("Hypothesis: Combining primitives beats single model")
    print()
    
    task = "Should a REST API use PUT or PATCH for partial updates?"
    
    print(f"Task: {task}")
    print()
    
    # Single model baseline
    print("1. Single model...")
    single_result = await model.generate(task)
    single_response = single_result.content if hasattr(single_result, "content") else str(single_result)
    
    # Interference scan
    print("2. Running interference scan (5 perspectives)...")
    interference = await interference_scan(task, model, n_perspectives=5)
    
    # If low agreement, run dialectic
    print("3. Checking agreement...")
    if should_escalate(interference, threshold=0.6):
        print(f"   Low agreement ({interference.agreement_score:.1%}), running dialectic...")
        dialectic = await dialectic_decide(task, model=model)
        final_response = dialectic.synthesis
        method = "interference + dialectic"
    else:
        print(f"   High agreement ({interference.agreement_score:.1%}), using consensus")
        final_response = interference.consensus_answer or single_response
        method = "interference (consensus)"
    
    print()
    print("--- RESULTS ---")
    print(f"\nSingle model ({len(single_response)} chars):")
    print(f"  {single_response[:200]}...")
    print(f"\nVortex ({method}, {len(final_response)} chars):")
    print(f"  {final_response[:200]}...")
    
    print()
    print("--- MINI VORTEX SUMMARY ---")
    print(f"Method used: {method}")
    print(f"Agreement: {interference.agreement_score:.1%}")
    print(f"Single response length: {len(single_response)}")
    print(f"Vortex response length: {len(final_response)}")
    
    return {
        "method": method,
        "agreement": interference.agreement_score,
        "single_length": len(single_response),
        "vortex_length": len(final_response),
    }


async def main():
    parser = argparse.ArgumentParser(description="Run vortex experiments")
    parser.add_argument(
        "--model",
        default="qwen2.5-coder:1.5b",
        help="Ollama model to use (default: qwen2.5-coder:1.5b)",
    )
    parser.add_argument(
        "--skip-gradient",
        action="store_true",
        help="Skip gradient test (slowest)",
    )
    args = parser.parse_args()
    
    print("="*60)
    print("VORTEX EXPERIMENTS")
    print("="*60)
    print(f"Model: {args.model}")
    print(f"Time: {datetime.now().isoformat()}")
    print()
    print("Testing emergent intelligence primitives...")
    print("="*60)
    
    model = OllamaModel(args.model)
    
    results = {}
    
    # Run experiments
    try:
        results["interference"] = await run_interference_test(model)
    except Exception as e:
        print(f"Interference test failed: {e}")
        results["interference"] = {"error": str(e)}
    
    try:
        results["resonance"] = await run_resonance_test(model)
    except Exception as e:
        print(f"Resonance test failed: {e}")
        results["resonance"] = {"error": str(e)}
    
    if not args.skip_gradient:
        try:
            results["gradient"] = await run_gradient_test(model)
        except Exception as e:
            print(f"Gradient test failed: {e}")
            results["gradient"] = {"error": str(e)}
    
    try:
        results["mini_vortex"] = await run_mini_vortex_test(model)
    except Exception as e:
        print(f"Mini vortex test failed: {e}")
        results["mini_vortex"] = {"error": str(e)}
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    emergent_signals = 0
    
    if "interference" in results and "error" not in results["interference"]:
        print("✓ Interference: Ran successfully")
        emergent_signals += 1
    
    if "resonance" in results and "error" not in results["resonance"]:
        r = results["resonance"]
        if r.get("improvement", 0) > 0:
            print(f"✓ Resonance: +{r['improvement']:.1%} improvement")
            emergent_signals += 1
        else:
            print("~ Resonance: No improvement")
    
    if "gradient" in results and "error" not in results["gradient"]:
        r = results["gradient"]
        if r.get("improvement", 0) > 0:
            print(f"✓ Gradient: +{r['improvement']:.1%} improvement")
            emergent_signals += 1
        else:
            print("~ Gradient: No improvement")
    
    if "mini_vortex" in results and "error" not in results["mini_vortex"]:
        print(f"✓ Mini Vortex: Completed ({results['mini_vortex']['method']})")
        emergent_signals += 1
    
    print()
    if emergent_signals >= 3:
        print("🌀 STRONG EMERGENCE SIGNALS - The vortex is forming!")
    elif emergent_signals >= 2:
        print("📊 MODERATE SIGNALS - Some primitives showing value")
    else:
        print("⚠️  WEAK SIGNALS - Need more testing or different tasks")
    
    # Save results
    results_dir = Path(__file__).parent.parent / "benchmark" / "results" / "vortex"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results_file = results_dir / f"experiment-{timestamp}.json"
    
    with open(results_file, "w") as f:
        json.dump({
            "model": args.model,
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    asyncio.run(main())
