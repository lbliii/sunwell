"""Project Context - RFC-045 Phase 5 + RFC-050 Bootstrap + RFC-052 Team Intelligence.

Unified context combining Simulacrum + Project Intelligence + Team Intelligence.

RFC-050 adds:
- OwnershipMap for code ownership tracking
- BootstrapStatus for tracking bootstrap state

RFC-052 adds:
- TeamKnowledgeStore for shared team decisions
- UnifiedIntelligence for team + personal + project
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.features.team import TeamKnowledgeStore, UnifiedIntelligence
    from sunwell.knowledge.bootstrap.ownership import OwnershipMap
    from sunwell.knowledge.bootstrap.types import BootstrapStatus
    from sunwell.knowledge.codebase.codebase import CodebaseGraph
    from sunwell.knowledge.codebase.decisions import DecisionMemory
    from sunwell.knowledge.codebase.failures import FailureMemory
    from sunwell.knowledge.codebase.patterns import PatternProfile
    from sunwell.memory.simulacrum.core.store import SimulacrumStore


@dataclass(slots=True)
class ProjectContext:
    """Unified context combining Simulacrum + Project Intelligence + Team Intelligence.

    This is the main interface for accessing all project intelligence.
    """

    # Conversation intelligence (existing)
    simulacrum: SimulacrumStore
    """RFC-013 + RFC-014: Conversation history, learnings, topology."""

    # Codebase intelligence (new)
    decisions: DecisionMemory
    """Architectural decisions with rationale."""

    codebase: CodebaseGraph
    """Semantic understanding of code structure."""

    patterns: PatternProfile
    """Learned user/project preferences."""

    failures: FailureMemory
    """Failed approaches with root cause analysis."""

    # RFC-050: Bootstrap intelligence
    ownership: OwnershipMap | None = None
    """Code ownership from git blame analysis (optional)."""

    bootstrap_status: BootstrapStatus | None = None
    """When/what was bootstrapped."""

    # RFC-052: Team intelligence
    team: TeamKnowledgeStore | None = None
    """Team-shared knowledge (decisions, failures, patterns)."""

    unified: UnifiedIntelligence | None = None
    """Combined team + personal + project intelligence."""

    # Session state
    active_goals: list[str] = field(default_factory=list)
    """What we're currently working on."""

    blocked_on: list[str] = field(default_factory=list)
    """What's blocking progress (waiting for user, external, etc.)."""

    @classmethod
    async def load(cls, project_root: Path) -> ProjectContext:
        """Load both systems from project root.

        Args:
            project_root: Project root directory

        Returns:
            ProjectContext with all intelligence loaded
        """
        from sunwell.features.team import TeamKnowledgeStore, UnifiedIntelligence
        from sunwell.features.team.gitignore_template import ensure_sunwell_structure
        from sunwell.knowledge.bootstrap.ownership import OwnershipMap
        from sunwell.knowledge.codebase.codebase import CodebaseGraph
        from sunwell.knowledge.codebase.decisions import DecisionMemory
        from sunwell.knowledge.codebase.failures import FailureMemory
        from sunwell.knowledge.codebase.patterns import PatternProfile
        from sunwell.memory.simulacrum.core.store import SimulacrumStore

        # Ensure .sunwell directory structure exists with proper gitignore
        ensure_sunwell_structure(project_root)

        intelligence_path = project_root / ".sunwell" / "intelligence"
        sessions_path = project_root / ".sunwell" / "sessions"

        # Load Simulacrum (existing)
        simulacrum = SimulacrumStore(base_path=sessions_path)

        # Load Project Intelligence (new)
        decisions = DecisionMemory(base_path=intelligence_path)
        codebase = CodebaseGraph.load(base_path=intelligence_path)
        patterns = PatternProfile.load(base_path=intelligence_path)
        failures = FailureMemory(base_path=intelligence_path)

        # RFC-050: Load ownership map
        ownership = OwnershipMap(intelligence_path)

        # RFC-050: Load bootstrap status
        bootstrap_status = cls._load_bootstrap_status(project_root)

        # RFC-052: Load team intelligence
        team = TeamKnowledgeStore(project_root)

        # RFC-052: Create unified intelligence (team + personal + project)
        unified = UnifiedIntelligence(
            team_store=team,
            personal_store=decisions,
            failure_store=failures,
            project_analyzer=None,  # Codebase analyzer integration is optional
        )

        return cls(
            simulacrum=simulacrum,
            decisions=decisions,
            codebase=codebase,
            patterns=patterns,
            failures=failures,
            ownership=ownership,
            bootstrap_status=bootstrap_status,
            team=team,
            unified=unified,
        )

    @staticmethod
    def _load_bootstrap_status(project_root: Path) -> BootstrapStatus | None:
        """Load bootstrap status from state file."""
        import json
        from datetime import datetime, timedelta

        from sunwell.knowledge.bootstrap.types import BootstrapStatus

        state_path = project_root / ".sunwell" / "bootstrap_state.json"
        if not state_path.exists():
            return None

        try:
            with open(state_path) as f:
                data = json.load(f)

            return BootstrapStatus(
                last_run=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
                last_commit_scanned=data.get("last_commit", ""),
                decisions_count=data.get("decisions_count", 0),
                patterns_count=data.get("patterns_count", 0),
                ownership_domains=data.get("ownership_domains", 0),
                scan_duration=timedelta(seconds=data.get("scan_duration_s", 0)),
            )
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    async def save(self) -> None:
        """Persist current state."""
        # Save codebase graph
        intelligence_path = self.decisions.base_path
        self.codebase.save(base_path=intelligence_path)

        # Save patterns
        self.patterns.save(base_path=intelligence_path)

        # Simulacrum saves automatically on operations


@dataclass(slots=True)
class ProjectIntelligence:
    """Main interface for project intelligence.

    Handles initialization, session management, and coordination.
    """

    project_root: Path

    def __post_init__(self) -> None:
        """Ensure project_root is a Path."""
        if not isinstance(self.project_root, Path):
            object.__setattr__(self, "project_root", Path(self.project_root))

    async def load(self) -> ProjectContext:
        """Load project intelligence, creating if needed.

        Returns:
            ProjectContext with all intelligence loaded
        """
        return await ProjectContext.load(self.project_root)

    async def start_session(self) -> ProjectContext:
        """Begin a new session with existing context.

        Returns:
            ProjectContext with session summary
        """
        context = await self.load()
        return context

    async def end_session(self, context: ProjectContext) -> None:
        """End session, persist learnings.

        Args:
            context: Current project context
        """
        await context.save()
