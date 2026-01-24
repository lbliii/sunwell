/**
 * Lineage store — Artifact lineage and provenance tracking (RFC-121)
 *
 * Provides reactive state for:
 * - File lineage (creation, edits, attribution)
 * - Dependency graphs
 * - Impact analysis
 * - Lineage statistics
 */

import { api } from '$lib/api';

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────

export interface ArtifactEdit {
  edit_id: string;
  artifact_id: string;
  goal_id: string | null;
  task_id: string | null;
  lines_added: number;
  lines_removed: number;
  edit_type: 'create' | 'modify' | 'rename' | 'delete';
  source: 'sunwell' | 'human' | 'external';
  model: string | null;
  timestamp: string;
  session_id: string | null;
  commit_hash: string | null;
  content_hash: string | null;
}

export interface ArtifactLineage {
  artifact_id: string;
  path: string;
  content_hash: string;
  created_by_goal: string | null;
  created_by_task: string | null;
  created_at: string;
  created_reason: string;
  model: string | null;
  human_edited: boolean;
  edits: ArtifactEdit[];
  imports: string[];
  imported_by: string[];
  deleted_at: string | null;
}

export interface LineageStats {
  tracked_files: number;
  deleted_files: number;
  total_edits: number;
  sunwell_edits: number;
  human_edits: number;
  human_edited_files: number;
  dependency_edges: number;
}

export interface ImpactAnalysis {
  path: string;
  affected_files: string[];
  affected_goals: string[];
  max_depth: number;
}

export interface DependencyNode {
  id: string;
  artifact_id: string;
  human_edited: boolean;
  edit_count: number;
  created_by_goal: string | null;
  model: string | null;
}

export interface DependencyEdge {
  source: string;
  target: string;
  type: 'imports';
}

export interface DependencyGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  node_count: number;
  edge_count: number;
}

export interface UntrackedChange {
  path: string;
  artifact_id: string;
  last_known_hash: string;
  current_hash: string;
}

interface LineageState {
  // Current file lineage
  currentLineage: ArtifactLineage | null;
  currentPath: string | null;

  // Goal artifacts
  goalArtifacts: ArtifactLineage[];
  currentGoalId: string | null;

  // Dependency view
  dependencies: {
    path: string;
    imports: string[];
    imported_by: string[];
  } | null;

  // Impact analysis
  impact: ImpactAnalysis | null;

  // Full graph for visualization
  graph: DependencyGraph | null;

  // Statistics
  stats: LineageStats | null;

  // Untracked changes
  untracked: UntrackedChange[];

  // Loading states
  loading: boolean;
  error: string | null;
}

// ─────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────

let state = $state<LineageState>({
  currentLineage: null,
  currentPath: null,
  goalArtifacts: [],
  currentGoalId: null,
  dependencies: null,
  impact: null,
  graph: null,
  stats: null,
  untracked: [],
  loading: false,
  error: null,
});

// ─────────────────────────────────────────────────────────────────
// Derived
// ─────────────────────────────────────────────────────────────────

export const lineageState = {
  get currentLineage() { return state.currentLineage; },
  get currentPath() { return state.currentPath; },
  get goalArtifacts() { return state.goalArtifacts; },
  get currentGoalId() { return state.currentGoalId; },
  get dependencies() { return state.dependencies; },
  get impact() { return state.impact; },
  get graph() { return state.graph; },
  get stats() { return state.stats; },
  get untracked() { return state.untracked; },
  get loading() { return state.loading; },
  get error() { return state.error; },
};

// ─────────────────────────────────────────────────────────────────
// Actions
// ─────────────────────────────────────────────────────────────────

/**
 * Load lineage for a specific file.
 */
export async function loadFileLineage(path: string, workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<ArtifactLineage | { error: string }>(
      `/api/lineage/${encodeURIComponent(path)}?${params}`
    );

    if ('error' in response) {
      state.currentLineage = null;
      state.error = response.error;
    } else {
      state.currentLineage = response;
      state.currentPath = path;
    }
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to load lineage';
  } finally {
    state.loading = false;
  }
}

/**
 * Load all artifacts for a goal.
 */
export async function loadGoalArtifacts(goalId: string, workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<{ goal_id: string; artifacts: ArtifactLineage[]; count: number }>(
      `/api/lineage/goal/${encodeURIComponent(goalId)}?${params}`
    );

    state.goalArtifacts = response.artifacts;
    state.currentGoalId = goalId;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to load goal artifacts';
  } finally {
    state.loading = false;
  }
}

/**
 * Load dependencies for a file.
 */
export async function loadDependencies(path: string, workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<{ path: string; imports: string[]; imported_by: string[] }>(
      `/api/lineage/deps/${encodeURIComponent(path)}?${params}`
    );

    state.dependencies = response;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to load dependencies';
  } finally {
    state.loading = false;
  }
}

/**
 * Analyze impact of modifying/deleting a file.
 */
export async function analyzeImpact(path: string, workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<ImpactAnalysis>(
      `/api/lineage/impact/${encodeURIComponent(path)}?${params}`
    );

    state.impact = response;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to analyze impact';
  } finally {
    state.loading = false;
  }
}

/**
 * Load full dependency graph for visualization.
 */
export async function loadGraph(workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<DependencyGraph>(`/api/lineage/graph?${params}`);
    state.graph = response;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to load graph';
  } finally {
    state.loading = false;
  }
}

/**
 * Load lineage statistics.
 */
export async function loadStats(workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<LineageStats>(`/api/lineage/stats?${params}`);
    state.stats = response;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to load stats';
  } finally {
    state.loading = false;
  }
}

/**
 * Detect untracked changes.
 */
export async function detectUntracked(workspace?: string): Promise<void> {
  state.loading = true;
  state.error = null;

  try {
    const params = new URLSearchParams();
    if (workspace) params.set('workspace', workspace);

    const response = await api.get<{ untracked: UntrackedChange[]; count: number }>(
      `/api/lineage/sync?${params}`
    );

    state.untracked = response.untracked;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to detect changes';
  } finally {
    state.loading = false;
  }
}

/**
 * Sync untracked changes.
 */
export async function syncUntracked(workspace?: string, markAsHuman = true): Promise<string[]> {
  state.loading = true;
  state.error = null;

  try {
    const response = await api.post<{ synced: string[]; count: number }>(
      '/api/lineage/sync',
      { workspace, mark_as_human: markAsHuman }
    );

    state.untracked = [];
    return response.synced;
  } catch (e) {
    state.error = e instanceof Error ? e.message : 'Failed to sync changes';
    return [];
  } finally {
    state.loading = false;
  }
}

/**
 * Clear current lineage view.
 */
export function clearLineage(): void {
  state.currentLineage = null;
  state.currentPath = null;
}

/**
 * Clear goal artifacts view.
 */
export function clearGoalArtifacts(): void {
  state.goalArtifacts = [];
  state.currentGoalId = null;
}

/**
 * Clear all state.
 */
export function resetLineage(): void {
  state.currentLineage = null;
  state.currentPath = null;
  state.goalArtifacts = [];
  state.currentGoalId = null;
  state.dependencies = null;
  state.impact = null;
  state.graph = null;
  state.stats = null;
  state.untracked = [];
  state.loading = false;
  state.error = null;
}

/**
 * Clear error.
 */
export function clearError(): void {
  state.error = null;
}

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

/**
 * Get edit source icon.
 */
export function getSourceIcon(source: ArtifactEdit['source']): string {
  switch (source) {
    case 'sunwell': return '🤖';
    case 'human': return '👤';
    case 'external': return '❓';
  }
}

/**
 * Get edit type label.
 */
export function getEditTypeLabel(type: ArtifactEdit['edit_type']): string {
  switch (type) {
    case 'create': return 'Created';
    case 'modify': return 'Modified';
    case 'rename': return 'Renamed';
    case 'delete': return 'Deleted';
  }
}

/**
 * Format timestamp.
 */
export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Get file extension from path.
 */
export function getFileExtension(path: string): string {
  const parts = path.split('.');
  return parts.length > 1 ? parts[parts.length - 1] : '';
}

/**
 * Get language icon from file extension.
 */
export function getLanguageIcon(path: string): string {
  const ext = getFileExtension(path).toLowerCase();
  switch (ext) {
    case 'py': return '🐍';
    case 'ts':
    case 'tsx': return '💠';
    case 'js':
    case 'jsx': return '🟨';
    case 'go': return '🐹';
    case 'rs': return '🦀';
    case 'md': return '📝';
    case 'json': return '📋';
    case 'yaml':
    case 'yml': return '⚙️';
    default: return '📄';
  }
}
