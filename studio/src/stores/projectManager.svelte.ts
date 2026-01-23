/**
 * Project Manager Store — Scalable project lifecycle control (RFC-096)
 * 
 * Provides filtering, sorting, search, bulk operations, and view state
 * for managing projects at scale. Follows the LensLibrary pattern.
 */

import {
  project,
  scanProjects,
  openProject,
  resumeProject,
  archiveProject as doArchive,
  deleteProject as doDelete,
  iterateProject as doIterate,
  analyzeProject,
} from './project.svelte';
import type { ProjectStatus } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type ProjectView = 'list' | 'detail';
export type ProjectSort = 'recent' | 'name' | 'status' | 'progress';
export type ProjectFilter = 'all' | 'active' | 'interrupted' | 'complete' | 'failed';

interface ProjectManagerState {
  /** Currently selected project for detail view */
  selectedProject: ProjectStatus | null;
  
  /** Selected project paths for bulk operations */
  selectedPaths: Set<string>;
  
  /** Filter state */
  filter: ProjectFilter;
  sort: ProjectSort;
  sortDirection: 'asc' | 'desc';
  search: string;
  
  /** UI state */
  view: ProjectView;
  loading: boolean;
  error: string | null;
  
  /** Focused index for keyboard navigation */
  focusedIndex: number;
}

function createInitialState(): ProjectManagerState {
  return {
    selectedProject: null,
    selectedPaths: new Set(),
    filter: 'all',
    sort: 'recent',
    sortDirection: 'desc',
    search: '',
    view: 'list',
    loading: false,
    error: null,
    focusedIndex: 0,
  };
}

let _state = $state<ProjectManagerState>(createInitialState());

// Debounce timer for search
let searchDebounce: ReturnType<typeof setTimeout> | null = null;

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const projectManager = {
  get selectedProject() { return _state.selectedProject; },
  get selectedPaths() { return Array.from(_state.selectedPaths); },
  get selectedCount() { return _state.selectedPaths.size; },
  get filter() { return _state.filter; },
  get sort() { return _state.sort; },
  get sortDirection() { return _state.sortDirection; },
  get search() { return _state.search; },
  get view() { return _state.view; },
  get loading() { return _state.loading; },
  get error() { return _state.error; },
  get focusedIndex() { return _state.focusedIndex; },
  // Delegate to project store
  get projects() { return project.discovered; },
  get isScanning() { return project.isScanning; },
};

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

/**
 * Get filtered and sorted projects based on current state.
 */
export function getFilteredProjects(): ProjectStatus[] {
  let result = project.discovered;
  
  // Apply status filter
  if (_state.filter !== 'all') {
    result = result.filter(p => {
      if (_state.filter === 'active') {
        // Active means no terminal status (none or null)
        return !p.status || p.status === 'none';
      }
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
      case 'name':
        return dir * a.name.localeCompare(b.name);
      case 'status':
        return dir * (a.status ?? '').localeCompare(b.status ?? '');
      case 'progress': {
        const aP = (a.tasks_completed ?? 0) / Math.max(a.tasks_total ?? 1, 1);
        const bP = (b.tasks_completed ?? 0) / Math.max(b.tasks_total ?? 1, 1);
        return dir * (aP - bP);
      }
      default: // recent
        return dir * (
          new Date(b.last_activity ?? 0).getTime() - 
          new Date(a.last_activity ?? 0).getTime()
        );
    }
  });
  
  return result;
}

/**
 * Get statistics about current projects.
 */
export function getProjectStats(): { total: number; active: number; interrupted: number; complete: number; failed: number } {
  const projects = project.discovered;
  return {
    total: projects.length,
    active: projects.filter(p => !p.status || p.status === 'none').length,
    interrupted: projects.filter(p => p.status === 'interrupted').length,
    complete: projects.filter(p => p.status === 'complete').length,
    failed: projects.filter(p => p.status === 'failed').length,
  };
}

/**
 * Check if a project is selected for bulk operations.
 */
export function isSelected(path: string): boolean {
  return _state.selectedPaths.has(path);
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS — Data Loading
// ═══════════════════════════════════════════════════════════════

/**
 * Load/refresh projects from the filesystem.
 */
export async function loadProjects(): Promise<void> {
  if (_state.loading || project.isScanning) return;
  
  _state = { ..._state, loading: true, error: null };
  
  try {
    await scanProjects();
    _state = { ..._state, loading: false };
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      loading: false,
    };
  }
}

/**
 * Select a project and show detail view.
 */
export function selectProject(proj: ProjectStatus): void {
  _state = {
    ..._state,
    selectedProject: proj,
    view: 'detail',
  };
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS — Selection
// ═══════════════════════════════════════════════════════════════

/**
 * Toggle selection for a single project (for bulk ops).
 */
export function toggleSelection(path: string): void {
  const newSet = new Set(_state.selectedPaths);
  if (newSet.has(path)) {
    newSet.delete(path);
  } else {
    newSet.add(path);
  }
  _state = { ..._state, selectedPaths: newSet };
}

/**
 * Select all visible (filtered) projects.
 */
export function selectAll(): void {
  const filtered = getFilteredProjects();
  const newSet = new Set(filtered.map(p => p.path));
  _state = { ..._state, selectedPaths: newSet };
}

/**
 * Clear all selections.
 */
export function clearSelection(): void {
  _state = { ..._state, selectedPaths: new Set() };
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS — CRUD
// ═══════════════════════════════════════════════════════════════

/**
 * Open a project (navigate to Project route).
 */
export async function openProjectAction(path: string): Promise<boolean> {
  try {
    await openProject(path);
    analyzeProject(path);
    return true;
  } catch (e) {
    _state = { ..._state, error: e instanceof Error ? e.message : String(e) };
    return false;
  }
}

/**
 * Resume an interrupted project.
 */
export async function resumeProjectAction(path: string): Promise<boolean> {
  try {
    await openProject(path);
    analyzeProject(path);
    await resumeProject(path);
    return true;
  } catch (e) {
    _state = { ..._state, error: e instanceof Error ? e.message : String(e) };
    return false;
  }
}

/**
 * Iterate on a project (create new version from learnings).
 */
export async function iterateProjectAction(path: string): Promise<{ success: boolean; new_path?: string }> {
  _state = { ..._state, loading: true };
  try {
    const result = await doIterate(path);
    _state = { ..._state, loading: false };
    return { success: result.success, new_path: result.new_path ?? undefined };
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      loading: false,
    };
    return { success: false };
  }
}

/**
 * Archive a single project.
 */
export async function archiveProject(path: string): Promise<boolean> {
  _state = { ..._state, loading: true };
  try {
    const result = await doArchive(path);
    // Remove from selection if was selected
    if (_state.selectedPaths.has(path)) {
      const newSet = new Set(_state.selectedPaths);
      newSet.delete(path);
      _state = { ..._state, selectedPaths: newSet };
    }
    // Clear detail view if this was selected
    if (_state.selectedProject?.path === path) {
      _state = { ..._state, selectedProject: null, view: 'list' };
    }
    _state = { ..._state, loading: false };
    return result.success;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      loading: false,
    };
    return false;
  }
}

/**
 * Delete a single project.
 */
export async function deleteProject(path: string): Promise<boolean> {
  _state = { ..._state, loading: true };
  try {
    const result = await doDelete(path);
    // Remove from selection if was selected
    if (_state.selectedPaths.has(path)) {
      const newSet = new Set(_state.selectedPaths);
      newSet.delete(path);
      _state = { ..._state, selectedPaths: newSet };
    }
    // Clear detail view if this was selected
    if (_state.selectedProject?.path === path) {
      _state = { ..._state, selectedProject: null, view: 'list' };
    }
    _state = { ..._state, loading: false };
    return result.success;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      loading: false,
    };
    return false;
  }
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS — Bulk Operations
// ═══════════════════════════════════════════════════════════════

/**
 * Archive all selected projects.
 */
export async function archiveSelected(): Promise<{ success: number; failed: number }> {
  const paths = Array.from(_state.selectedPaths);
  let success = 0;
  let failed = 0;
  
  _state = { ..._state, loading: true };
  
  for (const path of paths) {
    try {
      const result = await doArchive(path);
      if (result.success) success++;
      else failed++;
    } catch {
      failed++;
    }
  }
  
  _state = { ..._state, selectedPaths: new Set(), loading: false };
  return { success, failed };
}

/**
 * Delete all selected projects.
 */
export async function deleteSelected(): Promise<{ success: number; failed: number }> {
  const paths = Array.from(_state.selectedPaths);
  let success = 0;
  let failed = 0;
  
  _state = { ..._state, loading: true };
  
  for (const path of paths) {
    try {
      const result = await doDelete(path);
      if (result.success) success++;
      else failed++;
    } catch {
      failed++;
    }
  }
  
  _state = { ..._state, selectedPaths: new Set(), loading: false };
  return { success, failed };
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS — Filter/Sort
// ═══════════════════════════════════════════════════════════════

/**
 * Set the status filter.
 */
export function setFilter(filter: ProjectFilter): void {
  _state = { ..._state, filter, focusedIndex: 0 };
}

/**
 * Set the sort field.
 */
export function setSort(sort: ProjectSort): void {
  _state = { ..._state, sort, focusedIndex: 0 };
}

/**
 * Toggle sort direction.
 */
export function toggleSortDirection(): void {
  _state = {
    ..._state,
    sortDirection: _state.sortDirection === 'asc' ? 'desc' : 'asc',
    focusedIndex: 0,
  };
}

/**
 * Set search query (debounced).
 */
export function setSearch(query: string): void {
  if (searchDebounce) clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    _state = { ..._state, search: query, focusedIndex: 0 };
  }, 150);
}

/**
 * Set search query immediately (no debounce).
 */
export function setSearchImmediate(query: string): void {
  if (searchDebounce) clearTimeout(searchDebounce);
  _state = { ..._state, search: query, focusedIndex: 0 };
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS — View/Navigation
// ═══════════════════════════════════════════════════════════════

/**
 * Show detail view for a project.
 */
export function showDetail(proj: ProjectStatus): void {
  _state = { ..._state, selectedProject: proj, view: 'detail' };
}

/**
 * Navigate back to list view.
 */
export function backToList(): void {
  _state = { ..._state, selectedProject: null, view: 'list' };
}

/**
 * Set focused index for keyboard navigation.
 */
export function setFocusedIndex(index: number): void {
  const filtered = getFilteredProjects();
  const clamped = Math.max(0, Math.min(index, filtered.length - 1));
  _state = { ..._state, focusedIndex: clamped };
}

/**
 * Move focus up.
 */
export function focusUp(): void {
  setFocusedIndex(_state.focusedIndex - 1);
}

/**
 * Move focus down.
 */
export function focusDown(): void {
  setFocusedIndex(_state.focusedIndex + 1);
}

/**
 * Clear error state.
 */
export function clearError(): void {
  _state = { ..._state, error: null };
}

/**
 * Reset manager state to initial.
 */
export function resetManager(): void {
  if (searchDebounce) clearTimeout(searchDebounce);
  _state = createInitialState();
}
