/**
 * DAG Store — manages planning view state and graph layout
 * 
 * Uses dagre for automatic layout computation.
 */

import { writable, derived, get } from 'svelte/store';
import dagre from 'dagre';
import type { 
  DagGraph, 
  DagNode, 
  DagEdge, 
  DagViewState,
  DagNodeStatus,
  DagViewMode
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

const initialGraph: DagGraph = {
  nodes: [],
  edges: [],
  goal: undefined,
  totalProgress: 0,
};

const initialViewState: DagViewState = {
  mode: 'dag',
  selectedNodeId: null,
  hoveredNodeId: null,
  zoom: 1,
  pan: { x: 0, y: 0 },
  showCompleted: true,
};

export const dagGraph = writable<DagGraph>(initialGraph);
export const dagViewState = writable<DagViewState>(initialViewState);

// ═══════════════════════════════════════════════════════════════
// DERIVED
// ═══════════════════════════════════════════════════════════════

/** Nodes with layout applied */
export const layoutedGraph = derived(dagGraph, $graph => {
  return computeLayout($graph);
});

/** Selected node details */
export const selectedNode = derived(
  [dagGraph, dagViewState],
  ([$graph, $view]) => {
    if (!$view.selectedNodeId) return null;
    return $graph.nodes.find(n => n.id === $view.selectedNodeId) ?? null;
  }
);

/** Hovered node details */
export const hoveredNode = derived(
  [dagGraph, dagViewState],
  ([$graph, $view]) => {
    if (!$view.hoveredNodeId) return null;
    return $graph.nodes.find(n => n.id === $view.hoveredNodeId) ?? null;
  }
);

/** Nodes that would be unblocked if hovered node completes */
export const wouldUnblock = derived(
  [dagGraph, dagViewState],
  ([$graph, $view]) => {
    if (!$view.hoveredNodeId) return [];
    
    const completedIds = new Set(
      $graph.nodes
        .filter(n => n.status === 'complete')
        .map(n => n.id)
    );
    
    // Add the hovered node as if it were complete
    completedIds.add($view.hoveredNodeId);
    
    // Find nodes that would become ready
    return $graph.nodes.filter(node => {
      if (node.id === $view.hoveredNodeId) return false;
      if (node.status === 'complete') return false;
      if (node.status === 'ready' || node.status === 'running') return false;
      
      // Check if all dependencies would be met
      return node.dependsOn.every(depId => completedIds.has(depId));
    });
  }
);

/** Critical path (longest path to completion) */
export const criticalPath = derived(dagGraph, $graph => {
  // Simple longest path algorithm
  const memo = new Map<string, string[]>();
  
  function longestPath(nodeId: string): string[] {
    if (memo.has(nodeId)) return memo.get(nodeId)!;
    
    const node = $graph.nodes.find(n => n.id === nodeId);
    if (!node) return [];
    if (node.status === 'complete') return [];
    
    // Find dependents (nodes that depend on this)
    const dependents = $graph.nodes.filter(n => 
      n.dependsOn.includes(nodeId) && n.status !== 'complete'
    );
    
    if (dependents.length === 0) {
      const result = [nodeId];
      memo.set(nodeId, result);
      return result;
    }
    
    // Find longest path through dependents
    let longest: string[] = [];
    for (const dep of dependents) {
      const path = longestPath(dep.id);
      if (path.length > longest.length) {
        longest = path;
      }
    }
    
    const result = [nodeId, ...longest];
    memo.set(nodeId, result);
    return result;
  }
  
  // Find roots (no dependencies)
  const roots = $graph.nodes.filter(n => 
    n.dependsOn.length === 0 && n.status !== 'complete'
  );
  
  let criticalPath: string[] = [];
  for (const root of roots) {
    const path = longestPath(root.id);
    if (path.length > criticalPath.length) {
      criticalPath = path;
    }
  }
  
  return new Set(criticalPath);
});

/** Bottleneck nodes (block many others) */
export const bottlenecks = derived(dagGraph, $graph => {
  const blockedCount = new Map<string, number>();
  
  for (const node of $graph.nodes) {
    if (node.status === 'complete') continue;
    
    for (const depId of node.dependsOn) {
      const depNode = $graph.nodes.find(n => n.id === depId);
      if (depNode && depNode.status !== 'complete') {
        blockedCount.set(depId, (blockedCount.get(depId) ?? 0) + 1);
      }
    }
  }
  
  // Return nodes that block 3+ others
  return new Set(
    Array.from(blockedCount.entries())
      .filter(([_, count]) => count >= 3)
      .map(([id]) => id)
  );
});

/** Overall progress */
export const totalProgress = derived(dagGraph, $graph => {
  if ($graph.nodes.length === 0) return 0;
  
  const completed = $graph.nodes.filter(n => n.status === 'complete').length;
  return Math.round((completed / $graph.nodes.length) * 100);
});

// ═══════════════════════════════════════════════════════════════
// LAYOUT
// ═══════════════════════════════════════════════════════════════

function computeLayout(graph: DagGraph): DagGraph {
  if (graph.nodes.length === 0) return graph;
  
  // Create dagre graph
  const g = new dagre.graphlib.Graph();
  g.setGraph({ 
    rankdir: 'TB',  // Top to bottom
    nodesep: NODE_MARGIN_X,
    ranksep: NODE_MARGIN_Y,
    marginx: 40,
    marginy: 40,
  });
  g.setDefaultEdgeLabel(() => ({}));
  
  // Add nodes
  for (const node of graph.nodes) {
    g.setNode(node.id, { 
      width: NODE_WIDTH, 
      height: NODE_HEIGHT,
      label: node.id,
    });
  }
  
  // Add edges
  for (const edge of graph.edges) {
    g.setEdge(edge.source, edge.target);
  }
  
  // Compute layout
  dagre.layout(g);
  
  // Extract positions
  const layoutedNodes = graph.nodes.map(node => {
    const layoutNode = g.node(node.id);
    return {
      ...node,
      x: layoutNode?.x ?? 0,
      y: layoutNode?.y ?? 0,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    };
  });
  
  // Extract edge points
  const layoutedEdges = graph.edges.map(edge => {
    const layoutEdge = g.edge(edge.source, edge.target);
    return {
      ...edge,
      points: layoutEdge?.points ?? [],
    };
  });
  
  return {
    ...graph,
    nodes: layoutedNodes,
    edges: layoutedEdges,
  };
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/** Set the entire graph */
export function setGraph(graph: DagGraph): void {
  dagGraph.set(graph);
}

/** Update a single node */
export function updateNode(nodeId: string, updates: Partial<DagNode>): void {
  dagGraph.update(g => ({
    ...g,
    nodes: g.nodes.map(n => 
      n.id === nodeId ? { ...n, ...updates } : n
    ),
  }));
}

/** Mark a node as complete */
export function completeNode(nodeId: string): void {
  dagGraph.update(g => {
    const nodes = g.nodes.map(n => {
      if (n.id === nodeId) {
        return { ...n, status: 'complete' as DagNodeStatus, progress: 100 };
      }
      return n;
    });
    
    // Update ready status for dependents
    const completedIds = new Set(nodes.filter(n => n.status === 'complete').map(n => n.id));
    
    return {
      ...g,
      nodes: nodes.map(n => {
        if (n.status === 'pending' || n.status === 'blocked') {
          const allDepsMet = n.dependsOn.every(d => completedIds.has(d));
          if (allDepsMet) {
            return { ...n, status: 'ready' as DagNodeStatus };
          }
        }
        return n;
      }),
    };
  });
}

/** Select a node */
export function selectNode(nodeId: string | null): void {
  dagViewState.update(s => ({ ...s, selectedNodeId: nodeId }));
}

/** Hover a node */
export function hoverNode(nodeId: string | null): void {
  dagViewState.update(s => ({ ...s, hoveredNodeId: nodeId }));
}

/** Set view mode */
export function setViewMode(mode: DagViewMode): void {
  dagViewState.update(s => ({ ...s, mode }));
}

/** Set zoom level */
export function setZoom(zoom: number): void {
  dagViewState.update(s => ({ ...s, zoom: Math.max(0.25, Math.min(2, zoom)) }));
}

/** Pan the view */
export function setPan(x: number, y: number): void {
  dagViewState.update(s => ({ ...s, pan: { x, y } }));
}

/** Toggle show completed */
export function toggleShowCompleted(): void {
  dagViewState.update(s => ({ ...s, showCompleted: !s.showCompleted }));
}

/** Reset view */
export function resetView(): void {
  dagViewState.set(initialViewState);
}

// ═══════════════════════════════════════════════════════════════
// DEMO DATA
// ═══════════════════════════════════════════════════════════════

export function loadDemoGraph(): void {
  const demoGraph: DagGraph = {
    goal: 'Build a forum app with users, posts, and comments',
    nodes: [
      {
        id: 'user-model',
        title: 'User Model',
        description: 'Create User model with authentication fields',
        status: 'complete',
        source: 'ai',
        progress: 100,
        priority: 1.0,
        effort: 'small',
        dependsOn: [],
        category: 'models',
      },
      {
        id: 'post-model',
        title: 'Post Model',
        description: 'Create Post model with title, content, author',
        status: 'running',
        source: 'ai',
        progress: 65,
        priority: 0.9,
        effort: 'small',
        dependsOn: ['user-model'],
        category: 'models',
        currentAction: 'Adding validation...',
      },
      {
        id: 'comment-model',
        title: 'Comment Model',
        description: 'Create Comment model linked to posts',
        status: 'complete',
        source: 'ai',
        progress: 100,
        priority: 0.8,
        effort: 'small',
        dependsOn: ['user-model'],
        category: 'models',
      },
      {
        id: 'auth-system',
        title: 'Auth System',
        description: 'JWT authentication with refresh tokens',
        status: 'ready',
        source: 'ai',
        progress: 0,
        priority: 0.95,
        effort: 'medium',
        dependsOn: ['user-model'],
        category: 'auth',
      },
      {
        id: 'post-crud',
        title: 'Post CRUD',
        description: 'Create, read, update, delete posts',
        status: 'blocked',
        source: 'ai',
        progress: 0,
        priority: 0.85,
        effort: 'medium',
        dependsOn: ['post-model', 'auth-system'],
        category: 'routes',
      },
      {
        id: 'comment-crud',
        title: 'Comment CRUD',
        description: 'Create, read, update, delete comments',
        status: 'blocked',
        source: 'ai',
        progress: 0,
        priority: 0.75,
        effort: 'medium',
        dependsOn: ['comment-model', 'post-crud'],
        category: 'routes',
      },
      {
        id: 'rate-limiter',
        title: 'Rate Limiting',
        description: 'Add rate limiting to API endpoints',
        status: 'blocked',
        source: 'ai',
        progress: 0,
        priority: 0.6,
        effort: 'small',
        dependsOn: ['auth-system'],
        category: 'security',
      },
      {
        id: 'mobile-support',
        title: 'Mobile Support',
        description: 'Add responsive design for mobile',
        status: 'pending',
        source: 'human',
        progress: 0,
        priority: 0.4,
        effort: 'large',
        dependsOn: [],
        category: 'frontend',
      },
    ],
    edges: [
      { id: 'e1', source: 'user-model', target: 'post-model', artifact: 'User' },
      { id: 'e2', source: 'user-model', target: 'comment-model', artifact: 'User' },
      { id: 'e3', source: 'user-model', target: 'auth-system', artifact: 'User' },
      { id: 'e4', source: 'post-model', target: 'post-crud', artifact: 'Post' },
      { id: 'e5', source: 'auth-system', target: 'post-crud', artifact: 'AuthMiddleware' },
      { id: 'e6', source: 'comment-model', target: 'comment-crud', artifact: 'Comment' },
      { id: 'e7', source: 'post-crud', target: 'comment-crud', artifact: 'PostContext' },
      { id: 'e8', source: 'auth-system', target: 'rate-limiter', artifact: 'AuthContext' },
    ],
  };
  
  setGraph(demoGraph);
}

/** Clear the graph */
export function clearGraph(): void {
  dagGraph.set(initialGraph);
  dagViewState.set(initialViewState);
}
