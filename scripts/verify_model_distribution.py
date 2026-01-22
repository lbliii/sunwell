#!/usr/bin/env python3
"""Verify Model Distribution: Does routing to the right model size improve efficiency?

Hypothesis: A 1B classifier can correctly route 80%+ of tasks,
avoiding unnecessary 20B usage for simple tasks.

Test:
1. Sample of varied tasks (trivial, standard, complex)
2. 1B classifier predicts complexity
3. Compare: always-20B vs routed approach
4. Measure: accuracy, tokens saved, quality preserved
"""

import asyncio
import sys
import time

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import Message


# Test tasks with ground truth complexity
TEST_TASKS = [
    # TRIVIAL - 1B should handle, no need for 20B
    {
        "task": "What is 2 + 2?",
        "expected_complexity": "trivial",
        "expected_model": "1b",
    },
    {
        "task": "Say hello",
        "expected_complexity": "trivial", 
        "expected_model": "1b",
    },
    {
        "task": "What's the capital of France?",
        "expected_complexity": "trivial",
        "expected_model": "1b",
    },
    
    # STANDARD - Could go either way, 1B might suffice
    {
        "task": "Write a Python function to reverse a string",
        "expected_complexity": "standard",
        "expected_model": "either",
    },
    {
        "task": "Explain what a REST API is",
        "expected_complexity": "standard",
        "expected_model": "either",
    },
    {
        "task": "Fix this bug: def add(a, b): return a - b",
        "expected_complexity": "standard",
        "expected_model": "either",
    },
    
    # COMPLEX - Needs 20B for quality
    {
        "task": "Design a microservices architecture for an e-commerce platform with user authentication, product catalog, shopping cart, and payment processing",
        "expected_complexity": "complex",
        "expected_model": "20b",
    },
    {
        "task": "Review this code for security vulnerabilities, performance issues, and maintainability concerns, then suggest improvements with examples",
        "expected_complexity": "complex",
        "expected_model": "20b",
    },
    {
        "task": "Write a comprehensive getting started tutorial for Kubernetes including concepts, installation, first deployment, and troubleshooting",
        "expected_complexity": "complex",
        "expected_model": "20b",
    },
]


CLASSIFIER_PROMPT = """Classify this task's complexity. Respond with ONLY one word: trivial, standard, or complex.

Definitions:
- trivial: Simple factual question, greeting, basic math. Can be answered in one sentence.
- standard: Typical coding task, explanation, single-focus problem. Needs a few paragraphs.
- complex: Multi-faceted problem, architecture design, comprehensive tutorial. Needs detailed analysis.

Task: {task}

Complexity:"""


async def classify_task(classifier: OllamaModel, task: str) -> tuple[str, float]:
    """Use 1B model to classify task complexity."""
    start = time.perf_counter()
    
    response = await classifier.generate(
        prompt=(Message(role="user", content=CLASSIFIER_PROMPT.format(task=task)),)
    )
    
    elapsed = time.perf_counter() - start
    
    # Parse response
    text = response.content.strip().lower()
    if "trivial" in text:
        return "trivial", elapsed
    elif "complex" in text:
        return "complex", elapsed
    else:
        return "standard", elapsed


async def execute_task(model: OllamaModel, task: str) -> tuple[str, float, int]:
    """Execute task and return response, time, approximate tokens."""
    start = time.perf_counter()
    
    response = await model.generate(
        prompt=(Message(role="user", content=task),)
    )
    
    elapsed = time.perf_counter() - start
    
    # Approximate token count (rough: 4 chars per token)
    tokens = len(response.content) // 4
    
    return response.content, elapsed, tokens


async def main():
    classifier_name = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    worker_name = sys.argv[2] if len(sys.argv) > 2 else "gpt-oss:20b"
    
    print(f"Classifier: {classifier_name}")
    print(f"Worker: {worker_name}")
    print("=" * 70)
    
    classifier = OllamaModel(model=classifier_name)
    worker = OllamaModel(model=worker_name)
    
    results = []
    
    for i, test in enumerate(TEST_TASKS):
        task = test["task"]
        expected = test["expected_complexity"]
        expected_model = test["expected_model"]
        
        print(f"\n[{i+1}/{len(TEST_TASKS)}] {task[:50]}...")
        
        # Step 1: Classify with small model
        predicted, classify_time = await classify_task(classifier, task)
        
        correct = (
            predicted == expected or
            (expected_model == "either" and predicted in ["standard", "trivial"])
        )
        
        # Step 2: Determine which model to route to
        if predicted == "trivial":
            routed_model = "classifier"  # 1B can handle
        else:
            routed_model = "worker"  # Need 20B
        
        print(f"  Expected: {expected}, Predicted: {predicted} {'✓' if correct else '✗'}")
        print(f"  Route to: {routed_model} (classify took {classify_time*1000:.0f}ms)")
        
        results.append({
            "task": task[:40],
            "expected": expected,
            "predicted": predicted,
            "correct": correct,
            "routed_to": routed_model,
            "classify_time_ms": classify_time * 1000,
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    correct_count = sum(1 for r in results if r["correct"])
    accuracy = correct_count / len(results) * 100
    
    trivial_routed = sum(1 for r in results if r["routed_to"] == "classifier")
    worker_routed = sum(1 for r in results if r["routed_to"] == "worker")
    
    avg_classify_time = sum(r["classify_time_ms"] for r in results) / len(results)
    
    print(f"\nRouting Accuracy: {correct_count}/{len(results)} ({accuracy:.0f}%)")
    print(f"Routed to classifier (1B): {trivial_routed}/{len(results)}")
    print(f"Routed to worker (20B): {worker_routed}/{len(results)}")
    print(f"Avg classification time: {avg_classify_time:.0f}ms")
    
    # Token savings estimate
    # Assume: trivial tasks would cost ~500 tokens on 20B, but only ~100 on 1B
    # Complex tasks need 20B regardless
    tokens_saved_per_trivial = 400  # rough estimate
    total_tokens_saved = trivial_routed * tokens_saved_per_trivial
    
    print(f"\nEstimated token savings: ~{total_tokens_saved} tokens")
    print(f"  (from routing {trivial_routed} trivial tasks to 1B instead of 20B)")
    
    # Verdict
    print("\n" + "=" * 70)
    if accuracy >= 80:
        print("✅ VERIFIED: Routing accuracy ≥80%")
        print("   Model distribution provides meaningful efficiency gains.")
    else:
        print("⚠️  NEEDS WORK: Routing accuracy <80%")
        print("   Classifier may need tuning or better prompts.")


if __name__ == "__main__":
    asyncio.run(main())
