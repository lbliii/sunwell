"""Conflict Resolution - RFC-052.

Handles conflicts in team knowledge that arise from concurrent edits
by different team members.

Strategies:
1. Auto-merge compatible changes (non-conflicting lines in JSONL)
2. Merge endorsements when same decision exists
3. Escalate true conflicts for human resolution
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.team.store import TeamKnowledgeStore

from sunwell.team.types import TeamDecision

__all__ = ["KnowledgeConflict", "ConflictResolver"]


@dataclass(frozen=True, slots=True)
class KnowledgeConflict:
    """A conflict in team knowledge."""

    file: Path
    """File with conflict."""

    type: Literal["merge_conflict", "decision_contradiction", "pattern_override"]
    """Type of conflict."""

    local_version: str | None = None
    """Local version of conflicting content."""

    remote_version: str | None = None
    """Remote version of conflicting content."""

    suggested_resolution: str | None = None
    """AI-suggested resolution."""


class ConflictResolver:
    """Resolves conflicts in team knowledge.

    Strategies:
    1. Auto-merge compatible changes (non-conflicting lines)
    2. Prefer newer decision (timestamp-based) when configured
    3. Merge endorsements when same decision
    4. Escalate true conflicts for human resolution
    """

    def __init__(self, store: TeamKnowledgeStore):
        """Initialize conflict resolver.

        Args:
            store: Team knowledge store instance
        """
        self.store = store

    async def resolve_decision_conflict(
        self,
        local: TeamDecision,
        remote: TeamDecision,
    ) -> TeamDecision | KnowledgeConflict:
        """Attempt to resolve conflicting decisions.

        Resolution strategies:
        1. If same question, different answers → true conflict (escalate)
        2. If one supersedes other → use superseding decision
        3. If different questions → both valid (merge)
        4. If same question and answer → merge endorsements

        Args:
            local: Local version of decision
            remote: Remote version of decision

        Returns:
            Resolved TeamDecision or KnowledgeConflict if unresolvable
        """
        # Same question?
        if self._same_question(local.question, remote.question):
            # Same answer? → merge endorsements
            if local.choice == remote.choice:
                merged_endorsements = tuple(
                    set(local.endorsements) | set(remote.endorsements)
                )
                # Use the one with higher confidence, or newer if equal
                base = local if local.confidence >= remote.confidence else remote
                if local.confidence == remote.confidence:
                    base = local if local.timestamp > remote.timestamp else remote

                return TeamDecision(
                    id=base.id,
                    category=base.category,
                    question=base.question,
                    choice=base.choice,
                    rejected=base.rejected,
                    rationale=base.rationale,
                    confidence=max(local.confidence, remote.confidence),
                    author=base.author,
                    timestamp=base.timestamp,
                    supersedes=base.supersedes,
                    endorsements=merged_endorsements,
                    applies_until=base.applies_until,
                    tags=tuple(set(local.tags) | set(remote.tags)),
                )

            # Different answers → true conflict
            return KnowledgeConflict(
                file=self.store._decisions_path,
                type="decision_contradiction",
                local_version=f"{local.choice} (by {local.author})",
                remote_version=f"{remote.choice} (by {remote.author})",
                suggested_resolution=self._suggest_decision_resolution(local, remote),
            )

        # Different questions → both valid, no conflict
        return local

    def _same_question(self, q1: str, q2: str) -> bool:
        """Check if two questions are semantically the same.

        Simple keyword overlap check. Could be enhanced with embeddings.

        Args:
            q1: First question
            q2: Second question

        Returns:
            True if questions are similar enough to be the same
        """
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        return total > 0 and overlap / total > 0.6

    def _suggest_decision_resolution(
        self,
        local: TeamDecision,
        remote: TeamDecision,
    ) -> str:
        """Suggest resolution for conflicting decisions.

        Args:
            local: Local decision
            remote: Remote decision

        Returns:
            Human-readable suggestion for resolving the conflict
        """
        if local.timestamp > remote.timestamp:
            newer, older = local, remote
        else:
            newer, older = remote, local

        return (
            f"Conflict: '{local.question}'\n"
            f"  {older.author} chose: {older.choice}\n"
            f"  {newer.author} chose: {newer.choice}\n\n"
            f"Suggestion: Discuss with team. Consider:\n"
            f"  1. Is one choice clearly better for the use case?\n"
            f"  2. Can both approaches coexist (conditional decision)?\n"
            f"  3. Should this be a per-developer preference?\n"
        )

    async def resolve_merge_conflict(self, path: Path) -> bool:
        """Attempt to resolve git merge conflict in knowledge file.

        For JSONL files, we can often auto-merge by keeping all unique entries.

        Args:
            path: Path to file with conflict

        Returns:
            True if conflict was resolved, False if manual resolution needed
        """
        if not path.exists():
            return False

        content = path.read_text()
        if "<<<<<<" not in content:
            return True  # No conflict

        # Parse conflict markers
        lines = content.split("\n")
        resolved_lines: list[str] = []
        in_conflict = False
        in_local = False
        local_lines: list[str] = []
        remote_lines: list[str] = []

        for line in lines:
            if line.startswith("<<<<<<<"):
                in_conflict = True
                in_local = True
                local_lines = []
            elif line.startswith("======="):
                in_local = False
                remote_lines = []
            elif line.startswith(">>>>>>>"):
                in_conflict = False
                # Merge: keep all unique entries
                all_entries = set()
                for entry in local_lines + remote_lines:
                    if entry.strip():
                        all_entries.add(entry)
                resolved_lines.extend(sorted(all_entries))
            elif in_conflict:
                if in_local:
                    local_lines.append(line)
                else:
                    remote_lines.append(line)
            else:
                resolved_lines.append(line)

        # Write resolved content
        path.write_text("\n".join(resolved_lines))
        return True

    async def detect_contradictions(
        self,
        decisions: list[TeamDecision],
    ) -> list[KnowledgeConflict]:
        """Detect contradictions among team decisions.

        Finds decisions where:
        - One choice was rejected by another decision
        - Two active decisions answer the same question differently

        Args:
            decisions: List of team decisions to check

        Returns:
            List of detected contradictions
        """
        conflicts: list[KnowledgeConflict] = []
        checked: set[tuple[str, str]] = set()

        for d1 in decisions:
            for d2 in decisions:
                if d1.id == d2.id:
                    continue

                # Skip if already checked this pair
                pair = tuple(sorted([d1.id, d2.id]))
                if pair in checked:
                    continue
                checked.add(pair)

                # Check if same question with different answer
                if self._same_question(d1.question, d2.question) and d1.choice != d2.choice:
                    conflicts.append(
                        KnowledgeConflict(
                            file=self.store._decisions_path,
                            type="decision_contradiction",
                            local_version=f"{d1.choice} (by {d1.author})",
                            remote_version=f"{d2.choice} (by {d2.author})",
                            suggested_resolution=self._suggest_decision_resolution(d1, d2),
                        )
                    )

                # Check if one's choice is the other's rejected option
                for rejected in d1.rejected:
                    if self._similar_choice(rejected.option, d2.choice):
                        conflicts.append(
                            KnowledgeConflict(
                                file=self.store._decisions_path,
                                type="decision_contradiction",
                                local_version=f"{d1.author} rejected '{rejected.option}'",
                                remote_version=f"{d2.author} chose '{d2.choice}'",
                                suggested_resolution=(
                                    f"Decision conflict: {d1.author} rejected "
                                    f"'{rejected.option}' but {d2.author} chose '{d2.choice}'.\n"
                                    f"Reason for rejection: {rejected.reason}\n"
                                    f"Team should align on which approach to use."
                                ),
                            )
                        )

        return conflicts

    def _similar_choice(self, choice1: str, choice2: str) -> bool:
        """Check if two choices are similar.

        Args:
            choice1: First choice
            choice2: Second choice

        Returns:
            True if choices are similar
        """
        c1 = choice1.lower().strip()
        c2 = choice2.lower().strip()
        return c1 == c2 or c1 in c2 or c2 in c1
