"""Shards - Parallel CPU Helpers for the Naaru Architecture (RFC-019).

Shards are background processes that run in parallel while the main LLM generates.
They overlap I/O-bound operations with compute-bound operations.

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │  ← This module
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

Shard Types:
- **Memory Fetcher**: Query SimulacrumStore for relevant memories
- **Context Preparer**: Load lens, embed query, find related files
- **Quick Checker**: Syntax validation, structural checks
- **Lookahead**: Pre-fetch context for next task in queue
- **Consolidator**: Store learnings after task completion

The key insight: while GPU generates tokens (slow), CPU can do useful work (fast).

Naming Rationale:
    In Naaru lore, shards are fragments of the whole working in parallel.
    Each shard has a specific job that contributes to the greater purpose.

Example:
    >>> from sunwell.naaru.shards import Shard, ShardPool, ShardType
    >>> from sunwell.naaru.convergence import Convergence
    >>>
    >>> convergence = Convergence()
    >>> pool = ShardPool(convergence=convergence)
    >>>
    >>> # While LLM generates, shards prepare context
    >>> await pool.prepare_for_task({
    ...     "description": "Add error handling",
    ...     "category": "error_handling",
    ... })
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sunwell.naaru.convergence import Convergence, Slot, SlotSource


class ShardType(Enum):
    """Types of Shards (parallel helpers)."""

    MEMORY_FETCHER = "memory_fetcher"
    CONTEXT_PREPARER = "context_preparer"
    QUICK_CHECKER = "quick_checker"
    LOOKAHEAD = "lookahead"
    CONSOLIDATOR = "consolidator"
    THOUGHT_LEXER = "thought_lexer"  # RFC-028: Analyzes task → rotation plan


@dataclass
class Shard:
    """A background helper that runs while the main LLM thinks.

    Each shard has a specific job:
    - memory_fetcher: Query SimulacrumStore for relevant memories
    - context_preparer: Load lenses, embed queries, prepare context
    - quick_checker: Run structural validation (syntax, imports)
    - lookahead: Look at task queue, pre-fetch what's needed next
    - consolidator: After task completion, store learnings

    Example:
        >>> shard = Shard(
        ...     shard_type=ShardType.MEMORY_FETCHER,
        ...     convergence=convergence,
        ...     simulacrum_store=my_store,
        ... )
        >>>
        >>> result = await shard.run({"description": "Add tests", "category": "testing"})
    """

    shard_type: ShardType
    convergence: Convergence

    # Resources (injected)
    simulacrum_store: Any = None
    embedding_model: Any = None
    lens_loader: Any = None

    async def run(self, task: dict, context: dict | None = None) -> dict:
        """Run the shard's job and put results in convergence.

        Args:
            task: The task to prepare for
            context: Optional additional context

        Returns:
            Dict with results from the shard's job
        """
        if self.shard_type == ShardType.MEMORY_FETCHER:
            return await self._fetch_memories(task)
        elif self.shard_type == ShardType.CONTEXT_PREPARER:
            return await self._prepare_context(task)
        elif self.shard_type == ShardType.QUICK_CHECKER:
            return await self._quick_check(task)
        elif self.shard_type == ShardType.LOOKAHEAD:
            return await self._lookahead(task, context)
        elif self.shard_type == ShardType.CONSOLIDATOR:
            return await self._consolidate(task, context)

        return {}

    async def _fetch_memories(self, task: dict) -> dict:
        """Fetch relevant memories from SimulacrumStore.

        This shard queries the memory system for relevant context
        based on the task description and category.
        """
        task.get("description", "")
        category = task.get("category", "")

        memories = []

        if self.simulacrum_store:
            # In production: query SimulacrumStore
            # memories = await self.simulacrum_store.get_relevant(description)
            pass

        # Simulated domain-specific memories
        memory_bank = {
            "error_handling": [
                "Use specific exception types, not bare except",
                "Always include context in error messages",
                "Log errors with traceback for debugging",
                "Implement proper cleanup/rollback on failure",
            ],
            "testing": [
                "Use pytest fixtures for setup/teardown",
                "Test edge cases: None, empty, boundary values",
                "Mock external dependencies",
                "Use parametrize for multiple test cases",
            ],
            "documentation": [
                "Follow Google/NumPy docstring style",
                "Include examples in docstrings",
                "Document exceptions that can be raised",
                "Keep docstrings concise but complete",
            ],
            "code_quality": [
                "Use type hints for public functions",
                "Keep functions under 20 lines",
                "Prefer composition over inheritance",
                "Follow PEP 8 style guidelines",
            ],
        }

        memories = memory_bank.get(category, [
            "Write clean, readable code",
            "Handle edge cases",
            "Follow Python best practices",
        ])

        # Store in convergence
        slot = Slot(
            id=f"memories:{category}",
            content=memories,
            relevance=0.9,
            source=SlotSource.MEMORY_FETCHER,
        )
        await self.convergence.add(slot)

        return {"memories": memories}

    async def _prepare_context(self, task: dict) -> dict:
        """Prepare context: load lens, embed query, gather resources.

        This shard prepares all the context needed for generation:
        - Select appropriate lens file
        - Generate embeddings for semantic search
        - Find related files in the codebase
        """
        description = task.get("description", "")
        category = task.get("category", "")

        context = {
            "lens": None,
            "embedding": None,
            "related_files": [],
        }

        # Select appropriate lens
        lens_map = {
            "testing": "team-qa.lens",
            "code_quality": "code-reviewer.lens",
            "documentation": "tech-writer.lens",
            "error_handling": "code-reviewer.lens",
        }

        context["lens_file"] = lens_map.get(category, "helper.lens")

        # Generate embedding if model available
        if self.embedding_model and description:
            with contextlib.suppress(Exception):
                context["embedding"] = await self.embedding_model.embed_single(description)

        # Store in convergence
        slot = Slot(
            id=f"context:{category}",
            content=context,
            relevance=0.95,
            source=SlotSource.CONTEXT_PREPARER,
        )
        await self.convergence.add(slot)

        return context

    async def _quick_check(self, task: dict) -> dict:
        """Quick structural check without LLM.

        This shard performs fast validation:
        - Syntax checking via compile()
        - Import detection
        - Docstring presence
        - Basic code quality heuristics
        """
        code = task.get("code", task.get("diff", ""))

        checks = {
            "has_code": len(code.strip()) > 0,
            "has_function": "def " in code,
            "has_class": "class " in code,
            "has_return": "return " in code or "yield " in code,
            "has_docstring": '"""' in code or "'''" in code,
            "no_syntax_error": True,
        }

        # Try to parse for syntax errors
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            checks["no_syntax_error"] = False
            checks["syntax_error"] = str(e)

        # Calculate quick score
        score = sum([
            2.0 if checks["has_code"] else 0,
            2.0 if checks["has_function"] or checks["has_class"] else 0,
            1.5 if checks["has_return"] else 0,
            1.5 if checks["has_docstring"] else 0,
            3.0 if checks["no_syntax_error"] else -5.0,
        ])

        result = {
            "checks": checks,
            "quick_score": max(0, min(10, score)),
            "obvious_reject": score < 0,  # Syntax error = instant reject
            "obvious_approve": score >= 7,  # All checks pass
        }

        # Store in convergence
        slot = Slot(
            id="quick_check",
            content=result,
            relevance=1.0,  # High relevance - needed for decision
            source=SlotSource.QUICK_CHECKER,
        )
        await self.convergence.add(slot)

        return result

    async def _lookahead(self, task: dict, context: dict | None = None) -> dict:
        """Look ahead at the task queue, pre-fetch for next tasks.

        This shard anticipates what's coming next and pre-fetches context
        so it's ready when the model finishes the current task.
        """
        queue = context.get("task_queue", []) if context else []

        prefetched = []

        # Pre-fetch for next 2 tasks in queue
        for next_task in queue[:2]:
            next_desc = next_task.get("description", "")
            next_cat = next_task.get("category", "")

            # Store pre-fetch marker
            slot = Slot(
                id=f"prefetch:{next_cat}",
                content={"description": next_desc, "ready": False},
                relevance=0.5,  # Lower relevance than current task
                source=SlotSource.LOOKAHEAD,
                ready=False,
            )
            await self.convergence.add(slot)
            prefetched.append(next_cat)

        return {"prefetched": prefetched}

    async def _consolidate(self, task: dict, context: dict | None = None) -> dict:
        """After task completion, consolidate learnings.

        This shard captures what was learned during the task
        for potential storage in SimulacrumStore.
        """
        result = context.get("result", {}) if context else {}

        learnings = []

        # What did we learn from this task?
        if result.get("approved"):
            learnings.append({
                "type": "success_pattern",
                "category": task.get("category"),
                "key": "approved",
            })
        elif result.get("rejected_reason"):
            learnings.append({
                "type": "failure_pattern",
                "category": task.get("category"),
                "reason": result.get("rejected_reason"),
            })

        # Store in convergence for potential SimulacrumStore update
        if learnings:
            slot = Slot(
                id="learnings",
                content=learnings,
                relevance=0.3,  # Lower priority than active task
                source=SlotSource.CONSOLIDATOR,
            )
            await self.convergence.add(slot)

        return {"learnings": learnings}


class ShardPool:
    """Pool of Shards that run in parallel.

    The ShardPool coordinates multiple shards to prepare context
    while the main LLM generates. This overlaps I/O with compute.

    Example:
        >>> pool = ShardPool(convergence=convergence)
        >>>
        >>> # While main LLM thinks, shards gather context
        >>> await pool.run_parallel([
        ...     (ShardType.MEMORY_FETCHER, task),
        ...     (ShardType.CONTEXT_PREPARER, task),
        ...     (ShardType.QUICK_CHECKER, {"code": proposal}),
        ... ])
        >>>
        >>> # Main LLM can now use pre-fetched context
        >>> memories = await convergence.get("memories:error_handling")
    """

    def __init__(
        self,
        convergence: Convergence,
        simulacrum_store: Any = None,
        embedding_model: Any = None,
        lens_loader: Any = None,
    ):
        """Initialize the shard pool.

        Args:
            convergence: Shared working memory
            simulacrum_store: Optional SimulacrumStore for memory queries
            embedding_model: Optional model for semantic embeddings
            lens_loader: Optional loader for lens files
        """
        self.convergence = convergence
        self.shards = {
            st: Shard(
                shard_type=st,
                convergence=convergence,
                simulacrum_store=simulacrum_store,
                embedding_model=embedding_model,
                lens_loader=lens_loader,
            )
            for st in ShardType
        }
        self._stats = {
            "jobs_completed": 0,
            "parallel_runs": 0,
        }

    async def run_parallel(
        self,
        jobs: list[tuple[ShardType, dict, dict | None]],
    ) -> list[dict]:
        """Run multiple shards in parallel.

        Args:
            jobs: List of (shard_type, task, context) tuples

        Returns:
            List of results from each shard
        """
        tasks = [
            self.shards[st].run(task, context)
            for st, task, context in jobs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        self._stats["parallel_runs"] += 1
        self._stats["jobs_completed"] += len([r for r in results if not isinstance(r, Exception)])

        return results

    async def prepare_for_task(self, task: dict) -> dict:
        """Run all relevant shards to prepare for a task.

        This is the main entry point - while the LLM generates,
        call this to have shards pre-fetch everything needed.

        Args:
            task: The task to prepare for

        Returns:
            Summary of what's now in convergence
        """
        jobs = [
            (ShardType.MEMORY_FETCHER, task, None),
            (ShardType.CONTEXT_PREPARER, task, None),
        ]

        await self.run_parallel(jobs)

        # Return summary of what's in convergence
        ready_slots = await self.convergence.get_all_ready()
        return {
            "slots_ready": len(ready_slots),
            "slot_ids": [s.id for s in ready_slots],
        }

    async def quick_validate(self, proposal: dict) -> dict:
        """Run quick validation shard.

        Args:
            proposal: The proposal to validate

        Returns:
            Quick validation results
        """
        return await self.shards[ShardType.QUICK_CHECKER].run(proposal)

    async def consolidate_learnings(self, task: dict, result: dict) -> dict:
        """Run consolidation shard after task completion.

        Args:
            task: The completed task
            result: The task result

        Returns:
            Consolidation results
        """
        return await self.shards[ShardType.CONSOLIDATOR].run(
            task, {"result": result}
        )

    async def prefetch_for_queue(self, task_queue: list[dict]) -> dict:
        """Pre-fetch context for upcoming tasks.

        Args:
            task_queue: List of upcoming tasks

        Returns:
            Prefetch results
        """
        return await self.shards[ShardType.LOOKAHEAD].run(
            {}, {"task_queue": task_queue}
        )

    def get_stats(self) -> dict:
        """Get shard pool statistics."""
        return {
            **self._stats,
            "convergence_stats": self.convergence.get_stats(),
        }


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate the Shard pool."""
    print("=" * 60)
    print("Shards (Parallel Helpers) Demo")
    print("=" * 60)

    # Create convergence and shard pool
    convergence = Convergence(capacity=7)
    pool = ShardPool(convergence=convergence)

    print(f"\nShard types: {[st.value for st in ShardType]}")
    print()

    # Simulate preparing for a task
    task = {
        "description": "Add comprehensive error handling to the user service",
        "category": "error_handling",
    }

    print(f"📋 Task: {task['description']}")
    print(f"   Category: {task['category']}")
    print()

    print("🔧 Running shards in parallel...")
    result = await pool.prepare_for_task(task)

    print(f"\n📊 Convergence now has {result['slots_ready']} ready slots:")
    for slot_id in result['slot_ids']:
        slot = await convergence.get(slot_id)
        if slot:
            content_preview = str(slot.content)[:60] + "..." if len(str(slot.content)) > 60 else str(slot.content)
            print(f"   - {slot_id}: {content_preview}")

    # Test quick validation
    print("\n⚡ Quick validation check...")
    code_proposal = {
        "diff": '''
def handle_error(error: Exception) -> str:
    """Handle an error and return a message.

    Args:
        error: The exception to handle

    Returns:
        User-friendly error message
    """
    return f"An error occurred: {error}"
'''
    }

    check_result = await pool.quick_validate(code_proposal)
    print(f"   Quick score: {check_result['quick_score']}/10")
    print(f"   Checks passed: {sum(1 for v in check_result['checks'].values() if v)}/{len(check_result['checks'])}")

    print("\n📈 Pool Statistics:")
    stats = pool.get_stats()
    print(f"   Jobs completed: {stats['jobs_completed']}")
    print(f"   Parallel runs: {stats['parallel_runs']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
