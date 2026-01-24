# RFC-117: Project-Centric Workspace Isolation

**Status**: Draft  
**Created**: 2026-01-23  
**Author**: @llane  
**Depends on**: RFC-012 (Tool Calling), RFC-042 (Adaptive Agent)  
**Priority**: P0 — Prevents self-pollution bugs

---

## Summary

Replace implicit `Path.cwd()` workspace binding with explicit **Project** entities. All file operations require a bound project with a validated root path, eliminating the class of bugs where agent-generated content pollutes Sunwell's own source tree.

**The thesis**: A workspace is not just a path — it's a contract. Make that contract explicit.

---

## Problem Statement

### Current Behavior

When running `sunwell agent run` from Sunwell's repo directory:

```
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT: Implicit Workspace (Dangerous)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User: cd ~/sunwell && sunwell agent run "build a game"         │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ToolExecutor(workspace=Path.cwd())                     │   │
│  │  workspace = /Users/llane/sunwell  ← SUNWELL'S OWN REPO │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  Agent generates: write_file("src/rules/game_rules.py", ...)    │
│           │                                                     │
│           ▼                                                     │
│  File written to: /Users/llane/sunwell/src/rules/game_rules.py  │
│           │                                                     │
│           ▼                                                     │
│  😱 Project content leaks into Sunwell's source tree            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Real Bug (2026-01-23)

```
Gate gate_protocols failed at syntax: 1 errors
```

**Cause**: `src/rules/game_rules.py` contained markdown fences instead of Python — the agent wrote project content to Sunwell's own `src/` directory.

### Why This Happens

| Location | Code | Problem |
|----------|------|---------|
| `cli/agent/run.py:268` | `workspace=Path.cwd()` | cwd could be Sunwell repo |
| `cli/chat.py:1716` | `workspace=PathLib.cwd()` | Same issue |
| `cli/shortcuts.py:218` | `workspace_root or Path.cwd()` | Fallback to cwd |

**Root cause**: No concept of "project" — just raw paths with implicit cwd fallback.

---

## Goals

1. **Explicit project binding** — Every execution has a declared project root
2. **No cwd fallback** — Remove all `Path.cwd()` defaults for file operations
3. **Self-pollution guard** — Refuse to write to Sunwell's own directories
4. **Project manifest** — `.sunwell/project.toml` marks project boundaries
5. **Project registry** — Track known projects for quick switching

## Non-Goals

1. **Full project management** — Not replacing IDE project concepts
2. **Multi-project orchestration** — One project per execution (for now)
3. **Remote project support** — Local filesystem only
4. **Backward compatibility** — Will break existing `cwd()` workflows (intentionally)

---

## Design

### The Project Entity

```python
@dataclass(frozen=True, slots=True)
class Project:
    """A workspace with explicit boundaries.
    
    Projects are first-class entities that define where the agent can
    read/write files. No more implicit cwd() — all file operations are
    scoped to a project.
    """
    
    id: str
    """Unique identifier (e.g., 'my-fastapi-app')."""
    
    name: str
    """Human-readable name."""
    
    root: Path
    """Absolute path to project root. All file ops relative to this."""
    
    workspace_type: WorkspaceType
    """How the workspace was created/validated."""
    
    created_at: datetime
    """When this project was registered."""
    
    manifest_path: Path | None = None
    """Path to .sunwell/project.toml if it exists."""


class WorkspaceType(Enum):
    """How the workspace was established."""
    
    MANIFEST = "manifest"
    """Has .sunwell/project.toml — fully configured."""
    
    REGISTERED = "registered"
    """Manually registered via CLI, no manifest."""
    
    TEMPORARY = "temporary"
    """Ephemeral sandbox (e.g., benchmark runs)."""
```

### Project Manifest

Projects are marked with `.sunwell/project.toml`:

```toml
# .sunwell/project.toml
[project]
id = "my-fastapi-app"
name = "My FastAPI App"
created = "2026-01-23T14:30:00Z"

[workspace]
# "existing" = write directly to project
# "sandboxed" = stage changes for review (future)
type = "existing"

[agent]
# Default trust level for this project
trust = "workspace"

# Directories agent should NOT modify
protected = [
    ".git",
    "migrations",
]
```

### Project Registry

Global registry at `~/.sunwell/projects.json`:

```json
{
  "projects": {
    "my-fastapi-app": {
      "root": "/home/user/projects/my-app",
      "manifest": "/home/user/projects/my-app/.sunwell/project.toml",
      "last_used": "2026-01-23T15:00:00Z"
    },
    "game-prototype": {
      "root": "/home/user/projects/game",
      "manifest": null,
      "last_used": "2026-01-22T10:00:00Z"
    }
  },
  "default_project": "my-fastapi-app"
}
```

### Self-Pollution Guard

Before any file write, validate the project root:

```python
SUNWELL_MARKERS = frozenset({
    "src/sunwell",
    "bengal/core",
    "pyproject.toml"  # Check for name = "sunwell"
})

def validate_project_root(root: Path) -> None:
    """Refuse to use Sunwell's own repo as a project.
    
    Raises:
        ProjectValidationError: If root appears to be Sunwell itself
    """
    for marker in SUNWELL_MARKERS:
        if (root / marker).exists():
            # Additional check: is this actually sunwell?
            pyproject = root / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text()
                if 'name = "sunwell"' in content:
                    raise ProjectValidationError(
                        f"Cannot use Sunwell's own repository as project workspace.\n"
                        f"Root: {root}\n"
                        f"Create a separate directory for your project."
                    )
```

### ToolExecutor Changes

```python
@dataclass
class ToolExecutor:
    """Execute tool calls within a project boundary."""
    
    # BEFORE
    # workspace: Path  ← Raw path, could be anything
    
    # AFTER
    project: Project  # ← Validated project with explicit root
    
    def __post_init__(self):
        # Validate on construction
        validate_project_root(self.project.root)
        
        # Initialize handlers with project root
        self._core_handlers = CoreToolHandlers(
            workspace=self.project.root,
            blocked_patterns=self._get_blocked_patterns(),
        )
    
    def _get_blocked_patterns(self) -> frozenset[str]:
        """Combine default blocks with project-specific protections."""
        patterns = set(DEFAULT_BLOCKED_PATTERNS)
        
        if self.project.manifest_path:
            manifest = load_manifest(self.project.manifest_path)
            patterns.update(manifest.agent.protected)
        
        return frozenset(patterns)
```

### CLI Changes

```bash
# Initialize a project (creates .sunwell/project.toml)
sunwell project init [path]
sunwell project init .                    # Current directory
sunwell project init ~/projects/my-app    # Specific path

# List registered projects
sunwell project list
# ID               ROOT                          LAST USED
# my-fastapi-app   /home/user/projects/my-app    2 hours ago
# game-prototype   /home/user/projects/game      1 day ago

# Set default project
sunwell project default my-fastapi-app

# Remove from registry (doesn't delete files)
sunwell project remove game-prototype

# Agent commands now require project context
sunwell agent run "add user auth"                    # Uses default project
sunwell agent run "add user auth" -p my-fastapi-app  # Explicit project
sunwell agent run "add user auth" --project-root .   # Use cwd (with validation)

# Error if no project context
$ cd /tmp && sunwell agent run "build something"
Error: No project context. Either:
  - Run from a directory with .sunwell/project.toml
  - Use -p <project-id> to specify a registered project
  - Use --project-root <path> to specify an explicit path
```

### Studio Integration

Studio sends project context with all requests:

```typescript
interface AgentRunRequest {
  // BEFORE
  workspace?: string;  // Optional, defaulted to cwd
  
  // AFTER
  project_id: string;  // Required, must be registered
}

// Studio maintains project list
interface StudioState {
  projects: Project[];
  activeProject: Project | null;
}
```

### Resolution Order

When determining project context:

```
1. Explicit --project-root flag (with validation)
2. Explicit -p <project-id> flag
3. .sunwell/project.toml in current directory
4. Default project from registry
5. ERROR — no implicit fallback to cwd()
```

---

## Migration

### Breaking Changes

| Before | After |
|--------|-------|
| `sunwell agent run "task"` (uses cwd) | Must have project context |
| `ToolExecutor(workspace=Path.cwd())` | `ToolExecutor(project=Project(...))` |
| No manifest required | `.sunwell/project.toml` recommended |

### Migration Path

1. **Phase 1** (immediate): Add self-pollution guard to existing code
2. **Phase 2**: Create `Project` model and validation
3. **Phase 3**: Add `sunwell project` CLI commands
4. **Phase 4**: Refactor `ToolExecutor` to use `Project`
5. **Phase 5**: Update Studio to require project binding
6. **Phase 6**: Remove all `Path.cwd()` fallbacks

### Backward Compatibility

**None intentional.** The cwd fallback is the bug — removing it is the fix.

Users will see:

```
Error: No project context. Run 'sunwell project init .' to initialize this directory.
```

---

## Implementation

### New Files

```
src/sunwell/project/
├── __init__.py
├── types.py          # Project, WorkspaceType, ProjectManifest
├── registry.py       # ProjectRegistry (load/save ~/.sunwell/projects.json)
├── manifest.py       # Load/save .sunwell/project.toml
├── validation.py     # validate_project_root(), self-pollution guard
└── resolver.py       # Resolve project from flags/cwd/registry
```

### Modified Files

| File | Change |
|------|--------|
| `tools/executor.py` | `workspace: Path` → `project: Project` |
| `tools/handlers/base.py` | Accept `Project` instead of raw `Path` |
| `cli/agent/run.py` | Use `ProjectResolver`, remove cwd fallback |
| `cli/chat.py` | Same |
| `cli/main.py` | Add `sunwell project` command group |
| `server/main.py` | Require `project_id` in requests |

### Task Breakdown

| Task | Estimate | Dependencies |
|------|----------|--------------|
| Add self-pollution guard | 1 hour | None |
| Create `Project` types | 2 hours | None |
| Create `ProjectRegistry` | 2 hours | Project types |
| Create manifest loader | 1 hour | Project types |
| Create `ProjectResolver` | 2 hours | Registry, manifest |
| Add `sunwell project` CLI | 3 hours | All above |
| Refactor `ToolExecutor` | 3 hours | Project types |
| Update `cli/agent/run.py` | 1 hour | ProjectResolver |
| Update `cli/chat.py` | 1 hour | ProjectResolver |
| Update Studio | 2 hours | Server changes |
| Remove cwd fallbacks | 1 hour | All above |

**Total**: ~19 hours

---

## Alternatives Considered

### 1. Just Add `--workspace` Flag

**Rejected**: Still allows cwd fallback, doesn't solve the root problem.

### 2. Temp Sandbox for All Writes

**Deferred**: Good for high-trust scenarios, but adds UX friction. Can layer on later with `workspace.type = "sandboxed"`.

### 3. Blocklist Sunwell Paths

**Partial adoption**: The self-pollution guard is included as Phase 1, but it's a band-aid. The project model is the real fix.

### 4. Detect by Git Remote

**Rejected**: Not all projects use git, and remote URLs can be ambiguous.

---

## Security Considerations

1. **Path traversal**: `_safe_path()` already prevents escaping workspace; now workspace itself is validated
2. **Registry poisoning**: Registry is user-local (`~/.sunwell/`), same trust as user's home
3. **Manifest injection**: Manifest is read-only to agent; user controls protected paths

---

## Success Criteria

1. ✅ Running `sunwell agent run` from Sunwell's repo directory fails with clear error
2. ✅ `sunwell project init .` creates valid manifest
3. ✅ Projects persist across sessions via registry
4. ✅ Studio shows project selector, requires binding
5. ✅ No `Path.cwd()` remains in file operation paths

---

## References

- RFC-012: Tool Calling (defines `ToolExecutor`)
- RFC-042: Adaptive Agent (defines execution flow)
- Bug: `src/rules/game_rules.py` self-pollution (2026-01-23)
