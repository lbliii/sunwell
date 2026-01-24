/**
 * Coordinator Store — Multi-agent orchestration state management (RFC-100 Phase 4)
 *
 * Manages state for the ATC (Air Traffic Control) view:
 * - Worker statuses
 * - File conflicts
 * - Progress tracking
 * - Pause/resume controls
 */

import { apiGet, apiPost } from '$lib/socket';
import { debounce } from '$lib/debounce';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface WorkerStatus {
  id: number;
  goal: string;
  status: string;
  progress: number;
  current_file: string | null;
  branch: string;
  goals_completed: number;
  goals_failed: number;
  last_heartbeat: string;
}

export interface FileConflict {
  path: string;
  worker_a: number;
  worker_b: number;
  conflict_type: string;
  resolution: string | null;
  detected_at: string;
}

export interface CoordinatorState {
  workers: WorkerStatus[];
  conflicts: FileConflict[];
  total_progress: number;
  merged_branches: string[];
  pending_merges: string[];
  is_running: boolean;
  started_at: string | null;
  last_update: string;
}

export interface StateDagNode {
  id: string;
  path: string;
  artifact_type: string;
  title: string;
  health_score: number;
  confidence_band: string;
  health_probes: Array<{
    probe_name: string;
    score: number;
    issues: string[];
  }>;
  last_modified: string | null;
  line_count: number | null;
}

export interface StateDagEdge {
  source: string;
  target: string;
  edge_type: string;
}

export interface StateDag {
  root: string;
  scanned_at: string;
  lens_name: string | null;
  overall_health: number;
  node_count: number;
  edge_count: number;
  unhealthy_count: number;
  critical_count: number;
  nodes: StateDagNode[];
  edges: StateDagEdge[];
  metadata: Record<string, unknown>;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const emptyState: CoordinatorState = {
  workers: [],
  conflicts: [],
  total_progress: 0,
  merged_branches: [],
  pending_merges: [],
  is_running: false,
  started_at: null,
  last_update: new Date().toISOString(),
};

let _state = $state<CoordinatorState>(emptyState);
let _isLoading = $state<boolean>(false);
let _error = $state<string | null>(null);
let _projectPath = $state<string | null>(null);
let _pollingInterval = $state<number | null>(null);

// State DAG state (RFC-100 Phase 0)
let _stateDag = $state<StateDag | null>(null);
let _stateDagLoading = $state<boolean>(false);
let _stateDagError = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

function getActiveWorkers(): WorkerStatus[] {
  return _state.workers.filter(
    (w) => w.status !== 'stopped' && w.status !== 'failed'
  );
}

function getRunningWorkers(): WorkerStatus[] {
  return _state.workers.filter((w) => w.status === 'executing');
}

function getCompletedGoals(): number {
  return _state.workers.reduce((sum, w) => sum + w.goals_completed, 0);
}

function getFailedGoals(): number {
  return _state.workers.reduce((sum, w) => sum + w.goals_failed, 0);
}

function hasConflicts(): boolean {
  return _state.conflicts.length > 0;
}

// State DAG computed
function getUnhealthyNodes(): StateDagNode[] {
  if (!_stateDag) return [];
  return _stateDag.nodes.filter((n) => n.health_score < 0.7);
}

function getCriticalNodes(): StateDagNode[] {
  if (!_stateDag) return [];
  return _stateDag.nodes.filter((n) => n.health_score < 0.5);
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const coordinatorStore = {
  // Raw state
  get state() {
    return _state;
  },
  get isLoading() {
    return _isLoading;
  },
  get error() {
    return _error;
  },
  get projectPath() {
    return _projectPath;
  },

  // Workers
  get workers() {
    return _state.workers;
  },
  get activeWorkers() {
    return getActiveWorkers();
  },
  get runningWorkers() {
    return getRunningWorkers();
  },

  // Progress
  get totalProgress() {
    return _state.total_progress;
  },
  get completedGoals() {
    return getCompletedGoals();
  },
  get failedGoals() {
    return getFailedGoals();
  },

  // Conflicts
  get conflicts() {
    return _state.conflicts;
  },
  get hasConflicts() {
    return hasConflicts();
  },

  // Status
  get isRunning() {
    return _state.is_running;
  },
  get mergedBranches() {
    return _state.merged_branches;
  },
  get pendingMerges() {
    return _state.pending_merges;
  },

  // State DAG (RFC-100 Phase 0)
  get stateDag() {
    return _stateDag;
  },
  get stateDagLoading() {
    return _stateDagLoading;
  },
  get stateDagError() {
    return _stateDagError;
  },
  get unhealthyNodes() {
    return getUnhealthyNodes();
  },
  get criticalNodes() {
    return getCriticalNodes();
  },
  get overallHealth() {
    return _stateDag?.overall_health ?? 1.0;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set the project path for coordinator operations.
 */
export function setProjectPath(path: string): void {
  _projectPath = path;
}

/**
 * Load coordinator state from the backend.
 */
export async function loadCoordinatorState(): Promise<void> {
  if (!_projectPath) {
    _error = 'No project path set';
    return;
  }

  _isLoading = true;
  _error = null;

  try {
    const state = await apiGet<CoordinatorState>(`/api/coordinator/state?path=${encodeURIComponent(_projectPath)}`);
    if (state) _state = state;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Failed to load coordinator state:', e);
  } finally {
    _isLoading = false;
  }
}

/**
 * Debounced state reload for rapid event handling.
 */
export const reloadState = debounce(loadCoordinatorState, 100);

/**
 * Start polling for coordinator state updates.
 */
export function startPolling(intervalMs: number = 1000): void {
  if (_pollingInterval !== null) {
    stopPolling();
  }

  _pollingInterval = window.setInterval(() => {
    loadCoordinatorState();
  }, intervalMs);

  // Initial load
  loadCoordinatorState();
}

/**
 * Stop polling for state updates.
 */
export function stopPolling(): void {
  if (_pollingInterval !== null) {
    clearInterval(_pollingInterval);
    _pollingInterval = null;
  }
}

/**
 * Pause a specific worker.
 */
export async function pauseWorker(workerId: number): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    await apiPost('/api/coordinator/pause-worker', {
      projectPath: _projectPath,
      workerId,
    });
    // Reload state after action
    await loadCoordinatorState();
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Resume a paused worker.
 */
export async function resumeWorker(workerId: number): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    await apiPost('/api/coordinator/resume-worker', {
      projectPath: _projectPath,
      workerId,
    });
    await loadCoordinatorState();
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Start parallel execution with multiple workers.
 */
export async function startWorkers(
  numWorkers: number,
  dryRun: boolean = false
): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    await apiPost('/api/coordinator/start-workers', {
      projectPath: _projectPath,
      numWorkers,
      dryRun,
    });
    await loadCoordinatorState();
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Clear coordinator state and stop polling.
 */
export function clearState(): void {
  stopPolling();
  _state = emptyState;
  _error = null;
  _projectPath = null;
}

// ═══════════════════════════════════════════════════════════════
// STATE DAG ACTIONS (RFC-100 Phase 0)
// ═══════════════════════════════════════════════════════════════

/**
 * Load the State DAG for a project (brownfield scanning).
 */
export async function loadStateDag(projectPath?: string): Promise<void> {
  const path = projectPath ?? _projectPath;
  if (!path) {
    _stateDagError = 'No project path set';
    return;
  }

  _stateDagLoading = true;
  _stateDagError = null;

  try {
    const dag = await apiGet<StateDag>(`/api/coordinator/state-dag?path=${encodeURIComponent(path)}`);
    if (dag) _stateDag = dag;
    _projectPath = path;
  } catch (e) {
    _stateDagError = e instanceof Error ? e.message : String(e);
    console.error('Failed to load State DAG:', e);
  } finally {
    _stateDagLoading = false;
  }
}

/**
 * Clear the State DAG.
 */
export function clearStateDag(): void {
  _stateDag = null;
  _stateDagError = null;
}

/**
 * Get a node by ID from the State DAG.
 */
export function getStateDagNode(nodeId: string): StateDagNode | undefined {
  return _stateDag?.nodes.find((n) => n.id === nodeId);
}

/**
 * Get nodes connected to a given node.
 */
export function getConnectedNodes(nodeId: string): {
  parents: StateDagNode[];
  children: StateDagNode[];
} {
  if (!_stateDag) return { parents: [], children: [] };

  const parents: StateDagNode[] = [];
  const children: StateDagNode[] = [];

  for (const edge of _stateDag.edges) {
    if (edge.target === nodeId) {
      const parent = _stateDag.nodes.find((n) => n.id === edge.source);
      if (parent) parents.push(parent);
    }
    if (edge.source === nodeId) {
      const child = _stateDag.nodes.find((n) => n.id === edge.target);
      if (child) children.push(child);
    }
  }

  return { parents, children };
}
