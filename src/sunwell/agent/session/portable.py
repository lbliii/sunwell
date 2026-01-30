"""Portable session for cross-channel state transfer.

Enables session state to be exported, serialized, and imported
in a different channel (CLI → web, etc.).
"""

import base64
import hashlib
import json
import logging
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.agent.chat.checkpoint import ChatCheckpoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionToken:
    """A token representing a portable session.

    Can be used to share sessions via URL or text.

    Attributes:
        token: The compressed, base64-encoded session data
        session_id: Session identifier for reference
        created_at: When the token was created
        expires_at: When the token expires (optional)
    """

    token: str
    session_id: str
    created_at: datetime
    expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_url(self, base_url: str = "sunwell://session") -> str:
        """Convert to a shareable URL.

        Args:
            base_url: Base URL scheme

        Returns:
            URL with token as query parameter
        """
        return f"{base_url}?token={self.token}"


@dataclass
class PortableSession:
    """Portable session state for cross-channel transfer.

    Contains all state needed to resume a session in a different channel.

    Attributes:
        session_id: Unique session identifier
        workspace: Workspace path (relative or absolute)
        conversation_history: List of conversation messages
        current_dag_path: Current intent DAG path (as string tuple)
        pending_checkpoint: Checkpoint awaiting response (if any)
        snapshot_ids: IDs of available code snapshots
        auto_approve_paths: Paths with auto-approve enabled
        created_at: When session was created
        exported_at: When this export was created
        metadata: Additional metadata
    """

    session_id: str
    workspace: str
    conversation_history: list[dict[str, str]]
    current_dag_path: tuple[str, ...] | None = None
    pending_checkpoint: dict[str, Any] | None = None
    snapshot_ids: list[str] = field(default_factory=list)
    auto_approve_paths: list[tuple[str, ...]] = field(default_factory=list)
    created_at: datetime | None = None
    exported_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.exported_at is None:
            object.__setattr__(self, "exported_at", datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": 1,
            "session_id": self.session_id,
            "workspace": self.workspace,
            "conversation_history": self.conversation_history,
            "current_dag_path": list(self.current_dag_path) if self.current_dag_path else None,
            "pending_checkpoint": self.pending_checkpoint,
            "snapshot_ids": self.snapshot_ids,
            "auto_approve_paths": [list(p) for p in self.auto_approve_paths],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PortableSession":
        """Deserialize from dictionary."""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])

        exported_at = None
        if data.get("exported_at"):
            exported_at = datetime.fromisoformat(data["exported_at"])

        dag_path = None
        if data.get("current_dag_path"):
            dag_path = tuple(data["current_dag_path"])

        auto_paths = [tuple(p) for p in data.get("auto_approve_paths", [])]

        return cls(
            session_id=data["session_id"],
            workspace=data["workspace"],
            conversation_history=data.get("conversation_history", []),
            current_dag_path=dag_path,
            pending_checkpoint=data.get("pending_checkpoint"),
            snapshot_ids=data.get("snapshot_ids", []),
            auto_approve_paths=auto_paths,
            created_at=created_at,
            exported_at=exported_at,
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PortableSession":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_token(self, expires_hours: int | None = 24) -> SessionToken:
        """Create a shareable token from this session.

        The token is compressed and base64-encoded for easy sharing.

        Args:
            expires_hours: Hours until token expires (None for no expiry)

        Returns:
            SessionToken that can be shared
        """
        # Serialize to JSON
        json_data = json.dumps(self.to_dict())

        # Compress
        compressed = zlib.compress(json_data.encode("utf-8"), level=9)

        # Base64 encode
        token = base64.urlsafe_b64encode(compressed).decode("ascii")

        # Calculate expiry
        expires_at = None
        if expires_hours is not None:
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

        return SessionToken(
            token=token,
            session_id=self.session_id,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

    @classmethod
    def from_token(cls, token: str) -> "PortableSession":
        """Restore session from a token.

        Args:
            token: The token string (base64-encoded, compressed)

        Returns:
            PortableSession restored from token

        Raises:
            ValueError: If token is invalid or corrupted
        """
        try:
            # Base64 decode
            compressed = base64.urlsafe_b64decode(token.encode("ascii"))

            # Decompress
            json_data = zlib.decompress(compressed).decode("utf-8")

            # Parse JSON
            data = json.loads(json_data)

            return cls.from_dict(data)

        except Exception as e:
            raise ValueError(f"Invalid session token: {e}") from e

    def save(self, path: Path) -> None:
        """Save session to file.

        Args:
            path: Path to save to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
        logger.debug("Saved portable session to %s", path)

    @classmethod
    def load(cls, path: Path) -> "PortableSession":
        """Load session from file.

        Args:
            path: Path to load from

        Returns:
            Loaded PortableSession
        """
        path = Path(path)
        json_str = path.read_text()
        return cls.from_json(json_str)

    @classmethod
    def from_chat_loop(
        cls,
        loop: Any,  # UnifiedChatLoop
        pending_checkpoint: ChatCheckpoint | None = None,
    ) -> "PortableSession":
        """Create portable session from a UnifiedChatLoop instance.

        Args:
            loop: The chat loop to export
            pending_checkpoint: Checkpoint awaiting response (if any)

        Returns:
            PortableSession with loop state
        """
        # Get session ID
        session_id = "unknown"
        if hasattr(loop, "session") and loop.session:
            session_id = loop.session.session_id

        # Get current DAG path
        dag_path = None
        if hasattr(loop, "_current_dag_path") and loop._current_dag_path:
            dag_path = tuple(n.value for n in loop._current_dag_path)

        # Get auto-approve paths
        auto_paths: list[tuple[str, ...]] = []
        if hasattr(loop, "_auto_approve_config") and loop._auto_approve_config:
            rules = loop._auto_approve_config.list_rules(enabled_only=True)
            auto_paths = [r.intent_path for r in rules]

        # Get snapshot IDs
        snapshot_ids: list[str] = []
        if hasattr(loop, "_snapshot_manager") and loop._snapshot_manager:
            snapshots = loop._snapshot_manager.list_snapshots(limit=10)
            snapshot_ids = [s.id for s in snapshots]

        # Convert pending checkpoint if provided
        checkpoint_dict = None
        if pending_checkpoint:
            checkpoint_dict = {
                "type": pending_checkpoint.type.value,
                "message": pending_checkpoint.message,
                "options": list(pending_checkpoint.options),
                "default": pending_checkpoint.default,
            }

        return cls(
            session_id=session_id,
            workspace=str(loop.workspace),
            conversation_history=list(loop.conversation_history),
            current_dag_path=dag_path,
            pending_checkpoint=checkpoint_dict,
            snapshot_ids=snapshot_ids,
            auto_approve_paths=auto_paths,
            metadata={
                "trust_level": loop.trust_level,
                "auto_confirm": loop.auto_confirm,
            },
        )

    def restore_to_chat_loop(self, loop: Any) -> None:
        """Restore session state to a UnifiedChatLoop instance.

        Args:
            loop: The chat loop to restore state to
        """
        # Restore conversation history
        loop.conversation_history.clear()
        loop.conversation_history.extend(self.conversation_history)

        # Restore DAG path if available
        if self.current_dag_path and hasattr(loop, "_current_dag_path"):
            from sunwell.agent.intent.dag import IntentNode
            try:
                loop._current_dag_path = tuple(
                    IntentNode(n) for n in self.current_dag_path
                )
            except ValueError:
                pass  # Invalid node values, skip

        # Restore auto-approve rules if available
        if self.auto_approve_paths and hasattr(loop, "_auto_approve_config"):
            config = loop._auto_approve_config
            for path_tuple in self.auto_approve_paths:
                from sunwell.agent.intent.dag import IntentNode
                try:
                    path = tuple(IntentNode(n) for n in path_tuple)
                    if not config.has_rule(path):
                        config.add_rule(path, 0)
                except ValueError:
                    pass  # Invalid node values, skip

        logger.info(
            "Restored portable session %s with %d messages",
            self.session_id,
            len(self.conversation_history),
        )
