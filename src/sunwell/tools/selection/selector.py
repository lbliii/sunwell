"""Multi-signal tool selector for intelligent tool disclosure.

Combines multiple orthogonal signals to select the most relevant tools:
1. DAG-based workflow knowledge (tool progressions)
2. Learned patterns from LearningStore
3. Progressive trust from ProgressivePolicy
4. Project type filtering
5. Lens tool profiles (optional)
6. Dead end avoidance
7. Semantic relevance (embedding-based)
8. Planned tools (plan-then-execute pattern)

The goal is to reduce tool count from 40+ to 5-15 relevant tools,
dramatically improving accuracy for small models.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.knowledge.indexing.project_type import ProjectType, detect_project_type
from sunwell.tools.selection.embedding import ToolEmbeddingIndex
from sunwell.tools.selection.graph import DEFAULT_TOOL_DAG, ToolDAG
from sunwell.tools.selection.planner import ToolPlan, plan_heuristic

if TYPE_CHECKING:
    from sunwell.agent.learning.store import LearningStore
    from sunwell.foundation.core.lens import Lens
    from sunwell.models import Tool
    from sunwell.tools.progressive.enablement import ProgressivePolicy

logger = logging.getLogger(__name__)


# =============================================================================
# SELECTION TRACING
# =============================================================================


@dataclass(frozen=True, slots=True)
class ToolScore:
    """Score breakdown for a single tool.

    Attributes:
        name: Tool name
        total_score: Final combined score
        signals: Which signals contributed (signal_name -> points)
    """

    name: str
    total_score: float
    signals: tuple[tuple[str, float], ...]  # Immutable signal contributions

    def signal_dict(self) -> dict[str, float]:
        """Convert signals to dict for easier inspection."""
        return dict(self.signals)

    def active_signals(self) -> list[str]:
        """Return list of signals that contributed (non-zero)."""
        return [name for name, score in self.signals if score > 0]


@dataclass(frozen=True, slots=True)
class SelectionTrace:
    """Complete trace of a tool selection decision.

    Provides full visibility into which signals contributed to the final
    tool ranking and filtering decisions.

    Attributes:
        query: The user query
        task_type: Classified task type
        total_available: Total tools before filtering
        dag_available: Tools allowed by DAG
        project_filtered: Tools after project type filter
        planned_tools: Tools from planning step
        semantic_hits: Tools with high semantic relevance
        dead_ends_removed: Tools removed as dead ends
        final_count: Final selected tool count
        top_tools: Detailed scores for top tools
        winner: The highest-ranked tool
        winner_signals: Which signals contributed to winner
    """

    query: str
    task_type: str
    total_available: int
    dag_available: int
    project_filtered: int
    planned_tools: tuple[str, ...]
    semantic_hits: tuple[str, ...]
    dead_ends_removed: tuple[str, ...]
    final_count: int
    top_tools: tuple[ToolScore, ...]
    winner: str
    winner_signals: tuple[str, ...]

    def summary(self) -> str:
        """Generate a human-readable summary of the selection."""
        lines = [
            f"Query: {self.query[:50]}{'...' if len(self.query) > 50 else ''}",
            f"Tools: {self.total_available} → {self.final_count} ({self.final_count/self.total_available*100:.0f}%)",
            f"Winner: {self.winner} (signals: {', '.join(self.winner_signals) or 'base'})",
        ]
        if self.planned_tools:
            lines.append(f"Planned: {', '.join(self.planned_tools[:5])}")
        if self.semantic_hits:
            lines.append(f"Semantic: {', '.join(self.semantic_hits[:5])}")
        return "\n".join(lines)

    def detailed_breakdown(self) -> str:
        """Generate detailed breakdown of top tools and their scores."""
        lines = [
            "=" * 60,
            f"SELECTION TRACE: {self.query[:40]}",
            "=" * 60,
            "",
            "FILTERING:",
            f"  Total available: {self.total_available}",
            f"  After DAG:       {self.dag_available}",
            f"  After project:   {self.project_filtered}",
            f"  Final count:     {self.final_count}",
            "",
        ]

        if self.planned_tools:
            lines.append(f"PLANNED TOOLS: {', '.join(self.planned_tools)}")
        if self.semantic_hits:
            lines.append(f"SEMANTIC HITS: {', '.join(self.semantic_hits)}")
        if self.dead_ends_removed:
            lines.append(f"DEAD ENDS:     {', '.join(self.dead_ends_removed)}")

        lines.extend([
            "",
            "TOP TOOLS (with signal breakdown):",
        ])

        for i, ts in enumerate(self.top_tools[:10], 1):
            active = ts.active_signals()
            signal_str = ", ".join(f"{s}={ts.signal_dict()[s]:.0f}" for s in active) if active else "base"
            lines.append(f"  {i}. {ts.name}: {ts.total_score:.0f} [{signal_str}]")

        lines.extend(["", "=" * 60])
        return "\n".join(lines)


# =============================================================================
# PROJECT TYPE TO TOOL MAPPING
# =============================================================================

# Tools relevant for each project type
PROJECT_TYPE_TOOLS: dict[ProjectType, frozenset[str]] = {
    ProjectType.CODE: frozenset({
        # File operations
        "list_files", "search_files", "find_files", "read_file",
        "edit_file", "write_file", "patch_file", "mkdir",
        "delete_file", "rename_file", "copy_file",
        "undo_file", "list_backups", "restore_file",
        # Git (essential for code)
        "git_status", "git_diff", "git_log", "git_blame", "git_show", "git_info",
        "git_add", "git_restore", "git_commit", "git_branch", "git_checkout",
        "git_stash", "git_reset", "git_merge", "git_init",
        # Shell (build, test, etc.)
        "run_command",
        # Expertise
        "get_expertise", "verify_against_expertise", "list_expertise_areas",
    }),
    ProjectType.PROSE: frozenset({
        # File operations (no shell for prose)
        "list_files", "search_files", "find_files", "read_file",
        "edit_file", "write_file", "patch_file", "mkdir",
        "delete_file", "rename_file", "copy_file",
        "undo_file", "list_backups", "restore_file",
        # Git (still useful for version control)
        "git_status", "git_diff", "git_log", "git_add", "git_commit",
        # Research
        "web_search", "web_fetch",
        # Expertise
        "get_expertise", "verify_against_expertise", "list_expertise_areas",
    }),
    ProjectType.SCRIPT: frozenset({
        # File operations
        "list_files", "search_files", "find_files", "read_file",
        "edit_file", "write_file", "patch_file", "mkdir",
        "delete_file", "rename_file", "copy_file",
        "undo_file", "list_backups", "restore_file",
        # Git
        "git_status", "git_diff", "git_log", "git_add", "git_commit",
        # Expertise
        "get_expertise", "verify_against_expertise", "list_expertise_areas",
    }),
    ProjectType.DOCS: frozenset({
        # File operations
        "list_files", "search_files", "find_files", "read_file",
        "edit_file", "write_file", "patch_file", "mkdir",
        "delete_file", "rename_file", "copy_file",
        "undo_file", "list_backups", "restore_file",
        # Git
        "git_status", "git_diff", "git_log", "git_add", "git_commit",
        # Shell (for building docs)
        "run_command",
        # Research
        "web_search", "web_fetch",
        # Expertise
        "get_expertise", "verify_against_expertise", "list_expertise_areas",
    }),
    ProjectType.MIXED: frozenset(),  # Empty means all tools allowed
    ProjectType.UNKNOWN: frozenset(),  # Empty means all tools allowed
}

# Git tools to filter out for non-git projects
GIT_TOOLS: frozenset[str] = frozenset({
    "git_status", "git_diff", "git_log", "git_blame", "git_show", "git_info",
    "git_add", "git_restore", "git_commit", "git_branch", "git_checkout",
    "git_stash", "git_reset", "git_merge", "git_init",
})


# =============================================================================
# MODEL-ADAPTIVE LIMITS
# =============================================================================


def get_tool_limit_for_model(context_window: int | None, model_tier: str | None) -> int | None:
    """Get the maximum tool count based on model capabilities.

    Args:
        context_window: Model's context window size (tokens)
        model_tier: Model tier (small, medium, large, etc.)

    Returns:
        Maximum tool count, or None for no limit
    """
    # Small models get strict limits
    if model_tier == "small" or (context_window and context_window < 8000):
        return 5

    # Medium models get moderate limits
    if context_window and context_window < 32000:
        return 15

    # Large models get no artificial limit
    return None


# =============================================================================
# MULTI-SIGNAL TOOL SELECTOR
# =============================================================================


@dataclass(slots=True)
class MultiSignalToolSelector:
    """Combines multiple signals for intelligent tool selection.

    This selector dramatically reduces tool count for small models by
    combining workflow knowledge (DAG), learned patterns, trust levels,
    project context, lens profiles, semantic relevance, and tool planning.

    Thread-safe: All mutable state is accessed via thread-safe methods
    on the underlying stores.

    Attributes:
        dag: Tool DAG for workflow-based progressive disclosure
        workspace_root: Path to workspace for project type detection
        progressive_policy: Progressive trust policy (optional)
        learning_store: Learning store for pattern suggestions (optional)
        lens: Active lens for tool profiles (optional)
        max_tools: Hard limit on tool count (for small models)
        enable_dag: Whether to use DAG-based filtering
        enable_learned_boost: Whether to boost learned patterns
        enable_project_filter: Whether to filter by project type
        enable_semantic: Whether to use semantic embedding-based ranking
        enable_planning: Whether to use plan-then-execute pattern
        semantic_boost_weight: Score boost for semantic matches (0-100)
        planning_boost_weight: Score boost for planned tools (0-100)
    """

    dag: ToolDAG = field(default_factory=lambda: DEFAULT_TOOL_DAG)
    workspace_root: Path | None = None

    # Optional signal providers
    progressive_policy: "ProgressivePolicy | None" = None
    learning_store: "LearningStore | None" = None
    lens: "Lens | None" = None

    # Configuration
    max_tools: int | None = None
    enable_dag: bool = True
    enable_learned_boost: bool = True
    enable_project_filter: bool = True
    enable_semantic: bool = True
    enable_planning: bool = True  # Plan-then-execute pattern
    semantic_boost_weight: int = 40  # Score boost for semantic matches
    planning_boost_weight: int = 60  # Score boost for planned tools (higher than semantic)

    # Cached state
    _project_type: ProjectType | None = field(default=None, init=False)
    _has_git: bool | None = field(default=None, init=False)
    _embedding_index: ToolEmbeddingIndex | None = field(default=None, init=False)
    _current_plan: ToolPlan | None = field(default=None, init=False)

    def _detect_project_context(self) -> None:
        """Detect project type and git presence (cached)."""
        if self.workspace_root is None:
            self._project_type = ProjectType.UNKNOWN
            self._has_git = True  # Assume git unless proven otherwise
            return

        if self._project_type is None:
            self._project_type = detect_project_type(self.workspace_root)

        if self._has_git is None:
            git_dir = self.workspace_root / ".git"
            self._has_git = git_dir.exists()

    def _get_project_tools(self) -> frozenset[str]:
        """Get tools relevant for the current project type.

        Returns:
            Set of tool names, or empty set (meaning all tools allowed)
        """
        if not self.enable_project_filter:
            return frozenset()  # No filtering

        self._detect_project_context()

        project_type = self._project_type or ProjectType.UNKNOWN
        tools = PROJECT_TYPE_TOOLS.get(project_type, frozenset())

        # Filter out git tools if not a git repo
        if not self._has_git:
            tools = tools - GIT_TOOLS

        return tools

    def _get_learned_suggestions(self, task_type: str) -> frozenset[str]:
        """Get tools suggested by learned patterns.

        Args:
            task_type: Current task classification

        Returns:
            Set of suggested tool names
        """
        if not self.enable_learned_boost or self.learning_store is None:
            return frozenset()

        suggested = self.learning_store.suggest_tools(task_type, limit=5)
        return frozenset(suggested)

    def _get_dead_end_tools(self, query: str) -> frozenset[str]:
        """Get tools associated with dead ends (to suppress).

        Args:
            query: Current user query

        Returns:
            Set of tool names to suppress
        """
        if self.learning_store is None:
            return frozenset()

        # Get dead ends relevant to this query
        dead_ends = self.learning_store.get_dead_ends_for(query)

        # Extract tool names mentioned in dead end approaches
        # This is a heuristic - dead ends don't explicitly track tools
        suppressed: set[str] = set()
        all_dag_tools = self.dag.get_all_tools()

        for de in dead_ends:
            approach_lower = de.approach.lower()
            for tool_name in all_dag_tools:
                # Check if tool name appears in the dead end approach
                if tool_name.replace("_", " ") in approach_lower or tool_name in approach_lower:
                    suppressed.add(tool_name)

        return frozenset(suppressed)

    def _get_lens_profile_tools(self) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
        """Get tool preferences from lens profile.

        Returns:
            Tuple of (primary tools, secondary tools, tools to avoid)
        """
        if self.lens is None:
            return frozenset(), frozenset(), frozenset()

        # Check if lens has tool_profile attribute
        tool_profile = getattr(self.lens, "tool_profile", None)
        if tool_profile is None:
            return frozenset(), frozenset(), frozenset()

        primary = frozenset(getattr(tool_profile, "primary", ()) or ())
        secondary = frozenset(getattr(tool_profile, "secondary", ()) or ())
        avoid = frozenset(getattr(tool_profile, "avoid", ()) or ())

        return primary, secondary, avoid

    def _rank_tools_with_scores(
        self,
        tools: frozenset[str],
        dag_tools: frozenset[str],
        learned_boost: frozenset[str],
        primary_boost: frozenset[str],
        secondary_boost: frozenset[str],
        semantic_scores: dict[str, float] | None = None,
        planned_tools: frozenset[str] | None = None,
    ) -> list[ToolScore]:
        """Rank tools and return detailed score breakdown.

        Priority order:
        1. Learned patterns (highest - proven to work)
        2. Planned tools (explicit intent from planning step)
        3. Lens primary tools
        4. Semantic relevance (embedding match to query)
        5. DAG entry points
        6. Lens secondary tools
        7. Other available tools

        Args:
            tools: Available tools to rank
            dag_tools: Tools available from DAG
            learned_boost: Tools from learned patterns
            primary_boost: Primary lens tools
            secondary_boost: Secondary lens tools
            semantic_scores: Semantic relevance scores (0.0-1.0) per tool
            planned_tools: Tools from planning step

        Returns:
            Ordered list of ToolScore (most relevant first)
        """
        scored: list[ToolScore] = []
        semantic_scores = semantic_scores or {}
        planned_tools = planned_tools or frozenset()

        for tool in tools:
            signals: list[tuple[str, float]] = []
            total = 0.0

            # Learned patterns get highest priority
            if tool in learned_boost:
                signals.append(("learned", 100.0))
                total += 100

            # Planned tools get high priority (explicit intent)
            if tool in planned_tools:
                signals.append(("planned", float(self.planning_boost_weight)))
                total += self.planning_boost_weight

            # Lens primary tools
            if tool in primary_boost:
                signals.append(("lens_primary", 50.0))
                total += 50

            # Semantic relevance boost (scaled by weight and score)
            semantic_score = semantic_scores.get(tool, 0.0)
            if semantic_score > 0.3:  # Threshold for relevance
                sem_points = self.semantic_boost_weight * semantic_score
                signals.append(("semantic", sem_points))
                total += sem_points

            # DAG entry points
            if self.dag.is_entry_point(tool):
                signals.append(("dag_entry", 30.0))
                total += 30

            # Lens secondary tools
            if tool in secondary_boost:
                signals.append(("lens_secondary", 20.0))
                total += 20

            # DAG available (workflow relevant)
            if tool in dag_tools:
                signals.append(("dag_available", 10.0))
                total += 10

            scored.append(ToolScore(
                name=tool,
                total_score=total,
                signals=tuple(signals),
            ))

        # Sort by score descending, then alphabetically for stability
        scored.sort(key=lambda x: (-x.total_score, x.name))

        return scored

    def _rank_tools(
        self,
        tools: frozenset[str],
        dag_tools: frozenset[str],
        learned_boost: frozenset[str],
        primary_boost: frozenset[str],
        secondary_boost: frozenset[str],
        semantic_scores: dict[str, float] | None = None,
        planned_tools: frozenset[str] | None = None,
    ) -> list[str]:
        """Rank tools by relevance (returns names only).

        See _rank_tools_with_scores for detailed score breakdown.
        """
        scored = self._rank_tools_with_scores(
            tools, dag_tools, learned_boost, primary_boost,
            secondary_boost, semantic_scores, planned_tools,
        )
        return [ts.name for ts in scored]

    def _ensure_embedding_index(self, available_tools: "tuple[Tool, ...]") -> None:
        """Initialize embedding index if enabled and not yet built.

        Lazy initialization: Only builds index on first query with semantic enabled.

        Args:
            available_tools: Available tool definitions
        """
        if not self.enable_semantic:
            return

        if self._embedding_index is None:
            self._embedding_index = ToolEmbeddingIndex()

        # Initialize if not already done
        self._embedding_index.initialize(available_tools)

    def _get_semantic_scores(
        self,
        query: str,
        tool_names: frozenset[str],
    ) -> dict[str, float]:
        """Get semantic relevance scores for tools.

        Args:
            query: User query
            tool_names: Set of tool names to score

        Returns:
            Dict mapping tool name to relevance score (0.0-1.0)
        """
        if not self.enable_semantic or self._embedding_index is None:
            return {}

        return self._embedding_index.get_semantic_scores_sync(query, tool_names)

    def _get_planned_tools(
        self,
        query: str,
        available_tools: "tuple[Tool, ...]",
    ) -> frozenset[str]:
        """Get tools from heuristic planning.

        Args:
            query: User query
            available_tools: Available tool definitions

        Returns:
            Set of planned tool names
        """
        if not self.enable_planning:
            return frozenset()

        # Use heuristic planning (no model required, fast)
        plan = plan_heuristic(query, available_tools)
        self._current_plan = plan

        if plan.confidence > 0.5:
            return plan.as_set()
        return frozenset()

    def get_current_plan(self) -> ToolPlan | None:
        """Get the current tool plan (if planning is enabled).

        Returns:
            The last computed ToolPlan, or None
        """
        return self._current_plan

    def select(
        self,
        query: str,
        task_type: str,
        used_tools: frozenset[str],
        available_tools: "tuple[Tool, ...]",
        model_context_window: int | None = None,
        model_tier: str | None = None,
    ) -> "tuple[Tool, ...]":
        """Select relevant tools using multi-signal combination.

        This is the main entry point. It combines:
        1. DAG progressive disclosure (workflow knowledge)
        2. Progressive trust (hard constraint)
        3. Learned pattern boost (soft signal)
        4. Project type filtering (hard constraint)
        5. Lens profile (soft boost/avoid)
        6. Dead end suppression
        7. Semantic relevance (embedding-based boost)
        8. Planned tools (heuristic plan-then-execute)

        Args:
            query: Current user query
            task_type: Classified task type (bugfix, refactor, etc.)
            used_tools: Tools already used in this session
            available_tools: All available Tool definitions
            model_context_window: Model's context window (for adaptive limits)
            model_tier: Model tier (small, medium, large)

        Returns:
            Filtered and ranked tuple of Tool definitions
        """
        # Build name -> Tool mapping
        tool_map: dict[str, Tool] = {t.name: t for t in available_tools}
        all_tool_names = frozenset(tool_map.keys())

        # Initialize embedding index for semantic search (lazy)
        self._ensure_embedding_index(available_tools)

        # Layer 1: DAG progressive disclosure
        if self.enable_dag:
            dag_available = self.dag.get_available(used_tools)
            # Intersect with actually available tools (some DAG tools may not be registered)
            dag_available = dag_available & all_tool_names
        else:
            dag_available = all_tool_names

        # Layer 2: Progressive trust (hard constraint via already-filtered tools)
        # Note: ProgressivePolicy.filter_tools() should be called BEFORE this selector
        # We assume available_tools is already filtered by trust level
        trust_available = all_tool_names

        # Layer 3: Learned pattern boost
        learned_boost = self._get_learned_suggestions(task_type)

        # Layer 4: Project type filtering
        project_tools = self._get_project_tools()
        if project_tools:  # Empty means no filtering
            project_available = all_tool_names & project_tools
        else:
            project_available = all_tool_names

        # Layer 5: Lens profile
        primary_boost, secondary_boost, lens_avoid = self._get_lens_profile_tools()

        # Layer 6: Dead end suppression
        dead_end_tools = self._get_dead_end_tools(query)

        # Layer 7: Semantic relevance scores
        semantic_scores = self._get_semantic_scores(query, all_tool_names)

        # Layer 8: Planned tools (heuristic)
        planned_tools = self._get_planned_tools(query, available_tools)

        # Combine signals
        # Base: intersection of hard constraints (DAG + trust + project)
        base = dag_available & trust_available & project_available

        # Add boosted tools that pass trust check (learned patterns may suggest
        # tools not yet unlocked by DAG but still useful)
        boosted = base | (learned_boost & trust_available & project_available)
        boosted = boosted | (primary_boost & trust_available & project_available)

        # Add planned tools that pass trust check
        # Planning allows explicit tool requests that override DAG constraints
        if planned_tools:
            boosted = boosted | (planned_tools & trust_available & project_available)

        # Add semantically relevant tools that pass trust check
        # This allows semantic search to suggest tools not yet unlocked by DAG
        if semantic_scores:
            high_semantic = frozenset(
                name for name, score in semantic_scores.items()
                if score > 0.5  # High confidence threshold
            )
            boosted = boosted | (high_semantic & trust_available & project_available)

        # Subtract dead ends and lens avoid
        final = boosted - dead_end_tools - lens_avoid

        # If we ended up with no tools, fall back to DAG entry points
        if not final:
            final = dag_available & trust_available
            if not final:
                final = all_tool_names  # Last resort: all available

        # Rank tools with semantic and planning boost
        ranked = self._rank_tools(
            final,
            dag_available,
            learned_boost,
            primary_boost,
            secondary_boost,
            semantic_scores,
            planned_tools,
        )

        # Apply model-adaptive limit
        limit = self.max_tools or get_tool_limit_for_model(model_context_window, model_tier)
        if limit is not None:
            ranked = ranked[:limit]

        # Log selection for debugging
        if logger.isEnabledFor(logging.DEBUG):
            semantic_hits = sum(1 for s in semantic_scores.values() if s > 0.3)
            logger.debug(
                "Tool selection: %d/%d tools (DAG=%d, project=%d, learned=%d, "
                "semantic=%d, planned=%d, dead_ends=%d)",
                len(ranked),
                len(all_tool_names),
                len(dag_available),
                len(project_available) if project_tools else len(all_tool_names),
                len(learned_boost),
                semantic_hits,
                len(planned_tools),
                len(dead_end_tools),
            )

        # Convert back to Tool objects in ranked order
        return tuple(tool_map[name] for name in ranked if name in tool_map)

    def select_with_trace(
        self,
        query: str,
        task_type: str,
        used_tools: frozenset[str],
        available_tools: "tuple[Tool, ...]",
        model_context_window: int | None = None,
        model_tier: str | None = None,
    ) -> tuple["tuple[Tool, ...]", SelectionTrace]:
        """Select tools and return detailed trace of the decision.

        Same as select() but also returns a SelectionTrace for debugging
        and observability.

        Args:
            query: Current user query
            task_type: Classified task type
            used_tools: Tools already used
            available_tools: All available Tool definitions
            model_context_window: Model's context window
            model_tier: Model tier

        Returns:
            Tuple of (selected_tools, trace)
        """
        # Build name -> Tool mapping
        tool_map: dict[str, Tool] = {t.name: t for t in available_tools}
        all_tool_names = frozenset(tool_map.keys())

        # Initialize embedding index
        self._ensure_embedding_index(available_tools)

        # Layer 1: DAG progressive disclosure
        if self.enable_dag:
            dag_available = self.dag.get_available(used_tools)
            dag_available = dag_available & all_tool_names
        else:
            dag_available = all_tool_names

        # Layer 2: Trust (pre-filtered)
        trust_available = all_tool_names

        # Layer 3: Learned patterns
        learned_boost = self._get_learned_suggestions(task_type)

        # Layer 4: Project type
        project_tools = self._get_project_tools()
        if project_tools:
            project_available = all_tool_names & project_tools
        else:
            project_available = all_tool_names

        # Layer 5: Lens profile
        primary_boost, secondary_boost, lens_avoid = self._get_lens_profile_tools()

        # Layer 6: Dead ends
        dead_end_tools = self._get_dead_end_tools(query)

        # Layer 7: Semantic scores
        semantic_scores = self._get_semantic_scores(query, all_tool_names)

        # Layer 8: Planning
        planned_tools = self._get_planned_tools(query, available_tools)

        # Combine signals
        base = dag_available & trust_available & project_available
        boosted = base | (learned_boost & trust_available & project_available)
        boosted = boosted | (primary_boost & trust_available & project_available)

        if planned_tools:
            boosted = boosted | (planned_tools & trust_available & project_available)

        if semantic_scores:
            high_semantic = frozenset(
                name for name, score in semantic_scores.items()
                if score > 0.5
            )
            boosted = boosted | (high_semantic & trust_available & project_available)

        final = boosted - dead_end_tools - lens_avoid

        if not final:
            final = dag_available & trust_available
            if not final:
                final = all_tool_names

        # Rank with detailed scores
        ranked_scores = self._rank_tools_with_scores(
            final,
            dag_available,
            learned_boost,
            primary_boost,
            secondary_boost,
            semantic_scores,
            planned_tools,
        )

        # Apply limit
        limit = self.max_tools or get_tool_limit_for_model(model_context_window, model_tier)
        if limit is not None:
            ranked_scores = ranked_scores[:limit]

        # Build trace
        semantic_hits = tuple(
            name for name, score in semantic_scores.items()
            if score > 0.3
        )

        winner = ranked_scores[0] if ranked_scores else None

        trace = SelectionTrace(
            query=query,
            task_type=task_type,
            total_available=len(all_tool_names),
            dag_available=len(dag_available),
            project_filtered=len(project_available),
            planned_tools=tuple(planned_tools),
            semantic_hits=semantic_hits,
            dead_ends_removed=tuple(dead_end_tools),
            final_count=len(ranked_scores),
            top_tools=tuple(ranked_scores[:10]),
            winner=winner.name if winner else "",
            winner_signals=winner.active_signals() if winner else (),
        )

        # Convert to Tool objects
        ranked_names = [ts.name for ts in ranked_scores]
        tools = tuple(tool_map[name] for name in ranked_names if name in tool_map)

        return tools, trace

    def reset_cache(self) -> None:
        """Reset cached project context, embedding index, and plan (call if workspace changes)."""
        self._project_type = None
        self._has_git = None
        self._current_plan = None
        if self._embedding_index is not None:
            self._embedding_index.reset()
            self._embedding_index = None
