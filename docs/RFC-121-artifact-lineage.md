# RFC-121: Artifact Lineage & Provenance

**Status**: Evaluated (87% confidence)  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Revised**: 2026-01-24  
**Depends on**: RFC-119 (Unified Event Bus) ✅ Implemented, RFC-120 (Session Tracking)

## Summary

Track the complete lineage of every artifact Sunwell creates: which goal spawned it, which model wrote it, what edits were made, and how it relates to other artifacts. Enable "why does this file exist?" queries.

## Motivation

### Problem

After working with Sunwell for a while, users lose track of:

1. **Why does this file exist?** → Which goal created it?
2. **What changed this file?** → Which edits came from which goals?
3. **What depends on this?** → If I delete this, what breaks?
4. **Who wrote this?** → Which model/human contributed?

### Inspiration: Pachyderm

Pachyderm tracks data provenance automatically:
- Every output file knows which input files produced it
- Every pipeline version is recorded
- `pachctl inspect file` shows complete history

We want similar capabilities for code artifacts.

### User Stories

**"Why does this exist?":**
> "I have `utils/helpers.py` in my project. I don't remember creating it. Show me which goal created it and why."

**"What changed this?":**
> "My `api/routes.py` has some code I don't recognize. Show me all the changes Sunwell made."

**"What depends on this?":**
> "I want to delete `models/legacy.py`. What else uses it? What goals referenced it?"

---

## Goals

1. **Artifact birth tracking**: Record which goal/task creates each artifact
2. **Edit history**: Track all changes with goal attribution
3. **Dependency graph**: Know what imports/uses what
4. **Query interface**: CLI and API to explore lineage

## Non-Goals

- Full git replacement (we augment git, not replace it)
- Language-specific AST analysis (simple import detection only)
- Cross-project lineage
- Real-time file watching (we only track Sunwell-triggered events)

---

## Design Alternatives

### Option A: JSON File Store (Recommended)

Store lineage as JSON files in `.sunwell/lineage/`.

**Pros**:
- Simple implementation, human-readable
- Git-friendly (can be version controlled)
- No external dependencies
- Easy debugging and inspection

**Cons**:
- O(n) goal lookup requires scanning
- Index can drift from artifacts
- Concurrent writes need file locking

**Performance**: ~5-20ms for single file lookup (index-based), ~100-500ms for goal-based queries.

### Option B: SQLite Database

Store lineage in `.sunwell/lineage.db` using SQLite.

**Pros**:
- Fast queries with proper indexes
- ACID transactions, no corruption risk
- Complex queries (joins) for dependency analysis
- Built-in concurrent write handling

**Cons**:
- Binary file, not git-friendly
- Harder to debug/inspect
- Migration complexity for schema changes

**Performance**: ~1-5ms for all query types.

### Option C: Git Notes Integration

Store lineage as git notes attached to commits.

**Pros**:
- Native git integration
- Automatic commit correlation
- Distributed with repo

**Cons**:
- Complex implementation
- Requires git repository
- Notes not pushed by default
- Limited query capabilities

**Recommendation**: **Option A (JSON)** for v1. Simple, debuggable, and sufficient for typical project sizes (<10K files). Can migrate to SQLite later if performance becomes an issue (see Future Extensions).

---

## Design

### Part 1: Data Model

```python
# sunwell/lineage/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4
import hashlib

@dataclass(frozen=True, slots=True)
class ArtifactLineage:
    """Lineage record for a single artifact."""
    
    # Identity
    artifact_id: str              # Stable ID (UUID + content hash)
    path: str                     # Current path
    content_hash: str             # SHA256 of content at creation (for rename detection)
    
    # Birth
    created_by_goal: str | None   # Goal ID that created it
    created_by_task: str | None   # Task ID that created it
    created_at: datetime
    created_reason: str           # Why this artifact exists
    
    # Attribution
    model: str | None             # Which model wrote it
    human_edited: bool            # Has human modified it?
    
    # History (mutable via _replace or new instance)
    edits: tuple[ArtifactEdit, ...]
    
    # Dependencies
    imports: tuple[str, ...]            # What this file imports
    imported_by: tuple[str, ...]        # What imports this file


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
    edit_type: str               # "create" | "modify" | "rename" | "delete"
    
    # Attribution
    source: str                  # "sunwell" | "human" | "external"
    model: str | None            # If sunwell, which model
    
    # Timing
    timestamp: datetime
    session_id: str | None       # Links to RFC-120 SessionTracker
    
    # Git correlation
    commit_hash: str | None
    
    # Content snapshot for rename detection
    content_hash: str | None


def generate_artifact_id(path: str, content: str) -> str:
    """Generate stable artifact ID.
    
    Algorithm:
    1. Generate UUID for uniqueness
    2. Include content hash prefix for rename detection
    
    Format: {uuid}:{content_hash_prefix}
    Example: "a1b2c3d4-e5f6-7890-abcd-ef1234567890:abc123"
    """
    uuid_part = str(uuid4())
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"{uuid_part}:{content_hash}"


def compute_content_hash(content: str) -> str:
    """Compute content hash for similarity detection."""
    return hashlib.sha256(content.encode()).hexdigest()
```

### Part 2: Artifact ID Stability & Rename Detection

```python
# sunwell/lineage/identity.py

class ArtifactIdentityResolver:
    """Resolves artifact identity across renames and moves.
    
    Uses content hashing to detect when a file is moved/renamed
    rather than deleted and recreated.
    
    Algorithm:
    1. On file creation: Generate new artifact_id, store content_hash
    2. On file deletion: Mark as deleted, keep record for 24h
    3. On file creation with similar content_hash: Link to deleted artifact
    """
    
    SIMILARITY_THRESHOLD = 0.8  # 80% content similarity = same artifact
    DELETED_RETENTION_HOURS = 24
    
    def __init__(self, store: LineageStore):
        self.store = store
    
    def resolve_create(self, path: str, content: str) -> str:
        """Resolve artifact ID for a new file.
        
        Returns existing artifact_id if this looks like a rename,
        otherwise generates new ID.
        """
        content_hash = compute_content_hash(content)
        
        # Check recently deleted artifacts for content match
        deleted = self.store.get_recently_deleted(hours=self.DELETED_RETENTION_HOURS)
        for artifact in deleted:
            if self._content_similar(artifact.content_hash, content_hash):
                # This is a rename/move, reuse artifact_id
                return artifact.artifact_id
        
        # New artifact
        return generate_artifact_id(path, content)
    
    def _content_similar(self, hash_a: str, hash_b: str) -> bool:
        """Check if two content hashes indicate similar content.
        
        For exact match, compare hashes directly.
        For fuzzy match, would need to store more than hash (future).
        """
        return hash_a == hash_b
```

### Part 3: Lineage Store

```python
# sunwell/lineage/store.py

import json
import threading
from pathlib import Path
from datetime import datetime, UTC

class LineageStore:
    """Persistent storage for artifact lineage.
    
    Thread-safe with file locking for concurrent access.
    """
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'lineage'
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._index = self._load_index()
        self._identity_resolver = ArtifactIdentityResolver(self)
    
    # ── Recording ───────────────────────────────────────────
    
    def record_create(
        self,
        path: str,
        content: str,
        goal_id: str | None,
        task_id: str | None,
        reason: str,
        model: str | None,
        session_id: str | None = None,
    ) -> ArtifactLineage:
        """Record artifact creation."""
        with self._lock:
            # Resolve identity (handles rename detection)
            artifact_id = self._identity_resolver.resolve_create(path, content)
            content_hash = compute_content_hash(content)
            
            lineage = ArtifactLineage(
                artifact_id=artifact_id,
                path=path,
                content_hash=content_hash,
                created_by_goal=goal_id,
                created_by_task=task_id,
                created_at=datetime.now(UTC),
                created_reason=reason,
                model=model,
                human_edited=False,
                edits=(),
                imports=(),
                imported_by=(),
            )
            self._save(lineage)
            self._update_index(path, artifact_id)
            return lineage
    
    def record_edit(
        self,
        path: str,
        goal_id: str | None,
        task_id: str | None,
        lines_added: int,
        lines_removed: int,
        source: str,
        model: str | None = None,
        session_id: str | None = None,
        content: str | None = None,
    ) -> ArtifactEdit:
        """Record an edit to an artifact."""
        with self._lock:
            lineage = self.get_by_path(path)
            if not lineage:
                # File exists but wasn't created by Sunwell
                lineage = self._create_external(path, content or "")
            
            edit = ArtifactEdit(
                edit_id=str(uuid4()),
                artifact_id=lineage.artifact_id,
                goal_id=goal_id,
                task_id=task_id,
                lines_added=lines_added,
                lines_removed=lines_removed,
                edit_type="modify",
                source=source,
                model=model,
                timestamp=datetime.now(UTC),
                session_id=session_id,
                commit_hash=None,
                content_hash=compute_content_hash(content) if content else None,
            )
            
            self._append_edit(lineage.artifact_id, edit)
            
            if source == "human":
                self._mark_human_edited(lineage.artifact_id)
            
            return edit
    
    def record_rename(
        self,
        old_path: str,
        new_path: str,
        goal_id: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record artifact rename, preserving lineage."""
        with self._lock:
            lineage = self.get_by_path(old_path)
            if lineage:
                # Create rename edit
                edit = ArtifactEdit(
                    edit_id=str(uuid4()),
                    artifact_id=lineage.artifact_id,
                    goal_id=goal_id,
                    task_id=None,
                    lines_added=0,
                    lines_removed=0,
                    edit_type="rename",
                    source="sunwell",
                    model=None,
                    timestamp=datetime.now(UTC),
                    session_id=session_id,
                    commit_hash=None,
                    content_hash=lineage.content_hash,
                )
                self._append_edit(lineage.artifact_id, edit)
                
                # Update path
                self._update_path(lineage.artifact_id, new_path)
                self._update_index(old_path, None)  # Remove old
                self._update_index(new_path, lineage.artifact_id)  # Add new
    
    def record_delete(
        self,
        path: str,
        goal_id: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record artifact deletion (soft delete, keeps history)."""
        with self._lock:
            lineage = self.get_by_path(path)
            if lineage:
                edit = ArtifactEdit(
                    edit_id=str(uuid4()),
                    artifact_id=lineage.artifact_id,
                    goal_id=goal_id,
                    task_id=None,
                    lines_added=0,
                    lines_removed=0,
                    edit_type="delete",
                    source="sunwell",
                    model=None,
                    timestamp=datetime.now(UTC),
                    session_id=session_id,
                    commit_hash=None,
                    content_hash=lineage.content_hash,
                )
                self._append_edit(lineage.artifact_id, edit)
                self._mark_deleted(lineage.artifact_id)
                self._update_index(path, None)
    
    # ── Queries ─────────────────────────────────────────────
    
    def get_by_path(self, path: str) -> ArtifactLineage | None:
        """Get lineage for a file path. O(1) via index."""
        artifact_id = self._index.get(path)
        return self._load(artifact_id) if artifact_id else None
    
    def get_by_goal(self, goal_id: str) -> list[ArtifactLineage]:
        """Get all artifacts created/modified by a goal.
        
        Note: O(n) scan - consider caching for large projects.
        """
        results = []
        for artifact_id in self._list_artifact_ids():
            lineage = self._load(artifact_id)
            if lineage and (
                lineage.created_by_goal == goal_id or
                any(e.goal_id == goal_id for e in lineage.edits)
            ):
                results.append(lineage)
        return results
    
    def get_recently_deleted(self, hours: int = 24) -> list[ArtifactLineage]:
        """Get artifacts deleted within the last N hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        results = []
        for artifact_id in self._list_deleted_ids():
            lineage = self._load(artifact_id)
            if lineage:
                delete_edit = next(
                    (e for e in reversed(lineage.edits) if e.edit_type == "delete"),
                    None
                )
                if delete_edit and delete_edit.timestamp > cutoff:
                    results.append(lineage)
        return results
    
    def get_dependents(self, path: str) -> list[str]:
        """Get all files that import this file."""
        lineage = self.get_by_path(path)
        return list(lineage.imported_by) if lineage else []
    
    def get_dependencies(self, path: str) -> list[str]:
        """Get all files this file imports."""
        lineage = self.get_by_path(path)
        return list(lineage.imports) if lineage else []
    
    # ── External file handling ──────────────────────────────
    
    def _create_external(self, path: str, content: str) -> ArtifactLineage:
        """Create lineage record for file not created by Sunwell."""
        artifact_id = generate_artifact_id(path, content)
        lineage = ArtifactLineage(
            artifact_id=artifact_id,
            path=path,
            content_hash=compute_content_hash(content),
            created_by_goal=None,
            created_by_task=None,
            created_at=datetime.now(UTC),
            created_reason="Pre-existing file (not created by Sunwell)",
            model=None,
            human_edited=True,
            edits=(),
            imports=(),
            imported_by=(),
        )
        self._save(lineage)
        self._update_index(path, artifact_id)
        return lineage
```

### Part 4: Human Edit Detection

```python
# sunwell/lineage/human_detection.py

from datetime import datetime, UTC
from pathlib import Path


class HumanEditDetector:
    """Detects edits made by humans (not Sunwell).
    
    Detection strategies:
    1. Session-based: Edits outside active Sunwell session
    2. Diff-based: Changes not matching expected tool output
    3. Git-based: Commits not attributed to Sunwell
    """
    
    def __init__(self, store: LineageStore, session_tracker: SessionTracker):
        self.store = store
        self.session_tracker = session_tracker
        self._active_session_id: str | None = None
    
    def start_session(self, session_id: str) -> None:
        """Mark start of Sunwell session."""
        self._active_session_id = session_id
    
    def end_session(self) -> None:
        """Mark end of Sunwell session."""
        self._active_session_id = None
    
    def classify_edit(
        self,
        path: str,
        goal_id: str | None,
        model: str | None,
    ) -> str:
        """Classify edit source.
        
        Returns:
            "sunwell": Edit from active Sunwell session
            "human": Edit from user (no active session or no goal)
            "external": Edit from unknown source (e.g., other tools)
        """
        if self._active_session_id and goal_id and model:
            return "sunwell"
        elif self._active_session_id is None:
            return "human"
        else:
            return "external"
    
    def detect_untracked_changes(self, project_root: Path) -> list[dict]:
        """Detect files modified outside Sunwell.
        
        Compares stored content_hash with current file content.
        Returns list of files with untracked changes.
        """
        untracked = []
        for path, artifact_id in self.store._index.items():
            full_path = project_root / path
            if not full_path.exists():
                continue
            
            lineage = self.store.get_by_path(path)
            if not lineage:
                continue
            
            current_hash = compute_content_hash(full_path.read_text())
            last_known_hash = lineage.content_hash
            
            # Check if last edit's hash matches current
            if lineage.edits:
                last_edit_hash = lineage.edits[-1].content_hash
                if last_edit_hash:
                    last_known_hash = last_edit_hash
            
            if current_hash != last_known_hash:
                untracked.append({
                    "path": path,
                    "artifact_id": artifact_id,
                    "last_known_hash": last_known_hash,
                    "current_hash": current_hash,
                })
        
        return untracked
```

### Part 5: Dependency Detection

```python
# sunwell/lineage/dependencies.py

import re
from pathlib import Path

IMPORT_PATTERNS = {
    'python': [
        r'^import\s+([\w.]+)',
        r'^from\s+([\w.]+)\s+import',
    ],
    'typescript': [
        r"import\s+.*from\s+['\"]([^'\"]+)['\"]",
        r"import\s+['\"]([^'\"]+)['\"]",
        r"require\(['\"]([^'\"]+)['\"]\)",
        r"export\s+.*from\s+['\"]([^'\"]+)['\"]",
    ],
    'javascript': [
        r"import\s+.*from\s+['\"]([^'\"]+)['\"]",
        r"require\(['\"]([^'\"]+)['\"]\)",
    ],
    'go': [
        r'^\s*"([^"]+)"',  # Within import block
    ],
}

EXTENSION_TO_LANG = {
    '.py': 'python',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.mjs': 'javascript',
    '.go': 'go',
}


def detect_imports(path: Path, content: str) -> list[str]:
    """Detect imports in a file.
    
    Returns list of resolved import paths (relative to project root).
    Only resolves local/relative imports; skips stdlib and third-party.
    """
    lang = EXTENSION_TO_LANG.get(path.suffix)
    if not lang:
        return []
    
    patterns = IMPORT_PATTERNS.get(lang, [])
    
    raw_imports = []
    for pattern in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            raw_imports.append(match.group(1))
    
    return _resolve_imports(path, raw_imports, lang)


def _resolve_imports(
    file_path: Path,
    imports: list[str],
    lang: str,
) -> list[str]:
    """Resolve imports to project-relative paths."""
    resolved = []
    base_dir = file_path.parent
    
    for imp in imports:
        resolved_path = _resolve_single_import(base_dir, imp, lang)
        if resolved_path:
            resolved.append(resolved_path)
    
    return resolved


def _resolve_single_import(
    base_dir: Path,
    imp: str,
    lang: str,
) -> str | None:
    """Resolve a single import to a path.
    
    Returns None for stdlib/third-party imports.
    """
    if lang == 'python':
        # Relative import
        if imp.startswith('.'):
            parts = imp.lstrip('.').split('.')
            levels = len(imp) - len(imp.lstrip('.'))
            target = base_dir
            for _ in range(levels - 1):
                target = target.parent
            target = target / '/'.join(parts)
            # Try .py extension
            if (target.with_suffix('.py')).exists():
                return str(target.with_suffix('.py'))
            # Try __init__.py in directory
            if (target / '__init__.py').exists():
                return str(target / '__init__.py')
        # Absolute import starting with src/ or similar
        elif imp.startswith('sunwell.') or imp.startswith('src.'):
            parts = imp.split('.')
            target = Path('/'.join(parts))
            return str(target.with_suffix('.py'))
    
    elif lang in ('typescript', 'javascript'):
        # Relative import
        if imp.startswith('.'):
            target = (base_dir / imp).resolve()
            # Try various extensions
            for ext in ['.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.js']:
                candidate = Path(str(target) + ext)
                if candidate.exists():
                    return str(candidate)
            return str(target)  # Return as-is, might resolve later
    
    elif lang == 'go':
        # Go imports are full module paths, skip external
        if not imp.startswith('.'):
            return None
    
    return None


def update_dependency_graph(store: LineageStore, path: str, content: str) -> None:
    """Update import/imported_by relationships after file change."""
    new_imports = detect_imports(Path(path), content)
    
    lineage = store.get_by_path(path)
    if not lineage:
        return
    
    old_imports = set(lineage.imports)
    new_imports_set = set(new_imports)
    
    # Remove this file from old imports' imported_by
    for removed in old_imports - new_imports_set:
        store.remove_imported_by(removed, path)
    
    # Add this file to new imports' imported_by
    for added in new_imports_set - old_imports:
        store.add_imported_by(added, path)
    
    # Update this file's imports
    store.update_imports(path, list(new_imports_set))
```

### Part 6: Event Bus Integration

```python
# sunwell/lineage/listener.py

from sunwell.server.events import EventBus, BusEvent
from sunwell.lineage.store import LineageStore
from sunwell.lineage.dependencies import detect_imports, update_dependency_graph
from sunwell.lineage.human_detection import HumanEditDetector
from pathlib import Path


class LineageEventListener:
    """Listens to agent events and updates lineage.
    
    Integrates with RFC-119 EventBus to capture file operations.
    """
    
    # Event types we listen for
    FILE_EVENTS = frozenset(['file_created', 'file_modified', 'file_deleted', 'file_renamed'])
    
    def __init__(
        self,
        store: LineageStore,
        event_bus: EventBus,
        human_detector: HumanEditDetector,
    ):
        self.store = store
        self.event_bus = event_bus
        self.human_detector = human_detector
        
        # Subscribe to file events
        # Note: EventBus currently uses broadcast(), we filter by event type
        self._subscribed = False
    
    async def start(self) -> None:
        """Start listening for events."""
        if self._subscribed:
            return
        # Wire into event stream (implementation depends on EventBus API)
        self._subscribed = True
    
    async def handle_event(self, event: BusEvent) -> None:
        """Route event to appropriate handler."""
        if event.type == 'file_created':
            await self._on_file_created(event)
        elif event.type == 'file_modified':
            await self._on_file_modified(event)
        elif event.type == 'file_deleted':
            await self._on_file_deleted(event)
        elif event.type == 'file_renamed':
            await self._on_file_renamed(event)
    
    async def _on_file_created(self, event: BusEvent) -> None:
        """Handle file creation event."""
        data = event.data
        path = data['path']
        content = data.get('content', '')
        
        self.store.record_create(
            path=path,
            content=content,
            goal_id=data.get('goal_id'),
            task_id=data.get('task_id'),
            reason=data.get('reason', 'Created by Sunwell'),
            model=data.get('model'),
            session_id=data.get('session_id'),
        )
        
        # Update dependency graph
        update_dependency_graph(self.store, path, content)
    
    async def _on_file_modified(self, event: BusEvent) -> None:
        """Handle file modification event."""
        data = event.data
        path = data['path']
        content = data.get('content', '')
        
        source = self.human_detector.classify_edit(
            path=path,
            goal_id=data.get('goal_id'),
            model=data.get('model'),
        )
        
        self.store.record_edit(
            path=path,
            goal_id=data.get('goal_id'),
            task_id=data.get('task_id'),
            lines_added=data.get('lines_added', 0),
            lines_removed=data.get('lines_removed', 0),
            source=source,
            model=data.get('model'),
            session_id=data.get('session_id'),
            content=content,
        )
        
        # Update dependency graph
        if content:
            update_dependency_graph(self.store, path, content)
    
    async def _on_file_deleted(self, event: BusEvent) -> None:
        """Handle file deletion event."""
        data = event.data
        self.store.record_delete(
            path=data['path'],
            goal_id=data.get('goal_id'),
            session_id=data.get('session_id'),
        )
    
    async def _on_file_renamed(self, event: BusEvent) -> None:
        """Handle file rename event."""
        data = event.data
        self.store.record_rename(
            old_path=data['old_path'],
            new_path=data['new_path'],
            goal_id=data.get('goal_id'),
            session_id=data.get('session_id'),
        )
```

### Part 7: Agent Integration (Required Events)

For lineage to work, the agent must emit file events. Add to agent execution:

```python
# sunwell/agent/core.py (additions)

async def _emit_file_event(
    self,
    event_type: str,
    path: str,
    content: str | None = None,
    old_path: str | None = None,
    lines_added: int = 0,
    lines_removed: int = 0,
) -> None:
    """Emit file event for lineage tracking."""
    if not self._event_bus:
        return
    
    data = {
        'path': path,
        'goal_id': self._current_goal_id,
        'task_id': self._current_task_id,
        'model': self._model_name,
        'session_id': self._session_id,
    }
    
    if content is not None:
        data['content'] = content
        data['lines_added'] = lines_added
        data['lines_removed'] = lines_removed
    
    if old_path:
        data['old_path'] = old_path
    
    event = BusEvent(
        v=1,
        run_id=self._run_id,
        type=event_type,
        data=data,
        timestamp=datetime.now(UTC),
        source='sunwell',
        project_id=self._project_id,
    )
    
    await self._event_bus.broadcast(event)


# In tool execution, after write_file:
async def _handle_write_file(self, path: str, content: str) -> None:
    """Handle write_file tool call."""
    full_path = self._workspace / path
    
    if full_path.exists():
        old_content = full_path.read_text()
        lines_added, lines_removed = _diff_lines(old_content, content)
        event_type = 'file_modified'
    else:
        lines_added = content.count('\n') + 1
        lines_removed = 0
        event_type = 'file_created'
    
    # Actually write the file
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    
    # Emit lineage event
    await self._emit_file_event(
        event_type=event_type,
        path=path,
        content=content,
        lines_added=lines_added,
        lines_removed=lines_removed,
    )
```

### Part 8: CLI Interface

```bash
# Show lineage for a file
sunwell lineage show src/auth/oauth.py

╭─────────────────────────────────────────────────────╮
│  📜 src/auth/oauth.py                               │
╰─────────────────────────────────────────────────────╯

Created: 2026-01-24 10:30
Goal: "Add OAuth authentication"
Model: claude-sonnet-4-20250514 via Sunwell
Reason: "OAuth client configuration for third-party auth"

Edits:
  v1  10:30  Created           (claude-sonnet-4-20250514)
  v2  10:45  Modified (+15/-3)  (claude-sonnet-4-20250514)
  v3  11:00  Modified (+5/-0)   (human)

Dependencies:
  imports:
    - src/config/settings.py
    - src/auth/base.py
  
  imported by:
    - src/api/routes.py
    - src/api/middleware.py

# Show all artifacts from a goal
sunwell lineage goal abc123

Goal: "Add OAuth authentication"
Status: Completed
Artifacts: 5 files

Created:
  ✓ src/auth/oauth.py
  ✓ src/auth/callback.py
  ✓ tests/test_oauth.py

Modified:
  ✓ src/config/settings.py (+3 lines)
  ✓ src/api/routes.py (+25 lines)

# Show dependency graph
sunwell lineage deps src/api/routes.py

src/api/routes.py
├── imports
│   ├── src/auth/oauth.py
│   ├── src/auth/callback.py
│   └── src/models/user.py
└── imported by
    └── src/main.py

# Impact analysis
sunwell lineage impact src/auth/base.py

If you delete src/auth/base.py, these files will be affected:
  - src/auth/oauth.py (imports it)
  - src/auth/callback.py (imports it)
  - tests/test_auth.py (imports it)

These goals created dependencies:
  - "Add OAuth authentication" (abc123)
  - "Add auth callback route" (def456)

# Detect untracked changes (human edits)
sunwell lineage sync

Found 3 files with untracked changes:
  ⚠️  src/config/settings.py (modified outside Sunwell)
  ⚠️  src/api/routes.py (modified outside Sunwell)
  ⚠️  tests/test_auth.py (new file, not tracked)

Mark these as human edits? [y/N]
```

### Part 9: Server API

```
# Get lineage for a file
GET /api/lineage/file?path=src/auth/oauth.py
→ ArtifactLineage JSON

# Get all artifacts for a goal
GET /api/lineage/goal/{goal_id}
→ { created: [...], modified: [...] }

# Get dependency graph
GET /api/lineage/deps?path=src/auth/oauth.py&direction=both
→ { imports: [...], imported_by: [...] }

# Impact analysis
GET /api/lineage/impact?path=src/auth/base.py
→ { affected_files: [...], affected_goals: [...] }

# Sync/detect untracked changes
POST /api/lineage/sync
→ { untracked: [...], resolved: [...] }
```

### Part 10: Studio Integration

```svelte
<!-- LineagePanel.svelte -->
<script lang="ts">
  import { getLineage } from '$lib/api/lineage';
  import DependencyGraph from './DependencyGraph.svelte';
  
  let { path } = $props();
  let lineage = $derived(getLineage(path));
</script>

<div class="lineage-panel">
  <header>
    <h3>📜 {path}</h3>
    {#if lineage?.human_edited}
      <span class="badge human">Human Edited</span>
    {/if}
  </header>
  
  <section class="birth">
    <h4>Created</h4>
    {#if lineage?.created_by_goal}
      <p>
        <a href="#" onclick={() => goToGoal(lineage.created_by_goal)}>
          {lineage.created_reason}
        </a>
      </p>
      <span class="meta">
        {formatDate(lineage.created_at)} · {lineage.model}
      </span>
    {:else}
      <p class="external">Pre-existing file (not created by Sunwell)</p>
    {/if}
  </section>
  
  <section class="edits">
    <h4>History ({lineage?.edits.length ?? 0} edits)</h4>
    <ul>
      {#each lineage?.edits ?? [] as edit, i}
        <li class:human={edit.source === 'human'} class:external={edit.source === 'external'}>
          <span class="version">v{i + 1}</span>
          <span class="type">{edit.edit_type}</span>
          <span class="delta">+{edit.lines_added}/-{edit.lines_removed}</span>
          <span class="source">
            {#if edit.source === 'human'}👤{:else if edit.source === 'sunwell'}🤖{:else}❓{/if}
            {edit.source}
          </span>
          {#if edit.goal_id}
            <a href="#" onclick={() => goToGoal(edit.goal_id)} class="goal-link">
              goal
            </a>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
  
  <section class="deps">
    <h4>Dependencies</h4>
    <DependencyGraph {lineage} />
  </section>
</div>

<style>
  .badge.human {
    background: var(--color-warning);
    color: var(--color-warning-fg);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.75rem;
  }
  
  li.human {
    border-left: 3px solid var(--color-warning);
    padding-left: 8px;
  }
  
  li.external {
    border-left: 3px solid var(--color-muted);
    padding-left: 8px;
    opacity: 0.7;
  }
</style>
```

---

## Storage

```
.sunwell/
├── lineage/
│   ├── index.json          # path → artifact_id mapping
│   ├── deleted.json        # Recently deleted artifact IDs (for rename detection)
│   └── artifacts/
│       ├── abc123.json
│       ├── def456.json
│       └── ...
```

### Index Format

```json
{
  "version": 1,
  "updated_at": "2026-01-24T10:30:00Z",
  "paths": {
    "src/auth/oauth.py": "a1b2c3d4-...:abc123",
    "src/auth/callback.py": "e5f6g7h8-...:def456"
  }
}
```

### Artifact Format

```json
{
  "artifact_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890:abc123",
  "path": "src/auth/oauth.py",
  "content_hash": "abc123def456...",
  "created_by_goal": "goal-xyz",
  "created_by_task": "task-1",
  "created_at": "2026-01-24T10:30:00Z",
  "created_reason": "OAuth client configuration",
  "model": "claude-sonnet-4-20250514",
  "human_edited": true,
  "edits": [
    {
      "edit_id": "e1",
      "artifact_id": "a1b2c3d4-...:abc123",
      "goal_id": "goal-xyz",
      "task_id": "task-1",
      "edit_type": "create",
      "lines_added": 50,
      "lines_removed": 0,
      "source": "sunwell",
      "model": "claude-sonnet-4-20250514",
      "timestamp": "2026-01-24T10:30:00Z",
      "session_id": "session-abc",
      "commit_hash": null,
      "content_hash": "abc123def456..."
    }
  ],
  "imports": ["src/config/settings.py"],
  "imported_by": ["src/api/routes.py"],
  "deleted_at": null
}
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ~~RFC-119 EventBus not implemented~~ | ~~Medium~~ | ~~High~~ | ✅ Resolved: EventBus implemented in `server/events.py` |
| Agent doesn't emit file events | Medium | High | Add to implementation plan; gate lineage on event emission |
| Index drift from artifacts | Low | Medium | Add `sunwell lineage repair` command for reindexing |
| Performance at scale (>10K files) | Low | Medium | Migrate to SQLite (see Design Alternatives) |
| Human edits missed | Medium | Low | Add `sunwell lineage sync` to detect untracked changes |
| Concurrent write corruption | Low | Medium | File locking in LineageStore; JSON is append-friendly |

### Remaining Risk: File Event Emission

**Current state**: RFC-119 EventBus is ✅ fully implemented (`server/events.py`). However, the agent does not yet emit file-specific events (`file_created`, `file_modified`, `file_deleted`).

**Mitigation plan**:
1. Phase 2 adds file event emission to agent (see Part 7)
2. If EventBus integration delayed, lineage can call store directly from tool handlers
3. Lineage works with or without event bus (event bus enables real-time Studio updates)

---

## Migration Strategy

### New Projects

Lineage tracking starts automatically on first Sunwell run.

### Existing Projects

```bash
# Initialize lineage for existing project
sunwell lineage init

This will:
1. Create .sunwell/lineage/ directory
2. Scan existing files (optional)
3. Mark all existing files as "pre-existing"

Scan existing files for dependency graph? [y/N] y

Scanning 142 files...
✓ Found 89 Python files
✓ Built dependency graph (234 imports)
✓ Created lineage records (marked as pre-existing)

Lineage initialized. New Sunwell operations will be tracked.
```

### Data Format Migrations

Version field in index.json enables future migrations:

```python
def _migrate_if_needed(self) -> None:
    """Migrate lineage data to latest schema version."""
    current_version = self._index.get('version', 0)
    
    if current_version < 1:
        self._migrate_v0_to_v1()
    # Future migrations here
```

---

## Implementation Plan

### Phase 1: Core Store (1 day)

| Task | File | Status |
|------|------|--------|
| Create data models | `src/sunwell/lineage/models.py` | ⬜ |
| Create store with locking | `src/sunwell/lineage/store.py` | ⬜ |
| Add identity resolver | `src/sunwell/lineage/identity.py` | ⬜ |
| Add unit tests | `tests/test_lineage_store.py` | ⬜ |

### Phase 2: Agent Integration (1 day)

| Task | File | Status |
|------|------|--------|
| Add file event emission | `src/sunwell/agent/core.py` | ⬜ |
| Create event listener | `src/sunwell/lineage/listener.py` | ⬜ |
| Add human edit detection | `src/sunwell/lineage/human_detection.py` | ⬜ |
| Integration tests | `tests/integration/test_lineage_events.py` | ⬜ |

### Phase 3: Dependency Detection (0.5 day)

| Task | File | Status |
|------|------|--------|
| Create dependency detector | `src/sunwell/lineage/dependencies.py` | ⬜ |
| Python import patterns | `src/sunwell/lineage/dependencies.py` | ⬜ |
| TypeScript import patterns | `src/sunwell/lineage/dependencies.py` | ⬜ |
| Unit tests for patterns | `tests/test_lineage_deps.py` | ⬜ |

### Phase 4: CLI (0.5 day)

| Task | File | Status |
|------|------|--------|
| Add `sunwell lineage show` | `src/sunwell/cli/lineage_cmd.py` | ⬜ |
| Add `sunwell lineage goal` | `src/sunwell/cli/lineage_cmd.py` | ⬜ |
| Add `sunwell lineage deps` | `src/sunwell/cli/lineage_cmd.py` | ⬜ |
| Add `sunwell lineage impact` | `src/sunwell/cli/lineage_cmd.py` | ⬜ |
| Add `sunwell lineage init` | `src/sunwell/cli/lineage_cmd.py` | ⬜ |
| Add `sunwell lineage sync` | `src/sunwell/cli/lineage_cmd.py` | ⬜ |

### Phase 5: API & Studio (1 day)

| Task | File | Status |
|------|------|--------|
| Add server endpoints | `src/sunwell/server/main.py` | ⬜ |
| Create LineagePanel.svelte | `studio/src/components/lineage/` | ⬜ |
| Create DependencyGraph.svelte | `studio/src/components/lineage/` | ⬜ |

**Total estimated time**: 4 days

---

## Testing

```python
# tests/test_lineage_store.py

import pytest
from pathlib import Path
from sunwell.lineage.store import LineageStore
from sunwell.lineage.models import compute_content_hash


class TestLineageStore:
    """Core store functionality tests."""
    
    def test_record_create(self, tmp_path: Path) -> None:
        store = LineageStore(tmp_path)
        
        lineage = store.record_create(
            path="src/auth.py",
            content="class Auth: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Auth module",
            model="claude-sonnet",
        )
        
        assert lineage.artifact_id is not None
        assert lineage.path == "src/auth.py"
        assert lineage.content_hash == compute_content_hash("class Auth: pass")
        
        # Retrieve by path
        retrieved = store.get_by_path("src/auth.py")
        assert retrieved is not None
        assert retrieved.artifact_id == lineage.artifact_id
    
    def test_edit_history(self, tmp_path: Path) -> None:
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/auth.py",
            content="class Auth: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Auth module",
            model="claude-sonnet",
        )
        
        store.record_edit(
            path="src/auth.py",
            goal_id="goal-2",
            task_id="task-2",
            lines_added=10,
            lines_removed=5,
            source="sunwell",
            model="claude-sonnet",
            content="class Auth:\n    def login(self): pass",
        )
        
        lineage = store.get_by_path("src/auth.py")
        assert lineage is not None
        assert len(lineage.edits) == 1  # Only modify edit (create is implicit)
        assert lineage.edits[0].lines_added == 10
    
    def test_rename_preserves_lineage(self, tmp_path: Path) -> None:
        store = LineageStore(tmp_path)
        original = store.record_create(
            path="src/old.py",
            content="class Old: pass",
            goal_id="goal-1",
            task_id="task-1",
            reason="Initial",
            model="claude-sonnet",
        )
        
        store.record_rename(
            old_path="src/old.py",
            new_path="src/new.py",
            goal_id="goal-2",
        )
        
        # Old path should not resolve
        assert store.get_by_path("src/old.py") is None
        
        # New path should resolve to same artifact
        renamed = store.get_by_path("src/new.py")
        assert renamed is not None
        assert renamed.artifact_id == original.artifact_id
        assert renamed.path == "src/new.py"
        assert any(e.edit_type == "rename" for e in renamed.edits)
    
    def test_delete_soft_deletes(self, tmp_path: Path) -> None:
        store = LineageStore(tmp_path)
        store.record_create(
            path="src/temp.py",
            content="# temp",
            goal_id="goal-1",
            task_id="task-1",
            reason="Temporary",
            model="claude-sonnet",
        )
        
        store.record_delete(path="src/temp.py", goal_id="goal-2")
        
        # Should not resolve by path
        assert store.get_by_path("src/temp.py") is None
        
        # But should be in recently deleted
        deleted = store.get_recently_deleted(hours=1)
        assert len(deleted) == 1
        assert deleted[0].path == "src/temp.py"


class TestRenameDetection:
    """Content-based rename detection tests."""
    
    def test_detect_move_by_content(self, tmp_path: Path) -> None:
        store = LineageStore(tmp_path)
        content = "class Auth:\n    def login(self): pass"
        
        # Create file
        original = store.record_create(
            path="src/auth.py",
            content=content,
            goal_id="goal-1",
            task_id="task-1",
            reason="Auth module",
            model="claude-sonnet",
        )
        
        # Delete it
        store.record_delete(path="src/auth.py", goal_id="goal-2")
        
        # Create with same content at new path
        moved = store.record_create(
            path="src/auth/main.py",
            content=content,  # Same content
            goal_id="goal-3",
            task_id="task-3",
            reason="Moved auth module",
            model="claude-sonnet",
        )
        
        # Should reuse artifact ID
        assert moved.artifact_id == original.artifact_id


class TestDependencyDetection:
    """Import detection tests."""
    
    def test_python_imports(self) -> None:
        from sunwell.lineage.dependencies import detect_imports
        
        content = '''
from src.config import settings
from .base import BaseAuth
import os
import sunwell.core.models
'''
        imports = detect_imports(Path("src/auth/oauth.py"), content)
        
        # Should detect local imports, not stdlib
        assert any("config" in imp for imp in imports) or any("base" in imp for imp in imports)
        assert not any("os" in imp for imp in imports)
    
    def test_typescript_imports(self) -> None:
        from sunwell.lineage.dependencies import detect_imports
        
        content = '''
import { User } from './models/user';
import * as utils from '../utils';
import React from 'react';
export { handler } from './handlers';
'''
        imports = detect_imports(Path("src/components/Auth.tsx"), content)
        
        # Should detect relative imports
        assert any("models" in imp or "user" in imp for imp in imports)
        assert any("utils" in imp for imp in imports)
        # Should not include 'react'
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Lineage lookup latency | < 50ms (p99) | Benchmark `get_by_path` |
| Sunwell file tracking | 100% | Audit: created files vs lineage records |
| Dependency accuracy | > 90% for Python/TS | Manual review of 100 files |
| Human edit detection | > 95% | Audit: edits outside session vs detected |

---

## Future Extensions

- **SQLite backend**: Migrate to SQLite when JSON performance insufficient
- **Git integration**: Correlate edits with commit hashes automatically
- **AST-level tracking**: Track function/class level changes, not just files
- **Cross-project lineage**: Track artifacts across related projects
- **Lineage visualization**: Interactive dependency graph in Observatory
- **Blame view**: Show which goal wrote each line (like git blame)

---

## References

- Pachyderm data provenance: [docs.pachyderm.com/provenance](https://docs.pachyderm.com)
- RFC-119: Unified Event Bus
- RFC-120: Observability & Debugging (SessionTracker integration)
- RFC-112: Observatory (visualization target)
- `src/sunwell/server/events.py`: EventBus implementation
- `src/sunwell/session/tracker.py`: SessionTracker for file tracking