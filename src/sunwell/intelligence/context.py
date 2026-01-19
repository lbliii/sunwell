"""Project Context - RFC-045 Phase 5.

Unified context combining Simulacrum + Project Intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.intelligence.codebase import CodebaseGraph
    from sunwell.intelligence.decisions import DecisionMemory
    from sunwell.intelligence.failures import FailureMemory
    from sunwell.intelligence.patterns import PatternProfile
    from sunwell.simulacrum.core.store import SimulacrumStore


@dataclass
class ProjectContext:
    """Unified context combining Simulacrum + Project Intelligence.

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
        from sunwell.intelligence.codebase import CodebaseGraph
        from sunwell.intelligence.decisions import DecisionMemory
        from sunwell.intelligence.failures import FailureMemory
        from sunwell.intelligence.patterns import PatternProfile
        from sunwell.simulacrum.core.store import SimulacrumStore

        intelligence_path = project_root / ".sunwell" / "intelligence"
        sessions_path = project_root / ".sunwell" / "sessions"

        # Load Simulacrum (existing)
        simulacrum = SimulacrumStore(base_path=sessions_path)

        # Load Project Intelligence (new)
        decisions = DecisionMemory(base_path=intelligence_path)
        codebase = CodebaseGraph.load(base_path=intelligence_path)
        patterns = PatternProfile.load(base_path=intelligence_path)
        failures = FailureMemory(base_path=intelligence_path)

        return cls(
            simulacrum=simulacrum,
            decisions=decisions,
            codebase=codebase,
            patterns=patterns,
            failures=failures,
        )

    async def save(self) -> None:
        """Persist current state."""
        # Save codebase graph
        intelligence_path = self.decisions.base_path
        self.codebase.save(base_path=intelligence_path)

        # Save patterns
        self.patterns.save(base_path=intelligence_path)

        # Simulacrum saves automatically on operations


@dataclass
class ProjectIntelligence:
    """Main interface for project intelligence.

    Handles initialization, session management, and coordination.
    """

    project_root: Path

    def __init__(self, project_root: Path):
        """Initialize project intelligence.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root)

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
