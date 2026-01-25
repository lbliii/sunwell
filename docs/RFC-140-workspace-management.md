# RFC-140: Workspace Management & UX Improvements

## Status

**Status**: Implemented  
**Date**: 2026-01-25  
**Authors**: AI Assistant

## Problem Statement

The current workspace/project system has gaps in management, visibility, and switching capabilities:

**Current State:**
- Project registry exists (`ProjectRegistry`) but limited to registered projects
- Workspace resolution exists but no unified management layer
- CLI has `sunwell project` commands but missing workspace-level operations
- UI has `ProjectManager` but no workspace switcher or discovery
- No way to see "current" workspace or switch between workspaces quickly

**Gaps Identified:**
1. No workspace discovery (can't scan for existing workspaces)
2. No workspace switching (can set default but can't switch context)
3. Limited visibility (only see registered projects, not all workspaces)
4. No current workspace indicator (unclear what's active)
5. No unified workspace/project view (projects vs workspaces are separate)

## Goals

1. **Discovery**: Scan filesystem for existing workspaces/projects
2. **Switching**: Quick workspace context switching (CLI + UI)
3. **Visibility**: Unified view of registered projects + discovered workspaces
4. **Current State**: Clear indication of active workspace
5. **Management**: Full CRUD operations for workspaces

## Solution

### Backend

**New Module: `src/sunwell/knowledge/workspace/manager.py`**

`WorkspaceManager` class provides:
- `discover_workspaces()` - Scan filesystem for workspaces
- `get_current()` - Get current workspace
- `switch_workspace()` - Switch workspace context
- `get_status()` - Check workspace health
- `register_discovered()` - Register discovered workspace

**Current Workspace Tracking:**
- Stored in `~/.sunwell/current_workspace.json`
- Updated on workspace switch
- Used for default resolution when no explicit workspace specified

### CLI Commands

**New `sunwell workspace` commands:**
- `sunwell workspace list` - List all workspaces (registered + discovered)
- `sunwell workspace current` - Show current workspace
- `sunwell workspace switch <id>` - Switch to workspace
- `sunwell workspace discover` - Scan filesystem for workspaces
- `sunwell workspace status` - Show workspace health/status
- `sunwell workspace info <id>` - Detailed workspace info

**Enhanced `sunwell project` commands:**
- `sunwell project switch <id>` - Alias for workspace switch
- `sunwell project current` - Show current project/workspace

### API Endpoints

**New endpoints in `/api/workspace/`:**
- `GET /api/workspace/list` - List all workspaces
- `GET /api/workspace/current` - Get current workspace
- `POST /api/workspace/switch` - Switch workspace context
- `POST /api/workspace/discover` - Trigger discovery scan
- `GET /api/workspace/status?path=<path>` - Get workspace status
- `GET /api/workspace/info?path=<path>` - Detailed workspace info

**Enhanced `/api/project/` endpoints:**
- `GET /api/project/current` - Get current project
- `POST /api/project/switch` - Switch project context

### UI Components

**New Svelte Components:**

1. **`WorkspaceSwitcher.svelte`**
   - Dropdown/popover for quick workspace switching
   - Shows current workspace with indicator
   - Lists recent workspaces
   - Search/filter capability
   - Keyboard shortcuts (Cmd+K to open)

2. **`WorkspaceDiscovery.svelte`**
   - Full-page discovery interface
   - Shows discovered vs registered workspaces
   - Bulk registration actions
   - Filter by type, location, status

3. **`WorkspaceStatusBadge.svelte`**
   - Small badge showing current workspace
   - Click to open switcher
   - Shows workspace health indicator

4. **`WorkspaceList.svelte`**
   - Unified list of registered + discovered workspaces
   - Grouped by status (registered, discovered, invalid)
   - Actions: switch, register, remove

5. **`CurrentWorkspaceIndicator.svelte`**
   - Header component showing current workspace
   - Breadcrumb-style navigation
   - Quick actions menu

**Enhanced Components:**

1. **`ProjectManager.svelte`**
   - Added workspace discovery view
   - Shows workspace status alongside project info
   - "Discover Workspaces" button

2. **`ProjectHeader.svelte`**
   - Integrated workspace switcher badge
   - Shows workspace context

### Stores

**New Store: `studio/src/stores/workspaceManager.svelte.ts`**
- Unified workspace management state
- Combines project registry + discovery
- Manages current workspace context

**Enhanced Store: `studio/src/stores/workspace.svelte.ts`**
- Added `currentWorkspace` state
- Added `discoveredWorkspaces` state
- Added `switchWorkspace()` action
- Added `discoverWorkspaces()` action
- Added `getCurrentWorkspace()` action

## Implementation Details

### Workspace Discovery Logic

Scans common locations:
- `~/Sunwell/projects/`
- `~/Projects/`
- `~/Code/`
- `~/workspace/`
- `~/workspaces/`

Looks for project markers:
- `.sunwell/project.toml` (explicit Sunwell project)
- `pyproject.toml` (Python)
- `package.json` (Node)
- `Cargo.toml` (Rust)
- `go.mod` (Go)
- `.git/` (Git repository)
- `setup.py` (Legacy Python)
- `Makefile` (C/C++ or general)

Merges with registered projects and deduplicates by path.

### Current Workspace Tracking

Stored in `~/.sunwell/current_workspace.json`:
```json
{
  "workspace_id": "my-app",
  "workspace_path": "/path/to/workspace",
  "switched_at": "2026-01-25T12:00:00"
}
```

Used for:
- Default workspace resolution
- Persisting workspace context across sessions
- Quick workspace switching

## Usage Examples

### CLI

```bash
# List all workspaces
sunwell workspace list

# Show current workspace
sunwell workspace current

# Switch workspace
sunwell workspace switch my-app

# Discover workspaces
sunwell workspace discover

# Check workspace status
sunwell workspace status /path/to/workspace

# Get workspace info
sunwell workspace info my-app
```

### UI

1. **Quick Switch**: Click workspace badge in header → Select workspace
2. **Keyboard Shortcut**: Press `Cmd+K` → Workspace switcher opens
3. **Discovery**: Go to Projects → Click "Discover Workspaces"
4. **Status**: Workspace badge shows health indicator (✓/✗/?)

## Files Created/Modified

### Backend
- `src/sunwell/knowledge/workspace/manager.py` (new)
- `src/sunwell/interface/server/routes/workspace.py` (new)
- `src/sunwell/interface/server/routes/project.py` (enhanced)
- `src/sunwell/interface/server/routes/__init__.py` (enhanced)
- `src/sunwell/interface/server/main.py` (enhanced)
- `src/sunwell/knowledge/workspace/__init__.py` (enhanced)
- `src/sunwell/interface/cli/commands/workspace_cmd.py` (enhanced)
- `src/sunwell/interface/cli/commands/project_cmd.py` (enhanced)

### Frontend
- `studio/src/components/workspace/WorkspaceSwitcher.svelte` (new)
- `studio/src/components/workspace/WorkspaceDiscovery.svelte` (new)
- `studio/src/components/workspace/CurrentWorkspaceIndicator.svelte` (new)
- `studio/src/components/workspace/WorkspaceList.svelte` (new)
- `studio/src/components/workspace/WorkspaceStatusBadge.svelte` (new)
- `studio/src/components/workspace/index.ts` (enhanced)
- `studio/src/stores/workspaceManager.svelte.ts` (new)
- `studio/src/stores/workspace.svelte.ts` (enhanced)
- `studio/src/stores/index.ts` (enhanced)
- `studio/src/components/ProjectManager.svelte` (enhanced)
- `studio/src/components/project/ProjectHeader.svelte` (enhanced)

### Tests
- `tests/knowledge/test_workspace_manager.py` (new)

## Success Criteria

✅ Users can discover existing workspaces via CLI and UI  
✅ Users can switch workspaces quickly (CLI + UI)  
✅ Current workspace is always visible  
✅ Unified view of registered + discovered workspaces  
✅ Workspace status/health is visible  
✅ Keyboard shortcuts for quick switching (Cmd+K)

## Future Enhancements

1. Workspace favorites/pinned workspaces
2. Integration with VS Code workspace files
3. Automatic discovery on startup
4. Workspace templates
5. Workspace sharing/collaboration

## References

- RFC-117: Project-centric workspace isolation
- RFC-132: Project gate validation
- RFC-103: Workspace detection and linking
