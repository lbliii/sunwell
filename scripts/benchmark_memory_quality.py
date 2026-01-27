#!/usr/bin/env python3
"""Benchmark: Does hierarchical memory make Sunwell smarter?

Tests whether retrieving historical context actually improves LLM responses.

Methodology:
1. Simulate a conversation with specific facts spread across 50+ turns
2. Ask questions that require remembering those facts
3. Compare: with memory vs without memory (fresh context only)
4. Score: Does the model recall the facts correctly?
"""

import asyncio
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

# Facts to embed in the conversation (spread across turns)
FACTS = [
    {"turn": 5, "fact": "The user's name is Alex Chen", "query": "What is my name?", "expected": "Alex Chen"},
    {"turn": 15, "fact": "The project uses PostgreSQL 15 for the database", "query": "What database are we using?", "expected": "PostgreSQL 15"},
    {"turn": 25, "fact": "The API rate limit is 1000 requests per minute", "query": "What's our API rate limit?", "expected": "1000"},
    {"turn": 35, "fact": "The deployment target is Kubernetes on GKE", "query": "Where are we deploying?", "expected": "Kubernetes"},
    {"turn": 45, "fact": "The auth system uses JWT with 24 hour expiry", "query": "How long do our auth tokens last?", "expected": "24"},
]


@dataclass
class BenchmarkResult:
    """Result of a single memory test."""
    query: str
    expected: str
    response_with_memory: str
    response_without_memory: str
    with_memory_correct: bool
    without_memory_correct: bool


async def run_benchmark():
    """Run the memory quality benchmark."""
    from sunwell.simulacrum.core.store import SimulacrumStore
    from sunwell.simulacrum.core.turn import Turn, TurnType

    console.print("\n[bold cyan]Memory Quality Benchmark[/bold cyan]")
    console.print("Testing if hierarchical memory improves LLM responses\n")

    # Check if Ollama is available
    try:
        import subprocess
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0 or b"models" not in result.stdout:
            console.print("[red]Ollama not running. Start with: ollama serve[/red]")
            return
        console.print("[green]✓[/green] Ollama is running")
    except Exception as e:
        console.print(f"[red]Ollama check failed: {e}[/red]")
        return

    # Create test store with embeddings for semantic search
    test_dir = Path(tempfile.mkdtemp(prefix="sunwell_memory_bench_"))
    store = SimulacrumStore(base_path=test_dir)

    # Enable semantic search
    from sunwell.embedding import create_embedder
    embedder = create_embedder()
    store.set_embedder(embedder)
    console.print(f"[green]✓[/green] Embeddings enabled ({type(embedder).__name__})")

    try:
        # Phase 1: Build conversation history with embedded facts
        console.print("[bold]Phase 1: Building conversation history with facts[/bold]")

        topics = ["architecture", "testing", "security", "performance", "deployment"]
        fact_turns = {f["turn"]: f["fact"] for f in FACTS}

        for i in range(50):
            topic = topics[i % len(topics)]

            # Check if this turn should contain a fact
            if i in fact_turns:
                user_content = f"By the way, {fact_turns[i]}. Now, let's continue with {topic}."
                console.print(f"  Turn {i}: [green]Embedded fact[/green]")
            else:
                user_content = f"Tell me about {topic} considerations for our system."

            user_turn = Turn(content=user_content, turn_type=TurnType.USER)
            await store.add_turn_async(user_turn)

            assistant_turn = Turn(
                content=f"Here's information about {topic}...",
                turn_type=TurnType.ASSISTANT,
            )
            await store.add_turn_async(assistant_turn)

        console.print(f"[green]✓[/green] Added 50 turns with {len(FACTS)} embedded facts\n")

        # Phase 2: Test recall with and without memory
        console.print("[bold]Phase 2: Testing fact recall[/bold]")

        from sunwell.interface.cli.helpers import create_model

        try:
            model = create_model("ollama", "gemma3:4b")
        except Exception as e:
            console.print(f"[red]Failed to create model: {e}[/red]")
            console.print("[yellow]Install gemma3:4b with: ollama pull gemma3:4b[/yellow]")
            return

        results: list[BenchmarkResult] = []

        for fact in FACTS:
            query = fact["query"]
            expected = fact["expected"]

            # Test WITH memory (async for semantic search)
            context = await store.get_context_for_prompt_async(query, max_tokens=4000)
            prompt_with_memory = f"""Based on our conversation history:

{context}

---

Question: {query}

Answer concisely (1-2 sentences):"""

            # Test WITHOUT memory (fresh context only)
            prompt_without_memory = f"""Question: {query}

Answer concisely (1-2 sentences). If you don't know, say "I don't have that information."

Answer:"""

            # Get responses
            try:
                result_with = await model.generate(prompt_with_memory)
                result_without = await model.generate(prompt_without_memory)

                response_with = result_with.content.strip()
                response_without = result_without.content.strip()

                # Check if expected value is in response
                with_correct = expected.lower() in response_with.lower()
                without_correct = expected.lower() in response_without.lower()

                results.append(BenchmarkResult(
                    query=query,
                    expected=expected,
                    response_with_memory=response_with[:100],
                    response_without_memory=response_without[:100],
                    with_memory_correct=with_correct,
                    without_memory_correct=without_correct,
                ))

                status = "[green]✓[/green]" if with_correct else "[red]✗[/red]"
                console.print(f"  {status} {query}")

            except Exception as e:
                console.print(f"  [red]Error: {e}[/red]")
                continue

        # Phase 3: Results
        console.print("\n[bold]Phase 3: Results[/bold]")

        table = Table(title="Memory Quality Results")
        table.add_column("Query", style="cyan")
        table.add_column("Expected", style="green")
        table.add_column("With Memory", style="yellow")
        table.add_column("Without Memory", style="red")

        for r in results:
            with_status = "✓" if r.with_memory_correct else "✗"
            without_status = "✓" if r.without_memory_correct else "✗"
            table.add_row(
                r.query[:30],
                r.expected,
                f"{with_status} {r.response_with_memory[:40]}...",
                f"{without_status} {r.response_without_memory[:40]}...",
            )

        console.print(table)

        # Summary
        with_correct = sum(1 for r in results if r.with_memory_correct)
        without_correct = sum(1 for r in results if r.without_memory_correct)
        total = len(results)

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  With Memory:    {with_correct}/{total} ({100*with_correct/total:.0f}%) correct")
        console.print(f"  Without Memory: {without_correct}/{total} ({100*without_correct/total:.0f}%) correct")

        improvement = with_correct - without_correct
        if improvement > 0:
            console.print(f"\n[green]✅ Memory improves recall by {improvement} questions ({100*improvement/total:.0f}%)[/green]")
        elif improvement == 0:
            console.print(f"\n[yellow]⚠️ No difference in recall[/yellow]")
        else:
            console.print(f"\n[red]❌ Memory decreased recall (unexpected)[/red]")

        # Save results
        results_path = Path("benchmark/results/memory_quality.json")
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(results_path, "w") as f:
            json.dump({
                "with_memory_correct": with_correct,
                "without_memory_correct": without_correct,
                "total": total,
                "improvement_pct": 100 * improvement / total if total > 0 else 0,
                "results": [
                    {
                        "query": r.query,
                        "expected": r.expected,
                        "with_memory_correct": r.with_memory_correct,
                        "without_memory_correct": r.without_memory_correct,
                    }
                    for r in results
                ],
            }, f, indent=2)
        console.print(f"\n[dim]Results saved to {results_path}[/dim]")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
