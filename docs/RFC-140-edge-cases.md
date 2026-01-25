# RFC-140: Edge Cases & Gaps Analysis

## 🔴 Critical Gaps

### 1. **Race Conditions in Workspace Switching**

**Issue**: Multiple concurrent switch operations could cause inconsistent state.

**Current State**:
- No locking mechanism
- `_save_current_workspace()` writes directly to file
- Multiple API requests could overwrite each other

**Impact**: 
- Last write wins, could lose workspace context
- UI state could desync from backend state

**Fix Needed**:
```python
# Add file locking or atomic write
import fcntl  # Unix
# or use tempfile + rename pattern for atomic writes
```

### 2. **Current Workspace Becomes Invalid**

**Issue**: If current workspace is deleted or becomes invalid, `get_current()` returns `None` but doesn't clear the state file.

**Current State**:
- `get_current()` returns `None` if path doesn't exist
- But `~/.sunwell/current_workspace.json` still points to invalid path
- Next `get_current()` call will fail again

**Impact**:
- Stale state persists
- User can't easily recover

**Fix Needed**:
```python
def get_current(self) -> WorkspaceInfo | None:
    state = _load_current_workspace()
    if not state:
        return None
    
    workspace_path = Path(state["workspace_path"])
    if not workspace_path.exists():
        # Clear invalid state
        _clear_current_workspace()
        return None
    # ... rest of logic
```

### 3. **Symlink Resolution Issues**

**Issue**: `path.resolve()` follows symlinks, but discovery might find both symlink and target.

**Current State**:
- Uses `path.resolve()` which follows symlinks
- Could create duplicate entries (symlink path vs resolved path)
- Deduplication by `set[Path]` should catch this, but edge cases exist

**Impact**:
- Duplicate workspaces in list
- Confusion about which is "real"

**Fix Needed**:
```python
# Always resolve to canonical path
canonical_path = path.resolve().resolve()  # Double resolve for symlinks
```

### 4. **Discovery Performance on Large Directories**

**Issue**: `discover_workspaces()` scans all children of root directories. Large directories (e.g., `~/Code` with 1000+ subdirs) could be slow.

**Current State**:
- No depth limit
- No timeout
- No progress reporting
- Blocks API request

**Impact**:
- Slow API responses
- UI freezes during discovery
- Timeout errors

**Fix Needed**:
```python
# Add depth limit, timeout, or async scanning
MAX_DISCOVERY_DEPTH = 2
MAX_SCAN_TIME = 5.0  # seconds
```

### 5. **Case Sensitivity in Workspace IDs**

**Issue**: Workspace IDs derived from directory names use `.lower()`, but filesystems may be case-sensitive.

**Current State**:
```python
workspace_id = path.name.lower().replace(" ", "-")
```

**Impact**:
- On case-sensitive FS (Linux), `MyApp` and `myapp` are different
- But IDs would collide: both become `myapp`
- Could cause registry conflicts

**Fix Needed**:
- Use actual path for uniqueness, not just ID
- Or preserve case and normalize differently

### 6. **Concurrent Discovery Operations**

**Issue**: Multiple `discover_workspaces()` calls could run simultaneously, causing duplicate work.

**Current State**:
- No debouncing or locking
- Each API call creates new `WorkspaceManager()` instance
- No caching

**Impact**:
- Wasted CPU/IO
- Race conditions in registry access

**Fix Needed**:
```python
# Add discovery cache with TTL
# Or use singleton pattern for WorkspaceManager
```

## 🟡 Important Edge Cases

### 7. **Path Length Limits**

**Issue**: Very long paths (>260 chars on Windows, >4096 on Linux) could cause issues.

**Current State**:
- No validation of path length
- Could fail silently in some operations

**Impact**:
- Errors when saving/loading workspace state
- UI truncation issues

**Fix Needed**:
```python
MAX_PATH_LENGTH = 260 if sys.platform == 'win32' else 4096
if len(str(path)) > MAX_PATH_LENGTH:
    raise ValueError(f"Path too long: {len(str(path))} > {MAX_PATH_LENGTH}")
```

### 8. **Unicode/Special Characters in Paths**

**Issue**: Paths with emoji, non-ASCII, or special characters might cause issues.

**Current State**:
- No explicit handling
- Relies on Python's Path handling (usually fine)
- But ID generation could create invalid IDs

**Impact**:
- Invalid workspace IDs
- JSON serialization issues
- URL encoding problems in API

**Fix Needed**:
```python
# Sanitize IDs more carefully
import unicodedata
def sanitize_id(name: str) -> str:
    # Normalize unicode, remove special chars
    normalized = unicodedata.normalize('NFKD', name)
    return re.sub(r'[^\w\-]', '', normalized.lower())
```

### 9. **Permission Errors During Discovery**

**Issue**: Scanning directories without read permission causes silent failures.

**Current State**:
```python
except (OSError, PermissionError):
    continue
```

**Impact**:
- Workspaces in protected directories won't be discovered
- No user feedback about permission issues

**Fix Needed**:
- Log permission errors
- Optionally return partial results with warnings
- Or provide user feedback about inaccessible directories

### 10. **Nested Workspaces**

**Issue**: Workspace inside another workspace (e.g., `~/projects/my-app/docs`) could be discovered as separate workspace.

**Current State**:
- Discovery scans direct children only (good)
- But if user manually adds nested workspace, could cause confusion

**Impact**:
- Confusion about which workspace is "active"
- Potential conflicts

**Fix Needed**:
- Detect nested workspaces
- Warn or prevent nesting
- Or show hierarchy in UI

### 11. **Workspace Deletion While Active**

**Issue**: If current workspace is deleted externally (file manager, CLI), state becomes stale.

**Current State**:
- `get_current()` checks `exists()` but doesn't proactively validate
- Stale state persists until next check

**Impact**:
- User thinks workspace is active but it's gone
- Errors when trying to use workspace

**Fix Needed**:
- Periodic validation of current workspace
- Auto-clear on detection of deletion
- Event system to detect filesystem changes

### 12. **Registry Corruption**

**Issue**: If `~/.sunwell/projects.json` is corrupted or invalid JSON, `ProjectRegistry` fails.

**Current State**:
```python
def _load_registry() -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        raise RegistryError(f"Failed to load registry: {e}") from e
```

**Impact**:
- WorkspaceManager can't initialize
- All workspace operations fail

**Fix Needed**:
- Graceful fallback (empty registry)
- Auto-recovery (backup + restore)
- Validation on load

### 13. **API Error Handling**

**Issue**: API endpoints don't handle all error types consistently.

**Current State**:
```python
try:
    workspace_info = manager.switch_workspace(request.workspace_id)
except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
```

**Impact**:
- Other exceptions (OSError, PermissionError) become 500 errors
- No distinction between "not found" and "permission denied"

**Fix Needed**:
```python
except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
except PermissionError as e:
    raise HTTPException(status_code=403, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail="Internal error")
```

### 14. **Frontend State Desync**

**Issue**: If workspace changes via CLI while UI is open, frontend state is stale.

**Current State**:
- No polling or event system
- Frontend only updates on explicit actions

**Impact**:
- UI shows wrong current workspace
- User confusion

**Fix Needed**:
- Poll current workspace periodically
- Or WebSocket events for workspace changes
- Or timestamp-based cache invalidation

### 15. **Empty Workspace List**

**Issue**: If no workspaces are discovered, UI might be confusing.

**Current State**:
- Components handle empty lists
- But no guidance on what to do

**Impact**:
- User doesn't know how to create first workspace

**Fix Needed**:
- Better empty states with CTAs
- "Create workspace" button
- Link to project init docs

## 🟢 Minor Edge Cases

### 16. **Workspace Name Collisions**

**Issue**: Multiple workspaces with same name but different paths could be confusing.

**Current State**:
- IDs are unique (include path in some cases)
- But display names could collide

**Impact**:
- UI confusion
- Hard to distinguish workspaces

**Fix Needed**:
- Show path in UI when names collide
- Or include path in name

### 17. **Last Used Timestamp Format**

**Issue**: `last_used` is ISO string, but timezone handling unclear.

**Current State**:
```python
last_used = datetime.now().isoformat()
```

**Impact**:
- Timezone confusion
- Sorting might be wrong across timezones

**Fix Needed**:
- Use UTC timestamps
- Or include timezone info

### 18. **Workspace Type Consistency**

**Issue**: `workspace_type` values are strings, not enum.

**Current State**:
- Values: "manifest", "registered", "discovered"
- No validation

**Impact**:
- Typos possible
- Inconsistent values

**Fix Needed**:
- Use enum or constants
- Validate on creation

### 19. **Discovery Root Validation**

**Issue**: `discover_workspaces(root)` doesn't validate root is a directory.

**Current State**:
```python
scan_root = Path(root).resolve() if root else None
```

**Impact**:
- Could pass file path
- Error occurs later, confusing

**Fix Needed**:
```python
if root and not Path(root).is_dir():
    raise ValueError(f"Root must be a directory: {root}")
```

### 20. **Workspace Info Caching**

**Issue**: `WorkspaceInfo` objects are created fresh each time, no caching.

**Current State**:
- Every API call recreates all `WorkspaceInfo` objects
- Expensive for large workspace lists

**Impact**:
- Performance issues
- Wasted CPU

**Fix Needed**:
- Cache `WorkspaceInfo` objects
- Invalidate on workspace changes
- TTL-based expiration

## 📋 Priority Fixes

### High Priority (Fix Before Release)
1. ✅ Race conditions in workspace switching (file locking)
2. ✅ Current workspace invalidation handling
3. ✅ API error handling (catch all exception types)
4. ✅ Discovery performance (timeout/depth limits)

### Medium Priority (Fix Soon)
5. ✅ Symlink resolution consistency
6. ✅ Case sensitivity in IDs
7. ✅ Frontend state desync (polling/events)
8. ✅ Registry corruption handling

### Low Priority (Nice to Have)
9. ✅ Unicode/special character handling
10. ✅ Nested workspace detection
11. ✅ Empty state improvements
12. ✅ Workspace info caching

## Summary

**Total Issues Found**: 20
- 🔴 Critical: 6
- 🟡 Important: 9  
- 🟢 Minor: 5

**Recommendation**: Fix high-priority items before release, address medium-priority in next iteration, low-priority as needed.
