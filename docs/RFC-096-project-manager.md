# RFC-096: Project Manager — Scalable Project Lifecycle Control

**Status**: Implemented  
**Author**: AI Assistant  
**Created**: 2026-01-23  
**Target Version**: v1.x  
**Confidence**: 91% 🟢  
**Related**: RFC-080 (Unified Home Surface), RFC-070 (Lens Library)

---

## Executive Summary

Project management on the Home page regressed from full CRUD controls (`RecentProjects.svelte`) to a simplified read-only block (`ProjectsBlock.svelte`). This RFC proposes a scalable `ProjectManager` component—modeled after `LensLibrary`—that provides:

1. **List view** with filtering, sorting, and search
2. **Detail view** with project info, history, and stats
3. **Full CRUD** — Open, Resume, Iterate, Archive, Delete, Bulk operations
4. **Multiple access points** — Inline on Home, Modal, Dedicated route

**Key insight**: Projects are first-class entities that grow over time. A block-style widget doesn't scale; we need a manager pattern.

---

## Goals and Non-Goals

### Goals

1. **Restore all management actions** — Iterate, Archive, Delete accessible from Home
2. **Scale to 100+ projects** — Filtering, search, pagination
3. **Unified state management** — Single store pattern like `lensLibrary.svelte.ts`
4. **Multiple integration points** — Home (inline/modal), dedicated `/projects` route
5. **Keyboard accessible** — Full ARIA support, vim-style navigation (j/k)

### Non-Goals

1. **Project editing** — Opening a project goes to Project.svelte route
2. **Collaborative features** — Single-user for now
3. **Cloud sync** — Local filesystem only (~/Sunwell/projects)
4. **AI-driven project suggestions** — Future enhancement

---

## Motivation

### Problem Statement

The Home page uses `ProjectsBlock` which only surfaces two actions:

| Action | `ProjectsBlock` | `RecentProjects` | Needed |
|--------|-----------------|------------------|--------|
| Open | ✅ | ✅ | ✅ |
| Resume | ✅ (interrupted only) | ✅ | ✅ |
| Iterate | ❌ | ✅ | ✅ |
| Archive | ❌ (handler exists, no UI) | ✅ | ✅ |
| Delete | ❌ | ✅ | ✅ |
| Filter | ❌ | ❌ | ✅ |
| Search | ❌ | ❌ | ✅ |
| Bulk ops | ❌ | ❌ | ✅ |

**Evidence**: `ProjectsBlock.svelte:42-44` defines `handleArchive()` but no button calls it.

### Why `RecentProjects` Isn't Enough

`RecentProjects.svelte` has the controls but lacks:

1. **Filtering** — Can't filter by status (interrupted/complete/failed)
2. **Sorting** — Hardcoded to "most recent"
3. **Search** — No search by name or goal
4. **Bulk operations** — No multi-select archive/delete
5. **Detail view** — No way to see project stats without opening
6. **Scalability** — Linear list doesn't work at 50+ projects

### LensLibrary Pattern

`LensLibrary.svelte` demonstrates the right pattern:

```typescript
// stores/lensLibrary.svelte.ts
interface LensLibraryState {
  entries: LensLibraryEntry[];
  selectedLens: LensLibraryEntry | null;
  lensDetail: LensDetail | null;
  versions: LensVersionInfo[];
  filter: { domain: string | null; type: 'all' | 'builtin' | 'custom'; search: string };
  view: 'library' | 'detail' | 'editor' | 'versions';
  loading: boolean;
  error: string | null;
}
```

This enables:
- View state management (list → detail → editor)
- Filtering and search
- Loading/error states
- Separation of list data vs detail data

---

## Proposal

### Component Architecture

```
src/
├── components/
│   ├── ProjectManager.svelte          # Main orchestrator component
│   ├── project-manager/
│   │   ├── index.ts                   # Exports
│   │   ├── ProjectList.svelte         # List view with filters
│   │   ├── ProjectCard.svelte         # Individual project card
│   │   ├── ProjectDetail.svelte       # Detail panel (right side or modal)
│   │   ├── ProjectFilters.svelte      # Filter bar (status, date, search)
│   │   ├── ProjectBulkActions.svelte  # Bulk action toolbar
│   │   └── ProjectStats.svelte        # Summary statistics
│   └── blocks/
│       └── ProjectsBlock.svelte       # Keep for AI-routed quick view
├── stores/
│   └── projectManager.svelte.ts       # Dedicated state management
└── routes/
    └── Projects.svelte                # Dedicated route (optional)
```

### State Management

```typescript
// stores/projectManager.svelte.ts

export type ProjectView = 'list' | 'detail';
export type ProjectSort = 'recent' | 'name' | 'status' | 'progress';
export type ProjectFilter = 'all' | 'active' | 'interrupted' | 'complete' | 'failed';

interface ProjectManagerState {
  // Data
  projects: ProjectStatus[];
  selectedProject: ProjectStatus | null;
  selectedPaths: string[];  // For bulk operations (array for JSON serialization)
  
  // Filtering & Sorting
  filter: ProjectFilter;
  sort: ProjectSort;
  sortDirection: 'asc' | 'desc';
  search: string;
  
  // UI State
  view: ProjectView;
  loading: boolean;
  error: string | null;
  
  // Pagination (for 100+ projects)
  page: number;
  pageSize: number;
  totalCount: number;
}

// Derived state
export function getFilteredProjects(): ProjectStatus[] {
  let result = _state.projects;
  
  // Apply status filter
  if (_state.filter !== 'all') {
    result = result.filter(p => {
      if (_state.filter === 'active') return !p.status || p.status === 'running';
      return p.status === _state.filter;
    });
  }
  
  // Apply search
  if (_state.search) {
    const q = _state.search.toLowerCase();
    result = result.filter(p => 
      p.name.toLowerCase().includes(q) ||
      p.last_goal?.toLowerCase().includes(q)
    );
  }
  
  // Apply sort
  result = [...result].sort((a, b) => {
    const dir = _state.sortDirection === 'asc' ? 1 : -1;
    switch (_state.sort) {
      case 'name': return dir * a.name.localeCompare(b.name);
      case 'status': return dir * (a.status ?? '').localeCompare(b.status ?? '');
      case 'progress': {
        const aP = (a.tasks_completed ?? 0) / (a.tasks_total ?? 1);
        const bP = (b.tasks_completed ?? 0) / (b.tasks_total ?? 1);
        return dir * (aP - bP);
      }
      default: // recent
        return dir * (new Date(b.last_activity ?? 0).getTime() - 
                      new Date(a.last_activity ?? 0).getTime());
    }
  });
  
  return result;
}

// Actions
export async function loadProjects(): Promise<void>;
export async function selectProject(project: ProjectStatus): Promise<void>;
export function toggleSelection(projectPath: string): void;  // O(1) via Set internally, synced to array
export function selectAll(): void;
export function clearSelection(): void;
export function isSelected(projectPath: string): boolean;  // Fast lookup

// CRUD
export async function openProject(path: string): Promise<void>;
export async function resumeProject(path: string): Promise<void>;
export async function iterateProject(path: string): Promise<{ success: boolean; new_path?: string }>;
export async function archiveProject(path: string): Promise<void>;
export async function deleteProject(path: string): Promise<void>;

// Bulk operations
export async function archiveSelected(): Promise<void>;
export async function deleteSelected(): Promise<void>;

// Filter/Sort
export function setFilter(filter: ProjectFilter): void;
export function setSort(sort: ProjectSort): void;
export function toggleSortDirection(): void;
export function setSearch(query: string): void;

// View
export function showDetail(project: ProjectStatus): void;
export function backToList(): void;
```

### ProjectManager Component

```svelte
<!-- ProjectManager.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fly, fade } from 'svelte/transition';
  import {
    projectManager,
    getFilteredProjects,
    loadProjects,
    selectProject,
    setFilter,
    setSort,
    setSearch,
    backToList,
    archiveSelected,
    deleteSelected,
  } from '../stores/projectManager.svelte';
  import ProjectList from './project-manager/ProjectList.svelte';
  import ProjectDetail from './project-manager/ProjectDetail.svelte';
  import ProjectFilters from './project-manager/ProjectFilters.svelte';
  import ProjectBulkActions from './project-manager/ProjectBulkActions.svelte';
  import ProjectStats from './project-manager/ProjectStats.svelte';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  
  interface Props {
    mode?: 'inline' | 'modal' | 'page';
    onClose?: () => void;
    onOpenProject?: (path: string) => void;
  }
  
  let { mode = 'inline', onClose, onOpenProject }: Props = $props();
  
  // Confirmation modal
  let confirmModal = $state<{
    show: boolean;
    title: string;
    message: string;
    action: () => Promise<void>;
    destructive: boolean;
  }>({ show: false, title: '', message: '', action: async () => {}, destructive: false });
  
  // Accessibility: announce filter results
  let announceMessage = $state('');
  $effect(() => {
    const count = getFilteredProjects().length;
    const total = projectManager.projects.length;
    announceMessage = count === total 
      ? `${count} projects` 
      : `${count} of ${total} projects shown`;
  });
  
  onMount(() => {
    if (projectManager.projects.length === 0) {
      loadProjects();
    }
  });
  
  function handleConfirm() {
    confirmModal.action();
    confirmModal = { ...confirmModal, show: false };
  }
</script>

<div class="project-manager" class:modal-mode={mode === 'modal'} class:page-mode={mode === 'page'}>
  <!-- Screen reader announcements -->
  <div class="sr-only" aria-live="polite" aria-atomic="true">{announceMessage}</div>
  
  <header class="manager-header">
    <div class="header-left">
      {#if projectManager.view === 'detail'}
        <Button variant="ghost" size="sm" onclick={backToList}>← Back</Button>
      {/if}
      <h2 class="manager-title">
        {projectManager.view === 'detail' ? projectManager.selectedProject?.name : 'Projects'}
      </h2>
      {#if projectManager.view === 'list'}
        <ProjectStats />
      {/if}
    </div>
    
    <div class="header-right">
      {#if mode === 'modal' && onClose}
        <Button variant="ghost" size="sm" onclick={onClose}>✕</Button>
      {/if}
    </div>
  </header>
  
  {#if projectManager.view === 'list'}
    <div class="manager-toolbar">
      <ProjectFilters />
      {#if projectManager.selectedPaths.length > 0}
        <ProjectBulkActions 
          count={projectManager.selectedPaths.length}
          onArchive={() => showBulkConfirm('archive')}
          onDelete={() => showBulkConfirm('delete')}
        />
      {/if}
    </div>
    
    <ProjectList 
      projects={getFilteredProjects()}
      {onOpenProject}
    />
  {:else if projectManager.view === 'detail'}
    <ProjectDetail 
      project={projectManager.selectedProject}
      {onOpenProject}
    />
  {/if}
</div>

<Modal isOpen={confirmModal.show} onClose={() => confirmModal.show = false}>
  <!-- Confirmation content -->
</Modal>
```

### Visual Design

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← Back    Projects                           12 total • 3 active    │
├─────────────────────────────────────────────────────────────────────┤
│ [All ▾] [Recent ▾↓]  🔍 Search projects...     [Archive] [Delete]   │
│                                              ← aria-live region →   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ☐ ○ pirate-game                    ▸▸ Interrupted    3/8   2h ago   │
│     Build a 2D pirate adventure game                                 │
│                                                                      │
│ ☐ ✓ rest-api-demo                  ✓ Complete       12/12  1d ago   │
│     Create a REST API with authentication                            │
│                                                                      │
│ ☐ ○ data-dashboard                 -- Active        0/0    5m ago   │
│     Build a real-time analytics dashboard                            │
│                                                                      │
│ ☐ ✕ ml-pipeline                    ✕ Failed         5/10   3d ago   │
│     Set up ML training pipeline                                      │
│                                                                      │
│ ☐ ○ portfolio-site                 -- Active        2/6    1w ago   │
│     Personal portfolio website                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Legend:
☐     Checkbox for bulk selection
○/✓/✕ Status icon (active/complete/failed/interrupted)
▸▸    Interrupted indicator
3/8   Task progress
```

### Integration Points

#### 1. Home Page — Inline (Default)

Replace `ProjectsBlock` with compact `ProjectManager`:

```svelte
<!-- Home.svelte -->
{#if project.discovered.length > 0 && !homeState.response}
  <section class="contextual-blocks">
    <ProjectManager 
      mode="inline"
      onOpenProject={handleOpenProject}
    />
  </section>
{/if}
```

#### 2. Home Page — Modal (For Quick Management)

Add a "Manage Projects" button that opens full manager:

```svelte
<Button onclick={() => showProjectManager = true}>
  Manage Projects ({project.discovered.length})
</Button>

{#if showProjectManager}
  <Modal isOpen={true} onClose={() => showProjectManager = false} size="lg">
    <ProjectManager 
      mode="modal"
      onClose={() => showProjectManager = false}
      onOpenProject={handleOpenProject}
    />
  </Modal>
{/if}
```

#### 3. Dedicated Route

```svelte
<!-- routes/Projects.svelte -->
<script lang="ts">
  import { ProjectManager } from '../components';
  import { goHome, goToProject } from '../stores/app.svelte';
  import { openProject, analyzeProject } from '../stores/project.svelte';
  
  async function handleOpenProject(path: string) {
    await openProject(path);
    analyzeProject(path);
    goToProject();
  }
</script>

<div class="projects-page">
  <ProjectManager 
    mode="page"
    onOpenProject={handleOpenProject}
  />
</div>
```

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move selection down |
| `k` / `↑` | Move selection up |
| `Enter` | Open selected project |
| `Space` | Toggle checkbox |
| `a` | Select all |
| `Esc` | Clear selection / Close modal |
| `/` | Focus search |
| `d` | Delete selected (with confirm) |
| `x` | Archive selected (with confirm) |

**Implementation**:
- **Roving tabindex**: List is single tab stop; arrows move focus
- **Focus management**: `focusedIndex` tracks active item
- **Modal focus trap**: Use `focus-trap` package (consistent with `LensLibrary.svelte`)
- **Focus restoration**: On modal close, return focus to trigger button

```typescript
// Keyboard handler pattern (in ProjectList.svelte)
function handleKeydown(e: KeyboardEvent) {
  const filtered = getFilteredProjects();
  switch (e.key) {
    case 'j':
    case 'ArrowDown':
      e.preventDefault();
      focusedIndex = Math.min(focusedIndex + 1, filtered.length - 1);
      break;
    case 'k':
    case 'ArrowUp':
      e.preventDefault();
      focusedIndex = Math.max(focusedIndex - 1, 0);
      break;
    case 'Enter':
      if (filtered[focusedIndex]) onOpenProject?.(filtered[focusedIndex].path);
      break;
    case ' ':
      e.preventDefault();
      if (filtered[focusedIndex]) toggleSelection(filtered[focusedIndex].path);
      break;
  }
}
```

### Migration Path

#### Phase 1: Immediate (1-2 hours)
1. Create `projectManager.svelte.ts` store
2. Create basic `ProjectManager.svelte` with list view
3. Replace `ProjectsBlock` usage on Home with `ProjectManager`

#### Phase 2: Enhancement (2-3 hours)
1. Add filtering and sorting
2. Add search
3. Add detail view panel
4. Add bulk operations

#### Phase 3: Polish (1-2 hours)
1. Keyboard navigation (roving tabindex, vim keys)
2. Animations/transitions (stagger on mount, slide on detail)
3. Dedicated `/projects` route
4. Empty states and loading skeletons
5. Virtual scrolling if projects > 50 (`svelte-virtual-list`)

---

## Alternatives Considered

### Alternative A: Enhance ProjectsBlock

**Approach**: Add all controls directly to `ProjectsBlock.svelte`

**Pros**:
- Minimal change
- Works within existing block system

**Cons**:
- Blocks are meant to be lightweight AI-routed views
- No state management for filtering/search
- Would need to reinvent LensLibrary patterns
- Mixing concerns (block display vs full CRUD)

**Decision**: Rejected — blocks should remain lightweight

### Alternative B: Use RecentProjects Directly

**Approach**: Replace `ProjectsBlock` with `RecentProjects` on Home

**Pros**:
- Already built
- Has all CRUD actions

**Cons**:
- No filtering, sorting, search
- No bulk operations
- No detail view
- Doesn't scale past ~20 projects
- No dedicated store (state in component)

**Decision**: Viable as Phase 0, but doesn't solve scaling

### Alternative C: Projects as a Route Only

**Approach**: Keep Home simple, move all management to `/projects`

**Pros**:
- Clean separation
- Home stays minimal

**Cons**:
- Extra navigation for common actions
- Interrupts flow (Home → Projects → Home → Project)
- Other apps (Finder, VS Code) show recent items inline

**Decision**: Rejected as primary, but `/projects` route is good addition

---

## Risks & Mitigations

### Risk 1: State Synchronization

**Risk**: Two stores managing project state (`project.svelte.ts` and new `projectManager.svelte.ts`) could drift.

**Mitigation**: 
- `projectManager` uses `project.svelte.ts` actions internally (doesn't duplicate backend calls)
- Single source of truth: `project.discovered` feeds `projectManager.projects`
- On mutation (archive/delete), call `scanProjects()` to refresh both stores

```typescript
// projectManager.svelte.ts — delegates to project store
import { scanProjects, archiveProject as doArchive } from './project.svelte';

export async function archiveProject(path: string): Promise<void> {
  await doArchive(path);  // Uses existing store action
  // scanProjects() already called inside doArchive on success
  syncFromProjectStore();  // Pull fresh data
}

function syncFromProjectStore(): void {
  _state.projects = project.discovered;  // Single source
}
```

### Risk 2: Performance at Scale

**Risk**: 100+ projects with filtering/sorting could cause jank.

**Mitigation**:
- **Derived state** via `$derived` (Svelte 5) ensures reactive recomputation
- **Debounced search**: 150ms debounce on search input before filtering
- **Virtual scrolling** (Phase 3): Use `svelte-virtual-list` if list exceeds 50 items
- **Pagination**: Offset-based, 25 items per page (simple, stateless)

```typescript
// Debounced search
let searchDebounce: ReturnType<typeof setTimeout>;
export function setSearch(query: string): void {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    _state = { ..._state, search: query };
  }, 150);
}
```

### Risk 3: Accessibility Regressions

**Risk**: Keyboard navigation and screen reader support incomplete.

**Mitigation**:
- **Focus trap**: Modal mode uses `focus-trap` package (already used in LensLibrary)
- **Live regions**: Announce filter results with `aria-live="polite"`
- **Roving tabindex**: List uses single tab stop with arrow key navigation
- **Testing**: Manual a11y audit with VoiceOver before merge

### Risk 4: Complexity Creep

**Risk**: ProjectManager becomes a kitchen-sink component.

**Mitigation**:
- **Strict scope**: No project editing (that's Project.svelte route)
- **Phase gates**: Ship Phase 1 first, evaluate before Phase 2
- **Component boundaries**: Each sub-component is self-contained (<100 lines)

---

## Implementation Plan

### Files to Create

```
src/stores/projectManager.svelte.ts     # ~250 lines (includes sync, debounce)
src/components/ProjectManager.svelte    # ~180 lines (includes a11y, focus)
src/components/project-manager/
  ├── index.ts                          # ~10 lines
  ├── ProjectList.svelte                # ~120 lines (keyboard nav)
  ├── ProjectCard.svelte                # ~80 lines
  ├── ProjectDetail.svelte              # ~120 lines
  ├── ProjectFilters.svelte             # ~70 lines (debounced search)
  ├── ProjectBulkActions.svelte         # ~50 lines
  └── ProjectStats.svelte               # ~30 lines
src/routes/Projects.svelte              # ~50 lines (optional)
```

**Total**: ~900 lines new code

### Files to Modify

```
src/routes/Home.svelte                  # Replace ProjectsBlock import/usage
src/components/index.ts                 # Add ProjectManager export
src/stores/index.ts                     # Add projectManager export
```

### Testing Strategy

```yaml
unit_tests:
  - projectManager.svelte.ts filtering logic
  - projectManager.svelte.ts sorting (all 4 modes)
  - Selection toggle/clear/selectAll

integration_tests:
  - Open project from list navigates correctly
  - Bulk archive removes items from list
  - Filter + search combination works

accessibility_audit:
  - VoiceOver: list navigation announces item names
  - Keyboard-only: complete all actions without mouse
  - Focus trap: modal mode contains focus
  - Color contrast: all text meets WCAG AA
```

### Backend Requirements

None — all project operations already exist:
- `scan_projects` → list
- `open_project` → open
- `resume_project` → resume
- `iterate_project` → iterate  
- `archive_project` → archive
- `delete_project` → delete

---

## Success Criteria

| Metric | Target |
|--------|--------|
| All CRUD actions accessible from Home | ✅ |
| Filter by status works | ✅ |
| Search by name/goal works | ✅ |
| Bulk archive/delete works | ✅ |
| Keyboard navigation works | ✅ j/k/Enter/Space |
| Works at 100+ projects | < 100ms filter |
| No regression in project opening | Same latency |
| Accessibility: VoiceOver audit | Pass |
| Accessibility: Keyboard-only complete flow | Pass |
| Focus trap in modal mode | Pass |

---

## Open Questions

1. ~~**Should detail view be a slide-out panel or modal?**~~
   - **Resolved**: Panel for page mode, modal for inline mode

2. ~~**Should we show archived projects in a separate section?**~~
   - **Resolved**: Future enhancement, not MVP

3. ~~**Should ProjectsBlock remain for AI-routed responses?**~~
   - **Resolved**: Keep both — Block for AI quick view, Manager for full control

4. **Virtualization threshold** — At what count should we enable virtual scrolling?
   - Proposed: 50 items (balances DOM size vs complexity)
   - Alternative: Always enable (simpler code path)

---

## References

- `studio/src/components/LensLibrary.svelte` — Manager pattern reference
- `studio/src/stores/lensLibrary.svelte.ts` — State management pattern
- `studio/src/components/RecentProjects.svelte` — Existing project actions
- `studio/src/components/blocks/ProjectsBlock.svelte` — Current implementation
- `studio/src/stores/project.svelte.ts` — Backend integration
