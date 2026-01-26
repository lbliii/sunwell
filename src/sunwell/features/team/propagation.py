"""Knowledge Propagation - RFC-052.

Propagates knowledge between layers:
- Personal decision → prompt to share with team (promotion)
- Team decision → propagate to all local instances (sync)
- Project analysis → available to team

Flow:
1. User makes personal decision (RFC-045)
2. User confirms it should be team-wide
3. KnowledgePropagator promotes Decision → TeamDecision
4. TeamKnowledgeStore commits to git
5. Other team members pull and see the decision
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.features.team.store import TeamKnowledgeStore
    from sunwell.knowledge.codebase.decisions import Decision, DecisionMemory

from sunwell.features.team.types import (
    TeamDecision,
    TeamFailure,
    TeamKnowledgeContext,
    TeamKnowledgeUpdate,
)

__all__ = ["KnowledgePropagator"]

# Categories that indicate architecture-related decisions worth sharing team-wide
_ARCHITECTURE_CATEGORIES: frozenset[str] = frozenset({
    "database", "auth", "framework", "architecture", "api"
})


class KnowledgePropagator:
    """Propagates knowledge between layers.

    Flow:
    1. Personal decision → prompt to share with team
    2. Team decision → propagate to all local instances
    3. Project analysis → available to team
    """

    def __init__(
        self,
        team_store: TeamKnowledgeStore,
        personal_store: DecisionMemory | None = None,
    ):
        """Initialize knowledge propagator.

        Args:
            team_store: Team knowledge store
            personal_store: Personal decision memory (RFC-045)
        """
        self.team_store = team_store
        self.personal_store = personal_store

    async def promote_to_team(
        self,
        decision: Decision,
        author: str | None = None,
    ) -> TeamDecision:
        """Promote a personal decision to team knowledge.

        Called when user confirms a decision should be shared.

        Args:
            decision: Personal decision from RFC-045
            author: Override author (defaults to git user)

        Returns:
            The promoted TeamDecision
        """
        if author is None:
            author = await self.team_store.get_git_user()

        team_decision = TeamDecision(
            id=decision.id,
            category=decision.category,
            question=decision.question,
            choice=decision.choice,
            rejected=decision.rejected,
            rationale=decision.rationale,
            confidence=decision.confidence,
            author=author,
            timestamp=datetime.now(),
            supersedes=None,  # Fresh team decision
            endorsements=(),  # Author is implicit first endorser
            applies_until=None,
            tags=(),
        )

        await self.team_store.record_decision(team_decision)
        return team_decision

    async def promote_failure_to_team(
        self,
        description: str,
        error_type: str,
        root_cause: str,
        prevention: str,
        author: str | None = None,
        affected_files: list[str] | None = None,
    ) -> TeamFailure:
        """Promote a failure pattern to team knowledge.

        Args:
            description: What approach failed
            error_type: Type of failure
            root_cause: Why it failed
            prevention: How to avoid this
            author: Override author (defaults to git user)
            affected_files: Files/modules where this applies

        Returns:
            The promoted TeamFailure
        """
        if author is None:
            author = await self.team_store.get_git_user()

        return await self.team_store.create_failure(
            description=description,
            error_type=error_type,
            root_cause=root_cause,
            prevention=prevention,
            author=author,
            affected_files=affected_files,
        )

    async def check_team_knowledge(
        self,
        query: str,
    ) -> TeamKnowledgeContext:
        """Check team knowledge for relevant context.

        Called before any decision or action to surface team wisdom.

        Args:
            query: Natural language query describing what's being done

        Returns:
            TeamKnowledgeContext with relevant decisions, failures, patterns
        """
        relevant_decisions = await self.team_store.find_relevant_decisions(query)
        similar_failures = await self.team_store.check_similar_failures(query)
        patterns = await self.team_store.get_patterns()

        return TeamKnowledgeContext(
            decisions=relevant_decisions,
            failures=similar_failures,
            patterns=patterns,
        )

    async def check_for_contradiction(
        self,
        proposed_choice: str,
        category: str,
    ) -> TeamDecision | None:
        """Check if a proposed choice contradicts team decisions.

        Args:
            proposed_choice: What the user wants to do
            category: Decision category

        Returns:
            Contradicting team decision if found
        """
        return await self.team_store.check_contradiction(proposed_choice, category)

    async def on_git_pull(self) -> list[TeamKnowledgeUpdate]:
        """Handle new team knowledge after git pull.

        Returns list of new knowledge for user notification.

        Returns:
            List of TeamKnowledgeUpdate notifications
        """
        # Sync with remote
        result = await self.team_store.sync()

        updates: list[TeamKnowledgeUpdate] = []

        if result.conflicts:
            updates.append(
                TeamKnowledgeUpdate(
                    type="decision",
                    summary=f"⚠️ Merge conflicts in {len(result.conflicts)} files",
                    author="system",
                    detail="Run `sunwell team conflicts` to resolve",
                )
            )

        for decision in result.new_decisions:
            updates.append(
                TeamKnowledgeUpdate(
                    type="decision",
                    summary=f"New team decision: {decision.question}",
                    author=decision.author,
                    detail=f"Choice: {decision.choice}",
                )
            )

        for failure in result.new_failures:
            updates.append(
                TeamKnowledgeUpdate(
                    type="failure",
                    summary=f"New failure pattern: {failure.description}",
                    author=failure.author,
                    detail=f"Prevention: {failure.prevention}",
                )
            )

        return updates

    async def should_promote(
        self,
        decision: Decision,
    ) -> bool:
        """Heuristic to suggest if a decision should be promoted to team.

        A decision is a good candidate for promotion if:
        - High confidence
        - Affects architecture (database, auth, framework)
        - Has rejected alternatives (was a real choice)

        Args:
            decision: Personal decision to evaluate

        Returns:
            True if decision is a good candidate for team promotion
        """
        # High confidence decisions are worth sharing
        if decision.confidence >= 0.9:
            return True

        # Architecture-related decisions are usually team-wide
        if decision.category.lower() in _ARCHITECTURE_CATEGORIES:
            return True

        # Decisions with rejected alternatives show real trade-offs
        if len(decision.rejected) >= 2:
            return True

        return False

    def format_promotion_prompt(
        self,
        decision: Decision,
    ) -> str:
        """Format a prompt asking user if they want to promote a decision.

        Args:
            decision: The decision to potentially promote

        Returns:
            Formatted prompt string
        """
        rejected_text = ""
        if decision.rejected:
            rejected_list = "\n".join(
                f"  - {r.option}: {r.reason}" for r in decision.rejected
            )
            rejected_text = f"\nRejected alternatives:\n{rejected_list}"

        return (
            f"📋 **Decision Recorded**\n\n"
            f"**Category**: {decision.category}\n"
            f"**Question**: {decision.question}\n"
            f"**Choice**: {decision.choice}\n"
            f"**Rationale**: {decision.rationale}"
            f"{rejected_text}\n\n"
            f"**Should this be shared with the team?**\n"
            f"This would make it visible to all team members and guide their Sunwell instances.\n\n"
            f"Reply 'yes' to share, or 'no' to keep it personal."
        )

    async def get_pending_promotions(self) -> list[Decision]:
        """Get personal decisions that haven't been promoted yet.

        Finds decisions from RFC-045 that:
        - Are good candidates for promotion (via should_promote)
        - Haven't already been promoted to team

        Returns:
            List of decisions that could be promoted
        """
        if not self.personal_store:
            return []

        personal_decisions = await self.personal_store.get_decisions(active_only=True)
        team_decisions = await self.team_store.get_decisions(active_only=True)

        # Get IDs of already-promoted decisions
        team_ids = {d.id for d in team_decisions}

        # Find candidates
        candidates = []
        for decision in personal_decisions:
            if decision.id not in team_ids and await self.should_promote(decision):
                candidates.append(decision)

        return candidates
