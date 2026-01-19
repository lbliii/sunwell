# RFC-041: Surgical File Editing

| Field | Value |
|-------|-------|
| **RFC** | 041 |
| **Title** | Surgical File Editing |
| **Status** | Draft |
| **Created** | 2026-01-19 |
| **Author** | llane |
| **Builds on** | RFC-036 (Artifact-First Planning), RFC-015 (Mirror Neurons) |
| **Prerequisites** | None (can be implemented independently) |

---

## Abstract

Sunwell's current file modification capability is **all-or-nothing**: `write_file` replaces the entire file content. This prevents:

1. **Phased development** — Can't incrementally build up a file
2. **Multi-task coordination** — Multiple tasks targeting the same file clobber each other
3. **Self-improvement** — Can't safely modify existing code (as demonstrated when Sunwell deleted 361 lines trying to "improve" itself)
4. **Proper `modify` mode** — The planner distinguishes `generate` vs `modify`, but both use the same destructive `write_file`

This RFC proposes **surgical file editing**: tools that make targeted changes to files without replacing the entire content.

```
CURRENT:    Task A writes file.py (100 lines)
            Task B writes file.py (50 lines) ← Task A's work is LOST

PROPOSED:   Task A creates file.py (100 lines)
            Task B modifies lines 45-60 ← Task A's work is PRESERVED
```

---

## Goals and Non-Goals

### Goals

1. **`edit_file` tool** — Search-and-replace with context matching
2. **`patch_file` tool** — Apply unified diff patches
3. **`insert_at` tool** — Insert content at specific line numbers
4. **Conflict detection** — Warn when multiple tasks target the same file region
5. **Backup before edit** — Automatic `.bak` creation for rollback
6. **Analysis-only mode** — Return findings without any file writes

### Non-Goals

1. **Full merge conflict resolution** — Complex 3-way merges are out of scope
2. **AST-aware editing** — Syntactic transformations are future work
3. **Multi-file transactions** — Atomic multi-file commits are separate
4. **IDE integration** — Language server protocol is out of scope

---

## Motivation

### The Clobber Problem

On 2026-01-19, we asked Sunwell to analyze its own `mirror/analysis.py` and suggest improvements:

```bash
sunwell "Analyze src/sunwell/mirror/analysis.py and suggest 3 code improvements"
```

**Expected**: Analysis with suggestions, maybe targeted edits
**Actual**: File deleted (361 → 2 lines)

**What happened:**
1. Planner created 3 tasks, all targeting `analysis.py`
2. Each task used `mode=generate` (not `modify`)
3. Each task called `write_file` with its own content
4. Last task wrote a 2-line stub, destroying everything

### Why This Matters

| Use Case | Current Behavior | Needed Behavior |
|----------|-----------------|-----------------|
| Add feature to existing file | Overwrites entire file | Insert/append to file |
| Fix bug in function | Overwrites entire file | Replace specific lines |
| Multi-agent same file | Last agent wins | Merge edits safely |
| Self-improvement | Destroys code | Surgical patches |
| Phased development | Each phase clobbers previous | Accumulate changes |

### Evidence from Codebase

The planner already distinguishes modes (`agent.py:185-188`):
```python
TASK MODES - Choose based on the action:
- "generate" = CREATE new files that don't exist (use write_file)
- "modify"   = EDIT existing files (use write_file after read_file)
```

But both modes use the same `write_file` tool. The `modify` mode is a lie.

---

## Proposed Design

### New Tools

#### 1. `edit_file` — Context-Aware Search and Replace

```python
EDIT_FILE_TOOL = Tool(
    name="edit_file",
    description=(
        "Make targeted edits to a file by replacing specific content. "
        "Requires unique context to identify the edit location. "
        "Safer than write_file for modifying existing files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to workspace root",
            },
            "old_content": {
                "type": "string",
                "description": (
                    "The exact content to find and replace. "
                    "Include enough context (3-5 lines) to uniquely identify the location."
                ),
            },
            "new_content": {
                "type": "string",
                "description": "The content to replace old_content with",
            },
            "occurrence": {
                "type": "integer",
                "description": "Which occurrence to replace (1 = first, -1 = last, 0 = all). Default: 1",
                "default": 1,
            },
        },
        "required": ["path", "old_content", "new_content"],
    },
)
```

**Example usage:**
```json
{
  "path": "src/sunwell/mirror/analysis.py",
  "old_content": "def analyze_errors(\n    self,\n    audit_log: list[Any],",
  "new_content": "def analyze_errors(\n    self,\n    audit_log: list[AuditEntry],",
  "occurrence": 1
}
```

**Behavior:**
1. Read file content
2. Find `old_content` (exact match, including whitespace)
3. If not found → Error with helpful message
4. If found multiple times and `occurrence=1` → Replace first only
5. If `occurrence=0` → Replace all
6. Create `.bak` backup
7. Write modified content

#### 2. `patch_file` — Apply Unified Diff

```python
PATCH_FILE_TOOL = Tool(
    name="patch_file",
    description=(
        "Apply a unified diff patch to a file. "
        "Useful for complex multi-region edits. "
        "Creates backup before applying."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to workspace root",
            },
            "patch": {
                "type": "string",
                "description": "Unified diff format patch (output of diff -u)",
            },
        },
        "required": ["path", "patch"],
    },
)
```

**Example:**
```json
{
  "path": "src/analysis.py",
  "patch": "@@ -45,7 +45,7 @@\n def analyze_errors(\n     self,\n-    audit_log: list[Any],\n+    audit_log: list[AuditEntry],"
}
```

#### 3. `insert_at` — Line-Based Insertion

```python
INSERT_AT_TOOL = Tool(
    name="insert_at",
    description=(
        "Insert content at a specific line number. "
        "Line 0 inserts at the beginning, line -1 appends at end."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path",
            },
            "line": {
                "type": "integer",
                "description": "Line number to insert at (0 = beginning, -1 = end)",
            },
            "content": {
                "type": "string",
                "description": "Content to insert",
            },
        },
        "required": ["path", "line", "content"],
    },
)
```

### Conflict Detection

When multiple tasks in the same execution target the same file:

```python
@dataclass
class FileEditTracker:
    """Track edits to detect conflicts."""
    
    edits: dict[str, list[EditRecord]] = field(default_factory=dict)
    
    def record_edit(self, path: str, task_id: str, region: tuple[int, int]) -> None:
        """Record an edit for conflict detection."""
        self.edits.setdefault(path, []).append(
            EditRecord(task_id=task_id, start_line=region[0], end_line=region[1])
        )
    
    def check_conflicts(self, path: str, region: tuple[int, int]) -> list[EditRecord]:
        """Return conflicting edits if regions overlap."""
        conflicts = []
        for edit in self.edits.get(path, []):
            if self._overlaps(edit, region):
                conflicts.append(edit)
        return conflicts
```

**On conflict:**
- Warn user
- Show both edits
- Allow: skip, force, or manual resolution

### Analysis-Only Mode

New task mode for read-only operations:

```python
class TaskMode(Enum):
    RESEARCH = "research"   # Read files
    GENERATE = "generate"   # Create new files
    MODIFY = "modify"       # Edit existing files
    EXECUTE = "execute"     # Run commands
    ANALYZE = "analyze"     # NEW: Read and report, no writes
```

**Behavior:**
- Can use `read_file`, `search_files`, `list_files`
- Cannot use `write_file`, `edit_file`, `patch_file`
- Returns structured findings without file modifications

**Prompt update for planner:**
```
TASK MODES - Choose based on the action:
- "research" = READ existing files to understand them
- "generate" = CREATE new files that don't exist
- "modify"   = EDIT existing files surgically (use edit_file)
- "execute"  = RUN shell commands
- "analyze"  = INSPECT and REPORT without modifying (for audits, reviews)
```

---

## Implementation Plan

### Phase 1: Core Tools (2-3 hours)

1. **Add `edit_file` handler** in `tools/handlers.py`
   - Exact string matching
   - Backup creation
   - Occurrence handling

2. **Add tool definition** in `tools/builtins.py`

3. **Tests** in `tests/test_tools.py`
   - Single occurrence replacement
   - Multiple occurrence handling
   - Not-found error
   - Backup creation

### Phase 2: Planner Integration (1-2 hours)

1. **Update planner prompts** to prefer `edit_file` for modify mode
2. **Add `analyze` mode** to TaskMode enum
3. **Route modify tasks** through `edit_file` instead of `write_file`

### Phase 3: Conflict Detection (1 hour)

1. **FileEditTracker** class
2. **Integration with executor** to track edits
3. **Warning/resolution flow**

### Phase 4: Patch Support (optional, 1 hour)

1. **`patch_file` handler** using Python's `difflib`
2. **Tool definition**
3. **Tests**

---

## File Changes

```
src/sunwell/tools/
├── builtins.py      # Add EDIT_FILE_TOOL, INSERT_AT_TOOL, PATCH_FILE_TOOL
├── handlers.py      # Add handle_edit_file(), handle_insert_at(), handle_patch_file()
├── types.py         # Add edit tools to trust levels

src/sunwell/naaru/
├── types.py         # Add TaskMode.ANALYZE
├── planners/agent.py # Update prompts to use edit_file for modify mode
├── naaru.py         # Route modify tasks correctly
├── conflict.py      # NEW: FileEditTracker

tests/
├── test_tools.py    # Add edit_file tests
├── test_conflict.py # NEW: Conflict detection tests
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model generates wrong `old_content` | High | Medium | Include line numbers in error, suggest fuzzy match |
| Backup files accumulate | Low | Low | Cleanup after successful execution |
| Conflict detection false positives | Medium | Low | Allow force override |
| Patch format errors | Medium | Medium | Validate patch before applying |

---

## Success Criteria

1. **Self-improvement works** — Sunwell can modify `analysis.py` without destroying it
2. **Phased development works** — Multiple tasks can build up the same file
3. **Audit mode exists** — Can analyze code without writing files
4. **Tests pass** — Full coverage of new tools

---

## Future Work

1. **AST-aware editing** — "Add method to class X" without line numbers
2. **Semantic merge** — Handle conflicting edits intelligently
3. **Transaction support** — Atomic multi-file commits
4. **Undo stack** — Multiple levels of rollback

---

## References

- RFC-015: Mirror Neurons (self-introspection)
- RFC-036: Artifact-First Planning (task modes)
- Cursor's `search_replace` tool (inspiration for `edit_file`)
- GNU patch (unified diff format)
