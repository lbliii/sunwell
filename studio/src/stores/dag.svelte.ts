/**
 * DAG Store — manages planning view state and graph layout (Svelte 5 runes)
 * 
 * RFC-074: Extended with incremental execution state for skip/execute visualization.
 * RFC-094: Added debounced reload for backlog event handling.
 */

import dagre from 'dagre';
import { invoke } from '@tauri-apps/api/core';
import { DagNodeStatus, DagViewMode } from '$lib/constants';
import type { DagNodeStatus as DagNodeStatusType, DagViewMode as DagViewModeType } from '$lib/constants';
import { debounce } from '$lib/debounce';
import type { 
  DagGraph, 
  DagNode, 
  DagViewState, 
  IncrementalPlan,
  IncrementalStatus 
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
  return _viewState.selectedNodeId ? _graph.nodes.find(n => n.id === _viewState.selectedNodeId) ?? null : null;
}

function getHoveredNode(): DagNode | null {
  return _viewState.hoveredNodeId ? _graph.nodes.find(n => n.id === _viewState.hoveredNodeId) ?? null : null;
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
    const node = _graph.nodes.find(n => n.id === nodeId);
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
      const depNode = _graph.nodes.find(n => n.id === depId);
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

export function clearGraph(): void { _graph = initialGraph; _viewState = initialViewState; _incrementalPlan = null; _planError = null; }

// RFC-094: Store current project path for reload
let _currentProjectPath: string | null = null;

export function setProjectPath(path: string | null): void {
  _currentProjectPath = path;
}

/**
 * Reload the DAG from the backend (RFC-094).
 *
 * Called by event handlers when backlog changes.
 */
async function reloadDagInternal(): Promise<void> {
  if (!_currentProjectPath) return;

  try {
    const graph = await invoke<DagGraph>('get_project_dag', { path: _currentProjectPath });
    setGraph(graph);
  } catch (e) {
    console.error('Failed to reload DAG:', e);
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
