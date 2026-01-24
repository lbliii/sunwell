# RFC-121: Artifact Lineage & Provenance

**Status**: Draft  
**Author**: Auto-generated  
**Created**: 2026-01-24  
**Depends on**: RFC-119 (Unified Event Bus)

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

---

## Design

### Part 1: Data Model

```python
# sunwell/lineage/models.py

@dataclass(frozen=True)
class ArtifactLineage:
    """Lineage record for a single artifact."""
    
    # Identity
    artifact_id: str              # Stable ID across renames
    path: str                     # Current path
    
    # Birth
    created_by_goal: str | None   # Goal ID that created it
    created_by_task: str | None   # Task ID that created it
    created_at: datetime
    created_reason: str           # Why this artifact exists
    
    # Attribution
    model: str | None             # Which model wrote it
    human_edited: bool            # Has human modified it?
    
    # History
    edits: list[ArtifactEdit]
    
    # Dependencies
    imports: list[str]            # What this file imports
    imported_by: list[str]        # What imports this file
    

@dataclass(frozen=True)
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
    source: str                  # "sunwell" | "human"
    model: str | None            # If sunwell, which model
    
    # Timing
    timestamp: datetime
    
    # Git correlation (optional)
    commit_hash: str | None
```

### Part 2: Lineage Store

```python
# sunwell/lineage/store.py

class LineageStore:
    """Persistent storage for artifact lineage."""
    
    def __init__(self, project_root: Path):
        self.store_path = project_root / '.sunwell' / 'lineage'
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()
    
    # ── Recording ───────────────────────────────────────────
    
    def record_create(
        self,
        path: str,
        goal_id: str,
        task_id: str | None,
        reason: str,
        model: str | None,
    ) -> ArtifactLineage:
        """Record artifact creation."""
        artifact_id = self._generate_id()
        lineage = ArtifactLineage(
            artifact_id=artifact_id,
            path=path,
            created_by_goal=goal_id,
            created_by_task=task_id,
            created_at=datetime.utcnow(),
            created_reason=reason,
            model=model,
            human_edited=False,
            edits=[],
            imports=[],
            imported_by=[],
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
    ) -> ArtifactEdit:
        """Record an edit to an artifact."""
        lineage = self.get_by_path(path)
        if not lineage:
            # File exists but wasn't created by Sunwell
            lineage = self._create_external(path)
        
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
            timestamp=datetime.utcnow(),
            commit_hash=None,
        )
        
        self._append_edit(lineage.artifact_id, edit)
        
        if source == "human":
            self._mark_human_edited(lineage.artifact_id)
        
        return edit
    
    def record_rename(self, old_path: str, new_path: str, goal_id: str | None):
        """Record artifact rename."""
        lineage = self.get_by_path(old_path)
        if lineage:
            self._update_path(lineage.artifact_id, new_path)
            self._update_index(old_path, None)  # Remove old
            self._update_index(new_path, lineage.artifact_id)  # Add new
    
    def record_delete(self, path: str, goal_id: str | None):
        """Record artifact deletion."""
        lineage = self.get_by_path(path)
        if lineage:
            self._append_edit(lineage.artifact_id, ArtifactEdit(
                edit_type="delete",
                goal_id=goal_id,
                ...
            ))
    
    # ── Queries ─────────────────────────────────────────────
    
    def get_by_path(self, path: str) -> ArtifactLineage | None:
        """Get lineage for a file path."""
        artifact_id = self._index.get(path)
        return self._load(artifact_id) if artifact_id else None
    
    def get_by_goal(self, goal_id: str) -> list[ArtifactLineage]:
        """Get all artifacts created/modified by a goal."""
        ...
    
    def get_dependents(self, path: str) -> list[str]:
        """Get all files that import this file."""
        lineage = self.get_by_path(path)
        return lineage.imported_by if lineage else []
    
    def get_dependencies(self, path: str) -> list[str]:
        """Get all files this file imports."""
        lineage = self.get_by_path(path)
        return lineage.imports if lineage else []
```

### Part 3: Dependency Detection

Simple import detection (not full AST):

```python
# sunwell/lineage/dependencies.py

import re
from pathlib import Path

IMPORT_PATTERNS = {
    'python': [
        r'^import\s+(\S+)',
        r'^from\s+(\S+)\s+import',
    ],
    'typescript': [
        r"import\s+.*from\s+['\"](.+)['\"]",
        r"require\(['\"](.+)['\"]\)",
    ],
    'go': [
        r'"([^"]+)"',  # Within import block
    ],
}

def detect_imports(path: Path, content: str) -> list[str]:
    """Detect imports in a file."""
    ext = path.suffix
    lang = _extension_to_lang(ext)
    patterns = IMPORT_PATTERNS.get(lang, [])
    
    imports = []
    for pattern in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            imports.append(match.group(1))
    
    return _resolve_imports(path.parent, imports)

def _resolve_imports(base_dir: Path, imports: list[str]) -> list[str]:
    """Resolve relative imports to absolute paths."""
    resolved = []
    for imp in imports:
        if imp.startswith('.'):
            # Relative import
            resolved.append(str((base_dir / imp).resolve()))
        else:
            # Could be stdlib or third-party - skip for now
            pass
    return resolved
```

### Part 4: Integration with Event Bus

```python
# sunwell/lineage/listener.py

class LineageEventListener:
    """Listens to events and updates lineage."""
    
    def __init__(self, store: LineageStore, event_bus: EventBus):
        self.store = store
        event_bus.subscribe('file_created', self._on_file_created)
        event_bus.subscribe('file_modified', self._on_file_modified)
        event_bus.subscribe('file_deleted', self._on_file_deleted)
    
    async def _on_file_created(self, event: dict):
        self.store.record_create(
            path=event['path'],
            goal_id=event.get('goal_id'),
            task_id=event.get('task_id'),
            reason=event.get('reason', 'Unknown'),
            model=event.get('model'),
        )
        
        # Update dependency graph
        content = Path(event['path']).read_text()
        imports = detect_imports(Path(event['path']), content)
        self.store.update_imports(event['path'], imports)
    
    async def _on_file_modified(self, event: dict):
        self.store.record_edit(
            path=event['path'],
            goal_id=event.get('goal_id'),
            task_id=event.get('task_id'),
            lines_added=event.get('lines_added', 0),
            lines_removed=event.get('lines_removed', 0),
            source=event.get('source', 'sunwell'),
            model=event.get('model'),
        )
```

### Part 5: CLI Interface

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
```

### Part 6: Server API

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
```

### Part 7: Studio Integration

```svelte
<!-- LineagePanel.svelte -->
<script lang="ts">
  let { path } = $props();
  let lineage = $derived(getLineage(path));
</script>

<div class="lineage-panel">
  <header>
    <h3>📜 {path}</h3>
  </header>
  
  <section class="birth">
    <h4>Created</h4>
    <p>
      <a href="#" onclick={() => goToGoal(lineage.created_by_goal)}>
        {lineage.created_reason}
      </a>
    </p>
    <span class="meta">
      {formatDate(lineage.created_at)} · {lineage.model}
    </span>
  </section>
  
  <section class="edits">
    <h4>History ({lineage.edits.length} edits)</h4>
    <ul>
      {#each lineage.edits as edit}
        <li class:human={edit.source === 'human'}>
          <span class="version">v{edit.version}</span>
          <span class="type">{edit.edit_type}</span>
          <span class="delta">+{edit.lines_added}/-{edit.lines_removed}</span>
          <span class="source">{edit.source}</span>
        </li>
      {/each}
    </ul>
  </section>
  
  <section class="deps">
    <h4>Dependencies</h4>
    <DependencyGraph {lineage} />
  </section>
</div>
```

---

## Storage

```
.sunwell/
├── lineage/
│   ├── index.json          # path → artifact_id mapping
│   └── artifacts/
│       ├── abc123.json
│       ├── def456.json
│       └── ...
```

### Index Format

```json
{
  "src/auth/oauth.py": "abc123",
  "src/auth/callback.py": "def456",
  "tests/test_oauth.py": "ghi789"
}
```

### Artifact Format

```json
{
  "artifact_id": "abc123",
  "path": "src/auth/oauth.py",
  "created_by_goal": "goal-xyz",
  "created_by_task": "task-1",
  "created_at": "2026-01-24T10:30:00Z",
  "created_reason": "OAuth client configuration",
  "model": "claude-sonnet-4-20250514",
  "human_edited": true,
  "edits": [
    {
      "edit_id": "e1",
      "edit_type": "create",
      "lines_added": 50,
      "lines_removed": 0,
      "source": "sunwell",
      "timestamp": "2026-01-24T10:30:00Z"
    }
  ],
  "imports": ["src/config/settings.py"],
  "imported_by": ["src/api/routes.py"]
}
```

---

## Implementation Plan

### Phase 1: Core Store (1 day)

1. Create `sunwell/lineage/models.py`
2. Create `sunwell/lineage/store.py`
3. Add tests for store operations

### Phase 2: Event Integration (0.5 day)

1. Create `sunwell/lineage/listener.py`
2. Wire into event bus from RFC-119
3. Add `file_created`, `file_modified`, `file_deleted` events to agent

### Phase 3: Dependency Detection (0.5 day)

1. Create `sunwell/lineage/dependencies.py`
2. Add Python import detection
3. Add TypeScript import detection
4. Add dependency graph updates

### Phase 4: CLI (0.5 day)

1. Add `sunwell lineage show`
2. Add `sunwell lineage goal`
3. Add `sunwell lineage deps`
4. Add `sunwell lineage impact`

### Phase 5: API & Studio (1 day)

1. Add server endpoints
2. Create LineagePanel.svelte
3. Create DependencyGraph.svelte

---

## Testing

```python
# test_lineage_store.py
async def test_record_create():
    store = LineageStore(tmp_path)
    
    lineage = store.record_create(
        path="src/auth.py",
        goal_id="goal-1",
        task_id="task-1",
        reason="Auth module",
        model="claude-sonnet",
    )
    
    assert lineage.artifact_id is not None
    assert lineage.path == "src/auth.py"
    
    # Retrieve by path
    retrieved = store.get_by_path("src/auth.py")
    assert retrieved == lineage

async def test_edit_history():
    store = LineageStore(tmp_path)
    store.record_create(path="src/auth.py", ...)
    
    store.record_edit(
        path="src/auth.py",
        goal_id="goal-2",
        lines_added=10,
        lines_removed=5,
        source="sunwell",
    )
    
    lineage = store.get_by_path("src/auth.py")
    assert len(lineage.edits) == 2  # create + modify
    assert lineage.edits[-1].lines_added == 10

async def test_dependency_detection():
    content = '''
from src.config import settings
from .base import BaseAuth
import os
'''
    imports = detect_imports(Path("src/auth/oauth.py"), content)
    
    assert "src/config" in imports or "src.config" in imports
    assert "base" in imports or ".base" in imports
```

---

## Success Metrics

- Lineage lookup < 50ms
- 100% of Sunwell-created files tracked
- Dependency graph 90%+ accurate for Python/TypeScript

---

## Future Extensions

- **Git integration**: Correlate with commit hashes
- **AST-level tracking**: Track function/class level changes
- **Cross-project lineage**: Track artifacts across related projects
- **Lineage visualization**: Interactive graph in Observatory

---

## References

- Pachyderm data provenance
- RFC-119: Unified Event Bus
- RFC-112: Observatory (visualization target)
