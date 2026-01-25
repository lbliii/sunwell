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
  readonly id: number;
  readonly goal: string;
  readonly status: string;
  readonly progress: number;
  readonly current_file: string | null;
  readonly branch: string;
  readonly goals_completed: number;
  readonly goals_failed: number;
  readonly last_heartbeat: string;
}

export interface FileConflict {
  readonly path: string;
  readonly worker_a: number;
  readonly worker_b: number;
  readonly conflict_type: string;
  readonly resolution: string | null;
  readonly detected_at: string;
}

export interface CoordinatorState {
  readonly workers: readonly WorkerStatus[];
  readonly conflicts: readonly FileConflict[];
  readonly total_progress: number;
  readonly merged_branches: readonly string[];
  readonly pending_merges: readonly string[];
  readonly is_running: boolean;
  readonly started_at: string | null;
  readonly last_update: string;
}

export interface StateDagNode {
  readonly id: string;
  readonly path: string;
  readonly artifact_type: string;
  readonly title: string;
  readonly health_score: number;
  readonly confidence_band: string;
  readonly health_probes: ReadonlyArray<{
    readonly probe_name: string;
    readonly score: number;
    readonly issues: readonly string[];
  }>;
  readonly last_modified: string | null;
  readonly line_count: number | null;
}

export interface StateDagEdge {
  readonly source: string;
  readonly target: string;
  readonly edge_type: string;
}

export interface StateDag {
  readonly root: string;
  readonly scanned_at: string;
  readonly lens_name: string | null;
  readonly overall_health: number;
  readonly node_count: number;
  readonly edge_count: number;
  readonly unhealthy_count: number;
  readonly critical_count: number;
  readonly nodes: readonly StateDagNode[];
  readonly edges: readonly StateDagEdge[];
  readonly metadata: Readonly<Record<string, unknown>>;
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

// Cached node index for O(1) lookups
let _nodeMapCache: Map<string, StateDagNode> | null = null;
let _nodeMapCacheRef: readonly StateDagNode[] | null = null;

function getNodeMap(): Map<string, StateDagNode> {
  if (!_stateDag) return new Map();
  if (_nodeMapCacheRef !== _stateDag.nodes) {
    _nodeMapCache = new Map(_stateDag.nodes.map(n => [n.id, n]));
    _nodeMapCacheRef = _stateDag.nodes;
  }
  return _nodeMapCache!;
}

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

function getActiveWorkers(): WorkerStatus[] {
  const workers = _state.workers;
  if (!Array.isArray(workers)) return [];
  return workers.filter(
    (w) => w.status !== 'stopped' && w.status !== 'failed'
  );
}

function getRunningWorkers(): WorkerStatus[] {
  const workers = _state.workers;
  if (!Array.isArray(workers)) return [];
  return workers.filter((w) => w.status === 'executing');
}

function getCompletedGoals(): number {
  const workers = _state.workers;
  if (!Array.isArray(workers)) return 0;
  return workers.reduce((sum, w) => sum + w.goals_completed, 0);
}

function getFailedGoals(): number {
  const workers = _state.workers;
  if (!Array.isArray(workers)) return 0;
  return workers.reduce((sum, w) => sum + w.goals_failed, 0);
}

function hasConflicts(): boolean {
  const conflicts = _state.conflicts;
  return Array.isArray(conflicts) && conflicts.length > 0;
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
 * Get a node by ID from the State DAG - O(1) lookup via cached Map.
 */
export function getStateDagNode(nodeId: string): StateDagNode | undefined {
  return getNodeMap().get(nodeId);
}

/**
 * Get nodes connected to a given node - O(n) edges with O(1) node lookups.
 */
export function getConnectedNodes(nodeId: string): {
  parents: StateDagNode[];
  children: StateDagNode[];
} {
  if (!_stateDag) return { parents: [], children: [] };

  const edges = _stateDag.edges;
  if (!Array.isArray(edges)) return { parents: [], children: [] };

  const nodeMap = getNodeMap();
  const parents: StateDagNode[] = [];
  const children: StateDagNode[] = [];

  for (const edge of edges) {
    if (edge.target === nodeId) {
      const parent = nodeMap.get(edge.source);
      if (parent) parents.push(parent);
    }
    if (edge.source === nodeId) {
      const child = nodeMap.get(edge.target);
      if (child) children.push(child);
    }
  }

  return { parents, children };
}
