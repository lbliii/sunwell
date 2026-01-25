# RFC-132: Project Gate Architecture

**RFC Status**: Revised (Ready for Re-evaluation)  
**Author**: Architecture Team  
**Created**: 2026-01-24  
**Updated**: 2026-01-24  
**Related**: RFC-117 (Project Resolution), RFC-113 (Studio Server)  
**Phase 1 Status**: ✅ Complete (server-side fallback)

---

## Executive Summary

This RFC proposes a **Project Gate** — a validation checkpoint that ensures a valid project context exists before any agent execution. The gate runs at UI entry time (not execution time), provides graceful handling for invalid workspaces, and enables a guided project creation flow.

**The problem**: Users running Sunwell from its own repository (or other invalid workspaces) encounter a cryptic `ProjectValidationError` crash instead of a helpful resolution flow.

**The solution**: Move validation earlier, add structured error responses, and provide UI components for project selection/creation.

---

## 🎯 Goal: Zero-Friction Project Context

Every user interaction with Sunwell should have a valid project context. This RFC ensures:

| Scenario | Current (Phase 1) | After This RFC |
|----------|-------------------|----------------|
| First-time user | Auto-creates random workspace | Project creation wizard |
| User in Sunwell repo | Auto-creates, no explanation | "Choose a project" prompt |
| User with registered projects | Works (if `-p` specified) | Project picker in UI |
| No default project set | Auto-creates in default location | Prompts to select/create |

---

## 🚫 Non-Goals

This RFC does **not** address:

| Non-Goal | Rationale |
|----------|-----------|
| Multi-project workspaces | Out of scope; one project per session |
| Project templates | Future RFC; focus on basic create flow first |
| Project migration/import | Separate concern; `sunwell project init` handles this |
| Project deletion from UI | Dangerous; keep as CLI-only for now |
| Project settings/config UI | Separate RFC for full project management |

---

## 🔄 Alternatives Considered

### Alternative A: Keep Phase 1 Only (Rejected)

**Approach**: Auto-create workspace silently, show toast notification.

**Pros**:
- Already implemented
- Zero friction for quick experiments

**Cons**:
- User has no control over project location
- No visibility into existing projects
- Random workspace names (goal hash) are meaningless
- Users accumulate orphan workspaces

**Decision**: Rejected — poor UX for serious users.

### Alternative B: Extend `/project/open` Endpoint (Rejected)

**Approach**: Add validation to existing `/project/open` and handle errors there.

**Pros**:
- Fewer new endpoints
- Reuses existing code path

**Cons**:
- `/project/open` assumes path already exists
- Conflates "open existing" with "create new"
- Error handling becomes complex
- UI must handle both success and create flows

**Decision**: Rejected — muddies API semantics.

### Alternative C: Project Gate with Dedicated Endpoints (Selected) ✅

**Approach**: Separate endpoints for validate, create, list, default. UI gate component.

**Pros**:
- Clear API semantics (one job per endpoint)
- Composable (UI can call validate without create)
- Testable (each endpoint isolated)
- Leverages existing `ProjectRegistry` infrastructure

**Cons**:
- More endpoints to maintain
- UI complexity (gate component)

**Decision**: Selected — clean separation, leverages existing code.

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `default_workspace_root()` doesn't exist | Create fails | Low | Check/create parent in `create` endpoint |
| `default_workspace_root()` not writable | Create fails | Low | Return structured error, suggest alternative |
| Race condition: two tabs create same project | Duplicate project | Low | Use `mkdir` atomicity, handle `FileExistsError` |
| User creates project, closes tab before use | Orphan project | Medium | Accept as cleanup task; future: project GC |
| ProjectRegistry file corrupted | List/default fails | Low | Catch `RegistryError`, return empty list, log warning |
| Slow project list (many projects) | UI lag | Low | Paginate in future; <100 projects is fine |

### Error Handling Strategy

```python
# All endpoints return structured errors, never raise to client
class ValidationResult(BaseModel):
    valid: bool
    error_code: str | None = None      # Machine-readable
    error_message: str | None = None   # Human-readable
    suggestion: str | None = None      # Actionable next step
```

**Error codes**:
- `sunwell_repo` — User is in Sunwell source tree
- `not_found` — Path doesn't exist
- `not_writable` — Path not writable (future)
- `already_exists` — Project already initialized at path
- `registry_error` — Registry file issue
- `invalid_name` — Project name invalid (empty, too long, etc.)

---

## Current State: Phase 1 Complete, UX Gap Remains

### What We Fixed (Phase 1)

The server now catches `ProjectValidationError` and auto-creates a workspace:

```python
# AFTER (routes/agent.py:285-293) — Phase 1 fix
try:
    project = resolve_project(
        project_id=run.project_id,
        project_root=workspace_path,
    )
    workspace = project.root
except ProjectValidationError:
    # Auto-create in default location
    workspace = _create_default_workspace(run.goal, default_workspace_root())
    yield {"type": "info", "data": {"message": f"Created project workspace: {workspace}"}}
except ProjectResolutionError:
    workspace = workspace_path or Path.cwd()
```

### What's Still Missing

The fix is **reactive** (happens at execution time), not **proactive** (at UI entry time). Users don't get to:
- **Choose** where their project goes
- **See** what projects they have
- **Name** their project meaningfully

```
Current UX (after Phase 1):

User opens Studio → Enters goal → Clicks "Run"
                                       │
                                       ▼
                              Auto-creates workspace
                                       │
                                       ▼
                              User sees info toast 🤷
                              "Created project workspace: ~/Sunwell/projects/abc123"
```

### The Remaining Problem

| Scenario | Phase 1 Behavior | Desired Behavior |
|----------|------------------|------------------|
| First-time user | Auto-creates random workspace | Project creation wizard |
| User in Sunwell repo | Auto-creates, user confused | "Choose a project" prompt |
| User wants specific location | Gets default location | Project picker/creator |
| User has multiple projects | No visibility | Project selector in UI |

### Files Involved

| File | Role | Status |
|------|------|--------|
| `project/validation.py:13-75` | Blocks Sunwell repo usage | ✅ Working |
| `project/resolver.py:97` | Calls `validate_workspace()` | ✅ Working |
| `server/routes/agent.py:285-293` | Catches validation error, auto-creates | ✅ Phase 1 complete |
| `project/registry.py:47-195` | ProjectRegistry class | ✅ Has `get_default`, `set_default`, `list_projects` |
| `project/registry.py:197-265` | `init_project()` function | ✅ Ready for use |
| `server/routes/project.py` | Project API endpoints | ❌ Missing validation/create/default/list endpoints |

---

## Solution: Early Validation with Structured Errors

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NEW: PROJECT GATE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User opens Studio                                                          │
│          │                                                                   │
│          ▼                                                                   │
│   ┌──────────────────────┐                                                  │
│   │     Project Gate     │  ◀── NEW: Validates BEFORE goal input            │
│   │  (ProjectGate.svelte)│                                                  │
│   └──────────┬───────────┘                                                  │
│              │                                                               │
│      ┌───────┴───────┐                                                      │
│      │               │                                                      │
│   Valid?          Invalid/None                                              │
│      │               │                                                      │
│      ▼               ▼                                                      │
│   Continue     ┌─────────────────┐                                          │
│   to Goal      │ Project Picker  │  ◀── NEW: Select or create               │
│   Input        │ or Creator      │                                          │
│                └─────────────────┘                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component 1: Server-Side Validation Endpoint

Add explicit validation endpoint that returns structured errors:

```python
# NEW: routes/project.py

class ValidationResult(BaseModel):
    valid: bool
    error_code: str | None = None
    error_message: str | None = None
    suggestion: str | None = None


@router.post("/api/project/validate")
async def validate_project_path(request: ProjectPathRequest) -> ValidationResult:
    """Validate a workspace path before using it.
    
    Returns structured error with suggestion instead of raising.
    """
    from sunwell.project.validation import ProjectValidationError, validate_workspace
    from sunwell.workspace import default_workspace_root
    
    path = Path(request.path).expanduser().resolve()
    
    if not path.exists():
        return ValidationResult(
            valid=False,
            error_code="not_found",
            error_message=f"Path does not exist: {path}",
        )
    
    try:
        validate_workspace(path)
        return ValidationResult(valid=True)
    except ProjectValidationError as e:
        # Determine error type for structured response
        error_msg = str(e)
        
        if "sunwell" in error_msg.lower() and "repository" in error_msg.lower():
            return ValidationResult(
                valid=False,
                error_code="sunwell_repo",
                error_message="Cannot use Sunwell's own repository as project workspace",
                suggestion=str(default_workspace_root()),
            )
        
        return ValidationResult(
            valid=False,
            error_code="invalid_workspace",
            error_message=error_msg,
        )
```

### Component 2: Project List Endpoint

Add endpoint to list registered projects with validity status:

```python
# NEW: routes/project.py

class ProjectInfo(BaseModel):
    id: str
    name: str
    root: str
    valid: bool  # Whether workspace still exists and passes validation
    is_default: bool
    last_used: str | None


@router.get("/api/project/list")
async def list_projects() -> dict[str, list[ProjectInfo]]:
    """List all registered projects with validity status.
    
    Returns projects ordered by last_used descending.
    Includes validity check so UI can warn about broken projects.
    """
    from sunwell.project import ProjectRegistry
    from sunwell.project.validation import validate_workspace
    
    registry = ProjectRegistry()
    default_id = registry.default_project_id
    projects = []
    
    for project in registry.list_projects():
        # Check if still valid
        valid = True
        try:
            if not project.root.exists():
                valid = False
            else:
                validate_workspace(project.root)
        except Exception:
            valid = False
        
        projects.append(ProjectInfo(
            id=project.id,
            name=project.name,
            root=str(project.root),
            valid=valid,
            is_default=(project.id == default_id),
            last_used=project.last_used.isoformat() if project.last_used else None,
        ))
    
    # Sort by last_used descending (most recent first)
    projects.sort(key=lambda p: p.last_used or "", reverse=True)
    
    return {"projects": projects}
```

### Component 3: Project Creation Endpoint

Add endpoint to create projects in the default location:

```python
# NEW: routes/project.py

class CreateProjectRequest(BaseModel):
    name: str
    path: str | None = None  # Defaults to ~/Sunwell/projects/{name}


class CreateProjectResponse(BaseModel):
    project: dict
    path: str
    is_new: bool
    is_default: bool  # True if this became the default project


@router.post("/api/project/create")
async def create_project(request: CreateProjectRequest) -> CreateProjectResponse:
    """Create a new project in the specified or default location.
    
    If path is not provided, creates in ~/Sunwell/projects/{slugified_name}.
    Auto-sets as default if no default project exists.
    """
    import re
    from sunwell.project import ProjectRegistry, init_project
    from sunwell.workspace import default_workspace_root
    
    # Validate name
    name = request.name.strip()
    if not name:
        return {"error": "invalid_name", "message": "Project name cannot be empty"}
    if len(name) > 64:
        return {"error": "invalid_name", "message": "Project name too long (max 64 chars)"}
    if "/" in name or "\\" in name:
        return {"error": "invalid_name", "message": "Project name cannot contain path separators"}
    
    # Determine path
    if request.path:
        project_path = Path(request.path).expanduser().resolve()
    else:
        # Default location with slugified name
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-") or "project"
        project_path = default_workspace_root() / slug
    
    # Ensure parent exists
    project_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create directory
    is_new = not project_path.exists()
    project_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize project
    try:
        project = init_project(
            root=project_path,
            project_id=slug,
            name=name,
            trust="workspace",
            register=True,
        )
    except Exception as e:
        if "already initialized" in str(e).lower():
            return {"error": "already_exists", "message": str(e)}
        raise
    
    # Auto-set as default if no default exists
    registry = ProjectRegistry()
    became_default = False
    if registry.get_default() is None:
        registry.set_default(project.id)
        became_default = True
    
    return CreateProjectResponse(
        project={
            "id": project.id,
            "name": project.name,
            "root": str(project.root),
        },
        path=str(project_path),
        is_new=is_new,
        is_default=became_default,
    )
```

### Component 4: Default Project Endpoint

Add endpoint to get/set default project:

```python
# NEW: routes/project.py

@router.get("/api/project/default")
async def get_default_project() -> dict[str, Any]:
    """Get the default project (for zero-config startup).
    
    Returns project info if default is set and valid, null otherwise.
    """
    from sunwell.project import ProjectRegistry
    from sunwell.project.validation import validate_workspace
    
    registry = ProjectRegistry()
    default = registry.get_default()
    
    if not default:
        return {"project": None}
    
    # Verify default is still valid
    try:
        if not default.root.exists():
            return {"project": None, "warning": "Default project no longer exists"}
        validate_workspace(default.root)
    except Exception:
        return {"project": None, "warning": "Default project is no longer valid"}
    
    return {
        "project": {
            "id": default.id,
            "name": default.name,
            "root": str(default.root),
        }
    }


class SetDefaultRequest(BaseModel):
    project_id: str


@router.put("/api/project/default")
async def set_default_project(request: SetDefaultRequest) -> dict[str, Any]:
    """Set the default project.
    
    Validates project exists in registry before setting.
    """
    from sunwell.project import ProjectRegistry
    from sunwell.project.registry import RegistryError
    
    registry = ProjectRegistry()
    
    # Validate project exists
    project = registry.get(request.project_id)
    if not project:
        available = [p.id for p in registry.list_projects()]
        return {
            "error": "not_found",
            "message": f"Project not found: {request.project_id}",
            "available_projects": available,
        }
    
    try:
        registry.set_default(request.project_id)
    except RegistryError as e:
        return {"error": "registry_error", "message": str(e)}
    
    return {"success": True, "default_project": request.project_id}
```

### Component 5: Project Gate (Svelte)

UI component that gates the goal input behind project selection:

```svelte
<!-- NEW: studio/src/components/ProjectGate.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { apiGet, apiPost } from '$lib/socket';
  import { project, openProject } from '../stores/project.svelte';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';
  import Spinner from './ui/Spinner.svelte';
  
  // Gate state
  let isValidating = $state(true);
  let needsProject = $state(false);
  let validationError = $state<string | null>(null);
  let suggestion = $state<string | null>(null);
  
  // Project list for picker
  let projects = $state<Array<{id: string, name: string, root: string}>>([]);
  let isLoadingProjects = $state(false);
  
  // Creation state
  let showCreator = $state(false);
  let newProjectName = $state('');
  let isCreating = $state(false);
  
  onMount(async () => {
    await validateCurrentProject();
  });
  
  async function validateCurrentProject() {
    isValidating = true;
    
    try {
      // Check for default project first
      const defaultResp = await apiGet<{project: any}>('/api/project/default');
      
      if (defaultResp.project) {
        // Validate it's still valid
        const validation = await apiPost<{valid: boolean, error_code?: string, suggestion?: string}>(
          '/api/project/validate',
          { path: defaultResp.project.root }
        );
        
        if (validation.valid) {
          await openProject(defaultResp.project.root);
          needsProject = false;
          return;
        }
      }
      
      // Check current project (from URL or prior session)
      if (project.current?.path) {
        const validation = await apiPost<{valid: boolean, error_code?: string, suggestion?: string}>(
          '/api/project/validate',
          { path: project.current.path }
        );
        
        if (validation.valid) {
          needsProject = false;
          return;
        }
        
        // Current project invalid
        validationError = validation.error_code ?? null;
        suggestion = validation.suggestion ?? null;
      }
      
      // Need to select or create a project
      needsProject = true;
      await loadProjects();
      
    } finally {
      isValidating = false;
    }
  }
  
  async function loadProjects() {
    isLoadingProjects = true;
    try {
      const resp = await apiGet<{projects: any[]}>('/api/project/list');
      projects = resp.projects ?? [];
    } finally {
      isLoadingProjects = false;
    }
  }
  
  async function selectProject(proj: {id: string, root: string}) {
    await openProject(proj.root);
    needsProject = false;
  }
  
  async function createProject() {
    if (!newProjectName.trim()) return;
    
    isCreating = true;
    try {
      const resp = await apiPost<{project: any, path: string}>(
        '/api/project/create',
        { name: newProjectName }
      );
      
      await openProject(resp.path);
      showCreator = false;
      needsProject = false;
    } finally {
      isCreating = false;
    }
  }
</script>

{#if isValidating}
  <div class="gate-loading">
    <Spinner />
    <p>Checking project...</p>
  </div>
{:else if needsProject}
  <Modal title="Select Project" closable={false}>
    {#if validationError === 'sunwell_repo'}
      <div class="error-banner">
        <p>Cannot use Sunwell's source repository as workspace.</p>
        {#if suggestion}
          <p class="suggestion">Suggested location: <code>{suggestion}</code></p>
        {/if}
      </div>
    {/if}
    
    {#if projects.length > 0}
      <h3>Your Projects</h3>
      <ul class="project-list">
        {#each projects as proj}
          <li>
            <button onclick={() => selectProject(proj)}>
              <strong>{proj.name}</strong>
              <span class="path">{proj.root}</span>
            </button>
          </li>
        {/each}
      </ul>
      <hr />
    {/if}
    
    {#if showCreator}
      <div class="creator">
        <h3>Create New Project</h3>
        <input 
          type="text" 
          placeholder="Project name" 
          bind:value={newProjectName}
          onkeydown={(e) => e.key === 'Enter' && createProject()}
        />
        <p class="path-preview">
          Will create: ~/Sunwell/projects/{newProjectName.toLowerCase().replace(/[^a-z0-9]+/g, '-') || '...'}
        </p>
        <div class="actions">
          <Button onclick={() => showCreator = false} variant="ghost">Cancel</Button>
          <Button onclick={createProject} disabled={isCreating || !newProjectName.trim()}>
            {isCreating ? 'Creating...' : 'Create Project'}
          </Button>
        </div>
      </div>
    {:else}
      <Button onclick={() => showCreator = true}>
        + Create New Project
      </Button>
    {/if}
  </Modal>
{:else}
  <slot />
{/if}

<style>
  .gate-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: 1rem;
  }
  
  .error-banner {
    background: var(--color-error-bg);
    border: 1px solid var(--color-error);
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
  }
  
  .suggestion {
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }
  
  .project-list {
    list-style: none;
    padding: 0;
  }
  
  .project-list button {
    width: 100%;
    text-align: left;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    margin-bottom: 0.5rem;
    cursor: pointer;
  }
  
  .project-list button:hover {
    background: var(--color-bg-hover);
  }
  
  .path {
    display: block;
    font-size: 0.8rem;
    color: var(--color-text-muted);
  }
  
  .path-preview {
    font-size: 0.9rem;
    color: var(--color-text-muted);
  }
  
  .creator {
    padding: 1rem 0;
  }
  
  .actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
    margin-top: 1rem;
  }
</style>
```

### Component 6: App Integration

Wrap the main app with the Project Gate:

```svelte
<!-- MODIFY: studio/src/App.svelte -->
<script lang="ts">
  import ProjectGate from './components/ProjectGate.svelte';
  // ... existing imports
</script>

<ProjectGate>
  <!-- Existing app content -->
  <Router {routes} />
</ProjectGate>
```

---

## API Contract Summary

### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/project/validate` | POST | Validate workspace, return structured error |
| `/api/project/create` | POST | Create project in default location |
| `/api/project/default` | GET | Get default project |
| `/api/project/default` | PUT | Set default project |
| `/api/project/list` | GET | List all registered projects |

### Endpoint Behaviors

**`/api/project/list`**:
- Returns ALL registered projects (doesn't filter by validity)
- Includes `valid` field so UI can show warnings for broken projects
- Ordered by `last_used` descending

**`/api/project/create`**:
- Auto-sets as default if no default exists (first project wins)
- Returns `is_default: true` in response if it became default
- Validates name (non-empty, ≤64 chars, no path separators)

**`/api/project/default`** (PUT):
- Validates project exists in registry before setting
- Returns error if project_id not found

### Validation Error Codes

| Code | Meaning | UI Action |
|------|---------|-----------|
| `sunwell_repo` | User is in Sunwell's source tree | Show suggestion, prompt create |
| `not_found` | Path doesn't exist | Show error |
| `not_writable` | Path not writable | Show error |
| `already_exists` | Project already initialized | Offer to open instead |
| `invalid_name` | Name empty, too long, or invalid | Show validation message |
| `registry_error` | Registry file corrupted | Show error, suggest CLI repair |
| `invalid_workspace` | Generic validation failure | Show error |

---

## Migration Path

### Phase 1: Server-Side Fallback ✅ COMPLETE

Catch `ProjectValidationError` in `_execute_agent()` and auto-create workspace.

**Status**: ✅ Implemented at `routes/agent.py:285-293`

**Behavior**: Invalid workspace → auto-create in `~/Sunwell/projects/{goal_hash}/`

---

### Phase 2: Validation & List Endpoints

Add `/api/project/validate` and `/api/project/list` endpoints.

**Files**: `server/routes/project.py`

**Dependencies**: None (uses existing `ProjectRegistry`)

**Effort**: ~50 LOC

---

### Phase 3: Create & Default Endpoints

Add `/api/project/create` and `/api/project/default` (GET/PUT) endpoints.

**Files**: `server/routes/project.py`

**Dependencies**: Phase 2 (validate used internally by create)

**Effort**: ~80 LOC

---

### Phase 4: Project Gate Component

Add `ProjectGate.svelte` and integrate into `App.svelte`.

**Files**: 
- `studio/src/components/ProjectGate.svelte` (new)
- `studio/src/App.svelte` (modify)
- `studio/src/stores/project.svelte` (may need updates)

**Dependencies**: Phases 2-3 (all endpoints)

**Effort**: ~200 LOC Svelte

---

### Phase 5: Polish & Edge Cases

- First project auto-becomes default
- "Make default" button in project picker
- Error states for registry corruption
- Loading states in UI

**Files**: Various

**Dependencies**: Phase 4

**Effort**: ~50 LOC

---

## Testing Strategy

### Unit Tests

```python
# tests/project/test_validation_endpoint.py

async def test_validate_sunwell_repo():
    """Validation returns structured error for Sunwell repo."""
    response = await client.post("/api/project/validate", json={"path": SUNWELL_REPO})
    assert response.json()["valid"] is False
    assert response.json()["error_code"] == "sunwell_repo"
    assert response.json()["suggestion"] is not None


async def test_validate_valid_project():
    """Validation passes for normal project."""
    response = await client.post("/api/project/validate", json={"path": "/tmp/test-project"})
    assert response.json()["valid"] is True


async def test_create_project_default_location():
    """Create project uses default location when path not specified."""
    response = await client.post("/api/project/create", json={"name": "My Test App"})
    assert "my-test-app" in response.json()["path"]
    assert response.json()["is_new"] is True
```

### E2E Tests

```typescript
// studio/tests/projectGate.spec.ts

test('shows project picker when in sunwell repo', async ({ page }) => {
  // Mock /api/project/validate to return sunwell_repo error
  await page.route('/api/project/validate', route => {
    route.fulfill({
      json: { valid: false, error_code: 'sunwell_repo', suggestion: '~/Sunwell/projects' }
    });
  });
  
  await page.goto('/');
  await expect(page.getByText('Select Project')).toBeVisible();
  await expect(page.getByText('Cannot use Sunwell')).toBeVisible();
});


test('creates project and proceeds', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Create New Project').click();
  await page.getByPlaceholder('Project name').fill('My App');
  await page.getByRole('button', { name: 'Create Project' }).click();
  
  // Should proceed to main app
  await expect(page.getByText('Select Project')).not.toBeVisible();
});
```

---

## Success Criteria

| Criteria | Measurement |
|----------|-------------|
| No crashes from invalid workspace | Zero `ProjectValidationError` reaching UI |
| First-time user guided to create project | 100% of new users see creator flow |
| Existing users unaffected | Projects with valid manifests work unchanged |
| Default project works | Users with default set skip picker |

---

## Appendix: Error Message Improvements

### Before

```
❌
SW-0000
Cannot use Sunwell's own repository as project workspace. Root: /Users/llane/...
This would cause agent-generated files to pollute Sunwell's source.
Create a separate directory for your project:
  mkdir ~/projects/my-app && cd ~/projects/my-app
  sunwell project init .
```

### After

```
┌─────────────────────────────────────────┐
│          Select Project                  │
├─────────────────────────────────────────┤
│                                          │
│  ⚠️ Cannot use Sunwell's source         │
│     repository as workspace.             │
│                                          │
│  Your Projects:                          │
│  ┌─────────────────────────────────────┐│
│  │ my-app                              ││
│  │ ~/projects/my-app                   ││
│  └─────────────────────────────────────┘│
│                                          │
│  ─────────────────────────────────────  │
│                                          │
│  [ + Create New Project ]                │
│                                          │
└─────────────────────────────────────────┘
```

---

## References

- RFC-117: Project Resolution
- RFC-113: Studio Server Architecture
- `src/sunwell/project/validation.py:13-75` — Workspace validation logic
- `src/sunwell/project/registry.py:47-195` — `ProjectRegistry` class
- `src/sunwell/project/registry.py:197-265` — `init_project()` function
- `src/sunwell/project/resolver.py:18-200` — `ProjectResolver` class
- `src/sunwell/server/routes/agent.py:285-293` — Phase 1 fix (error handling)
- `src/sunwell/server/routes/project.py` — Existing project endpoints (to be extended)
