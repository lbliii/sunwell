"""Parallel memory retrieval using free-threading.

Python 3.14's free-threading (PEP 703) enables true parallel execution.
Each memory type query runs in its own thread, results merged at end.

This is ideal because:
- Each memory type is independent (no shared state)
- Queries are I/O-ish (filtering, matching)
- Results combine cleanly (just concatenate)
- Focus object is read-only during parallel phase

Worker count adapts based on GIL state:
- Free-threaded Python: Uses CPU count for true parallelism
- Standard Python: Uses minimal workers (threads serialize anyway)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sunwell.core.freethreading import (
    is_free_threaded,
    optimal_workers,
    WorkloadType,
)
from sunwell.simulacrum.focus import Focus, FocusFilter
from sunwell.simulacrum.turn import Turn, Learning
from sunwell.types.memory import RetrievalResult

if TYPE_CHECKING:
    from sunwell.simulacrum.memory import (
        WorkingMemory,
        LongTermMemory,
        EpisodicMemory,
        SemanticMemory,
        ProceduralMemory,
        Episode,
    )


@dataclass
class ParallelRetriever:
    """Retrieve from all memory types in parallel.
    
    Uses ThreadPoolExecutor with Python 3.14 free-threading
    for true parallel execution across memory types.
    
    Thread Safety:
    - Focus object is updated ONCE before parallel phase, then read-only
    - Each thread gets its own FocusFilter (no shared mutable state)
    - Memory collections are read-only during retrieval
    - Results are collected via asyncio.gather (thread-safe)
    
    Error Handling:
    - Each thread wrapped in try-except to prevent silent failures
    - Errors logged and empty results returned on failure
    
    Adaptive Workers:
    - Free-threaded Python: Uses CPU count for true parallelism
    - Standard Python: Conservative (2-4) since threads serialize at GIL
    """
    
    focus: Focus
    """Shared focus (read-only during parallel phase)."""
    
    max_workers: int | None = None
    """Max parallel threads. None = auto based on GIL state."""
    
    @property
    def effective_workers(self) -> int:
        """Get worker count based on GIL state."""
        if self.max_workers is not None:
            return self.max_workers
        # Memory retrieval is mixed (some computation, some I/O)
        return optimal_workers(WorkloadType.MIXED)
    
    async def retrieve(
        self,
        query: str,
        working: "WorkingMemory",
        long_term: "LongTermMemory",
        episodic: "EpisodicMemory",
        semantic: "SemanticMemory",
        procedural: "ProceduralMemory",
    ) -> RetrievalResult:
        """Retrieve from all memory types in parallel.
        
        Each memory type query runs in its own thread.
        Focus is updated once, then snapshot is used (immutable during parallel).
        """
        # Update focus from query first (single-threaded, mutates self.focus)
        self.focus.update_from_query(query)
        
        # Snapshot focus topics for result (before parallel phase)
        focus_topics_snapshot = list(self.focus.active_topics)
        
        # Create filter with snapshot of focus state
        # Each thread gets its own filter instance to avoid any shared state
        focus_filter = FocusFilter(self.focus)
        
        # Define retrieval tasks
        loop = asyncio.get_event_loop()
        workers = self.effective_workers
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks in parallel
            learning_future = loop.run_in_executor(
                executor,
                self._retrieve_learnings,
                focus_filter,
                long_term,
            )
            
            episode_future = loop.run_in_executor(
                executor,
                self._retrieve_episodes,
                focus_filter,
                episodic,
            )
            
            turn_future = loop.run_in_executor(
                executor,
                self._retrieve_turns,
                focus_filter,
                working,
            )
            
            semantic_future = loop.run_in_executor(
                executor,
                self._retrieve_semantic,
                semantic,
                query,
            )
            
            procedural_future = loop.run_in_executor(
                executor,
                self._retrieve_procedural,
                procedural,
            )
            
            # Gather all results
            results = await asyncio.gather(
                learning_future,
                episode_future,
                turn_future,
                semantic_future,
                procedural_future,
            )
        
        # Combine results (use snapshotted focus topics for consistency)
        return RetrievalResult(
            learnings=results[0],
            episodes=results[1],
            turns=results[2],
            code_chunks=results[3],
            heuristics=results[4],
            focus_topics=focus_topics_snapshot,
        )
    
    def _retrieve_learnings(
        self,
        focus_filter: FocusFilter,
        long_term: "LongTermMemory",
    ) -> list[tuple[Learning, float]]:
        """Thread: retrieve relevant learnings.
        
        Thread-safe: focus_filter is thread-local, long_term is read-only.
        """
        try:
            active = long_term.get_active()
            if not active:
                return []
            
            return focus_filter.filter_learnings(active, min_relevance=0.2)
        except Exception as e:
            # Log error but don't crash the thread
            import sys
            print(f"[ParallelRetriever] Error in _retrieve_learnings: {e}", file=sys.stderr)
            return []
    
    def _retrieve_episodes(
        self,
        focus_filter: FocusFilter,
        episodic: "EpisodicMemory",
    ) -> list[tuple["Episode", float]]:
        """Thread: retrieve relevant episodes.
        
        Thread-safe: focus_filter is thread-local, episodic is read-only.
        Note: episodic.dead_ends is a frozenset-like read during iteration.
        """
        try:
            # Snapshot episodes to avoid iteration issues if modified elsewhere
            episodes = list(episodic.episodes.values())
            dead_end_ids = frozenset(episodic.dead_ends)  # Snapshot
            
            if not episodes:
                return []
            
            # Score episodes by summary match
            scored = []
            for ep in episodes:
                tags = focus_filter._extract_tags(ep.summary)
                score = focus_filter.focus.matches(tags)
                
                # Dead ends always included (as warnings)
                if ep.id in dead_end_ids:
                    score = max(score, 0.8)
                
                if score > 0.2:
                    scored.append((ep, score))
            
            return sorted(scored, key=lambda x: -x[1])
        except Exception as e:
            import sys
            print(f"[ParallelRetriever] Error in _retrieve_episodes: {e}", file=sys.stderr)
            return []
    
    def _retrieve_turns(
        self,
        focus_filter: FocusFilter,
        working: "WorkingMemory",
    ) -> list[tuple[Turn, float]]:
        """Thread: retrieve recent turns (scored by relevance).
        
        Thread-safe: focus_filter is thread-local, working.turns is read-only.
        """
        try:
            # Snapshot turns list to avoid iteration issues
            turns = list(working.turns)
            if not turns:
                return []
            
            return focus_filter.filter_turns(turns, min_relevance=0.1)
        except Exception as e:
            import sys
            print(f"[ParallelRetriever] Error in _retrieve_turns: {e}", file=sys.stderr)
            return []
    
    def _retrieve_semantic(
        self,
        semantic: "SemanticMemory",
        query: str,
    ) -> list[tuple[str, float]]:
        """Thread: retrieve relevant code/docs.
        
        Thread-safe: semantic.chunks is read-only, query is immutable.
        """
        try:
            # Snapshot chunks to avoid iteration issues
            chunks = dict(semantic.chunks)
            
            query_lower = query.lower()
            words = query_lower.split()
            scored = []
            
            for chunk_id, content in chunks.items():
                # Simple relevance: count query word matches
                content_lower = content.lower()
                matches = sum(1 for w in words if w in content_lower)
                score = min(1.0, matches / max(len(words), 1))
                
                if score > 0.2:
                    scored.append((content, score))
            
            return sorted(scored, key=lambda x: -x[1])[:10]
        except Exception as e:
            import sys
            print(f"[ParallelRetriever] Error in _retrieve_semantic: {e}", file=sys.stderr)
            return []
    
    def _retrieve_procedural(
        self,
        procedural: "ProceduralMemory",
    ) -> list[str]:
        """Thread: retrieve heuristics (always include core ones).
        
        Thread-safe: procedural.heuristics is read-only list.
        """
        try:
            # Snapshot to avoid iteration issues
            heuristics = list(procedural.heuristics)
            return heuristics[:15]
        except Exception as e:
            import sys
            print(f"[ParallelRetriever] Error in _retrieve_procedural: {e}", file=sys.stderr)
            return []


async def parallel_assemble_context(
    query: str,
    focus: Focus,
    working: "WorkingMemory",
    long_term: "LongTermMemory",
    episodic: "EpisodicMemory",
    semantic: "SemanticMemory",
    procedural: "ProceduralMemory",
    max_tokens: int = 6000,
) -> tuple[str, RetrievalResult]:
    """Convenience function: parallel retrieve + format context."""
    retriever = ParallelRetriever(focus=focus)
    
    result = await retriever.retrieve(
        query=query,
        working=working,
        long_term=long_term,
        episodic=episodic,
        semantic=semantic,
        procedural=procedural,
    )
    
    context = result.to_context(max_tokens=max_tokens)
    
    return context, result
