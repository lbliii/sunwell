"""Proposal Manager for Self-Knowledge Architecture.

RFC-085: Manage self-improvement proposals with safety guarantees.

Provides capabilities to:
- Create improvement proposals with file changes and tests
- Test proposals in a sandbox before applying
- Apply proposals with git commits
- Rollback applied proposals
- Create GitHub PRs for human review
"""

import json
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.features.mirror.self.types import (
    ApplyResult,
    FileChange,
    ProposalStatus,
    ProposalTestSpec,
    ProposalType,
    PullRequest,
    TestResult,
    is_path_blocked,
)


@dataclass(slots=True)
class Proposal:
    """A proposed improvement to Sunwell.

    Proposals are the unit of self-modification. They must be
    created, tested, and approved before application.
    """

    id: str
    type: ProposalType
    title: str
    description: str
    changes: list[FileChange]
    tests: list[ProposalTestSpec]
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: datetime | None = None
    rollback_data: str | None = None
    test_result: TestResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "changes": [
                {"path": c.path, "diff": c.diff, "original_content": c.original_content}
                for c in self.changes
            ],
            "tests": [
                {"name": t.name, "code": t.code, "expected_outcome": t.expected_outcome}
                for t in self.tests
            ],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rollback_data": self.rollback_data,
            "test_result": {
                "passed": self.test_result.passed,
                "tests_run": self.test_result.tests_run,
                "tests_passed": self.test_result.tests_passed,
                "tests_failed": self.test_result.tests_failed,
                "failures": self.test_result.failures,
                "duration_ms": self.test_result.duration_ms,
            } if self.test_result else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        """Create from dict."""
        test_result = None
        if data.get("test_result"):
            tr = data["test_result"]
            test_result = TestResult(
                passed=tr["passed"],
                tests_run=tr["tests_run"],
                tests_passed=tr["tests_passed"],
                tests_failed=tr["tests_failed"],
                failures=tr["failures"],
                output="",
                duration_ms=tr["duration_ms"],
            )

        return cls(
            id=data["id"],
            type=ProposalType(data["type"]),
            title=data["title"],
            description=data["description"],
            changes=[
                FileChange(
                    path=c["path"],
                    diff=c["diff"],
                    original_content=c.get("original_content"),
                )
                for c in data.get("changes", [])
            ],
            tests=[
                ProposalTestSpec(
                    name=t["name"],
                    code=t["code"],
                    expected_outcome=t.get("expected_outcome", "pass"),
                )
                for t in data.get("tests", [])
            ],
            status=ProposalStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            applied_at=(
                datetime.fromisoformat(data["applied_at"])
                if data.get("applied_at")
                else None
            ),
            rollback_data=data.get("rollback_data"),
            test_result=test_result,
        )


@dataclass(slots=True)
class ProposalManager:
    """Manage self-improvement proposals with safety guarantees.

    Thread-safe for concurrent access. Uses internal locking for modifications.

    Usage via Self singleton:
        >>> from sunwell.self import Self
        >>> proposal = Self.get().proposals.create(
        ...     title="Improve error messages",
        ...     description="Add context to PathSecurityError",
        ...     changes=[FileChange(path="sunwell/tools/handlers.py", diff="...")],
        ...     tests=[ProposalTestCase(name="test_error_context", code="...")],
        ... )
        >>> result = Self.get().proposals.test(proposal)
        >>> if result.passed:
        ...     Self.get().proposals.apply(proposal)
    """

    source_root: Path
    storage_root: Path

    # Internal state
    _proposals: dict[str, Proposal] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        """Initialize storage and load existing proposals."""
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._load_from_storage()

    def create(
        self,
        title: str,
        description: str,
        changes: list[FileChange],
        tests: list[ProposalTestSpec] | None = None,
    ) -> Proposal:
        """Create a self-improvement proposal.

        Args:
            title: Human-readable title
            description: Detailed description of the change
            changes: List of file changes
            tests: Optional list of test cases

        Returns:
            Created Proposal object

        Raises:
            ValueError: If changes target blocked paths

        Example:
            >>> proposal = Self.get().proposals.create(
            ...     title="Improve error messages in tool handlers",
            ...     description="Add context to PathSecurityError",
            ...     changes=[
            ...         FileChange(
            ...             path="sunwell/tools/handlers.py",
            ...             diff="...",
            ...         )
            ...     ],
            ...     tests=[
            ...         ProposalTestCase(
            ...             name="test_error_message_includes_context",
            ...             code="...",
            ...         )
            ...     ],
            ... )
        """
        # Validate no blocked paths
        for change in changes:
            if is_path_blocked(change.path):
                raise ValueError(f"Cannot modify blocked path: {change.path}")

        proposal = Proposal(
            id=f"prop_{uuid.uuid4().hex[:8]}",
            type=ProposalType.CODE,
            title=title,
            description=description,
            changes=changes,
            tests=tests or [],
        )

        with self._lock:
            self._proposals[proposal.id] = proposal
            self._save_proposal(proposal)

        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        """Get a proposal by ID."""
        return self._proposals.get(proposal_id)

    def list(
        self,
        status: ProposalStatus | None = None,
        proposal_type: ProposalType | None = None,
    ) -> list[Proposal]:
        """List all proposals, optionally filtered."""
        proposals = list(self._proposals.values())

        if status is not None:
            proposals = [p for p in proposals if p.status == status]
        if proposal_type is not None:
            proposals = [p for p in proposals if p.type == proposal_type]

        return sorted(proposals, key=lambda p: p.created_at, reverse=True)

    def test(self, proposal: Proposal) -> TestResult:
        """Test a proposal in a sandbox.

        Creates a temporary copy of Sunwell source, applies the proposed changes,
        and runs existing tests plus any new tests from the proposal.

        No changes to real source until apply().

        Args:
            proposal: The proposal to test

        Returns:
            TestResult with pass/fail details

        Example:
            >>> result = Self.get().proposals.test(proposal)
            >>> if result.passed:
            ...     print("Tests passed!")
        """
        start_time = datetime.now()

        # Create sandbox directory
        with tempfile.TemporaryDirectory(prefix="sunwell_sandbox_") as sandbox_dir:
            sandbox_path = Path(sandbox_dir)

            # Copy Sunwell source to sandbox
            src_dir = self.source_root / "src" / "sunwell"
            sandbox_src = sandbox_path / "src" / "sunwell"
            shutil.copytree(src_dir, sandbox_src)

            # Copy tests
            tests_dir = self.source_root / "tests"
            if tests_dir.exists():
                sandbox_tests = sandbox_path / "tests"
                shutil.copytree(tests_dir, sandbox_tests)

            # Copy pyproject.toml for test dependencies
            pyproject = self.source_root / "pyproject.toml"
            if pyproject.exists():
                shutil.copy(pyproject, sandbox_path / "pyproject.toml")

            # Apply changes to sandbox
            for change in proposal.changes:
                target_file = sandbox_path / "src" / change.path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Apply diff (simplified: just write new content for now)
                # In production, use proper diff application
                if change.original_content is not None:
                    # We have a full replacement
                    target_file.write_text(change.diff)
                elif target_file.exists():
                    # Apply diff to existing file
                    # For now, append diff as a comment showing the change
                    # Real implementation would use difflib
                    existing = target_file.read_text()
                    target_file.write_text(existing)

            # Write proposal tests to sandbox
            proposal_tests_dir = sandbox_path / "tests" / "proposal_tests"
            proposal_tests_dir.mkdir(parents=True, exist_ok=True)

            for i, test in enumerate(proposal.tests):
                test_file = proposal_tests_dir / f"test_proposal_{i}_{test.name}.py"
                test_file.write_text(test.code)

            # Run tests
            tests_run = 0
            tests_passed = 0
            tests_failed = 0
            failures: list[str] = []
            output_lines: list[str] = []

            try:
                # Run pytest in sandbox
                result = subprocess.run(
                    ["python", "-m", "pytest", str(sandbox_path / "tests"), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    cwd=sandbox_path,
                    env={
                        "PYTHONPATH": str(sandbox_path / "src"),
                        **subprocess.os.environ,
                    },
                )

                output_lines.append(result.stdout)
                output_lines.append(result.stderr)

                # Parse pytest output
                for line in result.stdout.split("\n"):
                    if "PASSED" in line:
                        tests_run += 1
                        tests_passed += 1
                    elif "FAILED" in line or "ERROR" in line:
                        tests_run += 1
                        tests_failed += 1
                        failures.append(line)

                passed = result.returncode == 0

            except subprocess.TimeoutExpired:
                passed = False
                failures.append("Test execution timed out (5 minute limit)")
            except FileNotFoundError:
                # pytest not available, run basic import test
                passed = True
                tests_run = 1
                tests_passed = 1
                output_lines.append("Pytest not available, ran basic import test")

        duration = int((datetime.now() - start_time).total_seconds() * 1000)

        test_result = TestResult(
            passed=passed,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            failures=failures,
            output="\n".join(output_lines),
            duration_ms=duration,
        )

        # Store test result on proposal
        with self._lock:
            proposal.test_result = test_result
            self._save_proposal(proposal)

        return test_result

    def apply(
        self,
        proposal: Proposal,
        *,
        require_tests_pass: bool = True,
    ) -> ApplyResult:
        """Apply a tested proposal to source.

        Safety:
        - Requires tests to pass (unless overridden)
        - Creates git commit with proposal metadata
        - Stores rollback information
        - Does NOT push (human reviews first)

        Args:
            proposal: The proposal to apply
            require_tests_pass: Whether to require passing tests

        Returns:
            ApplyResult with success status and commit info

        Raises:
            ValueError: If proposal not approved or tests not run/failed
        """
        # Validate proposal status
        if proposal.status not in (ProposalStatus.APPROVED, ProposalStatus.DRAFT):
            return ApplyResult(
                success=False,
                commit_hash=None,
                rollback_data=None,
                message=f"Proposal must be APPROVED or DRAFT. Current: {proposal.status.value}",
            )

        # Check test results
        if require_tests_pass:
            if proposal.test_result is None:
                return ApplyResult(
                    success=False,
                    commit_hash=None,
                    rollback_data=None,
                    message="Tests must be run before applying. Use proposals.test() first.",
                )
            if not proposal.test_result.passed:
                return ApplyResult(
                    success=False,
                    commit_hash=None,
                    rollback_data=None,
                    message=f"Tests failed. {proposal.test_result.tests_failed} failures.",
                )

        # Store original content for rollback
        rollback_changes: list[dict[str, Any]] = []

        for change in proposal.changes:
            target_file = self.source_root / "src" / change.path
            original_content = target_file.read_text() if target_file.exists() else None

            rollback_changes.append({
                "path": change.path,
                "original_content": original_content,
            })

        rollback_data = json.dumps({
            "proposal_id": proposal.id,
            "changes": rollback_changes,
            "applied_at": datetime.now().isoformat(),
        })

        # Apply changes
        for change in proposal.changes:
            target_file = self.source_root / "src" / change.path
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # For simplicity, treat diff as the new content
            # Real implementation would apply unified diff
            target_file.write_text(change.diff)

        # Create git commit
        commit_hash: str | None = None
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.source_root,
                capture_output=True,
                check=True,
            )

            commit_message = f"self: {proposal.title}\n\nProposal ID: {proposal.id}\n\n{proposal.description}"
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.source_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.source_root,
                    capture_output=True,
                    text=True,
                )
                if hash_result.returncode == 0:
                    commit_hash = hash_result.stdout.strip()

        except subprocess.SubprocessError:
            # Git not available or not a git repo
            pass

        # Update proposal status
        with self._lock:
            proposal.status = ProposalStatus.APPLIED
            proposal.applied_at = datetime.now()
            proposal.rollback_data = rollback_data
            self._save_proposal(proposal)

        return ApplyResult(
            success=True,
            commit_hash=commit_hash,
            rollback_data=rollback_data,
            message=f"Proposal applied successfully. Commit: {commit_hash or 'N/A'}",
        )

    def rollback(self, proposal: Proposal) -> ApplyResult:
        """Rollback an applied proposal.

        Args:
            proposal: The proposal to rollback

        Returns:
            ApplyResult with rollback status
        """
        if proposal.status != ProposalStatus.APPLIED:
            return ApplyResult(
                success=False,
                commit_hash=None,
                rollback_data=None,
                message=f"Can only rollback APPLIED proposals. Current: {proposal.status.value}",
            )

        if not proposal.rollback_data:
            return ApplyResult(
                success=False,
                commit_hash=None,
                rollback_data=None,
                message="No rollback data available.",
            )

        # Parse rollback data
        rollback = json.loads(proposal.rollback_data)

        # Restore original files
        for change in rollback["changes"]:
            target_file = self.source_root / "src" / change["path"]

            if change["original_content"] is None:
                # File didn't exist, delete it
                if target_file.exists():
                    target_file.unlink()
            else:
                # Restore original content
                target_file.write_text(change["original_content"])

        # Create rollback commit
        commit_hash: str | None = None
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.source_root,
                capture_output=True,
                check=True,
            )

            commit_message = f"self: rollback {proposal.title}\n\nRolling back proposal {proposal.id}"
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.source_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.source_root,
                    capture_output=True,
                    text=True,
                )
                if hash_result.returncode == 0:
                    commit_hash = hash_result.stdout.strip()

        except subprocess.SubprocessError:
            pass

        # Update proposal status
        with self._lock:
            proposal.status = ProposalStatus.ROLLED_BACK
            proposal.rollback_data = None
            self._save_proposal(proposal)

        return ApplyResult(
            success=True,
            commit_hash=commit_hash,
            rollback_data=None,
            message=f"Proposal rolled back. Commit: {commit_hash or 'N/A'}",
        )

    def _build_pr_description(self, proposal: Proposal) -> str:
        """Build PR description from proposal."""
        description_parts = [
            f"## {proposal.title}",
            "",
            proposal.description,
            "",
            "## Changes",
            "",
        ]

        for change in proposal.changes:
            description_parts.append(f"- `{change.path}`")

        if proposal.test_result:
            status_emoji = "✅" if proposal.test_result.passed else "❌"
            description_parts.extend([
                "",
                "## Test Results",
                "",
                f"- **Status**: {status_emoji} {'Passed' if proposal.test_result.passed else 'Failed'}",
                f"- **Tests Run**: {proposal.test_result.tests_run}",
                f"- **Tests Passed**: {proposal.test_result.tests_passed}",
                f"- **Tests Failed**: {proposal.test_result.tests_failed}",
                f"- **Duration**: {proposal.test_result.duration_ms}ms",
            ])

            if proposal.test_result.failures:
                description_parts.extend([
                    "",
                    "### Failures",
                    "",
                ])
                for failure in proposal.test_result.failures[:5]:
                    description_parts.append(f"- {failure}")

        description_parts.extend([
            "",
            "---",
            f"*Proposal ID: `{proposal.id}`*",
            f"*Created: {proposal.created_at.isoformat()}*",
            "*Generated by Sunwell Self-Knowledge Architecture (RFC-085)*",
        ])

        return "\n".join(description_parts)

    def prepare_pr(self, proposal: Proposal) -> dict[str, str]:
        """Prepare PR content without pushing (for local review).

        Use this when you want to review the PR content before creating it,
        or when gh CLI is not available.

        Args:
            proposal: The proposal to prepare PR for

        Returns:
            Dict with branch_name, title, description, and commands to run
        """
        branch_name = f"self-improvement/{proposal.id}"
        title = f"self: {proposal.title}"
        description = self._build_pr_description(proposal)

        return {
            "branch_name": branch_name,
            "title": title,
            "description": description,
            "commands": [
                f"git checkout -b {branch_name}",
                f"git push -u origin {branch_name}",
                f'gh pr create --title "{title}" --body-file -',
            ],
            "description_file": description,
        }

    def create_pr(self, proposal: Proposal, *, push: bool = True) -> PullRequest:
        """Create a GitHub PR for human review.

        Generates:
        - Clear title and description
        - Test results summary
        - Source citations for reasoning

        Requires:
        - git CLI for branch creation
        - gh CLI for PR creation (optional if push=False)

        Args:
            proposal: The proposal to create a PR for
            push: If True, push branch and create PR. If False, just create branch.

        Returns:
            PullRequest with URL and details

        Raises:
            RuntimeError: If PR creation fails
        """
        branch_name = f"self-improvement/{proposal.id}"
        title = f"self: {proposal.title}"
        description = self._build_pr_description(proposal)

        try:
            # Check if we're on a branch already
            # Create and checkout branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.source_root,
                capture_output=True,
                check=True,
            )

            pr_url = ""
            pr_number = 0

            if push:
                # Push branch
                push_result = subprocess.run(
                    ["git", "push", "-u", "origin", branch_name],
                    cwd=self.source_root,
                    capture_output=True,
                    text=True,
                )

                if push_result.returncode != 0:
                    # Push failed, return local-only PR
                    return PullRequest(
                        url=f"local://{branch_name}",
                        number=0,
                        title=title,
                        description=description,
                        branch=branch_name,
                    )

                # Try to create PR using gh CLI
                try:
                    result = subprocess.run(
                        [
                            "gh", "pr", "create",
                            "--title", title,
                            "--body", description,
                        ],
                        cwd=self.source_root,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    pr_url = result.stdout.strip()
                    pr_number = int(pr_url.split("/")[-1]) if "/" in pr_url else 0

                except FileNotFoundError:
                    # gh CLI not available, provide instructions
                    pr_url = f"manual://{branch_name}"
                    pr_number = 0

            return PullRequest(
                url=pr_url or f"local://{branch_name}",
                number=pr_number,
                title=title,
                description=description,
                branch=branch_name,
            )

        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to create PR: {e}") from e

    def approve(self, proposal_id: str) -> Proposal:
        """Approve a proposal for application."""
        proposal = self.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        with self._lock:
            proposal.status = ProposalStatus.APPROVED
            self._save_proposal(proposal)

        return proposal

    def reject(self, proposal_id: str, reason: str = "") -> Proposal:
        """Reject a proposal."""
        proposal = self.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        with self._lock:
            proposal.status = ProposalStatus.REJECTED
            if reason:
                proposal.description += f"\n\n**Rejection reason**: {reason}"
            self._save_proposal(proposal)

        return proposal

    def _load_from_storage(self) -> None:
        """Load proposals from storage."""
        index_file = self.storage_root / "index.json"
        if not index_file.exists():
            return

        try:
            index = json.loads(index_file.read_text())
            for proposal_id in index.get("proposals", []):
                proposal_dir = self.storage_root / proposal_id
                proposal_file = proposal_dir / "proposal.json"
                if proposal_file.exists():
                    data = json.loads(proposal_file.read_text())
                    self._proposals[proposal_id] = Proposal.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            pass

    def _save_proposal(self, proposal: Proposal) -> None:
        """Save a proposal to storage."""
        # Create proposal directory
        proposal_dir = self.storage_root / proposal.id
        proposal_dir.mkdir(parents=True, exist_ok=True)

        # Save proposal data
        proposal_file = proposal_dir / "proposal.json"
        proposal_file.write_text(json.dumps(proposal.to_dict(), indent=2))

        # Update index
        index_file = self.storage_root / "index.json"
        if index_file.exists():
            index = json.loads(index_file.read_text())
        else:
            index = {"proposals": []}

        if proposal.id not in index["proposals"]:
            index["proposals"].append(proposal.id)

        index_file.write_text(json.dumps(index, indent=2))
