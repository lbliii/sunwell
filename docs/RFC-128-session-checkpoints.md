# RFC-128: Session Checkpoints — Intent-Enriched Workspace Snapshots

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-121 (Artifact Lineage), RFC-125 (Recovery & Review), RFC-032 (Agent Checkpoints)

## Summary

Add lightweight, intent-enriched workspace checkpointing that enables agents to safely experiment with automatic rollback. Unlike git (which tracks *what* changed), session checkpoints track *why* changes were made, enabling intelligent recovery and observable agent reasoning.

**Key insight**: Don't build a VCS. Build a **save-game system** by composing existing Sunwell primitives.

## Motivation

### Problem: Agents Can't Safely Experiment

Current agent execution is **all-or-nothing**:

```
Agent starts task
    │
    ├── Makes changes to 5 files
    ├── Realizes approach is wrong
    │
    └── Options:
        ├── Manual undo (error-prone, loses intent)
        ├── git reset --hard (loses ALL changes)
        └── Hope user has backup (they don't)
```

Agents need cheap checkpoints for:
- **Before risky operations**: "Let me try this refactor..."
- **After partial success**: "Auth works, let me checkpoint before API layer..."
- **Experimentation**: "Try approach A, if fail, restore and try B"

### Problem: Git Is Wrong Abstraction

| Git Is For | Agents Need |
|------------|-------------|
| Human collaboration | Solo experimentation |
| Permanent history | Session-scoped snapshots |
| Tracking *what* changed | Tracking *why* changed |
| Branch naming ceremony | Instant checkpoint |
| Commit message afterthought | Intent as primary data |

**Git overhead**:
- Subprocess call per operation (~500ms)
- Branch name uniqueness requirements
- Staging area complexity
- Merge conflict possibility
- Pollutes user's git log

### Problem: Existing Systems Don't Compose

Sunwell has the building blocks but no composition:

| System | Has | Missing |
|--------|-----|---------|
| `RecoveryState` | File content snapshots | Restore capability, intent |
| `AgentCheckpoint` | Task progress | File content |
| `LineageStore` | Content hashing, edit history | Point-in-time snapshots |
| `WorkflowState` | Atomic persistence | Workspace snapshots |

### User Stories

**"Let me try this"**:
> Agent: "I'll checkpoint here, try the async refactor, and restore if it breaks tests."

**"What was I thinking?"**:
> User reviewing Observatory: "Why did the agent make this checkpoint?" → Sees reasoning, goal linkage, confidence score.

**"Resume where I left off"**:
> Session interrupted → Resume → Restore to last checkpoint → Continue.

**"Compare approaches"**:
> "Checkpoint A used callbacks, checkpoint B used async/await. Show me the diff with reasoning."

---

## Goals

1. **Instant checkpoints**: Sub-100ms in-memory snapshots
2. **Intent-first**: Every checkpoint has reasoning, goal linkage, confidence
3. **Safe restore**: One-call restore to any checkpoint
4. **Compose existing primitives**: Reuse `RecoveryArtifact`, `compute_content_hash`, atomic writes
5. **Session-scoped lifecycle**: Checkpoints live with session, not forever
6. **Observable**: Integrate with Observatory for timeline visualization

## Non-Goals

- **Not a VCS**: No branches, no merges, no remotes
- **Not permanent**: Checkpoints archived/deleted when session ends
- **Not replacing git**: Accept-to-git promotes changes, doesn't replace it
- **Not file-system level**: Tracks Sunwell-managed files, not entire workspace
- **Not cross-session**: Each session has isolated checkpoints

---

## Design

### Architecture: Compose Existing Primitives

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SessionCheckpointer                                │
│                                                                         │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐       │
│  │ SnapshotIntent  │   │WorkspaceSnapshot│   │  ContentStore   │       │
│  │                 │   │                 │   │                 │       │
│  │ - reasoning     │   │ - id (hash)     │   │ - deduplicated  │       │
│  │ - goal_id       │   │ - parent        │   │ - content-addr  │       │
│  │ - confidence    │   │ - intent        │   │ - lazy persist  │       │
│  │ - tool_calls    │   │ - artifacts     │   │                 │       │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘       │
│           │                    │                     │                  │
│           └────────────────────┼─────────────────────┘                  │
│                                │                                        │
│  ┌─────────────────────────────┴─────────────────────────────────────┐ │
│  │                     REUSED PRIMITIVES                              │ │
│  │                                                                    │ │
│  │  lineage.compute_content_hash()    RecoveryArtifact pattern       │ │
│  │  RecoveryManager atomic writes     SimulacrumStore session scope  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Types

```python
# sunwell/session/checkpoint_types.py

"""Type definitions for session checkpointing (RFC-128).

Immutable data structures for checkpoint state.
Reuses RecoveryArtifact for file snapshots.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sunwell.recovery.types import RecoveryArtifact


@dataclass(frozen=True, slots=True)
class SnapshotIntent:
    """Why this snapshot was created — the key differentiator from git.
    
    Every checkpoint captures the agent's reasoning, making the history
    understandable and auditable.
    
    Attributes:
        reasoning: Human-readable explanation of why checkpoint created
        goal_id: Link to goal that triggered this checkpoint
        task_id: Link to specific task being executed
        tool_calls: Sequence of tool calls that led to this state
        confidence: Agent's confidence in current state (0.0-1.0)
        checkpoint_name: Optional human-readable name for quick reference
    """
    
    reasoning: str
    goal_id: str | None = None
    task_id: str | None = None
    tool_calls: tuple[str, ...] = ()
    confidence: float = 0.8
    checkpoint_name: str | None = None
    
    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "reasoning": self.reasoning,
            "goal_id": self.goal_id,
            "task_id": self.task_id,
            "tool_calls": list(self.tool_calls),
            "confidence": self.confidence,
            "checkpoint_name": self.checkpoint_name,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SnapshotIntent":
        """Deserialize from dict."""
        return cls(
            reasoning=data["reasoning"],
            goal_id=data.get("goal_id"),
            task_id=data.get("task_id"),
            tool_calls=tuple(data.get("tool_calls", [])),
            confidence=data.get("confidence", 0.8),
            checkpoint_name=data.get("checkpoint_name"),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    """Point-in-time workspace state with intent.
    
    Captures both the file state (via RecoveryArtifact) and the reasoning
    (via SnapshotIntent). Forms a linked list via parent references.
    
    Attributes:
        id: Content-addressed hash of manifest (deterministic)
        timestamp: When snapshot was created
        parent: ID of previous snapshot (None for first)
        intent: Why this snapshot was created
        artifacts: File snapshots (reusing RecoveryArtifact)
        manifest: Quick lookup of {path: content_hash}
    """
    
    id: str
    timestamp: datetime
    parent: str | None
    intent: SnapshotIntent
    artifacts: frozenset[RecoveryArtifact]
    manifest: frozenset[tuple[str, str]]  # {(path, content_hash), ...}
    
    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "parent": self.parent,
            "intent": self.intent.to_dict(),
            "artifacts": [
                {
                    "path": str(a.path),
                    "content_hash": dict(self.manifest).get(str(a.path)),
                    "status": a.status.value,
                }
                for a in self.artifacts
            ],
            "manifest": list(self.manifest),
        }
    
    @classmethod
    def from_dict(cls, data: dict, contents: dict[str, str]) -> "WorkspaceSnapshot":
        """Deserialize from dict, looking up content from store."""
        from sunwell.recovery.types import ArtifactStatus
        
        manifest = frozenset(tuple(m) for m in data["manifest"])
        manifest_dict = dict(manifest)
        
        artifacts = frozenset(
            RecoveryArtifact(
                path=Path(a["path"]),
                content=contents.get(manifest_dict.get(a["path"], ""), ""),
                status=ArtifactStatus(a["status"]),
            )
            for a in data["artifacts"]
        )
        
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            parent=data.get("parent"),
            intent=SnapshotIntent.from_dict(data["intent"]),
            artifacts=artifacts,
            manifest=manifest,
        )


@dataclass(frozen=True, slots=True)
class CheckpointSummary:
    """Lightweight summary for listing/display."""
    
    id: str
    timestamp: datetime
    checkpoint_name: str | None
    reasoning_preview: str  # First 80 chars
    confidence: float
    file_count: int
    parent: str | None
    
    @classmethod
    def from_snapshot(cls, snapshot: WorkspaceSnapshot) -> "CheckpointSummary":
        """Create summary from full snapshot."""
        return cls(
            id=snapshot.id,
            timestamp=snapshot.timestamp,
            checkpoint_name=snapshot.intent.checkpoint_name,
            reasoning_preview=snapshot.intent.reasoning[:80],
            confidence=snapshot.intent.confidence,
            file_count=len(snapshot.artifacts),
            parent=snapshot.parent,
        )
```

### SessionCheckpointer Implementation

```python
# sunwell/session/checkpointer.py

"""Session checkpointing with intent-enriched snapshots (RFC-128).

Provides checkpoint/restore primitives for agent sessions by composing
existing Sunwell infrastructure:
- lineage.compute_content_hash() for content-addressing
- RecoveryArtifact pattern for file snapshots  
- RecoveryManager atomic write pattern for persistence
- Session-scoped storage layout

Example:
    >>> checkpointer = SessionCheckpointer(workspace, session_id)
    >>>
    >>> # Before risky operation
    >>> cp_id = checkpointer.checkpoint("Before auth refactor", confidence=0.9)
    >>>
    >>> # Operation fails
    >>> checkpointer.restore(cp_id)
    >>>
    >>> # Review history
    >>> for snap in checkpointer.history():
    ...     print(f"{snap.intent.checkpoint_name}: {snap.intent.reasoning}")
"""

import json
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Callable

from sunwell.lineage.models import compute_content_hash
from sunwell.recovery.types import RecoveryArtifact, ArtifactStatus
from sunwell.session.checkpoint_types import (
    CheckpointSummary,
    SnapshotIntent,
    WorkspaceSnapshot,
)


@dataclass
class SessionCheckpointer:
    """In-memory checkpoint manager with lazy persistence.
    
    Design principles:
    1. Fast path is in-memory (checkpoint in <100ms)
    2. Content is deduplicated via content-addressing
    3. Persistence is lazy (explicit save() or auto-save on pause)
    4. Session-scoped lifecycle (archived when session ends)
    
    Thread Safety:
        Uses threading.Lock for thread-safe access in free-threaded Python.
    
    Attributes:
        workspace: Project root directory
        session_id: Current session identifier
        file_filter: Optional filter for which files to track
    """
    
    workspace: Path
    session_id: str
    file_filter: Callable[[Path], bool] | None = None
    
    # In-memory state (fast path)
    _snapshots: dict[str, WorkspaceSnapshot] = field(default_factory=dict)
    _contents: dict[str, bytes] = field(default_factory=dict)
    _head: str | None = None
    _history: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    # Statistics
    _stats: dict[str, int] = field(default_factory=lambda: {
        "checkpoints": 0,
        "restores": 0,
        "bytes_stored": 0,
        "bytes_deduped": 0,
    })
    
    def __post_init__(self) -> None:
        """Initialize lock if not set."""
        if not hasattr(self, "_lock") or self._lock is None:
            self._lock = threading.Lock()
    
    # ═══════════════════════════════════════════════════════════════
    # Core API (4 operations)
    # ═══════════════════════════════════════════════════════════════
    
    def checkpoint(
        self,
        reasoning: str,
        *,
        goal_id: str | None = None,
        task_id: str | None = None,
        tool_calls: tuple[str, ...] = (),
        confidence: float = 0.8,
        name: str | None = None,
    ) -> str:
        """Create checkpoint with intent. Returns snapshot ID.
        
        Fast path: All in-memory, <100ms for typical projects.
        Content is deduplicated via content-addressing.
        
        Args:
            reasoning: Why creating this checkpoint (required)
            goal_id: Link to current goal
            task_id: Link to current task  
            tool_calls: Recent tool calls that led here
            confidence: Agent's confidence (0.0-1.0)
            name: Optional human-readable name
            
        Returns:
            Snapshot ID (content-addressed hash)
            
        Example:
            >>> cp_id = checkpointer.checkpoint(
            ...     "Before async refactor",
            ...     goal_id="goal-123",
            ...     confidence=0.9,
            ...     name="pre-async",
            ... )
        """
        with self._lock:
            artifacts: list[RecoveryArtifact] = []
            manifest: dict[str, str] = {}
            bytes_new = 0
            bytes_deduped = 0
            
            for path in self._tracked_files():
                try:
                    content = path.read_text()
                except (OSError, UnicodeDecodeError):
                    continue  # Skip unreadable files
                
                content_bytes = content.encode()
                content_hash = compute_content_hash(content)
                
                # Deduplicated storage
                if content_hash not in self._contents:
                    self._contents[content_hash] = content_bytes
                    bytes_new += len(content_bytes)
                else:
                    bytes_deduped += len(content_bytes)
                
                rel_path = str(path.relative_to(self.workspace))
                manifest[rel_path] = content_hash
                
                # Reuse RecoveryArtifact — it already has the right shape
                artifacts.append(RecoveryArtifact(
                    path=Path(rel_path),
                    content=content,
                    status=ArtifactStatus.PASSED,
                ))
            
            # Create intent
            intent = SnapshotIntent(
                reasoning=reasoning,
                goal_id=goal_id,
                task_id=task_id,
                tool_calls=tool_calls,
                confidence=confidence,
                checkpoint_name=name,
            )
            
            # Create snapshot
            snapshot_id = compute_content_hash(
                json.dumps(sorted(manifest.items())) + reasoning
            )[:16]
            
            snapshot = WorkspaceSnapshot(
                id=snapshot_id,
                timestamp=datetime.now(UTC),
                parent=self._head,
                intent=intent,
                artifacts=frozenset(artifacts),
                manifest=frozenset(manifest.items()),
            )
            
            self._snapshots[snapshot_id] = snapshot
            self._history.append(snapshot_id)
            self._head = snapshot_id
            
            # Update stats
            self._stats["checkpoints"] += 1
            self._stats["bytes_stored"] += bytes_new
            self._stats["bytes_deduped"] += bytes_deduped
            
            return snapshot_id
    
    def restore(self, snapshot_id: str | None = None) -> int:
        """Restore workspace to snapshot state.
        
        Args:
            snapshot_id: Target snapshot (default: previous checkpoint)
            
        Returns:
            Number of files restored
            
        Raises:
            ValueError: If snapshot not found
            
        Example:
            >>> # Restore to specific checkpoint
            >>> checkpointer.restore("abc123")
            >>>
            >>> # Restore to previous checkpoint
            >>> checkpointer.restore()  # Uses parent of HEAD
        """
        with self._lock:
            # Default to previous checkpoint
            if snapshot_id is None:
                if self._head and self._snapshots[self._head].parent:
                    snapshot_id = self._snapshots[self._head].parent
                else:
                    raise ValueError("No previous checkpoint to restore")
            
            snapshot = self._snapshots.get(snapshot_id)
            if not snapshot:
                raise ValueError(f"Unknown snapshot: {snapshot_id}")
            
            files_restored = 0
            for artifact in snapshot.artifacts:
                full_path = self.workspace / artifact.path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(artifact.content)
                files_restored += 1
            
            self._head = snapshot_id
            self._stats["restores"] += 1
            
            return files_restored
    
    def diff(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
    ) -> dict[str, str]:
        """Compare two snapshots.
        
        Args:
            from_id: Start snapshot (default: first in history)
            to_id: End snapshot (default: HEAD)
            
        Returns:
            Dict of {path: change_type} where change_type is:
            - "added": File exists in to but not from
            - "removed": File exists in from but not to
            - "modified": File exists in both but content differs
            
        Example:
            >>> diff = checkpointer.diff(from_id="abc123")
            >>> for path, change in diff.items():
            ...     print(f"{change}: {path}")
        """
        with self._lock:
            # Resolve IDs
            if from_id is None and self._history:
                from_id = self._history[0]
            if to_id is None:
                to_id = self._head
            
            from_snap = self._snapshots.get(from_id) if from_id else None
            to_snap = self._snapshots.get(to_id) if to_id else None
            
            from_files = dict(from_snap.manifest) if from_snap else {}
            to_files = dict(to_snap.manifest) if to_snap else {}
            
            changes: dict[str, str] = {}
            all_paths = set(from_files) | set(to_files)
            
            for path in all_paths:
                old_hash = from_files.get(path)
                new_hash = to_files.get(path)
                
                if old_hash is None:
                    changes[path] = "added"
                elif new_hash is None:
                    changes[path] = "removed"
                elif old_hash != new_hash:
                    changes[path] = "modified"
            
            return changes
    
    def history(self, limit: int = 20) -> list[WorkspaceSnapshot]:
        """Get recent snapshots with intent.
        
        Args:
            limit: Maximum snapshots to return
            
        Returns:
            List of snapshots, most recent first
            
        Example:
            >>> for snap in checkpointer.history(limit=5):
            ...     print(f"{snap.intent.checkpoint_name}: {snap.intent.reasoning}")
        """
        with self._lock:
            return [
                self._snapshots[sid]
                for sid in reversed(self._history[-limit:])
            ]
    
    # ═══════════════════════════════════════════════════════════════
    # Convenience Methods
    # ═══════════════════════════════════════════════════════════════
    
    @property
    def head(self) -> WorkspaceSnapshot | None:
        """Current HEAD snapshot."""
        with self._lock:
            return self._snapshots.get(self._head) if self._head else None
    
    @property
    def checkpoint_count(self) -> int:
        """Number of checkpoints in this session."""
        with self._lock:
            return len(self._history)
    
    def get(self, snapshot_id: str) -> WorkspaceSnapshot | None:
        """Get specific snapshot by ID."""
        with self._lock:
            return self._snapshots.get(snapshot_id)
    
    def get_by_name(self, name: str) -> WorkspaceSnapshot | None:
        """Find snapshot by checkpoint_name."""
        with self._lock:
            for snap in self._snapshots.values():
                if snap.intent.checkpoint_name == name:
                    return snap
            return None
    
    def summaries(self) -> list[CheckpointSummary]:
        """Get lightweight summaries for all checkpoints."""
        with self._lock:
            return [
                CheckpointSummary.from_snapshot(self._snapshots[sid])
                for sid in reversed(self._history)
            ]
    
    @property
    def stats(self) -> dict[str, int]:
        """Get checkpoint statistics."""
        with self._lock:
            return {
                **self._stats,
                "snapshots": len(self._snapshots),
                "content_blobs": len(self._contents),
            }
    
    # ═══════════════════════════════════════════════════════════════
    # Persistence (Atomic Writes)
    # ═══════════════════════════════════════════════════════════════
    
    def save(self) -> Path:
        """Persist to .sunwell/sessions/{session_id}/checkpoints/.
        
        Uses atomic write pattern (temp file + rename) for crash safety.
        Reuses RecoveryManager's proven approach.
        
        Returns:
            Path to saved checkpoint directory
        """
        checkpoint_dir = self._checkpoint_dir()
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            # Save contents (content-addressed blobs)
            contents_dir = checkpoint_dir / "contents"
            contents_dir.mkdir(exist_ok=True)
            
            for hash_key, content in self._contents.items():
                prefix_dir = contents_dir / hash_key[:2]
                prefix_dir.mkdir(exist_ok=True)
                blob_path = prefix_dir / hash_key[2:]
                if not blob_path.exists():
                    blob_path.write_bytes(content)
            
            # Save snapshots (metadata only, content by reference)
            snapshots_data = {
                sid: snap.to_dict()
                for sid, snap in self._snapshots.items()
            }
            
            state_data = {
                "version": 1,
                "session_id": self.session_id,
                "head": self._head,
                "history": self._history,
                "stats": self._stats,
                "snapshots": snapshots_data,
            }
            
            # Atomic write
            state_path = checkpoint_dir / "state.json"
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=checkpoint_dir,
                suffix=".tmp",
                delete=False,
            ) as f:
                json.dump(state_data, f, indent=2, default=str)
                temp_path = Path(f.name)
            
            temp_path.rename(state_path)
        
        return checkpoint_dir
    
    @classmethod
    def load(cls, workspace: Path, session_id: str) -> "SessionCheckpointer":
        """Load from .sunwell/sessions/{session_id}/checkpoints/.
        
        Args:
            workspace: Project root directory
            session_id: Session to load
            
        Returns:
            SessionCheckpointer with restored state
        """
        checkpointer = cls(workspace=workspace, session_id=session_id)
        checkpoint_dir = checkpointer._checkpoint_dir()
        
        if not checkpoint_dir.exists():
            return checkpointer
        
        state_path = checkpoint_dir / "state.json"
        if not state_path.exists():
            return checkpointer
        
        # Load state
        with open(state_path) as f:
            state_data = json.load(f)
        
        # Load contents
        contents_dir = checkpoint_dir / "contents"
        contents: dict[str, bytes] = {}
        if contents_dir.exists():
            for prefix_dir in contents_dir.iterdir():
                if prefix_dir.is_dir():
                    for blob_file in prefix_dir.iterdir():
                        hash_key = prefix_dir.name + blob_file.name
                        contents[hash_key] = blob_file.read_bytes()
        
        checkpointer._contents = contents
        
        # Convert content bytes to strings for snapshot reconstruction
        content_strings = {k: v.decode() for k, v in contents.items()}
        
        # Load snapshots
        for sid, snap_data in state_data.get("snapshots", {}).items():
            checkpointer._snapshots[sid] = WorkspaceSnapshot.from_dict(
                snap_data, content_strings
            )
        
        checkpointer._head = state_data.get("head")
        checkpointer._history = state_data.get("history", [])
        checkpointer._stats = state_data.get("stats", checkpointer._stats)
        
        return checkpointer
    
    def archive(self) -> Path | None:
        """Archive checkpoints when session ends.
        
        Moves checkpoint data to archive, clears in-memory state.
        
        Returns:
            Archive path if archived, None if nothing to archive
        """
        if not self._history:
            return None
        
        # Save first
        self.save()
        
        # Move to archive
        checkpoint_dir = self._checkpoint_dir()
        archive_dir = (
            self.workspace / ".sunwell" / "sessions" / "archive" / self.session_id
        )
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        
        if checkpoint_dir.exists():
            checkpoint_dir.rename(archive_dir)
        
        # Clear in-memory
        with self._lock:
            self._snapshots.clear()
            self._contents.clear()
            self._head = None
            self._history.clear()
        
        return archive_dir
    
    # ═══════════════════════════════════════════════════════════════
    # Internal Helpers
    # ═══════════════════════════════════════════════════════════════
    
    def _checkpoint_dir(self) -> Path:
        """Get checkpoint storage directory."""
        return self.workspace / ".sunwell" / "sessions" / self.session_id / "checkpoints"
    
    def _tracked_files(self) -> list[Path]:
        """Get files to track.
        
        Default: All Python files in src/ (or workspace root).
        Override with file_filter for custom behavior.
        """
        if self.file_filter:
            return [
                p for p in self.workspace.rglob("*")
                if p.is_file() and self.file_filter(p)
            ]
        
        # Default: Python files in src/
        src_dir = self.workspace / "src"
        if src_dir.exists():
            base = src_dir
        else:
            base = self.workspace
        
        return [
            p for p in base.rglob("*.py")
            if "__pycache__" not in str(p)
            and ".sunwell" not in str(p)
        ]
```

### Agent Tools Integration

```python
# sunwell/tools/checkpoint_tools.py

"""Checkpoint tools for agent self-access (RFC-128).

Exposes session checkpointing as agent tools, enabling autonomous
experimentation with safe rollback.
"""

from sunwell.models.protocol import Tool

CHECKPOINT_TOOLS: dict[str, Tool] = {
    "sunwell_checkpoint": Tool(
        name="sunwell_checkpoint",
        description=(
            "Create a checkpoint of current workspace state with your reasoning. "
            "Use BEFORE risky operations to enable rollback if things go wrong. "
            "Checkpoints are instant (<100ms) and don't affect git. "
            "Include confidence (0.0-1.0) to indicate how stable this state is."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Why you're creating this checkpoint (required)",
                },
                "name": {
                    "type": "string",
                    "description": "Optional short name for quick reference (e.g., 'pre-auth')",
                },
                "confidence": {
                    "type": "number",
                    "description": "Your confidence in current state (0.0-1.0, default: 0.8)",
                    "default": 0.8,
                },
            },
            "required": ["reasoning"],
        },
    ),
    
    "sunwell_restore": Tool(
        name="sunwell_restore",
        description=(
            "Restore workspace to a previous checkpoint. "
            "Use when current approach failed and you want to try something else. "
            "Specify checkpoint ID or name, or omit to restore to previous."
        ),
        parameters={
            "type": "object",
            "properties": {
                "checkpoint": {
                    "type": "string",
                    "description": "Checkpoint ID or name (default: previous checkpoint)",
                },
            },
        },
    ),
    
    "sunwell_checkpoint_diff": Tool(
        name="sunwell_checkpoint_diff",
        description=(
            "See what changed between checkpoints. "
            "Use to review changes before committing or to understand what you've done."
        ),
        parameters={
            "type": "object",
            "properties": {
                "from_checkpoint": {
                    "type": "string",
                    "description": "Start checkpoint ID or name (default: first checkpoint)",
                },
                "to_checkpoint": {
                    "type": "string",
                    "description": "End checkpoint ID or name (default: current)",
                },
            },
        },
    ),
    
    "sunwell_checkpoint_history": Tool(
        name="sunwell_checkpoint_history",
        description=(
            "List checkpoint history with reasoning and confidence. "
            "Shows timeline of your session's progression."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max checkpoints to show (default: 10)",
                    "default": 10,
                },
            },
        },
    ),
}
```

### Tool Handlers

```python
# sunwell/tools/checkpoint_handlers.py

"""Handlers for checkpoint tools (RFC-128)."""

from pathlib import Path
from uuid import uuid4

from sunwell.session.checkpointer import SessionCheckpointer
from sunwell.tools.types import ToolResult


def _result(success: bool, output: str) -> ToolResult:
    """Factory for ToolResult with auto-generated ID."""
    return ToolResult(tool_call_id=str(uuid4()), success=success, output=output)


class CheckpointToolHandlers:
    """Handlers for checkpoint tools."""
    
    def __init__(self, workspace: Path, session_id: str):
        self.checkpointer = SessionCheckpointer(workspace, session_id)
    
    async def handle_checkpoint(
        self,
        reasoning: str,
        name: str | None = None,
        confidence: float = 0.8,
        goal_id: str | None = None,
        task_id: str | None = None,
    ) -> ToolResult:
        """Create checkpoint."""
        try:
            cp_id = self.checkpointer.checkpoint(
                reasoning=reasoning,
                name=name,
                confidence=confidence,
                goal_id=goal_id,
                task_id=task_id,
            )
            
            output = f"✓ Checkpoint created: {cp_id[:8]}"
            if name:
                output += f" ({name})"
            output += f"\nFiles: {len(self.checkpointer.head.artifacts) if self.checkpointer.head else 0}"
            output += f"\nConfidence: {confidence:.0%}"
            
            return _result(True, output)
        
        except Exception as e:
            return _result(False, f"Checkpoint failed: {e}")
    
    async def handle_restore(
        self,
        checkpoint: str | None = None,
    ) -> ToolResult:
        """Restore to checkpoint."""
        try:
            # Try by name first
            if checkpoint:
                snap = self.checkpointer.get_by_name(checkpoint)
                if snap:
                    checkpoint = snap.id
            
            files_restored = self.checkpointer.restore(checkpoint)
            
            head = self.checkpointer.head
            output = f"✓ Restored to checkpoint: {head.id[:8] if head else 'unknown'}"
            if head and head.intent.checkpoint_name:
                output += f" ({head.intent.checkpoint_name})"
            output += f"\nFiles restored: {files_restored}"
            
            return _result(True, output)
        
        except ValueError as e:
            return _result(False, str(e))
        except Exception as e:
            return _result(False, f"Restore failed: {e}")
    
    async def handle_diff(
        self,
        from_checkpoint: str | None = None,
        to_checkpoint: str | None = None,
    ) -> ToolResult:
        """Show diff between checkpoints."""
        try:
            # Resolve names to IDs
            if from_checkpoint:
                snap = self.checkpointer.get_by_name(from_checkpoint)
                if snap:
                    from_checkpoint = snap.id
            
            if to_checkpoint:
                snap = self.checkpointer.get_by_name(to_checkpoint)
                if snap:
                    to_checkpoint = snap.id
            
            diff = self.checkpointer.diff(from_checkpoint, to_checkpoint)
            
            if not diff:
                return _result(True, "No changes between checkpoints.")
            
            output = f"Changes ({len(diff)} files):\n\n"
            for path, change in sorted(diff.items()):
                icon = {"added": "➕", "removed": "➖", "modified": "📝"}.get(change, "?")
                output += f"{icon} {change}: {path}\n"
            
            return _result(True, output)
        
        except Exception as e:
            return _result(False, f"Diff failed: {e}")
    
    async def handle_history(
        self,
        limit: int = 10,
    ) -> ToolResult:
        """Show checkpoint history."""
        try:
            snapshots = self.checkpointer.history(limit)
            
            if not snapshots:
                return _result(True, "No checkpoints yet.")
            
            output = f"Checkpoint History ({len(snapshots)} shown):\n\n"
            
            for snap in snapshots:
                icon = "●" if snap.id == self.checkpointer.head.id else "○"
                name = snap.intent.checkpoint_name or snap.id[:8]
                conf = f"{snap.intent.confidence:.0%}"
                
                # Confidence color indicator
                if snap.intent.confidence >= 0.9:
                    conf_icon = "🟢"
                elif snap.intent.confidence >= 0.7:
                    conf_icon = "🟡"
                else:
                    conf_icon = "🟠"
                
                output += f"{icon} {name} — {conf_icon} {conf}\n"
                output += f"  {snap.intent.reasoning[:60]}...\n"
                output += f"  {snap.timestamp.strftime('%H:%M:%S')} • {len(snap.artifacts)} files\n\n"
            
            return _result(True, output)
        
        except Exception as e:
            return _result(False, f"History failed: {e}")
```

---

## Storage Layout

```
.sunwell/
├── sessions/
│   ├── {session_id}/
│   │   ├── checkpoints/
│   │   │   ├── state.json          # Snapshot metadata + history
│   │   │   └── contents/           # Deduplicated content blobs
│   │   │       ├── ab/cd1234...
│   │   │       └── ef/gh5678...
│   │   └── state.json              # Existing session state
│   └── archive/                    # Archived sessions
│       └── {old_session_id}/
│           └── checkpoints/
├── lineage/                        # Existing artifact lineage
├── recovery/                       # Existing recovery states
└── checkpoints/                    # Existing AgentCheckpoint (tasks)
```

### state.json Schema

```json
{
  "version": 1,
  "session_id": "session-2026-01-24-abc123",
  "head": "def456",
  "history": ["abc123", "def456"],
  "stats": {
    "checkpoints": 2,
    "restores": 0,
    "bytes_stored": 12345,
    "bytes_deduped": 5000
  },
  "snapshots": {
    "abc123": {
      "id": "abc123",
      "timestamp": "2026-01-24T10:30:00Z",
      "parent": null,
      "intent": {
        "reasoning": "Initial checkpoint before auth refactor",
        "goal_id": "goal-789",
        "confidence": 0.9,
        "checkpoint_name": "pre-auth"
      },
      "manifest": [["src/auth.py", "hash1"], ["src/api.py", "hash2"]]
    }
  }
}
```

---

## Observatory Integration

### Timeline Visualization

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Session Timeline: session-2026-01-24-abc123                            │
│                                                                         │
│  ○───●───○───○───●───○───●                                             │
│  │   │   │   │   │   │   │                                             │
│  │   │   │   │   │   │   └─ current (HEAD)                             │
│  │   │   │   │   │   │      "API tests passing" 92% 🟢                 │
│  │   │   │   │   │   │                                                 │
│  │   │   │   │   │   └─ "Add error handling" 78% 🟡                    │
│  │   │   │   │   │                                                     │
│  │   │   │   │   └─ "Auth flow working" 95% 🟢 ← named: "auth-done"   │
│  │   │   │   │                                                         │
│  │   │   │   └─ [restore point — tried async, failed]                  │
│  │   │   │                                                             │
│  │   │   └─ "Before async experiment" 85% 🟡                           │
│  │   │                                                                 │
│  │   └─ "Initial structure" 70% 🟡 ← named: "initial"                 │
│  │                                                                     │
│  └─ session start                                                      │
│                                                                         │
│  [Restore to "auth-done"]  [Show diff from initial]  [Accept to git]   │
└─────────────────────────────────────────────────────────────────────────┘
```

### REST API Endpoints

```python
# sunwell/server/routes/checkpoints.py

@router.get("/sessions/{session_id}/checkpoints")
async def list_checkpoints(session_id: str) -> list[CheckpointSummary]:
    """List all checkpoints for a session."""
    ...

@router.get("/sessions/{session_id}/checkpoints/{checkpoint_id}")
async def get_checkpoint(session_id: str, checkpoint_id: str) -> WorkspaceSnapshot:
    """Get full checkpoint details."""
    ...

@router.get("/sessions/{session_id}/checkpoints/diff")
async def get_diff(
    session_id: str,
    from_id: str | None = None,
    to_id: str | None = None,
) -> dict[str, str]:
    """Get diff between checkpoints."""
    ...

@router.get("/sessions/{session_id}/checkpoints/timeline")
async def get_timeline(session_id: str) -> dict:
    """Get timeline data for Observatory visualization."""
    ...
```

---

## Security Considerations

### Content Isolation

Checkpoints are session-scoped and project-scoped:

```python
# Storage path includes both session and project
.sunwell/sessions/{session_id}/checkpoints/

# Session IDs are UUIDs, not user-controllable
session_id = str(uuid4())
```

### No Cross-Session Access

Sessions cannot access other sessions' checkpoints:

```python
# Checkpointer is scoped to single session
checkpointer = SessionCheckpointer(workspace, session_id)
# Cannot access other_session_id's checkpoints
```

### Atomic Writes

Persistence uses temp file + rename for crash safety:

```python
with tempfile.NamedTemporaryFile(..., delete=False) as f:
    json.dump(data, f)
    temp_path = Path(f.name)
temp_path.rename(target_path)  # Atomic on POSIX
```

### Content Deduplication Safety

Content-addressed storage prevents tampering:

```python
content_hash = compute_content_hash(content)  # SHA256
# If content changes, hash changes, new blob created
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large file memory pressure | Medium | Medium | Lazy loading, streaming for large files |
| Concurrent access corruption | Low | High | Thread locks, atomic writes |
| Disk full during save | Low | Medium | Check space before save, clean old sessions |
| Restore loses recent changes | Medium | High | Confirm before restore, show diff first |
| Session orphaned checkpoints | Medium | Low | Cleanup on session archive/delete |
| User confusion with git | Medium | Low | Clear naming (checkpoints vs commits) |

---

## Implementation Plan

### Phase 1: Core Types & Checkpointer (1 day)

| Task | File | Status |
|------|------|--------|
| Define `SnapshotIntent`, `WorkspaceSnapshot` | `session/checkpoint_types.py` | ⬜ |
| Implement `SessionCheckpointer` | `session/checkpointer.py` | ⬜ |
| Unit tests for checkpoint/restore | `tests/test_checkpointer.py` | ⬜ |

### Phase 2: Tool Integration (0.5 day)

| Task | File | Status |
|------|------|--------|
| Define checkpoint tools | `tools/checkpoint_tools.py` | ⬜ |
| Implement handlers | `tools/checkpoint_handlers.py` | ⬜ |
| Wire into `ToolExecutor` | `tools/executor.py` | ⬜ |
| Tool tests | `tests/test_checkpoint_tools.py` | ⬜ |

### Phase 3: Agent Integration (0.5 day)

| Task | File | Status |
|------|------|--------|
| Auto-checkpoint before risky ops | `naaru/executor.py` | ⬜ |
| Auto-restore on failure | `recovery/handler.py` | ⬜ |
| Integration tests | `tests/integration/test_checkpoint_flow.py` | ⬜ |

### Phase 4: Observatory & API (1 day)

| Task | File | Status |
|------|------|--------|
| REST endpoints | `server/routes/checkpoints.py` | ⬜ |
| Timeline component | `studio/src/lib/components/Timeline.svelte` | ⬜ |
| E2E tests | `tests/e2e/test_checkpoint_ui.py` | ⬜ |

**Total estimated time**: 3 days

---

## Testing

```python
# tests/test_checkpointer.py

import pytest
from pathlib import Path
from sunwell.session.checkpointer import SessionCheckpointer


class TestCheckpointRestore:
    """Core checkpoint/restore functionality."""
    
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create minimal workspace."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('hello')")
        (src / "utils.py").write_text("def add(a, b): return a + b")
        return tmp_path
    
    @pytest.fixture
    def checkpointer(self, workspace: Path) -> SessionCheckpointer:
        return SessionCheckpointer(workspace, "test-session")
    
    def test_checkpoint_creates_snapshot(self, checkpointer):
        """Checkpoint should create snapshot with intent."""
        cp_id = checkpointer.checkpoint("Initial state", confidence=0.9)
        
        assert cp_id is not None
        assert checkpointer.head is not None
        assert checkpointer.head.intent.reasoning == "Initial state"
        assert checkpointer.head.intent.confidence == 0.9
    
    def test_restore_reverts_changes(self, checkpointer, workspace):
        """Restore should revert workspace to checkpoint state."""
        # Checkpoint initial state
        cp_id = checkpointer.checkpoint("Before changes")
        
        # Make changes
        (workspace / "src" / "main.py").write_text("print('modified')")
        
        # Restore
        checkpointer.restore(cp_id)
        
        # Verify reverted
        content = (workspace / "src" / "main.py").read_text()
        assert content == "print('hello')"
    
    def test_diff_shows_changes(self, checkpointer, workspace):
        """Diff should show what changed between checkpoints."""
        cp1 = checkpointer.checkpoint("Initial")
        
        # Modify file
        (workspace / "src" / "main.py").write_text("print('modified')")
        
        cp2 = checkpointer.checkpoint("After modification")
        
        diff = checkpointer.diff(cp1, cp2)
        
        assert "src/main.py" in diff
        assert diff["src/main.py"] == "modified"
    
    def test_history_returns_snapshots(self, checkpointer):
        """History should return snapshots in reverse order."""
        checkpointer.checkpoint("First", name="first")
        checkpointer.checkpoint("Second", name="second")
        checkpointer.checkpoint("Third", name="third")
        
        history = checkpointer.history()
        
        assert len(history) == 3
        assert history[0].intent.checkpoint_name == "third"
        assert history[2].intent.checkpoint_name == "first"


class TestPersistence:
    """Save/load functionality."""
    
    def test_save_and_load_preserves_state(self, workspace, checkpointer):
        """Save and load should preserve all state."""
        checkpointer.checkpoint("Test checkpoint", name="test", confidence=0.85)
        
        # Save
        checkpointer.save()
        
        # Load fresh instance
        loaded = SessionCheckpointer.load(workspace, "test-session")
        
        assert loaded.checkpoint_count == 1
        assert loaded.head.intent.checkpoint_name == "test"
        assert loaded.head.intent.confidence == 0.85


class TestDeduplication:
    """Content deduplication."""
    
    def test_identical_content_deduplicated(self, checkpointer, workspace):
        """Identical content should be stored once."""
        # Create checkpoint
        checkpointer.checkpoint("First")
        
        # Create another with no changes
        checkpointer.checkpoint("Second")
        
        # Content should be deduplicated
        stats = checkpointer.stats
        assert stats["bytes_deduped"] > 0
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Checkpoint latency | <100ms | p95 timing in tests |
| Restore latency | <500ms | p95 timing for 100-file project |
| Memory overhead | <50MB | Peak memory for 1000-file project |
| Deduplication ratio | >50% | bytes_deduped / (bytes_stored + bytes_deduped) |
| Agent rollback success | >95% | Successful restores / total restores |
| User comprehension | >80% | Survey: "I understood checkpoint timeline" |

---

## Future Extensions

- **Named branches**: Optional branching for parallel experimentation
- **Diff visualization**: Rich diff UI in Observatory
- **Accept-to-git**: Squash checkpoints into git commit
- **Cross-session comparison**: Compare approaches across sessions
- **Checkpoint annotations**: User can add notes to checkpoints
- **Auto-checkpoint triggers**: Configurable triggers (time, task completion)
- **Checkpoint sharing**: Export/import checkpoint bundles

---

## References

- RFC-032: Agent Checkpoints (task progress)
- RFC-121: Artifact Lineage (content hashing, edit tracking)
- RFC-125: Recovery & Review (RecoveryArtifact, atomic writes)
- RFC-086: Workflow State (persistence patterns)
- `sunwell/lineage/models.py`: `compute_content_hash()`
- `sunwell/recovery/types.py`: `RecoveryArtifact`
- `sunwell/recovery/manager.py`: Atomic write pattern
