"""Unified Intelligence - RFC-052.

Unifies personal and team intelligence with a consistent priority order.
When looking up decisions or checking approaches, Sunwell checks:
1. Team decisions (shared, authoritative)
2. Personal decisions (local override if allowed)
3. Project analysis (auto-generated from code)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.intelligence.codebase import CodebaseAnalyzer
    from sunwell.intelligence.decisions import Decision, DecisionMemory
    from sunwell.intelligence.failures import FailureMemory
    from sunwell.team.store import TeamKnowledgeStore

from sunwell.team.types import (
    TeamDecision,
    TeamPatterns,
)

__all__ = ["UnifiedIntelligence", "ApproachCheck", "ApproachWarning", "FileContext"]

# Category keywords to check for contradicting team decisions
_CATEGORY_KEYWORDS: tuple[str, ...] = (
    "architecture", "database", "auth", "framework", "api", "pattern"
)


@dataclass(frozen=True, slots=True)
class ApproachWarning:
    """Warning about a proposed approach."""

    level: Literal["team", "personal", "project"]
    """Where this warning came from."""

    message: str
    """Warning message."""

    prevention: str
    """How to prevent the issue."""


@dataclass(frozen=True, slots=True)
class ApproachCheck:
    """Result of checking a proposed approach."""

    safe: bool
    """Whether the approach is safe to proceed with."""

    warnings: tuple[ApproachWarning, ...] = ()
    """Warnings about the approach."""

    def format_for_prompt(self) -> str:
        """Format warnings for LLM prompt."""
        if self.safe:
            return ""

        lines = ["⚠️ **Approach Warnings**\n"]
        for w in self.warnings:
            lines.append(f"- [{w.level}] {w.message}")
            lines.append(f"  Prevention: {w.prevention}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class FileContext:
    """Context for working on a specific file."""

    owners: tuple[str, ...] = ()
    """Who owns this file."""

    patterns: TeamPatterns | None = None
    """Team patterns that apply."""

    relevant_decisions: tuple[TeamDecision, ...] = ()
    """Decisions relevant to this file's domain."""

    dependencies: tuple[Path, ...] = ()
    """Files this file depends on."""

    dependents: tuple[Path, ...] = ()
    """Files that depend on this file."""


class UnifiedIntelligence:
    """Unifies personal and team intelligence.

    Priority order for lookups:
    1. Team decisions (shared, authoritative)
    2. Personal decisions (local override if allowed)
    3. Project analysis (auto-generated)
    """

    def __init__(
        self,
        team_store: TeamKnowledgeStore,
        personal_store: DecisionMemory | None = None,
        failure_store: FailureMemory | None = None,
        project_analyzer: CodebaseAnalyzer | None = None,
    ):
        """Initialize unified intelligence.

        Args:
            team_store: Team knowledge store
            personal_store: Personal decision memory (RFC-045)
            failure_store: Personal failure memory (RFC-045)
            project_analyzer: Codebase analyzer (RFC-045)
        """
        self.team = team_store
        self.personal = personal_store
        self.failures = failure_store
        self.project = project_analyzer

    async def find_relevant_decision(
        self,
        query: str,
    ) -> Decision | TeamDecision | None:
        """Find most relevant decision for a query.

        Checks team knowledge first, then personal.

        Args:
            query: Natural language query

        Returns:
            Most relevant decision or None
        """
        # Check team decisions first (authoritative)
        team_decisions = await self.team.find_relevant_decisions(query)
        if team_decisions:
            return team_decisions[0]

        # Fall back to personal decisions
        if self.personal:
            personal_decisions = await self.personal.find_relevant_decisions(query)
            if personal_decisions:
                return personal_decisions[0]

        return None

    async def find_all_relevant_decisions(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[Decision | TeamDecision]:
        """Find all relevant decisions from both team and personal.

        Team decisions come first, then personal.

        Args:
            query: Natural language query
            top_k: Maximum total decisions to return

        Returns:
            List of relevant decisions (team first)
        """
        results: list[Decision | TeamDecision] = []

        # Team decisions first
        team_decisions = await self.team.find_relevant_decisions(query, top_k=top_k)
        results.extend(team_decisions)

        # Personal decisions if we have room
        remaining = top_k - len(results)
        if remaining > 0 and self.personal:
            personal_decisions = await self.personal.find_relevant_decisions(
                query, top_k=remaining
            )
            # Filter out any personal decisions that match team decisions
            team_ids = {d.id for d in team_decisions}
            for d in personal_decisions:
                if d.id not in team_ids:
                    results.append(d)

        return results[:top_k]

    async def check_approach(
        self,
        proposed_approach: str,
    ) -> ApproachCheck:
        """Check if proposed approach has known issues.

        Combines team and personal failure knowledge.

        Args:
            proposed_approach: Description of proposed approach

        Returns:
            ApproachCheck with warnings if any issues found
        """
        warnings: list[ApproachWarning] = []

        # Check team failures
        team_failures = await self.team.check_similar_failures(proposed_approach)
        for f in team_failures:
            warnings.append(
                ApproachWarning(
                    level="team",
                    message=f"Team failure ({f.occurrences}x): {f.description}",
                    prevention=f.prevention,
                )
            )

        # Check personal failures
        if self.failures:
            personal_failures = await self.failures.check_similar_failures(proposed_approach)
            for f in personal_failures:
                warnings.append(
                    ApproachWarning(
                        level="personal",
                        message=f"Personal failure: {f.description}",
                        prevention=f.root_cause or "Unknown",
                    )
                )

        # Check for contradicting team decisions
        # Try to infer category from approach description
        for category in _CATEGORY_KEYWORDS:
            if category in proposed_approach.lower():
                team_decision = await self.team.check_contradiction(
                    proposed_approach, category
                )
                if team_decision:
                    warnings.append(
                        ApproachWarning(
                            level="team",
                            message=f"Contradicts team decision: {team_decision.question}",
                            prevention=f"Team chose: {team_decision.choice}",
                        )
                    )

        return ApproachCheck(
            safe=len(warnings) == 0,
            warnings=tuple(warnings),
        )

    async def get_context_for_file(
        self,
        file_path: Path,
    ) -> FileContext:
        """Get all relevant context for working on a file.

        Combines ownership, patterns, decisions, and analysis.

        Args:
            file_path: Path to the file

        Returns:
            FileContext with all relevant information
        """
        owners = await self.team.get_owners(file_path)
        patterns = await self.team.get_patterns()

        # Find relevant decisions for this file's domain
        file_name = file_path.stem
        relevant_decisions = await self.team.find_relevant_decisions(file_name)

        # Get codebase graph context if available
        dependencies: list[Path] = []
        dependents: list[Path] = []
        if self.project:
            try:
                dependencies = await self.project.get_dependencies(file_path)
                dependents = await self.project.get_dependents(file_path)
            except Exception:
                pass  # Project analyzer might not be initialized

        return FileContext(
            owners=tuple(owners),
            patterns=patterns,
            relevant_decisions=tuple(relevant_decisions),
            dependencies=tuple(dependencies),
            dependents=tuple(dependents),
        )

    async def get_team_summary(self) -> dict:
        """Get summary of team knowledge.

        Returns:
            Summary dict with counts and top items
        """
        decisions = await self.team.get_decisions()
        failures = await self.team.get_failures()
        patterns = await self.team.get_patterns()
        ownership = await self.team.get_ownership()

        # Group decisions by category
        categories: dict[str, int] = {}
        for d in decisions:
            categories[d.category] = categories.get(d.category, 0) + 1

        # Get top contributors
        authors: dict[str, int] = {}
        for d in decisions:
            authors[d.author] = authors.get(d.author, 0) + 1
        top_contributors = sorted(authors.items(), key=lambda x: -x[1])[:5]

        return {
            "decisions": {
                "total": len(decisions),
                "by_category": categories,
            },
            "failures": {
                "total": len(failures),
                "top": [f.description for f in failures[:3]],
            },
            "patterns": {
                "enforcement_level": patterns.enforcement_level,
                "docstring_style": patterns.docstring_style,
                "type_annotations": patterns.type_annotation_level,
            },
            "ownership": {
                "paths_mapped": len(ownership.owners),
                "experts_registered": len(ownership.expertise),
            },
            "contributors": [{"author": a, "decisions": c} for a, c in top_contributors],
        }
