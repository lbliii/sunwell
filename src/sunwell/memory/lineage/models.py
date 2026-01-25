"""Artifact lineage data models (RFC-121).

Track the complete lineage of every artifact: which goal spawned it,
which model wrote it, what edits were made, and how it relates to other artifacts.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import uuid4

EditType = Literal["create", "modify", "rename", "delete"]
EditSource = Literal["sunwell", "human", "external"]


@dataclass(frozen=True, slots=True)
class ArtifactEdit:
    """A single edit to an artifact."""

    edit_id: str
    artifact_id: str
    goal_id: str | None
    task_id: str | None

    # Change info
    lines_added: int
    lines_removed: int
    edit_type: EditType

    # Attribution
    source: EditSource
    model: str | None

    # Timing
    timestamp: datetime
    session_id: str | None

    # Git correlation
    commit_hash: str | None

    # Content snapshot for rename detection
    content_hash: str | None

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "edit_id": self.edit_id,
            "artifact_id": self.artifact_id,
            "goal_id": self.goal_id,
            "task_id": self.task_id,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "edit_type": self.edit_type,
            "source": self.source,
            "model": self.model,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "commit_hash": self.commit_hash,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactEdit":
        """Deserialize from dict."""
        return cls(
            edit_id=data["edit_id"],
            artifact_id=data["artifact_id"],
            goal_id=data.get("goal_id"),
            task_id=data.get("task_id"),
            lines_added=data["lines_added"],
            lines_removed=data["lines_removed"],
            edit_type=data["edit_type"],
            source=data["source"],
            model=data.get("model"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id"),
            commit_hash=data.get("commit_hash"),
            content_hash=data.get("content_hash"),
        )


@dataclass(frozen=True, slots=True)
class ArtifactLineage:
    """Lineage record for a single artifact."""

    # Identity
    artifact_id: str
    path: str
    content_hash: str

    # Birth
    created_by_goal: str | None
    created_by_task: str | None
    created_at: datetime
    created_reason: str

    # Attribution
    model: str | None
    human_edited: bool

    # History
    edits: tuple[ArtifactEdit, ...]

    # Dependencies
    imports: tuple[str, ...]
    imported_by: tuple[str, ...]

    # Soft delete tracking
    deleted_at: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "content_hash": self.content_hash,
            "created_by_goal": self.created_by_goal,
            "created_by_task": self.created_by_task,
            "created_at": self.created_at.isoformat(),
            "created_reason": self.created_reason,
            "model": self.model,
            "human_edited": self.human_edited,
            "edits": [e.to_dict() for e in self.edits],
            "imports": list(self.imports),
            "imported_by": list(self.imported_by),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactLineage":
        """Deserialize from dict."""
        return cls(
            artifact_id=data["artifact_id"],
            path=data["path"],
            content_hash=data["content_hash"],
            created_by_goal=data.get("created_by_goal"),
            created_by_task=data.get("created_by_task"),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_reason=data["created_reason"],
            model=data.get("model"),
            human_edited=data["human_edited"],
            edits=tuple(ArtifactEdit.from_dict(e) for e in data.get("edits", [])),
            imports=tuple(data.get("imports", [])),
            imported_by=tuple(data.get("imported_by", [])),
            deleted_at=(
                datetime.fromisoformat(data["deleted_at"])
                if data.get("deleted_at")
                else None
            ),
        )

    def with_edit(self, edit: ArtifactEdit) -> "ArtifactLineage":
        """Return new lineage with edit appended."""
        return ArtifactLineage(
            artifact_id=self.artifact_id,
            path=self.path,
            content_hash=edit.content_hash or self.content_hash,
            created_by_goal=self.created_by_goal,
            created_by_task=self.created_by_task,
            created_at=self.created_at,
            created_reason=self.created_reason,
            model=self.model,
            human_edited=self.human_edited or edit.source == "human",
            edits=(*self.edits, edit),
            imports=self.imports,
            imported_by=self.imported_by,
            deleted_at=self.deleted_at,
        )

    def with_path(self, new_path: str) -> "ArtifactLineage":
        """Return new lineage with updated path."""
        return ArtifactLineage(
            artifact_id=self.artifact_id,
            path=new_path,
            content_hash=self.content_hash,
            created_by_goal=self.created_by_goal,
            created_by_task=self.created_by_task,
            created_at=self.created_at,
            created_reason=self.created_reason,
            model=self.model,
            human_edited=self.human_edited,
            edits=self.edits,
            imports=self.imports,
            imported_by=self.imported_by,
            deleted_at=self.deleted_at,
        )

    def with_deleted(self, deleted_at: datetime) -> "ArtifactLineage":
        """Return new lineage marked as deleted."""
        return ArtifactLineage(
            artifact_id=self.artifact_id,
            path=self.path,
            content_hash=self.content_hash,
            created_by_goal=self.created_by_goal,
            created_by_task=self.created_by_task,
            created_at=self.created_at,
            created_reason=self.created_reason,
            model=self.model,
            human_edited=self.human_edited,
            edits=self.edits,
            imports=self.imports,
            imported_by=self.imported_by,
            deleted_at=deleted_at,
        )

    def with_imports(
        self, imports: tuple[str, ...], imported_by: tuple[str, ...]
    ) -> "ArtifactLineage":
        """Return new lineage with updated dependency info."""
        return ArtifactLineage(
            artifact_id=self.artifact_id,
            path=self.path,
            content_hash=self.content_hash,
            created_by_goal=self.created_by_goal,
            created_by_task=self.created_by_task,
            created_at=self.created_at,
            created_reason=self.created_reason,
            model=self.model,
            human_edited=self.human_edited,
            edits=self.edits,
            imports=imports,
            imported_by=imported_by,
            deleted_at=self.deleted_at,
        )


def generate_artifact_id(path: str, content: str) -> str:
    """Generate stable artifact ID.

    Format: {uuid}:{content_hash_prefix}
    Example: "a1b2c3d4-e5f6-7890-abcd-ef1234567890:abc123def456"

    The UUID ensures uniqueness while the content hash prefix
    aids in rename detection.
    """
    uuid_part = str(uuid4())
    content_hash = compute_content_hash(content)[:12]
    return f"{uuid_part}:{content_hash}"


def compute_content_hash(content: str) -> str:
    """Compute SHA256 content hash for similarity detection."""
    return hashlib.sha256(content.encode()).hexdigest()
