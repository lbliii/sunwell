"""PersistentMemory — Unified access to all memory stores (RFC-MEMORY).

The PersistentMemory facade provides a single interface to all memory systems:
- SimulacrumStore (conversation history, learnings)
- DecisionMemory (architectural decisions)
- FailureMemory (failed approaches)
- PatternProfile (user/project preferences)
- TeamKnowledgeStore (shared team knowledge, optional)

This is loaded ONCE per workspace and reused across sessions.

Example:
    >>> memory = PersistentMemory.load(workspace)
    >>> ctx = await memory.get_relevant("add caching")
    >>> if ctx.constraints:
    ...     print("Avoid:", ctx.constraints)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.memory.core.types import MemoryContext, SyncResult, TaskMemoryContext

# =============================================================================
# Module-Level Constants (avoid per-call allocation)
# =============================================================================

_CODE_KEYWORDS: frozenset[str] = frozenset({"function", "class", "code", "implement"})
"""Keywords that indicate code-related goals."""

_GENERATION_KEYWORDS: frozenset[str] = frozenset({"generate", "create", "implement"})
"""Keywords that indicate generation/creation tasks."""

if TYPE_CHECKING:
    from sunwell.features.team.store import TeamKnowledgeStore
    from sunwell.knowledge.codebase.decisions import Decision, DecisionMemory
    from sunwell.knowledge.codebase.failures import FailedApproach, FailureMemory
    from sunwell.knowledge.codebase.patterns import PatternProfile
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PersistentMemory:
    """Unified access to all memory stores.

    Owns and coordinates:
    - SimulacrumStore — conversation history, learnings
    - DecisionMemory — architectural decisions
    - FailureMemory — failed approaches
    - PatternProfile — user preferences
    - TeamKnowledgeStore — shared team knowledge (optional)

    Load once per workspace using PersistentMemory.load(workspace).
    """

    workspace: Path
    """Root workspace path."""

    simulacrum: SimulacrumStore | None = None
    """Conversation history and learnings."""

    decisions: DecisionMemory | None = None
    """Architectural decisions."""

    failures: FailureMemory | None = None
    """Failed approaches."""

    patterns: PatternProfile | None = None
    """User/project preferences."""

    team: TeamKnowledgeStore | None = None
    """Shared team knowledge (optional)."""

    _initialized: bool = field(default=False, init=False, repr=False)
    """Whether all stores have been loaded."""

    @classmethod
    def load(
        cls,
        workspace: Path,
        workspace_id: str | None = None,
    ) -> PersistentMemory:
        """Load all memory for workspace.

        Each store loads independently — failure in one doesn't block others.
        Gracefully handles missing directories or corrupted files.

        Args:
            workspace: Root workspace path (project directory)
            workspace_id: Optional workspace container ID for workspace-scoped team memory

        Returns:
            PersistentMemory with all available stores loaded
        """
        workspace = Path(workspace).resolve()

        # Prevent nesting - if workspace IS .sunwell, use parent
        if workspace.name == ".sunwell":
            workspace = workspace.parent
            logger.warning("Workspace was .sunwell directory, using parent: %s", workspace)

        intel_path = workspace / ".sunwell" / "intelligence"
        memory_path = workspace / ".sunwell" / "memory"

        # Load each component independently
        simulacrum = _load_simulacrum(memory_path)
        decisions = _load_decisions(intel_path)
        failures = _load_failures(intel_path)
        patterns = _load_patterns(intel_path)

        # Team knowledge: workspace-scoped if workspace_id provided
        team = _load_team(workspace, workspace_id)

        instance = cls(
            workspace=workspace,
            simulacrum=simulacrum,
            decisions=decisions,
            failures=failures,
            patterns=patterns,
            team=team,
        )
        instance._initialized = True
        return instance

    @classmethod
    def empty(cls, workspace: Path) -> PersistentMemory:
        """Create empty memory for testing or fresh workspaces.

        Args:
            workspace: Root workspace path

        Returns:
            PersistentMemory with empty stores
        """
        workspace = Path(workspace).resolve()

        # Prevent nesting - if workspace IS .sunwell, use parent
        if workspace.name == ".sunwell":
            workspace = workspace.parent
            logger.warning("Workspace was .sunwell directory, using parent: %s", workspace)

        intel_path = workspace / ".sunwell" / "intelligence"

        # Create minimal stores without loading from disk
        from sunwell.knowledge import DecisionMemory, FailureMemory, PatternProfile

        instance = cls(
            workspace=workspace,
            simulacrum=None,  # Optional
            decisions=DecisionMemory(intel_path),
            failures=FailureMemory(intel_path),
            patterns=PatternProfile(),
            team=None,
        )
        instance._initialized = True
        return instance

    @classmethod
    async def load_async(
        cls,
        workspace: Path,
        workspace_id: str | None = None,
    ) -> PersistentMemory:
        """Load all memory for workspace asynchronously.

        Loads stores in parallel using asyncio.to_thread for I/O-bound operations.
        Each store loads independently — failure in one doesn't block others.

        Args:
            workspace: Root workspace path (project directory)
            workspace_id: Optional workspace container ID for workspace-scoped team memory

        Returns:
            PersistentMemory with all available stores loaded
        """
        import asyncio

        workspace = Path(workspace).resolve()
        intel_path = workspace / ".sunwell" / "intelligence"
        memory_path = workspace / ".sunwell" / "memory"

        # Load each component in parallel using asyncio.to_thread
        async def load_simulacrum() -> SimulacrumStore | None:
            return await asyncio.to_thread(_load_simulacrum, memory_path)

        async def load_decisions() -> DecisionMemory | None:
            return await asyncio.to_thread(_load_decisions, intel_path)

        async def load_failures() -> FailureMemory | None:
            return await asyncio.to_thread(_load_failures, intel_path)

        async def load_patterns() -> PatternProfile | None:
            return await asyncio.to_thread(_load_patterns, intel_path)

        async def load_team() -> TeamKnowledgeStore | None:
            return await asyncio.to_thread(_load_team, workspace, workspace_id)

        # Load all in parallel
        simulacrum, decisions, failures, patterns, team = await asyncio.gather(
            load_simulacrum(),
            load_decisions(),
            load_failures(),
            load_patterns(),
            load_team(),
        )

        instance = cls(
            workspace=workspace,
            simulacrum=simulacrum,
            decisions=decisions,
            failures=failures,
            patterns=patterns,
            team=team,
        )
        instance._initialized = True
        return instance

    async def get_relevant(self, goal: str, top_k: int = 5) -> MemoryContext:
        """Get all relevant memory for a goal.

        Queries each store and aggregates results into a MemoryContext
        suitable for injection into planning prompts.

        Args:
            goal: Natural language goal description
            top_k: Maximum items to return per category

        Returns:
            MemoryContext with learnings, constraints, dead_ends, etc.
        """
        constraints: list[str] = []
        dead_ends: list[str] = []
        team_decisions: list[str] = []
        learnings: list[Any] = []
        patterns: list[str] = []

        # Query DecisionMemory for constraints
        if self.decisions:
            try:
                relevant_decisions = await self.decisions.find_relevant_decisions(
                    goal, top_k=top_k
                )
                # Extract constraints from rejected options
                for decision in relevant_decisions:
                    for rejected in decision.rejected:
                        constraints.append(
                            f"{rejected.option}: {rejected.reason}"
                        )
            except Exception as e:
                logger.warning(f"Failed to query decisions: {e}")

        # Query FailureMemory for dead ends
        if self.failures:
            try:
                similar_failures = await self.failures.check_similar_failures(
                    goal, top_k=top_k
                )
                dead_ends = [f.description for f in similar_failures]
            except Exception as e:
                logger.warning(f"Failed to query failures: {e}")

        # Query TeamKnowledgeStore
        if self.team:
            try:
                team_ctx = await self.team.get_relevant_context(goal)
                if team_ctx and hasattr(team_ctx, "decisions"):
                    team_decisions = list(team_ctx.decisions)
            except Exception as e:
                logger.warning(f"Failed to query team knowledge: {e}")

        # Get learnings from SimulacrumStore
        if self.simulacrum:
            try:
                # Use retrieve_for_planning which returns categorized learnings
                planning_ctx = await self.simulacrum.retrieve_for_planning(goal, top_k)
                learnings = list(planning_ctx.all_learnings)[:top_k]
            except Exception as e:
                logger.warning(f"Failed to query simulacrum: {e}")

        # Get patterns from PatternProfile
        if self.patterns:
            patterns = self._get_relevant_patterns(goal)

        return MemoryContext(
            learnings=tuple(learnings),
            facts=(),  # TODO: Add fact extraction
            constraints=tuple(constraints),
            dead_ends=tuple(dead_ends),
            team_decisions=tuple(team_decisions),
            patterns=tuple(patterns),
        )

    def get_task_context(self, task: Any) -> TaskMemoryContext:
        """Get memory relevant to a specific task.

        Args:
            task: Task object with target_path and mode attributes

        Returns:
            TaskMemoryContext with constraints, hazards, and patterns
        """
        constraints: list[str] = []
        hazards: list[str] = []
        patterns: list[str] = []

        target_path = getattr(task, "target_path", None)
        task_mode = getattr(task, "mode", None)

        # Get constraints for path from DecisionMemory
        if self.decisions and target_path:
            try:
                path_constraints = self._get_constraints_for_path(target_path)
                constraints.extend(path_constraints)
            except Exception as e:
                logger.warning(f"Failed to get path constraints: {e}")

        # Get hazards from FailureMemory
        if self.failures and target_path:
            try:
                path_hazards = self._get_hazards_for_path(target_path)
                hazards.extend(path_hazards)
            except Exception as e:
                logger.warning(f"Failed to get path hazards: {e}")

        # Get patterns for task type
        if self.patterns and task_mode:
            try:
                mode_patterns = self._get_patterns_for_mode(task_mode)
                patterns.extend(mode_patterns)
            except Exception as e:
                logger.warning(f"Failed to get mode patterns: {e}")

        return TaskMemoryContext(
            constraints=tuple(constraints),
            hazards=tuple(hazards),
            patterns=tuple(patterns),
        )

    def _get_relevant_patterns(self, goal: str) -> list[str]:
        """Extract relevant patterns from PatternProfile."""
        if not self.patterns:
            return []

        patterns: list[str] = []
        goal_lower = goal.lower()

        # Add naming conventions if goal mentions code
        if any(kw in goal_lower for kw in _CODE_KEYWORDS) and self.patterns.naming_conventions:
            for kind, style in self.patterns.naming_conventions.items():
                patterns.append(f"Use {style} for {kind}")

        # Add docstring style
        if self.patterns.docstring_style != "none":
            patterns.append(f"Use {self.patterns.docstring_style} docstring style")

        # Add type annotation preference
        if self.patterns.type_annotation_level == "all":
            patterns.append("Add type annotations to all functions")
        elif self.patterns.type_annotation_level == "public":
            patterns.append("Add type annotations to public functions")

        # Add formatter/linter if configured
        if self.patterns.formatter:
            patterns.append(f"Format code with {self.patterns.formatter}")
        if self.patterns.linter:
            patterns.append(f"Code must pass {self.patterns.linter}")

        return patterns

    def _get_constraints_for_path(self, target_path: str) -> list[str]:
        """Get constraints relevant to a specific file path."""
        # For now, return empty - this would need path-based filtering
        # in DecisionMemory to work properly
        return []

    def _get_hazards_for_path(self, target_path: str) -> list[str]:
        """Get past failures involving a specific file path."""
        if not self.failures:
            return []

        hazards: list[str] = []
        for failure in self.failures._failures.values():
            # Check if failure context mentions this path
            in_context = target_path in (failure.context or "")
            in_snapshot = failure.code_snapshot and target_path in failure.code_snapshot
            if in_context or in_snapshot:
                hazards.append(f"{failure.description}: {failure.error_message}")

        return hazards[:3]  # Limit to top 3

    def _get_patterns_for_mode(self, task_mode: Any) -> list[str]:
        """Get patterns relevant to a task mode."""
        if not self.patterns:
            return []

        patterns: list[str] = []
        mode_str = str(task_mode).lower() if task_mode else ""

        # Test-related patterns
        if "test" in mode_str:
            patterns.append(f"Test preference: {self.patterns.test_preference}")

        # Error handling patterns
        if any(kw in mode_str for kw in _GENERATION_KEYWORDS):
            patterns.append(f"Error handling: {self.patterns.error_handling}")

        return patterns

    # === RECORD METHODS (during/after execution) ===

    def add_learning(self, learning: Any) -> None:
        """Record a new learning.

        Args:
            learning: Learning object to add (agent or simulacrum Learning)
        """
        if self.simulacrum:
            try:
                dag = self.simulacrum.get_dag()
                # Convert agent Learning to SimLearning if needed
                if not hasattr(learning, "source_turns"):
                    from sunwell.memory.simulacrum.core import Learning as SimLearning

                    # Map agent categories to SimLearning Literal categories
                    category_map = {
                        "type": "pattern",
                        "api": "pattern",
                        "pattern": "pattern",
                        "fix": "fact",
                        "heuristic": "heuristic",
                        "template": "template",
                        "task_completion": "fact",
                        "project": "fact",
                        "preference": "preference",
                    }
                    sim_category = category_map.get(
                        getattr(learning, "category", "pattern"), "pattern"
                    )
                    learning = SimLearning(
                        fact=learning.fact,
                        source_turns=(),
                        confidence=getattr(learning, "confidence", 0.7),
                        category=sim_category,  # type: ignore[arg-type]
                    )
                dag.add_learning(learning)
            except Exception as e:
                logger.warning(f"Failed to add learning: {e}")

    async def add_decision(self, decision: Decision) -> None:
        """Record an architectural decision.

        Args:
            decision: Decision object to record
        """
        if self.decisions:
            try:
                await self.decisions.record_decision(
                    category=decision.category,
                    question=decision.question,
                    choice=decision.choice,
                    rejected=[(r.option, r.reason) for r in decision.rejected],
                    rationale=decision.rationale,
                    context=decision.context,
                    session_id=decision.session_id,
                    confidence=decision.confidence,
                    source=decision.source,
                    metadata=decision.metadata,
                )
            except Exception as e:
                logger.warning(f"Failed to add decision: {e}")

    async def add_failure(self, failure: FailedApproach) -> None:
        """Record what didn't work.

        Args:
            failure: FailedApproach object to record
        """
        if self.failures:
            try:
                await self.failures.record_failure(
                    description=failure.description,
                    error_type=failure.error_type,
                    error_message=failure.error_message,
                    context=failure.context,
                    code=failure.code_snapshot,
                    fix_attempted=failure.fix_attempted,
                    root_cause=failure.root_cause,
                    session_id=failure.session_id,
                )
            except Exception as e:
                logger.warning(f"Failed to add failure: {e}")

    # === SYNC ===

    def sync(self) -> SyncResult:
        """Persist all changes to disk.

        Returns:
            SyncResult with success/failure status for each component
        """
        results: list[tuple[str, bool, str | None]] = []

        # Sync SimulacrumStore
        if self.simulacrum:
            try:
                self.simulacrum.save_session()
                results.append(("simulacrum", True, None))
            except Exception as e:
                logger.error(f"Failed to sync simulacrum: {e}")
                results.append(("simulacrum", False, str(e)))

        # Sync PatternProfile
        if self.patterns:
            try:
                intel_path = self.workspace / ".sunwell" / "intelligence"
                self.patterns.save(intel_path)
                results.append(("patterns", True, None))
            except Exception as e:
                logger.error(f"Failed to sync patterns: {e}")
                results.append(("patterns", False, str(e)))

        # DecisionMemory and FailureMemory auto-save on add
        results.append(("decisions", True, None))
        results.append(("failures", True, None))

        # Sync TeamKnowledgeStore if configured
        if self.team:
            try:
                self.team.sync()
                results.append(("team", True, None))
            except Exception as e:
                logger.error(f"Failed to sync team: {e}")
                results.append(("team", False, str(e)))

        return SyncResult(results=tuple(results))

    # === PROPERTIES ===

    @property
    def learning_count(self) -> int:
        """Number of learnings in memory."""
        if self.simulacrum:
            try:
                return len(self.simulacrum.get_dag().get_learnings())
            except Exception:
                pass
        return 0

    @property
    def decision_count(self) -> int:
        """Number of decisions in memory."""
        if self.decisions:
            return len(self.decisions._decisions)
        return 0

    @property
    def failure_count(self) -> int:
        """Number of recorded failures."""
        if self.failures:
            return len(self.failures._failures)
        return 0

    # =========================================================================
    # RFC-130: Memory-Informed Prefetch
    # =========================================================================

    async def find_similar_goals(
        self,
        goal: str,
        limit: int = 3,
    ) -> list[GoalMemory]:
        """Find similar past goals for memory-informed prefetch.

        RFC-130: Searches memory stores for goals similar to the current one.
        Returns context from successful past executions to inform prefetch
        and guide execution strategy.

        Args:
            goal: Natural language goal description
            limit: Maximum number of similar goals to return

        Returns:
            List of GoalMemory objects from similar past goals
        """
        similar_goals: list[GoalMemory] = []

        # Search SimulacrumStore for similar conversations
        if self.simulacrum:
            try:
                # Get planning context which includes similar learnings
                planning_ctx = await self.simulacrum.retrieve_for_planning(goal, limit)

                # Extract goal-level info from learnings
                for learning in planning_ctx.all_learnings[:limit]:
                    if hasattr(learning, "original_goal"):
                        similar_goals.append(GoalMemory(
                            goal=learning.original_goal,
                            success=learning.success,
                            hot_files=tuple(getattr(learning, "files_touched", [])),
                            learnings=tuple(getattr(learning, "related_learnings", [])),
                            skills_used=tuple(getattr(learning, "skills_used", [])),
                            lens_used=getattr(learning, "lens_used", None),
                            success_pattern=getattr(learning, "success_pattern", None),
                            similarity_score=getattr(learning, "relevance_score", 0.5),
                        ))
            except Exception as e:
                logger.warning(f"Failed to find similar goals in simulacrum: {e}")

        # Search DecisionMemory for goals with relevant decisions
        if self.decisions and len(similar_goals) < limit:
            try:
                relevant_decisions = await self.decisions.find_relevant_decisions(
                    goal, top_k=limit
                )
                for decision in relevant_decisions:
                    if decision.context and "goal:" in decision.context.lower():
                        # Extract goal from context
                        goal_from_decision = decision.context.split("goal:")[-1].strip()[:100]
                        if goal_from_decision:
                            similar_goals.append(GoalMemory(
                                goal=goal_from_decision,
                                success=True,  # Assume success if decision exists
                                hot_files=(),
                                learnings=(),
                                skills_used=(),
                                lens_used=None,
                                success_pattern=f"Decision: {decision.choice}",
                                similarity_score=0.3,
                            ))
            except Exception as e:
                logger.warning(f"Failed to find similar goals in decisions: {e}")

        # Phase 4.2: Search LearningCache for project-level context
        # This captures learnings like "Project uses python" that help inform prefetch
        try:
            from sunwell.memory.core.learning_cache import get_learning_cache

            cache = get_learning_cache(self.workspace)

            # Get project-level learnings
            project_learnings = cache.get_by_category("project", limit=5)

            # Search for goal-related learnings
            if goal:
                goal_keywords = goal.lower().split()[:3]  # First 3 words
                for keyword in goal_keywords:
                    matching = cache.search_facts(keyword, limit=3)
                    for entry in matching:
                        # Create a GoalMemory with just the learning context
                        similar_goals.append(GoalMemory(
                            goal=f"Context: {entry.fact[:50]}",
                            success=True,
                            hot_files=(entry.source_file,) if entry.source_file else (),
                            learnings=(entry.fact,),
                            skills_used=(),
                            lens_used=None,
                            success_pattern=None,
                            similarity_score=entry.confidence * 0.5,  # Lower score for keyword match
                        ))
        except Exception as e:
            logger.debug("Failed to search learning cache: %s", e)

        # Deduplicate and sort by similarity
        seen_goals: set[str] = set()
        unique_goals: list[GoalMemory] = []
        for gm in sorted(similar_goals, key=lambda g: g.similarity_score, reverse=True):
            goal_key = gm.goal[:50].lower()
            if goal_key not in seen_goals:
                seen_goals.add(goal_key)
                unique_goals.append(gm)
                if len(unique_goals) >= limit:
                    break

        return unique_goals


# =============================================================================
# RFC-130: Goal Memory Type
# =============================================================================


@dataclass(frozen=True, slots=True)
class GoalMemory:
    """Memory from a past goal execution (RFC-130).

    Used by memory-informed prefetch to provide context from similar past goals.
    """

    goal: str
    """The goal description."""

    success: bool
    """Whether the goal succeeded."""

    hot_files: tuple[str, ...]
    """Files that were important for this goal."""

    learnings: tuple[str, ...]
    """Learnings extracted during/after execution."""

    skills_used: tuple[str, ...]
    """Skills that were used."""

    lens_used: str | None
    """Lens that was used (if any)."""

    success_pattern: str | None
    """Pattern that made this goal succeed (if known)."""

    similarity_score: float = 0.0
    """How similar this goal is to the query (0.0-1.0)."""


# =============================================================================
# Loader Functions (graceful failure handling)
# =============================================================================


def _load_simulacrum(memory_path: Path) -> SimulacrumStore | None:
    """Load SimulacrumStore, returning None on failure.

    Also loads learnings from the durable journal and syncs them to the DAG.
    """
    try:
        from sunwell.memory.simulacrum.core.store import SimulacrumStore

        if memory_path.exists():
            store = SimulacrumStore(memory_path)
            # Try to load existing session
            sessions = list(memory_path.glob("*.session"))
            if sessions:
                # Load most recent session
                latest = max(sessions, key=lambda p: p.stat().st_mtime)
                store.load_session(latest.stem)

            # Load learnings from journal and sync to DAG
            _sync_journal_to_dag(memory_path, store)

            return store
        return SimulacrumStore(memory_path)
    except Exception as e:
        logger.warning(f"Failed to load SimulacrumStore: {e}")
        return None


def _sync_journal_to_dag(memory_path: Path, store: SimulacrumStore) -> int:
    """Sync learnings from journal to SimulacrumStore DAG.

    This ensures learnings from the journal are available for retrieval.
    Returns the number of learnings synced.
    """
    try:
        from sunwell.memory.core.journal import LearningJournal
        from sunwell.memory.simulacrum.core.turn import Learning as SimLearning

        journal = LearningJournal(memory_path)
        if not journal.exists():
            return 0

        dag = store.get_dag()
        existing_ids = set(dag.learnings.keys())

        synced = 0
        for entry in journal.load_deduplicated().values():
            if entry.id not in existing_ids:
                # Convert journal entry to SimLearning
                sim_learning = SimLearning(
                    fact=entry.fact,
                    source_turns=(),
                    confidence=entry.confidence,
                    category=_map_category(entry.category),
                )
                dag.add_learning(sim_learning)
                synced += 1

        if synced > 0:
            logger.debug("Synced %d learnings from journal to DAG", synced)

        return synced
    except Exception as e:
        logger.debug("Failed to sync journal to DAG: %s", e)
        return 0


def _map_category(category: str) -> str:
    """Map agent learning categories to SimLearning categories."""
    category_map = {
        "type": "pattern",
        "api": "pattern",
        "pattern": "pattern",
        "fix": "fact",
        "heuristic": "heuristic",
        "template": "template",
        "task_completion": "fact",
        "preference": "preference",
        "project": "fact",  # Project-level facts (language, framework)
    }
    return category_map.get(category, "fact")


def _load_decisions(intel_path: Path) -> DecisionMemory | None:
    """Load DecisionMemory, returning None on failure."""
    try:
        from sunwell.knowledge import DecisionMemory

        return DecisionMemory(intel_path)
    except Exception as e:
        logger.warning(f"Failed to load DecisionMemory: {e}")
        return None


def _load_failures(intel_path: Path) -> FailureMemory | None:
    """Load FailureMemory, returning None on failure."""
    try:
        from sunwell.knowledge import FailureMemory

        return FailureMemory(intel_path)
    except Exception as e:
        logger.warning(f"Failed to load FailureMemory: {e}")
        return None


def _load_patterns(intel_path: Path) -> PatternProfile | None:
    """Load PatternProfile, returning None on failure."""
    try:
        from sunwell.knowledge import PatternProfile

        return PatternProfile.load(intel_path)
    except Exception as e:
        logger.warning(f"Failed to load PatternProfile: {e}")
        return None


def _load_team(
    project_root: Path,
    workspace_id: str | None = None,
) -> TeamKnowledgeStore | None:
    """Load TeamKnowledgeStore with workspace or project scope.

    Args:
        project_root: Project root directory.
        workspace_id: Optional workspace ID for workspace-scoped storage.

    Returns:
        TeamKnowledgeStore or None if not configured/available.
    """
    try:
        from sunwell.features.team.store import TeamKnowledgeStore, get_workspace_team_dir

        if workspace_id:
            # Workspace-scoped: check if workspace team dir exists or create it
            team_path = get_workspace_team_dir(workspace_id)
            if team_path.exists() or workspace_id:
                return TeamKnowledgeStore(
                    root=project_root,
                    workspace_id=workspace_id,
                )
        else:
            # Project-scoped (legacy)
            team_path = project_root / ".sunwell" / "team"
            if team_path.exists():
                config_path = team_path / "config.json"
                if config_path.exists():
                    return TeamKnowledgeStore(root=project_root)

        return None
    except Exception as e:
        logger.warning(f"Failed to load TeamKnowledgeStore: {e}")
        return None
