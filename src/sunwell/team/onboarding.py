"""Team Onboarding - RFC-052.

Helps new team members understand accumulated knowledge.
When a new developer runs 'sunwell init', they get:
1. Summary of team decisions
2. Key failure patterns to avoid
3. Code patterns to follow
4. Ownership map
"""

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.team.store import TeamKnowledgeStore

from sunwell.team.types import (
    TeamDecision,
    TeamFailure,
    TeamOwnership,
    TeamPatterns,
)

__all__ = ["TeamOnboarding", "OnboardingSummary"]


@dataclass(frozen=True, slots=True)
class OnboardingSummary:
    """Summary for new team member onboarding."""

    total_decisions: int
    """Total number of team decisions."""

    decisions_by_category: MappingProxyType[str, tuple[TeamDecision, ...]]
    """Decisions organized by category."""

    critical_failures: tuple[TeamFailure, ...]
    """Most important failure patterns to know."""

    patterns: TeamPatterns
    """Team code patterns."""

    ownership_summary: MappingProxyType[str, str]
    """Human-readable ownership mapping."""

    top_contributors: tuple[str, ...]
    """Team members who contributed most decisions."""

    def format_welcome_message(self) -> str:
        """Format as welcome message for new team member.

        Returns:
            Formatted welcome message string
        """
        return f"""
🎉 Welcome to the team! Here's what Sunwell has learned:

📋 **Team Decisions**: {self.total_decisions} recorded
   Categories: {', '.join(self.decisions_by_category.keys())}

⚠️ **Critical Failures to Avoid**:
{self._format_failures()}

📝 **Code Patterns**:
   - Naming: {self.patterns.naming_conventions or 'Not specified'}
   - Docstrings: {self.patterns.docstring_style}
   - Type hints: {self.patterns.type_annotation_level}
   - Enforcement: {self.patterns.enforcement_level}

👥 **Key Contributors**: {', '.join(self.top_contributors) or 'None yet'}

Run `sunwell team decisions` to see all team decisions.
Run `sunwell team failures` to see failure patterns.
"""

    def _format_failures(self) -> str:
        """Format failure patterns for display."""
        if not self.critical_failures:
            return "   No critical failures recorded yet."
        lines = []
        for f in self.critical_failures[:3]:
            lines.append(f"   - {f.description} ({f.occurrences}x)")
        return "\n".join(lines)

    def format_detailed_summary(self) -> str:
        """Format a detailed summary for comprehensive onboarding.

        Returns:
            Detailed summary string
        """
        sections = [self.format_welcome_message()]

        # Add detailed decisions by category
        sections.append("\n" + "=" * 60)
        sections.append("📋 TEAM DECISIONS BY CATEGORY")
        sections.append("=" * 60)

        for category, decisions in sorted(self.decisions_by_category.items()):
            sections.append(f"\n### {category.upper()} ({len(decisions)} decisions)")
            for d in decisions[:5]:  # Show top 5 per category
                sections.append(f"\n**{d.question}**")
                sections.append(f"  Choice: {d.choice}")
                sections.append(f"  By: {d.author}")
                if d.rationale:
                    sections.append(f"  Why: {d.rationale[:100]}...")

        # Add detailed failure patterns
        if self.critical_failures:
            sections.append("\n" + "=" * 60)
            sections.append("⚠️ FAILURE PATTERNS TO AVOID")
            sections.append("=" * 60)

            for f in self.critical_failures:
                sections.append(f"\n**{f.description}**")
                sections.append(f"  Error type: {f.error_type}")
                sections.append(f"  Root cause: {f.root_cause}")
                sections.append(f"  Prevention: {f.prevention}")
                sections.append(f"  Occurrences: {f.occurrences}")

        # Add ownership info
        if self.ownership_summary:
            sections.append("\n" + "=" * 60)
            sections.append("👤 CODE OWNERSHIP")
            sections.append("=" * 60)

            for path, owner_info in self.ownership_summary.items():
                sections.append(f"  {path}: {owner_info}")

        return "\n".join(sections)


class TeamOnboarding:
    """Helps new team members understand accumulated knowledge.

    When a new developer runs 'sunwell init', they get:
    1. Summary of team decisions
    2. Key failure patterns to avoid
    3. Code patterns to follow
    4. Ownership map
    """

    def __init__(self, store: TeamKnowledgeStore):
        """Initialize team onboarding.

        Args:
            store: Team knowledge store
        """
        self.store = store

    async def generate_onboarding_summary(self) -> OnboardingSummary:
        """Generate onboarding summary for new team member.

        Returns:
            OnboardingSummary with all relevant information
        """
        decisions = await self.store.get_decisions()
        failures = await self.store.get_failures()
        patterns = await self.store.get_patterns()
        ownership = await self.store.get_ownership()

        # Categorize decisions by topic
        decisions_by_category: dict[str, list[TeamDecision]] = {}
        for d in decisions:
            if d.category not in decisions_by_category:
                decisions_by_category[d.category] = []
            decisions_by_category[d.category].append(d)

        # Find high-occurrence failures
        critical_failures = sorted(failures, key=lambda f: -f.occurrences)[:5]

        return OnboardingSummary(
            total_decisions=len(decisions),
            decisions_by_category=decisions_by_category,
            critical_failures=critical_failures,
            patterns=patterns,
            ownership_summary=self._summarize_ownership(ownership),
            top_contributors=self._get_top_contributors(decisions),
        )

    def _summarize_ownership(self, ownership: TeamOwnership) -> dict[str, str]:
        """Create human-readable ownership summary.

        Args:
            ownership: Team ownership data

        Returns:
            Dict mapping paths to ownership descriptions
        """
        summary = {}
        for path, owners in ownership.owners.items():
            summary[path] = f"Owned by: {', '.join(owners)}"
        return summary

    def _get_top_contributors(self, decisions: list[TeamDecision]) -> list[str]:
        """Get team members who contributed most decisions.

        Args:
            decisions: List of team decisions

        Returns:
            List of top contributor identifiers
        """
        author_counts = Counter(d.author for d in decisions)
        return [author for author, _ in author_counts.most_common(5)]

    async def check_onboarding_needed(self) -> bool:
        """Check if onboarding summary should be shown.

        Returns True if:
        - Team knowledge exists
        - User hasn't seen onboarding before (or it's been updated)

        Returns:
            True if onboarding should be shown
        """
        decisions = await self.store.get_decisions()
        return len(decisions) > 0

    async def get_quick_tips(self) -> list[str]:
        """Get quick tips for a new team member.

        Returns:
            List of actionable tips
        """
        tips = []

        # Tip about patterns
        patterns = await self.store.get_patterns()
        if patterns.docstring_style != "none":
            tips.append(f"📝 Use {patterns.docstring_style} style docstrings")
        if patterns.type_annotation_level != "none":
            tips.append(f"🔤 Type annotations: {patterns.type_annotation_level}")
        if patterns.naming_conventions:
            conventions = ", ".join(
                f"{k}: {v}" for k, v in list(patterns.naming_conventions.items())[:2]
            )
            tips.append(f"📛 Naming: {conventions}")

        # Tip about top failure
        failures = await self.store.get_failures()
        if failures:
            top_failure = failures[0]
            tips.append(f"⚠️ Avoid: {top_failure.description}")

        # Tip about recent decisions
        decisions = await self.store.get_decisions()
        if decisions:
            recent = decisions[0]
            tips.append(
                f"📋 Recent decision: {recent.question} → {recent.choice[:30]}..."
            )

        return tips[:5]  # Max 5 tips

    async def get_category_summary(self, category: str) -> dict:
        """Get summary for a specific decision category.

        Args:
            category: Category to summarize

        Returns:
            Summary dict for the category
        """
        decisions = await self.store.get_decisions(category=category)

        return {
            "category": category,
            "total": len(decisions),
            "decisions": [
                {
                    "question": d.question,
                    "choice": d.choice,
                    "author": d.author,
                    "endorsements": len(d.endorsements),
                }
                for d in decisions[:10]
            ],
        }
