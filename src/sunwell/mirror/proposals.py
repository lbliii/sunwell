"""Proposal generation and management for RFC-015 Mirror Neurons.

Provides a system for creating, storing, approving, and applying
improvement proposals with full audit trail and rollback support.
"""


import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ProposalStatus(Enum):
    """Status of an improvement proposal."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


class ProposalType(Enum):
    """Type of improvement proposal."""

    HEURISTIC = "heuristic"
    VALIDATOR = "validator"
    WORKFLOW = "workflow"
    CONFIG = "config"
    TOOL = "tool"


@dataclass(slots=True)
class Proposal:
    """A proposed improvement to Sunwell.

    Proposals are the unit of self-modification. They must be
    created, reviewed, and approved before application.

    Attributes:
        id: Unique identifier (generated)
        type: Type of change (heuristic, validator, etc.)
        title: Human-readable title
        rationale: Why this change is needed
        evidence: Supporting evidence from analysis
        diff: The actual change in diff format
        status: Current status
        created_at: When created
        applied_at: When applied (if applicable)
        rollback_data: Data needed to revert (if applied)
    """

    id: str
    type: ProposalType
    title: str
    rationale: str
    evidence: list[str]
    diff: str
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: datetime | None = None
    rollback_data: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "diff": self.diff,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rollback_data": self.rollback_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        """Create from dict."""
        return cls(
            id=data["id"],
            type=ProposalType(data["type"]),
            title=data["title"],
            rationale=data["rationale"],
            evidence=data["evidence"],
            diff=data["diff"],
            status=ProposalStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            applied_at=(
                datetime.fromisoformat(data["applied_at"])
                if data.get("applied_at")
                else None
            ),
            rollback_data=data.get("rollback_data"),
        )

    def summary(self) -> str:
        """Get a brief summary of the proposal."""
        return (
            f"[{self.id}] {self.title}\n"
            f"  Type: {self.type.value}\n"
            f"  Status: {self.status.value}\n"
            f"  Rationale: {self.rationale[:100]}..."
        )


@dataclass(slots=True)
class ProposalManager:
    """Manage proposals for self-improvement.

    Handles the full lifecycle of proposals:
    - Creation with unique IDs
    - Storage to disk
    - Status transitions
    - Application and rollback

    Proposals are stored as JSON files in the storage directory.
    """

    storage_path: Path

    def __post_init__(self) -> None:
        """Initialize storage directory."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def create_proposal(
        self,
        proposal_type: str | ProposalType,
        title: str,
        rationale: str,
        evidence: list[str],
        diff: str,
    ) -> Proposal:
        """Create a new proposal.

        Args:
            proposal_type: Type of change
            title: Human-readable title
            rationale: Why this change is needed
            evidence: Supporting evidence
            diff: The actual change

        Returns:
            Created Proposal object
        """
        if isinstance(proposal_type, str):
            proposal_type = ProposalType(proposal_type)

        proposal = Proposal(
            id=f"prop_{uuid.uuid4().hex[:8]}",
            type=proposal_type,
            title=title,
            rationale=rationale,
            evidence=evidence,
            diff=diff,
        )

        self._save_proposal(proposal)
        return proposal

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        """Retrieve a proposal by ID.

        Args:
            proposal_id: The proposal ID

        Returns:
            Proposal object or None if not found
        """
        path = self.storage_path / f"{proposal_id}.json"
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        return Proposal.from_dict(data)

    def list_proposals(
        self,
        status: ProposalStatus | None = None,
        proposal_type: ProposalType | None = None,
    ) -> list[Proposal]:
        """List all proposals, optionally filtered.

        Args:
            status: Filter by status
            proposal_type: Filter by type

        Returns:
            List of matching proposals, sorted by creation time (newest first)
        """
        proposals = []
        for path in self.storage_path.glob("prop_*.json"):
            try:
                data = json.loads(path.read_text())

                # Apply filters
                if status is not None and data["status"] != status.value:
                    continue
                if proposal_type is not None and data["type"] != proposal_type.value:
                    continue

                proposals.append(Proposal.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(proposals, key=lambda p: p.created_at, reverse=True)

    def submit_for_review(self, proposal_id: str) -> Proposal:
        """Submit a proposal for review.

        Args:
            proposal_id: The proposal ID

        Returns:
            Updated Proposal

        Raises:
            ValueError: If proposal not found or in wrong state
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        if proposal.status != ProposalStatus.DRAFT:
            raise ValueError(
                f"Can only submit DRAFT proposals. Current: {proposal.status.value}"
            )

        proposal.status = ProposalStatus.PENDING_REVIEW
        self._save_proposal(proposal)
        return proposal

    def approve_proposal(self, proposal_id: str) -> Proposal:
        """Approve a proposal for application.

        Args:
            proposal_id: The proposal ID

        Returns:
            Updated Proposal

        Raises:
            ValueError: If proposal not found or in wrong state
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        if proposal.status != ProposalStatus.PENDING_REVIEW:
            raise ValueError(
                f"Can only approve PENDING_REVIEW proposals. Current: {proposal.status.value}"
            )

        proposal.status = ProposalStatus.APPROVED
        self._save_proposal(proposal)
        return proposal

    def reject_proposal(self, proposal_id: str, reason: str = "") -> Proposal:
        """Reject a proposal.

        Args:
            proposal_id: The proposal ID
            reason: Reason for rejection

        Returns:
            Updated Proposal
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        proposal.status = ProposalStatus.REJECTED
        if reason:
            proposal.evidence.append(f"Rejection reason: {reason}")
        self._save_proposal(proposal)
        return proposal

    def apply_proposal(self, proposal_id: str, rollback_data: str) -> Proposal:
        """Mark a proposal as applied.

        Args:
            proposal_id: The proposal ID
            rollback_data: Data needed to revert the change

        Returns:
            Updated Proposal

        Raises:
            ValueError: If proposal not found or not approved
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError(
                f"Can only apply APPROVED proposals. Current: {proposal.status.value}"
            )

        proposal.status = ProposalStatus.APPLIED
        proposal.applied_at = datetime.now()
        proposal.rollback_data = rollback_data
        self._save_proposal(proposal)
        return proposal

    def rollback_proposal(self, proposal_id: str) -> str:
        """Rollback an applied proposal.

        Args:
            proposal_id: The proposal ID

        Returns:
            Rollback data to use for reverting

        Raises:
            ValueError: If proposal not found, not applied, or no rollback data
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        if proposal.status != ProposalStatus.APPLIED:
            raise ValueError(
                f"Can only rollback APPLIED proposals. Current: {proposal.status.value}"
            )

        if not proposal.rollback_data:
            raise ValueError(f"No rollback data for proposal: {proposal_id}")

        rollback_data = proposal.rollback_data
        proposal.status = ProposalStatus.ROLLED_BACK
        proposal.rollback_data = None
        self._save_proposal(proposal)

        return rollback_data

    def _save_proposal(self, proposal: Proposal) -> None:
        """Save a proposal to disk."""
        path = self.storage_path / f"{proposal.id}.json"
        path.write_text(json.dumps(proposal.to_dict(), indent=2))

    def get_pending_count(self) -> int:
        """Get count of proposals pending review."""
        return len(self.list_proposals(status=ProposalStatus.PENDING_REVIEW))

    def get_stats(self) -> dict[str, Any]:
        """Get proposal statistics."""
        all_proposals = self.list_proposals()

        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for p in all_proposals:
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            by_type[p.type.value] = by_type.get(p.type.value, 0) + 1

        return {
            "total": len(all_proposals),
            "by_status": by_status,
            "by_type": by_type,
        }
