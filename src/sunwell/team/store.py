"""Team Knowledge Store - RFC-052.

Git-tracked storage for team-shared decisions, failures, and patterns.
All team knowledge is stored in `.sunwell/team/` and committed to git.
Changes are detected via git status/diff.

Storage format:
- decisions.jsonl: Team architectural decisions (append-only JSONL)
- failures.jsonl: Team failure patterns (append-only JSONL)
- patterns.yaml: Enforced code patterns (YAML)
- ownership.yaml: File/module ownership map (YAML)
"""

from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.embedding.protocol import EmbeddingProtocol

from sunwell.team.types import (
    RejectedOption,
    TeamDecision,
    TeamFailure,
    TeamOwnership,
    TeamPatterns,
)

__all__ = ["TeamKnowledgeStore", "SyncResult"]


@dataclass
class SyncResult:
    """Result of team knowledge synchronization."""

    success: bool
    """Whether sync completed successfully."""

    new_decisions: list[TeamDecision] = field(default_factory=list)
    """New decisions from team after sync."""

    new_failures: list[TeamFailure] = field(default_factory=list)
    """New failure patterns from team after sync."""

    conflicts: list[str] = field(default_factory=list)
    """Files with unresolved merge conflicts."""

    error: str | None = None
    """Error message if sync failed."""


class TeamKnowledgeStore:
    """Manages team-shared knowledge.

    All team knowledge is stored in .sunwell/team/ and committed to git.
    Changes are detected via git status/diff.
    """

    def __init__(
        self,
        root: Path,
        embedder: "EmbeddingProtocol | None" = None,
    ):
        """Initialize team knowledge store.

        Args:
            root: Project root directory (where .sunwell/ is located)
            embedder: Optional embedder for semantic search
        """
        self.root = Path(root)
        self.team_dir = self.root / ".sunwell" / "team"
        self.team_dir.mkdir(parents=True, exist_ok=True)

        self._decisions_path = self.team_dir / "decisions.jsonl"
        self._failures_path = self.team_dir / "failures.jsonl"
        self._patterns_path = self.team_dir / "patterns.yaml"
        self._ownership_path = self.team_dir / "ownership.yaml"

        self._embedder = embedder

        # In-memory cache
        self._decisions: dict[str, TeamDecision] = {}
        self._failures: dict[str, TeamFailure] = {}
        self._embeddings: dict[str, list[float]] = {}

        # Track last known commit for change detection
        self._last_known_commit: str | None = None

        # Load existing knowledge
        self._load_decisions()
        self._load_failures()

    # =========================================================================
    # DECISIONS
    # =========================================================================

    def _load_decisions(self) -> None:
        """Load decisions from JSONL file."""
        if not self._decisions_path.exists():
            return

        with open(self._decisions_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    decision = TeamDecision.from_dict(data)
                    self._decisions[decision.id] = decision
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    async def record_decision(
        self,
        decision: TeamDecision,
        auto_commit: bool = True,
    ) -> None:
        """Record a team decision.

        Args:
            decision: The decision to record
            auto_commit: If True, commits the change to git
        """
        # Check for existing decision being superseded
        if decision.supersedes and decision.supersedes in self._decisions:
            # Old decision is kept, new one references it via supersedes link
            pass

        # Append to decisions file
        with open(self._decisions_path, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

        self._decisions[decision.id] = decision

        if auto_commit:
            await self._commit(
                f"sunwell: record decision — {decision.question[:50]}",
                [self._decisions_path],
            )

    async def create_decision(
        self,
        category: str,
        question: str,
        choice: str,
        rationale: str,
        author: str,
        rejected: list[tuple[str, str]] | None = None,
        confidence: float = 0.8,
        supersedes: str | None = None,
        tags: list[str] | None = None,
        auto_commit: bool = True,
    ) -> TeamDecision:
        """Create and record a new team decision.

        Args:
            category: Decision category (e.g., 'database', 'auth')
            question: What decision was being made
            choice: What was chosen
            rationale: Why this choice was made
            author: Who made this decision (git email)
            rejected: List of (option, reason) tuples for rejected options
            confidence: Confidence level (0.0-1.0)
            supersedes: ID of decision this replaces (if changed)
            tags: Tags for categorization
            auto_commit: If True, commits the change to git

        Returns:
            The recorded TeamDecision
        """
        decision_id = self._generate_id(category, question, choice)

        rejected_options = tuple(
            RejectedOption(option=opt, reason=reason)
            for opt, reason in (rejected or [])
        )

        decision = TeamDecision(
            id=decision_id,
            category=category,
            question=question,
            choice=choice,
            rejected=rejected_options,
            rationale=rationale,
            confidence=confidence,
            author=author,
            timestamp=datetime.now(),
            supersedes=supersedes,
            tags=tuple(tags or []),
        )

        await self.record_decision(decision, auto_commit=auto_commit)
        return decision

    async def get_decisions(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[TeamDecision]:
        """Get team decisions, optionally filtered.

        Args:
            category: Filter by category (None = all)
            active_only: If True, exclude superseded and expired decisions

        Returns:
            List of team decisions
        """
        decisions = list(self._decisions.values())

        if category:
            decisions = [d for d in decisions if d.category == category]

        if active_only:
            now = datetime.now()
            # Exclude superseded decisions
            superseded_ids = {d.supersedes for d in decisions if d.supersedes}
            decisions = [
                d
                for d in decisions
                if d.id not in superseded_ids
                and (d.applies_until is None or d.applies_until > now)
            ]

        # Sort by timestamp (newest first)
        decisions.sort(key=lambda d: d.timestamp, reverse=True)

        return decisions

    async def find_relevant_decisions(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[TeamDecision]:
        """Find decisions relevant to a query using embeddings.

        Args:
            query: Natural language query
            top_k: Maximum number of decisions to return

        Returns:
            List of relevant decisions sorted by relevance
        """
        if not self._embedder or not self._embeddings:
            # Fall back to keyword search
            return self._keyword_search_decisions(query, top_k)

        try:
            # Embed query
            result = await self._embedder.embed([query])
            query_vec = result.vectors[0].tolist()

            # Calculate similarities
            scores: list[tuple[TeamDecision, float]] = []
            for decision_id, decision_embedding in self._embeddings.items():
                if decision_id not in self._decisions:
                    continue

                decision = self._decisions[decision_id]

                # Skip superseded decisions
                superseded_ids = {d.supersedes for d in self._decisions.values() if d.supersedes}
                if decision.id in superseded_ids:
                    continue

                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_vec, decision_embedding)
                scores.append((decision, similarity))

            # Sort by score and return top_k
            scores.sort(key=lambda x: x[1], reverse=True)
            return [d for d, _ in scores[:top_k]]

        except Exception:
            # Fall back to keyword search on error
            return self._keyword_search_decisions(query, top_k)

    def _keyword_search_decisions(self, query: str, top_k: int) -> list[TeamDecision]:
        """Fallback keyword search when embeddings unavailable."""
        query_lower = query.lower()
        scores: list[tuple[TeamDecision, int]] = []

        superseded_ids = {d.supersedes for d in self._decisions.values() if d.supersedes}

        for decision in self._decisions.values():
            if decision.id in superseded_ids:
                continue

            score = 0
            text = decision.to_text().lower()

            # Count keyword matches
            for word in query_lower.split():
                if word in text:
                    score += 1

            if score > 0:
                scores.append((decision, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [d for d, _ in scores[:top_k]]

    async def check_contradiction(
        self,
        proposed_choice: str,
        category: str,
    ) -> TeamDecision | None:
        """Check if proposed choice contradicts existing team decision.

        Args:
            proposed_choice: The proposed choice
            category: Decision category

        Returns:
            Contradicting decision if found, None otherwise
        """
        decisions = await self.get_decisions(category=category)

        for decision in decisions:
            # Check if proposed choice was previously rejected
            for rejected in decision.rejected:
                if self._similar(proposed_choice, rejected.option):
                    return decision

        return None

    async def endorse_decision(
        self,
        decision_id: str,
        endorser: str,
        auto_commit: bool = True,
    ) -> TeamDecision | None:
        """Add endorsement to an existing decision.

        Args:
            decision_id: ID of decision to endorse
            endorser: Who is endorsing (git email)
            auto_commit: If True, commits the change to git

        Returns:
            Updated decision or None if not found
        """
        if decision_id not in self._decisions:
            return None

        old_decision = self._decisions[decision_id]

        # Don't duplicate endorsements
        if endorser in old_decision.endorsements:
            return old_decision

        # Create updated decision with new endorsement
        new_endorsements = old_decision.endorsements + (endorser,)
        updated = TeamDecision(
            id=old_decision.id,
            category=old_decision.category,
            question=old_decision.question,
            choice=old_decision.choice,
            rejected=old_decision.rejected,
            rationale=old_decision.rationale,
            confidence=min(old_decision.confidence + 0.05, 1.0),  # Boost confidence
            author=old_decision.author,
            timestamp=old_decision.timestamp,
            supersedes=old_decision.supersedes,
            endorsements=new_endorsements,
            applies_until=old_decision.applies_until,
            tags=old_decision.tags,
        )

        # Append endorsement as new record (preserves history)
        with open(self._decisions_path, "a") as f:
            f.write(json.dumps(updated.to_dict()) + "\n")

        self._decisions[decision_id] = updated

        if auto_commit:
            await self._commit(
                f"sunwell: endorse decision — {updated.question[:40]}",
                [self._decisions_path],
            )

        return updated

    # =========================================================================
    # FAILURES
    # =========================================================================

    def _load_failures(self) -> None:
        """Load failures from JSONL file."""
        if not self._failures_path.exists():
            return

        with open(self._failures_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    failure = TeamFailure.from_dict(data)
                    self._failures[failure.id] = failure
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    async def record_failure(
        self,
        failure: TeamFailure,
        auto_commit: bool = True,
    ) -> None:
        """Record a team failure pattern.

        Args:
            failure: The failure to record
            auto_commit: If True, commits the change to git
        """
        # Check for existing similar failure (increment occurrence)
        existing = await self._find_similar_failure(failure)
        if existing:
            # Update occurrence count
            updated = TeamFailure(
                id=existing.id,
                description=existing.description,
                error_type=existing.error_type,
                root_cause=existing.root_cause,
                prevention=existing.prevention,
                author=existing.author,
                timestamp=existing.timestamp,
                occurrences=existing.occurrences + 1,
                affected_files=existing.affected_files,
            )
            self._failures[existing.id] = updated
            # Append updated record
            with open(self._failures_path, "a") as f:
                f.write(json.dumps(updated.to_dict()) + "\n")
        else:
            # Append new failure
            with open(self._failures_path, "a") as f:
                f.write(json.dumps(failure.to_dict()) + "\n")
            self._failures[failure.id] = failure

        if auto_commit:
            await self._commit(
                f"sunwell: record failure — {failure.description[:50]}",
                [self._failures_path],
            )

    async def create_failure(
        self,
        description: str,
        error_type: str,
        root_cause: str,
        prevention: str,
        author: str,
        affected_files: list[str] | None = None,
        auto_commit: bool = True,
    ) -> TeamFailure:
        """Create and record a new team failure pattern.

        Args:
            description: What approach failed
            error_type: Type of failure
            root_cause: Why it failed
            prevention: How to avoid this in the future
            author: Who discovered this failure (git email)
            affected_files: Files/modules where this failure applies
            auto_commit: If True, commits the change to git

        Returns:
            The recorded TeamFailure
        """
        failure_id = self._generate_id(description, error_type, root_cause)

        failure = TeamFailure(
            id=failure_id,
            description=description,
            error_type=error_type,
            root_cause=root_cause,
            prevention=prevention,
            author=author,
            timestamp=datetime.now(),
            affected_files=tuple(affected_files or []),
        )

        await self.record_failure(failure, auto_commit=auto_commit)
        return failure

    async def get_failures(self) -> list[TeamFailure]:
        """Get all team failure patterns.

        Returns:
            List of failure patterns sorted by occurrence count
        """
        failures = list(self._failures.values())
        # Sort by occurrences (most common first)
        failures.sort(key=lambda f: f.occurrences, reverse=True)
        return failures

    async def check_similar_failures(
        self,
        proposed_approach: str,
    ) -> list[TeamFailure]:
        """Check if proposed approach matches past team failures.

        Args:
            proposed_approach: Description of proposed approach

        Returns:
            List of similar failures
        """
        failures = await self.get_failures()
        similar = []

        for failure in failures:
            if self._similar(proposed_approach, failure.description):
                similar.append(failure)

        return similar

    async def _find_similar_failure(
        self,
        failure: TeamFailure,
    ) -> TeamFailure | None:
        """Find an existing similar failure for deduplication."""
        for existing in self._failures.values():
            if (
                existing.error_type == failure.error_type
                and self._similar(existing.description, failure.description)
            ):
                return existing
        return None

    # =========================================================================
    # PATTERNS
    # =========================================================================

    async def get_patterns(self) -> TeamPatterns:
        """Get team code patterns.

        Returns:
            Team patterns (defaults if not configured)
        """
        if not self._patterns_path.exists():
            return TeamPatterns()

        try:
            import yaml

            data = yaml.safe_load(self._patterns_path.read_text())
            return TeamPatterns.from_dict(data or {})
        except Exception:
            return TeamPatterns()

    async def update_patterns(
        self,
        patterns: TeamPatterns,
        auto_commit: bool = True,
    ) -> None:
        """Update team patterns.

        Args:
            patterns: New patterns to set
            auto_commit: If True, commits the change to git
        """
        import yaml

        self._patterns_path.write_text(yaml.dump(patterns.to_dict(), default_flow_style=False))

        if auto_commit:
            await self._commit(
                "sunwell: update team patterns",
                [self._patterns_path],
            )

    # =========================================================================
    # OWNERSHIP
    # =========================================================================

    async def get_ownership(self) -> TeamOwnership:
        """Get file/module ownership mapping.

        Returns:
            Team ownership map (empty if not configured)
        """
        if not self._ownership_path.exists():
            return TeamOwnership()

        try:
            import yaml

            data = yaml.safe_load(self._ownership_path.read_text())
            return TeamOwnership.from_dict(data or {})
        except Exception:
            return TeamOwnership()

    async def update_ownership(
        self,
        ownership: TeamOwnership,
        auto_commit: bool = True,
    ) -> None:
        """Update team ownership mapping.

        Args:
            ownership: New ownership to set
            auto_commit: If True, commits the change to git
        """
        import yaml

        self._ownership_path.write_text(yaml.dump(ownership.to_dict(), default_flow_style=False))

        if auto_commit:
            await self._commit(
                "sunwell: update team ownership",
                [self._ownership_path],
            )

    async def get_owners(self, file_path: Path) -> list[str]:
        """Get owners for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            List of owner identifiers
        """
        ownership = await self.get_ownership()

        # Convert to relative path if needed
        try:
            rel_path = file_path.relative_to(self.root)
        except ValueError:
            rel_path = file_path

        for pattern, owners in ownership.owners.items():
            if self._path_matches(rel_path, pattern):
                return owners

        return []

    # =========================================================================
    # GIT OPERATIONS
    # =========================================================================

    async def _commit(self, message: str, files: list[Path]) -> None:
        """Stage and commit changes.

        Args:
            message: Commit message
            files: Files to stage
        """
        try:
            for file in files:
                rel_path = file.relative_to(self.root)
                await self._run_git(["add", str(rel_path)])

            await self._run_git(["commit", "-m", message])
        except subprocess.CalledProcessError:
            # Commit failed (maybe nothing to commit), that's okay
            pass

    async def sync(self) -> SyncResult:
        """Sync team knowledge with remote.

        1. Stash local changes if any
        2. Pull latest changes
        3. Apply stashed changes
        4. Detect conflicts
        5. Report new knowledge from team

        Returns:
            SyncResult with new knowledge and any conflicts
        """
        # Remember current decisions/failures before sync
        old_decision_ids = set(self._decisions.keys())
        old_failure_ids = set(self._failures.keys())

        # Pull latest
        try:
            await self._run_git(["pull", "--rebase"])
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else str(e)
            if "CONFLICT" in stderr:
                conflicts = await self._detect_conflicts()
                return SyncResult(
                    success=False,
                    conflicts=conflicts,
                    error="Merge conflicts detected",
                )
            return SyncResult(
                success=False,
                error=f"Git pull failed: {stderr}",
            )

        # Reload to pick up changes
        self._decisions.clear()
        self._failures.clear()
        self._load_decisions()
        self._load_failures()

        # Detect new knowledge
        new_decisions = [
            d for d in self._decisions.values() if d.id not in old_decision_ids
        ]
        new_failures = [
            f for f in self._failures.values() if f.id not in old_failure_ids
        ]

        return SyncResult(
            success=True,
            new_decisions=new_decisions,
            new_failures=new_failures,
        )

    async def push(self) -> bool:
        """Push local team knowledge changes to remote.

        Returns:
            True if push succeeded
        """
        try:
            await self._run_git(["push"])
            return True
        except subprocess.CalledProcessError:
            return False

    async def _run_git(self, args: list[str]) -> str:
        """Run a git command.

        Args:
            args: Git command arguments

        Returns:
            Command output

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            check=True,
        )
        return result.stdout.decode()

    async def _detect_conflicts(self) -> list[str]:
        """Detect files with merge conflicts.

        Returns:
            List of file paths with conflicts
        """
        conflicts = []

        for path in [self._decisions_path, self._failures_path]:
            if path.exists():
                content = path.read_text()
                if "<<<<<<" in content or "======" in content:
                    conflicts.append(str(path.relative_to(self.root)))

        return conflicts

    async def get_git_user(self) -> str:
        """Get current git user email.

        Returns:
            Git user email or 'unknown'
        """
        try:
            result = await self._run_git(["config", "user.email"])
            return result.strip()
        except subprocess.CalledProcessError:
            return "unknown"

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _generate_id(self, *parts: str) -> str:
        """Generate unique ID from content parts."""
        content = ":".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _similar(self, a: str, b: str) -> bool:
        """Check if two strings are similar (simple keyword overlap)."""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        overlap = len(a_words & b_words)
        total = len(a_words | b_words)
        return total > 0 and overlap / total >= 0.5

    def _path_matches(self, path: Path, pattern: str) -> bool:
        """Check if path matches a glob pattern."""
        return fnmatch(str(path), pattern)

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot = sum(x * y for x, y in zip(a, b, strict=True))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(self) -> dict[str, int]:
        """Get team knowledge statistics.

        Returns:
            Dict with counts of decisions, failures, etc.
        """
        decisions = await self.get_decisions()
        failures = await self.get_failures()

        # Count by category
        categories: dict[str, int] = {}
        for d in decisions:
            categories[d.category] = categories.get(d.category, 0) + 1

        return {
            "total_decisions": len(decisions),
            "total_failures": len(failures),
            "categories": categories,  # type: ignore[dict-item]
        }
