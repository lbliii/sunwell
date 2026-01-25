/**
 * Workspace Manager Store — Unified workspace management (RFC-140)
 *
 * Manages workspace discovery, switching, and current workspace state.
 * Combines project registry + discovery for unified workspace view.
 */

import { apiGet, apiPost } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface WorkspaceInfo {
  readonly id: string;
  readonly name: string;
  readonly path: string;
  readonly isRegistered: boolean;
  readonly isCurrent: boolean;
  readonly status: 'valid' | 'invalid' | 'not_found' | 'unregistered';
  readonly workspaceType: string;
  readonly lastUsed: string | null;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _workspaces = $state<WorkspaceInfo[]>([]);
let _current = $state<WorkspaceInfo | null>(null);
let _isLoading = $state(false);
let _error = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const workspaceManager = {
  get workspaces() {
    return _workspaces;
  },
  get current() {
    return _current;
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
