/**
 * DAG Store — manages planning view state and graph layout (Svelte 5 runes)
 * 
 * RFC-074: Extended with incremental execution state for skip/execute visualization.
 * RFC-094: Added debounced reload for backlog event handling.
 * RFC-105: Added hierarchical DAG support (Project → Workspace → Environment).
 */

import dagre from 'dagre';
import { apiGet, apiPost } from '$lib/socket';
import { DagNodeStatus, DagViewMode } from '$lib/constants';
import type { DagNodeStatus as DagNodeStatusType, DagViewMode as DagViewModeType } from '$lib/constants';
import { debounce } from '$lib/debounce';
import type { 
  DagGraph, 
  DagNode, 
  DagViewState, 
  IncrementalPlan,
  IncrementalStatus,
  // RFC-105: Hierarchical DAG types
  DagViewLevel,
  DagIndex,
  GoalSummary,
  GoalNode,
  WorkspaceDagIndex,
  EnvironmentDag,
} from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const NODE_WIDTH = 180;
const NODE_HEIGHT = 80;
const NODE_MARGIN_X = 50;
const NODE_MARGIN_Y = 40;

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const initialGraph: DagGraph = { nodes: [], edges: [], goal: undefined, totalProgress: 0 };
const initialViewState: DagViewState = { mode: DagViewMode.DAG, selectedNodeId: null, hoveredNodeId: null, zoom: 1, pan: { x: 0, y: 0 }, showCompleted: true };

let _graph = $state<DagGraph>(initialGraph);
let _viewState = $state<DagViewState>(initialViewState);

// RFC-074: Incremental execution state
let _incrementalPlan = $state<IncrementalPlan | null>(null);
let _isPlanLoading = $state<boolean>(false);
let _planError = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// RFC-105: HIERARCHICAL DAG STATE
// ═══════════════════════════════════════════════════════════════

let _viewLevel = $state<DagViewLevel>('project');

// Project level (detailed, fast index)
let _projectIndex = $state<DagIndex | null>(null);
let _projectPath = $state<string | null>(null);
let _expandedGoals = $state<Map<string, GoalNode>>(new Map());
let _isLoadingProjectIndex = $state<boolean>(false);
let _projectIndexError = $state<string | null>(null);

// Workspace level (aggregated)
let _workspaceIndex = $state<WorkspaceDagIndex | null>(null);
let _workspacePath = $state<string | null>(null);
let _isLoadingWorkspace = $state<boolean>(false);
let _workspaceError = $state<string | null>(null);

// Environment level (overview)
let _environmentDag = $state<EnvironmentDag | null>(null);
let _isLoadingEnvironment = $state<boolean>(false);
let _environmentError = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// NODE INDEX (O(1) lookups)
// ═══════════════════════════════════════════════════════════════

/** Derived node index for O(1) lookups by ID */
let _nodeIndex = $derived(new Map(_graph.nodes.map(n => [n.id, n])));

// ═══════════════════════════════════════════════════════════════
// LAYOUT COMPUTATION
// ═══════════════════════════════════════════════════════════════

function computeLayout(graph: DagGraph): DagGraph {
  if (graph.nodes.length === 0) return graph;
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: NODE_MARGIN_X, ranksep: NODE_MARGIN_Y, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const node of graph.nodes) g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT, label: node.id });
  for (const edge of graph.edges) g.setEdge(edge.source, edge.target);
  dagre.layout(g);
  const layoutedNodes = graph.nodes.map(node => {
    const layoutNode = g.node(node.id);
    return { ...node, x: layoutNode?.x ?? 0, y: layoutNode?.y ?? 0, width: NODE_WIDTH, height: NODE_HEIGHT };
  });
  const layoutedEdges = graph.edges.map(edge => {
    const layoutEdge = g.edge(edge.source, edge.target);
    return { ...edge, points: layoutEdge?.points ?? [] };
  });
  return { ...graph, nodes: layoutedNodes, edges: layoutedEdges };
}

// ═══════════════════════════════════════════════════════════════
// COMPUTED HELPERS
// ═══════════════════════════════════════════════════════════════

function getLayoutedGraph(): DagGraph { return computeLayout(_graph); }

function getSelectedNode(): DagNode | null {
  return _viewState.selectedNodeId ? _nodeIndex.get(_viewState.selectedNodeId) ?? null : null;
}

function getHoveredNode(): DagNode | null {
  return _viewState.hoveredNodeId ? _nodeIndex.get(_viewState.hoveredNodeId) ?? null : null;
}

function getWouldUnblock(): DagNode[] {
  if (!_viewState.hoveredNodeId) return [];
  const completedIds = new Set(_graph.nodes.filter(n => n.status === DagNodeStatus.COMPLETE).map(n => n.id));
  completedIds.add(_viewState.hoveredNodeId);
  return _graph.nodes.filter(node => {
    if (node.id === _viewState.hoveredNodeId) return false;
    if (node.status === DagNodeStatus.COMPLETE || node.status === DagNodeStatus.READY || node.status === DagNodeStatus.RUNNING) return false;
    return node.dependsOn.every(depId => completedIds.has(depId));
  });
}

function getCriticalPath(): Set<string> {
  const memo = new Map<string, string[]>();
  function longestPath(nodeId: string): string[] {
    if (memo.has(nodeId)) return memo.get(nodeId)!;
    const node = _nodeIndex.get(nodeId);
    if (!node || node.status === DagNodeStatus.COMPLETE) return [];
    const dependents = _graph.nodes.filter(n => n.dependsOn.includes(nodeId) && n.status !== DagNodeStatus.COMPLETE);
    if (dependents.length === 0) { const result = [nodeId]; memo.set(nodeId, result); return result; }
    let longest: string[] = [];
    for (const dep of dependents) { const path = longestPath(dep.id); if (path.length > longest.length) longest = path; }
    const result = [nodeId, ...longest];
    memo.set(nodeId, result);
    return result;
  }
  const roots = _graph.nodes.filter(n => n.dependsOn.length === 0 && n.status !== DagNodeStatus.COMPLETE);
  let critical: string[] = [];
  for (const root of roots) { const path = longestPath(root.id); if (path.length > critical.length) critical = path; }
  return new Set(critical);
}

function getBottlenecks(): Set<string> {
  const blockedCount = new Map<string, number>();
  for (const node of _graph.nodes) {
    if (node.status === DagNodeStatus.COMPLETE) continue;
    for (const depId of node.dependsOn) {
      const depNode = _nodeIndex.get(depId);
      if (depNode && depNode.status !== DagNodeStatus.COMPLETE) blockedCount.set(depId, (blockedCount.get(depId) ?? 0) + 1);
    }
  }
  return new Set(Array.from(blockedCount.entries()).filter(([, count]) => count >= 3).map(([id]) => id));
}

function getTotalProgress(): number {
  return _graph.nodes.length === 0 ? 0 : Math.round((_graph.nodes.filter(n => n.status === DagNodeStatus.COMPLETE).length / _graph.nodes.length) * 100);
}

// RFC-074: Incremental execution helpers
function getSkipSet(): Set<string> {
  return new Set(_incrementalPlan?.toSkip ?? []);
}

function getExecuteSet(): Set<string> {
  return new Set(_incrementalPlan?.toExecute ?? []);
}

function getNodeIncrementalStatus(nodeId: string): IncrementalStatus | undefined {
  if (!_incrementalPlan) return undefined;
  const decision = _incrementalPlan.decisions?.find(d => d.artifactId === nodeId);
  if (!decision) return undefined;
  return {
    canSkip: decision.canSkip,
    reason: decision.reason as IncrementalStatus['reason'],
    currentHash: decision.currentHash,
    previousHash: decision.previousHash,
    lastExecutedAt: decision.lastExecutedAt,
    skipCount: undefined, // Would need additional API call
  };
}

function getSkipPercentage(): number {
  return _incrementalPlan?.skipPercentage ?? 0;
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const dag = {
  // Graph data
  get nodes() { return _graph.nodes; },
  get edges() { return _graph.edges; },
  get goal() { return _graph.goal; },
  get totalProgress() { return getTotalProgress(); },
  // Loading state
  get isLoading() { return _isLoading; },
  get loadError() { return _loadError; },
  // Computed (layout applied)
  get layouted() { return getLayoutedGraph(); },
  get selectedNode() { return getSelectedNode(); },
  get hoveredNode() { return getHoveredNode(); },
  get wouldUnblock() { return getWouldUnblock(); },
  get criticalPath() { return getCriticalPath(); },
  get bottlenecks() { return getBottlenecks(); },
  // View state
  get mode() { return _viewState.mode; },
  get selectedNodeId() { return _viewState.selectedNodeId; },
  get hoveredNodeId() { return _viewState.hoveredNodeId; },
  get zoom() { return _viewState.zoom; },
  get pan() { return _viewState.pan; },
  get showCompleted() { return _viewState.showCompleted; },
  // RFC-074: Incremental execution state
  get incrementalPlan() { return _incrementalPlan; },
  get isPlanLoading() { return _isPlanLoading; },
  get planError() { return _planError; },
  get skipSet() { return getSkipSet(); },
  get executeSet() { return getExecuteSet(); },
  get skipPercentage() { return getSkipPercentage(); },
  getNodeIncrementalStatus,
  
  // ═══════════════════════════════════════════════════════════════
  // RFC-105: Hierarchical DAG state
  // ═══════════════════════════════════════════════════════════════
  
  /** Current view level (project | workspace | environment) */
  get viewLevel() { return _viewLevel; },
  
  // Project level (fast index)
  /** Project DAG index for fast loading */
  get projectIndex() { return _projectIndex; },
  get projectPath() { return _projectPath; },
  /** Expanded goal details (lazy loaded) */
  get expandedGoals() { return _expandedGoals; },
  get isLoadingProjectIndex() { return _isLoadingProjectIndex; },
  get projectIndexError() { return _projectIndexError; },
  
  // Workspace level (aggregated)
  get workspaceIndex() { return _workspaceIndex; },
  get workspacePath() { return _workspacePath; },
  get isLoadingWorkspace() { return _isLoadingWorkspace; },
  get workspaceError() { return _workspaceError; },
  
  // Environment level (overview)
  get environmentDag() { return _environmentDag; },
  get isLoadingEnvironment() { return _isLoadingEnvironment; },
  get environmentError() { return _environmentError; },
  
  // RFC-105: Computed helpers for hierarchical views
  /** Get total goals across all projects in workspace */
  get workspaceTotalGoals(): number {
    if (!_workspaceIndex) return 0;
    return _workspaceIndex.projects.reduce((sum, p) => sum + p.summary.totalGoals, 0);
  },
  /** Get completed goals across all projects in workspace */
  get workspaceCompletedGoals(): number {
    if (!_workspaceIndex) return 0;
    return _workspaceIndex.projects.reduce((sum, p) => sum + p.summary.completedGoals, 0);
  },
  /** Get workspace completion rate */
  get workspaceCompletionRate(): number {
    const total = this.workspaceTotalGoals;
    return total === 0 ? 0 : Math.round((this.workspaceCompletedGoals / total) * 100);
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export function setGraph(graph: DagGraph): void { _graph = graph; }

export function updateNode(nodeId: string, updates: Partial<DagNode>): void {
  _graph = { ..._graph, nodes: _graph.nodes.map(n => n.id === nodeId ? { ...n, ...updates } : n) };
}

export function completeNode(nodeId: string): void {
  const nodes = _graph.nodes.map(n => n.id === nodeId ? { ...n, status: DagNodeStatus.COMPLETE as DagNodeStatusType, progress: 100 } : n);
  const completedIds = new Set(nodes.filter(n => n.status === DagNodeStatus.COMPLETE).map(n => n.id));
  _graph = {
    ..._graph,
    nodes: nodes.map(n => {
      if (n.status === DagNodeStatus.PENDING || n.status === DagNodeStatus.BLOCKED) {
        if (n.dependsOn.every(d => completedIds.has(d))) return { ...n, status: DagNodeStatus.READY as DagNodeStatusType };
      }
      return n;
    }),
  };
}

export function selectNode(nodeId: string | null): void { _viewState = { ..._viewState, selectedNodeId: nodeId }; }
export function hoverNode(nodeId: string | null): void { _viewState = { ..._viewState, hoveredNodeId: nodeId }; }
export function setViewMode(mode: DagViewModeType): void { _viewState = { ..._viewState, mode }; }
export function setZoom(zoom: number): void { _viewState = { ..._viewState, zoom: Math.max(0.25, Math.min(2, zoom)) }; }
export function setPan(x: number, y: number): void { _viewState = { ..._viewState, pan: { x, y } }; }
export function toggleShowCompleted(): void { _viewState = { ..._viewState, showCompleted: !_viewState.showCompleted }; }
export function resetView(): void { _viewState = initialViewState; }

export function loadDemoGraph(): void {
  const demoGraph: DagGraph = {
    goal: 'Build a forum app with users, posts, and comments',
    nodes: [
      { id: 'user-model', title: 'User Model', description: 'Create User model', status: 'complete', source: 'ai', progress: 100, priority: 1.0, effort: 'small', dependsOn: [], category: 'models' },
      { id: 'post-model', title: 'Post Model', description: 'Create Post model', status: 'running', source: 'ai', progress: 65, priority: 0.9, effort: 'small', dependsOn: ['user-model'], category: 'models', currentAction: 'Adding validation...' },
      { id: 'comment-model', title: 'Comment Model', description: 'Create Comment model', status: 'complete', source: 'ai', progress: 100, priority: 0.8, effort: 'small', dependsOn: ['user-model'], category: 'models' },
      { id: 'auth-system', title: 'Auth System', description: 'JWT auth', status: 'ready', source: 'ai', progress: 0, priority: 0.95, effort: 'medium', dependsOn: ['user-model'], category: 'auth' },
      { id: 'post-crud', title: 'Post CRUD', description: 'CRUD for posts', status: 'blocked', source: 'ai', progress: 0, priority: 0.85, effort: 'medium', dependsOn: ['post-model', 'auth-system'], category: 'routes' },
      { id: 'comment-crud', title: 'Comment CRUD', description: 'CRUD for comments', status: 'blocked', source: 'ai', progress: 0, priority: 0.75, effort: 'medium', dependsOn: ['comment-model', 'post-crud'], category: 'routes' },
    ],
    edges: [
      { id: 'e1', source: 'user-model', target: 'post-model', artifact: 'User' },
      { id: 'e2', source: 'user-model', target: 'comment-model', artifact: 'User' },
      { id: 'e3', source: 'user-model', target: 'auth-system', artifact: 'User' },
      { id: 'e4', source: 'post-model', target: 'post-crud', artifact: 'Post' },
      { id: 'e5', source: 'auth-system', target: 'post-crud', artifact: 'AuthMiddleware' },
      { id: 'e6', source: 'comment-model', target: 'comment-crud', artifact: 'Comment' },
      { id: 'e7', source: 'post-crud', target: 'comment-crud', artifact: 'PostContext' },
    ],
  };
  setGraph(demoGraph);
}

export function clearGraph(): void { 
  _graph = initialGraph; 
  _viewState = initialViewState; 
  _incrementalPlan = null; 
  _planError = null;
  _isLoading = false;
  _loadError = null;
}

// RFC-094: Store current project path for reload
let _currentProjectPath: string | null = null;
let _isLoading = $state(false);
let _loadError = $state<string | null>(null);

/**
 * Set the current project path for DAG operations.
 * Clears stale graph data when switching projects.
 */
export function setProjectPath(path: string | null): void {
  // If switching to a different project, clear the old graph to prevent stale data
  if (path !== _currentProjectPath) {
    clearGraph();
    _currentProjectPath = path;
    _loadError = null;
    
    // If we have a new path, trigger a reload
    if (path) {
      reloadDagInternal();
    }
  }
}

/**
 * Reload the DAG from the backend (RFC-094).
 *
 * Called by event handlers when backlog changes.
 */
async function reloadDagInternal(): Promise<void> {
  if (!_currentProjectPath) return;
  if (_isLoading) return; // Prevent concurrent loads

  _isLoading = true;
  _loadError = null;
  
  try {
    const graph = await apiGet<DagGraph>(`/api/dag?path=${encodeURIComponent(_currentProjectPath)}`);
    if (graph) setGraph(graph);
  } catch (e) {
    console.error('Failed to reload DAG:', e);
    _loadError = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoading = false;
  }
}

/**
 * Debounced DAG reload (100ms) to handle rapid event bursts (RFC-094).
 */
export const reloadDag = debounce(reloadDagInternal, 100);

/**
 * Immediate DAG reload for manual refresh (RFC-094).
 */
export const reloadDagImmediate = reloadDagInternal;

// RFC-074: Incremental execution actions
export function setIncrementalPlan(plan: IncrementalPlan | null): void { 
  _incrementalPlan = plan;
  _planError = null;
}

export function setPlanLoading(loading: boolean): void { 
  _isPlanLoading = loading; 
}

export function setPlanError(error: string | null): void { 
  _planError = error;
  _isPlanLoading = false;
}

export function clearIncrementalPlan(): void {
  _incrementalPlan = null;
  _planError = null;
  _isPlanLoading = false;
}

// ═══════════════════════════════════════════════════════════════
// RFC-105: HIERARCHICAL DAG ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set the view level for hierarchical DAG display.
 */
export function setViewLevel(level: DagViewLevel): void {
  _viewLevel = level;
}

/**
 * Load project DAG index for fast initial display (RFC-105).
 * 
 * This loads only the index (~1KB) for quick project switching.
 * Target: <10ms cold load.
 */
export async function loadProjectDagIndex(path: string): Promise<void> {
  if (_isLoadingProjectIndex) return;
  
  // Clear stale data if switching projects
  if (path !== _projectPath) {
    _projectIndex = null;
    _expandedGoals = new Map();
    _projectIndexError = null;
  }
  
  _projectPath = path;
  _isLoadingProjectIndex = true;
  _projectIndexError = null;
  
  try {
    const index = await apiGet<DagIndex>(`/api/dag/index?path=${encodeURIComponent(path)}`);
    if (index) _projectIndex = index;
  } catch (e) {
    console.error('Failed to load project DAG index:', e);
    _projectIndexError = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoadingProjectIndex = false;
  }
}

/**
 * Expand a goal to load its full details (RFC-105).
 * 
 * Lazy loads the complete goal data when user expands a goal in the UI.
 */
export async function expandGoal(goalId: string): Promise<GoalNode | null> {
  if (!_projectPath) return null;
  
  // Check if already loaded
  const existing = _expandedGoals.get(goalId);
  if (existing) return existing;
  
  try {
    const goal = await apiGet<GoalNode>(`/api/dag/goal/${goalId}?path=${encodeURIComponent(_projectPath)}`);
    if (!goal) return null;
    
    // Update expanded goals map
    _expandedGoals = new Map(_expandedGoals).set(goalId, goal);
    return goal;
  } catch (e) {
    console.error(`Failed to load goal ${goalId}:`, e);
    return null;
  }
}

/**
 * Collapse a goal to free memory (RFC-105).
 */
export function collapseGoal(goalId: string): void {
  const newMap = new Map(_expandedGoals);
  newMap.delete(goalId);
  _expandedGoals = newMap;
}

/**
 * Load workspace DAG index (RFC-105).
 * 
 * Aggregates project indexes from all projects in the workspace.
 */
export async function loadWorkspaceDag(path: string): Promise<void> {
  if (_isLoadingWorkspace) return;
  
  _workspacePath = path;
  _isLoadingWorkspace = true;
  _workspaceError = null;
  
  try {
    const index = await apiGet<WorkspaceDagIndex>(`/api/dag/workspace?path=${encodeURIComponent(path)}`);
    if (index) _workspaceIndex = index;
  } catch (e) {
    console.error('Failed to load workspace DAG:', e);
    _workspaceError = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoadingWorkspace = false;
  }
}

/**
 * Refresh workspace index by re-scanning all projects (RFC-105).
 */
export async function refreshWorkspaceIndex(): Promise<void> {
  if (!_workspacePath || _isLoadingWorkspace) return;
  
  _isLoadingWorkspace = true;
  _workspaceError = null;
  
  try {
    const index = await apiPost<WorkspaceDagIndex>('/api/dag/workspace/refresh', { path: _workspacePath });
    if (index) _workspaceIndex = index;
  } catch (e) {
    console.error('Failed to refresh workspace index:', e);
    _workspaceError = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoadingWorkspace = false;
  }
}

/**
 * Load environment-level DAG overview (RFC-105).
 */
export async function loadEnvironmentDag(): Promise<void> {
  if (_isLoadingEnvironment) return;
  
  _isLoadingEnvironment = true;
  _environmentError = null;
  
  try {
    const env = await apiGet<EnvironmentDag>('/api/dag/environment');
    if (env) _environmentDag = env;
  } catch (e) {
    console.error('Failed to load environment DAG:', e);
    _environmentError = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoadingEnvironment = false;
  }
}

/**
 * Clear all hierarchical DAG state (RFC-105).
 */
export function clearHierarchicalState(): void {
  _viewLevel = 'project';
  _projectIndex = null;
  _projectPath = null;
  _expandedGoals = new Map();
  _isLoadingProjectIndex = false;
  _projectIndexError = null;
  _workspaceIndex = null;
  _workspacePath = null;
  _isLoadingWorkspace = false;
  _workspaceError = null;
  _environmentDag = null;
  _isLoadingEnvironment = false;
  _environmentError = null;
}

/**
 * Get a goal summary by ID from the current project index.
 */
export function getGoalSummary(goalId: string): GoalSummary | undefined {
  return _projectIndex?.goals.find(g => g.id === goalId);
}

/**
 * Get all goals sorted by status (in-progress first, then pending, then complete).
 */
export function getSortedGoals(): GoalSummary[] {
  if (!_projectIndex) return [];
  
  const statusOrder: Record<string, number> = {
    'running': 0,
    'in_progress': 1,
    'pending': 2,
    'ready': 3,
    'complete': 4,
    'failed': 5,
  };
  
  return [..._projectIndex.goals].sort((a, b) => {
    const orderA = statusOrder[a.status] ?? 10;
    const orderB = statusOrder[b.status] ?? 10;
    return orderA - orderB;
  });
}
