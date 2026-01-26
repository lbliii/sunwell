/**
 * Workspace Manager Store — Unified workspace management (RFC-140)
 *
 * Manages workspace discovery, switching, and current workspace state.
 * Combines project registry + discovery for unified workspace view.
 *
 * Multi-Project Architecture:
 * - WorkspaceContainer: Groups related projects (frontend + backend + shared)
 * - WorkspaceInfo: Individual project information
 * - Supports tiered indexing (L0-L3) for scalability
 */

import { apiGet, apiPost } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

/**
 * Project role hints for query routing.
 */
export type ProjectRole =
  | 'frontend'
  | 'backend'
  | 'api'
  | 'shared'
  | 'infra'
  | 'docs'
  | 'mobile'
  | 'cli'
  | 'library'
  | 'monorepo'
  | 'unknown';

/**
 * Index tier for tiered indexing.
 */
export type IndexTier = 'l0_manifest' | 'l1_signatures' | 'l2_full' | 'l3_deep';

/**
 * A project reference within a workspace.
 */
export interface WorkspaceProject {
  readonly id: string;
  readonly path: string;
  readonly role: ProjectRole;
  readonly isPrimary: boolean;
}

/**
 * A workspace container grouping related projects.
 */
export interface WorkspaceContainer {
  readonly id: string;
  readonly name: string;
  readonly projects: WorkspaceProject[];
  readonly root: string | null;
  readonly createdAt: string;
}

/**
 * Individual project/workspace info (backward compatible).
 */
export interface WorkspaceInfo {
  readonly id: string;
  readonly name: string;
  readonly path: string;
  readonly isRegistered: boolean;
  readonly isCurrent: boolean;
  readonly status: 'valid' | 'invalid' | 'not_found' | 'unregistered';
  readonly workspaceType: string;
  readonly lastUsed: string | null;
  readonly workspaceId: string | null;
  readonly role: ProjectRole;
  readonly indexTier: IndexTier;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _workspaces = $state<WorkspaceInfo[]>([]);
let _workspaceContainers = $state<WorkspaceContainer[]>([]);
let _current = $state<WorkspaceInfo | null>(null);
let _currentContainer = $state<WorkspaceContainer | null>(null);
let _isLoading = $state(false);
let _error = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const workspaceManager = {
  /** All individual projects (backward compatible) */
  get workspaces() {
    return _workspaces;
  },
  /** All workspace containers (multi-project) */
  get containers() {
    return _workspaceContainers;
  },
  /** Current project */
  get current() {
    return _current;
  },
  /** Current workspace container */
  get currentContainer() {
    return _currentContainer;
  },
  get isLoading() {
    return _isLoading;
  },
  get error() {
    return _error;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load all workspaces (registered + discovered).
 */
export async function loadWorkspaces(): Promise<void> {
  if (_isLoading) return;

  try {
    _isLoading = true;
    _error = null;

    const response = await apiGet<{
      workspaces: WorkspaceInfo[];
      current: WorkspaceInfo | null;
    }>('/api/workspace/list');

    _workspaces = response.workspaces || [];
    _current = response.current || null;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Failed to load workspaces:', e);
    // Don't throw - allow UI to show error state
  } finally {
    _isLoading = false;
  }
}

/**
 * Get current workspace.
 */
export async function getCurrentWorkspace(): Promise<WorkspaceInfo | null> {
  try {
    const current = await apiGet<WorkspaceInfo | null>('/api/workspace/current');
    _current = current;
    return current;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Failed to get current workspace:', e);
    return null;
  }
}

/**
 * Switch to a workspace.
 */
export async function switchWorkspace(workspaceId: string): Promise<void> {
  try {
    _error = null;

    const workspace = await apiPost<WorkspaceInfo>('/api/workspace/switch', {
      workspace_id: workspaceId,
    });

    // Update current
    _current = workspace;

    // Update workspace list to reflect current status
    _workspaces = _workspaces.map((w) => ({
      ...w,
      isCurrent: w.id === workspace.id,
    }));

    // Reload page or trigger workspace change event
    // For now, just update state - UI can listen and react
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Discover workspaces by scanning filesystem.
 */
export async function discoverWorkspaces(root?: string): Promise<WorkspaceInfo[]> {
  try {
    _isLoading = true;
    _error = null;

    const params = root ? `?root=${encodeURIComponent(root)}` : '';
    const response = await apiPost<{
      workspaces: WorkspaceInfo[];
      current: WorkspaceInfo | null;
    }>(`/api/workspace/discover${params}`, {});

    _workspaces = response.workspaces || [];
    _current = response.current || null;

    return _workspaces;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Failed to discover workspaces:', e);
    return [];
  } finally {
    _isLoading = false;
  }
}

// ═══════════════════════════════════════════════════════════════
// WORKSPACE CONTAINER ACTIONS (Multi-Project)
// ═══════════════════════════════════════════════════════════════

/**
 * Load all workspace containers.
 */
export async function loadContainers(): Promise<WorkspaceContainer[]> {
  try {
    _isLoading = true;
    _error = null;

    const response = await apiGet<{
      containers: WorkspaceContainer[];
      current: WorkspaceContainer | null;
    }>('/api/workspace/containers');

    _workspaceContainers = response.containers || [];
    _currentContainer = response.current || null;

    return _workspaceContainers;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Failed to load workspace containers:', e);
    return [];
  } finally {
    _isLoading = false;
  }
}

/**
 * Create a new workspace container.
 */
export async function createContainer(options: {
  id: string;
  name?: string;
  projects?: Array<{ id: string; path: string; role?: ProjectRole }>;
}): Promise<WorkspaceContainer> {
  try {
    _error = null;

    const container = await apiPost<WorkspaceContainer>('/api/workspace/containers', {
      id: options.id,
      name: options.name || options.id,
      projects: options.projects || [],
    });

    // Reload containers
    await loadContainers();

    return container;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Add a project to a workspace container.
 */
export async function addProjectToContainer(
  containerId: string,
  project: { id: string; path: string; role?: ProjectRole; isPrimary?: boolean }
): Promise<WorkspaceContainer> {
  try {
    _error = null;

    const container = await apiPost<WorkspaceContainer>(
      `/api/workspace/containers/${encodeURIComponent(containerId)}/projects`,
      project
    );

    // Update local state
    _workspaceContainers = _workspaceContainers.map((c) =>
      c.id === containerId ? container : c
    );

    return container;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Remove a project from a workspace container.
 */
export async function removeProjectFromContainer(
  containerId: string,
  projectId: string
): Promise<WorkspaceContainer> {
  try {
    _error = null;

    const container = await apiDelete<WorkspaceContainer>(
      `/api/workspace/containers/${encodeURIComponent(containerId)}/projects/${encodeURIComponent(projectId)}`
    );

    // Update local state
    _workspaceContainers = _workspaceContainers.map((c) =>
      c.id === containerId ? container : c
    );

    return container;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Switch to a workspace container.
 */
export async function switchContainer(containerId: string): Promise<void> {
  try {
    _error = null;

    const container = await apiPost<WorkspaceContainer>(
      `/api/workspace/containers/${encodeURIComponent(containerId)}/switch`,
      {}
    );

    _currentContainer = container;

    // Also set current project to primary
    if (container.projects.length > 0) {
      const primary = container.projects.find((p) => p.isPrimary) || container.projects[0];
      await switchWorkspace(primary.id);
    }
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Delete a workspace container.
 */
export async function deleteContainer(containerId: string): Promise<void> {
  try {
    _error = null;

    await apiDelete<void>(`/api/workspace/containers/${encodeURIComponent(containerId)}`);

    // Reload containers
    await loadContainers();
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Get workspace status.
 */
export async function getWorkspaceStatus(path: string): Promise<{
  status: string;
  valid: boolean;
}> {
  try {
    const response = await apiGet<{
      status: string;
      valid: boolean;
      path: string;
    }>(`/api/workspace/status?path=${encodeURIComponent(path)}`);

    return {
      status: response.status,
      valid: response.valid,
    };
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Get detailed workspace information.
 */
export async function getWorkspaceInfo(path: string): Promise<WorkspaceInfo> {
  try {
    const info = await apiGet<WorkspaceInfo>(
      `/api/workspace/info?path=${encodeURIComponent(path)}`
    );
    return info;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

// ═══════════════════════════════════════════════════════════════
// LIFECYCLE ACTIONS (RFC-141)
// ═══════════════════════════════════════════════════════════════

export type DeletionMode = 'unregister' | 'purge' | 'full';

export interface DeleteWorkspaceResult {
  status: string;
  mode: string;
  workspaceId: string;
  deletedItems: string[];
  failedItems: string[];
  runsDeleted: number;
  runsOrphaned: number;
  wasCurrent: boolean;
  error?: string;
}

export interface ActiveRunsResult {
  workspaceId: string;
  activeRuns: string[];
  hasActiveRuns: boolean;
}

export interface CleanupResult {
  dryRun: boolean;
  orphanedRuns: string[];
  invalidRegistrations: string[];
  cleanedRuns: number;
  cleanedRegistrations: number;
}

/**
 * Check for active runs in a workspace.
 */
export async function checkActiveRuns(workspaceId: string): Promise<ActiveRunsResult> {
  try {
    const result = await apiGet<ActiveRunsResult>(
      `/api/workspace/${encodeURIComponent(workspaceId)}/active-runs`
    );
    return result;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Delete (unregister, purge, or fully delete) a workspace.
 */
export async function deleteWorkspace(
  workspaceId: string,
  options: {
    mode: DeletionMode;
    confirm?: boolean;
    deleteRuns?: boolean;
    force?: boolean;
  }
): Promise<DeleteWorkspaceResult> {
  try {
    _error = null;

    const params = new URLSearchParams({
      mode: options.mode,
      confirm: String(options.confirm ?? false),
      delete_runs: String(options.deleteRuns ?? false),
      force: String(options.force ?? false),
    });

    const result = await apiDelete<DeleteWorkspaceResult>(
      `/api/workspace/${encodeURIComponent(workspaceId)}?${params}`
    );

    // Reload workspaces to reflect changes
    await loadWorkspaces();

    return result;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Rename a workspace.
 */
export async function renameWorkspace(
  workspaceId: string,
  newId: string,
  newName?: string
): Promise<WorkspaceInfo | null> {
  try {
    _error = null;

    const result = await apiPatch<{
      status: string;
      workspace: WorkspaceInfo | null;
      runsUpdated: number;
    }>(`/api/workspace/${encodeURIComponent(workspaceId)}`, {
      id: newId,
      name: newName,
    });

    // Reload workspaces to reflect changes
    await loadWorkspaces();

    return result.workspace;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Update workspace path after manual move.
 */
export async function moveWorkspace(
  workspaceId: string,
  newPath: string
): Promise<WorkspaceInfo | null> {
  try {
    _error = null;

    const result = await apiPatch<{
      status: string;
      workspace: WorkspaceInfo | null;
    }>(`/api/workspace/${encodeURIComponent(workspaceId)}`, {
      path: newPath,
    });

    // Reload workspaces to reflect changes
    await loadWorkspaces();

    return result.workspace;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Find and clean up orphaned data.
 */
export async function cleanupOrphaned(dryRun: boolean = true): Promise<CleanupResult> {
  try {
    _error = null;

    const result = await apiPost<CleanupResult>('/api/workspace/cleanup', {
      dryRun,
    });

    // Reload workspaces to reflect changes
    if (!dryRun) {
      await loadWorkspaces();
    }

    return result;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

// Helper functions for HTTP methods
async function apiDelete<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Request failed');
  }
  return response.json();
}

async function apiPatch<T>(url: string, body: object): Promise<T> {
  const response = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Request failed');
  }
  return response.json();
}
